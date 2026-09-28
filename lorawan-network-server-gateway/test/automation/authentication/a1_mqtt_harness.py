#!/usr/bin/env python3
"""Fail-closed Chapter 3 A1 MQTT authentication/authorization harness.

Runs only the isolated ULC-01 research broker profile. It never edits/restarts
production Mosquitto and never exposes generated test passwords to this process.
Formal mode is exactly 3 conditions x 10 attempts = 30 MQTT attempts.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "test" / "automation" / "research_contract.py"
SSH = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "OpenSSH" / "ssh.exe"
ACTION_KEY = Path.home() / ".ssh" / "id_ed25519_lorawan_research_actions"
ULC01 = "opsadmin@143.198.205.54"
RESULTS = ROOT / "chapter4-results" / "authentication" / "mqtt"
CONDITIONS = ("MQTT_ALLOWED", "MQTT_WRONG_PASSWORD", "MQTT_PROHIBITED_TOPIC")
EXPECTED = {"MQTT_ALLOWED": "ALLOW", "MQTT_WRONG_PASSWORD": "REJECT", "MQTT_PROHIBITED_TOPIC": "REJECT"}

def load_contract():
    spec = importlib.util.spec_from_file_location("research_contract", CONTRACT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import research contract")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

RC = load_contract()
RC.validate_static_contract()

def action(command: str, timeout: float = 90.0) -> str:
    cp = subprocess.run(
        [str(SSH), "-i", str(ACTION_KEY), "-o", "BatchMode=yes",
         "-o", "ConnectTimeout=8", "-o", "ConnectionAttempts=1",
         "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=yes",
         ULC01, command],
        cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False,
    )
    if cp.returncode != 0:
        raise RuntimeError(f"research action {command!r} failed rc={cp.returncode}: {(cp.stderr or cp.stdout)[-600:]}")
    return cp.stdout

def parse_trials(text: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in text.splitlines():
        if not line.startswith("AUTH_TRIAL|"):
            continue
        parts = line.split("|")
        if len(parts) != 7:
            raise RuntimeError(f"malformed AUTH_TRIAL row: {line}")
        _, condition, trial, expected, actual, response_ms, delivered = parts
        if delivered not in {"0", "1"}:
            raise RuntimeError(f"invalid observer delivery proof in AUTH_TRIAL: {line}")
        rows.append({
            "layer": "MQTT",
            "condition": condition,
            "trial": int(trial),
            "expected_decision": expected,
            "actual_decision": actual,
            "correct_decision": expected == actual,
            "false_acceptance": expected == "REJECT" and actual == "ALLOW",
            "false_rejection": expected == "ALLOW" and actual == "REJECT",
            "unauthorized_state_change": expected == "REJECT" and delivered == "1",
            "delivered_to_observer": delivered == "1",
            "response_time_ms": int(response_ms),
        })
    return rows

def validate(rows: list[dict[str, object]], attempts_each: int) -> list[str]:
    errors: list[str] = []
    expected_total = len(CONDITIONS) * attempts_each
    if len(rows) != expected_total:
        errors.append(f"trial rows={len(rows)} expected={expected_total}")
    for condition in CONDITIONS:
        group = [r for r in rows if r["condition"] == condition]
        if len(group) != attempts_each:
            errors.append(f"{condition} rows={len(group)} expected={attempts_each}")
        trials = sorted(int(r["trial"]) for r in group)
        if trials != list(range(1, attempts_each + 1)):
            errors.append(f"{condition} trial IDs are incomplete/duplicated: {trials}")
    for row in rows:
        condition = str(row["condition"])
        if condition not in EXPECTED or row["expected_decision"] != EXPECTED.get(condition):
            errors.append(f"invalid expected decision for condition {condition!r}")
        if row["actual_decision"] not in {"ALLOW", "REJECT"}:
            errors.append(f"invalid actual decision for condition {condition!r}")
        if int(row["response_time_ms"]) < 0:
            errors.append(f"negative response time for condition {condition!r}")
        if condition == "MQTT_ALLOWED" and row["actual_decision"] == "ALLOW" and not row["delivered_to_observer"]:
            errors.append("allowed decision lacks observer delivery proof")
    if any(not bool(r["correct_decision"]) for r in rows):
        errors.append("one or more MQTT authentication decisions were incorrect")
    if any(bool(r["false_acceptance"]) for r in rows):
        errors.append("false acceptance observed")
    if any(bool(r["unauthorized_state_change"]) for r in rows):
        errors.append("unauthorized state change observed")
    return errors

def write_outputs(session_dir: Path, result: dict[str, object]) -> None:
    session_dir.mkdir(parents=True, exist_ok=False)
    (session_dir / "a1-mqtt-summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rows = result["trials"]
    with (session_dir / "a1-mqtt-trials.csv").open("w", newline="", encoding="utf-8") as fh:
        fields = ["layer","condition","trial","expected_decision","actual_decision",
                  "correct_decision","false_acceptance","false_rejection",
                  "unauthorized_state_change","delivered_to_observer","response_time_ms"]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rehearsal", action="store_true",
                    help="interface/fixture rehearsal; still executes the helper's fixed 30 sanitized MQTT trials")
    args = ap.parse_args()
    if not ACTION_KEY.is_file():
        raise RuntimeError(f"research-actions SSH key missing: {ACTION_KEY}")
    attempts_each = int(RC.FORMAL["A1"]["attempts_per_condition"])
    if len(RC.FORMAL["A1"]["conditions"]) != 9 or RC.FORMAL["A1"]["total_attempts"] != 90:
        raise RuntimeError("A1 authoritative condition/count contract drift")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    session_dir = RESULTS / f"A1-MQTT-{'rehearsal' if args.rehearsal else 'formal'}-{stamp}"
    started = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
    result: dict[str, object] = {
        "test": "A1",
        "layer": "MQTT",
        "formal": not args.rehearsal,
        "conditions": list(CONDITIONS),
        "attempts_per_condition": attempts_each,
        "started_at_utc": started,
        "trials": [],
        "status": "FAIL",
        "errors": [],
        "fixture_smoke": "",
        "cleanup": "",
    }
    started_listener = False
    try:
        remote_version = action("version", timeout=30).strip()
        if remote_version != "research-actions-v2|ulc-01":
            raise RuntimeError(
                f"stale research-actions wrapper: {remote_version!r}; expected 'research-actions-v2|ulc-01'"
            )
        try:
            action("auth-listener-stop", timeout=30)
        except Exception:
            pass
        started_listener = True  # teardown even if startup partially succeeds then raises
        action("auth-listener-start", timeout=60)
        smoke = action("auth-listener-smoke", timeout=30).strip()
        if "AUTH_SMOKE=PASS" not in smoke:
            raise RuntimeError(f"isolated auth listener smoke failed: {smoke[-300:]}")
        result["fixture_smoke"] = "PASS"
        raw = action("auth-listener-run", timeout=180)
        rows = parse_trials(raw)
        result["trials"] = rows
        errors = validate(rows, attempts_each)
        result["errors"] = errors
        result["status"] = "PASS" if not errors else "FAIL"
    except Exception as exc:
        result["errors"] = list(result.get("errors", [])) + [str(exc)]
        result["status"] = "FAIL"
    finally:
        if started_listener:
            try:
                stop = action("auth-listener-stop", timeout=30).strip()
                state = action("auth-listener-status", timeout=30).strip()
                if "listener=INACTIVE" not in stop or "listener=INACTIVE" not in state:
                    raise RuntimeError(f"isolated listener remained active after stop: {stop!r} / {state!r}")
                result["cleanup"] = "PASS"
            except Exception as exc:
                result["cleanup"] = f"FAIL:{exc}"
                result["errors"] = list(result.get("errors", [])) + [f"cleanup:{exc}"]
                result["status"] = "FAIL"
        result["finished_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
        write_outputs(session_dir, result)
    print(f"A1_MQTT_HARNESS={result['status']} formal={not args.rehearsal} trials={len(result['trials'])}")
    print(f"SESSION_DIR={session_dir}")
    for err in result["errors"]:
        print(f"ERROR={err}", file=sys.stderr)
    return 0 if result["status"] == "PASS" else 2

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        raise SystemExit(1)
