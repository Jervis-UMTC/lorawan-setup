package fabricadapter

import (
	"bytes"
	"testing"
	"time"
)

func TestBuildEvidencePreservesNullsAndMillisecondTimestamps(t *testing.T) {
	work := OutboxWork{
		OutboxID: 20, EventKey: "uplink:nulls", SourceEventKey: "nulls",
		ObservedAt: time.Date(2026, 8, 31, 2, 3, 4, 123987000, time.UTC),
		EventType:  EventTypeUplink, SchemaVersion: SchemaVersionV1,
	}
	source := SourceRow{
		ReceivedAt:  time.Date(2026, 8, 31, 2, 3, 5, 987654000, time.UTC),
		DevEUI:      "0000000000000001",
		PayloadJSON: []byte(`{}`),
	}
	evidence, err := BuildEvidence(work, source, nil)
	if err != nil {
		t.Fatal(err)
	}
	canonical, err := CanonicalizeEvidence(evidence)
	if err != nil {
		t.Fatal(err)
	}
	for _, expected := range [][]byte{
		[]byte(`"application_id":null`), []byte(`"device_id":null`), []byte(`"device_model":null`),
		[]byte(`"gateway_id":null`), []byte(`"region":null`), []byte(`"f_port":null`),
		[]byte(`"f_cnt":null`), []byte(`"confirmed":null`), []byte(`"decoder_version":null`),
		[]byte(`"raw_data_base64":null`),
		[]byte(`"observed_at":"2026-08-31T02:03:04.123Z"`),
		[]byte(`"received_at":"2026-08-31T02:03:05.987Z"`),
	} {
		if !bytes.Contains(canonical.CanonicalJSON, expected) {
			t.Fatalf("canonical evidence missing %s: %s", expected, canonical.CanonicalJSON)
		}
	}
}
