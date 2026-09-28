#!/usr/bin/env python3
"""Run a sealed P2 session through the production-path benchmark binary.

Control-only mode is safe to commission before the Fabric side is ready.
Full mode executes each pair in its pre-registered order and is reserved for a
synchronized rehearsal/formal run after Fabric readiness has been confirmed.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import math
import importlib.util
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "test" / "automation" / "research_contract.py"
DEFAULT_BINARY = ROOT / "evidence-services" / "cloud" / ".dev-out" / "research-fabric-benchmark.exe"

def load_contract():
    spec = importlib.util.spec_from_file_location("research_contract", CONTRACT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import research contract")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

RC = load_contract()
RC.validate_static_contract()

def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def verify_json_sidecar(path: Path) -> str:
    sidecar = path.with_suffix(path.suffix + ".sha256")
    if not sidecar.is_file():
        raise RuntimeError(f"missing SHA-256 sidecar: {sidecar}")
    expected = sidecar.read_text(encoding="ascii").strip().lower()
    actual = hashlib.sha256(canonical(load_json(path))).hexdigest()
    if actual != expected:
        raise RuntimeError(f"SHA-256 mismatch: {path}")
    return actual

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)

def validate_session_pairs(session: dict[str, Any]) -> None:
    pairs = session.get("pairs")
    if not isinstance(pairs, list) or not pairs:
        raise RuntimeError("P2 session contains no pairs")
    seconds = int(session.get("seconds") or 0)
    repetitions = int(session.get("repetitions") or 0)
    if seconds <= 0 or repetitions <= 0:
        raise RuntimeError("P2 seconds/repetitions must be positive")
    if bool(session.get("formal")) and (seconds != RC.FORMAL["P2"]["duration_seconds"]
        or repetitions != RC.FORMAL["P2"]["repetitions"]):
        raise RuntimeError("formal P2 duration/repetition drift")
    expected_pairs = len(RC.FORMAL["P2"]["rates_tps"]) * repetitions
    if len(pairs) != expected_pairs:
        raise RuntimeError(f"P2 pair count {len(pairs)} != {expected_pairs}")
    seen_ids: set[str] = set()
    seen_workloads: set[tuple[float, int]] = set()
    for pair in pairs:
        pid = str(pair.get("pair_id") or "")
        rate = float(pair.get("rate_tps") or 0)
        rep = int(pair.get("repetition") or 0)
        planned = int(pair.get("planned_record_count") or 0)
        if not pid or pid in seen_ids:
            raise RuntimeError("P2 missing/duplicate pair_id")
        seen_ids.add(pid)
        if rate not in RC.FORMAL["P2"]["rates_tps"] or rep not in range(1, repetitions + 1):
            raise RuntimeError(f"{pid}: invalid rate/repetition")
        if (rate, rep) in seen_workloads:
            raise RuntimeError(f"{pid}: duplicate rate/repetition")
        seen_workloads.add((rate, rep))
        if planned != max(1, RC.p2_planned_records(rate, seconds)):
            raise RuntimeError(f"{pid}: rate/duration/planned count mismatch")
        order = tuple(str(x).lower() for x in pair.get("pair_order", ()))
        expected_order = tuple(x.lower() for x in RC.P2_PAIR_ORDER[rep]) if session.get("formal") else (
            ("control", "fabric") if rep % 2 else ("fabric", "control")
        )
        if order != expected_order:
            raise RuntimeError(f"{pid}: pair order mismatch")
    if bool(session.get("formal")) and sum(int(p["planned_record_count"]) for p in pairs) != RC.FORMAL["P2"]["planned_with_fabric_records"]:
        raise RuntimeError("formal P2 total planned record count drift")


def validate_pair_manifests(
    pair: dict[str, Any], run: dict[str, Any], records: dict[str, Any],
    run_hash: str, record_hash: str, seconds: int, *, formal: bool | None = None,
) -> None:
    pid = str(pair["pair_id"])
    workload = run.get("workload") or {}
    planned = int(pair["planned_record_count"])
    if run.get("test_id") != "P2" or run.get("run_id") != pid or int(run.get("duration_seconds") or 0) != seconds:
        raise RuntimeError(f"{pid}: run manifest identity/duration mismatch")
    rate = float(pair["rate_tps"])
    if float(workload.get("target_tps") or 0) != rate or int(workload.get("planned_record_count") or 0) != planned:
        raise RuntimeError(f"{pid}: run workload mismatch")
    if abs(float(workload.get("interval_ms") or 0) - 1000.0 / rate) > 1e-5:
        raise RuntimeError(f"{pid}: interval_ms inconsistent with frozen target rate")
    if int(run.get("repetition") or 0) != int(pair["repetition"]) or tuple(workload.get("pair_order") or ()) != tuple(pair["pair_order"]):
        raise RuntimeError(f"{pid}: run repetition/order mismatch")
    if type(run.get("formal")) is not bool:
        raise RuntimeError(f"{pid}: run formal/rehearsal identity missing")
    if formal is not None and run["formal"] is not formal:
        raise RuntimeError(f"{pid}: session/run formal/rehearsal identity mismatch")
    if pair.get("run_manifest_sha256") != run_hash or pair.get("record_manifest_sha256") != record_hash or records.get("run_manifest_sha256") != run_hash:
        raise RuntimeError(f"{pid}: session/run/record digest join mismatch")
    rows = records.get("records")
    if int(records.get("record_count") or 0) != planned or not isinstance(rows, list) or len(rows) != planned:
        raise RuntimeError(f"{pid}: record manifest count mismatch")
    ids = [str(row.get("source_record_id") or "") for row in rows]
    if not all(ids) or len(ids) != len(set(ids)):
        raise RuntimeError(f"{pid}: record IDs missing/duplicated")
    for row in rows:
        try:
            payload = base64.b64decode(row["exact_payload_base64"], validate=True)
        except (KeyError, ValueError) as exc:
            raise RuntimeError(f"{pid}: invalid exact record payload") from exc
        if not payload or hashlib.sha256(payload).hexdigest() != row.get("payload_sha256"):
            raise RuntimeError(f"{pid}: exact payload SHA-256 mismatch")
        if row.get("authenticated_source_system_id") != "lorawan-gateway-evidence":
            raise RuntimeError(f"{pid}: record source identity mismatch")


def parse_utc(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be UTC")
    return parsed


def validate_summary(summary: dict[str, Any], phase: str, planned: int,
                     *, run: dict[str, Any]) -> None:
    if summary.get("status") != "PASS":
        raise RuntimeError(f"{phase} benchmark summary status={summary.get('status')}")
    if (
        summary.get("schema_version") != "1.0"
        or summary.get("study_id") != "zacharias-lorawan-fabric"
        or summary.get("test_id") != "P2"
        or summary.get("mode") != phase
        or summary.get("run_id") != run.get("run_id")
        or type(summary.get("formal")) is not bool
        or summary["formal"] is not run.get("formal")
    ):
        raise RuntimeError(f"{phase} summary test/mode/run/formal identity mismatch")
    expected_rate = float(run["workload"]["target_tps"])
    expected_seconds = float(run["duration_seconds"])
    if abs(float(summary.get("target_tps") or 0) - expected_rate) > 1e-9:
        raise RuntimeError(f"{phase} benchmark target rate mismatch")
    if abs(float(summary.get("measurement_seconds") or 0) - expected_seconds) > 1e-6:
        raise RuntimeError(f"{phase} benchmark measurement duration mismatch")
    start = parse_utc(summary.get("measurement_start_utc"))
    end = parse_utc(summary.get("measurement_end_utc"))
    drain_end = parse_utc(summary.get("wall_end_utc_including_drain"))
    if abs((end - start).total_seconds() - expected_seconds) > 1e-6 or drain_end < end:
        raise RuntimeError(f"{phase} benchmark measurement window/drain mismatch")
    if abs(float(summary.get("wall_seconds_including_drain", -1)) - (drain_end - start).total_seconds()) > 0.01:
        raise RuntimeError(f"{phase} wall duration/drain timestamp mismatch")
    for field in ("max_queue_delay_ms", "mean_client_operation_latency_ms", "mean_commit_latency_ms",
                  "achieved_attempt_tps", "achieved_commit_tps"):
        if field not in summary or not math.isfinite(float(summary[field])) or float(summary[field]) < 0:
            raise RuntimeError(f"{phase} missing/invalid performance measurement {field}")
    if float(summary["max_queue_delay_ms"]) > float(run["workload"]["interval_ms"]):
        raise RuntimeError(f"{phase} benchmark queue exceeded intended interval")
    if int(summary.get("planned_records") or -1) != planned:
        raise RuntimeError(f"{phase} planned_records mismatch")
    if int(summary.get("attempted_records") or -1) != planned:
        raise RuntimeError(f"{phase} attempted_records mismatch")
    committed = int(summary.get("committed_records", -1))
    if committed != (planned if phase == "fabric" else 0):
        raise RuntimeError(f"{phase} committed_records mismatch")
    if int(summary.get("failed_records", -1)) != 0 or int(summary.get("unknown_records", -1)) != 0:
        raise RuntimeError(f"{phase} failed/unknown records must be zero")
    if abs(float(summary["achieved_attempt_tps"]) - planned / expected_seconds) > 1e-6:
        raise RuntimeError(f"{phase} achieved_attempt_tps inconsistent with attempts/window")
    if abs(float(summary["achieved_commit_tps"]) - committed / expected_seconds) > 1e-6:
        raise RuntimeError(f"{phase} achieved_commit_tps inconsistent with commits/window")

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--session-dir", required=True)
    ap.add_argument("--benchmark-binary", default=str(DEFAULT_BINARY))
    ap.add_argument("--scope", choices=("control-only", "full"), default="control-only")
    ap.add_argument("--max-inflight", type=int, default=512)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--rehearsal-gap-seconds", type=int, default=0)
    args = ap.parse_args()

    session_dir = Path(args.session_dir).resolve()
    binary = Path(args.benchmark_binary).resolve()
    if not binary.is_file():
        raise RuntimeError(f"P2 benchmark binary missing: {binary}")
    session_path = session_dir / "p2-session.json"
    session_hash = verify_json_sidecar(session_path)
    session = load_json(session_path)
    if session.get("test_id") != "P2":
        raise RuntimeError("session is not P2")
    formal = bool(session.get("formal"))
    pairs = session.get("pairs")
    validate_session_pairs(session)

    if formal:
        if int(session.get("seconds") or 0) != RC.FORMAL["P2"]["duration_seconds"]:
            raise RuntimeError("formal P2 duration drift")
        if int(session.get("repetitions") or 0) != RC.FORMAL["P2"]["repetitions"]:
            raise RuntimeError("formal P2 repetition drift")
        gap_seconds = int(RC.FORMAL["P2"]["stable_between_runs_seconds"])
    else:
        if args.rehearsal_gap_seconds < 0:
            raise RuntimeError("--rehearsal-gap-seconds must be >= 0")
        gap_seconds = args.rehearsal_gap_seconds

    if args.scope == "full" and formal:
        # Formal full execution is allowed only when explicitly invoked after the
        # synchronized readiness handshake; the caller controls that release.
        pass

    result: dict[str, Any] = {
        "test": "P2",
        "session_id": session.get("session_id"),
        "formal": formal,
        "scope": args.scope,
        "session_sha256": session_hash,
        "started_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "runs": [],
        "status": "FAIL",
        "errors": [],
    }

    first_run = True
    try:
        for pair in pairs:
            pair_id = str(pair.get("pair_id") or "")
            if not pair_id:
                raise RuntimeError("P2 pair missing pair_id")
            pair_dir = session_dir / pair_id
            run_manifest = pair_dir / "run-manifest.json"
            record_manifest = pair_dir / "record-manifest.json"
            run_hash = verify_json_sidecar(run_manifest)
            record_hash = verify_json_sidecar(record_manifest)
            run_metadata = load_json(run_manifest)
            record_metadata = load_json(record_manifest)
            validate_pair_manifests(pair, run_metadata, record_metadata, run_hash, record_hash,
                                    int(session["seconds"]), formal=formal)
            planned = int(pair.get("planned_record_count") or 0)
            if planned <= 0:
                raise RuntimeError(f"{pair_id}: invalid planned count")

            order = tuple(str(x).lower() for x in (pair.get("pair_order") or ()))
            if formal:
                rep = int(pair.get("repetition") or 0)
                expected = tuple(x.lower() for x in RC.P2_PAIR_ORDER[rep])
                if order != expected:
                    raise RuntimeError(f"{pair_id}: pair order drift {order} != {expected}")
            phases = ("control",) if args.scope == "control-only" else order
            if args.scope == "full" and set(phases) != {"control", "fabric"}:
                raise RuntimeError(f"{pair_id}: full scope requires one control and one fabric phase")

            for phase in phases:
                if not first_run and gap_seconds:
                    print(f"P2_STABILITY_GAP seconds={gap_seconds}", flush=True)
                    time.sleep(gap_seconds)
                first_run = False

                out_dir = pair_dir / f"benchmark-{phase}"
                summary_path = out_dir / "summary.json"
                if args.resume and summary_path.is_file():
                    summary = load_json(summary_path)
                    validate_summary(summary, phase, planned, run=run_metadata)
                    result["runs"].append({
                        "pair_id": pair_id, "phase": phase, "status": "PASS",
                        "planned_records": planned, "resumed": True,
                        "summary": str(summary_path),
                    })
                    print(f"P2_PHASE_SKIPPED pair={pair_id} phase={phase} reason=existing-pass")
                    continue
                if out_dir.exists() and any(out_dir.iterdir()):
                    raise RuntimeError(f"refusing to overwrite existing evidence: {out_dir}")
                out_dir.mkdir(parents=True, exist_ok=True)

                cmd = [
                    str(binary),
                    "--mode", phase,
                    "--run-manifest", str(run_manifest),
                    "--record-manifest", str(record_manifest),
                    "--output-dir", str(out_dir),
                    "--max-inflight", str(args.max_inflight),
                ]
                print(f"P2_PHASE_BEGIN pair={pair_id} phase={phase} planned={planned}", flush=True)
                began = time.monotonic()
                cp = subprocess.run(
                    cmd, cwd=ROOT, text=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=max(900, int(session.get("seconds") or 0) + 600),
                    check=False,
                )
                elapsed = time.monotonic() - began
                (out_dir / "runner.stdout.log").write_text(cp.stdout or "", encoding="utf-8")
                (out_dir / "runner.stderr.log").write_text(cp.stderr or "", encoding="utf-8")
                if cp.returncode != 0:
                    raise RuntimeError(
                        f"{pair_id}/{phase}: benchmark rc={cp.returncode}: "
                        + "\n".join(((cp.stdout or "") + (cp.stderr or "")).splitlines()[-8:])
                    )
                if not summary_path.is_file():
                    raise RuntimeError(f"{pair_id}/{phase}: summary.json missing")
                summary = load_json(summary_path)
                validate_summary(summary, phase, planned, run=run_metadata)
                result["runs"].append({
                    "pair_id": pair_id, "phase": phase, "status": "PASS",
                    "planned_records": planned, "elapsed_wall_seconds": elapsed,
                    "resumed": False, "summary": str(summary_path),
                })
                print(f"P2_PHASE_END pair={pair_id} phase={phase} status=PASS", flush=True)

        result["status"] = "PASS"
    except Exception as exc:
        result["errors"].append(str(exc))
    finally:
        result["finished_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        write_json(session_dir / f"pair-runner-{args.scope}.json", result)

    print(f"P2_PAIR_RUNNER={result['status']} scope={args.scope} runs={len(result['runs'])}")
    if result["errors"]:
        for err in result["errors"]:
            print("ERROR=" + err, file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        raise SystemExit(1)
