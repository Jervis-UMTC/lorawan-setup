package fabricadapter

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"regexp"
	"strings"
	"sync/atomic"
	"time"
)

var (
	ErrLocalSealInvalid     = errors.New("local Fabric evidence seal is invalid")
	ErrEvidenceConstruction = errors.New("Fabric evidence construction failed")
)

var hrcRecordIDPattern = regexp.MustCompile(`^[A-Za-z0-9._:-]{1,128}$`)

type SignerOperationError struct {
	Err error
}

func (e *SignerOperationError) Error() string { return e.Err.Error() }
func (e *SignerOperationError) Unwrap() error { return e.Err }

type Worker struct {
	repository      Repository
	signer          EvidenceSigner
	ledger          LedgerClient
	workerID        string
	processingLease time.Duration
	maxAttempts     int
	retryBase       time.Duration
	retryMax        time.Duration
	retryJitter     time.Duration
	sourceSystemID  string
}

func NewWorker(repository Repository, signer EvidenceSigner, ledger LedgerClient, cfg Config) (*Worker, error) {
	if repository == nil || signer == nil || ledger == nil {
		return nil, errors.New("Fabric adapter repository, signer, and ledger client are required")
	}
	if strings.TrimSpace(cfg.WorkerID) == "" || len(cfg.WorkerID) > 128 {
		return nil, errors.New("Fabric adapter worker ID must be 1 through 128 characters")
	}
	if cfg.ProcessingLease < 10*time.Second || cfg.ProcessingLease > time.Hour {
		return nil, errors.New("Fabric adapter processing lease must be 10 seconds through 1 hour")
	}
	if cfg.MaxAttempts < 1 || cfg.RetryBase <= 0 || cfg.RetryMax < cfg.RetryBase || cfg.RetryJitter < 0 {
		return nil, errors.New("Fabric adapter retry configuration is invalid")
	}
	if !hrcSourceIDPattern.MatchString(cfg.FabricSourceSystemID) {
		return nil, errors.New("Fabric authenticated source-system ID is invalid")
	}
	return &Worker{
		repository:      repository,
		signer:          signer,
		ledger:          ledger,
		workerID:        cfg.WorkerID,
		processingLease: cfg.ProcessingLease,
		maxAttempts:     cfg.MaxAttempts,
		retryBase:       cfg.RetryBase,
		retryMax:        cfg.RetryMax,
		retryJitter:     cfg.RetryJitter,
		sourceSystemID:  cfg.FabricSourceSystemID,
	}, nil
}

func (w *Worker) RunOnce(ctx context.Context) (bool, error) {
	work, err := w.repository.ClaimReconciliation(ctx, w.workerID, w.processingLease)
	if err != nil {
		return false, fmt.Errorf("claim Fabric reconciliation work: %w", err)
	}
	if work != nil {
		return true, w.withLeaseHeartbeat(ctx, *work, w.reconcile)
	}

	work, err = w.repository.ClaimWork(ctx, w.workerID, w.processingLease)
	if err != nil {
		return false, fmt.Errorf("claim Fabric submission work: %w", err)
	}
	if work == nil {
		return false, nil
	}
	return true, w.withLeaseHeartbeat(ctx, *work, w.process)
}

func (w *Worker) withLeaseHeartbeat(ctx context.Context, work OutboxWork, fn func(context.Context, OutboxWork) error) error {
	opCtx, cancel := context.WithCancel(ctx)
	defer cancel()

	interval := w.processingLease / 3
	if interval < time.Second {
		interval = time.Second
	}
	leaseErrCh := make(chan error, 1)
	var finished atomic.Bool
	go func() {
		ticker := time.NewTicker(interval)
		defer ticker.Stop()
		for {
			select {
			case <-opCtx.Done():
				return
			case <-ticker.C:
				renewCtx, renewCancel := context.WithTimeout(opCtx, interval)
				err := w.repository.RenewLease(renewCtx, work.OutboxID, w.workerID, w.processingLease)
				renewCancel()
				if err != nil {
					if finished.Load() {
						return
					}
					select {
					case leaseErrCh <- err:
					default:
					}
					cancel()
					return
				}
			}
		}
	}()

	err := fn(opCtx, work)
	finished.Store(true)
	cancel()
	select {
	case leaseErr := <-leaseErrCh:
		return leaseErr
	default:
		return err
	}
}

func (w *Worker) process(ctx context.Context, work OutboxWork) error {
	if work.Attempts > w.maxAttempts {
		return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "max_attempts_exceeded", "Fabric adapter maximum attempts exceeded before processing")
	}
	if work.SchemaVersion != SchemaVersionV1 && work.SchemaVersion != SchemaVersionV2 {
		return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "unsupported_schema", "unsupported Fabric evidence schema version")
	}

	seal, err := w.obtainSeal(ctx, work)
	if err != nil {
		if errors.Is(err, ErrLeaseLost) {
			return err
		}
		if errors.Is(err, ErrEvidenceConstruction) || errors.Is(err, ErrLocalSealInvalid) {
			return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "evidence_seal_failure", boundedError(err))
		}
		var signerErr *SignerOperationError
		if errors.As(err, &signerErr) {
			if IsTransientOpenBaoError(signerErr.Err) {
				return w.retryFailure(ctx, work, "openbao_unavailable", signerErr.Err)
			}
			return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "evidence_signing_failure", boundedError(signerErr.Err))
		}
		return err
	}

	if err := w.verifySeal(ctx, seal); err != nil {
		if errors.Is(err, ErrLocalSealInvalid) || errors.Is(err, ErrSignatureRejected) {
			return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "invalid_local_seal", boundedError(err))
		}
		var signerErr *SignerOperationError
		if errors.As(err, &signerErr) {
			if IsTransientOpenBaoError(signerErr.Err) {
				return w.retryFailure(ctx, work, "openbao_verify_unavailable", signerErr.Err)
			}
			return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "openbao_verify_permanent_failure", boundedError(signerErr.Err))
		}
		return err
	}

	anchor, err := w.buildAnchor(ctx, work)
	if err != nil {
		if errors.Is(err, ErrEvidenceConstruction) {
			return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "fabric_anchor_construction_failure", boundedError(err))
		}
		return err
	}
	prepared, prepareErr := w.ledger.Prepare(ctx, anchor)
	if prepareErr != nil {
		if IsPermanentFabricError(prepareErr) {
			return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "fabric_prepare_permanent_failure", boundedError(prepareErr))
		}
		return w.retryFailure(ctx, work, "fabric_prepare_failure", prepareErr)
	}
	if prepared.TransactionID == "" || prepared.RecordID == "" || len(prepared.PreparedTransaction) == 0 || len(prepared.CommitStatusRequest) == 0 {
		return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "fabric_prepare_invalid", "Fabric preparation returned incomplete durable transaction material")
	}
	if err := w.repository.PersistPreparedSubmission(ctx, work.OutboxID, w.workerID, prepared.TransactionID, prepared.RecordID, prepared.PreparedTransaction, prepared.CommitStatusRequest); err != nil {
		return err
	}
	result, submitErr := w.ledger.SubmitPrepared(ctx, prepared)
	if result.TransactionID == "" {
		result.TransactionID = prepared.TransactionID
	}
	if result.Committed && result.TransactionID == prepared.TransactionID && submitErr == nil {
		return w.confirmAnchor(ctx, work, anchor, result.TransactionID, prepared.RecordID)
	}
	if result.Unknown {
		return w.repository.MarkSubmittedUnknown(ctx, work.OutboxID, w.workerID, prepared.TransactionID, w.retryDelay(work.Attempts), boundedError(submitErr))
	}
	if result.TransactionID != "" && !result.Committed {
		return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "fabric_commit_invalid", boundedError(submitErr))
	}
	return w.repository.MarkSubmittedUnknown(ctx, work.OutboxID, w.workerID, prepared.TransactionID, w.retryDelay(work.Attempts), boundedError(submitErr))
}

func (w *Worker) buildAnchor(ctx context.Context, work OutboxWork) (FabricAnchor, error) {
	if !hrcRecordIDPattern.MatchString(work.SourceEventKey) {
		return FabricAnchor{}, fmt.Errorf("%w: source_event_key is not a valid HRC SourceRecordID", ErrEvidenceConstruction)
	}
	source, err := w.repository.LoadSource(ctx, work)
	if err != nil {
		if errors.Is(err, ErrSourceMissing) {
			return FabricAnchor{}, fmt.Errorf("%w: source row missing", ErrEvidenceConstruction)
		}
		return FabricAnchor{}, fmt.Errorf("load Fabric anchor source: %w", err)
	}
	// HRC Task 37 protects the exact finalized JSON artifact emitted at the
	// upstream acceptance boundary. finalized_payload is immutable BYTEA on the
	// outbox row; never reconstruct it from JSONB, structs, maps, or projections.
	payload := append([]byte(nil), work.FinalizedPayload...)
	if err := validateFinalizedExactPayload(payload); err != nil {
		return FabricAnchor{}, fmt.Errorf("%w: %v", ErrEvidenceConstruction, err)
	}
	digestBytes := sha256.Sum256(payload)
	digest := hex.EncodeToString(digestBytes[:])
	if work.SchemaVersion == SchemaVersionV2 {
		verification, err := w.repository.LoadVerification(ctx, work)
		if err != nil {
			if errors.Is(err, ErrVerificationMissing) {
				return FabricAnchor{}, fmt.Errorf("%w: verified gateway row missing", ErrEvidenceConstruction)
			}
			return FabricAnchor{}, fmt.Errorf("load gateway verification for Fabric anchor: %w", err)
		}
		if verification.Status != "verified" {
			return FabricAnchor{}, fmt.Errorf("%w: gateway evidence is not verified", ErrEvidenceConstruction)
		}
	}
	producer := strings.TrimSpace(source.DevEUI)
	if producer == "" || len(producer) > 128 || strings.TrimSpace(work.EventType) == "" || len(strings.TrimSpace(work.EventType)) > 128 || len(work.SchemaVersion) > 128 {
		return FabricAnchor{}, fmt.Errorf("%w: HRC source metadata is invalid", ErrEvidenceConstruction)
	}
	return FabricAnchor{
		AuthenticatedSourceSystemID: w.sourceSystemID,
		SourceRecordID:              work.SourceEventKey,
		Digest:                      digest,
		PayloadLength:               len(payload),
		ExactPayload:                append([]byte(nil), payload...),
		SourceType:                  strings.TrimSpace(work.EventType),
		Producer:                    producer,
		ProducedAt:                  work.ObservedAt.UTC().Format(time.RFC3339Nano),
		SchemaVersion:               strings.TrimSpace(work.SchemaVersion),
	}, nil
}

func validateFinalizedExactPayload(payload []byte) error {
	if len(payload) < 1 {
		return errors.New("exact finalized JSON payload must contain at least 1 byte")
	}
	if len(payload) > maxFabricExactPayloadBytes {
		return fmt.Errorf("exact finalized JSON payload exceeds HRC maximum of %d bytes", maxFabricExactPayloadBytes)
	}
	if !json.Valid(payload) {
		return errors.New("exact finalized payload is not valid JSON bytes")
	}
	return nil
}

func (w *Worker) confirmAnchor(ctx context.Context, work OutboxWork, anchor FabricAnchor, txID, recordID string) error {
	query, err := w.ledger.Query(ctx, anchor.AuthenticatedSourceSystemID, anchor.SourceRecordID)
	if err != nil {
		return w.repository.MarkSubmittedUnknown(ctx, work.OutboxID, w.workerID, txID, w.retryDelay(maxInt(work.Attempts, 1)), boundedError(err))
	}
	if err := validateAnchorQuery(anchor, recordID, query); err != nil {
		return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "fabric_anchor_conflict", boundedError(err))
	}
	verification, err := w.ledger.VerifyDigest(ctx, anchor.AuthenticatedSourceSystemID, anchor.SourceRecordID, anchor.Digest)
	if err != nil {
		return w.repository.MarkSubmittedUnknown(ctx, work.OutboxID, w.workerID, txID, w.retryDelay(maxInt(work.Attempts, 1)), boundedError(err))
	}
	if err := validateDigestVerification(recordID, anchor.Digest, verification); err != nil {
		return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "fabric_digest_mismatch", boundedError(err))
	}
	return w.repository.MarkConfirmed(ctx, work.OutboxID, w.workerID, txID)
}

func validateAnchorQuery(expected FabricAnchor, expectedRecordID string, actual FabricQueryResult) error {
	if !actual.Found {
		return errors.New("Fabric QuerySourceBoundAnchor did not find the committed anchor")
	}
	if expectedRecordID == "" || actual.RecordID != expectedRecordID || actual.DigestAlgorithm != "sha256" {
		return errors.New("Fabric QuerySourceBoundAnchor record identity or digest algorithm does not match the prepared anchor")
	}
	if actual.AuthenticatedSourceSystemID != expected.AuthenticatedSourceSystemID || actual.SourceRecordID != expected.SourceRecordID ||
		actual.Digest != expected.Digest || actual.PayloadLength != expected.PayloadLength || actual.SourceType != expected.SourceType ||
		actual.Producer != expected.Producer || actual.ProducedAt != expected.ProducedAt || actual.SchemaVersion != expected.SchemaVersion {
		return errors.New("Fabric QuerySourceBoundAnchor fields do not match the submitted anchor")
	}
	return nil
}

func validateDigestVerification(expectedRecordID, expectedDigest string, actual FabricVerifyResult) error {
	if strings.TrimSpace(expectedRecordID) == "" || strings.TrimSpace(expectedDigest) == "" {
		return errors.New("Fabric VerifySourceBoundDigest expected identity is incomplete")
	}
	if actual.Outcome != "MATCH" {
		return fmt.Errorf("Fabric VerifySourceBoundDigest outcome is %q, expected MATCH", actual.Outcome)
	}
	if actual.RecordID != expectedRecordID {
		return errors.New("Fabric VerifySourceBoundDigest record_id does not match the prepared anchor")
	}
	if actual.ExpectedDigest != expectedDigest || actual.ObservedDigest != expectedDigest {
		return errors.New("Fabric VerifySourceBoundDigest digest fields do not match the prepared anchor")
	}
	return nil
}

func (w *Worker) obtainSeal(ctx context.Context, work OutboxWork) (Seal, error) {
	if work.CanonicalJSON != nil {
		return w.repository.LoadSeal(ctx, work.OutboxID)
	}
	source, err := w.repository.LoadSource(ctx, work)
	if err != nil {
		if errors.Is(err, ErrSourceMissing) {
			return Seal{}, fmt.Errorf("%w: source row missing", ErrEvidenceConstruction)
		}
		return Seal{}, fmt.Errorf("load Fabric source evidence: %w", err)
	}
	var verification *VerificationRow
	if work.SchemaVersion == SchemaVersionV2 {
		row, err := w.repository.LoadVerification(ctx, work)
		if err != nil {
			if errors.Is(err, ErrVerificationMissing) {
				return Seal{}, fmt.Errorf("%w: verified gateway row missing", ErrEvidenceConstruction)
			}
			return Seal{}, fmt.Errorf("load verified gateway evidence: %w", err)
		}
		verification = &row
	}
	evidence, err := BuildEvidence(work, source, verification)
	if err != nil {
		return Seal{}, fmt.Errorf("%w: %v", ErrEvidenceConstruction, err)
	}
	canonical, err := CanonicalizeEvidence(evidence)
	if err != nil {
		return Seal{}, fmt.Errorf("%w: %v", ErrEvidenceConstruction, err)
	}
	signature, keyID, err := w.signer.Sign(ctx, canonical.CanonicalJSON)
	if err != nil {
		return Seal{}, &SignerOperationError{Err: err}
	}
	if signature == "" || keyID == "" {
		return Seal{}, fmt.Errorf("%w: signer returned incomplete seal metadata", ErrLocalSealInvalid)
	}
	if _, err := w.repository.PersistSeal(ctx, work.OutboxID, w.workerID, canonical, signature, keyID); err != nil {
		return Seal{}, err
	}
	return w.repository.LoadSeal(ctx, work.OutboxID)
}

func (w *Worker) reconcile(ctx context.Context, work OutboxWork) error {
	if work.FabricTxID == nil || strings.TrimSpace(*work.FabricTxID) == "" {
		return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "reconciliation_txid_missing", "submitted/expired Fabric work has no transaction ID")
	}
	txID := strings.TrimSpace(*work.FabricTxID)
	if work.FabricRecordID == nil || strings.TrimSpace(*work.FabricRecordID) == "" {
		return w.repository.MarkSubmittedUnknown(ctx, work.OutboxID, w.workerID, txID, w.retryDelay(maxInt(work.Attempts, 1)), "durable HRC record_id is missing; governed reconciliation is required")
	}
	recordID := strings.TrimSpace(*work.FabricRecordID)

	seal, err := w.repository.LoadSeal(ctx, work.OutboxID)
	if err != nil {
		return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "reconciliation_seal_missing", boundedError(err))
	}
	if err := w.verifySeal(ctx, seal); err != nil {
		if errors.Is(err, ErrLocalSealInvalid) || errors.Is(err, ErrSignatureRejected) {
			return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "invalid_local_seal", boundedError(err))
		}
		var signerErr *SignerOperationError
		if errors.As(err, &signerErr) && IsTransientOpenBaoError(signerErr.Err) {
			return w.repository.MarkSubmittedUnknown(ctx, work.OutboxID, w.workerID, txID, w.retryDelay(maxInt(work.Attempts, 1)), boundedError(signerErr.Err))
		}
		if errors.As(err, &signerErr) {
			return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "openbao_verify_permanent_failure", boundedError(signerErr.Err))
		}
		return err
	}
	anchor, err := w.buildAnchor(ctx, work)
	if err != nil {
		if errors.Is(err, ErrEvidenceConstruction) {
			return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "fabric_anchor_construction_failure", boundedError(err))
		}
		return err
	}

	query, queryErr := w.ledger.Query(ctx, anchor.AuthenticatedSourceSystemID, anchor.SourceRecordID)
	if queryErr == nil && query.Found {
		if err := validateAnchorQuery(anchor, recordID, query); err != nil {
			return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "fabric_anchor_conflict", boundedError(err))
		}
		verification, err := w.ledger.VerifyDigest(ctx, anchor.AuthenticatedSourceSystemID, anchor.SourceRecordID, anchor.Digest)
		if err != nil {
			return w.repository.MarkSubmittedUnknown(ctx, work.OutboxID, w.workerID, txID, w.retryDelay(maxInt(work.Attempts, 1)), boundedError(err))
		}
		if err := validateDigestVerification(recordID, anchor.Digest, verification); err != nil {
			return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "fabric_digest_mismatch", boundedError(err))
		}
		return w.repository.MarkConfirmed(ctx, work.OutboxID, w.workerID, txID)
	}

	if len(work.FabricCommitRequest) == 0 {
		detail := "Fabric anchor was not confirmed and durable commit-status request is missing"
		if queryErr != nil {
			detail = "Fabric query failed and durable commit-status request is missing: " + boundedError(queryErr)
		}
		return w.repository.MarkSubmittedUnknown(ctx, work.OutboxID, w.workerID, txID, w.retryDelay(maxInt(work.Attempts, 1)), detail)
	}

	statusResult, statusErr := w.ledger.CommitStatus(ctx, txID, work.FabricCommitRequest)
	if statusResult.Committed && statusErr == nil {
		return w.confirmAnchor(ctx, work, anchor, txID, recordID)
	}
	if !statusResult.Unknown && statusErr != nil {
		return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "fabric_commit_invalid", boundedError(statusErr))
	}
	if queryErr != nil && IsPermanentFabricError(queryErr) {
		return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "fabric_reconcile_permanent_failure", boundedError(queryErr))
	}

	// A crash can occur after the endorsed transaction and signed commit-status
	// request are persisted but before the first orderer Submit call. Once both
	// source-bound Query and exact-tx CommitStatus have failed to prove a commit,
	// retry only the same endorsed transaction bytes and transaction ID. Never
	// prepare a new proposal while the prior transaction remains uncertain.
	if len(work.FabricPreparedTx) > 0 {
		prepared := FabricPreparedSubmission{
			TransactionID:       txID,
			PreparedTransaction: append([]byte(nil), work.FabricPreparedTx...),
			CommitStatusRequest: append([]byte(nil), work.FabricCommitRequest...),
			RecordID:            recordID,
		}
		retryResult, retryErr := w.ledger.SubmitPrepared(ctx, prepared)
		if retryResult.TransactionID == "" {
			retryResult.TransactionID = txID
		}
		if retryResult.Committed && retryResult.TransactionID == txID && retryErr == nil {
			return w.confirmAnchor(ctx, work, anchor, txID, recordID)
		}
		if !retryResult.Unknown && retryErr != nil {
			return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "fabric_commit_invalid", boundedError(retryErr))
		}
		detail := "Fabric exact transaction remains unknown after query, commit-status reconciliation, and same-tx resubmit"
		if retryErr != nil {
			detail += ": " + boundedError(retryErr)
		}
		return w.repository.MarkSubmittedUnknown(ctx, work.OutboxID, w.workerID, txID, w.retryDelay(maxInt(work.Attempts, 1)), detail)
	}

	detail := "Fabric submission remains unknown after source-bound query and commit-status reconciliation; prepared transaction bytes are unavailable"
	if queryErr != nil && statusErr != nil {
		detail = fmt.Sprintf("Fabric query failed: %s; commit status failed: %s; prepared transaction bytes are unavailable", boundedError(queryErr), boundedError(statusErr))
	} else if queryErr != nil {
		detail = "Fabric query failed: " + boundedError(queryErr) + "; prepared transaction bytes are unavailable"
	} else if statusErr != nil {
		detail = "Fabric commit status failed: " + boundedError(statusErr) + "; prepared transaction bytes are unavailable"
	}
	return w.repository.MarkSubmittedUnknown(ctx, work.OutboxID, w.workerID, txID, w.retryDelay(maxInt(work.Attempts, 1)), detail)
}

func (w *Worker) verifySeal(ctx context.Context, seal Seal) error {
	if seal.Algorithm != EvidenceSignatureAlgorithm {
		return fmt.Errorf("%w: unsupported evidence signature algorithm", ErrLocalSealInvalid)
	}
	if strings.TrimSpace(seal.CanonicalJSON) == "" || strings.TrimSpace(seal.DigestSHA256) == "" || strings.TrimSpace(seal.SigningKeyID) == "" || strings.TrimSpace(seal.Signature) == "" {
		return fmt.Errorf("%w: incomplete local seal", ErrLocalSealInvalid)
	}
	digest := sha256.Sum256([]byte(seal.CanonicalJSON))
	actual := hex.EncodeToString(digest[:])
	if actual != seal.DigestSHA256 {
		return fmt.Errorf("%w: canonical evidence digest mismatch", ErrLocalSealInvalid)
	}
	if err := w.signer.Verify(ctx, []byte(seal.CanonicalJSON), seal.Signature, seal.SigningKeyID); err != nil {
		if errors.Is(err, ErrSignatureRejected) {
			return err
		}
		return &SignerOperationError{Err: err}
	}
	return nil
}

func (w *Worker) retryFailure(ctx context.Context, work OutboxWork, category string, cause error) error {
	if work.Attempts >= w.maxAttempts {
		return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "max_attempts_exhausted", boundedError(cause))
	}
	return w.repository.MarkFailed(ctx, work.OutboxID, w.workerID, w.retryDelay(maxInt(work.Attempts, 1)), category, boundedError(cause))
}

func (w *Worker) retryDelay(attempt int) time.Duration {
	if attempt < 1 {
		attempt = 1
	}
	delay := w.retryBase
	for i := 1; i < attempt && delay < w.retryMax; i++ {
		if delay > w.retryMax/2 {
			delay = w.retryMax
			break
		}
		delay *= 2
	}
	if delay > w.retryMax {
		delay = w.retryMax
	}
	if w.retryJitter <= 0 {
		return delay
	}
	var raw [8]byte
	if _, err := rand.Read(raw[:]); err != nil {
		return delay
	}
	jitterNanos := uint64(w.retryJitter.Nanoseconds())
	if jitterNanos == 0 {
		return delay
	}
	jitter := time.Duration(binary.LittleEndian.Uint64(raw[:]) % (jitterNanos + 1))
	if delay+jitter > w.retryMax {
		return w.retryMax
	}
	return delay + jitter
}

func boundedError(err error) string {
	if err == nil {
		return ""
	}
	message := strings.TrimSpace(err.Error())
	if len(message) > 1000 {
		message = message[:1000]
	}
	return message
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}
