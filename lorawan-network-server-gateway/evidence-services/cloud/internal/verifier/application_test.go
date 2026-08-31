package verifier

import (
	"encoding/base64"
	"encoding/hex"
	"testing"
	"time"

	"lorawan/evidence-services/cloud/internal/trusteddecoder"
)

func validApplicationFixture(t *testing.T) ApplicationEvidence {
	t.Helper()
	raw, err := hex.DecodeString(trusteddecoder.FixtureRawHex)
	if err != nil {
		t.Fatal(err)
	}
	decoded, err := trusteddecoder.Decode(raw)
	if err != nil {
		t.Fatal(err)
	}
	gatewayID := "0016c001f139a1cb"
	gatewayUplinkID := int64(16909060)
	gatewayFrequencyHz := int64(923200000)
	gatewayContextBase64 := "3q2+7w=="
	gatewayRSSI := int32(-72)
	gatewaySNR := 8.5
	decoderVersion := OperationalDecoderVersion
	rawB64 := base64.StdEncoding.EncodeToString(raw)
	app := ApplicationEvidence{
		EventType:                 ExpectedEventType,
		SchemaVersion:             SchemaVersionV2,
		EventKey:                  "fixture-event",
		ObservedAt:                time.Date(2026, 8, 30, 1, 0, 0, 0, time.UTC),
		DevEUI:                    "0000000000000001",
		GatewayID:                 &gatewayID,
		GatewayUplinkID:           &gatewayUplinkID,
		GatewayFrequencyHz:        &gatewayFrequencyHz,
		GatewayContextBase64:      &gatewayContextBase64,
		GatewayRSSIDbm:            &gatewayRSSI,
		GatewaySNRDb:              &gatewaySNR,
		OperationalDecoderVersion: &decoderVersion,
		RawDataBase64:             &rawB64,
	}
	for _, expected := range decoded.Normalized.Metrics {
		metric := StoredMetric{
			DevEUI:      app.DevEUI,
			MetricName:  expected.MetricName,
			ValueNumber: expected.ValueNumber,
			ValueBool:   expected.ValueBool,
			Unit:        expected.Unit,
			Quality:     expected.Quality,
			SourceField: expected.SourceField,
		}
		app.Measurements = append(app.Measurements, metric)
	}
	return app
}

func TestCheckApplicationValidFixture(t *testing.T) {
	app := validApplicationFixture(t)
	check := CheckApplication(app)
	if !check.Consistent || check.Reason != "" {
		t.Fatalf("CheckApplication consistent=%v reason=%q", check.Consistent, check.Reason)
	}
	if check.Evidence.RawAppDataSHA256 != trusteddecoder.FixtureRawSHA256 || check.Evidence.NormalizedDigestSHA256 != trusteddecoder.FixtureNormalizedSHA256 {
		t.Fatal("trusted decoder fixed digests changed")
	}
}

func TestCheckApplicationRejectsStoredMetricMismatch(t *testing.T) {
	app := validApplicationFixture(t)
	for i := range app.Measurements {
		if app.Measurements[i].ValueNumber != nil {
			value := *app.Measurements[i].ValueNumber + 1
			app.Measurements[i].ValueNumber = &value
			break
		}
	}
	check := CheckApplication(app)
	if check.Consistent || check.Reason != ReasonStoredTelemetryMismatch {
		t.Fatalf("CheckApplication consistent=%v reason=%q", check.Consistent, check.Reason)
	}
}

func TestCheckApplicationRejectsMalformedGatewayProvenance(t *testing.T) {
	app := validApplicationFixture(t)
	badContext := "%%%"
	app.GatewayContextBase64 = &badContext
	check := CheckApplication(app)
	if check.Consistent || check.Reason != ReasonApplicationGatewayInvalid {
		t.Fatalf("CheckApplication consistent=%v reason=%q", check.Consistent, check.Reason)
	}
}

func TestCheckApplicationRejectsInvalidRawBase64(t *testing.T) {
	app := validApplicationFixture(t)
	bad := "%%%"
	app.RawDataBase64 = &bad
	check := CheckApplication(app)
	if check.Consistent || check.Reason != ReasonApplicationPayloadInvalid {
		t.Fatalf("CheckApplication consistent=%v reason=%q", check.Consistent, check.Reason)
	}
}
