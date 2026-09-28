#!/usr/bin/env python3
"""Verify sealed run files and reproduce summaries without modifying original evidence."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify(run):
    run = run.resolve()
    manifest = run / "metadata" / "SHA256SUMS.csv"
    rows = list(csv.DictReader(manifest.open(encoding="utf-8-sig", newline="")))
    if not rows:
        raise ValueError("Empty evidence manifest")
    paths = set()
    for row in rows:
        relative = row["relative_path"]
        target = (run / relative).resolve()
        if not target.is_relative_to(run) or relative in paths:
            raise ValueError("Unsafe or duplicate manifest path: " + relative)
        paths.add(relative)
        if not target.is_file() or target.stat().st_size != int(row["bytes"]) or digest(target) != row["sha256"].lower():
            raise ValueError("Evidence seal mismatch: " + relative)
    for required in ("derived/run-summary.json", "derived/run-summary.csv", "metadata/run-meta.json"):
        if required not in paths:
            raise ValueError("Required file is not sealed: " + required)
    for source in (run / "raw").rglob("*"):
        if source.is_file() and source.relative_to(run).as_posix() not in paths:
            raise ValueError("Unsealed raw evidence: " + source.name)
    original = json.loads((run / "derived/run-summary.json").read_text(encoding="utf-8-sig"))
    original.pop("run_dir", None)
    original_csv = (run / "derived/run-summary.csv").read_bytes()
    summarizer = Path(__file__).resolve().parent / "summarize-run.py"
    with tempfile.TemporaryDirectory(prefix="lorawan-reproduce-") as tmp:
        copy = Path(tmp) / run.name
        shutil.copytree(run, copy)
        for iteration in (1, 2):
            cp = subprocess.run([sys.executable, str(summarizer), str(copy)], capture_output=True, text=True, timeout=120)
            if cp.returncode:
                raise ValueError("Summary regeneration failed: " + (cp.stderr or cp.stdout)[-1000:])
            rebuilt = json.loads((copy / "derived/run-summary.json").read_text(encoding="utf-8-sig"))
            rebuilt.pop("run_dir", None)
            if rebuilt != original or (copy / "derived/run-summary.csv").read_bytes() != original_csv:
                raise ValueError(f"Summary differs from sealed result on regeneration {iteration}")
    return {"status": "PASS", "run": run.name, "sealed_files_checked": len(rows),
            "summary_regenerations": 2, "python_version": sys.version.split()[0], "json_comparison": "all fields except relocated run_dir",
            "csv_comparison": "byte-exact", "summarizer_sha256": digest(summarizer)}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.run_dir)
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}))
        return 1
    print(json.dumps(result, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
