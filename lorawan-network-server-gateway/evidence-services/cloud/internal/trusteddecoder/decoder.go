package trusteddecoder

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"sort"
	"strings"
)

const (
	DecoderID               = "emu01-agriculture-kit-payload-v2"
	DecoderVersion          = "trusted-decoder-go-v1"
	NormalizedSchemaVersion = "trusted-decoder-normalized-v1"
	PayloadVersion          = 2
	PayloadLength           = 46
	FixtureRawHex           = "0200000001000003e81595fb2e014100018bcd09980000303900001a850aae17eb000189c00001e240010e74007f"
	FixtureRawSHA256        = "06800936504bb1fa954546c3a6bbde7d3a5f2539590d1f32119b19ae162d7460"
	FixtureNormalizedSHA256 = "594e6f77e8f8f6058a16250e6b30ba96a6766f5813c323c22d93ed6fec7d6118"
)

// PackageDigest identifies the exact production trusted-decoder source package.
// The reproducible build hashes a canonical manifest of sorted non-test Go
// source files and injects that lowercase SHA-256 at link time. The verifier
// binary/image has a separate artifact digest, avoiding a circular self-hash.
// Production startup rejects PackageDigest when it is unset or malformed.
var PackageDigest string

type Metric struct {
	MetricName  string
	Quality     string
	SourceField string
	Unit        string
	ValueBool   *bool
	ValueNumber *float64
}

type Normalized struct {
	Metrics              []Metric
	PayloadVersion       uint8
	SensorUptimeMS       uint32
	SensorValidityBitmap uint16
	TestSequence         uint32
}

type Result struct {
	DecoderID        string
	DecoderVersion   string
	RawSHA256        string
	NormalizedSHA256 string
	NormalizedJSON   []byte
	Normalized       Normalized
}

type canonicalMetric struct {
	MetricName  string   `json:"metric_name"`
	Quality     string   `json:"quality"`
	SourceField string   `json:"source_field"`
	Unit        string   `json:"unit"`
	ValueBool   *bool    `json:"value_bool"`
	ValueNumber *float64 `json:"value_number"`
}

type canonicalNormalized struct {
	Metrics              []canonicalMetric `json:"metrics"`
	PayloadVersion       uint8             `json:"payload_version"`
	SchemaVersion        string            `json:"schema_version"`
	SensorUptimeMS       uint32            `json:"sensor_uptime_ms"`
	SensorValidityBitmap uint16            `json:"sensor_validity_bitmap"`
	TestSequence         uint32            `json:"test_sequence"`
}

func Decode(raw []byte) (Result, error) {
	if len(raw) != PayloadLength {
		return Result{}, fmt.Errorf("expected %d-byte Agriculture Kit payload v2, got %d", PayloadLength, len(raw))
	}
	if raw[0] != PayloadVersion {
		return Result{}, fmt.Errorf("unsupported Agriculture Kit payload version %d", raw[0])
	}
	if raw[41] > 1 {
		return Result{}, fmt.Errorf("invalid rain_wet encoding %d", raw[41])
	}

	u16 := func(offset int) uint16 { return binary.BigEndian.Uint16(raw[offset : offset+2]) }
	i16 := func(offset int) int16 { return int16(u16(offset)) }
	u32 := func(offset int) uint32 { return binary.BigEndian.Uint32(raw[offset : offset+4]) }

	validity := u16(44)
	bitValid := func(bit uint) bool { return validity&(1<<bit) != 0 }

	metrics := []Metric{
		numericMetric("soil_moisture_percent", "%", float64(u16(9))/100, bitValid(0)),
		numericMetric("soil_temperature_c", "Cel", float64(i16(11))/100, bitValid(0)),
		numericMetric("uv_index", "1", float64(u16(13))/100, bitValid(1)),
		numericMetric("barometer_pressure_pa", "Pa", float64(u32(15)), bitValid(2)),
		numericMetric("barometer_temperature_c", "Cel", float64(i16(19))/100, bitValid(2)),
		numericMetric("light_veml7700_lux", "lx", float64(u32(21))/100, bitValid(3)),
		numericMetric("light_opt3001_lux", "lx", float64(u32(25))/100, bitValid(4)),
		numericMetric("environment_temperature_c", "Cel", float64(i16(29))/100, bitValid(5)),
		numericMetric("environment_humidity_percent", "%", float64(u16(31))/100, bitValid(5)),
		numericMetric("environment_pressure_pa", "Pa", float64(u32(33)), bitValid(5)),
		numericMetric("environment_gas_resistance_ohm", "ohm", float64(u32(37)), bitValid(5)),
		booleanMetric("rain_wet", "boolean", raw[41] == 1, bitValid(6)),
		numericMetric("battery_v", "V", float64(u16(42))/1000, u16(42) > 0),
	}

	sort.Slice(metrics, func(i, j int) bool { return metrics[i].MetricName < metrics[j].MetricName })

	normalized := Normalized{
		Metrics:              metrics,
		PayloadVersion:       raw[0],
		SensorUptimeMS:       u32(5),
		SensorValidityBitmap: validity,
		TestSequence:         u32(1),
	}

	canonical, err := CanonicalBytes(normalized)
	if err != nil {
		return Result{}, err
	}
	rawDigest := sha256.Sum256(raw)
	normalizedDigest := sha256.Sum256(canonical)

	return Result{
		DecoderID:        DecoderID,
		DecoderVersion:   DecoderVersion,
		RawSHA256:        hex.EncodeToString(rawDigest[:]),
		NormalizedSHA256: hex.EncodeToString(normalizedDigest[:]),
		NormalizedJSON:   canonical,
		Normalized:       normalized,
	}, nil
}

func numericMetric(name, unit string, value float64, valid bool) Metric {
	metric := Metric{MetricName: name, Quality: "invalid", SourceField: name, Unit: unit}
	if valid {
		metric.Quality = "measured"
		metric.ValueNumber = floatPtr(value)
	}
	return metric
}

func booleanMetric(name, unit string, value, valid bool) Metric {
	metric := Metric{MetricName: name, Quality: "invalid", SourceField: name, Unit: unit}
	if valid {
		metric.Quality = "measured"
		metric.ValueBool = boolPtr(value)
	}
	return metric
}

func CanonicalBytes(n Normalized) ([]byte, error) {
	metrics := append([]Metric(nil), n.Metrics...)
	sort.Slice(metrics, func(i, j int) bool { return metrics[i].MetricName < metrics[j].MetricName })

	canonicalMetrics := make([]canonicalMetric, 0, len(metrics))
	for _, metric := range metrics {
		if metric.MetricName == "" || metric.SourceField == "" || metric.Unit == "" || (metric.Quality != "measured" && metric.Quality != "invalid") {
			return nil, fmt.Errorf("invalid normalized metric %q", metric.MetricName)
		}
		if metric.ValueBool != nil && metric.ValueNumber != nil {
			return nil, fmt.Errorf("metric %q has both boolean and numeric values", metric.MetricName)
		}
		if metric.Quality == "invalid" && (metric.ValueBool != nil || metric.ValueNumber != nil) {
			return nil, fmt.Errorf("invalid metric %q must have null value", metric.MetricName)
		}

		canonicalMetrics = append(canonicalMetrics, canonicalMetric{
			MetricName:  metric.MetricName,
			Quality:     metric.Quality,
			SourceField: metric.SourceField,
			Unit:        metric.Unit,
			ValueBool:   metric.ValueBool,
			ValueNumber: metric.ValueNumber,
		})
	}

	return json.Marshal(canonicalNormalized{
		Metrics:              canonicalMetrics,
		PayloadVersion:       n.PayloadVersion,
		SchemaVersion:        NormalizedSchemaVersion,
		SensorUptimeMS:       n.SensorUptimeMS,
		SensorValidityBitmap: n.SensorValidityBitmap,
		TestSequence:         n.TestSequence,
	})
}

func SelfTest() error {
	raw, err := hex.DecodeString(FixtureRawHex)
	if err != nil {
		return fmt.Errorf("decode trusted-decoder fixture: %w", err)
	}
	result, err := Decode(raw)
	if err != nil {
		return fmt.Errorf("trusted-decoder fixture decode: %w", err)
	}
	if result.RawSHA256 != FixtureRawSHA256 {
		return fmt.Errorf("trusted-decoder fixture raw digest mismatch")
	}
	if result.NormalizedSHA256 != FixtureNormalizedSHA256 {
		return fmt.Errorf("trusted-decoder fixture normalized digest mismatch")
	}
	return nil
}

func ValidatePackageDigest() error {
	if len(PackageDigest) != 64 || PackageDigest != strings.ToLower(PackageDigest) {
		return fmt.Errorf("trusted-decoder package digest must be injected as lowercase 64-hex SHA-256")
	}
	decoded, err := hex.DecodeString(PackageDigest)
	if err != nil || len(decoded) != sha256.Size {
		return fmt.Errorf("trusted-decoder package digest is not valid SHA-256")
	}
	return nil
}

func floatPtr(v float64) *float64 { return &v }
func boolPtr(v bool) *bool        { return &v }
