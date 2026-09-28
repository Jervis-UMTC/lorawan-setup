#!/usr/bin/env python3
"""Fail-closed operator entry point for the Chapter 3 research test manual.

Status meanings are deliberately strict:
- READY: the one-block command can execute the complete formal action.
- CAPTURE_READY: capture/tooling is proven, but the complete action harness is not.
- HARNESS_REQUIRED: a controlled research fixture/orchestrator is still required.
- METHODOLOGY_REQUIRED: Chapter 3 does not define enough method to implement safely.

Only READY tests can be started as counted tests from this wrapper. Other statuses
exit cleanly after validation so an incomplete experiment can never be mistaken
for a valid counted run.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

AUTOMATION_DIR = Path(__file__).resolve().parents[1]
if str(AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(AUTOMATION_DIR))
from research_contract import FABRIC_OPTIONAL, FABRIC_REQUIRED, FORMAL, validate_static_contract

TEST_IDS = ("PRE","P1","P2","R1","R2","A1","A2","S1","S2","F1","F2","I1","I2","I3","T1","T2")
ROOT = Path(__file__).resolve().parents[3]
RECORDER = ROOT / "test" / "automation" / "research-recorder" / "research_recorder.py"
ENSURE_READY = ROOT / "test" / "automation" / "research-manual" / "ensure_ready.py"
STUDY_SUMMARY = ROOT / "test" / "automation" / "research-recorder" / "summarize-study.py"
CONN_FLOOD = ROOT / "test" / "automation" / "load-tools" / "connection_flood.py"
MSG_FLOOD = ROOT / "test" / "automation" / "load-tools" / "invalid_message_stream.py"
MQTT_WIRE = ROOT / "test" / "automation" / "load-tools" / "mqtt_wire.py"
MQTT_PUBLISH = ROOT / "test" / "automation" / "load-tools" / "mqtt_publish_stream.py"
NODERED_FLOOD = ROOT / "test" / "automation" / "node-red-flood-test" / "node_red_flood_branch.py"
FLOOD_HARNESS = ROOT / "test" / "automation" / "flooding" / "flood_harness.py"
TRACE_HARNESS = ROOT / "test" / "automation" / "traceability" / "traceability_harness.py"
SEC_REPLAY = ROOT / "test" / "automation" / "research-recorder" / "sec02_replay.py"
FABRIC_ISOLATION = ROOT / "test" / "automation" / "resilience" / "fabric_endpoint_isolation.sh"
R2_HARNESS = ROOT / "test" / "automation" / "resilience" / "r2_fabric_reconciliation.py"
R1_ROUTE_GATE = ROOT / "test" / "automation" / "resilience" / "r1_internet_route_gate.py"
RESEARCH_CONTRACT = ROOT / "test" / "automation" / "research_contract.py"
FABRIC_SYNC = ROOT / "test" / "automation" / "fabric-sync" / "fabric_sync.py"
OFFLINE_RUNNER = ROOT / "test" / "automation" / "offline_test.py"

# Formal readiness is intentionally conservative. A status can move to READY only
# after the same entry point orchestrates the complete Chapter-3 action, not merely
# the recorder around an action that a human would still need to remember.
STATUS = {
    "PRE": ("READY", "Full-stack preflight is implemented by the recorder."),
    "P1": ("READY", "Complete normal-operation orchestration is commissioned: warm-up gating, closed 30-minute measurement window, calibrated source/ChirpStack/database correlation, bounded Fabric settlement, sealed evidence, and strict post-run validation."),
    "P2": ("HARNESS_REQUIRED", "LoRaWAN-side synchronized manifests, deterministic matched payload sets, frozen control/Fabric ordering, and fail-closed Fabric-result validation are implemented; the real production-path open-loop Fabric injector and live commissioning are still required."),
    "R1": ("CAPTURE_READY", "The LTE-only WAN/no-fallback route gate is implemented and live-proven; full evidence capture works. Release remains withheld until the 30m/60m/30m outage/restore action is deployed through a dedicated gateway mutation path that preserves br-lan management and local LoRa capture."),
    "R2": ("HARNESS_REQUIRED", "Real non-counted two-record Fabric Prepare outage/reconciliation passed: 2/2 same-source keys and digests confirmed after restore, 56.370-second recovery, adapter-only rule removed (20260921-160954). The complete ten-record formal R2 and independently queried HRC ledger / prepared-Tx runtime proof remain uncommissioned."),
    "A1": ("CAPTURE_READY", "Non-counted real LoRaWAN authentication rehearsal passed 3/3 (valid OTAA, wrong AppKey, unregistered DevEUI); isolated MQTT broker rehearsal passed 30/30 with observer delivery, zero false acceptance, and inactive-listener cleanup. The Fabric authentication third and full nine-condition x10 synchronized orchestration remain uncommissioned; counted A1 is not released."),
    "A2": ("HARNESS_REQUIRED", "A controlled missing-required-endorsement fixture with world-state pre/post proof is required."),
    "S1": ("CAPTURE_READY", "Real non-counted replay 1/1 and modified-MIC DevAddr spoof 1/1 were independently RAK5146-received with zero accepted application/DB/outbox rows, and SEC-01 was restored. Explicit MIC-error logs, 40-attempt controls and one-block formal orchestration remain uncommissioned; counted S1 is not released."),
    "S2": ("METHODOLOGY_REQUIRED", "Chapter 3 does not define count, duration, injection boundary, acceptance rule, or analysis formula for the application-layer duplicate/replay test."),
    "F1": ("CAPTURE_READY", "Real non-counted 0/10/50 connection/s cloud-UTC rehearsal passed with legitimate EMU-01 delivery in every window and zero invalid acceptance (20260921-141932); complete formal 300-second x3-repetition release remains withheld."),
    "F2": ("CAPTURE_READY", "Real non-counted 0/10/50 malformed-message/s window results passed, legitimate EMU-01 delivered in each, all 186 sealed evidence files verified (20260921-143817). However, the outer MCP command timed out after the windows before final session/exit and needed independent listener cleanup; exact one-block completion and formal 300-second x3-repetition release remain withheld."),
    "I1": ("HARNESS_REQUIRED", "Controlled post-hash/pre-storage alteration fixture is required."),
    "I2": ("HARNESS_REQUIRED", "Live EMU-01 Fabric outbox uses telemetry-attestation-v2 and immutable HRC finalized_payload anchors; existing I2 Go read-only recompute/Python scorer are v1-only synthetic code (explicit v2 fail-closed). Requires verified gateway lineage, separate original exact-payload Fabric vs sealed-evidence canonical digest checks, controlled isolated tamper/restore and independent HRC readback before live release."),
    "I3": ("HARNESS_REQUIRED", "Dedicated synthetic Fabric duplicate/overwrite mutation namespace and world-state query proof are required."),
    "T1": ("CAPTURE_READY", "Complete ten-record persisted source-to-DB-to-Fabric retrieval/scoring harness exists; release is withheld until a clean live commissioning rehearsal passes."),
    "T2": ("CAPTURE_READY", "Complete ten non-overlapping x five-record chronology reconstruction/scoring harness exists; release is withheld until a clean live commissioning rehearsal passes."),
}


def require_file(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"Required file missing: {path}")


def help_check(script: Path, *args: str) -> None:
    require_file(script)
    cp = subprocess.run([sys.executable, str(script), *args, "--help"], cwd=ROOT,
                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    if cp.returncode != 0:
        tail = "\n".join(cp.stdout.splitlines()[-8:])
        raise RuntimeError(f"Interface check failed for {script.name} {' '.join(args)}:\n{tail}")


def show(test_id: str, status: str, detail: str) -> None:
    print(f"TEST_ID={test_id}")
    print(f"STATUS={status}")
    print(f"DETAIL={detail}")


def validate_test_tools(test_id: str) -> None:
    require_file(RESEARCH_CONTRACT)
    if test_id in FABRIC_REQUIRED or test_id in FABRIC_OPTIONAL:
        help_check(FABRIC_SYNC)
    contract = subprocess.run([sys.executable, str(RESEARCH_CONTRACT)], cwd=ROOT,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    if contract.returncode != 0 or "RESEARCH_CONTRACT=PASS" not in contract.stdout:
        raise RuntimeError("research contract self-validation failed: " + contract.stdout[-1000:])
    require_file(RECORDER)
    require_file(ENSURE_READY)
    require_file(STUDY_SUMMARY)
    help_check(RECORDER)
    if test_id == "PRE":
        help_check(RECORDER, "preflight")
    else:
        help_check(RECORDER, "run")
    if test_id == "S1":
        help_check(SEC_REPLAY)
    if test_id in {"T1", "T2"}:
        help_check(TRACE_HARNESS, test_id)
    if test_id in {"F1", "F2"}:
        help_check(FLOOD_HARNESS, test_id)
    if test_id == "F1":
        help_check(CONN_FLOOD)
        require_file(MQTT_WIRE)
    if test_id == "F2":
        help_check(MSG_FLOOD)
        help_check(MQTT_PUBLISH)
        help_check(NODERED_FLOOD)
        require_file(MQTT_WIRE)
    if test_id == "R1":
        help_check(R1_ROUTE_GATE)
    if test_id == "R2":
        require_file(FABRIC_ISOLATION)
        help_check(R2_HARNESS)


def validate_p1_measurement_boundary(run_id: str, minimum_source_attempts: int = 1,
                                     expected_source_attempts: int | None = None) -> None:
    group = "smoke" if run_id.startswith("manual-P1-rehearsal-") else "normal-operation"
    summary_path = ROOT / "chapter4-results" / group / run_id / "derived" / "run-summary.json"
    require_file(summary_path)
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    source = data.get("source", {})
    telemetry = data.get("telemetry", {})
    attempts = int(source.get("attempts") or 0)
    accepted = int(telemetry.get("formal_chapter3_pdr_numerator_unique_chirpstack_accepted") or 0)
    pdr_status = str(telemetry.get("formal_chapter3_pdr_status") or "")
    sensor_latency_status = str(telemetry.get("sensor_to_database_status") or "")
    sensor_latency = telemetry.get("sensor_to_database_ms") or {}
    sensor_latency_count = int(sensor_latency.get("count") or 0) if isinstance(sensor_latency, dict) else 0
    fabric = data.get("fabric_outbox", {})
    fabric_rows = int(fabric.get("rows") or 0)
    fabric_committed = int(fabric.get("committed_with_tx_id") or 0)
    fabric_status = fabric.get("status_counts") or {}
    if expected_source_attempts is not None and attempts != expected_source_attempts:
        raise RuntimeError(
            f"P1 formal denominator invalid: source attempts={attempts}, expected exactly {expected_source_attempts} "
            "scheduled attempts in the closed 30-minute window"
        )
    if attempts < minimum_source_attempts:
        raise RuntimeError(f"P1 measurement boundary invalid: source attempts={attempts}, need >= {minimum_source_attempts}")
    if pdr_status != "MEASURED_CHIRPSTACK_ACCEPTANCE_BOUNDARY":
        raise RuntimeError(f"P1 measurement boundary invalid: formal PDR status={pdr_status or 'missing'}")
    if sensor_latency_status != "MEASURED_CALIBRATED_SENSOR_TO_DATABASE" or sensor_latency_count < 1:
        raise RuntimeError(
            f"P1 timing boundary invalid: status={sensor_latency_status or 'missing'} samples={sensor_latency_count}"
        )
    if fabric_rows != accepted:
        raise RuntimeError(
            f"P1 Fabric boundary invalid: outbox rows={fabric_rows}, ChirpStack accepted={accepted}, source attempts={attempts}"
        )
    if fabric_committed != fabric_rows or set(fabric_status) != {"confirmed"}:
        raise RuntimeError(
            f"P1 Fabric boundary invalid: rows={fabric_rows} committed_with_txid={fabric_committed} status_counts={fabric_status}"
        )
    print(
        f"P1_MEASUREMENT_BOUNDARY=PASS source_attempts={attempts} pdr_status={pdr_status} "
        f"sensor_to_database_samples={sensor_latency_count} fabric_confirmed={fabric_committed}/{fabric_rows}"
    )


def run_ready(test_id: str) -> int:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = [sys.executable, str(RECORDER)]
    rehearsal_seconds = int(os.environ.get("RESEARCH_MANUAL_REHEARSAL_SECONDS", "0") or "0")
    if rehearsal_seconds < 0:
        raise RuntimeError("RESEARCH_MANUAL_REHEARSAL_SECONDS must be >= 0")
    if test_id == "PRE":
        cp = subprocess.run([sys.executable, str(ENSURE_READY)], cwd=ROOT)
        return int(cp.returncode)
    if test_id in {"F1", "F2"}:
        pre = subprocess.run([sys.executable, str(ENSURE_READY)], cwd=ROOT)
        if pre.returncode != 0:
            return int(pre.returncode)
        cmd = [sys.executable, str(FLOOD_HARNESS), test_id]
        if rehearsal_seconds:
            # F2's actual 30 s flood windows passed; the equal-length recovery
            # between each uncounted window exceeded the remote command limit.
            # Formal F2 still uses the unchanged 300 s recovery contract.
            recovery_seconds = rehearsal_seconds
            if test_id == "F2":
                recovery_seconds = int(os.environ.get(
                    "RESEARCH_MANUAL_REHEARSAL_RECOVERY_SECONDS",
                    str(min(10, rehearsal_seconds)),
                ))
                if recovery_seconds < 1 or recovery_seconds > rehearsal_seconds:
                    raise RuntimeError("F2 rehearsal recovery must be 1..measurement seconds")
            print(f"REHEARSAL_MODE=1 duration_seconds={rehearsal_seconds} "
                  f"recovery_seconds={recovery_seconds} group=dos-flooding counted_research=NO")
            cmd += ["--rehearsal-seconds", str(rehearsal_seconds),
                    "--rehearsal-recovery-seconds", str(recovery_seconds)]
        cp = subprocess.run(cmd, cwd=ROOT)
        if cp.returncode == 0:
            subprocess.run([sys.executable, str(STUDY_SUMMARY)], cwd=ROOT, check=False)
        return int(cp.returncode)
    if test_id == "R2":
        pre = subprocess.run([sys.executable, str(ENSURE_READY)], cwd=ROOT)
        if pre.returncode != 0:
            return int(pre.returncode)
        cmd = [sys.executable, str(R2_HARNESS)]
        if rehearsal_seconds:
            print("REHEARSAL_MODE=1 group=resilience target_records_per_phase=2 counted_research=NO")
            cmd.append("--rehearsal")
        cp = subprocess.run(cmd, cwd=ROOT)
        return int(cp.returncode)
    if test_id in {"T1", "T2"}:
        pre = subprocess.run([sys.executable, str(ENSURE_READY)], cwd=ROOT)
        if pre.returncode != 0:
            return int(pre.returncode)
        cmd = [sys.executable, str(TRACE_HARNESS), test_id]
        if rehearsal_seconds:
            print(f"REHEARSAL_MODE=1 duration_seconds={rehearsal_seconds} group=traceability counted_research=NO")
            cmd += ["--rehearsal-seconds", str(rehearsal_seconds)]
        cp = subprocess.run(cmd, cwd=ROOT)
        return int(cp.returncode)
    if test_id != "P1":
        raise RuntimeError(f"internal readiness error: {test_id} is not a complete formal action")
    pre = subprocess.run([sys.executable, str(ENSURE_READY)], cwd=ROOT)
    if pre.returncode != 0:
        return int(pre.returncode)
    if rehearsal_seconds:
        print(f"REHEARSAL_MODE=1 duration_seconds={rehearsal_seconds} group=smoke counted_research=NO")
        run_id = f"manual-P1-rehearsal-{stamp}"
        cmd = base + ["run", "--group", "smoke", "--run-id", run_id,
                      "--condition", "REHEARSAL P1 normal-operation recorder path", "--expected",
                      "full-stack recorder path starts/stops cleanly with measurable sensor-to-ChirpStack boundary",
                      "--scope", "full", "--duration-seconds", str(rehearsal_seconds),
                      "--fabric-settle-seconds", "420"]
        cp = subprocess.run(cmd, cwd=ROOT)
        if cp.returncode != 0:
            return int(cp.returncode)
        validate_p1_measurement_boundary(run_id, minimum_source_attempts=1)
        subprocess.run([sys.executable, str(STUDY_SUMMARY)], cwd=ROOT, check=False)
        return 0
    validate_static_contract()
    rep = input("P1 repetition (1-3): ").strip()
    if rep not in {"1", "2", "3"}:
        raise RuntimeError("Use repetition 1, 2, or 3")
    run_id = f"P1-{rep}-{stamp}"
    cmd = base + ["run", "--group", "normal-operation", "--run-id", run_id,
                  "--condition", "P1 normal operation; no attack/outage/failure", "--expected",
                  "legitimate 15-second EMU-01 uplinks accepted, stored, and Fabric-confirmed",
                  "--scope", "full", "--duration-seconds", "1800",
                  "--fabric-settle-seconds", "420"]
    cp = subprocess.run(cmd, cwd=ROOT)
    if cp.returncode != 0:
        return int(cp.returncode)
    validate_p1_measurement_boundary(
        run_id,
        minimum_source_attempts=int(FORMAL["P1"]["planned_attempts_per_run"]),
        expected_source_attempts=int(FORMAL["P1"]["planned_attempts_per_run"]),
    )
    summary = subprocess.run([sys.executable, str(STUDY_SUMMARY)], cwd=ROOT)
    return int(summary.returncode)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("test", choices=TEST_IDS)
    ap.add_argument("--synthetic", action="store_true",
                    help="Run non-counted offline code checks; never start live test actions")
    args = ap.parse_args()
    test_id = args.test
    if args.synthetic:
        from offline_test import OFFLINE_SUITES
        if test_id not in OFFLINE_SUITES:
            print(f"TEST_ID={test_id} SYNTHETIC=UNAVAILABLE LIVE_TEST=NOT_STARTED "
                  "(no complete offline suite for this experiment)", file=sys.stderr)
            return 2
        print(f"TEST_ID={test_id} MODE=SYNTHETIC RESEARCH_SAMPLES=0 LIVE_TEST=NOT_STARTED", flush=True)
        cp = subprocess.run([sys.executable, str(OFFLINE_RUNNER), test_id], cwd=ROOT,
                            timeout=120, check=False)
        return int(cp.returncode)
    validate_test_tools(test_id)
    status, detail = STATUS[test_id]
    show(test_id, status, detail)

    # Validation of every exact manual command must be possible without mutation.
    # P1 also has an explicit non-counted commissioning rehearsal. This lets us
    # prove the complete live action before promoting the operator command to
    # READY, without weakening the normal guard for unreleased counted tests.
    commissioning_rehearsal = (
        test_id in {"P1", "R2", "F1", "F2", "T1", "T2"}
        and os.environ.get("RESEARCH_MANUAL_REHEARSAL_SECONDS", "0").strip() not in {"", "0"}
    )
    if status != "READY" and not commissioning_rehearsal:
        print("CODE_BLOCK_TEST=PASS (guard/interface path executed; counted test not started)")
        return 0
    if commissioning_rehearsal:
        print("COMMISSIONING_REHEARSAL=ENABLED counted_research=NO")

    try:
        confirm = input("Type EXECUTE to start this real test command, or press Enter to stop after validation: ").strip()
    except EOFError:
        confirm = ""
    if confirm != "EXECUTE":
        print("CODE_BLOCK_TEST=PASS (exact command executed through safe validation path; counted test not started)")
        return 0
    return run_ready(test_id)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        raise SystemExit(1)


