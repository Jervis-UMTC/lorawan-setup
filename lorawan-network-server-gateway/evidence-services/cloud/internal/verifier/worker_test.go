package verifier

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"testing"
	"time"

	"lorawan/evidence-services/cloud/internal/mqttcapture"
	"lorawan/evidence-services/cloud/internal/objectstore"
)

type fakeRepository struct {
	application      ApplicationEvidence
	work             *Work
	mqtt             MQTTEvidence
	mqttErr          error
	segments         []JournalSegmentMetadata
	checkpoint       CheckpointEvidence
	checkpointErr    error
	releaseReason    string
	failureReason    string
	verified         bool
	verifiedEvidence LineageEvidence
}

func (r *fakeRepository) Ping(context.Context) error                   { return nil }
func (r *fakeRepository) Discover(context.Context, int) (int64, error) { return 0, nil }
func (r *fakeRepository) Claim(context.Context, string, time.Duration) (*Work, error) {
	return r.work, nil
}
func (r *fakeRepository) LoadApplication(context.Context, Work) (ApplicationEvidence, error) {
	return r.application, nil
}
func (r *fakeRepository) LoadMQTT(context.Context, ApplicationEvidence) (MQTTEvidence, error) {
	if r.mqttErr != nil {
		return MQTTEvidence{}, r.mqttErr
	}
	if r.mqtt.GatewayEventID == 0 {
		return MQTTEvidence{}, ErrMQTTMissing
	}
	return r.mqtt, nil
}
func (r *fakeRepository) ListJournalSegments(context.Context, string) ([]JournalSegmentMetadata, error) {
	return r.segments, nil
}
func (r *fakeRepository) LoadCheckpoint(context.Context, JournalSegmentMetadata) (CheckpointEvidence, error) {
	if r.checkpointErr != nil {
		return CheckpointEvidence{}, r.checkpointErr
	}
	return r.checkpoint, nil
}
func (r *fakeRepository) ReleasePending(_ context.Context, _ int64, _ string, reason string, _ time.Duration) error {
	r.releaseReason = reason
	return nil
}
func (r *fakeRepository) CompleteVerified(_ context.Context, _ int64, _ string, evidence LineageEvidence) error {
	r.verified = true
	r.verifiedEvidence = evidence
	return nil
}
func (r *fakeRepository) CompleteIntegrityFailure(_ context.Context, _ int64, _ string, reason string, _ DecoderEvidence) error {
	r.failureReason = reason
	return nil
}

func testWorker(t *testing.T, repo Repository) *Worker {
	t.Helper()
	store, err := objectstore.NewFilesystem(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	worker, err := NewWorker(repo, store, "verifier-test", 30*time.Second, time.Minute, 10)
	if err != nil {
		t.Fatal(err)
	}
	return worker
}

func TestWorkerKeepsConsistentApplicationPendingUntilMQTTExists(t *testing.T) {
	repo := &fakeRepository{
		application: validApplicationFixture(t),
		work:        &Work{VerificationID: 1, SourceEventKey: "fixture-event", WorkerID: "verifier-test"},
		mqttErr:     ErrMQTTMissing,
	}
	processed, err := testWorker(t, repo).RunOnce(context.Background())
	if err != nil || !processed {
		t.Fatalf("RunOnce processed=%v err=%v", processed, err)
	}
	if repo.releaseReason != ReasonMQTTSourceMissing || repo.failureReason != "" {
		t.Fatalf("release=%q failure=%q", repo.releaseReason, repo.failureReason)
	}
}

func TestWorkerKeepsMissingGatewayProvenancePending(t *testing.T) {
	app := validApplicationFixture(t)
	app.GatewayUplinkID = nil
	repo := &fakeRepository{application: app, work: &Work{VerificationID: 2, WorkerID: "verifier-test"}}
	processed, err := testWorker(t, repo).RunOnce(context.Background())
	if err != nil || !processed {
		t.Fatalf("RunOnce processed=%v err=%v", processed, err)
	}
	if repo.releaseReason != ReasonApplicationGatewayMissing || repo.failureReason != "" {
		t.Fatalf("release=%q failure=%q", repo.releaseReason, repo.failureReason)
	}
}

func TestWorkerWritesIntegrityFailureForDeterministicMismatch(t *testing.T) {
	app := validApplicationFixture(t)
	bad := "not-base64"
	app.RawDataBase64 = &bad
	repo := &fakeRepository{application: app, work: &Work{VerificationID: 3, WorkerID: "verifier-test"}}
	processed, err := testWorker(t, repo).RunOnce(context.Background())
	if err != nil || !processed {
		t.Fatalf("RunOnce processed=%v err=%v", processed, err)
	}
	if repo.failureReason != ReasonApplicationPayloadInvalid {
		t.Fatalf("failure reason=%q", repo.failureReason)
	}
}

func TestWorkerCompletesVerifiedAfterFullLineage(t *testing.T) {
	ctx := context.Background()
	store, err := objectstore.NewFilesystem(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}

	mqttPayload, err := hex.DecodeString(syntheticMQTTUplinkHex)
	if err != nil {
		t.Fatal(err)
	}
	topic := "as923/gateway/0016c001f139a1cb/event/up"
	captureKey, err := mqttcapture.CaptureKey(topic, mqttPayload)
	if err != nil {
		t.Fatal(err)
	}
	mqttRef := "mqtt/" + captureKey + ".event"
	if _, err := store.PutIfAbsent(ctx, mqttRef, bytes.NewReader(mqttPayload)); err != nil {
		t.Fatal(err)
	}
	serialized := sha256.Sum256(mqttPayload)

	segmentRef := "segments/0016c001f139a1cb/1.segment"
	if _, err := store.PutIfAbsent(ctx, segmentRef, bytes.NewReader(correlationJournalFixture)); err != nil {
		t.Fatal(err)
	}

	repo := &fakeRepository{
		application: validApplicationFixture(t),
		work:        &Work{VerificationID: 4, SourceEventKey: "fixture-event", WorkerID: "verifier-test"},
		mqtt: MQTTEvidence{
			GatewayEventID:          91,
			GatewayID:               "0016c001f139a1cb",
			MQTTTopic:               topic,
			CaptureKeySHA256:        captureKey,
			SerializedEventSHA256:   hex.EncodeToString(serialized[:]),
			PHYPayloadSHA256:        "9f64a747e1b97f131fabb6b447296c9b6f0201e79fb3c5356e6c77e89b6a806a",
			UplinkID:                "16909060",
			FrequencyHz:             923200000,
			RSSIDbm:                 -72,
			SNRDb:                   8.5,
			GatewayContextBase64:    "3q2+7w==",
			CorrelationDigestSHA256: correlationDigest,
			ObjectRef:               mqttRef,
		},
		segments: []JournalSegmentMetadata{{
			GatewayID:           "0016c001f139a1cb",
			SegmentID:           1,
			FirstSequence:       1,
			LastSequence:        1,
			RecordCount:         1,
			PreviousSegmentHash: journalGenesis,
			FinalRecordHash:     correlationRecordHash,
			SegmentHash:         correlationSegmentHash,
			ObjectRef:           segmentRef,
			ObjectSHA256:        correlationObjectSHA,
		}},
		checkpoint: CheckpointEvidence{CheckpointID: 812},
	}

	worker, err := NewWorker(repo, store, "verifier-test", 30*time.Second, time.Minute, 10)
	if err != nil {
		t.Fatal(err)
	}
	processed, err := worker.RunOnce(ctx)
	if err != nil || !processed {
		t.Fatalf("RunOnce processed=%v err=%v", processed, err)
	}
	if !repo.verified || repo.releaseReason != "" || repo.failureReason != "" {
		t.Fatalf("verified=%v release=%q failure=%q", repo.verified, repo.releaseReason, repo.failureReason)
	}
	got := repo.verifiedEvidence
	if got.GatewayID != "0016c001f139a1cb" || got.JournalSegmentID != 1 || got.JournalSequence != 1 ||
		got.JournalRecordHash != correlationRecordHash || got.JournalSegmentHash != correlationSegmentHash ||
		got.CheckpointID != 812 || got.GatewayEventID != 91 || got.Decoder.DecoderID == "" ||
		got.Decoder.DecoderVersion == "" || got.Decoder.RawAppDataSHA256 == "" || got.Decoder.NormalizedDigestSHA256 == "" {
		t.Fatalf("incomplete verified lineage: %+v", got)
	}
}
