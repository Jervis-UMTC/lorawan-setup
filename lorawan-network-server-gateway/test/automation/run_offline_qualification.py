#!/usr/bin/env python3
"""Run allowlisted offline-only research test-code suites and seal a CODE_ONLY report.

No recorder, gateway, sensor, production broker or Fabric endpoint is contacted
by this orchestrator. The allowlisted load-tools tests use an in-process mock
broker on local loopback. A successful report is NOT a real research measurement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTOMATION = ROOT / "test" / "automation"
DEFAULT_OUTPUT = ROOT / "chapter4-results" / "code-qualification"

# Fixed allowlist, so adding a new script cannot silently introduce live I/O.
SUITES = (
    ("research-contract", ".", "test_research_contract.py"),
    ("a1-mqtt", "authentication", "test_a1_mqtt_harness.py"),
    ("a1-lorawan", "authentication", "test_a1_lorawan_harness.py"),
    ("a1-lorawan-workflow", "authentication", "test_a1_lorawan_workflow.py"),
    ("a2-fabric-evidence", "authentication", "test_a2_fabric_endorsement_evidence.py"),
    ("i1-application-integrity", "integrity", "test_i1_evidence.py"),
    ("i2-post-storage-integrity", "integrity", "test_i2_evidence.py"),
    ("i3-ledger-duplicate-overwrite", "integrity", "test_i3_ledger_evidence.py"),
    ("fabric-sync", "fabric-sync", "test_fabric_sync.py"),
    ("p2-pair-runner", "fabric-performance", "test_p2_pair_runner.py"),
    ("r1-lte-route", "resilience", "test_r1_internet_route_gate.py"),
    ("r2-reconciliation", "resilience", "test_r2_fabric_reconciliation.py"),
    ("f1-f2-flood-validation", "flooding", "test_flood_harness.py"),
    ("t1-t2-traceability", "traceability", "test_traceability_harness.py"),
    ("s1-replay-helper", "research-recorder", "test_sec02_replay.py"),
    ("mqtt-wire-mock", "load-tools", "test_mqtt_wire.py"),
)
COUNT_RE = re.compile(r"Ran (\d+) tests? in ")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(output_root: Path = DEFAULT_OUTPUT) -> tuple[int, Path]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = output_root / f"offline-code-{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    summary: dict[str, object] = {
        "qualification": "CODE_ONLY",
        "counted_research": False,
        "hardware_measurements": False,
        "production_services_touched": False,
        "python_version": sys.version.split()[0],
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FAIL",
        "suites": [],
    }
    results: list[dict[str, object]] = []
    for label, folder, filename in SUITES:
        suite_file = AUTOMATION / folder / filename
        row: dict[str, object] = {"suite": label, "file": str(suite_file.relative_to(ROOT))}
        if not suite_file.is_file():
            row.update({"status": "FAIL", "error": "allowlisted test module missing", "tests": 0})
            results.append(row)
            print(f"{label}: FAIL (missing module)", flush=True)
            continue
        row["source_sha256"] = sha256_file(suite_file)
        cmd = [sys.executable, "-m", "unittest", "discover", "-s", str(suite_file.parent),
               "-p", suite_file.name, "-v"]
        try:
            p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                               timeout=45, check=False)
            (out / f"{label}.stdout.txt").write_text(p.stdout, encoding="utf-8")
            (out / f"{label}.stderr.txt").write_text(p.stderr, encoding="utf-8")
            counts = COUNT_RE.findall(p.stderr + "\n" + p.stdout)
            tests = int(counts[-1]) if counts else 0
            passed = p.returncode == 0 and tests > 0
            row.update({"status": "PASS" if passed else "FAIL",
                        "exit_code": p.returncode, "tests": tests})
            if not passed:
                row["error"] = "nonzero exit code or zero/missing test-count summary; inspect suite logs"
        except subprocess.TimeoutExpired as e:
            row.update({"status": "FAIL", "tests": 0, "error": f"timeout: {e.timeout}s"})
        results.append(row)
        print(f"{label}: {row['status']} ({row['tests']} offline tests)", flush=True)
    summary["suites"] = results
    summary["total_tests"] = sum(int(x["tests"]) for x in results)
    summary["status"] = "PASS" if all(x["status"] == "PASS" for x in results) else "FAIL"
    summary["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    (out / "code-only-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"OFFLINE_CODE_QUALIFICATION={summary['status']} total_tests={summary['total_tests']}")
    print(f"NON_COUNTED_RESULTS={out}")
    return (0 if summary["status"] == "PASS" else 2), out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()
    raise SystemExit(execute(args.output_root)[0])
