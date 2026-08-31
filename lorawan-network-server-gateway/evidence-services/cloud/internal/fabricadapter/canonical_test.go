package fabricadapter

import (
	"encoding/json"
	"testing"
)

const v1ExpectedCanonical = `{"event_key":"uplink:test","event_type":"lorawan_uplink_accepted","lorawan":{"confirmed":false,"f_cnt":104,"f_port":2},"observation":{"observed_at":"2000-01-01T00:00:00.000Z","received_at":"2000-01-01T00:00:01.000Z"},"payload":{"decoded_payload":{"battery_v":3.6,"temperature_c":24.5},"decoder_version":"test-v1","raw_data_base64":"AQI="},"schema_version":"telemetry-attestation-v1","source":{"application_id":"test","dev_eui":"0000000000000001","device_id":"test-device","device_model":"test-model","gateway_id":"0000000000000002","network_server":"chirpstack","region":"as923_3"},"source_event_key":"test"}`
const v1ExpectedDigest = "c2952e8cddc7f39a17522cb49dd3292c9af75c00fdc37172f74bb3dc955f3a5c"

const v2ExpectedCanonical = `{"event_key":"uplink:test-v2","event_type":"lorawan_uplink_accepted","gateway_evidence":{"checkpoint_id":812,"decoder_id":"agriculture-kit-payload-v2","decoder_version":"test-decoder-v2","gateway_event_id":99123,"gateway_id":"0016c001f139a1cb","journal_record_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","journal_segment_hash":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","journal_segment_id":53,"journal_sequence":52987,"normalized_digest_sha256":"dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd","raw_app_data_sha256":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","status":"verified","verification_id":12345},"lorawan":{"confirmed":false,"f_cnt":104,"f_port":2},"observation":{"observed_at":"2000-01-01T00:00:00.000Z","received_at":"2000-01-01T00:00:01.000Z"},"payload":{"decoded_payload":{"battery_v":3.6,"temperature_c":24.5},"decoder_version":"test-v2","raw_data_base64":"AQI="},"schema_version":"telemetry-attestation-v2","source":{"application_id":"test","dev_eui":"0000000000000001","device_id":"test-device","device_model":"test-model","gateway_id":"0016c001f139a1cb","network_server":"chirpstack","region":"as923"},"source_event_key":"test-v2"}`
const v2ExpectedDigest = "25740c6bd9eee20b01151789c891f9b100b7dd0aa1144c20689ce1231cf7b96f"

func TestCanonicalV1FrozenVector(t *testing.T) {
	evidence := fixtureV1()
	actual, err := CanonicalizeEvidence(evidence)
	if err != nil {
		t.Fatal(err)
	}
	if string(actual.CanonicalJSON) != v1ExpectedCanonical {
		t.Fatalf("canonical v1 mismatch\nactual: %s\nexpected: %s", actual.CanonicalJSON, v1ExpectedCanonical)
	}
	if actual.DigestSHA256 != v1ExpectedDigest {
		t.Fatalf("v1 digest=%s want=%s", actual.DigestSHA256, v1ExpectedDigest)
	}
}

func TestCanonicalV2FrozenVector(t *testing.T) {
	evidence := fixtureV2()
	actual, err := CanonicalizeEvidence(evidence)
	if err != nil {
		t.Fatal(err)
	}
	if string(actual.CanonicalJSON) != v2ExpectedCanonical {
		t.Fatalf("canonical v2 mismatch\nactual: %s\nexpected: %s", actual.CanonicalJSON, v2ExpectedCanonical)
	}
	if actual.DigestSHA256 != v2ExpectedDigest {
		t.Fatalf("v2 digest=%s want=%s", actual.DigestSHA256, v2ExpectedDigest)
	}
}

func TestCanonicalV2RejectsUnverifiedOrMismatchedGateway(t *testing.T) {
	evidence := fixtureV2()
	evidence.GatewayEvidence.Status = "pending"
	if _, err := CanonicalizeEvidence(evidence); err == nil {
		t.Fatal("expected unverified v2 evidence to fail")
	}
	evidence = fixtureV2()
	evidence.GatewayEvidence.GatewayID = "0000000000000002"
	if _, err := CanonicalizeEvidence(evidence); err == nil {
		t.Fatal("expected gateway mismatch to fail")
	}
}

func fixtureV1() Evidence {
	raw := "AQI="
	return Evidence{
		SchemaVersion:  SchemaVersionV1,
		EventKey:       "uplink:test",
		SourceEventKey: "test",
		EventType:      EventTypeUplink,
		Source: SourceEvidence{
			NetworkServer: "chirpstack", ApplicationID: stringPtr("test"), DeviceID: stringPtr("test-device"),
			DeviceModel: stringPtr("test-model"), DevEUI: "0000000000000001",
			GatewayID: stringPtr("0000000000000002"), Region: stringPtr("as923_3"),
		},
		LoRaWAN:     LoRaWANEvidence{FPort: int64Ptr(2), FCnt: int64Ptr(104), Confirmed: boolPtr(false)},
		Observation: ObservationEvidence{ObservedAt: "2000-01-01T00:00:00.000Z", ReceivedAt: "2000-01-01T00:00:01.000Z"},
		Payload: PayloadEvidence{
			RawDataBase64: &raw, DecodedPayload: json.RawMessage(`{"battery_v":3.6,"temperature_c":24.5}`), DecoderVersion: stringPtr("test-v1"),
		},
	}
}

func fixtureV2() Evidence {
	evidence := fixtureV1()
	evidence.SchemaVersion = SchemaVersionV2
	evidence.EventKey = "uplink:test-v2"
	evidence.SourceEventKey = "test-v2"
	evidence.Source.GatewayID = stringPtr("0016c001f139a1cb")
	evidence.Source.Region = stringPtr("as923")
	evidence.Payload.DecoderVersion = stringPtr("test-v2")
	evidence.GatewayEvidence = &GatewayEvidence{
		Status: "verified", VerificationID: 12345, GatewayID: "0016c001f139a1cb",
		JournalSegmentID: 53, JournalSequence: 52987,
		JournalRecordHash:  "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
		JournalSegmentHash: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
		CheckpointID:       812, GatewayEventID: 99123,
		DecoderID: "agriculture-kit-payload-v2", DecoderVersion: "test-decoder-v2",
		RawAppDataSHA256:       "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
		NormalizedDigestSHA256: "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
	}
	return evidence
}

func stringPtr(value string) *string { return &value }
func int64Ptr(value int64) *int64    { return &value }
func boolPtr(value bool) *bool       { return &value }
