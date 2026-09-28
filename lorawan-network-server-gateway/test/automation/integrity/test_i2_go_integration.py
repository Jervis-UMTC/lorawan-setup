#!/usr/bin/env python3
"""Optional I2 Python<->actual production-Go CLI qualification, purely local files.

Explicit --go path required. This is not part of the Go-free portable base
offline runner. No DB, Fabric or sensor access.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
CLOUD=HERE.parents[2]/"evidence-services/cloud"
sys.path.insert(0,str(HERE))
from test_i2_evidence import trial

def main(go:str)->int:
    entry=trial("TAMPERED",1)
    observed=[]
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        for name in ("baseline","current","restored"):
            phase=entry[name]
            source=root/f"{name}-snapshot.json"
            result=root/f"{name}-result.json"
            source.write_text(phase["source_snapshot_json"],encoding="utf-8")
            command=[go,"run","./cmd/research-i2-current-source",
                     "--input",str(source),"--output",str(result)]
            p=subprocess.run(command,cwd=CLOUD,timeout=65,capture_output=True,text=True)
            if p.returncode:
                raise RuntimeError(f"{name} production Go CLI failed: {p.stderr}")
            actual=json.loads(result.read_text(encoding="utf-8"))
            expected=phase["recomputed"]
            if actual["canonical_json"]!=expected["canonical_json"]:
                raise AssertionError(f"{name} exact production canonical bytes differ")
            if actual["digest_sha256"]!=expected["digest_sha256"]:
                raise AssertionError(f"{name} production SHA-256 differs")
            if actual["source_snapshot_sha256"]!=hashlib.sha256(source.read_bytes()).hexdigest():
                raise AssertionError(f"{name} source snapshot hash differs")
            if actual["counted_research"] is not False:
                raise AssertionError("local Go recompute must not mark research as counted")
            observed.append(actual["digest_sha256"])
        if observed[0]==observed[1] or observed[0]!=observed[2]:
            raise AssertionError("unchanged/tampered/restored Go digest sequence invalid")
    print("I2_GO_CROSS_LANGUAGE=PASS PHASES=3 COUNTED_RESEARCH=FALSE")
    return 0

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--go",required=True,help="path to vetted Go 1.25+ executable")
    opts=ap.parse_args()
    try:raise SystemExit(main(opts.go))
    except (OSError,ValueError,RuntimeError,AssertionError,subprocess.TimeoutExpired) as exc:
        print(f"I2_GO_CROSS_LANGUAGE=FAIL ERROR={exc}",file=sys.stderr)
        raise SystemExit(2)
