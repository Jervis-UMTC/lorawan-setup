package ingest

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"lorawan/evidence-services/cloud/internal/database"
)

const (
	gatewayAdvisoryLockSQL = `SELECT pg_advisory_xact_lock(hashtextextended($1, 0))`
	checkpointIdentitySQL  = `
SELECT checkpoint_digest, server_received_at
FROM gateway_evidence.checkpoints
WHERE gateway_id = $1 AND last_sequence = $2`
	latestCheckpointSQL = `
SELECT last_sequence
FROM gateway_evidence.checkpoints
WHERE gateway_id = $1
ORDER BY last_sequence DESC, checkpoint_id DESC
LIMIT 1`
	insertCheckpointSQL = `
INSERT INTO gateway_evidence.checkpoints (
  gateway_id, checkpoint_version, segment_id, last_sequence,
  last_record_hash, segment_hash, gateway_created_at,
  client_identity, request_id, checkpoint_digest
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NULLIF($9, ''), $10)
RETURNING server_received_at`
	selectSegmentSQL = `
SELECT segment_version, first_sequence, last_sequence, record_count,
       previous_segment_hash, final_record_hash, segment_hash,
       object_ref, object_sha256, uploaded_at
FROM gateway_evidence.segments
WHERE gateway_id = $1 AND segment_id = $2`
	insertSegmentSQL = `
INSERT INTO gateway_evidence.segments (
  gateway_id, segment_version, segment_id, first_sequence, last_sequence,
  record_count, previous_segment_hash, final_record_hash, segment_hash,
  object_ref, object_sha256
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
RETURNING uploaded_at`
	writableRoleProbeSQL = `
SELECT current_database(), current_user,
       pg_has_role(current_user, $1, 'member'),
       pg_is_in_recovery(), current_setting('transaction_read_only')`
)

type PostgresRepository struct {
	pool             *pgxpool.Pool
	expectedDatabase string
}

func NewPostgresRepository(pool *pgxpool.Pool, expectedDatabase string) (*PostgresRepository, error) {
	if pool == nil {
		return nil, errors.New("PostgreSQL pool is required")
	}
	if expectedDatabase == "" {
		return nil, errors.New("expected PostgreSQL database is required")
	}
	return &PostgresRepository{pool: pool, expectedDatabase: expectedDatabase}, nil
}

func (r *PostgresRepository) Ping(ctx context.Context) error {
	if err := r.pool.Ping(ctx); err != nil {
		return errors.New("PostgreSQL ping failed")
	}

	var databaseName, currentUser, transactionReadOnly string
	var roleMember, inRecovery bool
	if err := r.pool.QueryRow(ctx, writableRoleProbeSQL, database.RoleIngestor).Scan(
		&databaseName, &currentUser, &roleMember, &inRecovery, &transactionReadOnly,
	); err != nil {
		return errors.New("PostgreSQL ingest-role validation query failed")
	}
	if databaseName != r.expectedDatabase {
		return fmt.Errorf("PostgreSQL connected to unexpected database %q", databaseName)
	}
	if !roleMember {
		return fmt.Errorf("PostgreSQL user %q is not a member of %s", currentUser, database.RoleIngestor)
	}
	if inRecovery || transactionReadOnly != "off" {
		return errors.New("PostgreSQL ingest endpoint is not writable primary routing")
	}
	return nil
}

func (r *PostgresRepository) PutCheckpoint(ctx context.Context, record CheckpointRecord) (Acceptance, error) {
	tx, err := r.pool.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return Acceptance{}, errors.New("begin checkpoint transaction failed")
	}
	defer func() { _ = tx.Rollback(context.Background()) }()

	if _, err := tx.Exec(ctx, gatewayAdvisoryLockSQL, record.GatewayID); err != nil {
		return Acceptance{}, errors.New("acquire checkpoint gateway lock failed")
	}

	var existingDigest string
	var serverReceivedAt time.Time
	err = tx.QueryRow(ctx, checkpointIdentitySQL, record.GatewayID, record.LastSequence).Scan(&existingDigest, &serverReceivedAt)
	switch {
	case err == nil:
		if existingDigest != record.CheckpointDigest {
			return Acceptance{}, ErrConflict
		}
		if err := tx.Commit(ctx); err != nil {
			return Acceptance{}, errors.New("commit checkpoint idempotent transaction failed")
		}
		return Acceptance{ServerReceivedAt: serverReceivedAt.UTC()}, nil
	case errors.Is(err, pgx.ErrNoRows):
		// No exact accepted identity. Regression is checked against newer history below.
	default:
		return Acceptance{}, errors.New("read checkpoint identity failed")
	}

	var latestSequence int64
	err = tx.QueryRow(ctx, latestCheckpointSQL, record.GatewayID).Scan(&latestSequence)
	switch {
	case err == nil:
		if latestSequence > record.LastSequence {
			return Acceptance{}, ErrRegression
		}
	case errors.Is(err, pgx.ErrNoRows):
		// First checkpoint for this gateway.
	default:
		return Acceptance{}, errors.New("read latest checkpoint failed")
	}

	if err := tx.QueryRow(ctx, insertCheckpointSQL,
		record.GatewayID, CheckpointVersion, record.SegmentID, record.LastSequence,
		record.LastRecordHash, record.SegmentHash, record.GatewayCreatedAt,
		record.ClientIdentity, record.RequestID, record.CheckpointDigest,
	).Scan(&serverReceivedAt); err != nil {
		return Acceptance{}, errors.New("insert checkpoint failed")
	}
	if err := tx.Commit(ctx); err != nil {
		return Acceptance{}, errors.New("commit checkpoint transaction failed")
	}
	return Acceptance{Created: true, ServerReceivedAt: serverReceivedAt.UTC()}, nil
}

func (r *PostgresRepository) PutSegment(ctx context.Context, record SegmentRecord) (Acceptance, error) {
	tx, err := r.pool.BeginTx(ctx, pgx.TxOptions{})
	if err != nil {
		return Acceptance{}, errors.New("begin segment transaction failed")
	}
	defer func() { _ = tx.Rollback(context.Background()) }()

	if _, err := tx.Exec(ctx, gatewayAdvisoryLockSQL, record.GatewayID); err != nil {
		return Acceptance{}, errors.New("acquire segment gateway lock failed")
	}

	var version string
	var existing SegmentRecord
	var serverReceivedAt time.Time
	existing.GatewayID = record.GatewayID
	existing.SegmentID = record.SegmentID
	err = tx.QueryRow(ctx, selectSegmentSQL, record.GatewayID, record.SegmentID).Scan(
		&version,
		&existing.FirstSequence,
		&existing.LastSequence,
		&existing.RecordCount,
		&existing.PreviousSegmentHash,
		&existing.FinalRecordHash,
		&existing.SegmentHash,
		&existing.ObjectRef,
		&existing.ObjectSHA256,
		&serverReceivedAt,
	)
	switch {
	case err == nil:
		if version != SegmentVersion || existing != record {
			return Acceptance{}, ErrConflict
		}
		if err := tx.Commit(ctx); err != nil {
			return Acceptance{}, errors.New("commit segment idempotent transaction failed")
		}
		return Acceptance{ServerReceivedAt: serverReceivedAt.UTC()}, nil
	case errors.Is(err, pgx.ErrNoRows):
		// First metadata record for this segment identity.
	default:
		return Acceptance{}, errors.New("read segment identity failed")
	}

	if err := tx.QueryRow(ctx, insertSegmentSQL,
		record.GatewayID, SegmentVersion, record.SegmentID, record.FirstSequence,
		record.LastSequence, record.RecordCount, record.PreviousSegmentHash,
		record.FinalRecordHash, record.SegmentHash, record.ObjectRef, record.ObjectSHA256,
	).Scan(&serverReceivedAt); err != nil {
		return Acceptance{}, errors.New("insert segment metadata failed")
	}
	if err := tx.Commit(ctx); err != nil {
		return Acceptance{}, errors.New("commit segment transaction failed")
	}
	return Acceptance{Created: true, ServerReceivedAt: serverReceivedAt.UTC()}, nil
}
