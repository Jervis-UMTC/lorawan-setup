package fabricadapter

import (
	"context"
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"

	"github.com/hyperledger/fabric-gateway/pkg/client"
	"github.com/hyperledger/fabric-gateway/pkg/identity"
	gatewaypb "github.com/hyperledger/fabric-protos-go-apiv2/gateway"
	"github.com/hyperledger/fabric-protos-go-apiv2/msp"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"
)

const maxFabricExactPayloadBytes = 1_048_576

type FabricSubmitResult struct {
	TransactionID string
	Committed     bool
	Unknown       bool
}

type LedgerClient interface {
	Prepare(context.Context, FabricAnchor) (FabricPreparedSubmission, error)
	SubmitPrepared(context.Context, FabricPreparedSubmission) (FabricSubmitResult, error)
	CommitStatus(context.Context, string, []byte) (FabricSubmitResult, error)
	Query(context.Context, string, string) (FabricQueryResult, error)
	VerifyDigest(context.Context, string, string, string) (FabricVerifyResult, error)
	Close() error
}

type GatewayClient struct {
	connection *grpc.ClientConn
	gateway    *client.Gateway
	contract   *client.Contract
	submitName string
	queryName  string
	verifyName string
	channelID  string
	creator    []byte
	sign       identity.Sign
}

type hrcAnchorRecord struct {
	RecordID                    string `json:"record_id"`
	AuthenticatedSourceSystemID string `json:"authenticated_source_system_id"`
	SourceRecordID              string `json:"source_record_id"`
	DigestAlgorithm             string `json:"digest_algorithm"`
	Digest                      string `json:"digest"`
	PayloadLength               int    `json:"payload_length"`
	SourceType                  string `json:"source_type"`
	Producer                    string `json:"producer"`
	ProducedAt                  string `json:"produced_at"`
	SchemaVersion               string `json:"schema_version"`
}

type hrcCreateResponse struct {
	Outcome  string          `json:"outcome"`
	RecordID string          `json:"record_id"`
	Anchor   hrcAnchorRecord `json:"anchor"`
}

type hrcVerifyResponse struct {
	Outcome        string `json:"outcome"`
	RecordID       string `json:"record_id"`
	ExpectedDigest string `json:"expected_digest"`
	ObservedDigest string `json:"observed_digest"`
}

func NewGatewayClient(cfg Config) (*GatewayClient, error) {
	rootPEM, err := os.ReadFile(cfg.FabricTLSRootCert)
	if err != nil {
		return nil, errors.New("read Fabric TLS root certificate failed")
	}
	roots := x509.NewCertPool()
	if !roots.AppendCertsFromPEM(rootPEM) {
		return nil, errors.New("Fabric TLS root file contains no usable certificate")
	}
	tlsConfig := &tls.Config{
		MinVersion: tls.VersionTLS12,
		RootCAs:    roots,
		ServerName: cfg.FabricTLSServerName,
	}
	connection, err := grpc.NewClient(cfg.FabricEndpoint, grpc.WithTransportCredentials(credentials.NewTLS(tlsConfig)))
	if err != nil {
		return nil, fmt.Errorf("create Fabric Gateway gRPC connection: %w", err)
	}

	certificatePEM, err := os.ReadFile(cfg.FabricCertPath)
	if err != nil {
		_ = connection.Close()
		return nil, errors.New("read Fabric identity certificate failed")
	}
	certificate, err := identity.CertificateFromPEM(certificatePEM)
	if err != nil {
		_ = connection.Close()
		return nil, fmt.Errorf("parse Fabric identity certificate: %w", err)
	}
	clientIdentity, err := identity.NewX509Identity(cfg.FabricMSPID, certificate)
	if err != nil {
		_ = connection.Close()
		return nil, fmt.Errorf("create Fabric X509 identity: %w", err)
	}
	privateKeyPEM, err := os.ReadFile(cfg.FabricKeyPath)
	if err != nil {
		_ = connection.Close()
		return nil, errors.New("read Fabric identity private key failed")
	}
	privateKey, err := identity.PrivateKeyFromPEM(privateKeyPEM)
	if err != nil {
		_ = connection.Close()
		return nil, fmt.Errorf("parse Fabric identity private key: %w", err)
	}
	sign, err := identity.NewPrivateKeySign(privateKey)
	if err != nil {
		_ = connection.Close()
		return nil, fmt.Errorf("create Fabric identity signer: %w", err)
	}
	creator, err := proto.Marshal(&msp.SerializedIdentity{
		Mspid:   clientIdentity.MspID(),
		IdBytes: clientIdentity.Credentials(),
	})
	if err != nil {
		_ = connection.Close()
		return nil, fmt.Errorf("serialize Fabric client identity: %w", err)
	}

	gateway, err := client.Connect(
		clientIdentity,
		client.WithSign(sign),
		client.WithClientConnection(connection),
		client.WithEvaluateTimeout(cfg.CommitTimeout),
		client.WithEndorseTimeout(cfg.CommitTimeout),
		client.WithSubmitTimeout(cfg.CommitTimeout),
		client.WithCommitStatusTimeout(cfg.CommitTimeout),
	)
	if err != nil {
		_ = connection.Close()
		return nil, fmt.Errorf("connect Fabric Gateway client: %w", err)
	}
	network := gateway.GetNetwork(cfg.FabricChannel)
	var contract *client.Contract
	if cfg.FabricContract == "" {
		contract = network.GetContract(cfg.FabricChaincode)
	} else {
		contract = network.GetContractWithName(cfg.FabricChaincode, cfg.FabricContract)
	}
	return &GatewayClient{
		connection: connection,
		gateway:    gateway,
		contract:   contract,
		submitName: cfg.FabricSubmitFunction,
		queryName:  cfg.FabricQueryFunction,
		verifyName: cfg.FabricVerifyFunction,
		channelID:  cfg.FabricChannel,
		creator:    creator,
		sign:       sign,
	}, nil
}

func (c *GatewayClient) Close() error {
	var result error
	if c.gateway != nil {
		result = c.gateway.Close()
	}
	if c.connection != nil {
		if err := c.connection.Close(); err != nil && result == nil {
			result = err
		}
	}
	return result
}

// Prepare performs proposal construction and endorsement but never submits to the
// orderer. It returns all material required to durably record the transaction ID
// and later recover commit status before any submit attempt can occur.
func (c *GatewayClient) Prepare(ctx context.Context, anchor FabricAnchor) (FabricPreparedSubmission, error) {
	if len(anchor.ExactPayload) == 0 {
		return FabricPreparedSubmission{}, errors.New("exact payload is required for Fabric source-bound submission")
	}
	if len(anchor.ExactPayload) > maxFabricExactPayloadBytes {
		return FabricPreparedSubmission{}, fmt.Errorf("exact payload exceeds HRC maximum of %d bytes", maxFabricExactPayloadBytes)
	}
	args := []string{
		anchor.SourceRecordID,
		anchor.SourceType,
		anchor.Producer,
		anchor.ProducedAt,
		anchor.SchemaVersion,
	}
	proposal, err := c.contract.NewProposal(
		c.submitName,
		client.WithArguments(args...),
		client.WithTransient(map[string][]byte{"hrc.exact_payload": anchor.ExactPayload}),
	)
	if err != nil {
		return FabricPreparedSubmission{}, fmt.Errorf("prepare Fabric source-bound proposal: %w", err)
	}
	transaction, err := proposal.EndorseWithContext(ctx)
	if err != nil {
		return FabricPreparedSubmission{}, err
	}
	if transaction == nil || strings.TrimSpace(transaction.TransactionID()) == "" {
		return FabricPreparedSubmission{}, errors.New("Fabric endorsement returned no transaction ID")
	}
	create, err := decodeCreateResponse(transaction.Result(), anchor)
	if err != nil {
		return FabricPreparedSubmission{}, err
	}
	preparedBytes, err := transaction.Bytes()
	if err != nil {
		return FabricPreparedSubmission{}, fmt.Errorf("serialize endorsed Fabric transaction: %w", err)
	}
	if len(preparedBytes) == 0 {
		return FabricPreparedSubmission{}, errors.New("endorsed Fabric transaction serialized to empty bytes")
	}
	commitRequest, err := c.buildSignedCommitStatusRequest(transaction.TransactionID())
	if err != nil {
		return FabricPreparedSubmission{}, err
	}
	return FabricPreparedSubmission{
		TransactionID:       transaction.TransactionID(),
		PreparedTransaction: append([]byte(nil), preparedBytes...),
		CommitStatusRequest: append([]byte(nil), commitRequest...),
		CreateOutcome:       create.Outcome,
		RecordID:            create.RecordID,
	}, nil
}

func (c *GatewayClient) buildSignedCommitStatusRequest(transactionID string) ([]byte, error) {
	transactionID = strings.TrimSpace(transactionID)
	if transactionID == "" {
		return nil, errors.New("Fabric transaction ID is required for commit-status request")
	}
	requestBytes, err := proto.Marshal(&gatewaypb.CommitStatusRequest{
		ChannelId:     c.channelID,
		TransactionId: transactionID,
		Identity:      c.creator,
	})
	if err != nil {
		return nil, fmt.Errorf("serialize Fabric commit-status request: %w", err)
	}
	digest := sha256.Sum256(requestBytes)
	signature, err := c.sign(digest[:])
	if err != nil {
		return nil, fmt.Errorf("sign Fabric commit-status request: %w", err)
	}
	if len(signature) == 0 {
		return nil, errors.New("Fabric commit-status signer returned an empty signature")
	}
	result, err := proto.Marshal(&gatewaypb.SignedCommitStatusRequest{Request: requestBytes, Signature: signature})
	if err != nil {
		return nil, fmt.Errorf("serialize signed Fabric commit-status request: %w", err)
	}
	return result, nil
}

// SubmitPrepared submits only a transaction that was already durably prepared.
// Any error after entering this function is conservatively treated as unknown
// because the orderer may have accepted the transaction before the client saw
// the failure.
func (c *GatewayClient) SubmitPrepared(ctx context.Context, prepared FabricPreparedSubmission) (FabricSubmitResult, error) {
	txID := strings.TrimSpace(prepared.TransactionID)
	if txID == "" || len(prepared.PreparedTransaction) == 0 || len(prepared.CommitStatusRequest) == 0 {
		return FabricSubmitResult{}, errors.New("durable Fabric prepared submission is incomplete")
	}
	transaction, err := c.gateway.NewTransaction(prepared.PreparedTransaction)
	if err != nil {
		return FabricSubmitResult{TransactionID: txID, Unknown: true}, fmt.Errorf("restore prepared Fabric transaction: %w", err)
	}
	if transaction.TransactionID() != txID {
		return FabricSubmitResult{TransactionID: txID, Unknown: true}, errors.New("persisted Fabric prepared transaction ID does not match durable transaction ID")
	}
	if _, err := transaction.SubmitWithContext(ctx); err != nil {
		return FabricSubmitResult{TransactionID: txID, Unknown: true}, err
	}
	return c.CommitStatus(ctx, txID, prepared.CommitStatusRequest)
}

// CommitStatus reconstructs a signed status request persisted before submission,
// allowing restart-safe status recovery without generating a new transaction.
func (c *GatewayClient) CommitStatus(ctx context.Context, transactionID string, requestBytes []byte) (FabricSubmitResult, error) {
	txID := strings.TrimSpace(transactionID)
	result := FabricSubmitResult{TransactionID: txID}
	if txID == "" || len(requestBytes) == 0 {
		result.Unknown = true
		return result, errors.New("durable Fabric commit-status material is incomplete")
	}
	commit, err := c.gateway.NewCommit(requestBytes)
	if err != nil {
		result.Unknown = true
		return result, fmt.Errorf("restore Fabric commit-status request: %w", err)
	}
	if commit.TransactionID() != txID {
		result.Unknown = true
		return result, errors.New("persisted Fabric commit-status transaction ID does not match durable transaction ID")
	}
	commitStatus, err := commit.StatusWithContext(ctx)
	if err != nil {
		result.Unknown = true
		return result, err
	}
	if !commitStatus.Successful || int32(commitStatus.Code) != 0 {
		return result, fmt.Errorf("Fabric transaction %s committed invalid with code %d", txID, int32(commitStatus.Code))
	}
	result.Committed = true
	return result, nil
}

func (c *GatewayClient) Query(ctx context.Context, sourceSystemID, sourceRecordID string) (FabricQueryResult, error) {
	payload, err := c.contract.EvaluateWithContext(ctx, c.queryName, client.WithArguments(sourceRecordID))
	if err != nil {
		return FabricQueryResult{}, err
	}
	record, err := decodeQueryResponse(payload, sourceSystemID, sourceRecordID)
	if err != nil {
		return FabricQueryResult{}, err
	}
	return FabricQueryResult{
		Found:                       true,
		RecordID:                    record.RecordID,
		AuthenticatedSourceSystemID: record.AuthenticatedSourceSystemID,
		SourceRecordID:              record.SourceRecordID,
		DigestAlgorithm:             record.DigestAlgorithm,
		Digest:                      record.Digest,
		PayloadLength:               record.PayloadLength,
		SourceType:                  record.SourceType,
		Producer:                    record.Producer,
		ProducedAt:                  record.ProducedAt,
		SchemaVersion:               record.SchemaVersion,
	}, nil
}

func (c *GatewayClient) VerifyDigest(ctx context.Context, sourceSystemID, sourceRecordID, digest string) (FabricVerifyResult, error) {
	payload, err := c.contract.EvaluateWithContext(ctx, c.verifyName, client.WithArguments(sourceRecordID, digest))
	if err != nil {
		return FabricVerifyResult{}, err
	}
	return decodeVerifyResponse(payload, digest)
}

func decodeCreateResponse(payload []byte, expected FabricAnchor) (hrcCreateResponse, error) {
	var response hrcCreateResponse
	if err := json.Unmarshal(payload, &response); err != nil {
		return hrcCreateResponse{}, errors.New("Fabric CreateSourceBoundAnchor result is not the documented JSON envelope")
	}
	if response.Outcome != "CREATE" && response.Outcome != "IDEMPOTENT_RETRY" {
		return hrcCreateResponse{}, fmt.Errorf("Fabric CreateSourceBoundAnchor returned unsupported outcome %q", response.Outcome)
	}
	if strings.TrimSpace(response.RecordID) == "" || response.RecordID != response.Anchor.RecordID {
		return hrcCreateResponse{}, errors.New("Fabric CreateSourceBoundAnchor record_id is missing or inconsistent")
	}
	if err := validateHRCAnchorRecord(expected, response.Anchor); err != nil {
		return hrcCreateResponse{}, fmt.Errorf("Fabric CreateSourceBoundAnchor returned conflicting anchor: %w", err)
	}
	return response, nil
}

func decodeQueryResponse(payload []byte, sourceSystemID, sourceRecordID string) (hrcAnchorRecord, error) {
	var record hrcAnchorRecord
	if err := json.Unmarshal(payload, &record); err != nil {
		return hrcAnchorRecord{}, errors.New("Fabric QuerySourceBoundAnchor result is not the documented JSON anchor envelope")
	}
	if strings.TrimSpace(record.RecordID) == "" || strings.TrimSpace(record.AuthenticatedSourceSystemID) == "" || strings.TrimSpace(record.SourceRecordID) == "" || strings.TrimSpace(record.Digest) == "" || record.PayloadLength <= 0 {
		return hrcAnchorRecord{}, errors.New("Fabric QuerySourceBoundAnchor result is missing required anchor fields")
	}
	if record.DigestAlgorithm != "sha256" {
		return hrcAnchorRecord{}, errors.New("Fabric QuerySourceBoundAnchor digest_algorithm is not sha256")
	}
	if record.AuthenticatedSourceSystemID != sourceSystemID || record.SourceRecordID != sourceRecordID {
		return hrcAnchorRecord{}, errors.New("Fabric QuerySourceBoundAnchor returned a different source identity")
	}
	return record, nil
}

func decodeVerifyResponse(payload []byte, digest string) (FabricVerifyResult, error) {
	var response hrcVerifyResponse
	if err := json.Unmarshal(payload, &response); err != nil {
		return FabricVerifyResult{}, errors.New("Fabric VerifySourceBoundDigest result is not the documented JSON envelope")
	}
	if response.Outcome != "MATCH" {
		return FabricVerifyResult{}, fmt.Errorf("Fabric VerifySourceBoundDigest outcome is %q, expected MATCH", response.Outcome)
	}
	if strings.TrimSpace(response.RecordID) == "" {
		return FabricVerifyResult{}, errors.New("Fabric VerifySourceBoundDigest record_id is missing")
	}
	if response.ExpectedDigest != digest || response.ObservedDigest != digest {
		return FabricVerifyResult{}, errors.New("Fabric VerifySourceBoundDigest returned digest fields that do not match the observed digest")
	}
	return FabricVerifyResult{
		Outcome:        response.Outcome,
		RecordID:       response.RecordID,
		ExpectedDigest: response.ExpectedDigest,
		ObservedDigest: response.ObservedDigest,
	}, nil
}

func validateHRCAnchorRecord(expected FabricAnchor, actual hrcAnchorRecord) error {
	if strings.TrimSpace(actual.RecordID) == "" {
		return errors.New("record_id is missing")
	}
	if actual.DigestAlgorithm != "sha256" {
		return errors.New("digest_algorithm is not sha256")
	}
	if actual.AuthenticatedSourceSystemID != expected.AuthenticatedSourceSystemID || actual.SourceRecordID != expected.SourceRecordID ||
		actual.Digest != expected.Digest || actual.PayloadLength != expected.PayloadLength || actual.SourceType != expected.SourceType ||
		actual.Producer != expected.Producer || actual.ProducedAt != expected.ProducedAt || actual.SchemaVersion != expected.SchemaVersion {
		return errors.New("returned anchor fields do not match the submitted anchor")
	}
	return nil
}

func IsTransientFabricError(err error) bool {
	if err == nil {
		return false
	}
	switch status.Code(err) {
	case codes.Unavailable, codes.DeadlineExceeded, codes.ResourceExhausted, codes.Aborted:
		return true
	default:
		return false
	}
}

func IsPermanentFabricError(err error) bool {
	if err == nil {
		return false
	}
	switch status.Code(err) {
	case codes.PermissionDenied, codes.Unauthenticated, codes.InvalidArgument, codes.FailedPrecondition:
		return true
	default:
		return false
	}
}
