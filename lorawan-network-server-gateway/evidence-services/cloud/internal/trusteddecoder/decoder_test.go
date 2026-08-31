package trusteddecoder

import (
	"encoding/hex"
	"testing"
)

const (
	validFixtureHex       = "0200000001000003e81595fb2e014100018bcd09980000303900001a850aae17eb000189c00001e240010e74007f"
	validRawSHA256        = "06800936504bb1fa954546c3a6bbde7d3a5f2539590d1f32119b19ae162d7460"
	validNormalizedSHA256 = "594e6f77e8f8f6058a16250e6b30ba96a6766f5813c323c22d93ed6fec7d6118"
)

func TestDecodeFixedValidVector(t *testing.T) {
	raw, err := hex.DecodeString(validFixtureHex)
	if err != nil {
		t.Fatalf("DecodeString() error = %v", err)
	}

	got, err := Decode(raw)
	if err != nil {
		t.Fatalf("Decode() error = %v", err)
	}
	if got.DecoderID != DecoderID || got.DecoderVersion != DecoderVersion {
		t.Fatalf("decoder identity changed: %s / %s", got.DecoderID, got.DecoderVersion)
	}
	if got.RawSHA256 != validRawSHA256 {
		t.Fatalf("raw SHA-256 = %s, want %s", got.RawSHA256, validRawSHA256)
	}
	if got.NormalizedSHA256 != validNormalizedSHA256 {
		t.Fatalf("normalized SHA-256 = %s, want %s\n%s", got.NormalizedSHA256, validNormalizedSHA256, got.NormalizedJSON)
	}
	if got.Normalized.PayloadVersion != 2 || got.Normalized.TestSequence != 1 || got.Normalized.SensorUptimeMS != 1000 || got.Normalized.SensorValidityBitmap != 127 {
		t.Fatalf("unexpected normalized metadata: %+v", got.Normalized)
	}

	wantNumbers := map[string]float64{
		"barometer_pressure_pa":          101325,
		"barometer_temperature_c":        24.56,
		"battery_v":                      3.7,
		"environment_gas_resistance_ohm": 123456,
		"environment_humidity_percent":   61.23,
		"environment_pressure_pa":        100800,
		"environment_temperature_c":      27.34,
		"light_opt3001_lux":              67.89,
		"light_veml7700_lux":             123.45,
		"soil_moisture_percent":          55.25,
		"soil_temperature_c":             -12.34,
		"uv_index":                       3.21,
	}
	for _, metric := range got.Normalized.Metrics {
		if metric.Quality != "measured" {
			t.Fatalf("metric %s quality = %s, want measured", metric.MetricName, metric.Quality)
		}
		if metric.MetricName == "rain_wet" {
			if metric.ValueBool == nil || !*metric.ValueBool || metric.ValueNumber != nil {
				t.Fatalf("rain_wet = %+v", metric)
			}
			continue
		}
		want, ok := wantNumbers[metric.MetricName]
		if !ok || metric.ValueNumber == nil || *metric.ValueNumber != want || metric.ValueBool != nil {
			t.Fatalf("unexpected metric %+v, want numeric %v", metric, want)
		}
	}
}

func TestDecodeValidityAndBatterySentinel(t *testing.T) {
	raw, _ := hex.DecodeString(validFixtureHex)
	raw[42], raw[43] = 0, 0
	raw[44], raw[45] = 0, 0

	got, err := Decode(raw)
	if err != nil {
		t.Fatalf("Decode() error = %v", err)
	}
	for _, metric := range got.Normalized.Metrics {
		if metric.Quality != "invalid" || metric.ValueBool != nil || metric.ValueNumber != nil {
			t.Fatalf("metric should be invalid/null: %+v", metric)
		}
	}
}

func TestValidatePackageDigest(t *testing.T) {
	original := PackageDigest
	t.Cleanup(func() { PackageDigest = original })

	PackageDigest = ""
	if err := ValidatePackageDigest(); err == nil {
		t.Fatal("ValidatePackageDigest() accepted an unset digest")
	}

	PackageDigest = "ABCDEF"
	if err := ValidatePackageDigest(); err == nil {
		t.Fatal("ValidatePackageDigest() accepted malformed digest")
	}

	PackageDigest = validRawSHA256
	if err := ValidatePackageDigest(); err != nil {
		t.Fatalf("ValidatePackageDigest() rejected valid lowercase SHA-256: %v", err)
	}
}

func TestDecodeRejectsWrongLengthVersionAndRainEncoding(t *testing.T) {
	if _, err := Decode(make([]byte, 45)); err == nil {
		t.Fatal("Decode() accepted wrong length")
	}
	raw := make([]byte, PayloadLength)
	raw[0] = 3
	if _, err := Decode(raw); err == nil {
		t.Fatal("Decode() accepted unsupported version")
	}

	raw, _ = hex.DecodeString(validFixtureHex)
	raw[41] = 2
	if _, err := Decode(raw); err == nil {
		t.Fatal("Decode() accepted invalid rain_wet byte")
	}
}
