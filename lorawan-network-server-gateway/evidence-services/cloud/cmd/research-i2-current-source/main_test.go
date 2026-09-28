package main

import (
	"encoding/json"
	"strings"
	"testing"
)

const frozenDigest = "c2952e8cddc7f39a17522cb49dd3292c9af75c00fdc37172f74bb3dc955f3a5c"
const frozenCanonical = `{"event_key":"uplink:test","event_type":"lorawan_uplink_accepted","lorawan":{"confirmed":false,"f_cnt":104,"f_port":2},"observation":{"observed_at":"2000-01-01T00:00:00.000Z","received_at":"2000-01-01T00:00:01.000Z"},"payload":{"decoded_payload":{"battery_v":3.6,"temperature_c":24.5},"decoder_version":"test-v1","raw_data_base64":"AQI="},"schema_version":"telemetry-attestation-v1","source":{"application_id":"test","dev_eui":"0000000000000001","device_id":"test-device","device_model":"test-model","gateway_id":"0000000000000002","network_server":"chirpstack","region":"as923_3"},"source_event_key":"test"}`

func frozenSnapshot() inputSnapshot {
	fport := int64(2)
	fcnt := int64(104)
	confirmed := false
	temperature := 24.5
	application, device, model := "test", "test-device", "test-model"
	gateway, region, decoder, raw := "0000000000000002", "as923_3", "test-v1", "AQI="
	return inputSnapshot{
		SourceQueryRef: "read-only-source:frozen-test",
		OutboxQueryRef: "read-only-outbox:frozen-test",
		SchemaVersion:  "telemetry-attestation-v1",
		EventKey:       "uplink:test", SourceEventKey: "test", EventType: "lorawan_uplink_accepted",
		ObservedAt: "2000-01-01T00:00:00.000Z",
		Source: sourceSnapshot{
			ReceivedAt:    "2000-01-01T00:00:01.000Z",
			ApplicationID: &application, DeviceID: &device, DeviceModel: &model,
			DecoderVersion: &decoder, DevEUI: "0000000000000001",
			GatewayID: &gateway, Region: &region, FPort: &fport, FCnt: &fcnt,
			Confirmed: &confirmed, RawDataBase64: &raw,
			PayloadJSON:  json.RawMessage(`{"battery_v":3.6,"temperature_c":24.5}`),
			TemperatureC: &temperature,
		},
	}
}
func asJSON(t *testing.T, s inputSnapshot) []byte {
	t.Helper()
	raw, err := json.Marshal(s)
	if err != nil {
		t.Fatal(err)
	}
	return raw
}
func TestV1FrozenProductionCanonicalization(t *testing.T) {
	result, err := rebuild(asJSON(t, frozenSnapshot()))
	if err != nil {
		t.Fatal(err)
	}
	if result.CanonicalJSON != frozenCanonical || result.DigestSHA256 != frozenDigest {
		t.Fatalf("production vector mismatch: %s", result.DigestSHA256)
	}
	if result.CountedResearch {
		t.Fatal("offline snapshot must never mark research counted")
	}
}
func TestCurrentSourceTamperAndRestoration(t *testing.T) {
	original := frozenSnapshot()
	altered := original
	altered.Source.PayloadJSON = json.RawMessage(`{"battery_v":3.6,"temperature_c":34.5}`)
	temperature := 34.5
	altered.Source.TemperatureC = &temperature
	after, err := rebuild(asJSON(t, altered))
	if err != nil {
		t.Fatal(err)
	}
	if after.DigestSHA256 == frozenDigest {
		t.Fatal("temperature tamper not detected")
	}
	if !strings.Contains(after.CanonicalJSON, `"temperature_c":34.5`) {
		t.Fatal("modified source not used")
	}
	restored, err := rebuild(asJSON(t, original))
	if err != nil {
		t.Fatal(err)
	}
	if restored.DigestSHA256 != frozenDigest {
		t.Fatal("restoration not proven")
	}
}
func TestNoFallbackFromUnsupportedSchema(t *testing.T) {
	bad := frozenSnapshot()
	bad.SchemaVersion = "telemetry-attestation-v2"
	if _, err := rebuild(asJSON(t, bad)); err == nil {
		t.Fatal("v2 accepted as v1")
	}
}
func TestMissingCurrentQueryRefsRejected(t *testing.T) {
	bad := frozenSnapshot()
	bad.SourceQueryRef = ""
	if _, err := rebuild(asJSON(t, bad)); err == nil {
		t.Fatal("missing query accepted")
	}
}
func TestInvalidCurrentSourceDataRejected(t *testing.T) {
	bad := frozenSnapshot()
	bad.Source.DevEUI = "INVALID"
	if _, err := rebuild(asJSON(t, bad)); err == nil {
		t.Fatal("bad DevEUI accepted")
	}
	bad = frozenSnapshot()
	bad.Source.PayloadJSON = json.RawMessage(`{"temperature_c":34.5}`)
	if _, err := rebuild(asJSON(t, bad)); err == nil {
		t.Fatal("column/payload mismatch accepted")
	}
	if _, err := rebuild([]byte(`{"event_key":"uplink:test"}`)); err == nil {
		t.Fatal("missing payload accepted")
	}
}
