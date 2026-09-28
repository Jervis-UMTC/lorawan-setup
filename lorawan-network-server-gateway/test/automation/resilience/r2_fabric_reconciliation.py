#!/usr/bin/env python3
"""Chapter 3 R2 Fabric-unavailability and same-record reconciliation harness.

The only induced fault is a scoped REJECT from the ULC-01 Fabric-adapter
container to its discovered Fabric Gateway endpoint. LoRaWAN, MQTT, PostgreSQL,
host routing, and the other evidence services remain untouched.

Formal mode proves:
1. ten fresh confirmed baseline records;
2. ten fresh records created while Fabric is unreachable, none falsely confirmed;
3. restoration and terminal confirmation of those exact ten source-event keys
   with unchanged digests and without duplicate outbox rows.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
RECORDER=ROOT/"test"/"automation"/"research-recorder"/"research_recorder.py"
ACTION_KEY=Path.home()/".ssh"/"id_ed25519_lorawan_research_actions"
SSH=Path(os.environ.get("WINDIR",r"C:\Windows"))/"System32"/"OpenSSH"/"ssh.exe"
ULC01_ACTION="opsadmin@143.198.205.54"
DEV_EUI="ac1f09fffe296d29"
RESULTS=ROOT/"chapter4-results"/"resilience"
EXPECTED_ENDPOINT="10.104.0.7:7051"
CONTRACT=ROOT/"test"/"automation"/"research_contract.py"
WORKER_SOURCE=ROOT/"evidence-services"/"cloud"/"internal"/"fabricadapter"/"worker.go"
HEX64=re.compile(r"^[0-9a-f]{64}$",re.I)


def load_recorder():
    spec=importlib.util.spec_from_file_location("rr",RECORDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import research recorder")
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
RR=load_recorder()


def load_contract():
    spec=importlib.util.spec_from_file_location("research_contract",CONTRACT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import research contract")
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


RC=load_contract()


def validate_reconciliation_source_contract()->dict[str,object]:
    raw=WORKER_SOURCE.read_bytes()
    text=raw.decode("utf-8")
    query=text.find("query, queryErr := w.ledger.Query")
    verify=text.find("w.ledger.VerifyDigest", query)
    status=text.find("w.ledger.CommitStatus", query)
    retry=text.find("w.ledger.SubmitPrepared", query)
    if min(query,verify,status,retry) < 0 or not (query < verify < status < retry):
        raise RuntimeError("Fabric adapter reconciliation no longer proves Query -> VerifyDigest -> CommitStatus -> same prepared transaction retry")
    return {
        "status":"PASS",
        "worker_source_sha256":hashlib.sha256(raw).hexdigest(),
        "query_before_digest_verify":True,
        "digest_verify_before_commit_status":True,
        "same_prepared_tx_retry_after_status":True,
    }


def action(command:str, timeout:float=45.0)->str:
    cp=subprocess.run([
        str(SSH),"-i",str(ACTION_KEY),"-o","BatchMode=yes","-o","ConnectTimeout=8",
        "-o","ConnectionAttempts=1","-o","IdentitiesOnly=yes","-o","StrictHostKeyChecking=yes",
        ULC01_ACTION,command
    ],cwd=ROOT,text=True,capture_output=True,timeout=timeout,check=False)
    if cp.returncode!=0:
        raise RuntimeError(f"research action failed rc={cp.returncode}: {(cp.stderr or cp.stdout).strip()[-500:]}")
    return cp.stdout.strip()


def choose_db_reader()->str:
    roles={}
    for node in ("ulc01","ulc02","ulc03"):
        cp=RR.run_remote(node,"db-role",check=False)
        roles[node]=(cp.stdout or "").strip()
    for node in ("ulc01","ulc02","ulc03"):
        if roles[node]=="leader":
            return node
    raise RuntimeError(f"no database leader: {roles}")


def state()->dict:
    return json.loads(RR.STATE_PATH.read_text(encoding="utf-8-sig"))


def live_utc()->str:
    deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        value=RR.latest_server_capture_utc(state())
        if value:
            dt=RR.parse_utc(value)+timedelta(seconds=6)
            return dt.isoformat(timespec="milliseconds").replace("+00:00","Z")
        time.sleep(.2)
    raise RuntimeError("authoritative in-run UTC unavailable")


def parse_csv(text:str)->list[dict[str,str]]:
    lines=[x for x in text.splitlines() if x.strip()]
    return list(csv.DictReader(io.StringIO("\n".join(lines)))) if lines else []


def outbox_rows(node:str,start:str,end:str)->list[dict[str,str]]:
    cp=RR.run_remote(node,f"db-export outbox {start} {end} {DEV_EUI}",check=True)
    rows=parse_csv(cp.stdout or "")
    rows.sort(key=lambda r:(r.get("observed_at",""),r.get("source_event_key","")))
    return rows


def wait_rows(node:str,start:str,want:int,timeout:float,predicate,description:str)->list[dict[str,str]]:
    deadline=time.monotonic()+timeout
    last=[]
    while time.monotonic()<deadline:
        end=live_utc()
        last=outbox_rows(node,start,end)
        candidates=[r for r in last if predicate(r)]
        if len(candidates)>=want:
            return candidates[:want]
        time.sleep(4)
    raise RuntimeError(f"timeout waiting for {description}: have={len([r for r in last if predicate(r)])} need={want}")


def isolation_state()->dict[str,str]:
    text=action("fabric-isolation-status")
    values={}
    for line in text.splitlines():
        if "=" in line:
            k,v=line.split("=",1); values[k.strip()]=v.strip()
    endpoint=values.get("fabric_endpoint","")
    if endpoint and endpoint!=EXPECTED_ENDPOINT:
        raise RuntimeError(f"Fabric endpoint changed unexpectedly: {endpoint}")
    return values


def normalize_inactive()->None:
    try:
        action("fabric-isolation-remove")
    except Exception:
        pass
    st=isolation_state()
    if st.get("isolation")!="INACTIVE":
        raise RuntimeError(f"cannot establish inactive Fabric-isolation baseline: {st}")


def wait_outage_rows(node:str,start:str,want:int,timeout:float)->list[dict[str,str]]:
    """Wait for the earliest outage rows to acquire durable seals, without cherry-picking later keys."""
    deadline=time.monotonic()+timeout
    selected:list[dict[str,str]]=[]
    while time.monotonic()<deadline:
        selected=outbox_rows(node,start,live_utc())[:want]
        if len(selected)==want:
            problems=[p for row in selected for p in validate_row(row,must_confirm=False)
                      if p!="missing/invalid digest"]
            if problems:
                raise RuntimeError("first outage rows invalid: "+"; ".join(problems))
            if all(HEX64.fullmatch((row.get("digest_sha256") or "").strip())
                   for row in selected):
                return selected
        time.sleep(4)
    ready=sum(bool(HEX64.fullmatch((row.get("digest_sha256") or "").strip()))
              for row in selected)
    raise RuntimeError(f"timeout waiting for first {want} outage rows to have durable digests: "
                       f"rows={len(selected)} digests={ready}")


def start_recorder(run_id:str)->Path:
    cp=subprocess.run([
        sys.executable,str(RECORDER),"start",
        "--group","resilience","--run-id",run_id,
        "--condition","R2 scoped Fabric Gateway unavailability and same-record reconciliation",
        "--expected","ten outage records stay non-confirmed during isolation then the same records confirm after restore",
        "--scope","full","--interval","5","--fabric-settle-seconds","0"
    ],cwd=ROOT,text=True,capture_output=True,timeout=180,check=False)
    if cp.returncode!=0:
        raise RuntimeError("recorder start failed: "+"\n".join(((cp.stdout or "")+(cp.stderr or "")).splitlines()[-12:]))
    return Path(state()["run_dir"])


def stop_recorder()->subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable,str(RECORDER),"stop"],cwd=ROOT,text=True,capture_output=True,timeout=240,check=False)


def validate_row(row:dict[str,str], *, must_confirm:bool)->list[str]:
    errs=[]
    if not row.get("source_event_key"): errs.append("missing source_event_key")
    if not HEX64.fullmatch((row.get("digest_sha256") or "").strip()): errs.append("missing/invalid digest")
    status=(row.get("status") or "").lower()
    tx=(row.get("fabric_tx_id") or "").strip()
    if must_confirm:
        if status!="confirmed": errs.append(f"status={status}")
        if not HEX64.fullmatch(tx): errs.append("confirmed row has no valid Fabric TxID")
        if not (row.get("committed_at") or "").strip(): errs.append("confirmed row missing committed_at")
    else:
        allowed={"pending","processing","submitted_unknown","reconciling","failed"}
        if status=="confirmed": errs.append("row falsely confirmed while isolated")
        elif status not in allowed: errs.append(f"unrecoverable or unknown outage status={status!r}")
        if (row.get("committed_at") or "").strip():
            errs.append("non-confirmed outage row has committed_at")
    return errs


def freeze_outage_set(rows:list[dict[str,str]],want:int)->dict[str,dict[str,str]]:
    if len(rows)!=want:
        raise RuntimeError(f"outage record count {len(rows)} != {want}")
    problems=[problem for row in rows for problem in validate_row(row,must_confirm=False)]
    if problems:
        raise RuntimeError("outage boundary invalid: "+"; ".join(problems))
    selected={row["source_event_key"]:{
        "digest":row["digest_sha256"],"status_before_restore":row.get("status",""),
        "tx_before_restore":row.get("fabric_tx_id","")
    } for row in rows}
    if len(selected)!=want:
        raise RuntimeError(f"outage keys are missing/duplicated: unique={len(selected)} expected={want}")
    return selected


def main()->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rehearsal",action="store_true",help="non-counted two-record commissioning path")
    args=ap.parse_args()
    target=2 if args.rehearsal else 10
    RC.validate_static_contract()
    RC.validate_r2_profile(target, not args.rehearsal)
    source_guard=validate_reconciliation_source_contract()
    stamp=datetime.now().strftime("%Y%m%d-%H%M%S")
    run_id=f"R2-{'rehearsal' if args.rehearsal else 'formal'}-{stamp}"
    session_dir=RESULTS/"_sessions"; session_dir.mkdir(parents=True,exist_ok=True)
    session=session_dir/f"{run_id}.json"
    normalize_inactive()
    reader=choose_db_reader()
    run_dir=start_recorder(run_id)
    result={
        "test":"R2","formal":not args.rehearsal,"target_records_per_phase":target,
        "run_id":run_id,"run_dir":str(run_dir),"db_reader_node":reader,
        "fabric_endpoint":EXPECTED_ENDPOINT,"baseline":[],"outage":[],"reconciled":[],
        "reconciliation_source_guard":source_guard,
        "status":"FAIL","errors":[]
    }
    isolated=False
    stop_cp=None
    try:
        baseline_start=live_utc()
        baseline=wait_rows(reader,baseline_start,target,720 if args.rehearsal else 420,
                           lambda r:(r.get("status") or "").lower()=="confirmed",
                           "fresh confirmed baseline records")
        baseline_errors=[e for r in baseline for e in validate_row(r,must_confirm=True)]
        if baseline_errors: raise RuntimeError("baseline invalid: "+"; ".join(baseline_errors))
        result["baseline"]=baseline

        isolated=True  # attempt removal if apply partially succeeds then raises
        apply=action("fabric-isolation-apply")
        st=isolation_state()
        if st.get("isolation")!="ACTIVE":
            raise RuntimeError(f"Fabric isolation did not become ACTIVE: {st}")
        outage_start=live_utc()
        outage=wait_outage_rows(reader,outage_start,target,720 if args.rehearsal else 360)
        selected=freeze_outage_set(outage,target)
        result["outage"]=outage
        result["frozen_outage_source_event_keys"]=sorted(selected)
        result["pending_identification_rate_percent"]=100.0*len(selected)/target
        result["false_verification_count"]=sum((r.get("status") or "").lower()=="confirmed" for r in outage)

        restore_begin=time.monotonic()
        action("fabric-isolation-remove")
        st=isolation_state()
        if st.get("isolation")!="INACTIVE":
            raise RuntimeError(f"Fabric isolation did not clear: {st}")
        isolated=False
        deadline=time.monotonic()+(720 if args.rehearsal else 720)
        final_by_key={}
        while time.monotonic()<deadline:
            rows=outbox_rows(reader,outage_start,live_utc())
            by={}
            for row in rows:
                by.setdefault(row.get("source_event_key",""),[]).append(row)
            final_by_key=by
            if all(k in by and len(by[k])==1 and (by[k][0].get("status") or "").lower()=="confirmed"
                   and HEX64.fullmatch((by[k][0].get("fabric_tx_id") or "").strip())
                   for k in selected):
                break
            time.sleep(5)
        else:
            missing=[k for k in selected if not (k in final_by_key and len(final_by_key[k])==1
                    and (final_by_key[k][0].get("status") or "").lower()=="confirmed")]
            raise RuntimeError(f"reconciliation timeout; remaining={missing}")

        recovery=time.monotonic()-restore_begin
        reconciled=[final_by_key[k][0] for k in selected]
        errs=[]
        for row in reconciled:
            errs.extend(validate_row(row,must_confirm=True))
            key=row["source_event_key"]
            if row.get("digest_sha256")!=selected[key]["digest"]:
                errs.append(f"digest changed for {key}")
            if len(final_by_key.get(key,[]))!=1:
                errs.append(f"duplicate outbox rows for {key}")
        if errs: raise RuntimeError("post-recovery validation failed: "+"; ".join(errs))
        result["reconciled"]=reconciled
        result["recovery_time_seconds"]=recovery
        result["recovery_success_rate_percent"]=100.0*len(reconciled)/target
        result["post_recovery_hash_consistency_rate_percent"]=100.0
        result["missing_blockchain_record_count"]=0
        result["duplicate_blockchain_record_count"]=0
        result["conflicting_hash_count"]=0
        result["failed_reconciliation_count"]=0
        result["remaining_pending_count"]=0
        result["status"]="PASS"
    except Exception as exc:
        result["errors"].append(str(exc))
    finally:
        if isolated:
            try: action("fabric-isolation-remove")
            except Exception as exc: result["errors"].append(f"cleanup isolation remove: {exc}")
        try:
            stop_cp=stop_recorder()
            result["recorder_returncode"]=stop_cp.returncode
            result["recorder_tail"]="\n".join(((stop_cp.stdout or "")+(stop_cp.stderr or "")).splitlines()[-12:])
            if stop_cp.returncode!=0:
                result["errors"].append(f"recorder finalization rc={stop_cp.returncode}")
                result["status"]="FAIL"
        except Exception as exc:
            result["errors"].append(f"recorder stop: {exc}"); result["status"]="FAIL"
        result["sealed_evidence_manifest"]=str(run_dir/"metadata"/"SHA256SUMS.csv")
        result["generated_utc"]=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")
        session.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"R2_HARNESS={result['status']} formal={not args.rehearsal} target={target}")
    print(f"SESSION_RESULT={session}")
    for err in result["errors"]: print(f"ERROR={err}",file=sys.stderr)
    return 0 if result["status"]=="PASS" else 2

if __name__=="__main__":
    try: raise SystemExit(main())
    except (RuntimeError,subprocess.TimeoutExpired) as exc:
        print(f"ERROR={exc}",file=sys.stderr); raise SystemExit(1)
