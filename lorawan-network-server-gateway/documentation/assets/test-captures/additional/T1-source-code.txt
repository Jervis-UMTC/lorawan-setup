#!/usr/bin/env python3
"""Fail-closed Chapter 3 T1/T2 traceability orchestrator.

T1 collects fresh legitimate EMU-01 readings, waits for terminal Fabric
confirmation, then independently re-retrieves each selected record through the
restricted DB interface and scores required-field completeness and DB/Fabric
linkage.

T2 does the same for non-overlapping five-reading histories and additionally
scores sequence/frame-counter chronology.

Commissioning mode uses smaller samples but the same retrieval/scoring path and
is never counted research.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "test" / "automation" / "research_contract.py"
RECORDER = ROOT / "test" / "automation" / "research-recorder" / "research_recorder.py"
SUMMARY = ROOT / "test" / "automation" / "research-recorder" / "summarize-study.py"
RESULTS = ROOT / "chapter4-results" / "traceability"
DEV_EUI = "ac1f09fffe296d29"
HEX64 = re.compile(r"^[0-9a-f]{64}$", re.I)
EXPECTED_SENSOR_METRICS = frozenset({
    "soil_moisture_percent", "soil_temperature_c", "uv_index",
    "barometer_pressure_pa", "barometer_temperature_c",
    "light_veml7700_lux", "light_opt3001_lux",
    "environment_temperature_c", "environment_humidity_percent",
    "environment_pressure_pa", "environment_gas_resistance_ohm",
    "rain_wet", "battery_v",
})


def load_recorder_module():
    spec = importlib.util.spec_from_file_location("research_recorder_module", RECORDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not import research recorder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RR = load_recorder_module()


def load_contract_module():
    spec = importlib.util.spec_from_file_location("research_contract", CONTRACT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not import research contract")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RC = load_contract_module()


def parse_dt(value: str) -> datetime:
    text = (value or "").strip().replace(" ", "T", 1).replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def parse_csv_text(text: str) -> list[dict[str, str]]:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    return list(csv.DictReader(io.StringIO("\n".join(lines))))


def source_sequences(path: Path) -> set[int]:
    values: set[int] = set()
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "|SENSOR_TX," not in line:
            continue
        match = re.search(r"(?:^|,)seq=(\d+)(?:,|$)", line.split("|SENSOR_TX,", 1)[1])
        if match:
            values.add(int(match.group(1)))
    return values


def choose_db_reader() -> str:
    roles: dict[str, str] = {}
    for node in ("ulc01", "ulc02", "ulc03"):
        cp = RR.run_remote(node, "db-role", check=False)
        role = (cp.stdout or "").strip().splitlines()[-1:] or [""]
        roles[node] = role[0].strip()
    for node in ("ulc01", "ulc02", "ulc03"):
        if roles.get(node) == "leader":
            return node
    raise RuntimeError(f"no readable PostgreSQL leader found: {roles}")


def remote_export(node: str, table: str, start: datetime, end: datetime) -> list[dict[str, str]]:
    command = f"db-export {table} {iso_z(start)} {iso_z(end)} {DEV_EUI}"
    cp = RR.run_remote(node, command, check=True)
    return parse_csv_text(cp.stdout or "")


def retrieval_bundle(node: str, start: datetime, end: datetime) -> tuple[dict[str, list[dict[str, str]]], float]:
    began = time.perf_counter()
    bundle = {
        "uplinks": remote_export(node, "uplinks", start, end),
        "measurements": remote_export(node, "measurements", start, end),
        "outbox": remote_export(node, "outbox", start, end),
    }
    return bundle, time.perf_counter() - began


def index_by(rows: list[dict[str, str]], key: str) -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        out.setdefault(row.get(key, ""), []).append(row)
    return out


def score_record(row: dict[str, str], measurements: list[dict[str, str]], outbox: list[dict[str, str]],
                 source_seq: set[int]) -> tuple[bool, list[str], dict[str, object]]:
    errors: list[str] = []
    event_key = row.get("event_key", "")
    seq_text = row.get("test_sequence", "")
    try:
        seq = int(seq_text)
    except ValueError:
        seq = -1
        errors.append("test_sequence missing/non-integer")
    if seq not in source_seq:
        errors.append("matching SENSOR_TX source sequence missing")
    required_uplink = ("event_key", "time", "dev_eui", "gateway_id", "f_cnt", "test_sequence")
    for field in required_uplink:
        if not (row.get(field) or "").strip():
            errors.append(f"uplink field missing:{field}")
    if (row.get("dev_eui") or "").lower() != DEV_EUI:
        errors.append("unexpected DevEUI")
    if len(measurements) != len(EXPECTED_SENSOR_METRICS):
        errors.append(f"measurement count={len(measurements)} expected={len(EXPECTED_SENSOR_METRICS)}")
    names = [m.get("metric_name", "") for m in measurements]
    if len(names) != len(set(names)):
        errors.append("duplicate measurement metric names")
    if set(names) != EXPECTED_SENSOR_METRICS:
        errors.append(f"required sensor metrics missing={sorted(EXPECTED_SENSOR_METRICS - set(names))} unexpected={sorted(set(names) - EXPECTED_SENSOR_METRICS)}")
    known_unavailable: list[str] = []
    for measurement in measurements:
        name = measurement.get("metric_name", "")
        if not name.strip():
            errors.append("measurement metric_name missing")
        if not (measurement.get("unit") or "").strip():
            errors.append(f"measurement unit missing:{name or '?'}")
        has_value = any((measurement.get(field) or "").strip()
                        for field in ("metric_value", "metric_text", "metric_bool"))
        if not has_value:
            # USB-powered EMU-01 reports battery_mv=0; the decoder retains
            # battery_v=NULL, quality=invalid. This is traceably unavailable,
            # NOT a measured 0 V battery. Other missing sensor values still fail.
            if (name == "battery_v"
                    and measurement.get("unit") == "V"
                    and measurement.get("quality") == "invalid"
                    and measurement.get("source_field") == "battery_v"):
                known_unavailable.append(name)
            else:
                errors.append(f"measurement value missing:{name or '?'}")
    if len(outbox) != 1:
        errors.append(f"outbox rows={len(outbox)} expected=1")
        fabric = outbox[0] if outbox else {}
    else:
        fabric = outbox[0]
    if fabric:
        if fabric.get("source_event_key") != event_key:
            errors.append("DB/Fabric source_event_key mismatch")
        if (fabric.get("status") or "").lower() != "confirmed":
            errors.append(f"Fabric status={fabric.get('status','')}")
        digest = (fabric.get("digest_sha256") or "").strip()
        if not HEX64.fullmatch(digest):
            errors.append("Fabric SHA-256 missing/invalid")
        txid = (fabric.get("fabric_tx_id") or "").strip()
        if not HEX64.fullmatch(txid):
            errors.append("Fabric transaction ID missing/invalid")
        if not (fabric.get("committed_at") or "").strip():
            errors.append("Fabric commit timestamp missing")
    fabric_linked = bool(fabric) and (
        fabric.get("source_event_key") == event_key
        and (fabric.get("status") or "").lower() == "confirmed"
        and bool(HEX64.fullmatch((fabric.get("digest_sha256") or "").strip()))
        and bool(HEX64.fullmatch((fabric.get("fabric_tx_id") or "").strip()))
        and bool((fabric.get("committed_at") or "").strip())
    )
    detail = {
        "trace_id": event_key,
        "dev_eui": row.get("dev_eui", ""),
        "frame_counter": row.get("f_cnt", ""),
        "test_sequence": seq_text,
        "event_timestamp": row.get("time", ""),
        "gateway_identifier": row.get("gateway_id", ""),
        "database_record_identifier": event_key,
        "measurement_count": len(measurements),
        "known_unavailable_measurements": sorted(known_unavailable),
        "measurement_values_available_count": sum(
            any((m.get(field) or "").strip() for field in
                ("metric_value", "metric_text", "metric_bool"))
            for m in measurements
        ),
        "sensor_measurements": [
            {
                "type": m.get("metric_name", ""),
                "value": next(
                    (m.get(field) for field in ("metric_value", "metric_text", "metric_bool")
                     if (m.get(field) or "").strip()), None
                ),
                "unit": m.get("unit", ""),
                "quality": m.get("quality", ""),
            }
            for m in measurements
        ],
        "sha256": fabric.get("digest_sha256", "") if fabric else "",
        "fabric_transaction_id": fabric.get("fabric_tx_id", "") if fabric else "",
        "fabric_commit_timestamp": fabric.get("committed_at", "") if fabric else "",
        "fabric_linked": fabric_linked,
        "complete": not errors,
    }
    return not errors, errors, detail


def select_rows(run_dir: Path) -> tuple[list[dict[str, str]], dict[str, list[dict[str, str]]],
                                         dict[str, list[dict[str, str]]], set[int]]:
    uplinks = read_csv(run_dir / "raw" / "uplinks.csv")
    measurements = index_by(read_csv(run_dir / "raw" / "measurements.csv"), "event_key")
    outbox = index_by(read_csv(run_dir / "raw" / "fabric-outbox.csv"), "source_event_key")
    source = source_sequences(run_dir / "raw" / "emu-01-source.log")
    uplinks.sort(key=lambda row: (parse_dt(row["time"]), int(row.get("f_cnt") or 0)))
    return uplinks, measurements, outbox, source


def run_recorder(test_id: str, rehearsal: bool, duration: int, stamp: str) -> Path:
    mode = "rehearsal" if rehearsal else "formal"
    run_id = f"{test_id}-{mode}-{stamp}"
    expected = (
        "fresh legitimate readings are completely retrievable with correct DB/Fabric linkage"
        if test_id == "T1"
        else "fresh five-reading histories are completely retrievable, linked, and chronologically correct"
    )
    command = [
        sys.executable, str(RECORDER), "run",
        "--group", "traceability",
        "--run-id", run_id,
        "--condition", f"{test_id} {'non-counted commissioning' if rehearsal else 'formal traceability'}",
        "--expected", expected,
        "--scope", "full",
        "--duration-seconds", str(duration),
        "--fabric-settle-seconds", "420",
    ]
    cp = subprocess.run(command, cwd=ROOT)
    if cp.returncode != 0:
        raise RuntimeError(f"recorder failed for {run_id} returncode={cp.returncode}")
    return RESULTS / run_id


def t1_score(run_dir: Path, required: int, node: str) -> dict[str, object]:
    uplinks, measurements, outbox, source = select_rows(run_dir)
    if len(uplinks) < required:
        raise RuntimeError(f"T1 only {len(uplinks)} stored readings; need {required}")
    selected = uplinks[:required]
    keys = [row.get("event_key", "") for row in selected]
    if not all(keys) or len(set(keys)) != required:
        raise RuntimeError("T1 selected readings contain missing/duplicated event keys")
    try:
        sensor_seqs = [int(row["test_sequence"]) for row in selected]
    except (ValueError, KeyError) as exc:
        raise RuntimeError("T1 selected readings lack valid source sequence numbers") from exc
    if len(set(sensor_seqs)) != required:
        raise RuntimeError("T1 selected readings reuse source sequence numbers")
    trials: list[dict[str, object]] = []
    for index, row in enumerate(selected, 1):
        at = parse_dt(row["time"])
        bundle, retrieval = retrieval_bundle(node, at, at + timedelta(milliseconds=1))
        live_uplink = [x for x in bundle["uplinks"] if x.get("event_key") == row.get("event_key")]
        live_measurements = [x for x in bundle["measurements"] if x.get("event_key") == row.get("event_key")]
        live_outbox = [x for x in bundle["outbox"] if x.get("source_event_key") == row.get("event_key")]
        if len(live_uplink) != 1:
            ok = False
            errors = [f"live DB retrieval uplink rows={len(live_uplink)} expected=1"]
            detail = {"trace_id": row.get("event_key", "")}
        else:
            ok, errors, detail = score_record(live_uplink[0], live_measurements, live_outbox, source)
        trials.append({
            "trial": index,
            "status": "PASS" if ok else "FAIL",
            "retrieval_time_seconds": retrieval,
            "errors": errors,
            "record": detail,
        })
    passed = sum(t["status"] == "PASS" for t in trials)
    complete_records = sum(bool(t.get("record", {}).get("complete")) for t in trials)
    linked_records = sum(bool(t.get("record", {}).get("fabric_linked")) for t in trials)
    return {
        "test": "T1",
        "required_trials": required,
        "records_expected": required,
        "records_complete": complete_records,
        "records_fabric_linked": linked_records,
        "known_unavailable_measurement_count": sum(
            len(t.get("record", {}).get("known_unavailable_measurements", []))
            for t in trials
        ),
        "trials": trials,
        "trace_retrieval_success_rate_percent": 100.0 * passed / required,
        "record_completeness_rate_percent": 100.0 * complete_records / required,
        "database_blockchain_linkage_rate_percent": 100.0 * linked_records / required,
        "missing_record_count": sum(bool(t["errors"]) for t in trials),
        "duplicate_record_count": 0,
        "status": "PASS" if passed == required else "FAIL",
    }


def t2_score(run_dir: Path, groups_required: int, node: str) -> dict[str, object]:
    uplinks, measurements, outbox, source = select_rows(run_dir)
    need = groups_required * 5
    if len(uplinks) < need:
        raise RuntimeError(f"T2 only {len(uplinks)} stored readings; need {need}")
    selected = uplinks[:need]
    selected_keys = [row.get("event_key", "") for row in selected]
    if len(set(selected_keys)) != need:
        raise RuntimeError("T2 selected history contains duplicate event keys; sequences would overlap")
    groups: list[dict[str, object]] = []
    for group_index in range(groups_required):
        expected = selected[group_index * 5:(group_index + 1) * 5]
        start = parse_dt(expected[0]["time"])
        end = parse_dt(expected[-1]["time"]) + timedelta(milliseconds=1)
        bundle, retrieval = retrieval_bundle(node, start, end)
        expected_keys = [r["event_key"] for r in expected]
        rows = [r for r in bundle["uplinks"] if r.get("event_key") in expected_keys]
        rows.sort(key=lambda r: parse_dt(r["time"]))
        errors: list[str] = []
        if len(rows) != 5:
            errors.append(f"retrieved uplinks={len(rows)} expected=5")
        if [r.get("event_key") for r in rows] != expected_keys:
            errors.append("retrieved event order does not match expected five-reading history")
        seqs: list[int] = []
        fcnts: list[int] = []
        details: list[dict[str, object]] = []
        for row in rows:
            try:
                seqs.append(int(row.get("test_sequence") or "-1"))
                fcnts.append(int(row.get("f_cnt") or "-1"))
            except ValueError:
                errors.append("non-integer test_sequence/frame counter")
            ms = [x for x in bundle["measurements"] if x.get("event_key") == row.get("event_key")]
            os = [x for x in bundle["outbox"] if x.get("source_event_key") == row.get("event_key")]
            ok, record_errors, detail = score_record(row, ms, os, source)
            details.append(detail)
            if not ok:
                errors.extend([f"{row.get('event_key','?')}:{x}" for x in record_errors])
        if len(seqs) == 5 and any(b != a + 1 for a, b in zip(seqs, seqs[1:])):
            errors.append(f"test_sequence not consecutive:{seqs}")
        if len(fcnts) == 5 and any(b <= a for a, b in zip(fcnts, fcnts[1:])):
            errors.append(f"frame counters not strictly increasing:{fcnts}")
        chronology_ok = (
            len(rows) == 5
            and [r.get("event_key") for r in rows] == expected_keys
            and len(seqs) == 5 and all(b == a + 1 for a, b in zip(seqs, seqs[1:]))
            and len(fcnts) == 5 and all(b > a for a, b in zip(fcnts, fcnts[1:]))
        )
        groups.append({
            "sequence": group_index + 1,
            "status": "PASS" if not errors else "FAIL",
            "reconstruction_time_seconds": retrieval,
            "expected_event_keys": expected_keys,
            "test_sequences": seqs,
            "frame_counters": fcnts,
            "missing_records": max(0, 5 - len(rows)),
            "duplicate_records": max(0, len(rows) - len(set(r.get("event_key") for r in rows))),
            "chronological_order_correct": chronology_ok,
            "errors": errors,
            "records": details,
        })
    passed = sum(g["status"] == "PASS" for g in groups)
    all_records = [record for group in groups for record in group.get("records", [])]
    complete_records = sum(bool(record.get("complete")) for record in all_records)
    linked_records = sum(bool(record.get("fabric_linked")) for record in all_records)
    return {
        "test": "T2",
        "required_sequences": groups_required,
        "records_expected": need,
        "records_complete": complete_records,
        "records_fabric_linked": linked_records,
        "known_unavailable_measurement_count": sum(
            len(record.get("known_unavailable_measurements", []))
            for record in all_records
        ),
        "sequences": groups,
        "trace_retrieval_success_rate_percent": 100.0 * passed / groups_required,
        "record_completeness_rate_percent": 100.0 * complete_records / need,
        "database_blockchain_linkage_rate_percent": 100.0 * linked_records / need,
        "chronological_order_accuracy_percent": 100.0 * sum(g["chronological_order_correct"] for g in groups) / groups_required,
        "missing_record_count": sum(int(g["missing_records"]) for g in groups),
        "duplicate_record_count": sum(int(g["duplicate_records"]) for g in groups),
        "status": "PASS" if passed == groups_required else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("test", choices=("T1", "T2"))
    parser.add_argument("--rehearsal-seconds", type=int, default=0,
                        help="non-counted commissioning duration; 0 selects the formal sample size")
    args = parser.parse_args()
    rehearsal = args.rehearsal_seconds > 0
    if args.rehearsal_seconds < 0:
        raise RuntimeError("rehearsal-seconds must be >=0")
    if rehearsal:
        duration = args.rehearsal_seconds
        required = 2 if args.test == "T1" else 1
    else:
        duration = 180 if args.test == "T1" else 810
        required = 10
    RC.validate_static_contract()
    RC.validate_trace_profile(args.test, required, not rehearsal)
    if rehearsal and args.test == "T1" and duration < 45:
        raise RuntimeError("T1 commissioning needs at least 45 seconds")
    if rehearsal and args.test == "T2" and duration < 90:
        raise RuntimeError("T2 commissioning needs at least 90 seconds")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = run_recorder(args.test, rehearsal, duration, stamp)
    node = choose_db_reader()
    result = t1_score(run_dir, required, node) if args.test == "T1" else t2_score(run_dir, required, node)
    result.update({
        "formal": not rehearsal,
        "db_reader_node": node,
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "sealed_evidence_manifest": str(run_dir / "metadata" / "SHA256SUMS.csv"),
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    })
    session_dir = RESULTS / "_sessions"
    session_dir.mkdir(parents=True, exist_ok=True)
    out = session_dir / f"{args.test}-{stamp}.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, str(SUMMARY)], cwd=ROOT, check=False)
    print(f"TRACEABILITY_HARNESS={result['status']} test={args.test} formal={not rehearsal}")
    print(f"RUN_DIR={run_dir}")
    print(f"SESSION_RESULT={out}")
    if result["status"] != "PASS":
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        raise SystemExit(1)
