package fabricadapter

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"os"
	"os/exec"
	"testing"
	"time"
)

type fakeRepository struct {
	reconciliation       *OutboxWork
	work                 *OutboxWork
	source               SourceRow
	sourceErr            error
	verification         VerificationRow
	verificationErr      error
	seal                 Seal
	sealErr              error
	loadSourceCalls      int
	persistCalls         int
	persistPreparedCalls int
	renewLeaseCalls      int
	preparedTxID         string
	preparedRecordID     string
	preparedTx           []byte
	commitRequest        []byte
	confirmedTxID        string
	unknownTxID          string
	failedCategory       string
	deadCategory         string
	persistPreparedHook  func(string, string, []byte, []byte)
}

func (r *fakeRepository) Ping(context.Context) error { return nil }
func (r *fakeRepository) ClaimReconciliation(context.Context, string, time.Duration) (*OutboxWork, error) {
	work := r.reconciliation
	r.reconciliation = nil
	return work, nil
}
func (r *fakeRepository) ClaimWork(context.Context, string, time.Duration) (*OutboxWork, error) {
	work := r.work
	r.work = nil
	return work, nil
}
func (r *fakeRepository) LoadOutboxReadOnly(context.Context, int64) (*OutboxWork, error) {
	if r.work == nil {
		return nil, ErrOutboxMissing
	}
	copy := *r.work
	return &copy, nil
}
func (r *fakeRepository) LoadSource(context.Context, OutboxWork) (SourceRow, error) {
	r.loadSourceCalls++
	if r.sourceErr != nil {
		return SourceRow{}, r.sourceErr
	}
	return r.source, nil
}
func (r *fakeRepository) LoadVerification(context.Context, OutboxWork) (VerificationRow, error) {
	if r.verificationErr != nil {
		return VerificationRow{}, r.verificationErr
	}
	return r.verification, nil
}
func (r *fakeRepository) PersistSeal(_ context.Context, _ int64, _ string, input CanonicalSealInput, signature, keyID string) (Seal, error) {
	r.persistCalls++
	r.seal = Seal{
		CanonicalJSON: string(input.CanonicalJSON),
		DigestSHA256:  input.DigestSHA256,
		Algorithm:     EvidenceSignatureAlgorithm,
		SigningKeyID:  keyID,
		Signature:     signature,
		SealedAt:      time.Date(2026, 8, 31, 0, 0, 0, 0, time.UTC),
	}
	return r.seal, nil
}
func (r *fakeRepository) LoadSeal(context.Context, int64) (Seal, error) {
	if r.sealErr != nil {
		return Seal{}, r.sealErr
	}
	return r.seal, nil
}
func (r *fakeRepository) PersistPreparedSubmission(_ context.Context, _ int64, _ string, txID, recordID string, preparedTx, commitRequest []byte) error {
	r.persistPreparedCalls++
	r.preparedTxID = txID
	r.preparedRecordID = recordID
	r.preparedTx = append([]byte(nil), preparedTx...)
	r.commitRequest = append([]byte(nil), commitRequest...)
	if r.persistPreparedHook != nil {
		r.persistPreparedHook(txID, recordID, preparedTx, commitRequest)
	}
	return nil
}
func (r *fakeRepository) RenewLease(context.Context, int64, string, time.Duration) error {
	r.renewLeaseCalls++
	return nil
}
func (r *fakeRepository) MarkConfirmed(_ context.Context, _ int64, _ string, txID string) error {
	r.confirmedTxID = txID
	return nil
}
func (r *fakeRepository) MarkSubmittedUnknown(_ context.Context, _ int64, _ string, txID string, _ time.Duration, _ string) error {
	r.unknownTxID = txID
	return nil
}
func (r *fakeRepository) MarkFailed(_ context.Context, _ int64, _ string, _ time.Duration, category, _ string) error {
	r.failedCategory = category
	return nil
}
func (r *fakeRepository) MarkDeadLetter(_ context.Context, _ int64, _ string, category, _ string) error {
	r.deadCategory = category
	return nil
}

type fakeSigner struct {
	signCalls   int
	verifyCalls int
	signErr     error
	verifyErr   error
}

func (s *fakeSigner) Sign(context.Context, []byte) (string, string, error) {
	s.signCalls++
	if s.signErr != nil {
		return "", "", s.signErr
	}
	return "vault:v1:dGVzdA==", "openbao:transit:lorawan-evidence:v1", nil
}
func (s *fakeSigner) Verify(context.Context, []byte, string, string) error {
	s.verifyCalls++
	return s.verifyErr
}

type fakeLedger struct {
	prepareCalls      int
	submitCalls       int
	commitStatusCalls int
	queryCalls        int
	verifyCalls       int
	prepare           FabricPreparedSubmission
	prepareErr        error
	submit            FabricSubmitResult
	submitErr         error
	commitStatus      FabricSubmitResult
	commitStatusErr   error
	query             FabricQueryResult
	queryErr          error
	verify            FabricVerifyResult
	verifyErr         error
	lastAnchor        FabricAnchor
	lastPrepared      FabricPreparedSubmission
	autoQuery         bool
	submitHook        func(FabricPreparedSubmission)
}

func (l *fakeLedger) Prepare(_ context.Context, anchor FabricAnchor) (FabricPreparedSubmission, error) {
	l.prepareCalls++
	l.lastAnchor = anchor
	if l.prepareErr != nil {
		return FabricPreparedSubmission{}, l.prepareErr
	}
	if l.prepare.TransactionID == "" {
		l.prepare = FabricPreparedSubmission{
			TransactionID:       "tx-default",
			PreparedTransaction: []byte("prepared-transaction"),
			CommitStatusRequest: []byte("signed-commit-status-request"),
			CreateOutcome:       "CREATE",
			RecordID:            "hrc-record-default",
		}
	}
	return l.prepare, nil
}
func (l *fakeLedger) SubmitPrepared(_ context.Context, prepared FabricPreparedSubmission) (FabricSubmitResult, error) {
	l.submitCalls++
	l.lastPrepared = prepared
	if l.submitHook != nil {
		l.submitHook(prepared)
	}
	return l.submit, l.submitErr
}
func (l *fakeLedger) CommitStatus(_ context.Context, txID string, _ []byte) (FabricSubmitResult, error) {
	l.commitStatusCalls++
	if l.commitStatus.TransactionID == "" {
		l.commitStatus.TransactionID = txID
	}
	return l.commitStatus, l.commitStatusErr
}
func (l *fakeLedger) Query(_ context.Context, sourceSystemID, sourceRecordID string) (FabricQueryResult, error) {
	l.queryCalls++
	if l.autoQuery {
		a := l.lastAnchor
		recordID := l.lastPrepared.RecordID
		if recordID == "" {
			recordID = l.prepare.RecordID
		}
		return FabricQueryResult{
			Found:                       true,
			RecordID:                    recordID,
			AuthenticatedSourceSystemID: a.AuthenticatedSourceSystemID,
			SourceRecordID:              a.SourceRecordID,
			DigestAlgorithm:             "sha256",
			Digest:                      a.Digest,
			PayloadLength:               a.PayloadLength,
			SourceType:                  a.SourceType,
			Producer:                    a.Producer,
			ProducedAt:                  a.ProducedAt,
			SchemaVersion:               a.SchemaVersion,
		}, l.queryErr
	}
	return l.query, l.queryErr
}
func (l *fakeLedger) VerifyDigest(_ context.Context, _, _ string, digest string) (FabricVerifyResult, error) {
	l.verifyCalls++
	if l.verify.Outcome == "" && l.verifyErr == nil {
		recordID := l.lastPrepared.RecordID
		if recordID == "" {
			recordID = l.prepare.RecordID
		}
		return FabricVerifyResult{Outcome: "MATCH", RecordID: recordID, ExpectedDigest: digest, ObservedDigest: digest}, nil
	}
	return l.verify, l.verifyErr
}
func (l *fakeLedger) Close() error { return nil }

func TestWorkerFreshV2SealsVerifiesSubmitsAndConfirms(t *testing.T) {
	repo := &fakeRepository{
		work:         fixtureWorkV2(),
		source:       fixtureSource(),
		verification: fixtureVerification(),
	}
	signer := &fakeSigner{}
	ledger := &fakeLedger{
		prepare: FabricPreparedSubmission{TransactionID: "tx-v2-1", PreparedTransaction: []byte("prepared"), CommitStatusRequest: []byte("status"), CreateOutcome: "CREATE", RecordID: "hrc-v2-1"},
		submit:  FabricSubmitResult{TransactionID: "tx-v2-1", Committed: true}, autoQuery: true,
	}
	worker := fixtureWorker(t, repo, signer, ledger)

	processed, err := worker.RunOnce(context.Background())
	if err != nil || !processed {
		t.Fatalf("RunOnce processed=%v err=%v", processed, err)
	}
	if signer.signCalls != 1 || signer.verifyCalls != 1 || repo.persistCalls != 1 || repo.persistPreparedCalls != 1 || ledger.prepareCalls != 1 || ledger.submitCalls != 1 || ledger.queryCalls != 1 || ledger.verifyCalls != 1 {
		t.Fatalf("sign=%d verify=%d persistSeal=%d persistPrepared=%d prepare=%d submit=%d query=%d verifyDigest=%d", signer.signCalls, signer.verifyCalls, repo.persistCalls, repo.persistPreparedCalls, ledger.prepareCalls, ledger.submitCalls, ledger.queryCalls, ledger.verifyCalls)
	}
	if ledger.lastAnchor.AuthenticatedSourceSystemID != "lorawan-test" || ledger.lastAnchor.SourceRecordID != "test-v2" || ledger.lastAnchor.Digest != fixtureExactDigest() || ledger.lastAnchor.PayloadLength != len(fixtureExactPayload()) || ledger.lastAnchor.SourceType != EventTypeUplink || ledger.lastAnchor.Producer != "0000000000000001" || ledger.lastAnchor.SchemaVersion != SchemaVersionV2 {
		t.Fatalf("unexpected HRC anchor: %+v", ledger.lastAnchor)
	}
	if !bytes.Equal(ledger.lastAnchor.ExactPayload, fixtureExactPayload()) {
		t.Fatalf("unexpected transient exact payload: %x", ledger.lastAnchor.ExactPayload)
	}
	if repo.preparedTxID != "tx-v2-1" || repo.preparedRecordID != "hrc-v2-1" || repo.confirmedTxID != "tx-v2-1" || repo.deadCategory != "" || repo.failedCategory != "" {
		t.Fatalf("preparedTx=%q preparedRecord=%q confirmed=%q dead=%q failed=%q", repo.preparedTxID, repo.preparedRecordID, repo.confirmedTxID, repo.deadCategory, repo.failedCategory)
	}
}

func TestWorkerPersistsDurableTransactionBeforeSubmitAndKeepsUnknown(t *testing.T) {
	repo := &fakeRepository{work: fixtureWorkV2(), source: fixtureSource(), verification: fixtureVerification()}
	ledger := &fakeLedger{
		prepare:   FabricPreparedSubmission{TransactionID: "tx-crash-window", PreparedTransaction: []byte("prepared"), CommitStatusRequest: []byte("status"), CreateOutcome: "CREATE", RecordID: "hrc-crash-window"},
		submit:    FabricSubmitResult{TransactionID: "tx-crash-window", Unknown: true},
		submitErr: errors.New("connection lost after orderer submit"),
	}
	persistedBeforeSubmit := false
	ledger.submitHook = func(prepared FabricPreparedSubmission) {
		persistedBeforeSubmit = repo.preparedTxID == prepared.TransactionID && repo.preparedRecordID == prepared.RecordID && bytes.Equal(repo.preparedTx, prepared.PreparedTransaction) && bytes.Equal(repo.commitRequest, prepared.CommitStatusRequest)
	}
	worker := fixtureWorker(t, repo, &fakeSigner{}, ledger)

	processed, err := worker.RunOnce(context.Background())
	if err != nil || !processed {
		t.Fatalf("RunOnce processed=%v err=%v", processed, err)
	}
	if !persistedBeforeSubmit {
		t.Fatal("Fabric transaction material was not durable before SubmitPrepared")
	}
	if repo.unknownTxID != "tx-crash-window" || repo.confirmedTxID != "" || ledger.prepareCalls != 1 || ledger.submitCalls != 1 {
		t.Fatalf("unknown=%q confirmed=%q prepare=%d submit=%d", repo.unknownTxID, repo.confirmedTxID, ledger.prepareCalls, ledger.submitCalls)
	}
}

type txCrashState struct {
	TransactionID       string `json:"transaction_id"`
	RecordID            string `json:"record_id"`
	PreparedTransaction []byte `json:"prepared_transaction"`
	CommitStatusRequest []byte `json:"commit_status_request"`
}

func TestTXIDDurabilityFaultInjectionProcessKillAndRestart(t *testing.T) {
	statePath := os.Getenv("TASK37_TX_CRASH_STATE")
	if os.Getenv("TASK37_TX_CRASH_CHILD") == "1" {
		repo := &fakeRepository{work: fixtureWorkV2(), source: fixtureSource(), verification: fixtureVerification()}
		repo.persistPreparedHook = func(txID, recordID string, preparedTx, commitRequest []byte) {
			state := txCrashState{TransactionID: txID, RecordID: recordID, PreparedTransaction: append([]byte(nil), preparedTx...), CommitStatusRequest: append([]byte(nil), commitRequest...)}
			encoded, err := json.Marshal(state)
			if err != nil {
				panic(err)
			}
			if err := os.WriteFile(statePath, encoded, 0o600); err != nil {
				panic(err)
			}
			os.Exit(97)
		}
		ledger := &fakeLedger{prepare: FabricPreparedSubmission{TransactionID: "tx-fault-injection", PreparedTransaction: []byte("exact-prepared-transaction"), CommitStatusRequest: []byte("exact-commit-status-request"), CreateOutcome: "CREATE", RecordID: "hrc-fault-injection"}}
		worker := fixtureWorker(t, repo, &fakeSigner{}, ledger)
		_, _ = worker.RunOnce(context.Background())
		os.Exit(98)
	}

	statePath = t.TempDir() + string(os.PathSeparator) + "durable-tx.json"
	cmd := exec.Command(os.Args[0], "-test.run=^TestTXIDDurabilityFaultInjectionProcessKillAndRestart$")
	cmd.Env = append(os.Environ(), "TASK37_TX_CRASH_CHILD=1", "TASK37_TX_CRASH_STATE="+statePath)
	err := cmd.Run()
	exitErr, ok := err.(*exec.ExitError)
	if !ok || exitErr.ExitCode() != 97 {
		t.Fatalf("fault-injection child exit=%v, expected hard crash exit 97", err)
	}

	encoded, err := os.ReadFile(statePath)
	if err != nil {
		t.Fatalf("read durable tx state: %v", err)
	}
	var state txCrashState
	if err := json.Unmarshal(encoded, &state); err != nil {
		t.Fatalf("decode durable tx state: %v", err)
	}
	if state.TransactionID == "" || state.RecordID == "" || len(state.PreparedTransaction) == 0 || len(state.CommitStatusRequest) == 0 {
		t.Fatalf("incomplete durable transaction after crash: %+v", state)
	}

	seal := fixtureSeal(`{"frozen":true}`)
	repo := &fakeRepository{
		reconciliation: &OutboxWork{
			OutboxID: 77, EventKey: "uplink:fault-restart", SourceEventKey: "fault-restart",
			ObservedAt: time.Date(2026, 9, 7, 0, 0, 0, 0, time.UTC), EventType: EventTypeUplink,
			SchemaVersion: SchemaVersionV2, Attempts: 1, FinalizedPayload: fixtureExactPayload(),
			FabricTxID: &state.TransactionID, FabricRecordID: &state.RecordID,
			FabricPreparedTx: append([]byte(nil), state.PreparedTransaction...), FabricCommitRequest: append([]byte(nil), state.CommitStatusRequest...),
		},
		seal: seal, source: fixtureSource(), verification: fixtureVerification(),
	}
	ledger := &fakeLedger{
		query:           FabricQueryResult{Found: false},
		commitStatus:    FabricSubmitResult{TransactionID: state.TransactionID, Unknown: true},
		commitStatusErr: errors.New("injected commit-status uncertainty after restart"),
		submit:          FabricSubmitResult{TransactionID: state.TransactionID, Unknown: true},
		submitErr:       errors.New("injected same-tx resubmit uncertainty"),
	}
	worker := fixtureWorker(t, repo, &fakeSigner{}, ledger)
	processed, err := worker.RunOnce(context.Background())
	if err != nil || !processed {
		t.Fatalf("restart RunOnce processed=%v err=%v", processed, err)
	}
	if ledger.prepareCalls != 0 {
		t.Fatalf("restart prepared a blind second Create: prepareCalls=%d", ledger.prepareCalls)
	}
	if ledger.commitStatusCalls != 1 || ledger.submitCalls != 1 {
		t.Fatalf("restart reconciliation status=%d sameTxSubmit=%d", ledger.commitStatusCalls, ledger.submitCalls)
	}
	if ledger.lastPrepared.TransactionID != state.TransactionID || !bytes.Equal(ledger.lastPrepared.PreparedTransaction, state.PreparedTransaction) || !bytes.Equal(ledger.lastPrepared.CommitStatusRequest, state.CommitStatusRequest) {
		t.Fatalf("restart did not reuse exact durable transaction: %+v", ledger.lastPrepared)
	}
	if repo.unknownTxID != state.TransactionID {
		t.Fatalf("restart did not preserve uncertain txid: %q", repo.unknownTxID)
	}
}

func TestWorkerAlreadySealedNeverRebuildsOrResigns(t *testing.T) {
	seal := fixtureSeal(`{"frozen":true}`)
	canonical := seal.CanonicalJSON
	repo := &fakeRepository{
		work: &OutboxWork{
			OutboxID: 9, EventKey: "uplink:frozen", SourceEventKey: "frozen", EventType: EventTypeUplink,
			ObservedAt: time.Date(2026, 8, 31, 1, 2, 3, 0, time.UTC), SchemaVersion: SchemaVersionV1, Attempts: 1, CanonicalJSON: &canonical, FinalizedPayload: fixtureExactPayload(),
		},
		seal: seal, source: fixtureSource(),
	}
	signer := &fakeSigner{}
	ledger := &fakeLedger{
		prepare: FabricPreparedSubmission{TransactionID: "tx-frozen", PreparedTransaction: []byte("prepared"), CommitStatusRequest: []byte("status"), CreateOutcome: "CREATE", RecordID: "hrc-frozen"},
		submit:  FabricSubmitResult{TransactionID: "tx-frozen", Committed: true}, autoQuery: true,
	}
	worker := fixtureWorker(t, repo, signer, ledger)

	processed, err := worker.RunOnce(context.Background())
	if err != nil || !processed {
		t.Fatalf("RunOnce processed=%v err=%v", processed, err)
	}
	if signer.signCalls != 0 || repo.persistCalls != 0 || repo.loadSourceCalls != 1 {
		t.Fatalf("sealed row rebuilt: sign=%d persist=%d loadSource=%d", signer.signCalls, repo.persistCalls, repo.loadSourceCalls)
	}
	if signer.verifyCalls != 1 || ledger.prepareCalls != 1 || ledger.submitCalls != 1 || repo.confirmedTxID != "tx-frozen" {
		t.Fatalf("verify=%d prepare=%d submit=%d confirmed=%q", signer.verifyCalls, ledger.prepareCalls, ledger.submitCalls, repo.confirmedTxID)
	}
}

func TestWorkerSubmittedUnknownReconcilesWithoutResubmit(t *testing.T) {
	seal := fixtureSeal(`{"frozen":true}`)
	txID := "tx-unknown"
	recordID := "hrc-unknown"
	repo := &fakeRepository{
		reconciliation: &OutboxWork{OutboxID: 10, EventKey: "uplink:unknown", SourceEventKey: "unknown", ObservedAt: time.Date(2026, 8, 31, 1, 2, 3, 0, time.UTC), EventType: EventTypeUplink, SchemaVersion: SchemaVersionV1, Attempts: 2, FinalizedPayload: fixtureExactPayload(), FabricTxID: &txID, FabricRecordID: &recordID},
		seal:           seal, source: fixtureSource(),
	}
	signer := &fakeSigner{}
	digest := fixtureExactDigest()
	ledger := &fakeLedger{
		query:  FabricQueryResult{Found: true, RecordID: recordID, AuthenticatedSourceSystemID: "lorawan-test", SourceRecordID: "unknown", DigestAlgorithm: "sha256", Digest: digest, PayloadLength: len(fixtureExactPayload()), SourceType: EventTypeUplink, Producer: "0000000000000001", ProducedAt: "2026-08-31T01:02:03Z", SchemaVersion: SchemaVersionV1},
		verify: FabricVerifyResult{Outcome: "MATCH", RecordID: recordID, ExpectedDigest: digest, ObservedDigest: digest},
	}
	worker := fixtureWorker(t, repo, signer, ledger)

	processed, err := worker.RunOnce(context.Background())
	if err != nil || !processed {
		t.Fatalf("RunOnce processed=%v err=%v", processed, err)
	}
	if ledger.prepareCalls != 0 || ledger.submitCalls != 0 || ledger.queryCalls != 1 || ledger.verifyCalls != 1 || repo.confirmedTxID != txID {
		t.Fatalf("prepare=%d submit=%d query=%d verify=%d confirmed=%q", ledger.prepareCalls, ledger.submitCalls, ledger.queryCalls, ledger.verifyCalls, repo.confirmedTxID)
	}
}

func TestWorkerUnknownReconcileUsesPersistedCommitStatusWithoutResubmit(t *testing.T) {
	seal := fixtureSeal(`{"frozen":true}`)
	txID := "tx-status"
	recordID := "hrc-status"
	repo := &fakeRepository{
		reconciliation: &OutboxWork{OutboxID: 14, EventKey: "uplink:status", SourceEventKey: "status", ObservedAt: time.Date(2026, 8, 31, 1, 2, 3, 0, time.UTC), EventType: EventTypeUplink, SchemaVersion: SchemaVersionV1, Attempts: 2, FinalizedPayload: fixtureExactPayload(), FabricTxID: &txID, FabricRecordID: &recordID, FabricCommitRequest: []byte("signed-status")},
		seal:           seal, source: fixtureSource(),
	}
	digest := fixtureExactDigest()
	ledger := &fakeLedger{
		query:           FabricQueryResult{Found: false},
		commitStatus:    FabricSubmitResult{TransactionID: txID, Committed: true},
		commitStatusErr: nil,
	}
	ledger.queryErr = errors.New("anchor not visible yet")
	worker := fixtureWorker(t, repo, &fakeSigner{}, ledger)
	// After VALID commit status, confirmAnchor must query the committed record.
	calls := 0
	originalErr := ledger.queryErr
	_ = originalErr
	// Use a small wrapper behavior by flipping the fake after first status is observed
	// through the commit-status result: the first query fails; confirm query is provided
	// by setting autoQuery and a prepared anchor snapshot before RunOnce.
	ledger.lastAnchor = FabricAnchor{AuthenticatedSourceSystemID: "lorawan-test", SourceRecordID: "status", Digest: digest, PayloadLength: len(fixtureExactPayload()), SourceType: EventTypeUplink, Producer: "0000000000000001", ProducedAt: "2026-08-31T01:02:03Z", SchemaVersion: SchemaVersionV1}
	ledger.prepare.RecordID = recordID
	// This test focuses on the no-resubmit/status path. A query that stays unavailable
	// after VALID correctly remains unknown, so count status and assert no submit.
	processed, err := worker.RunOnce(context.Background())
	calls = ledger.queryCalls
	if err != nil || !processed {
		t.Fatalf("RunOnce processed=%v err=%v", processed, err)
	}
	if ledger.prepareCalls != 0 || ledger.submitCalls != 0 || ledger.commitStatusCalls != 1 || calls < 1 || repo.unknownTxID != txID {
		t.Fatalf("prepare=%d submit=%d status=%d query=%d unknown=%q", ledger.prepareCalls, ledger.submitCalls, ledger.commitStatusCalls, calls, repo.unknownTxID)
	}
}

func TestWorkerUnknownReconcileResubmitsOnlySamePreparedTransaction(t *testing.T) {
	seal := fixtureSeal(`{"frozen":true}`)
	txID := "tx-prepared-retry"
	recordID := "hrc-prepared-retry"
	preparedBytes := []byte("exact-endorsed-transaction")
	commitRequest := []byte("exact-signed-commit-status-request")
	repo := &fakeRepository{
		reconciliation: &OutboxWork{
			OutboxID: 15, EventKey: "uplink:prepared-retry", SourceEventKey: "prepared-retry",
			ObservedAt: time.Date(2026, 8, 31, 1, 2, 3, 0, time.UTC), EventType: EventTypeUplink,
			SchemaVersion: SchemaVersionV1, Attempts: 2, FinalizedPayload: fixtureExactPayload(), FabricTxID: &txID, FabricRecordID: &recordID,
			FabricPreparedTx: preparedBytes, FabricCommitRequest: commitRequest,
		},
		seal: seal, source: fixtureSource(),
	}
	ledger := &fakeLedger{
		queryErr:        errors.New("anchor not yet visible"),
		commitStatus:    FabricSubmitResult{TransactionID: txID, Unknown: true},
		commitStatusErr: errors.New("commit status timed out"),
		submit:          FabricSubmitResult{TransactionID: txID, Unknown: true},
		submitErr:       errors.New("same transaction resubmit still uncertain"),
	}
	worker := fixtureWorker(t, repo, &fakeSigner{}, ledger)

	processed, err := worker.RunOnce(context.Background())
	if err != nil || !processed {
		t.Fatalf("RunOnce processed=%v err=%v", processed, err)
	}
	if ledger.prepareCalls != 0 || ledger.submitCalls != 1 || ledger.commitStatusCalls != 1 {
		t.Fatalf("prepare=%d submit=%d commitStatus=%d", ledger.prepareCalls, ledger.submitCalls, ledger.commitStatusCalls)
	}
	if ledger.lastPrepared.TransactionID != txID || ledger.lastPrepared.RecordID != recordID || !bytes.Equal(ledger.lastPrepared.PreparedTransaction, preparedBytes) || !bytes.Equal(ledger.lastPrepared.CommitStatusRequest, commitRequest) {
		t.Fatalf("reconciliation did not reuse exact durable transaction: %+v", ledger.lastPrepared)
	}
	if repo.unknownTxID != txID || repo.confirmedTxID != "" {
		t.Fatalf("unknown=%q confirmed=%q", repo.unknownTxID, repo.confirmedTxID)
	}
}

func TestWorkerInvalidLocalDigestBlocksFabric(t *testing.T) {
	seal := fixtureSeal(`{"frozen":true}`)
	seal.DigestSHA256 = "0000000000000000000000000000000000000000000000000000000000000000"
	canonical := seal.CanonicalJSON
	repo := &fakeRepository{
		work: &OutboxWork{OutboxID: 11, EventKey: "uplink:tampered", SchemaVersion: SchemaVersionV1, EventType: EventTypeUplink, Attempts: 1, CanonicalJSON: &canonical},
		seal: seal,
	}
	signer := &fakeSigner{}
	ledger := &fakeLedger{}
	worker := fixtureWorker(t, repo, signer, ledger)

	processed, err := worker.RunOnce(context.Background())
	if err != nil || !processed {
		t.Fatalf("RunOnce processed=%v err=%v", processed, err)
	}
	if repo.deadCategory != "invalid_local_seal" || ledger.prepareCalls != 0 || ledger.submitCalls != 0 || ledger.queryCalls != 0 || signer.verifyCalls != 0 {
		t.Fatalf("dead=%q prepare=%d submit=%d query=%d verify=%d", repo.deadCategory, ledger.prepareCalls, ledger.submitCalls, ledger.queryCalls, signer.verifyCalls)
	}
}

func TestWorkerReconcileDigestConflictDeadLetters(t *testing.T) {
	seal := fixtureSeal(`{"frozen":true}`)
	txID := "tx-conflict"
	recordID := "hrc-conflict"
	repo := &fakeRepository{
		reconciliation: &OutboxWork{OutboxID: 12, EventKey: "uplink:conflict", SourceEventKey: "conflict", ObservedAt: time.Date(2026, 8, 31, 1, 2, 3, 0, time.UTC), EventType: EventTypeUplink, SchemaVersion: SchemaVersionV1, Attempts: 2, FinalizedPayload: fixtureExactPayload(), FabricTxID: &txID, FabricRecordID: &recordID},
		seal:           seal, source: fixtureSource(),
	}
	signer := &fakeSigner{}
	ledger := &fakeLedger{query: FabricQueryResult{Found: true, RecordID: recordID, AuthenticatedSourceSystemID: "lorawan-test", SourceRecordID: "conflict", DigestAlgorithm: "sha256", Digest: "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff", PayloadLength: 2, SourceType: EventTypeUplink, Producer: "0000000000000001", ProducedAt: "2026-08-31T01:02:03Z", SchemaVersion: SchemaVersionV1}}
	worker := fixtureWorker(t, repo, signer, ledger)

	processed, err := worker.RunOnce(context.Background())
	if err != nil || !processed {
		t.Fatalf("RunOnce processed=%v err=%v", processed, err)
	}
	if repo.deadCategory != "fabric_anchor_conflict" || ledger.prepareCalls != 0 || ledger.submitCalls != 0 {
		t.Fatalf("dead=%q prepare=%d submit=%d", repo.deadCategory, ledger.prepareCalls, ledger.submitCalls)
	}
}

func TestWorkerDatabaseReadErrorDoesNotDeadLetter(t *testing.T) {
	repo := &fakeRepository{
		work:      &OutboxWork{OutboxID: 13, EventKey: "uplink:db", SourceEventKey: "db", EventType: EventTypeUplink, SchemaVersion: SchemaVersionV1, Attempts: 1},
		sourceErr: errors.New("temporary database read failure"),
	}
	worker := fixtureWorker(t, repo, &fakeSigner{}, &fakeLedger{})

	processed, err := worker.RunOnce(context.Background())
	if err == nil || !processed {
		t.Fatalf("RunOnce processed=%v err=%v", processed, err)
	}
	if repo.deadCategory != "" || repo.failedCategory != "" {
		t.Fatalf("database error changed queue state dead=%q failed=%q", repo.deadCategory, repo.failedCategory)
	}
}

func TestBuildAnchorEnforcesHRCExactPayloadBounds(t *testing.T) {
	validJSONWithLength := func(length int) []byte {
		if length == 0 {
			return nil
		}
		if length == 1 {
			return []byte("0")
		}
		return append(append([]byte{'"'}, bytes.Repeat([]byte{'a'}, length-2)...), '"')
	}
	tests := []struct {
		name      string
		length    int
		wantError bool
	}{
		{name: "zero-bytes-rejected", length: 0, wantError: true},
		{name: "one-byte-accepted", length: 1},
		{name: "1048576-bytes-accepted", length: maxFabricExactPayloadBytes},
		{name: "1048577-bytes-rejected", length: maxFabricExactPayloadBytes + 1, wantError: true},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			payload := validJSONWithLength(tc.length)
			repo := &fakeRepository{source: fixtureSource()}
			worker := &Worker{repository: repo, sourceSystemID: "lorawan-test"}
			work := OutboxWork{OutboxID: 99, SourceEventKey: "payload-boundary", EventType: EventTypeUplink, ObservedAt: time.Date(2026, 9, 7, 0, 0, 0, 0, time.UTC), SchemaVersion: SchemaVersionV1, FinalizedPayload: payload}
			anchor, err := worker.buildAnchor(context.Background(), work)
			if tc.wantError {
				if err == nil {
					t.Fatalf("buildAnchor accepted payload length %d", tc.length)
				}
				return
			}
			if err != nil {
				t.Fatalf("buildAnchor length %d: %v", tc.length, err)
			}
			if anchor.PayloadLength != tc.length || !bytes.Equal(anchor.ExactPayload, payload) {
				t.Fatalf("length=%d exact payload was not preserved", tc.length)
			}
		})
	}
}

func TestInvalidExactPayloadNeverInvokesFabric(t *testing.T) {
	seal := fixtureSeal(`{"frozen":true}`)
	canonical := seal.CanonicalJSON
	for _, payload := range [][]byte{nil, append(append([]byte{'"'}, bytes.Repeat([]byte{'a'}, maxFabricExactPayloadBytes-1)...), '"')} {
		repo := &fakeRepository{
			work: &OutboxWork{OutboxID: 99, EventKey: "uplink:invalid-size", SourceEventKey: "invalid-size", EventType: EventTypeUplink, ObservedAt: time.Date(2026, 9, 7, 0, 0, 0, 0, time.UTC), SchemaVersion: SchemaVersionV1, Attempts: 1, CanonicalJSON: &canonical, FinalizedPayload: payload},
			seal: seal, source: fixtureSource(),
		}
		ledger := &fakeLedger{}
		worker := fixtureWorker(t, repo, &fakeSigner{}, ledger)
		processed, err := worker.RunOnce(context.Background())
		if err != nil || !processed {
			t.Fatalf("RunOnce processed=%v err=%v", processed, err)
		}
		if ledger.prepareCalls != 0 || ledger.submitCalls != 0 || repo.deadCategory != "fabric_anchor_construction_failure" {
			t.Fatalf("invalid payload reached Fabric: prepare=%d submit=%d dead=%q", ledger.prepareCalls, ledger.submitCalls, repo.deadCategory)
		}
	}
}

func TestHRCResponseValidation(t *testing.T) {
	digest := "a12871fee210fb8619291eaea194581cbd2531e4b23759d225f6806923f63222"
	expected := FabricAnchor{
		AuthenticatedSourceSystemID: "lorawan-test", SourceRecordID: "source-1", Digest: digest, PayloadLength: 2,
		SourceType: EventTypeUplink, Producer: "0000000000000001", ProducedAt: "2026-09-07T00:00:00Z", SchemaVersion: SchemaVersionV2,
	}
	validCreate := []byte(`{"outcome":"CREATE","record_id":"hrc-1","anchor":{"record_id":"hrc-1","authenticated_source_system_id":"lorawan-test","source_record_id":"source-1","digest_algorithm":"sha256","digest":"a12871fee210fb8619291eaea194581cbd2531e4b23759d225f6806923f63222","payload_length":2,"source_type":"lorawan_uplink_accepted","producer":"0000000000000001","produced_at":"2026-09-07T00:00:00Z","schema_version":"telemetry-attestation-v2"}}`)
	create, err := decodeCreateResponse(validCreate, expected)
	if err != nil || create.RecordID != "hrc-1" || create.Outcome != "CREATE" {
		t.Fatalf("valid create rejected: response=%+v err=%v", create, err)
	}
	validRetry := bytes.Replace(validCreate, []byte(`"CREATE"`), []byte(`"IDEMPOTENT_RETRY"`), 1)
	if _, err := decodeCreateResponse(validRetry, expected); err != nil {
		t.Fatalf("valid idempotent retry rejected: %v", err)
	}
	wrongAlgorithm := bytes.Replace(validCreate, []byte(`"sha256"`), []byte(`"sha512"`), 1)
	if _, err := decodeCreateResponse(wrongAlgorithm, expected); err == nil {
		t.Fatal("create response with wrong digest_algorithm was accepted")
	}

	validQuery := []byte(`{"record_id":"hrc-1","authenticated_source_system_id":"lorawan-test","source_record_id":"source-1","digest_algorithm":"sha256","digest":"a12871fee210fb8619291eaea194581cbd2531e4b23759d225f6806923f63222","payload_length":2,"source_type":"lorawan_uplink_accepted","producer":"0000000000000001","produced_at":"2026-09-07T00:00:00Z","schema_version":"telemetry-attestation-v2"}`)
	query, err := decodeQueryResponse(validQuery, "lorawan-test", "source-1")
	if err != nil || query.RecordID != "hrc-1" || query.DigestAlgorithm != "sha256" {
		t.Fatalf("valid query rejected: response=%+v err=%v", query, err)
	}
	if _, err := decodeQueryResponse(bytes.Replace(validQuery, []byte(`"sha256"`), []byte(`"sha512"`), 1), "lorawan-test", "source-1"); err == nil {
		t.Fatal("query response with wrong digest_algorithm was accepted")
	}

	validVerify := []byte(`{"outcome":"MATCH","record_id":"hrc-1","expected_digest":"a12871fee210fb8619291eaea194581cbd2531e4b23759d225f6806923f63222","observed_digest":"a12871fee210fb8619291eaea194581cbd2531e4b23759d225f6806923f63222"}`)
	verify, err := decodeVerifyResponse(validVerify, digest)
	if err != nil || verify.Outcome != "MATCH" || verify.RecordID != "hrc-1" {
		t.Fatalf("valid verify rejected: response=%+v err=%v", verify, err)
	}
	if _, err := decodeVerifyResponse([]byte(`MATCH`), digest); err == nil {
		t.Fatal("legacy/plain MATCH response was accepted")
	}
	if _, err := decodeVerifyResponse(bytes.Replace(validVerify, []byte(digest), []byte("ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"), 1), digest); err == nil {
		t.Fatal("verify response with mismatched digest was accepted")
	}
}

func fixtureWorker(t *testing.T, repo Repository, signer EvidenceSigner, ledger LedgerClient) *Worker {
	t.Helper()
	worker, err := NewWorker(repo, signer, ledger, Config{
		WorkerID: "fabric-test", FabricSourceSystemID: "lorawan-test", ProcessingLease: 90 * time.Second,
		MaxAttempts: 5, RetryBase: time.Second, RetryMax: 30 * time.Second, RetryJitter: 0,
	})
	if err != nil {
		t.Fatal(err)
	}
	return worker
}

func fixtureWorkV2() *OutboxWork {
	return &OutboxWork{
		OutboxID: 1, EventKey: "uplink:test-v2", SourceEventKey: "test-v2",
		ObservedAt: time.Date(2026, 8, 31, 1, 2, 3, 456789000, time.UTC),
		EventType:  EventTypeUplink, SchemaVersion: SchemaVersionV2, Attempts: 1, FinalizedPayload: fixtureExactPayload(),
	}
}

func fixtureExactPayload() []byte {
	return []byte(`{"normalized":"accepted"}`)
}

func fixtureExactDigest() string {
	digest := sha256.Sum256(fixtureExactPayload())
	return hex.EncodeToString(digest[:])
}

func fixtureSource() SourceRow {
	return SourceRow{
		ReceivedAt:     time.Date(2026, 8, 31, 1, 2, 4, 987654000, time.UTC),
		ApplicationID:  testString("app"),
		DeviceID:       testString("device"),
		DeviceModel:    testString("model"),
		DecoderVersion: testString("node-red-v1"),
		DevEUI:         "0000000000000001",
		GatewayID:      testString("0016c001f139a1cb"),
		Region:         testString("as923"),
		FPort:          testInt64(2),
		FCnt:           testInt64(104),
		Confirmed:      testBool(false),
		RawDataBase64:  testString("AQI="),
		PayloadJSON:    []byte(`{"temperature_c":24.5}`),
	}
}

func fixtureVerification() VerificationRow {
	return VerificationRow{
		VerificationID: 7, Status: "verified", GatewayID: "0016c001f139a1cb",
		JournalSegmentID: 3, JournalSequence: 44,
		JournalRecordHash:  "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
		JournalSegmentHash: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
		CheckpointID:       5, GatewayEventID: 6,
		DecoderID: "trusted", DecoderVersion: "v1",
		RawAppDataSHA256:       "a12871fee210fb8619291eaea194581cbd2531e4b23759d225f6806923f63222",
		NormalizedDigestSHA256: "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
	}
}

func fixtureSeal(canonical string) Seal {
	digest := sha256.Sum256([]byte(canonical))
	return Seal{
		CanonicalJSON: canonical,
		DigestSHA256:  hex.EncodeToString(digest[:]),
		Algorithm:     EvidenceSignatureAlgorithm,
		SigningKeyID:  "openbao:transit:lorawan-evidence:v1",
		Signature:     "vault:v1:dGVzdA==",
		SealedAt:      time.Date(2026, 8, 31, 0, 0, 0, 0, time.UTC),
	}
}

func testString(value string) *string { return &value }
func testInt64(value int64) *int64    { return &value }
func testBool(value bool) *bool       { return &value }
