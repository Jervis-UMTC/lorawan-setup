package verifier

import (
	"context"
	"errors"
	"fmt"
	"time"

	"lorawan/evidence-services/cloud/internal/objectstore"
)

type Worker struct {
	repository     Repository
	store          objectstore.Store
	workerID       string
	lease          time.Duration
	retryAfter     time.Duration
	discoveryLimit int
}

func NewWorker(repository Repository, store objectstore.Store, workerID string, lease, retryAfter time.Duration, discoveryLimit int) (*Worker, error) {
	if repository == nil || store == nil {
		return nil, errors.New("verifier repository and object store are required")
	}
	if workerID == "" {
		return nil, errors.New("verifier worker ID is required")
	}
	if lease < 5*time.Second || lease > time.Hour {
		return nil, errors.New("verifier lease must be 5 seconds through 1 hour")
	}
	if retryAfter < time.Second || retryAfter > 24*time.Hour {
		return nil, errors.New("verifier retry interval must be 1 second through 24 hours")
	}
	if discoveryLimit < 1 || discoveryLimit > 1000 {
		return nil, errors.New("verifier discovery limit must be 1 through 1000")
	}
	return &Worker{repository: repository, store: store, workerID: workerID, lease: lease, retryAfter: retryAfter, discoveryLimit: discoveryLimit}, nil
}

func (w *Worker) RunOnce(ctx context.Context) (bool, error) {
	if _, err := w.repository.Discover(ctx, w.discoveryLimit); err != nil {
		return false, err
	}
	work, err := w.repository.Claim(ctx, w.workerID, w.lease)
	if err != nil || work == nil {
		return false, err
	}

	app, err := w.repository.LoadApplication(ctx, *work)
	if errors.Is(err, ErrApplicationMissing) {
		return true, w.repository.ReleasePending(ctx, work.VerificationID, w.workerID, ReasonApplicationSourceMissing, w.retryAfter)
	}
	if errors.Is(err, ErrApplicationAmbiguous) {
		return true, w.repository.ReleasePending(ctx, work.VerificationID, w.workerID, ReasonApplicationSourceAmbiguous, w.retryAfter)
	}
	if err != nil {
		return true, fmt.Errorf("load application evidence: %w", err)
	}
	if !app.HasGatewayProvenance() {
		return true, w.repository.ReleasePending(ctx, work.VerificationID, w.workerID, ReasonApplicationGatewayMissing, w.retryAfter)
	}

	check := CheckApplication(app)
	if !check.Consistent {
		return true, w.repository.CompleteIntegrityFailure(ctx, work.VerificationID, w.workerID, check.Reason, check.Evidence)
	}

	mqttEvidence, err := w.repository.LoadMQTT(ctx, app)
	if errors.Is(err, ErrMQTTMissing) {
		return true, w.repository.ReleasePending(ctx, work.VerificationID, w.workerID, ReasonMQTTSourceMissing, w.retryAfter)
	}
	if errors.Is(err, ErrMQTTAmbiguous) {
		return true, w.repository.CompleteIntegrityFailure(ctx, work.VerificationID, w.workerID, ReasonMQTTSourceAmbiguous, check.Evidence)
	}
	if err != nil {
		return true, fmt.Errorf("load MQTT evidence: %w", err)
	}
	verifiedMQTT, err := VerifyMQTTObject(ctx, w.store, app, mqttEvidence)
	if errors.Is(err, ErrMQTTIntegrity) {
		return true, w.repository.CompleteIntegrityFailure(ctx, work.VerificationID, w.workerID, ReasonMQTTIntegrityMismatch, check.Evidence)
	}
	if err != nil {
		return true, fmt.Errorf("verify MQTT evidence object: %w", err)
	}

	segments, err := w.repository.ListJournalSegments(ctx, mqttEvidence.GatewayID)
	if err != nil {
		return true, fmt.Errorf("list journal segments: %w", err)
	}
	journalMatch, err := FindJournalRecord(ctx, w.store, segments, verifiedMQTT)
	switch {
	case errors.Is(err, ErrJournalMissing):
		return true, w.repository.ReleasePending(ctx, work.VerificationID, w.workerID, ReasonJournalSourceMissing, w.retryAfter)
	case errors.Is(err, ErrJournalLineagePending):
		return true, w.repository.ReleasePending(ctx, work.VerificationID, w.workerID, ReasonJournalLineagePending, w.retryAfter)
	case errors.Is(err, ErrJournalAmbiguous):
		return true, w.repository.CompleteIntegrityFailure(ctx, work.VerificationID, w.workerID, ReasonJournalSourceAmbiguous, check.Evidence)
	case errors.Is(err, ErrJournalIntegrity):
		return true, w.repository.CompleteIntegrityFailure(ctx, work.VerificationID, w.workerID, ReasonJournalIntegrityMismatch, check.Evidence)
	case err != nil:
		return true, fmt.Errorf("verify journal evidence: %w", err)
	}

	checkpoint, err := w.repository.LoadCheckpoint(ctx, journalMatch.Segment)
	if errors.Is(err, ErrCheckpointMissing) {
		return true, w.repository.ReleasePending(ctx, work.VerificationID, w.workerID, ReasonCheckpointMissing, w.retryAfter)
	}
	if errors.Is(err, ErrCheckpointMismatch) {
		return true, w.repository.CompleteIntegrityFailure(ctx, work.VerificationID, w.workerID, ReasonCheckpointMismatch, check.Evidence)
	}
	if err != nil {
		return true, fmt.Errorf("load checkpoint evidence: %w", err)
	}

	lineage := LineageEvidence{
		GatewayID:          mqttEvidence.GatewayID,
		JournalSegmentID:   journalMatch.Segment.SegmentID,
		JournalSequence:    journalMatch.Record.Body.Sequence,
		JournalRecordHash:  journalMatch.Record.RecordHash,
		JournalSegmentHash: journalMatch.Segment.SegmentHash,
		CheckpointID:       checkpoint.CheckpointID,
		GatewayEventID:     mqttEvidence.GatewayEventID,
		Decoder:            check.Evidence,
	}
	return true, w.repository.CompleteVerified(ctx, work.VerificationID, w.workerID, lineage)
}
