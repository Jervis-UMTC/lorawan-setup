package verifier

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/jackc/pgx/v5/pgxpool"
)

type PostgresRepository struct {
	pool *pgxpool.Pool
}

func NewPostgresRepository(pool *pgxpool.Pool) (*PostgresRepository, error) {
	if pool == nil {
		return nil, errors.New("PostgreSQL pool is required")
	}
	return &PostgresRepository{pool: pool}, nil
}

func (r *PostgresRepository) Ping(ctx context.Context) error { return r.pool.Ping(ctx) }

func (r *PostgresRepository) Discover(ctx context.Context, limit int) (int64, error) {
	if limit < 1 || limit > 1000 {
		return 0, errors.New("verifier discovery limit must be from 1 through 1000")
	}
	tag, err := r.pool.Exec(ctx, `
INSERT INTO gateway_evidence.event_verification (source_event_key, observed_at)
SELECT source_event_key, observed_at
FROM (
    SELECT source_event_key, observed_at, min(outbox_id) AS first_outbox_id
    FROM telemetry.fabric_outbox
    WHERE schema_version = 'telemetry-attestation-v2'
    GROUP BY source_event_key, observed_at
    ORDER BY min(outbox_id)
    LIMIT $1
) AS source
ON CONFLICT (source_event_key, observed_at) DO NOTHING`, limit)
	if err != nil {
		return 0, fmt.Errorf("discover verifier work: %w", err)
	}
	return tag.RowsAffected(), nil
}

func (r *PostgresRepository) Claim(ctx context.Context, workerID string, lease time.Duration) (*Work, error) {
	workerID = strings.TrimSpace(workerID)
	if workerID == "" || len(workerID) > 128 {
		return nil, errors.New("verifier worker ID must be 1 through 128 characters")
	}
	leaseSeconds := int64(lease / time.Second)
	if leaseSeconds < 5 || leaseSeconds > 3600 {
		return nil, errors.New("verifier lease must be from 5 seconds through 1 hour")
	}

	tx, err := r.pool.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return nil, fmt.Errorf("begin verifier claim transaction: %w", err)
	}
	defer func() { _ = tx.Rollback(context.Background()) }()

	var work Work
	err = tx.QueryRow(ctx, `
WITH candidate AS (
  SELECT verification_id
  FROM gateway_evidence.event_verification
  WHERE status = 'pending'
    AND next_attempt_at <= now()
    AND (lease_expires_at IS NULL OR lease_expires_at <= now())
  ORDER BY next_attempt_at, verification_id
  FOR UPDATE SKIP LOCKED
  LIMIT 1
)
UPDATE gateway_evidence.event_verification AS v
SET worker_id = $1,
    lease_expires_at = now() + make_interval(secs => $2::double precision),
    attempts = attempts + 1,
    updated_at = now()
FROM candidate AS c
WHERE v.verification_id = c.verification_id
RETURNING v.verification_id, v.source_event_key, v.observed_at, v.worker_id, v.attempts`,
		workerID, leaseSeconds,
	).Scan(&work.VerificationID, &work.SourceEventKey, &work.ObservedAt, &work.WorkerID, &work.Attempts)
	if errors.Is(err, pgx.ErrNoRows) {
		if err := tx.Commit(ctx); err != nil {
			return nil, fmt.Errorf("commit empty verifier claim: %w", err)
		}
		return nil, nil
	}
	if err != nil {
		return nil, fmt.Errorf("claim verifier work: %w", err)
	}
	if err := tx.Commit(ctx); err != nil {
		return nil, fmt.Errorf("commit verifier lease before evidence reads: %w", err)
	}
	return &work, nil
}

func (r *PostgresRepository) LoadApplication(ctx context.Context, work Work) (ApplicationEvidence, error) {
	rows, err := r.pool.Query(ctx, `
SELECT o.event_type, o.schema_version,
       u.event_key, u.time, u.dev_eui, u.gateway_id,
       u.gateway_uplink_id, u.gateway_frequency_hz, u.gateway_context_base64,
       u.rssi_dbm, u.snr_db, u.decoder_version, u.raw_data
FROM telemetry.fabric_outbox AS o
JOIN telemetry.uplinks AS u
  ON u.event_key = o.source_event_key
 AND u.time = o.observed_at
WHERE o.source_event_key = $1
  AND o.observed_at = $2
  AND o.schema_version = 'telemetry-attestation-v2'
ORDER BY o.outbox_id
LIMIT 2`, work.SourceEventKey, work.ObservedAt)
	if err != nil {
		return ApplicationEvidence{}, fmt.Errorf("load application evidence: %w", err)
	}
	defer rows.Close()

	var candidates []ApplicationEvidence
	for rows.Next() {
		var app ApplicationEvidence
		var gatewayID, gatewayContext, decoderVersion, rawData pgtype.Text
		var gatewayUplinkID, gatewayFrequency pgtype.Int8
		var gatewayRSSI pgtype.Int4
		var gatewaySNR pgtype.Float8
		if err := rows.Scan(
			&app.EventType, &app.SchemaVersion,
			&app.EventKey, &app.ObservedAt, &app.DevEUI, &gatewayID,
			&gatewayUplinkID, &gatewayFrequency, &gatewayContext,
			&gatewayRSSI, &gatewaySNR, &decoderVersion, &rawData,
		); err != nil {
			return ApplicationEvidence{}, fmt.Errorf("scan application evidence: %w", err)
		}
		if gatewayID.Valid {
			value := gatewayID.String
			app.GatewayID = &value
		}
		if gatewayUplinkID.Valid {
			value := gatewayUplinkID.Int64
			app.GatewayUplinkID = &value
		}
		if gatewayFrequency.Valid {
			value := gatewayFrequency.Int64
			app.GatewayFrequencyHz = &value
		}
		if gatewayContext.Valid {
			value := gatewayContext.String
			app.GatewayContextBase64 = &value
		}
		if gatewayRSSI.Valid {
			value := gatewayRSSI.Int32
			app.GatewayRSSIDbm = &value
		}
		if gatewaySNR.Valid {
			value := gatewaySNR.Float64
			app.GatewaySNRDb = &value
		}
		if decoderVersion.Valid {
			value := decoderVersion.String
			app.OperationalDecoderVersion = &value
		}
		if rawData.Valid {
			value := rawData.String
			app.RawDataBase64 = &value
		}
		candidates = append(candidates, app)
	}
	if err := rows.Err(); err != nil {
		return ApplicationEvidence{}, fmt.Errorf("iterate application evidence: %w", err)
	}
	if len(candidates) == 0 {
		return ApplicationEvidence{}, ErrApplicationMissing
	}
	if len(candidates) != 1 {
		return ApplicationEvidence{}, ErrApplicationAmbiguous
	}
	app := candidates[0]

	metricRows, err := r.pool.Query(ctx, `
SELECT dev_eui, metric_name, metric_value, metric_text,
       metric_bool, unit, quality, source_field
FROM telemetry.measurements
WHERE event_key = $1 AND time = $2
ORDER BY metric_name, unit, measurement_id`, app.EventKey, app.ObservedAt)
	if err != nil {
		return ApplicationEvidence{}, fmt.Errorf("load telemetry measurements: %w", err)
	}
	defer metricRows.Close()
	for metricRows.Next() {
		var metric StoredMetric
		var number pgtype.Float8
		var text, sourceField pgtype.Text
		var boolean pgtype.Bool
		if err := metricRows.Scan(
			&metric.DevEUI, &metric.MetricName, &number, &text,
			&boolean, &metric.Unit, &metric.Quality, &sourceField,
		); err != nil {
			return ApplicationEvidence{}, fmt.Errorf("scan telemetry measurement: %w", err)
		}
		if number.Valid {
			value := number.Float64
			metric.ValueNumber = &value
		}
		if text.Valid {
			value := text.String
			metric.ValueText = &value
		}
		if boolean.Valid {
			value := boolean.Bool
			metric.ValueBool = &value
		}
		if sourceField.Valid {
			metric.SourceField = sourceField.String
		}
		app.Measurements = append(app.Measurements, metric)
	}
	if err := metricRows.Err(); err != nil {
		return ApplicationEvidence{}, fmt.Errorf("iterate telemetry measurements: %w", err)
	}
	return app, nil
}

func (r *PostgresRepository) LoadMQTT(ctx context.Context, app ApplicationEvidence) (MQTTEvidence, error) {
	if !app.HasGatewayProvenance() {
		return MQTTEvidence{}, ErrMQTTMissing
	}
	rows, err := r.pool.Query(ctx, `
SELECT gateway_event_id, gateway_id, mqtt_topic, capture_key_sha256,
       serialized_event_sha256, phy_payload_sha256, uplink_id,
       frequency_hz, rssi_dbm, snr_db, gateway_context_base64,
       correlation_digest_sha256, object_ref
FROM gateway_evidence.mqtt_gateway_events
WHERE gateway_id = $1
  AND uplink_id = $2
  AND frequency_hz = $3
  AND gateway_context_base64 = $4
  AND correlation_digest_sha256 IS NOT NULL
ORDER BY gateway_event_id
LIMIT 2`, *app.GatewayID, strconv.FormatInt(*app.GatewayUplinkID, 10), *app.GatewayFrequencyHz, *app.GatewayContextBase64)
	if err != nil {
		return MQTTEvidence{}, fmt.Errorf("load MQTT evidence: %w", err)
	}
	defer rows.Close()

	var candidates []MQTTEvidence
	for rows.Next() {
		var item MQTTEvidence
		if err := rows.Scan(
			&item.GatewayEventID, &item.GatewayID, &item.MQTTTopic,
			&item.CaptureKeySHA256, &item.SerializedEventSHA256,
			&item.PHYPayloadSHA256, &item.UplinkID, &item.FrequencyHz,
			&item.RSSIDbm, &item.SNRDb, &item.GatewayContextBase64,
			&item.CorrelationDigestSHA256, &item.ObjectRef,
		); err != nil {
			return MQTTEvidence{}, fmt.Errorf("scan MQTT evidence: %w", err)
		}
		candidates = append(candidates, item)
	}
	if err := rows.Err(); err != nil {
		return MQTTEvidence{}, fmt.Errorf("iterate MQTT evidence: %w", err)
	}
	if len(candidates) == 0 {
		return MQTTEvidence{}, ErrMQTTMissing
	}
	if len(candidates) != 1 {
		return MQTTEvidence{}, ErrMQTTAmbiguous
	}
	return candidates[0], nil
}

func (r *PostgresRepository) ListJournalSegments(ctx context.Context, gatewayID string) ([]JournalSegmentMetadata, error) {
	rows, err := r.pool.Query(ctx, `
SELECT gateway_id, segment_id, first_sequence, last_sequence, record_count,
       previous_segment_hash, final_record_hash, segment_hash,
       object_ref, object_sha256
FROM gateway_evidence.segments
WHERE gateway_id = $1
ORDER BY segment_id`, gatewayID)
	if err != nil {
		return nil, fmt.Errorf("list journal segments: %w", err)
	}
	defer rows.Close()
	var segments []JournalSegmentMetadata
	for rows.Next() {
		var item JournalSegmentMetadata
		if err := rows.Scan(
			&item.GatewayID, &item.SegmentID, &item.FirstSequence,
			&item.LastSequence, &item.RecordCount, &item.PreviousSegmentHash,
			&item.FinalRecordHash, &item.SegmentHash, &item.ObjectRef,
			&item.ObjectSHA256,
		); err != nil {
			return nil, fmt.Errorf("scan journal segment: %w", err)
		}
		segments = append(segments, item)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate journal segments: %w", err)
	}
	return segments, nil
}

func (r *PostgresRepository) LoadCheckpoint(ctx context.Context, segment JournalSegmentMetadata) (CheckpointEvidence, error) {
	var item CheckpointEvidence
	err := r.pool.QueryRow(ctx, `
SELECT checkpoint_id, checkpoint_version, gateway_id, segment_id, last_sequence,
       last_record_hash, segment_hash, gateway_created_at, checkpoint_digest
FROM gateway_evidence.checkpoints
WHERE gateway_id = $1 AND last_sequence = $2`, segment.GatewayID, segment.LastSequence).Scan(
		&item.CheckpointID, &item.CheckpointVersion, &item.GatewayID, &item.SegmentID, &item.LastSequence,
		&item.LastRecordHash, &item.SegmentHash, &item.GatewayCreatedAt, &item.CheckpointDigest,
	)
	if errors.Is(err, pgx.ErrNoRows) {
		return CheckpointEvidence{}, ErrCheckpointMissing
	}
	if err != nil {
		return CheckpointEvidence{}, fmt.Errorf("load checkpoint evidence: %w", err)
	}
	if item.CheckpointVersion != "gateway-checkpoint-v1" || item.GatewayID != segment.GatewayID || item.SegmentID != segment.SegmentID ||
		item.LastSequence != segment.LastSequence || item.LastRecordHash != segment.FinalRecordHash ||
		item.SegmentHash != segment.SegmentHash || checkpointEvidenceDigest(item) != item.CheckpointDigest {
		return CheckpointEvidence{}, ErrCheckpointMismatch
	}
	return item, nil
}

func checkpointEvidenceDigest(item CheckpointEvidence) string {
	parts := []string{
		"gateway-checkpoint-v1",
		item.GatewayID,
		strconv.FormatInt(item.SegmentID, 10),
		strconv.FormatInt(item.LastSequence, 10),
		item.LastRecordHash,
		item.SegmentHash,
		item.GatewayCreatedAt.UTC().Format(time.RFC3339Nano),
	}
	digest := sha256.Sum256([]byte(strings.Join(parts, "\x00")))
	return hex.EncodeToString(digest[:])
}

func (r *PostgresRepository) CompleteVerified(ctx context.Context, verificationID int64, workerID string, evidence LineageEvidence) error {
	workerID = strings.TrimSpace(workerID)
	if workerID == "" || len(workerID) > 128 {
		return errors.New("verifier worker ID must be 1 through 128 characters")
	}
	tag, err := r.pool.Exec(ctx, `
UPDATE gateway_evidence.event_verification
SET gateway_id = $3,
    journal_segment_id = $4,
    journal_sequence = $5,
    journal_record_hash = $6,
    journal_segment_hash = $7,
    checkpoint_id = $8,
    gateway_event_id = $9,
    decoder_id = NULLIF($10, ''),
    decoder_version = NULLIF($11, ''),
    raw_app_data_sha256 = NULLIF($12, ''),
    normalized_digest_sha256 = NULLIF($13, ''),
    status = 'verified',
    reason_code = NULL,
    worker_id = NULL,
    lease_expires_at = NULL,
    verified_at = now(),
    updated_at = now()
WHERE verification_id = $1
  AND status = 'pending'
  AND worker_id = $2
  AND lease_expires_at > now()`,
		verificationID, workerID, evidence.GatewayID,
		evidence.JournalSegmentID, evidence.JournalSequence,
		evidence.JournalRecordHash, evidence.JournalSegmentHash,
		evidence.CheckpointID, evidence.GatewayEventID,
		evidence.Decoder.DecoderID, evidence.Decoder.DecoderVersion,
		evidence.Decoder.RawAppDataSHA256, evidence.Decoder.NormalizedDigestSHA256,
	)
	if err != nil {
		return fmt.Errorf("complete verifier verified transition: %w", err)
	}
	if tag.RowsAffected() != 1 {
		return ErrLeaseLost
	}
	return nil
}

func (r *PostgresRepository) ReleasePending(ctx context.Context, verificationID int64, workerID, reason string, retryAfter time.Duration) error {
	retrySeconds := int64(retryAfter / time.Second)
	if retrySeconds < 1 || retrySeconds > 86400 {
		return errors.New("verifier retry interval must be from 1 second through 24 hours")
	}
	if err := validateReason(reason); err != nil {
		return err
	}
	tag, err := r.pool.Exec(ctx, `
UPDATE gateway_evidence.event_verification
SET worker_id = NULL,
    lease_expires_at = NULL,
    reason_code = $3,
    next_attempt_at = now() + make_interval(secs => $4::double precision),
    updated_at = now()
WHERE verification_id = $1
  AND status = 'pending'
  AND worker_id = $2`, verificationID, workerID, reason, retrySeconds)
	if err != nil {
		return fmt.Errorf("release pending verifier work: %w", err)
	}
	if tag.RowsAffected() != 1 {
		return ErrLeaseLost
	}
	return nil
}

func (r *PostgresRepository) CompleteIntegrityFailure(ctx context.Context, verificationID int64, workerID, reason string, evidence DecoderEvidence) error {
	if err := validateReason(reason); err != nil {
		return err
	}
	tag, err := r.pool.Exec(ctx, `
UPDATE gateway_evidence.event_verification
SET gateway_id = $3,
    decoder_id = NULLIF($4, ''),
    decoder_version = NULLIF($5, ''),
    raw_app_data_sha256 = NULLIF($6, ''),
    normalized_digest_sha256 = NULLIF($7, ''),
    status = 'integrity_failure',
    reason_code = $8,
    worker_id = NULL,
    lease_expires_at = NULL,
    verified_at = NULL,
    updated_at = now()
WHERE verification_id = $1
  AND status = 'pending'
  AND worker_id = $2`,
		verificationID, workerID, evidence.GatewayID,
		evidence.DecoderID, evidence.DecoderVersion,
		evidence.RawAppDataSHA256, evidence.NormalizedDigestSHA256, reason,
	)
	if err != nil {
		return fmt.Errorf("complete verifier integrity failure: %w", err)
	}
	if tag.RowsAffected() != 1 {
		return ErrLeaseLost
	}
	return nil
}

func validateReason(reason string) error {
	reason = strings.TrimSpace(reason)
	if reason == "" || len(reason) > 128 {
		return errors.New("verifier reason code must be 1 through 128 characters")
	}
	return nil
}
