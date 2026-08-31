package verifier

import (
	"encoding/base64"
	"math"
	"regexp"

	"lorawan/evidence-services/cloud/internal/trusteddecoder"
)

var canonicalEUI = regexp.MustCompile(`^[0-9a-f]{16}$`)

type ApplicationCheck struct {
	Consistent bool
	Reason     string
	Evidence   DecoderEvidence
}

func CheckApplication(app ApplicationEvidence) ApplicationCheck {
	check := ApplicationCheck{Reason: ReasonStoredTelemetryMismatch}
	if app.SchemaVersion != SchemaVersionV2 {
		check.Reason = ReasonUnsupportedSchemaVersion
		return check
	}
	if app.EventType != ExpectedEventType {
		check.Reason = ReasonUnsupportedEventType
		return check
	}
	if app.OperationalDecoderVersion == nil || *app.OperationalDecoderVersion != OperationalDecoderVersion {
		check.Reason = ReasonUnsupportedApplicationCodec
		return check
	}
	if !canonicalEUI.MatchString(app.DevEUI) || app.GatewayID == nil || !canonicalEUI.MatchString(*app.GatewayID) ||
		app.GatewayUplinkID == nil || *app.GatewayUplinkID < 0 || *app.GatewayUplinkID > math.MaxUint32 ||
		app.GatewayFrequencyHz == nil || *app.GatewayFrequencyHz <= 0 || *app.GatewayFrequencyHz > math.MaxUint32 ||
		app.GatewayContextBase64 == nil || app.GatewayRSSIDbm == nil || *app.GatewayRSSIDbm < -200 || *app.GatewayRSSIDbm > 0 ||
		app.GatewaySNRDb == nil || math.IsNaN(*app.GatewaySNRDb) || math.IsInf(*app.GatewaySNRDb, 0) || *app.GatewaySNRDb < -100 || *app.GatewaySNRDb > 100 {
		check.Reason = ReasonApplicationGatewayInvalid
		return check
	}
	contextBytes, err := base64.StdEncoding.Strict().DecodeString(*app.GatewayContextBase64)
	if err != nil || base64.StdEncoding.EncodeToString(contextBytes) != *app.GatewayContextBase64 {
		check.Reason = ReasonApplicationGatewayInvalid
		return check
	}
	check.Evidence.GatewayID = app.GatewayID
	if app.RawDataBase64 == nil {
		check.Reason = ReasonApplicationPayloadInvalid
		return check
	}
	raw, err := base64.StdEncoding.Strict().DecodeString(*app.RawDataBase64)
	if err != nil {
		check.Reason = ReasonApplicationPayloadInvalid
		return check
	}
	decoded, err := trusteddecoder.Decode(raw)
	if err != nil {
		check.Reason = ReasonApplicationPayloadInvalid
		return check
	}
	check.Evidence.DecoderID = decoded.DecoderID
	check.Evidence.DecoderVersion = decoded.DecoderVersion
	check.Evidence.RawAppDataSHA256 = decoded.RawSHA256
	check.Evidence.NormalizedDigestSHA256 = decoded.NormalizedSHA256

	if len(app.Measurements) != len(decoded.Normalized.Metrics) {
		return check
	}
	stored := make(map[string]StoredMetric, len(app.Measurements))
	for _, metric := range app.Measurements {
		key := metric.MetricName + "\x00" + metric.Unit
		if _, exists := stored[key]; exists {
			return check
		}
		stored[key] = metric
	}
	for _, expected := range decoded.Normalized.Metrics {
		key := expected.MetricName + "\x00" + expected.Unit
		actual, ok := stored[key]
		if !ok || actual.DevEUI != app.DevEUI || actual.SourceField != expected.SourceField || actual.Quality != expected.Quality {
			return check
		}
		if actual.ValueText != nil {
			return check
		}
		if !sameNumber(actual.ValueNumber, expected.ValueNumber) || !sameBool(actual.ValueBool, expected.ValueBool) {
			return check
		}
	}
	check.Consistent = true
	check.Reason = ""
	return check
}

func sameNumber(actual, expected *float64) bool {
	if actual == nil || expected == nil {
		return actual == nil && expected == nil
	}
	return math.Abs(*actual-*expected) <= 1e-9
}

func sameBool(actual, expected *bool) bool {
	if actual == nil || expected == nil {
		return actual == nil && expected == nil
	}
	return *actual == *expected
}
