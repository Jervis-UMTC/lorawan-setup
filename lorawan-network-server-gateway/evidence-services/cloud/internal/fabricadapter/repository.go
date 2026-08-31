package fabricadapter

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

var (
	ErrLeaseLost           = errors.New("Fabric adapter processing lease lost")
	ErrOutboxMissing       = errors.New("Fabric outbox row missing")
	ErrSourceMissing       = errors.New("Fabric source row missing")
	ErrVerificationMissing = errors.New("gateway verification row missing")
	ErrSealMissing         = errors.New("Fabric evidence seal missing")
)

type Repository interface {
	Ping(context.Context) error
	ClaimReconciliation(context.Context, string, time.Duration) (*OutboxWork, error)
	ClaimWork(context.Context, string, time.Duration) (*OutboxWork, error)
	LoadOutboxReadOnly(context.Context, int64) (*OutboxWork, error)
	LoadSource(context.Context, OutboxWork) (SourceRow, error)
	LoadVerification(context.Context, OutboxWork) (VerificationRow, error)
	PersistSeal(context.Context, int64, string, CanonicalSealInput, string, string) (Seal, error)
	LoadSeal(context.Context, int64) (Seal, error)
	MarkConfirmed(context.Context, int64, string, string) error
	MarkSubmittedUnknown(context.Context, int64, string, string, time.Duration, string) error
	MarkFailed(context.Context, int64, string, time.Duration, string, string) error
	MarkDeadLetter(context.Context, int64, string, string, string) error
}

type PostgresRepository struct {
	pool *pgxpool.Pool
}

func NewPostgresRepository(pool *pgxpool.Pool) (*PostgresRepository, error) {
	if pool == nil {
		return nil, errors.New("Fabric adapter PostgreSQL pool is required")
	}
	return &PostgresRepository{pool: pool}, nil
}

func (r *PostgresRepository) Ping(ctx context.Context) error { return r.pool.Ping(ctx) }

func (r *PostgresRepository) ClaimReconciliation(ctx context.Context, workerID string, lease time.Duration) (*OutboxWork, error) {
	return r.claim(ctx, workerID, lease, true)
}

func (r *PostgresRepository) ClaimWork(ctx context.Context, workerID string, lease time.Duration) (*OutboxWork, error) {
	return r.claim(ctx, workerID, lease, false)
}

func (r *PostgresRepository) claim(ctx context.Context, workerID string, lease time.Duration, reconciliation bool) (*OutboxWork, error) {
	seconds := int64(lease / time.Second)
	if seconds < 10 || seconds > 3600 {
		return nil, errors.New("Fabric adapter processing lease must be 10 seconds through 1 hour")
	}
	predicate := `
(
  (o.status IN ('pending','failed') AND o.next_attempt_at <= now())
  OR (o.status = 'processing' AND o.lease_expires_at <= now() AND o.fabric_tx_id IS NULL)
)
AND (
  o.schema_version <> 'telemetry-attestation-v2'
  OR EXISTS (
    SELECT 1
    FROM gateway_evidence.event_verification AS v
    WHERE v.source_event_key = o.source_event_key
      AND v.observed_at = o.observed_at
      AND v.status = 'verified'
  )
)`
	attemptUpdate := "attempts = o.attempts + 1,"
	if reconciliation {
		predicate = `
(
  (o.status = 'submitted_unknown' AND o.next_attempt_at <= now())
  OR (o.status = 'processing' AND o.lease_expires_at <= now() AND o.fabric_tx_id IS NOT NULL)
)`
		attemptUpdate = ""
	}
	query := fmt.Sprintf(`
WITH candidate AS (
  SELECT o.outbox_id
  FROM telemetry.fabric_outbox AS o
  WHERE %s
  ORDER BY COALESCE(o.lease_expires_at, o.next_attempt_at), o.outbox_id
  FOR UPDATE OF o SKIP LOCKED
  LIMIT 1
)
UPDATE telemetry.fabric_outbox AS o
SET status = 'processing',
    worker_id = $1,
    processing_started_at = now(),
    lease_expires_at = now() + make_interval(secs => $2::double precision),
    %s
    updated_at = now()
FROM candidate AS c
WHERE o.outbox_id = c.outbox_id
RETURNING o.outbox_id, o.event_key, o.source_event_key, o.observed_at,
          o.event_type, o.schema_version, o.attempts,
          o.canonical_json, o.digest_sha256, o.evidence_signature_alg,
          o.evidence_signing_key_id, o.evidence_signature, o.evidence_sealed_at,
          o.fabric_tx_id`, predicate, attemptUpdate)
	var work OutboxWork
	err := r.pool.QueryRow(ctx, query, workerID, seconds).Scan(
		&work.OutboxID, &work.EventKey, &work.SourceEventKey, &work.ObservedAt,
		&work.EventType, &work.SchemaVersion, &work.Attempts,
		&work.CanonicalJSON, &work.DigestSHA256, &work.EvidenceSignatureAlg,
		&work.EvidenceSigningKeyID, &work.EvidenceSignature, &work.EvidenceSealedAt,
		&work.FabricTxID,
	)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("claim Fabric outbox work: %w", err)
	}
	return &work, nil
}

func (r *PostgresRepository) LoadOutboxReadOnly(ctx context.Context, outboxID int64) (*OutboxWork, error) {
	var work OutboxWork
	err := r.pool.QueryRow(ctx, `
SELECT outbox_id, event_key, source_event_key, observed_at,
       event_type, schema_version, attempts,
       canonical_json, digest_sha256, evidence_signature_alg,
       evidence_signing_key_id, evidence_signature, evidence_sealed_at,
       fabric_tx_id
FROM telemetry.fabric_outbox
WHERE outbox_id = $1`, outboxID).Scan(
		&work.OutboxID, &work.EventKey, &work.SourceEventKey, &work.ObservedAt,
		&work.EventType, &work.SchemaVersion, &work.Attempts,
		&work.CanonicalJSON, &work.DigestSHA256, &work.EvidenceSignatureAlg,
		&work.EvidenceSigningKeyID, &work.EvidenceSignature, &work.EvidenceSealedAt,
		&work.FabricTxID,
	)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrOutboxMissing
	}
	if err != nil {
		return nil, fmt.Errorf("load Fabric outbox row read-only: %w", err)
	}
	return &work, nil
}

func (r *PostgresRepository) LoadSource(ctx context.Context, work OutboxWork) (SourceRow, error) {
	var source SourceRow
	err := r.pool.QueryRow(ctx, `
SELECT u.received_at, u.application_id, u.device_id, u.device_model,
       u.decoder_version, u.dev_eui, u.gateway_id, u.region,
       u.f_port::bigint, u.f_cnt, u.confirmed, u.raw_data,
       u.payload_json::text
FROM telemetry.fabric_outbox AS o
JOIN telemetry.uplinks AS u
  ON u.event_key = o.source_event_key
 AND u.time = o.observed_at
WHERE o.outbox_id = $1
  AND o.source_event_key = $2
  AND o.observed_at = $3`, work.OutboxID, work.SourceEventKey, work.ObservedAt).Scan(
		&source.ReceivedAt, &source.ApplicationID, &source.DeviceID, &source.DeviceModel,
		&source.DecoderVersion, &source.DevEUI, &source.GatewayID, &source.Region,
		&source.FPort, &source.FCnt, &source.Confirmed, &source.RawDataBase64,
		&source.PayloadJSON,
	)
	if errors.Is(err, pgx.ErrNoRows) {
		return SourceRow{}, ErrSourceMissing
	}
	if err != nil {
		return SourceRow{}, fmt.Errorf("load Fabric source row: %w", err)
	}
	return source, nil
}

func (r *PostgresRepository) LoadVerification(ctx context.Context, work OutboxWork) (VerificationRow, error) {
	var row VerificationRow
	err := r.pool.QueryRow(ctx, `
SELECT verification_id, status, gateway_id, journal_segment_id,
       journal_sequence, journal_record_hash, journal_segment_hash,
       checkpoint_id, gateway_event_id, decoder_id, decoder_version,
       raw_app_data_sha256, normalized_digest_sha256
FROM gateway_evidence.event_verification
WHERE source_event_key = $1
  AND observed_at = $2`, work.SourceEventKey, work.ObservedAt).Scan(
		&row.VerificationID, &row.Status, &row.GatewayID, &row.JournalSegmentID,
		&row.JournalSequence, &row.JournalRecordHash, &row.JournalSegmentHash,
		&row.CheckpointID, &row.GatewayEventID, &row.DecoderID, &row.DecoderVersion,
		&row.RawAppDataSHA256, &row.NormalizedDigestSHA256,
	)
	if errors.Is(err, pgx.ErrNoRows) {
		return VerificationRow{}, ErrVerificationMissing
	}
	if err != nil {
		return VerificationRow{}, fmt.Errorf("load gateway verification: %w", err)
	}
	return row, nil
}

func (r *PostgresRepository) PersistSeal(ctx context.Context, outboxID int64, workerID string, input CanonicalSealInput, signature, signingKeyID string) (Seal, error) {
	var seal Seal
	err := r.pool.QueryRow(ctx, `
UPDATE telemetry.fabric_outbox
SET canonical_json = $3,
    digest_sha256 = $4,
    evidence_signature_alg = $5,
    evidence_signing_key_id = $6,
    evidence_signature = $7,
    evidence_sealed_at = now(),
    updated_at = now()
WHERE outbox_id = $1
  AND status = 'processing'
  AND worker_id = $2
  AND lease_expires_at > now()
  AND canonical_json IS NULL
RETURNING canonical_json, digest_sha256, evidence_signature_alg,
          evidence_signing_key_id, evidence_signature, evidence_sealed_at`,
		outboxID, workerID, string(input.CanonicalJSON), input.DigestSHA256,
		EvidenceSignatureAlgorithm, signingKeyID, signature,
	).Scan(&seal.CanonicalJSON, &seal.DigestSHA256, &seal.Algorithm,
		&seal.SigningKeyID, &seal.Signature, &seal.SealedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return Seal{}, ErrLeaseLost
	}
	if err != nil {
		return Seal{}, fmt.Errorf("persist complete Fabric evidence seal: %w", err)
	}
	return seal, nil
}

func (r *PostgresRepository) LoadSeal(ctx context.Context, outboxID int64) (Seal, error) {
	var seal Seal
	err := r.pool.QueryRow(ctx, `
SELECT canonical_json, digest_sha256, evidence_signature_alg,
       evidence_signing_key_id, evidence_signature, evidence_sealed_at
FROM telemetry.fabric_outbox
WHERE outbox_id = $1
  AND canonical_json IS NOT NULL`, outboxID).Scan(
		&seal.CanonicalJSON, &seal.DigestSHA256, &seal.Algorithm,
		&seal.SigningKeyID, &seal.Signature, &seal.SealedAt,
	)
	if errors.Is(err, pgx.ErrNoRows) {
		return Seal{}, ErrSealMissing
	}
	if err != nil {
		return Seal{}, fmt.Errorf("load Fabric evidence seal: %w", err)
	}
	return seal, nil
}

func (r *PostgresRepository) MarkConfirmed(ctx context.Context, outboxID int64, workerID, txID string) error {
	return r.finish(ctx, outboxID, workerID, `
status = 'confirmed', fabric_tx_id = $3,
submitted_at = COALESCE(submitted_at, now()), committed_at = now(),
last_error_category = NULL, last_error = NULL`, txID, 0, "", "")
}

func (r *PostgresRepository) MarkSubmittedUnknown(ctx context.Context, outboxID int64, workerID, txID string, retryAfter time.Duration, detail string) error {
	return r.finish(ctx, outboxID, workerID, `
status = 'submitted_unknown', fabric_tx_id = $3,
submitted_at = COALESCE(submitted_at, now()), committed_at = NULL,
next_attempt_at = now() + make_interval(secs => $4::double precision),
last_error_category = 'fabric_submission_unknown', last_error = $5`, txID, retryAfter, detail, "")
}

func (r *PostgresRepository) MarkFailed(ctx context.Context, outboxID int64, workerID string, retryAfter time.Duration, category, detail string) error {
	return r.finish(ctx, outboxID, workerID, `
status = 'failed',
next_attempt_at = now() + make_interval(secs => $4::double precision),
last_error_category = $6, last_error = $5`, "", retryAfter, detail, category)
}

func (r *PostgresRepository) MarkDeadLetter(ctx context.Context, outboxID int64, workerID, category, detail string) error {
	return r.finish(ctx, outboxID, workerID, `
status = 'dead_letter', next_attempt_at = now(),
last_error_category = $6, last_error = $5`, "", 0, detail, category)
}

func (r *PostgresRepository) finish(ctx context.Context, outboxID int64, workerID, setClause, txID string, retryAfter time.Duration, detail, category string) error {
	seconds := int64(retryAfter / time.Second)
	if seconds < 0 || seconds > 86400 {
		return errors.New("Fabric adapter retry delay must not exceed 24 hours")
	}
	query := `UPDATE telemetry.fabric_outbox SET ` + setClause + `,
worker_id = NULL, processing_started_at = NULL, lease_expires_at = NULL,
updated_at = now()
WHERE outbox_id = $1
  AND status = 'processing'
  AND worker_id = $2`
	tag, err := r.pool.Exec(ctx, query, outboxID, workerID, txID, seconds, detail, category)
	if err != nil {
		return fmt.Errorf("finish Fabric outbox work: %w", err)
	}
	if tag.RowsAffected() != 1 {
		return ErrLeaseLost
	}
	return nil
}
