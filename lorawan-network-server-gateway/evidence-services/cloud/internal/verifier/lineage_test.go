package verifier

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"testing"

	"lorawan/evidence-services/cloud/internal/mqttcapture"
	"lorawan/evidence-services/cloud/internal/objectstore"
)

const syntheticMQTTUplinkHex = "0a040102030422060880d49bb8032a2d0a1030303136633030316631333961316362108486880830b8ffffffffffffffff013d000008416a04deadbeef"

func TestMQTTAndJournalCorrelationFixedVector(t *testing.T) {
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

	app := validApplicationFixture(t)
	mqttEvidence := MQTTEvidence{
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
	}
	verifiedMQTT, err := VerifyMQTTObject(ctx, store, app, mqttEvidence)
	if err != nil {
		t.Fatal(err)
	}

	segmentRef := "segments/0016c001f139a1cb/1.segment"
	if _, err := store.PutIfAbsent(ctx, segmentRef, bytes.NewReader(correlationJournalFixture)); err != nil {
		t.Fatal(err)
	}
	segments := []JournalSegmentMetadata{{
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
	}}
	match, err := FindJournalRecord(ctx, store, segments, verifiedMQTT)
	if err != nil {
		t.Fatal(err)
	}
	if match.Record.RecordHash != correlationRecordHash || match.Record.Body.Sequence != 1 || match.Segment.SegmentHash != correlationSegmentHash {
		t.Fatalf("unexpected journal match: %+v", match)
	}
}

func TestVerifyMQTTObjectRejectsStoredProjectionMismatch(t *testing.T) {
	ctx := context.Background()
	store, _ := objectstore.NewFilesystem(t.TempDir())
	payload, _ := hex.DecodeString(syntheticMQTTUplinkHex)
	topic := "as923/gateway/0016c001f139a1cb/event/up"
	key, _ := mqttcapture.CaptureKey(topic, payload)
	ref := "mqtt/" + key + ".event"
	_, _ = store.PutIfAbsent(ctx, ref, bytes.NewReader(payload))
	digest := sha256.Sum256(payload)
	app := validApplicationFixture(t)
	evidence := MQTTEvidence{
		GatewayEventID: 1, GatewayID: "0016c001f139a1cb", MQTTTopic: topic,
		CaptureKeySHA256: key, SerializedEventSHA256: hex.EncodeToString(digest[:]),
		PHYPayloadSHA256: "9f64a747e1b97f131fabb6b447296c9b6f0201e79fb3c5356e6c77e89b6a806a",
		UplinkID:         "16909060", FrequencyHz: 923200000, RSSIDbm: -72, SNRDb: 8.5,
		GatewayContextBase64: "AAAA", CorrelationDigestSHA256: correlationDigest, ObjectRef: ref,
	}
	if _, err := VerifyMQTTObject(ctx, store, app, evidence); !errors.Is(err, ErrMQTTIntegrity) {
		t.Fatalf("projection mismatch error=%v", err)
	}
}
