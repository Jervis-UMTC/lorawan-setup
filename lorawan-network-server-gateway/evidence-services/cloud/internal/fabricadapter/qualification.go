package fabricadapter

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"regexp"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

var (
	ErrQualificationState = errors.New("Task 37 qualification candidate is not in an authorized state")
	sha256HexPattern      = regexp.MustCompile(`^[0-9a-f]{64}$`)
)

type QualificationMode string

const (
	QualificationModeSubmission QualificationMode = "submission"
	QualificationModeRecovery   QualificationMode = "same_transaction_recovery"
)

type QualificationSeal struct {
	OutboxID                  int64
	SourceRecordID            string
	SourceType                string
	Producer                  string
	ProducedAtRFC3339Nano     string
	SchemaVersion             string
	FinalizedPayloadLength    int
	FinalizedPayloadSHA256    string
	GatewayVerificationStatus string
}

type QualificationSnapshot struct {
	OutboxID                   int64
	SourceRecordID             string
	Status                     string
	Attempts                   int
	FabricTransactionID        string
	FabricRecordID             string
	PreparedTransactionPresent bool
	PreparedTransactionLength  int
	CommitStatusRequestPresent bool
	CommitStatusRequestLength  int
	SourceType                 string
	Producer                   string
	ProducedAt                 time.Time
	SchemaVersion              string
	FinalizedPayloadLength     int
	FinalizedPayloadSHA256     string
	GatewayVerificationStatus  string
	NextAttemptDue             bool
	LeaseExpiredOrAbsent       bool
}

type QualificationRuntimeContract struct {
	WorkerID             string
	DatabaseExpectedHost string
	DatabaseExpectedName string
	OpenBaoAddr          string
	OpenBaoCAFile        string
	OpenBaoRoleIDFile    string
	OpenBaoSecretIDFile  string
	FabricEndpoint       string
	FabricTLSServerName  string
	FabricTLSRootCert    string
	FabricMSPID          string
	FabricCertPath       string
	FabricKeyPath        string
	FabricChannel        string
	FabricChaincode      string
	FabricContract       string
	FabricSourceSystemID string
	FabricSubmitFunction string
	FabricQueryFunction  string
	FabricVerifyFunction string
}

func ValidateQualificationConfig(cfg Config, expected QualificationRuntimeContract) error {
	if cfg.Enabled {
		return errors.New("qualification runner requires FABRIC_ADAPTER_ENABLED=false; the normal adapter must remain disabled")
	}
	required := map[string]string{
		"FABRIC_ADAPTER_DATABASE_URL":           cfg.DatabaseDSN,
		"FABRIC_ADAPTER_WORKER_ID":              cfg.WorkerID,
		"OPENBAO_ADDR":                          cfg.OpenBaoAddr,
		"OPENBAO_CA_FILE":                       cfg.OpenBaoCAFile,
		"OPENBAO_APPROLE_ROLE_ID_FILE":          cfg.OpenBaoRoleIDFile,
		"OPENBAO_APPROLE_SECRET_ID_FILE":        cfg.OpenBaoSecretIDFile,
		"FABRIC_GATEWAY_ENDPOINT":               cfg.FabricEndpoint,
		"FABRIC_TLS_SERVER_NAME":                cfg.FabricTLSServerName,
		"FABRIC_TLS_ROOT_CERT":                  cfg.FabricTLSRootCert,
		"FABRIC_MSP_ID":                         cfg.FabricMSPID,
		"FABRIC_CERT_PATH":                      cfg.FabricCertPath,
		"FABRIC_KEY_PATH":                       cfg.FabricKeyPath,
		"FABRIC_CHANNEL":                        cfg.FabricChannel,
		"FABRIC_CHAINCODE":                      cfg.FabricChaincode,
		"FABRIC_AUTHENTICATED_SOURCE_SYSTEM_ID": cfg.FabricSourceSystemID,
		"FABRIC_SUBMIT_FUNCTION":                cfg.FabricSubmitFunction,
		"FABRIC_QUERY_FUNCTION":                 cfg.FabricQueryFunction,
		"FABRIC_VERIFY_FUNCTION":                cfg.FabricVerifyFunction,
	}
	for name, value := range required {
		if strings.TrimSpace(value) == "" {
			return fmt.Errorf("%s is required for qualification", name)
		}
	}

	exact := []struct {
		name string
		got  string
		want string
	}{
		{"FABRIC_ADAPTER_WORKER_ID", cfg.WorkerID, expected.WorkerID},
		{"FABRIC_ADAPTER_DATABASE_EXPECTED_HOST", cfg.DatabaseExpectedHost, expected.DatabaseExpectedHost},
		{"FABRIC_ADAPTER_DATABASE_EXPECTED_NAME", cfg.DatabaseExpectedName, expected.DatabaseExpectedName},
		{"OPENBAO_ADDR", cfg.OpenBaoAddr, expected.OpenBaoAddr},
		{"OPENBAO_CA_FILE", cfg.OpenBaoCAFile, expected.OpenBaoCAFile},
		{"OPENBAO_APPROLE_ROLE_ID_FILE", cfg.OpenBaoRoleIDFile, expected.OpenBaoRoleIDFile},
		{"OPENBAO_APPROLE_SECRET_ID_FILE", cfg.OpenBaoSecretIDFile, expected.OpenBaoSecretIDFile},
		{"FABRIC_GATEWAY_ENDPOINT", cfg.FabricEndpoint, expected.FabricEndpoint},
		{"FABRIC_TLS_SERVER_NAME", cfg.FabricTLSServerName, expected.FabricTLSServerName},
		{"FABRIC_TLS_ROOT_CERT", cfg.FabricTLSRootCert, expected.FabricTLSRootCert},
		{"FABRIC_MSP_ID", cfg.FabricMSPID, expected.FabricMSPID},
		{"FABRIC_CERT_PATH", cfg.FabricCertPath, expected.FabricCertPath},
		{"FABRIC_KEY_PATH", cfg.FabricKeyPath, expected.FabricKeyPath},
		{"FABRIC_CHANNEL", cfg.FabricChannel, expected.FabricChannel},
		{"FABRIC_CHAINCODE", cfg.FabricChaincode, expected.FabricChaincode},
		{"FABRIC_CONTRACT", cfg.FabricContract, expected.FabricContract},
		{"FABRIC_AUTHENTICATED_SOURCE_SYSTEM_ID", cfg.FabricSourceSystemID, expected.FabricSourceSystemID},
		{"FABRIC_SUBMIT_FUNCTION", cfg.FabricSubmitFunction, expected.FabricSubmitFunction},
		{"FABRIC_QUERY_FUNCTION", cfg.FabricQueryFunction, expected.FabricQueryFunction},
		{"FABRIC_VERIFY_FUNCTION", cfg.FabricVerifyFunction, expected.FabricVerifyFunction},
	}
	for _, item := range exact {
		if item.got != item.want {
			return fmt.Errorf("%s mismatch: got %q", item.name, item.got)
		}
	}
	return nil
}

func validateQualificationSeal(seal QualificationSeal) (time.Time, error) {
	if seal.OutboxID <= 0 {
		return time.Time{}, errors.New("qualification outbox_id must be positive")
	}
	if !hrcRecordIDPattern.MatchString(seal.SourceRecordID) {
		return time.Time{}, errors.New("qualification SourceRecordID is invalid")
	}
	if strings.TrimSpace(seal.SourceType) == "" || len(seal.SourceType) > 128 {
		return time.Time{}, errors.New("qualification sourceType is invalid")
	}
	if strings.TrimSpace(seal.Producer) == "" || len(seal.Producer) > 128 {
		return time.Time{}, errors.New("qualification producer is invalid")
	}
	if strings.TrimSpace(seal.SchemaVersion) == "" || len(seal.SchemaVersion) > 128 {
		return time.Time{}, errors.New("qualification schemaVersion is invalid")
	}
	if seal.FinalizedPayloadLength < 1 || seal.FinalizedPayloadLength > maxFabricExactPayloadBytes {
		return time.Time{}, errors.New("qualification finalized payload length is invalid")
	}
	if !sha256HexPattern.MatchString(seal.FinalizedPayloadSHA256) {
		return time.Time{}, errors.New("qualification finalized payload SHA-256 is invalid")
	}
	if seal.GatewayVerificationStatus != "verified" {
		return time.Time{}, errors.New("qualification gateway verification status must be verified")
	}
	producedAt, err := time.Parse(time.RFC3339Nano, seal.ProducedAtRFC3339Nano)
	if err != nil {
		return time.Time{}, fmt.Errorf("qualification producedAt is invalid: %w", err)
	}
	producedAt = producedAt.UTC()
	if producedAt.Format(time.RFC3339Nano) != seal.ProducedAtRFC3339Nano {
		return time.Time{}, errors.New("qualification producedAt must be canonical UTC RFC3339Nano")
	}
	return producedAt, nil
}

func ValidateQualificationSnapshot(snapshot QualificationSnapshot, seal QualificationSeal) (QualificationMode, error) {
	producedAt, err := validateQualificationSeal(seal)
	if err != nil {
		return "", err
	}
	mismatches := make([]string, 0, 10)
	if snapshot.OutboxID != seal.OutboxID {
		mismatches = append(mismatches, "outbox_id")
	}
	if snapshot.SourceRecordID != seal.SourceRecordID {
		mismatches = append(mismatches, "SourceRecordID")
	}
	if snapshot.SourceType != seal.SourceType {
		mismatches = append(mismatches, "sourceType")
	}
	if snapshot.Producer != seal.Producer {
		mismatches = append(mismatches, "producer")
	}
	if !snapshot.ProducedAt.UTC().Equal(producedAt) {
		mismatches = append(mismatches, "producedAt")
	}
	if snapshot.SchemaVersion != seal.SchemaVersion {
		mismatches = append(mismatches, "schemaVersion")
	}
	if snapshot.FinalizedPayloadLength != seal.FinalizedPayloadLength {
		mismatches = append(mismatches, "finalized_payload_length")
	}
	if snapshot.FinalizedPayloadSHA256 != seal.FinalizedPayloadSHA256 {
		mismatches = append(mismatches, "finalized_payload_sha256")
	}
	if snapshot.GatewayVerificationStatus != seal.GatewayVerificationStatus {
		mismatches = append(mismatches, "gateway_verification_status")
	}
	if len(mismatches) > 0 {
		return "", fmt.Errorf("%w: sealed field mismatch: %s", ErrQualificationState, strings.Join(mismatches, ","))
	}

	txPresent := strings.TrimSpace(snapshot.FabricTransactionID) != ""
	recordPresent := strings.TrimSpace(snapshot.FabricRecordID) != ""
	anyDurable := txPresent || recordPresent || snapshot.PreparedTransactionPresent || snapshot.CommitStatusRequestPresent
	if !anyDurable {
		if snapshot.Status != "pending" || snapshot.Attempts != 0 || !snapshot.NextAttemptDue {
			return "", fmt.Errorf("%w: untouched candidate must be pending, attempts=0, and due", ErrQualificationState)
		}
		return QualificationModeSubmission, nil
	}

	completeDurable := txPresent && recordPresent && snapshot.PreparedTransactionPresent && snapshot.PreparedTransactionLength > 0 && snapshot.CommitStatusRequestPresent && snapshot.CommitStatusRequestLength > 0
	if !completeDurable {
		return "", fmt.Errorf("%w: partial durable Fabric transaction material detected; do not prepare another proposal", ErrQualificationState)
	}
	if snapshot.Status == "reconciling" && snapshot.NextAttemptDue {
		return QualificationModeRecovery, nil
	}
	if snapshot.Status == "processing" && snapshot.LeaseExpiredOrAbsent {
		return QualificationModeRecovery, nil
	}
	return "", fmt.Errorf("%w: durable transaction exists but is not in a recoverable due/expired state", ErrQualificationState)
}

func (r *PostgresRepository) LoadQualificationSnapshot(ctx context.Context, outboxID int64, sourceRecordID string) (QualificationSnapshot, error) {
	var snapshot QualificationSnapshot
	err := r.pool.QueryRow(ctx, `
SELECT o.outbox_id, o.source_event_key, o.status, o.attempts,
       COALESCE(o.fabric_tx_id, ''), COALESCE(o.fabric_record_id, ''),
       o.fabric_prepared_tx IS NOT NULL, COALESCE(octet_length(o.fabric_prepared_tx), 0),
       o.fabric_commit_status_request IS NOT NULL, COALESCE(octet_length(o.fabric_commit_status_request), 0),
       o.event_type, u.dev_eui, o.observed_at, o.schema_version,
       COALESCE(octet_length(o.finalized_payload), 0),
       COALESCE(encode(sha256(o.finalized_payload), 'hex'), ''),
       COALESCE(v.status, ''),
       o.next_attempt_at <= now(),
       o.lease_expires_at IS NULL OR o.lease_expires_at <= now()
FROM telemetry.fabric_outbox AS o
JOIN telemetry.uplinks AS u
  ON u.event_key = o.source_event_key
 AND u.time = o.observed_at
LEFT JOIN gateway_evidence.event_verification AS v
  ON v.source_event_key = o.source_event_key
 AND v.observed_at = o.observed_at
WHERE o.outbox_id = $1
  AND o.source_event_key = $2`, outboxID, sourceRecordID).Scan(
		&snapshot.OutboxID, &snapshot.SourceRecordID, &snapshot.Status, &snapshot.Attempts,
		&snapshot.FabricTransactionID, &snapshot.FabricRecordID,
		&snapshot.PreparedTransactionPresent, &snapshot.PreparedTransactionLength,
		&snapshot.CommitStatusRequestPresent, &snapshot.CommitStatusRequestLength,
		&snapshot.SourceType, &snapshot.Producer, &snapshot.ProducedAt, &snapshot.SchemaVersion,
		&snapshot.FinalizedPayloadLength, &snapshot.FinalizedPayloadSHA256,
		&snapshot.GatewayVerificationStatus, &snapshot.NextAttemptDue, &snapshot.LeaseExpiredOrAbsent,
	)
	if errors.Is(err, pgx.ErrNoRows) {
		return QualificationSnapshot{}, ErrOutboxMissing
	}
	if err != nil {
		return QualificationSnapshot{}, fmt.Errorf("load Task 37 qualification snapshot: %w", err)
	}
	return snapshot, nil
}

func (r *PostgresRepository) ClaimQualification(ctx context.Context, seal QualificationSeal, workerID string, lease time.Duration) (*OutboxWork, QualificationMode, error) {
	producedAt, err := validateQualificationSeal(seal)
	if err != nil {
		return nil, "", err
	}
	if strings.TrimSpace(workerID) == "" || len(workerID) > 128 {
		return nil, "", errors.New("qualification worker ID must be 1 through 128 characters")
	}
	seconds := int64(lease / time.Second)
	if seconds < 10 || seconds > 3600 {
		return nil, "", errors.New("qualification processing lease must be 10 seconds through 1 hour")
	}

	snapshot, err := r.LoadQualificationSnapshot(ctx, seal.OutboxID, seal.SourceRecordID)
	if err != nil {
		return nil, "", err
	}
	mode, err := ValidateQualificationSnapshot(snapshot, seal)
	if err != nil {
		return nil, "", err
	}

	var row pgx.Row
	commonArgs := []any{
		seal.OutboxID,
		seal.SourceRecordID,
		seal.SourceType,
		seal.Producer,
		producedAt,
		seal.SchemaVersion,
		seal.FinalizedPayloadLength,
		seal.FinalizedPayloadSHA256,
		seal.GatewayVerificationStatus,
		workerID,
		seconds,
	}
	if mode == QualificationModeSubmission {
		row = r.pool.QueryRow(ctx, `
UPDATE telemetry.fabric_outbox AS o
SET status = 'processing',
    worker_id = $10,
    processing_started_at = now(),
    lease_expires_at = now() + make_interval(secs => $11::double precision),
    attempts = o.attempts + 1,
    updated_at = now()
WHERE o.outbox_id = $1
  AND o.source_event_key = $2
  AND o.event_type = $3
  AND o.observed_at = $5
  AND o.schema_version = $6
  AND octet_length(o.finalized_payload) = $7
  AND encode(sha256(o.finalized_payload), 'hex') = $8
  AND o.status = 'pending'
  AND o.attempts = 0
  AND o.next_attempt_at <= now()
  AND o.fabric_tx_id IS NULL
  AND o.fabric_record_id IS NULL
  AND o.fabric_prepared_tx IS NULL
  AND o.fabric_commit_status_request IS NULL
  AND EXISTS (
    SELECT 1 FROM telemetry.uplinks AS u
    WHERE u.event_key = o.source_event_key
      AND u.time = o.observed_at
      AND u.dev_eui = $4
  )
  AND EXISTS (
    SELECT 1 FROM gateway_evidence.event_verification AS v
    WHERE v.source_event_key = o.source_event_key
      AND v.observed_at = o.observed_at
      AND v.status = $9
  )
RETURNING o.outbox_id, o.event_key, o.source_event_key, o.observed_at,
          o.event_type, o.schema_version, o.attempts,
          o.canonical_json, o.digest_sha256, o.evidence_signature_alg,
          o.evidence_signing_key_id, o.evidence_signature, o.evidence_sealed_at,
          o.finalized_payload, o.fabric_tx_id, o.fabric_record_id,
          o.fabric_prepared_tx, o.fabric_commit_status_request`, commonArgs...)
	} else {
		row = r.pool.QueryRow(ctx, `
UPDATE telemetry.fabric_outbox AS o
SET status = 'processing',
    worker_id = $10,
    processing_started_at = now(),
    lease_expires_at = now() + make_interval(secs => $11::double precision),
    updated_at = now()
WHERE o.outbox_id = $1
  AND o.source_event_key = $2
  AND o.event_type = $3
  AND o.observed_at = $5
  AND o.schema_version = $6
  AND octet_length(o.finalized_payload) = $7
  AND encode(sha256(o.finalized_payload), 'hex') = $8
  AND (
    (o.status = 'reconciling' AND o.next_attempt_at <= now())
    OR (o.status = 'processing' AND o.lease_expires_at <= now())
  )
  AND NULLIF(o.fabric_tx_id, '') IS NOT NULL
  AND NULLIF(o.fabric_record_id, '') IS NOT NULL
  AND COALESCE(octet_length(o.fabric_prepared_tx), 0) > 0
  AND COALESCE(octet_length(o.fabric_commit_status_request), 0) > 0
  AND EXISTS (
    SELECT 1 FROM telemetry.uplinks AS u
    WHERE u.event_key = o.source_event_key
      AND u.time = o.observed_at
      AND u.dev_eui = $4
  )
  AND EXISTS (
    SELECT 1 FROM gateway_evidence.event_verification AS v
    WHERE v.source_event_key = o.source_event_key
      AND v.observed_at = o.observed_at
      AND v.status = $9
  )
RETURNING o.outbox_id, o.event_key, o.source_event_key, o.observed_at,
          o.event_type, o.schema_version, o.attempts,
          o.canonical_json, o.digest_sha256, o.evidence_signature_alg,
          o.evidence_signing_key_id, o.evidence_signature, o.evidence_sealed_at,
          o.finalized_payload, o.fabric_tx_id, o.fabric_record_id,
          o.fabric_prepared_tx, o.fabric_commit_status_request`, commonArgs...)
	}

	work, err := scanQualificationWork(row)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, "", fmt.Errorf("%w: atomic qualification claim predicate no longer matches", ErrQualificationState)
	}
	if err != nil {
		return nil, "", fmt.Errorf("claim Task 37 qualification candidate: %w", err)
	}
	if work.OutboxID != seal.OutboxID || work.SourceEventKey != seal.SourceRecordID {
		return nil, "", fmt.Errorf("%w: atomic claim returned the wrong candidate", ErrQualificationState)
	}
	payloadDigest := sha256.Sum256(work.FinalizedPayload)
	if len(work.FinalizedPayload) != seal.FinalizedPayloadLength || hex.EncodeToString(payloadDigest[:]) != seal.FinalizedPayloadSHA256 {
		return nil, "", fmt.Errorf("%w: claimed payload does not match the sealed bytes", ErrQualificationState)
	}
	return &work, mode, nil
}

func scanQualificationWork(row pgx.Row) (OutboxWork, error) {
	var work OutboxWork
	err := row.Scan(
		&work.OutboxID, &work.EventKey, &work.SourceEventKey, &work.ObservedAt,
		&work.EventType, &work.SchemaVersion, &work.Attempts,
		&work.CanonicalJSON, &work.DigestSHA256, &work.EvidenceSignatureAlg,
		&work.EvidenceSigningKeyID, &work.EvidenceSignature, &work.EvidenceSealedAt,
		&work.FinalizedPayload, &work.FabricTxID, &work.FabricRecordID,
		&work.FabricPreparedTx, &work.FabricCommitRequest,
	)
	return work, err
}

func (w *Worker) ProcessQualification(ctx context.Context, work OutboxWork, mode QualificationMode) error {
	switch mode {
	case QualificationModeSubmission:
		return w.withLeaseHeartbeat(ctx, work, w.process)
	case QualificationModeRecovery:
		return w.withLeaseHeartbeat(ctx, work, w.reconcile)
	default:
		return errors.New("unsupported qualification mode")
	}
}
