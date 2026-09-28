#!/usr/bin/env python3
"""Launch counted P1 independently of an SSH/MCP session; never mark an interrupted run PASS."""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[3]
RESULTS = PROJECT / "chapter4-results"
ROOT = RESULTS / "_operator-p1-durable"
ENTRY = PROJECT / "test/automation/research-manual/run_test.py"
RECORDER_STATE = RESULTS / "_recorder-active.json"

def utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

def save(path: Path, item: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(item,indent=2)+"\n",encoding="utf-8")
    os.replace(tmp,path)

def alive(pid: int) -> bool:
    if pid <= 0 or os.name != "nt":
        return False
    import ctypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    try:
        exit_code = ctypes.c_ulong(0)
        return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))) and exit_code.value == 259
    finally:
        kernel32.CloseHandle(handle)

def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def start(rep: str) -> int:
    if os.name != "nt":
        raise RuntimeError("This launcher is for the Windows research workstation")
    if RECORDER_STATE.exists():
        raise RuntimeError(f"Recorder already active: {RECORDER_STATE}; do not overlap runs")
    ROOT.mkdir(parents=True,exist_ok=True)
    for p in ROOT.glob("*/result.json"):
        try:
            r=read(p)
            if not r.get("finished_utc") and alive(int(r.get("pid") or 0)):
                raise RuntimeError(f"Another durable P1 operator is active: {p.parent}")
        except (ValueError,KeyError,json.JSONDecodeError):continue
    # Worker has independent console/process group and owns the recorder through settlement.
    name=f"P1-{rep}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    d=ROOT/name
    d.mkdir(parents=True,exist_ok=False)
    report={"test":"P1","repetition":rep,"started_utc":utc(),"pid":None,
            "finished_utc":None,"exit_code":None,"status":"STARTING"}
    save(d/"result.json",report)
    creationflags=(subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP|
                   subprocess.CREATE_NO_WINDOW)
    try:
        with (d/"launcher.txt").open("wb") as out:
            p=subprocess.Popen([sys.executable,"-u",str(Path(__file__).resolve()),
                                "_worker","--repetition",rep,"--directory",str(d)],
                                cwd=PROJECT,stdin=subprocess.DEVNULL,stdout=out,
                                stderr=subprocess.STDOUT,close_fds=True,creationflags=creationflags)
    except Exception:
        (d/"result.json").unlink(missing_ok=True)
        raise
    current=read(d/"result.json")
    current["pid"]=p.pid
    if not current.get("finished_utc"):
        current["status"]="RUNNING"
    save(d/"result.json",current)
    print("P1_OPERATOR_STARTED="+str(d))
    print("PID="+str(p.pid))
    print("Use status or the result.json to check finalization; NEVER assume launch means PASS.")
    return 0

def worker(rep: str, d: Path) -> int:
    record_path=d/"result.json"
    r=read(record_path)
    r.update(pid=os.getpid(),status="RUNNING")
    save(record_path,r)
    with (d/"operator-console.txt").open("w",encoding="utf-8",buffering=1) as out:
        out.write("COMMAND=py -3 test/automation/research-manual/run_test.py P1\n"
                  "REPETITION="+rep+"\nSTART_UTC="+utc()+"\n")
        out.flush()
        try:
            env={**os.environ,"RESEARCH_MANUAL_REHEARSAL_SECONDS":"0"}
            cp=subprocess.run([sys.executable,"-u",str(ENTRY),"P1"],cwd=PROJECT,
                              input="EXECUTE\n"+rep+"\n",text=True,stdout=out,
                              stderr=subprocess.STDOUT,env=env)
            exit_code=cp.returncode
        except Exception as exc:
            exit_code=125
            out.write("OPERATOR_EXCEPTION="+repr(exc)+"\n")
        out.write("OPERATOR_EXIT_CODE="+str(exit_code)+"\nEND_UTC="+utc()+"\n")
    # No fabricated PASS: derive from exact new run and sealed status, not stdout alone.
    runs=sorted((RESULTS/"normal-operation").glob("P1-"+rep+"-*"),
                key=lambda x:x.stat().st_mtime,reverse=True)
    run_start=datetime.fromisoformat(r["started_utc"])
    candidates=[p for p in runs if datetime.fromtimestamp(p.stat().st_ctime,timezone.utc)>=run_start]
    run=candidates[0] if candidates else None
    sealed=(run/"derived/run-status.txt").read_text().strip() if run and (run/"derived/run-status.txt").exists() else None
    clean=bool(exit_code==0 and run and sealed=="RECORDED_UNCLASSIFIED"
               and (run/"derived/run-summary.json").is_file()
               and (run/"metadata/SHA256SUMS.csv").is_file())
    r.update(finished_utc=utc(),exit_code=exit_code,
             run_dir=str(run) if run else None,sealed_status=sealed,
             status="COMPLETED_CLEAN" if clean else "NOT_ACCEPTED")
    save(record_path,r)
    return exit_code if exit_code else (0 if clean else 2)

def status() -> int:
    if not ROOT.exists():
        print("P1_DURABLE_OPERATOR=NOT_STARTED")
        return 0
    directories=sorted([d for d in ROOT.iterdir() if (d/"result.json").exists()],
                       key=lambda x:x.stat().st_mtime,reverse=True)
    if not directories:
        print("P1_DURABLE_OPERATOR=NOT_STARTED")
        return 0
    x=read(directories[0]/"result.json")
    if not x.get("finished_utc") and not alive(int(x.get("pid") or 0)):
        x["status"]="OPERATOR_EXITED_WITHOUT_FINAL_RESULT"
    print(json.dumps(x,indent=2))
    return 0

def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest="mode",required=True)
    p=sub.add_parser("start");p.add_argument("--repetition",choices=("1","2","3"),required=True)
    sub.add_parser("status")
    p=sub.add_parser("_worker");p.add_argument("--repetition",choices=("1","2","3"),required=True)
    p.add_argument("--directory",type=Path,required=True)
    a=ap.parse_args()
    if a.mode=="start":return start(a.repetition)
    if a.mode=="status":return status()
    return worker(a.repetition,a.directory)

if __name__=="__main__":
    try:raise SystemExit(main())
    except Exception as exc:
        print("ERROR="+str(exc),file=sys.stderr)
        raise SystemExit(1)
