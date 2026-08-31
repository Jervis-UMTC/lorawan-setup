package mqttcollector

import (
	"context"
	"errors"
	"fmt"

	"github.com/jackc/pgx/v5"
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

func (r *PostgresRepository) Ping(ctx context.Context) error {
	return r.pool.Ping(ctx)
}

func (r *PostgresRepository) PutCapture(ctx context.Context, record CaptureRecord) (bool, error) {
	var phySHA, uplinkID, gatewayContext, correlation any
	var frequency, rssi, snr any
	if record.HasUplinkProjection {
		phySHA = record.PHYPayloadSHA256
		uplinkID = record.UplinkID
		frequency = record.FrequencyHz
		rssi = record.RSSIDbm
		snr = record.SNRDb
		gatewayContext = record.GatewayContextBase64
		correlation = record.CorrelationDigestSHA256
	}

	var id int64
	err := r.pool.QueryRow(ctx, `
INSERT INTO gateway_evidence.mqtt_gateway_events (
    gateway_id, mqtt_topic, broker_received_at,
    capture_key_sha256, serialized_event_sha256,
    phy_payload_sha256, uplink_id, frequency_hz, rssi_dbm, snr_db,
    gateway_context_base64, correlation_digest_sha256, collector_version, object_ref
) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
ON CONFLICT (capture_key_sha256) DO NOTHING
RETURNING gateway_event_id`,
		record.GatewayID, record.MQTTTopic, record.BrokerReceivedAt,
		record.CaptureKeySHA256, record.SerializedEventSHA256,
		phySHA, uplinkID, frequency, rssi, snr, gatewayContext, correlation,
		record.CollectorVersion, record.ObjectRef,
	).Scan(&id)
	if err == nil {
		return true, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return false, fmt.Errorf("insert MQTT evidence capture: %w", err)
	}

	var existing CaptureRecord
	err = r.pool.QueryRow(ctx, `
SELECT gateway_id, mqtt_topic, capture_key_sha256,
       serialized_event_sha256, object_ref,
       correlation_digest_sha256 IS NOT NULL,
       COALESCE(phy_payload_sha256, ''), COALESCE(uplink_id, ''),
       COALESCE(frequency_hz, 0), COALESCE(rssi_dbm, 0), COALESCE(snr_db, 0),
       COALESCE(gateway_context_base64, ''), COALESCE(correlation_digest_sha256, '')
FROM gateway_evidence.mqtt_gateway_events
WHERE capture_key_sha256 = $1`, record.CaptureKeySHA256).Scan(
		&existing.GatewayID,
		&existing.MQTTTopic,
		&existing.CaptureKeySHA256,
		&existing.SerializedEventSHA256,
		&existing.ObjectRef,
		&existing.HasUplinkProjection,
		&existing.PHYPayloadSHA256,
		&existing.UplinkID,
		&existing.FrequencyHz,
		&existing.RSSIDbm,
		&existing.SNRDb,
		&existing.GatewayContextBase64,
		&existing.CorrelationDigestSHA256,
	)
	if err != nil {
		return false, fmt.Errorf("read accepted MQTT evidence capture: %w", err)
	}
	if !sameAuthoritativeCapture(existing, record) {
		return false, ErrCaptureConflict
	}
	return false, nil
}
