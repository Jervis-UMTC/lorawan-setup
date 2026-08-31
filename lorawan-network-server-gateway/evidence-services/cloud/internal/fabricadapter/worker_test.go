package fabricadapter

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"testing"
	"time"
)

type fakeRepository struct {
	reconciliation  *OutboxWork
	work            *OutboxWork
	source          SourceRow
	sourceErr       error
	verification    VerificationRow
	verificationErr error
	seal            Seal
	sealErr         error
	loadSourceCalls int
	persistCalls    int
	confirmedTxID   string
	unknownTxID     string
	failedCategory  string
	deadCategory    string
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
	submitCalls int
	queryCalls  int
	submit      FabricSubmitResult
	submitErr   error
	query       FabricQueryResult
	queryErr    error
}

func (l *fakeLedger) Submit(context.Context, FabricAttestation) (FabricSubmitResult, error) {
	l.submitCalls++
	return l.submit, l.submitErr
}
func (l *fakeLedger) Query(context.Context, string) (FabricQueryResult, error) {
	l.queryCalls++
	return l.query, l.queryErr
}
func (l *fakeLedger) Close() error { return nil }

func TestWorkerFreshV2SealsVerifiesSubmitsAndConfirms(t *testing.T) {
	repo := &fakeRepository{
		work:         fixtureWorkV2(),
		source:       fixtureSource(),
		verification: fixtureVerification(),
	}
	signer := &fakeSigner{}
	ledger := &fakeLedger{submit: FabricSubmitResult{TransactionID: "tx-v2-1", Committed: true}}
	worker := fixtureWorker(t, repo, signer, ledger)

	processed, err := worker.RunOnce(context.Background())
	if err != nil || !processed {
		t.Fatalf("RunOnce processed=%v err=%v", processed, err)
	}
	if signer.signCalls != 1 || signer.verifyCalls != 1 || repo.persistCalls != 1 || ledger.submitCalls != 1 {
		t.Fatalf("sign=%d verify=%d persist=%d submit=%d", signer.signCalls, signer.verifyCalls, repo.persistCalls, ledger.submitCalls)
	}
	if repo.confirmedTxID != "tx-v2-1" || repo.deadCategory != "" || repo.failedCategory != "" {
		t.Fatalf("confirmed=%q dead=%q failed=%q", repo.confirmedTxID, repo.deadCategory, repo.failedCategory)
	}
}

func TestWorkerAlreadySealedNeverRebuildsOrResigns(t *testing.T) {
	seal := fixtureSeal(`{"frozen":true}`)
	canonical := seal.CanonicalJSON
	repo := &fakeRepository{
		work: &OutboxWork{
			OutboxID: 9, EventKey: "uplink:frozen", SourceEventKey: "frozen", EventType: EventTypeUplink,
			SchemaVersion: SchemaVersionV1, Attempts: 1, CanonicalJSON: &canonical,
		},
		seal: seal,
	}
	signer := &fakeSigner{}
	ledger := &fakeLedger{submit: FabricSubmitResult{TransactionID: "tx-frozen", Committed: true}}
	worker := fixtureWorker(t, repo, signer, ledger)

	processed, err := worker.RunOnce(context.Background())
	if err != nil || !processed {
		t.Fatalf("RunOnce processed=%v err=%v", processed, err)
	}
	if signer.signCalls != 0 || repo.persistCalls != 0 || repo.loadSourceCalls != 0 {
		t.Fatalf("sealed row rebuilt: sign=%d persist=%d loadSource=%d", signer.signCalls, repo.persistCalls, repo.loadSourceCalls)
	}
	if signer.verifyCalls != 1 || ledger.submitCalls != 1 || repo.confirmedTxID != "tx-frozen" {
		t.Fatalf("verify=%d submit=%d confirmed=%q", signer.verifyCalls, ledger.submitCalls, repo.confirmedTxID)
	}
}

func TestWorkerSubmittedUnknownReconcilesWithoutResubmit(t *testing.T) {
	seal := fixtureSeal(`{"frozen":true}`)
	txID := "tx-unknown"
	repo := &fakeRepository{
		reconciliation: &OutboxWork{OutboxID: 10, EventKey: "uplink:unknown", Attempts: 2, FabricTxID: &txID},
		seal:           seal,
	}
	signer := &fakeSigner{}
	ledger := &fakeLedger{query: FabricQueryResult{Found: true, EventKey: "uplink:unknown", Digest: seal.DigestSHA256, TxID: txID, Committed: true}}
	worker := fixtureWorker(t, repo, signer, ledger)

	processed, err := worker.RunOnce(context.Background())
	if err != nil || !processed {
		t.Fatalf("RunOnce processed=%v err=%v", processed, err)
	}
	if ledger.submitCalls != 0 || ledger.queryCalls != 1 || repo.confirmedTxID != txID {
		t.Fatalf("submit=%d query=%d confirmed=%q", ledger.submitCalls, ledger.queryCalls, repo.confirmedTxID)
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
	if repo.deadCategory != "invalid_local_seal" || ledger.submitCalls != 0 || ledger.queryCalls != 0 || signer.verifyCalls != 0 {
		t.Fatalf("dead=%q submit=%d query=%d verify=%d", repo.deadCategory, ledger.submitCalls, ledger.queryCalls, signer.verifyCalls)
	}
}

func TestWorkerReconcileDigestConflictDeadLetters(t *testing.T) {
	seal := fixtureSeal(`{"frozen":true}`)
	txID := "tx-conflict"
	repo := &fakeRepository{
		reconciliation: &OutboxWork{OutboxID: 12, EventKey: "uplink:conflict", Attempts: 2, FabricTxID: &txID},
		seal:           seal,
	}
	signer := &fakeSigner{}
	ledger := &fakeLedger{query: FabricQueryResult{Found: true, EventKey: "uplink:conflict", Digest: "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff", TxID: txID, Committed: true}}
	worker := fixtureWorker(t, repo, signer, ledger)

	processed, err := worker.RunOnce(context.Background())
	if err != nil || !processed {
		t.Fatalf("RunOnce processed=%v err=%v", processed, err)
	}
	if repo.deadCategory != "fabric_digest_conflict" || ledger.submitCalls != 0 {
		t.Fatalf("dead=%q submit=%d", repo.deadCategory, ledger.submitCalls)
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

func fixtureWorker(t *testing.T, repo Repository, signer EvidenceSigner, ledger LedgerClient) *Worker {
	t.Helper()
	worker, err := NewWorker(repo, signer, ledger, Config{
		WorkerID: "fabric-test", ProcessingLease: 90 * time.Second,
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
		EventType:  EventTypeUplink, SchemaVersion: SchemaVersionV2, Attempts: 1,
	}
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
		RawAppDataSHA256:       "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
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
