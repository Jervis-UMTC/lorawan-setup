package fabricadapter

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
	"time"
)

var (
	ErrLocalSealInvalid     = errors.New("local Fabric evidence seal is invalid")
	ErrEvidenceConstruction = errors.New("Fabric evidence construction failed")
)

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
	}, nil
}

func (w *Worker) RunOnce(ctx context.Context) (bool, error) {
	work, err := w.repository.ClaimReconciliation(ctx, w.workerID, w.processingLease)
	if err != nil {
		return false, fmt.Errorf("claim Fabric reconciliation work: %w", err)
	}
	if work != nil {
		return true, w.reconcile(ctx, *work)
	}

	work, err = w.repository.ClaimWork(ctx, w.workerID, w.processingLease)
	if err != nil {
		return false, fmt.Errorf("claim Fabric submission work: %w", err)
	}
	if work == nil {
		return false, nil
	}
	return true, w.process(ctx, *work)
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

	attestation := FabricAttestation{
		SchemaVersion: work.SchemaVersion,
		EventKey:      work.EventKey,
		EventType:     work.EventType,
		Digest:        seal.DigestSHA256,
		SealAlgorithm: seal.Algorithm,
		SealKeyID:     seal.SigningKeyID,
		SealSignature: seal.Signature,
	}
	result, submitErr := w.ledger.Submit(ctx, attestation)
	if result.Committed && result.TransactionID != "" && submitErr == nil {
		return w.repository.MarkConfirmed(ctx, work.OutboxID, w.workerID, result.TransactionID)
	}
	if result.Unknown && result.TransactionID != "" {
		return w.repository.MarkSubmittedUnknown(ctx, work.OutboxID, w.workerID, result.TransactionID, w.retryDelay(work.Attempts), boundedError(submitErr))
	}
	if result.TransactionID != "" && !result.Unknown && !result.Committed {
		return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "fabric_commit_invalid", boundedError(submitErr))
	}

	query, queryErr := w.ledger.Query(ctx, work.EventKey)
	if queryErr == nil && query.Found {
		if query.Digest != seal.DigestSHA256 {
			return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "fabric_digest_conflict", "existing Fabric attestation has a different digest")
		}
		if query.TxID != "" {
			return w.repository.MarkConfirmed(ctx, work.OutboxID, w.workerID, query.TxID)
		}
		return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "fabric_existing_attestation_txid_unavailable", "matching Fabric attestation exists but query returned no transaction ID")
	}
	if IsPermanentFabricError(submitErr) {
		return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "fabric_permanent_failure", boundedError(submitErr))
	}
	if queryErr != nil && IsPermanentFabricError(queryErr) {
		return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "fabric_query_permanent_failure", boundedError(queryErr))
	}
	return w.retryFailure(ctx, work, "fabric_transient_failure", submitErr)
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
			return w.repository.MarkSubmittedUnknown(ctx, work.OutboxID, w.workerID, *work.FabricTxID, w.retryDelay(maxInt(work.Attempts, 1)), boundedError(signerErr.Err))
		}
		if errors.As(err, &signerErr) {
			return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "openbao_verify_permanent_failure", boundedError(signerErr.Err))
		}
		return err
	}
	query, err := w.ledger.Query(ctx, work.EventKey)
	if err != nil {
		if IsPermanentFabricError(err) {
			return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "fabric_reconcile_permanent_failure", boundedError(err))
		}
		return w.repository.MarkSubmittedUnknown(ctx, work.OutboxID, w.workerID, *work.FabricTxID, w.retryDelay(maxInt(work.Attempts, 1)), boundedError(err))
	}
	if !query.Found {
		return w.repository.MarkSubmittedUnknown(ctx, work.OutboxID, w.workerID, *work.FabricTxID, w.retryDelay(maxInt(work.Attempts, 1)), "Fabric attestation not found during reconciliation")
	}
	if query.Digest != seal.DigestSHA256 {
		return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "fabric_digest_conflict", "Fabric reconciliation returned a conflicting digest")
	}
	txID := strings.TrimSpace(*work.FabricTxID)
	if query.TxID != "" && query.TxID != txID {
		return w.repository.MarkDeadLetter(ctx, work.OutboxID, w.workerID, "fabric_txid_conflict", "Fabric reconciliation returned a different transaction ID")
	}
	return w.repository.MarkConfirmed(ctx, work.OutboxID, w.workerID, txID)
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
