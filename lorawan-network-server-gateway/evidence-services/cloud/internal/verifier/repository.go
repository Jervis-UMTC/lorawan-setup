package verifier

import (
	"context"
	"errors"
	"time"
)

var (
	ErrLeaseLost            = errors.New("verification work lease is no longer owned")
	ErrApplicationMissing   = errors.New("application evidence source is missing")
	ErrApplicationAmbiguous = errors.New("application evidence source is ambiguous")
	ErrMQTTMissing          = errors.New("MQTT evidence source is missing")
	ErrMQTTAmbiguous        = errors.New("MQTT evidence source is ambiguous")
	ErrCheckpointMissing    = errors.New("checkpoint evidence is missing")
	ErrCheckpointMismatch   = errors.New("checkpoint evidence conflicts with verified segment")
)

type Repository interface {
	Ping(ctx context.Context) error
	Discover(ctx context.Context, limit int) (created int64, err error)
	Claim(ctx context.Context, workerID string, lease time.Duration) (*Work, error)
	LoadApplication(ctx context.Context, work Work) (ApplicationEvidence, error)
	LoadMQTT(ctx context.Context, app ApplicationEvidence) (MQTTEvidence, error)
	ListJournalSegments(ctx context.Context, gatewayID string) ([]JournalSegmentMetadata, error)
	LoadCheckpoint(ctx context.Context, segment JournalSegmentMetadata) (CheckpointEvidence, error)
	ReleasePending(ctx context.Context, verificationID int64, workerID, reason string, retryAfter time.Duration) error
	CompleteVerified(ctx context.Context, verificationID int64, workerID string, evidence LineageEvidence) error
	CompleteIntegrityFailure(ctx context.Context, verificationID int64, workerID, reason string, evidence DecoderEvidence) error
}
