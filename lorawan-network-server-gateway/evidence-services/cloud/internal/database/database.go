package database

import (
	"context"
	"database/sql"
)

const (
	SchemaGatewayEvidence  = "gateway_evidence"
	TableCheckpoints       = "gateway_evidence.checkpoints"
	TableSegments          = "gateway_evidence.segments"
	TableMQTTGatewayEvents = "gateway_evidence.mqtt_gateway_events"
	TableEventVerification = "gateway_evidence.event_verification"
	ViewCheckpointStatus   = "gateway_evidence.checkpoint_status"
	ViewVerificationStatus = "gateway_evidence.verification_status"
)

type Executor interface {
	ExecContext(ctx context.Context, query string, args ...any) (sql.Result, error)
}

type Querier interface {
	QueryContext(ctx context.Context, query string, args ...any) (*sql.Rows, error)
	QueryRowContext(ctx context.Context, query string, args ...any) *sql.Row
}

type DBTX interface {
	Executor
	Querier
}

// These role names are intentionally NOLOGIN shells in migration 001.
// Credential activation is a separate deployment boundary.
const (
	RoleIngestor      = "gateway_evidence_ingestor"
	RoleCollector     = "gateway_evidence_collector"
	RoleVerifier      = "gateway_evidence_verifier"
	RoleFabricAdapter = "fabric_adapter"
)
