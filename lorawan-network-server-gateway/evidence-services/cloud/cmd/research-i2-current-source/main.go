// research-i2-current-source reconstructs source evidence from a read-only
// database snapshot. It does NOT connect to PostgreSQL, OpenBao or Fabric;
// no signing, outbox update or new Fabric transaction can occur here.
// Its canonicalization uses the SAME fabricadapter.BuildEvidence and
// fabricadapter.CanonicalizeEvidence used by the production adapter.
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"lorawan/evidence-services/cloud/internal/fabricadapter"
)

type sourceSnapshot struct {
	ReceivedAt     string          `json:"received_at"`
	ApplicationID  *string         `json:"application_id"`
	DeviceID       *string         `json:"device_id"`
	DeviceModel    *string         `json:"device_model"`
	DecoderVersion *string         `json:"decoder_version"`
	DevEUI         string          `json:"dev_eui"`
	GatewayID      *string         `json:"gateway_id"`
	Region         *string         `json:"region"`
	FPort          *int64          `json:"f_port"`
	FCnt           *int64          `json:"f_cnt"`
	Confirmed      *bool           `json:"confirmed"`
	RawDataBase64  *string         `json:"raw_data_base64"`
	PayloadJSON    json.RawMessage `json:"payload_json"`
	TemperatureC   *float64        `json:"temperature_c"` // convenience column; NOT a new canonical field
}
type inputSnapshot struct {
	SourceQueryRef string         `json:"source_query_ref"`
	OutboxQueryRef string         `json:"outbox_query_ref"`
	SchemaVersion  string         `json:"schema_version"`
	EventKey       string         `json:"event_key"`
	SourceEventKey string         `json:"source_event_key"`
	EventType      string         `json:"event_type"`
	ObservedAt     string         `json:"observed_at"`
	Source         sourceSnapshot `json:"source"`
}
type result struct {
	Qualification        string `json:"qualification"`
	CountedResearch      bool   `json:"counted_research"`
	SourceQueryRef       string `json:"source_query_ref"`
	OutboxQueryRef       string `json:"outbox_query_ref"`
	EventKey             string `json:"event_key"`
	SourceEventKey       string `json:"source_event_key"`
	SchemaVersion        string `json:"schema_version"`
	SourceSnapshotSHA256 string `json:"source_snapshot_sha256"`
	CanonicalJSON        string `json:"canonical_json"`
	DigestSHA256         string `json:"digest_sha256"`
}

func parseUTC(s string) (time.Time, error) {
	t, err := time.Parse(time.RFC3339Nano, s)
	if err != nil || t.IsZero() || t.Location() == nil || t.Format(time.RFC3339Nano) == "" {
		return time.Time{}, errors.New("source/outbox timestamp must be RFC3339 with timezone")
	}
	if t.UTC().UnixNano() != t.UnixNano() {
		return time.Time{}, errors.New("timestamp conversion failed")
	}
	return t, nil
}
func rebuild(raw []byte) (result, error) {
	if err := fabricadapter.SelfTest(); err != nil {
		return result{}, fmt.Errorf("production canonicalization vector failed: %w", err)
	}
	var input inputSnapshot
	if err := json.Unmarshal(raw, &input); err != nil {
		return result{}, fmt.Errorf("source snapshot invalid JSON: %w", err)
	}
	if strings.TrimSpace(input.SourceQueryRef) == "" || strings.TrimSpace(input.OutboxQueryRef) == "" {
		return result{}, errors.New("read-only source and outbox query references required")
	}
	if input.SchemaVersion != fabricadapter.SchemaVersionV1 {
		return result{}, errors.New("I2 is frozen to telemetry-attestation-v1; no fallback canonicalization")
	}
	observed, err := parseUTC(input.ObservedAt)
	if err != nil {
		return result{}, err
	}
	received, err := parseUTC(input.Source.ReceivedAt)
	if err != nil {
		return result{}, err
	}
	work := fabricadapter.OutboxWork{
		EventKey: input.EventKey, SourceEventKey: input.SourceEventKey,
		EventType: input.EventType, SchemaVersion: input.SchemaVersion,
		ObservedAt: observed,
	}
	source := fabricadapter.SourceRow{
		ReceivedAt: received, ApplicationID: input.Source.ApplicationID,
		DeviceID: input.Source.DeviceID, DeviceModel: input.Source.DeviceModel,
		DecoderVersion: input.Source.DecoderVersion, DevEUI: input.Source.DevEUI,
		GatewayID: input.Source.GatewayID, Region: input.Source.Region,
		FPort: input.Source.FPort, FCnt: input.Source.FCnt,
		Confirmed: input.Source.Confirmed, RawDataBase64: input.Source.RawDataBase64,
		PayloadJSON: input.Source.PayloadJSON,
	}
	if input.Source.TemperatureC == nil {
		return result{}, errors.New("current convenience temperature_c missing")
	}
	var decoded map[string]any
	if err := json.Unmarshal(input.Source.PayloadJSON, &decoded); err != nil {
		return result{}, errors.New("current source decoded payload must be a JSON object")
	}
	temp, ok := decoded["temperature_c"].(float64)
	if !ok || temp != *input.Source.TemperatureC {
		return result{}, errors.New("current temperature_c column/payload mismatch")
	}
	evidence, err := fabricadapter.BuildEvidence(work, source, nil)
	if err != nil {
		return result{}, err
	}
	sealed, err := fabricadapter.CanonicalizeEvidence(evidence)
	if err != nil {
		return result{}, err
	}
	if evidence.EventKey != input.EventKey || evidence.SourceEventKey != input.SourceEventKey {
		return result{}, errors.New("source identity changed during recomputation")
	}
	sum := sha256.Sum256(raw)
	return result{
		Qualification:   "READ_ONLY_SNAPSHOT_RECOMPUTE_NOT_LIVE_ATTESTATION",
		CountedResearch: false, SourceQueryRef: input.SourceQueryRef,
		OutboxQueryRef: input.OutboxQueryRef, EventKey: input.EventKey,
		SourceEventKey: input.SourceEventKey, SchemaVersion: input.SchemaVersion,
		SourceSnapshotSHA256: hex.EncodeToString(sum[:]),
		CanonicalJSON:        string(sealed.CanonicalJSON),
		DigestSHA256:         sealed.DigestSHA256,
	}, nil
}
func main() {
	in := flag.String("input", "", "JSON exported from independently read-only source/outbox SQL")
	out := flag.String("output", "", "different file for recomputed canonical bytes and digest")
	flag.Parse()
	if *in == "" || *out == "" {
		fmt.Fprintln(os.Stderr, "--input and --output are required")
		os.Exit(2)
	}
	srcPath, err := filepath.Abs(*in)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	dstPath, err := filepath.Abs(*out)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	if strings.EqualFold(srcPath, dstPath) {
		fmt.Fprintln(os.Stderr, "refusing to overwrite input snapshot")
		os.Exit(2)
	}
	f, err := os.Open(srcPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	raw, err := io.ReadAll(io.LimitReader(f, 4<<20+1))
	f.Close()
	if err != nil || len(raw) > 4<<20 {
		fmt.Fprintln(os.Stderr, "snapshot read/size limit failed")
		os.Exit(1)
	}
	result, err := rebuild(raw)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	bytes, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err = os.MkdirAll(filepath.Dir(dstPath), 0700); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err = os.WriteFile(dstPath, append(bytes, '\n'), 0600); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println("I2_CURRENT_SOURCE=RECOMPUTED_READ_ONLY COUNTED_RESEARCH=FALSE")
}
