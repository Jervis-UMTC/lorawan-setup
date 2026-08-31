package fabricadapter

import (
	"encoding/json"
	"fmt"
)

const (
	v1VectorCanonical = `{"event_key":"uplink:test","event_type":"lorawan_uplink_accepted","lorawan":{"confirmed":false,"f_cnt":104,"f_port":2},"observation":{"observed_at":"2000-01-01T00:00:00.000Z","received_at":"2000-01-01T00:00:01.000Z"},"payload":{"decoded_payload":{"battery_v":3.6,"temperature_c":24.5},"decoder_version":"test-v1","raw_data_base64":"AQI="},"schema_version":"telemetry-attestation-v1","source":{"application_id":"test","dev_eui":"0000000000000001","device_id":"test-device","device_model":"test-model","gateway_id":"0000000000000002","network_server":"chirpstack","region":"as923_3"},"source_event_key":"test"}`
	v1VectorDigest    = "c2952e8cddc7f39a17522cb49dd3292c9af75c00fdc37172f74bb3dc955f3a5c"
	v2VectorCanonical = `{"event_key":"uplink:test-v2","event_type":"lorawan_uplink_accepted","gateway_evidence":{"checkpoint_id":812,"decoder_id":"agriculture-kit-payload-v2","decoder_version":"test-decoder-v2","gateway_event_id":99123,"gateway_id":"0016c001f139a1cb","journal_record_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","journal_segment_hash":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","journal_segment_id":53,"journal_sequence":52987,"normalized_digest_sha256":"dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd","raw_app_data_sha256":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","status":"verified","verification_id":12345},"lorawan":{"confirmed":false,"f_cnt":104,"f_port":2},"observation":{"observed_at":"2000-01-01T00:00:00.000Z","received_at":"2000-01-01T00:00:01.000Z"},"payload":{"decoded_payload":{"battery_v":3.6,"temperature_c":24.5},"decoder_version":"test-v2","raw_data_base64":"AQI="},"schema_version":"telemetry-attestation-v2","source":{"application_id":"test","dev_eui":"0000000000000001","device_id":"test-device","device_model":"test-model","gateway_id":"0016c001f139a1cb","network_server":"chirpstack","region":"as923"},"source_event_key":"test-v2"}`
	v2VectorDigest    = "25740c6bd9eee20b01151789c891f9b100b7dd0aa1144c20689ce1231cf7b96f"
)

func SelfTest() error {
	vectors := []struct {
		name      string
		evidence  Evidence
		canonical string
		digest    string
	}{
		{name: "v1", evidence: startupVectorV1(), canonical: v1VectorCanonical, digest: v1VectorDigest},
		{name: "v2", evidence: startupVectorV2(), canonical: v2VectorCanonical, digest: v2VectorDigest},
	}
	for _, vector := range vectors {
		actual, err := CanonicalizeEvidence(vector.evidence)
		if err != nil {
			return fmt.Errorf("Fabric canonicalization %s startup vector: %w", vector.name, err)
		}
		if string(actual.CanonicalJSON) != vector.canonical || actual.DigestSHA256 != vector.digest {
			return fmt.Errorf("Fabric canonicalization %s startup vector mismatch", vector.name)
		}
	}
	return nil
}

func startupVectorV1() Evidence {
	raw := "AQI="
	return Evidence{
		SchemaVersion:  SchemaVersionV1,
		EventKey:       "uplink:test",
		SourceEventKey: "test",
		EventType:      EventTypeUplink,
		Source: SourceEvidence{
			NetworkServer: "chirpstack", ApplicationID: vectorString("test"), DeviceID: vectorString("test-device"),
			DeviceModel: vectorString("test-model"), DevEUI: "0000000000000001",
			GatewayID: vectorString("0000000000000002"), Region: vectorString("as923_3"),
		},
		LoRaWAN:     LoRaWANEvidence{FPort: vectorInt64(2), FCnt: vectorInt64(104), Confirmed: vectorBool(false)},
		Observation: ObservationEvidence{ObservedAt: "2000-01-01T00:00:00.000Z", ReceivedAt: "2000-01-01T00:00:01.000Z"},
		Payload: PayloadEvidence{
			RawDataBase64: &raw, DecodedPayload: json.RawMessage(`{"battery_v":3.6,"temperature_c":24.5}`), DecoderVersion: vectorString("test-v1"),
		},
	}
}

func startupVectorV2() Evidence {
	evidence := startupVectorV1()
	evidence.SchemaVersion = SchemaVersionV2
	evidence.EventKey = "uplink:test-v2"
	evidence.SourceEventKey = "test-v2"
	evidence.Source.GatewayID = vectorString("0016c001f139a1cb")
	evidence.Source.Region = vectorString("as923")
	evidence.Payload.DecoderVersion = vectorString("test-v2")
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

func vectorString(value string) *string { return &value }
func vectorInt64(value int64) *int64    { return &value }
func vectorBool(value bool) *bool       { return &value }
