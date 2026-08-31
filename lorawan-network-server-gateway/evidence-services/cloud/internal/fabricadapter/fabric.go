package fabricadapter

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"

	"github.com/hyperledger/fabric-gateway/pkg/client"
	"github.com/hyperledger/fabric-gateway/pkg/identity"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/status"
)

type FabricSubmitResult struct {
	TransactionID string
	Committed     bool
	Unknown       bool
}

type LedgerClient interface {
	Submit(context.Context, FabricAttestation) (FabricSubmitResult, error)
	Query(context.Context, string) (FabricQueryResult, error)
	Close() error
}

type GatewayClient struct {
	connection *grpc.ClientConn
	gateway    *client.Gateway
	contract   *client.Contract
	submitName string
	queryName  string
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

func (c *GatewayClient) Submit(ctx context.Context, attestation FabricAttestation) (FabricSubmitResult, error) {
	args := []string{
		attestation.SchemaVersion,
		attestation.EventKey,
		attestation.EventType,
		attestation.Digest,
		attestation.SealAlgorithm,
		attestation.SealKeyID,
		attestation.SealSignature,
	}
	_, commit, err := c.contract.SubmitAsyncWithContext(ctx, c.submitName, client.WithArguments(args...))
	if err != nil {
		var submitErr *client.SubmitError
		if errors.As(err, &submitErr) && submitErr.TransactionID != "" {
			return FabricSubmitResult{TransactionID: submitErr.TransactionID, Unknown: true}, err
		}
		return FabricSubmitResult{}, err
	}
	if commit == nil || strings.TrimSpace(commit.TransactionID()) == "" {
		return FabricSubmitResult{}, errors.New("Fabric Gateway accepted submission without transaction ID")
	}
	result := FabricSubmitResult{TransactionID: commit.TransactionID()}
	commitStatus, err := commit.StatusWithContext(ctx)
	if err != nil {
		result.Unknown = true
		return result, err
	}
	if !commitStatus.Successful {
		return result, fmt.Errorf("Fabric transaction %s committed invalid with code %d", result.TransactionID, int32(commitStatus.Code))
	}
	result.Committed = true
	return result, nil
}

func (c *GatewayClient) Query(ctx context.Context, eventKey string) (FabricQueryResult, error) {
	payload, err := c.contract.EvaluateWithContext(ctx, c.queryName, client.WithArguments(eventKey))
	if err != nil {
		return FabricQueryResult{}, err
	}
	var record struct {
		EventKey      string `json:"event_key"`
		Digest        string `json:"digest"`
		FabricTxID    string `json:"fabric_tx_id"`
		TransactionID string `json:"transaction_id"`
		TxID          string `json:"tx_id"`
	}
	if err := json.Unmarshal(payload, &record); err != nil {
		return FabricQueryResult{}, errors.New("Fabric query result is not the documented JSON attestation envelope")
	}
	if record.EventKey == "" || record.Digest == "" {
		return FabricQueryResult{}, errors.New("Fabric query result is missing event_key or digest")
	}
	if record.EventKey != eventKey {
		return FabricQueryResult{}, errors.New("Fabric query returned a different event_key")
	}
	txID := strings.TrimSpace(record.FabricTxID)
	if txID == "" {
		txID = strings.TrimSpace(record.TransactionID)
	}
	if txID == "" {
		txID = strings.TrimSpace(record.TxID)
	}
	return FabricQueryResult{Found: true, EventKey: record.EventKey, Digest: record.Digest, TxID: txID, Committed: true}, nil
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
