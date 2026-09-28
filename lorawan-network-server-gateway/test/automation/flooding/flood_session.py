#!/usr/bin/env python3
"""Reconcile sealed F1/F2 rehearsal windows after an interrupted operator wrapper.

Read-only against research measurements; requires the ephemeral fixtures to be
independently confirmed stopped before reporting a recovered session. This
does not convert an MCP timeout into a successful original command exit.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import socket
from datetime import datetime, timezone
from pathlib import Path

import flood_harness as flood

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "chapter4-results" / "dos-flooding"


def verified_manifest(run_dir: Path) -> tuple[int, str]:
    manifest = run_dir / "metadata" / "SHA256SUMS.csv"
    if not manifest.is_file():
        raise RuntimeError(f"missing recorder SHA256 manifest: {manifest}")
    count = 0
    with manifest.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            rel = Path(row["relative_path"])
            fp = (run_dir / rel).resolve()
            if not fp.is_relative_to(run_dir.resolve()) or not fp.is_file():
                raise RuntimeError(f"missing or unsafe evidence file: {rel}")
            data = fp.read_bytes()
            if len(data) != int(row["bytes"]) or hashlib.sha256(data).hexdigest().lower() != row["sha256"].lower():
                raise RuntimeError(f"tampered evidence: {rel}")
            count += 1
    if not count:
        raise RuntimeError(f"empty evidence manifest: {manifest}")
    return count, hashlib.sha256(manifest.read_bytes()).hexdigest()


def verify_cleanup(test: str) -> dict[str, object]:
    # Do not trust an earlier manual statement that the test fixtures stopped.
    branch = json.loads(flood.action(flood.ULC03, "flood-branch-status"))
    listener = flood.action(flood.ULC01, "flood-listener-status")
    if branch.get("branch_installed") or branch.get("state_present") or branch.get("research_nodes_present"):
        raise RuntimeError("temporary Node-RED flood branch remains installed")
    if branch.get("container_health") != "healthy":
        raise RuntimeError("Node-RED is not healthy after flood")
    if "listener=INACTIVE" not in listener:
        raise RuntimeError("isolated flood listener remains active")
    with socket.socket() as probe:
        probe.settimeout(0.4)
        if probe.connect_ex((flood.LOCAL_HOST, flood.LOCAL_PORT)) == 0:
            raise RuntimeError("SSH flood tunnel is still listening")
    recorder_marker = ROOT / "chapter4-results" / "_recorder-active.json"
    if recorder_marker.exists():
        raise RuntimeError("a research recorder remains active")
    return {
        "branch_installed": False,
        "branch_state_present": False,
        "research_nodes_present": [],
        "node_red_health": "healthy",
        "node_red_flow_sha256": branch.get("flow_sha256"),
        "isolated_listener": "INACTIVE",
        "ssh_tunnel": "ABSENT",
        "recorder": "CLEAN",
        "verified_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def recover(test: str, stamp: str, *, check_cleanup: bool = True,
            results_dir: Path = RESULTS) -> dict[str, object]:
    if test not in ("F1", "F2") or len(stamp) != 15 or stamp[8] != "-" or not stamp[:8].isdigit() or not stamp[9:].isdigit():
        raise RuntimeError("expected test F1/F2 and run stamp YYYYMMDD-HHMMSS")
    base = results_dir.resolve()
    recovered = []
    manifest_files = 0
    duration = None
    recovery = None
    for rate in (0, 10, 50):
        run_id = f"{test}-rehearsal-r{rate}-n1-{stamp}"
        rd = base / run_id
        rp = rd / "derived" / "flood-harness-result.json"
        if not rp.is_file():
            raise RuntimeError(f"incomplete rehearsal; missing {rp}")
        result = json.loads(rp.read_text(encoding="utf-8-sig"))
        if result.get("run_id") != run_id or result.get("rate_per_second") != rate or result.get("repetition") != 1 or result.get("formal") is not False:
            raise RuntimeError(f"identity/formal mismatch: {run_id}")
        seconds = result.get("duration_seconds")
        rec = result.get("recovery_seconds")
        if type(seconds) is not int or seconds < 20 or type(rec) is not int or rec < 0:
            raise RuntimeError(f"invalid full-window/recovery duration: {run_id}")
        if duration is None:
            duration, recovery = seconds, rec
        if (seconds, rec) != (duration, recovery):
            raise RuntimeError("inconsistent flood rehearsal duration")
        if result.get("status") != "PASS" or result.get("errors") or result.get("recorder_returncode") != 0:
            raise RuntimeError(f"window did not finish cleanly: {run_id}")
        if (rd / "derived" / "run-status.txt").read_text(encoding="utf-8-sig").strip() != "RECORDED_UNCLASSIFIED":
            raise RuntimeError(f"unexpected recorder classification: {run_id}")
        errors = flood.validate_run(test, rate, seconds, result.get("load", {}),
                                    result.get("window", {}), result.get("db_guard", {}), False)
        if errors:
            raise RuntimeError(f"window validation failed {run_id}: {errors}")
        count, manifest_hash = verified_manifest(rd)
        manifest_files += count
        recovered.append({**result,
                          "recorder_manifest_sha256": manifest_hash,
                          "flood_result_sha256": hashlib.sha256(rp.read_bytes()).hexdigest(),
                          "verified_manifest_files": count})
    cleanup = verify_cleanup(test) if check_cleanup else {"status": "NOT_VERIFIED_OFFLINE"}
    return {
        "test": test, "formal": False, "phase_seconds": duration,
        "recovery_seconds": recovery, "results": recovered,
        "cleanup_errors": [],
        "cleanup_verification": cleanup,
        "recovered_after_operator_timeout": True,
        "operator_exit_code": None,
        "status": "WINDOWS_PASS_OPERATOR_TIMEOUT",
        "counted_research": False,
        "manifest_files_verified": manifest_files,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("test", choices=("F1", "F2"))
    ap.add_argument("stamp", help="existing real run stamp YYYYMMDD-HHMMSS")
    args = ap.parse_args()
    data = recover(args.test, args.stamp)
    out = RESULTS / "_sessions" / f"{args.test}-{args.stamp}.json"
    if out.exists():
        raise RuntimeError(f"session exists; refuse overwrite: {out}")
    flood.write_json(out, data)
    print(f"RECOVERED_EVIDENCE=PASS test={args.test} windows=3 "
          f"sealed_files={data['manifest_files_verified']} counted_research=NO")
    print("OPERATOR_COMMAND_EXIT=TIMEOUT_NOT_PASS")
    print(f"SESSION_RESULT={out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, OSError, KeyError) as exc:
        print(f"RECOVERY_ERROR={exc}")
        raise SystemExit(2)
