package main

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	"lorawan/evidence-services/cloud/internal/fabricadapter"
)

const studyID = "zacharias-lorawan-fabric"

type benchRecord struct {
	TrialID        string
	SourceRecordID string
	SourceSystemID string
	SourceType     string
	Producer       string
	ProducedAt     string
	SchemaVersion  string
	PayloadSHA256  string
	Payload        []byte
}

type benchResult struct {
	Sequence int
	Values   map[string]any
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintf(os.Stderr, "P2_BENCHMARK_ERROR=%s\n", strings.ReplaceAll(err.Error(), "\n", " "))
		os.Exit(1)
	}
}

func run() error {
	mode := flag.String("mode", "", "control or fabric")
	runPath := flag.String("run-manifest", "", "run-manifest.json")
	recordPath := flag.String("record-manifest", "", "record-manifest.json")
	outDir := flag.String("output-dir", "", "output directory")
	maxInflight := flag.Int("max-inflight", 512, "maximum concurrent client operations")
	flag.Parse()
	if *mode != "control" && *mode != "fabric" {
		return errors.New("--mode must be control or fabric")
	}
	if *runPath == "" || *recordPath == "" || *outDir == "" {
		return errors.New("--run-manifest, --record-manifest, and --output-dir are required")
	}
	if *maxInflight < 1 || *maxInflight > 4096 {
		return errors.New("--max-inflight must be 1..4096")
	}

	runManifest, err := readObject(*runPath)
	if err != nil {
		return fmt.Errorf("read run manifest: %w", err)
	}
	recordManifest, err := readObject(*recordPath)
	if err != nil {
		return fmt.Errorf("read record manifest: %w", err)
	}

	runID := str(runManifest, "run_id")
	if str(runManifest, "schema_version") != "1.0" || str(runManifest, "study_id") != studyID || str(runManifest, "test_id") != "P2" || runID == "" {
		return errors.New("unsupported P2 run manifest")
	}
	workload := obj(runManifest, "workload")
	rate := number(workload, "target_tps")
	intervalMS := number(workload, "interval_ms")
	planned := integer(workload, "planned_record_count")
	if rate <= 0 || intervalMS <= 0 || planned <= 0 || number(runManifest, "duration_seconds") <= 0 {
		return errors.New("P2 workload/duration is incomplete")
	}
	records, err := loadRecords(recordManifest, planned)
	if err != nil {
		return err
	}

	if err := os.MkdirAll(*outDir, 0750); err != nil {
		return err
	}

	var ledger *fabricadapter.GatewayClient
	if *mode == "fabric" {
		cfg, err := fabricadapter.LoadConfig()
		if err != nil {
			return fmt.Errorf("load production Fabric config: %w", err)
		}
		if !cfg.Enabled {
			return errors.New("FABRIC_ADAPTER_ENABLED must be true for fabric mode")
		}
		if cfg.FabricSourceSystemID != "lorawan-gateway-evidence" {
			return fmt.Errorf("unexpected Fabric source system ID %q", cfg.FabricSourceSystemID)
		}
		ledger, err = fabricadapter.NewGatewayClient(cfg)
		if err != nil {
			return fmt.Errorf("connect production Fabric Gateway: %w", err)
		}
		defer ledger.Close()
	}

	results := make([]benchResult, len(records))
	startUTC := time.Now().UTC()
	startMono := time.Now()
	interval := time.Duration(float64(time.Second) / rate)
	sem := make(chan struct{}, *maxInflight)
	var wg sync.WaitGroup

	for i := range records {
		i := i
		wg.Add(1)
		go func() {
			defer wg.Done()
			offset := time.Duration(i) * interval
			due := startMono.Add(offset)
			if wait := time.Until(due); wait > 0 {
				time.Sleep(wait)
			}
			scheduledUTC := startUTC.Add(offset)
			sem <- struct{}{}
			defer func() { <-sem }()
			results[i] = executeOne(ledger, records[i], *mode, runID, i+1, offset, scheduledUTC)
		}()
	}
	wg.Wait()
	endUTC := time.Now().UTC()
	sort.Slice(results, func(i, j int) bool { return results[i].Sequence < results[j].Sequence })

	if err := writeNDJSON(filepath.Join(*outDir, "transactions.ndjson"), results); err != nil {
		return err
	}
	summary := summarize(runManifest, *mode, rate, intervalMS, planned, startUTC, endUTC, results)
	if err := writeJSON(filepath.Join(*outDir, "summary.json"), summary); err != nil {
		return err
	}

	fmt.Printf("P2_BENCHMARK=%s mode=%s run_id=%s attempted=%d committed=%d unknown=%d\n",
		summary["status"], *mode, runID, summary["attempted_records"], summary["committed_records"], summary["unknown_records"])
	fmt.Printf("P2_RESULTS=%s\n", *outDir)
	if summary["status"] != "PASS" {
		return errors.New("benchmark completed with invalid schedule or terminal transaction outcomes; evidence retained")
	}
	return nil
}

func loadRecords(manifest map[string]any, planned int) ([]benchRecord, error) {
	if str(manifest, "schema_version") != "1.0" || str(manifest, "study_id") != studyID {
		return nil, errors.New("record manifest metadata mismatch")
	}
	raw, ok := manifest["records"].([]any)
	if !ok {
		return nil, errors.New("record manifest records missing")
	}
	if integer(manifest, "record_count") != len(raw) || len(raw) != planned {
		return nil, fmt.Errorf("record count=%d planned=%d", len(raw), planned)
	}
	seenTrial := map[string]bool{}
	seenSource := map[string]bool{}
	out := make([]benchRecord, 0, len(raw))
	for _, item := range raw {
		m, ok := item.(map[string]any)
		if !ok {
			return nil, errors.New("invalid record object")
		}
		r := benchRecord{
			TrialID: str(m, "trial_id"), SourceRecordID: str(m, "source_record_id"),
			SourceSystemID: str(m, "authenticated_source_system_id"), SourceType: str(m, "source_type"),
			Producer: str(m, "producer"), ProducedAt: str(m, "produced_at_utc"),
			SchemaVersion: str(m, "schema_version"), PayloadSHA256: strings.ToLower(str(m, "payload_sha256")),
		}
		if r.TrialID == "" || r.SourceRecordID == "" || r.SourceSystemID != "lorawan-gateway-evidence" {
			return nil, errors.New("record identity/source system incomplete")
		}
		if seenTrial[r.TrialID] || seenSource[r.SourceRecordID] {
			return nil, errors.New("duplicate trial/source identity")
		}
		seenTrial[r.TrialID] = true
		seenSource[r.SourceRecordID] = true
		payload, err := base64.StdEncoding.DecodeString(str(m, "exact_payload_base64"))
		if err != nil || len(payload) == 0 {
			return nil, fmt.Errorf("invalid exact payload for %s", r.SourceRecordID)
		}
		d := sha256.Sum256(payload)
		if hex.EncodeToString(d[:]) != r.PayloadSHA256 {
			return nil, fmt.Errorf("payload SHA-256 mismatch for %s", r.SourceRecordID)
		}
		r.Payload = payload
		out = append(out, r)
	}
	return out, nil
}

func executeOne(ledger *fabricadapter.GatewayClient, r benchRecord, mode, runID string, sequence int, offset time.Duration, scheduledUTC time.Time) benchResult {
	started := time.Now().UTC()
	v := map[string]any{
		"schema_version": "1.0", "study_id": studyID, "test_id": "P2", "run_id": runID,
		"trial_id": r.TrialID, "source_record_id": r.SourceRecordID, "payload_sha256": r.PayloadSHA256,
		"mode": mode, "sequence": sequence, "scheduled_offset_ms": float64(offset) / float64(time.Millisecond),
		"scheduled_at_utc":         scheduledUTC.Format(time.RFC3339Nano),
		"operation_started_at_utc": started.Format(time.RFC3339Nano),
		"queue_delay_ms":           float64(started.Sub(scheduledUTC)) / float64(time.Millisecond),
		"committed":                false, "unresolved": false,
	}
	opStart := time.Now()
	payload := append([]byte(nil), r.Payload...)
	digest := sha256.Sum256(payload)
	anchor := fabricadapter.FabricAnchor{
		AuthenticatedSourceSystemID: r.SourceSystemID, SourceRecordID: r.SourceRecordID,
		Digest: hex.EncodeToString(digest[:]), PayloadLength: len(payload), ExactPayload: payload,
		SourceType: r.SourceType, Producer: r.Producer, ProducedAt: r.ProducedAt, SchemaVersion: r.SchemaVersion,
	}
	if mode == "control" {
		finish := time.Now().UTC()
		v["operation_finished_at_utc"] = finish.Format(time.RFC3339Nano)
		v["client_operation_latency_ms"] = float64(time.Since(opStart)) / float64(time.Millisecond)
		v["normalized_status"] = "CONTROL_OK"
		return benchResult{Sequence: sequence, Values: v}
	}

	ctx, cancel := context.WithTimeout(context.Background(), 4*time.Minute)
	defer cancel()
	prepStart := time.Now().UTC()
	v["prepare_started_at_utc"] = prepStart.Format(time.RFC3339Nano)
	prepared, err := ledger.Prepare(ctx, anchor)
	prepEnd := time.Now().UTC()
	v["prepare_finished_at_utc"] = prepEnd.Format(time.RFC3339Nano)
	v["prepare_latency_ms"] = float64(prepEnd.Sub(prepStart)) / float64(time.Millisecond)
	if err != nil {
		v["raw_error_class"] = "PREPARE_ERROR"
		v["raw_error_message"] = err.Error()
		v["normalized_status"] = "REJECTED"
		v["operation_finished_at_utc"] = prepEnd.Format(time.RFC3339Nano)
		v["client_operation_latency_ms"] = float64(time.Since(opStart)) / float64(time.Millisecond)
		return benchResult{Sequence: sequence, Values: v}
	}
	v["tx_id"] = prepared.TransactionID
	v["create_outcome"] = prepared.CreateOutcome
	v["transaction_size_bytes"] = len(prepared.PreparedTransaction)
	subStart := time.Now().UTC()
	v["submit_started_at_utc"] = subStart.Format(time.RFC3339Nano)
	sr, err := ledger.SubmitPrepared(ctx, prepared)
	subEnd := time.Now().UTC()
	v["submit_finished_at_utc"] = subEnd.Format(time.RFC3339Nano)
	v["commit_observed_at_utc"] = subEnd.Format(time.RFC3339Nano)
	v["commit_latency_ms"] = float64(subEnd.Sub(subStart)) / float64(time.Millisecond)
	v["tx_id"] = sr.TransactionID
	v["committed"] = sr.Committed
	v["unresolved"] = sr.Unresolved
	if err != nil {
		v["raw_error_class"] = "SUBMIT_OR_COMMIT_ERROR"
		v["raw_error_message"] = err.Error()
		if sr.Unresolved {
			v["normalized_status"] = "UNKNOWN"
		} else {
			v["normalized_status"] = "REJECTED"
		}
	} else if sr.Committed {
		v["normalized_status"] = "COMMITTED"
	} else {
		v["normalized_status"] = "UNKNOWN"
		v["unresolved"] = true
	}
	finish := time.Now().UTC()
	v["operation_finished_at_utc"] = finish.Format(time.RFC3339Nano)
	v["client_operation_latency_ms"] = float64(time.Since(opStart)) / float64(time.Millisecond)
	return benchResult{Sequence: sequence, Values: v}
}

func summarize(run map[string]any, mode string, rate, intervalMS float64, planned int, start, end time.Time, rows []benchResult) map[string]any {
	committed, failed, unknown := 0, 0, 0
	maxQueue, clientSum, commitSum := 0.0, 0.0, 0.0
	commitN := 0
	for _, r := range rows {
		q := toFloat(r.Values["queue_delay_ms"])
		if q > maxQueue {
			maxQueue = q
		}
		clientSum += toFloat(r.Values["client_operation_latency_ms"])
		status, _ := r.Values["normalized_status"].(string)
		if c, _ := r.Values["committed"].(bool); c {
			committed++
		}
		if status == "REJECTED" {
			failed++
		}
		if status == "UNKNOWN" {
			unknown++
		}
		if v, ok := r.Values["commit_latency_ms"]; ok {
			commitSum += toFloat(v)
			commitN++
		}
	}
	// Anchor the measurement window to the frozen session duration, not the
	// rounded record count (which differs for shortened low-rate rehearsals).
	measurement := number(run, "duration_seconds")
	measurementEnd := start.Add(time.Duration(measurement * float64(time.Second)))
	status := "PASS"
	if len(rows) != planned || maxQueue > intervalMS {
		status = "FAIL"
	}
	if mode == "fabric" && (committed != planned || failed != 0 || unknown != 0) {
		status = "FAIL"
	}
	meanClient := 0.0
	if len(rows) > 0 {
		meanClient = clientSum / float64(len(rows))
	}
	meanCommit := 0.0
	if commitN > 0 {
		meanCommit = commitSum / float64(commitN)
	}
	formal, _ := run["formal"].(bool)
	return map[string]any{
		"schema_version": "1.0", "study_id": studyID, "test_id": "P2", "run_id": str(run, "run_id"),
		"mode": mode, "formal": formal, "target_tps": rate, "planned_records": planned,
		"attempted_records": len(rows), "committed_records": committed, "failed_records": failed, "unknown_records": unknown,
		"measurement_start_utc": start.Format(time.RFC3339Nano), "measurement_end_utc": measurementEnd.Format(time.RFC3339Nano),
		"measurement_seconds": measurement, "wall_end_utc_including_drain": end.Format(time.RFC3339Nano),
		"wall_seconds_including_drain": end.Sub(start).Seconds(),
		"achieved_attempt_tps": float64(len(rows)) / measurement, "achieved_commit_tps": float64(committed) / measurement,
		"max_queue_delay_ms": maxQueue, "mean_client_operation_latency_ms": meanClient,
		"mean_commit_latency_ms": meanCommit, "status": status,
	}
}

func readObject(path string) (map[string]any, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var v map[string]any
	if err = json.Unmarshal(b, &v); err != nil {
		return nil, err
	}
	return v, nil
}
func str(m map[string]any, k string) string         { v, _ := m[k].(string); return strings.TrimSpace(v) }
func obj(m map[string]any, k string) map[string]any { v, _ := m[k].(map[string]any); return v }
func number(m map[string]any, k string) float64     { return toFloat(m[k]) }
func integer(m map[string]any, k string) int        { return int(toFloat(m[k])) }
func toFloat(v any) float64 {
	if x, ok := v.(float64); ok {
		return x
	}
	return 0
}
func writeJSON(path string, v any) error {
	b, e := json.MarshalIndent(v, "", "  ")
	if e != nil {
		return e
	}
	b = append(b, 10)
	return os.WriteFile(path, b, 0640)
}
func writeNDJSON(path string, rows []benchResult) error {
	f, e := os.OpenFile(path, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0640)
	if e != nil {
		return e
	}
	defer f.Close()
	enc := json.NewEncoder(f)
	for _, r := range rows {
		if e = enc.Encode(r.Values); e != nil {
			return e
		}
	}
	return nil
}
