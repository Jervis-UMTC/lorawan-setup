#!/usr/bin/env python3
"""I1 experimental hash-gate evidence scorer; never connects to Node-RED/DB/Fabric.

Expects independent storage/outbox query observations supplied later by recorder.
A consistent synthetic fixture PASS is CODE_ONLY, not real research evidence.
The experimental JSON.stringify digest is DISTINCT from RFC8785 Fabric evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

DEV_EUI = "ac1f09fffe296d29"
SCOPE = "I1_EXPERIMENTAL_JSON_STRINGIFY_NOT_FABRIC"
FIELDS = ("test_id","dev_eui","f_cnt","sensor_type","sensor_value","unit","event_time")
CONDITIONS = ("UNCHANGED","ALTERED")
HEX64 = re.compile(r"^[a-f0-9]{64}$")
def hex64(v: Any) -> bool:
    return isinstance(v,str) and HEX64.fullmatch(v) is not None

def state_query(v: Any, label: str) -> list[str]:
    if not isinstance(v,dict):
        return [f"{label}: independent DB/outbox query missing"]
    errors=[]
    for k in ("uplinks","outbox"):
        if type(v.get(k)) is not int or v[k] < 0:
            errors.append(f"{label}: {k} count invalid")
    if not str(v.get("query_ref") or "").strip():
        errors.append(f"{label}: query reference missing")
    return errors

def score(row: Any, condition: str, attempt: int) -> dict[str,Any]:
    prefix={"condition":condition,"attempt":attempt}
    if not isinstance(row,dict):
        return {**prefix,"status":"INVALID","errors":["trial is not an object"]}
    invalid=[]
    if row.get("condition")!=condition or row.get("attempt")!=attempt:
        invalid.append("condition/attempt mismatch")
    gate=row.get("gate")
    if not isinstance(gate,dict):
        return {**prefix,"status":"INVALID","errors":["gate observation missing"]}
    if not str(row.get("source_test_id") or "").strip() or row.get("source_test_id")!=gate.get("test_id"):
        invalid.append("source test ID does not match gate")
    if row.get("test_sequence")!=gate.get("test_sequence") or type(row.get("test_sequence")) is not int or row["test_sequence"]<0:
        invalid.append("source sequence does not match gate")
    if gate.get("dev_eui")!=DEV_EUI or gate.get("hash_scope")!=SCOPE:
        invalid.append("wrong target device or experimental hash scope")
    if type(gate.get("altered")) is not bool or gate["altered"]!=(condition=="ALTERED"):
        invalid.append("controlled alteration flag not proven")
    before,after=None,None
    for field,target in (("initial_record_json","before"),("final_record_json","after")):
        raw=gate.get(field)
        if not isinstance(raw,str):
            invalid.append(f"{field} exact JSON bytes missing")
            continue
        expected_hash=hashlib.sha256(raw.encode("utf-8")).hexdigest()
        if gate.get("initial_hash" if target=="before" else "final_hash")!=expected_hash:
            invalid.append(f"{target} experimental SHA-256 does not match recorded exact bytes")
        try:
            parsed=json.loads(raw)
        except (json.JSONDecodeError,UnicodeError):
            invalid.append(f"{target} JSON invalid")
            continue
        if not isinstance(parsed,dict) or tuple(parsed)!=FIELDS:
            invalid.append(f"{target} seven-field JSON structure/order invalid")
            continue
        if target=="before": before=parsed
        else: after=parsed
    if before is not None and after is not None:
        if before.get("test_id")!=row.get("source_test_id") or after.get("test_id")!=row.get("source_test_id"):
            invalid.append("experimental test ID mismatch")
        if before.get("dev_eui")!=DEV_EUI or after.get("dev_eui")!=DEV_EUI:
            invalid.append("record DevEUI mismatch")
        if before.get("sensor_type")!="temperature" or before.get("unit")!="Cel":
            invalid.append("temperature field/unit mismatch")
        if type(before.get("f_cnt")) is not int or before["f_cnt"]<0:
            invalid.append("source frame counter invalid")
        for field in ("event_time","test_id","dev_eui","f_cnt","sensor_type","unit"):
            if before.get(field)!=after.get(field):
                invalid.append(f"unexpected mutation of {field}")
        for record in (before,after):
            value=record.get("sensor_value")
            if type(value) not in (int,float) or not math.isfinite(value):
                invalid.append("nonfinite sensor value")
        if not invalid:
            delta=after["sensor_value"]-before["sensor_value"]
            if condition=="UNCHANGED" and delta!=0:
                invalid.append("unchanged control was deliberately mutated")
            if condition=="ALTERED" and not math.isclose(delta,10.0,abs_tol=1e-9,rel_tol=0):
                invalid.append("alteration was not exactly +10 Cel")
    invalid+=state_query(row.get("pre_storage"),"pre_storage")
    invalid+=state_query(row.get("post_storage"),"post_storage")
    if not str(row.get("gate_observation_ref") or "").strip():
        invalid.append("gate observation reference missing")
    if not str(gate.get("observed_at_utc") or "").strip():
        invalid.append("gate UTC observation timestamp missing")
    else:
        try:
            observed=datetime.fromisoformat(gate["observed_at_utc"].replace("Z","+00:00"))
            if observed.utcoffset() is None or observed.utcoffset().total_seconds()!=0:
                raise ValueError("non UTC")
        except (TypeError,ValueError,OverflowError):
            invalid.append("gate UTC observation timestamp invalid")
    try:
        response_ms=float(row.get("verification_time_ms"))
        if not math.isfinite(response_ms) or response_ms<0: raise ValueError()
    except (ValueError,TypeError,OverflowError):
        invalid.append("verification time invalid")
        response_ms=None
    if invalid:
        return {**prefix,"status":"INVALID","errors":invalid,"source_test_id":row.get("source_test_id")}

    problems=[]
    match=gate["initial_hash"]==gate["final_hash"]
    if gate.get("match") is not match:
        problems.append("gate match boolean disagrees with recomputed hashes")
    observed_status=gate.get("status")
    before_state,after_state=row["pre_storage"],row["post_storage"]
    if before_state["uplinks"]!=0 or before_state["outbox"]!=0:
        invalid.append("target already stored before attempt; attribution impossible")
    if condition=="UNCHANGED":
        if not match or observed_status!="ALLOW":
            problems.append("valid unchanged control was not allowed")
        if after_state["uplinks"]!=1:
            problems.append("unchanged source not stored exactly once")
        if after_state["outbox"] not in (0,1):
            problems.append("unexpected control outbox count")
        if not str(row.get("storage_ref") or "").strip():
            invalid.append("normal storage evidence reference missing")
    else:
        if match or observed_status!="QUARANTINE":
            problems.append("altered record not detected and quarantined")
        if after_state["uplinks"]!=0 or after_state["outbox"]!=0:
            problems.append("altered record propagated to database/outbox")
        if not str(row.get("quarantine_ref") or "").strip():
            invalid.append("quarantine evidence reference missing")
    if invalid:
        return {**prefix,"status":"INVALID","errors":invalid,"source_test_id":row.get("source_test_id")}
    return {**prefix,"status":"FAIL" if problems else "PASS","errors":problems,
            "source_test_id":row["source_test_id"],"verification_time_ms":response_ms,
            "unauthorized_storage":condition=="ALTERED" and
                (after_state["uplinks"]>0 or after_state["outbox"]>0),
            "false_negative":condition=="ALTERED" and (match or observed_status!="QUARANTINE"),
            "false_positive":condition=="UNCHANGED" and (not match or observed_status!="ALLOW")}

def validate(evidence: Any)->dict[str,Any]:
    errors=[]
    if not isinstance(evidence,dict):
        return {"test_id":"I1","status":"INVALID","errors":["invalid evidence object"],"counted_research":False}
    if evidence.get("test_id")!="I1":errors.append("wrong test ID")
    if type(evidence.get("formal")) is not bool:errors.append("formal must be boolean")
    n=evidence.get("attempts_per_condition")
    if type(n) is not int or n<1 or n>10 or (evidence.get("formal") is True and n!=10):
        errors.append("I1 count mismatch: formal needs 10+10")
    groups=evidence.get("conditions")
    if not isinstance(groups,dict) or set(groups)!=set(CONDITIONS):
        errors.append("I1 requires exactly UNCHANGED and ALTERED groups")
    if not hex64(evidence.get("flow_export_sha256")) or not hex64(evidence.get("test_gate_sha256")):
        errors.append("flow export and test gate SHA-256 required")
    if not str(evidence.get("flow_export_ref") or "").strip():
        errors.append("reviewed flow-export reference missing")
    if errors:
        return {"test_id":"I1","status":"INVALID","errors":errors,"counted_research":False}
    seen_ids=set();seen_seq=set();rows=[]
    for name in CONDITIONS:
        group=groups[name]
        if not isinstance(group,list) or len(group)!=n:
            errors.append(f"{name}: expected {n} trials")
            continue
        for i,item in enumerate(group,1):
            result=score(item,name,i);rows.append(result)
            if isinstance(item,dict):
                sid=item.get("source_test_id");seq=item.get("test_sequence")
                if not isinstance(sid,str) or not sid or type(seq) is not int or seq < 0:
                    errors.append(f"{name}/{i}: missing/invalid source ID or sequence")
                elif sid in seen_ids or seq in seen_seq:
                    errors.append(f"{name}/{i}: repeated source ID or sequence")
                else:
                    seen_ids.add(sid);seen_seq.add(seq)
    invalid=bool(errors) or any(x["status"]=="INVALID" for x in rows)
    failed=any(x["status"]=="FAIL" for x in rows)
    statistics_by_condition={}
    for name in CONDITIONS:
        subset=[x for x in rows if x["condition"]==name]
        times=[x["verification_time_ms"] for x in subset if "verification_time_ms" in x]
        statistics_by_condition[name]={
            "passed":sum(x["status"]=="PASS" for x in subset),
            "failed":sum(x["status"]=="FAIL" for x in subset),
            "invalid":sum(x["status"]=="INVALID" for x in subset),
            "mean_verification_time_ms":statistics.mean(times) if times else None,
            "sample_sd_verification_time_ms":statistics.stdev(times) if len(times)>1 else None,
        }
    return {"test_id":"I1","status":"INVALID" if invalid else "FAIL" if failed else "PASS",
            "errors":errors,"trials":rows,"conditions":statistics_by_condition,
            "false_negative_count":sum(x.get("false_negative",False) for x in rows),
            "false_positive_count":sum(x.get("false_positive",False) for x in rows),
            "unauthorized_storage_count":sum(x.get("unauthorized_storage",False) for x in rows),
            "counted_research":False,"qualification":"SUPPLIED_EVIDENCE_VALIDATION_ONLY"}

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    if args.output.resolve()==args.evidence.resolve():
        raise ValueError("source evidence would be overwritten")
    result=validate(json.loads(args.evidence.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"I1_EVIDENCE_CHECK={result['status']} CODE_ONLY_SCORER=1")
    print(f"I1_RESULT={args.output}")
    return 0 if result["status"]=="PASS" else 2
if __name__=="__main__":
    try:raise SystemExit(main())
    except (OSError,ValueError,json.JSONDecodeError) as exc:
        print(f"ERROR={exc}",file=sys.stderr);raise SystemExit(1)
