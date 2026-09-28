#!/usr/bin/env python3
"""I2 post-storage synthetic/external evidence checker, read-only and fail-closed.

Does NOT hash arbitrary DB JSON to impersonate production evidence:
current-source canonical_json must be exported by the Go companion reusing
fabricadapter.BuildEvidence+CanonicalizeEvidence; the supplied exact canonical
bytes, immutable original seal, independent Fabric readback and restoration
are then cross-checked. External references require separate provenance review.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
import statistics
import sys
from pathlib import Path
from typing import Any

HEX64 = re.compile(r"^[a-f0-9]{64}$")
EUI = "ac1f09fffe296d29"
SCHEMA = "telemetry-attestation-v1"
QUAL = "READ_ONLY_SNAPSHOT_RECOMPUTE_NOT_LIVE_ATTESTATION"
CONDITIONS = ("UNCHANGED", "TAMPERED")
CORE_KEYS = {"event_key","source_event_key","schema_version","event_type",
             "source","lorawan","observation","payload"}
def hex64(x:Any)->bool: return isinstance(x,str) and HEX64.fullmatch(x) is not None

def strict_object(pairs:list[tuple[str,Any]])->dict[str,Any]:
    result={}
    for key,val in pairs:
        if key in result: raise ValueError("duplicate JSON object key")
        result[key]=val
    return result

def parse_json(raw:str)->Any:
    return json.loads(raw,object_pairs_hook=strict_object,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite "+x)))

def digest(s:str)->str: return hashlib.sha256(s.encode("utf-8")).hexdigest()

def canonical(export:Any, key:str, event_key:str, sealed:bool=False)->tuple[dict[str,Any]|None,list[str]]:
    errors=[]
    if not isinstance(export,dict):return None,["canonical export absent"]
    if not sealed and export.get("qualification")!=QUAL:
        errors.append("read-only production adapter origin missing")
    if export.get("counted_research") is not False:
        errors.append("recompute must not assert counted research")
    if export.get("event_key")!=event_key or export.get("source_event_key")!=key:
        errors.append("current-source event key mismatch")
    if export.get("schema_version")!=SCHEMA:
        errors.append("must use production v1 schema")
    raw=export.get("canonical_json")
    if not isinstance(raw,str): return None,errors+["exact UTF-8 canonical JSON missing"]
    if not hex64(export.get("digest_sha256")) or digest(raw)!=export["digest_sha256"]:
        errors.append("canonical-byte SHA-256 mismatch")
    try: obj=parse_json(raw)
    except (ValueError,TypeError):return None,errors+["canonical JSON malformed"]
    if not isinstance(obj,dict) or set(obj)!=CORE_KEYS or "gateway_evidence" in obj:
        errors.append("v1 evidence object shape is invalid")
        return None,errors
    if (obj.get("schema_version")!=SCHEMA or obj.get("event_type")!="lorawan_uplink_accepted"
            or obj.get("event_key")!=event_key or obj.get("source_event_key")!=key):
        errors.append("canonical identity/schema differs from trial")
    if not isinstance(obj.get("source"),dict) or obj["source"].get("dev_eui")!=EUI or obj["source"].get("network_server")!="chirpstack":
        errors.append("canonical source identity differs from EMU-01")
    if not isinstance(obj.get("payload"),dict) or not isinstance(obj["payload"].get("decoded_payload"),dict):
        errors.append("canonical decoded payload absent")
    return obj,errors

def compare_snapshot(phase:Any,key:str,event_key:str)->list[str]:
    errors=[]
    if not isinstance(phase,dict):return ["phase/current-source evidence absent"]
    current=phase.get("recomputed")
    if not isinstance(current,dict):return ["read-only adapter recompute absent"]
    snapshot_raw=phase.get("source_snapshot_json")
    if not isinstance(snapshot_raw,str):return ["exact current-source snapshot missing"]
    if current.get("source_snapshot_sha256")!=digest(snapshot_raw):
        errors.append("source snapshot digest does not match read-only adapter input")
    try: snap=parse_json(snapshot_raw)
    except (ValueError,TypeError):return errors+["snapshot JSON malformed"]
    if not isinstance(snap,dict):return errors+["snapshot is not a JSON object"]
    if snap.get("schema_version")!=SCHEMA or snap.get("event_key")!=event_key or snap.get("source_event_key")!=key:
        errors.append("snapshot outbox identity/schema mismatch")
    if snap.get("event_type")!="lorawan_uplink_accepted":
        errors.append("snapshot event type mismatch")
    source=snap.get("source")
    if not isinstance(source,dict) or source.get("dev_eui")!=EUI:
        return errors+["snapshot source DevEUI invalid"]
    for field in ("source_query_ref","outbox_query_ref"):
        if not str(snap.get(field) or "").strip() or current.get(field)!=snap.get(field):
            errors.append(f"{field} missing/mismatch")
    if current.get("event_key")!=event_key or current.get("source_event_key")!=key:
        errors.append("recompute result event key mismatch")
    obj,err=canonical(current,key,event_key);errors+=err
    if obj is None:return errors
    if obj.get("observation",{}).get("observed_at")!=snap.get("observed_at"):
        errors.append("outbox observation timestamp not reconstructed from snapshot")
    source_fields={"application_id":"application_id","device_id":"device_id","device_model":"device_model",
        "gateway_id":"gateway_id","region":"region","dev_eui":"dev_eui"}
    canonical_source=obj.get("source",{})
    for snap_key,canon_key in source_fields.items():
        if canonical_source.get(canon_key)!=source.get(snap_key):
            errors.append(f"source attribute {snap_key} differs from current snapshot")
    for snap_key,canon_key in (("f_cnt","f_cnt"),("f_port","f_port"),("confirmed","confirmed")):
        if obj.get("lorawan",{}).get(canon_key)!=source.get(snap_key):
            errors.append(f"LoRaWAN {snap_key} differs from source snapshot")
    payload=obj.get("payload",{})
    if payload.get("raw_data_base64")!=source.get("raw_data_base64") or payload.get("decoder_version")!=source.get("decoder_version"):
        errors.append("raw/decoder source fields differ")
    if obj.get("observation",{}).get("received_at")!=source.get("received_at"):
        errors.append("source received_at differs")
    data=source.get("payload_json")
    if not isinstance(data,dict) or payload.get("decoded_payload")!=data:
        errors.append("current decoded_payload differs from current source row")
    if type(source.get("temperature_c")) not in (int,float) or not math.isfinite(source["temperature_c"]):
        errors.append("source temperature_c convenience column invalid")
    elif data.get("temperature_c")!=source["temperature_c"]:
        errors.append("convenience temperature column differs from payload")
    return errors

def score(row:Any, condition:str, index:int)->dict[str,Any]:
    core={"condition":condition,"attempt":index}
    if not isinstance(row,dict):return {**core,"status":"INVALID","errors":["trial not object"]}
    errors=[]
    if row.get("condition")!=condition or row.get("attempt")!=index:
        errors.append("condition/attempt mismatch")
    key=row.get("source_event_key")
    if not isinstance(key,str) or not key.startswith("i2-synthetic:") or len(key)<16:
        errors.append("dedicated test source_event_key missing")
        key=str(key or "")
    event_key=row.get("event_key")
    if not isinstance(event_key,str) or not event_key.startswith("uplink:i2-synthetic:"):
        errors.append("event key/source record correlation missing")
        event_key=str(event_key or "")
    if type(row.get("test_sequence")) is not int or row["test_sequence"]<0:
        errors.append("source test_sequence missing/invalid")
    orig=row.get("original_seal")
    orig_obj,orig_errors=canonical(orig,key,event_key,sealed=True);errors+=orig_errors
    if not isinstance(orig,dict):orig={}
    if not str(orig.get("signature_ref") or "").strip() or not str(orig.get("signing_key_id") or "").strip():
        errors.append("immutable signed-seal reference missing")
    if not str(orig.get("outbox_query_ref") or "").strip() or orig.get("outbox_status")!="confirmed":
        errors.append("original confirmed outbox proof missing")
    tx=orig.get("fabric_tx_id")
    if not hex64(tx):errors.append("confirmed Fabric transaction ID missing")
    anchor=row.get("fabric_anchor")
    if not isinstance(anchor,dict):anchor={}
    for name in ("before_query_ref","after_query_ref"):
        if not str(anchor.get(name) or "").strip():errors.append(f"{name} missing")
    if anchor.get("source_event_key")!=key or anchor.get("fabric_tx_id")!=tx:
        errors.append("Fabric anchor event/transaction mismatch")
    if anchor.get("before_digest_sha256")!=orig.get("digest_sha256"):
        errors.append("pre-tamper Fabric anchor does not prove original baseline")
    if not hex64(anchor.get("after_digest_sha256")):
        errors.append("post-tamper Fabric anchor digest missing/invalid")
    if type(anchor.get("new_commits_for_key")) is not int or anchor["new_commits_for_key"]<0:
        errors.append("Fabric new-commit observation missing/invalid")
    if not hex64(row.get("outbox_post_digest_sha256")) or not isinstance(row.get("outbox_post_canonical_json"),str):
        errors.append("post-tamper sealed outbox readback missing")
    for name in ("baseline","current","restored"):
        if condition=="UNCHANGED" and name=="restored":continue
        errors += [name+": "+e for e in compare_snapshot(row.get(name),key,event_key)]
    try:
        latency=float(row.get("verification_time_ms"))
        if not math.isfinite(latency) or latency<0:raise ValueError()
    except (ValueError,TypeError,OverflowError):
        errors.append("nonnegative verification time missing")
        latency=None
    if errors:return {**core,"status":"INVALID","errors":errors,"source_event_key":key}
    def phase(name:str)->dict[str,Any]:
        return row[name]["recomputed"]
    original=orig["digest_sha256"]
    before=phase("baseline")["digest_sha256"]
    current=phase("current")["digest_sha256"]
    restored=phase("restored")["digest_sha256"] if condition=="TAMPERED" else None
    before_doc=parse_json(phase("baseline")["canonical_json"])
    after_doc=parse_json(phase("current")["canonical_json"])
    problems=[]
    if anchor["after_digest_sha256"]!=original:
        problems.append("Fabric anchor changed during controlled trial")
    if anchor["new_commits_for_key"]!=0:
        problems.append("unexpected new Fabric commit during controlled trial")
    if row["outbox_post_digest_sha256"]!=original or row["outbox_post_canonical_json"]!=orig["canonical_json"]:
        problems.append("immutable sealed outbox changed during controlled trial")
    if before!=original or phase("baseline")["canonical_json"]!=orig["canonical_json"]:
        problems.append("pre-tamper live source did not match original sealed Fabric evidence")
    if condition=="UNCHANGED":
        if current!=original or phase("current")["canonical_json"]!=orig["canonical_json"]:
            problems.append("unchanged source falsely differs from original")
    else:
        prior=before_doc["payload"]["decoded_payload"]
        after=after_doc["payload"]["decoded_payload"]
        if set(prior)!=set(after) or any(prior[k]!=after[k] for k in prior if k!="temperature_c"):
            return {**core,"status":"INVALID","errors":["tamper changed fields other than temperature_c"],"source_event_key":key}
        if (type(prior.get("temperature_c")) not in (int,float)
                or type(after.get("temperature_c")) not in (int,float)
                or not math.isclose(after["temperature_c"]-prior["temperature_c"],10,abs_tol=1e-9,rel_tol=0)):
            return {**core,"status":"INVALID","errors":["tamper did not change temperature_c by +10 Cel"],"source_event_key":key}
        # All other canonical evidence fields are frozen across tamper.
        c1=dict(before_doc);c2=dict(after_doc)
        c1["payload"]=dict(c1["payload"]);c2["payload"]=dict(c2["payload"])
        c1["payload"]["decoded_payload"]=dict(prior)
        c2["payload"]["decoded_payload"]=dict(after)
        del c1["payload"]["decoded_payload"]["temperature_c"]
        del c2["payload"]["decoded_payload"]["temperature_c"]
        if c1!=c2:
            return {**core,"status":"INVALID","errors":["tamper changed non-selected canonical evidence field"],"source_event_key":key}
        if current==original:
            problems.append("tamper not detected: current-source digest equals original")
        if restored!=original or phase("restored")["canonical_json"]!=orig["canonical_json"]:
            problems.append("current source not restored to sealed baseline")
    return {**core,"status":"FAIL" if problems else "PASS","errors":problems,
            "source_event_key":key,"verification_time_ms":latency,
            "false_negative":condition=="TAMPERED" and current==original,
            "false_positive":condition=="UNCHANGED" and current!=original,
            "restoration_failed":condition=="TAMPERED" and restored!=original}

def validate(evidence:Any)->dict[str,Any]:
    errors=[]
    if not isinstance(evidence,dict):
        return {"test_id":"I2","status":"INVALID","errors":["invalid top-level evidence"],"counted_research":False}
    if evidence.get("test_id")!="I2" or evidence.get("schema_version")!=SCHEMA:
        errors.append("I2 production v1 schema/test ID mismatch")
    if type(evidence.get("formal")) is not bool:errors.append("formal must be boolean")
    n=evidence.get("attempts_per_condition")
    if type(n) is not int or n not in range(1,11) or (evidence.get("formal") is True and n!=10):
        errors.append("formal I2 requires 10 unchanged + 10 tampered")
    groups=evidence.get("conditions")
    if not isinstance(groups,dict) or set(groups)!=set(CONDITIONS):
        errors.append("exactly UNCHANGED/TAMPERED groups required")
    if errors:
        return {"test_id":"I2","status":"INVALID","errors":errors,"counted_research":False}
    ids=set();seqs=set();rows=[]
    for condition in CONDITIONS:
        trials=groups[condition]
        if not isinstance(trials,list) or len(trials)!=n:
            errors.append(f"{condition}: expected {n} trials")
            continue
        for i,item in enumerate(trials,1):
            result=score(item,condition,i);rows.append(result)
            if not isinstance(item,dict):continue
            key,seq=item.get("source_event_key"),item.get("test_sequence")
            if not isinstance(key,str) or not key or type(seq) is not int or seq<0 or key in ids or seq in seqs:
                errors.append(f"{condition}/{i}: duplicated/missing identity or sequence")
            ids.add(key);seqs.add(seq)
    status="INVALID" if errors or any(x["status"]=="INVALID" for x in rows) else "FAIL" if any(x["status"]=="FAIL" for x in rows) else "PASS"
    groups_summary={}
    for name in CONDITIONS:
        sub=[r for r in rows if r["condition"]==name]
        times=[r["verification_time_ms"] for r in sub if "verification_time_ms" in r]
        groups_summary[name]={"passed":sum(r["status"]=="PASS" for r in sub),
            "failed":sum(r["status"]=="FAIL" for r in sub),
            "invalid":sum(r["status"]=="INVALID" for r in sub),
            "mean_verification_time_ms":statistics.mean(times) if times else None,
            "sample_sd_verification_time_ms":statistics.stdev(times) if len(times)>1 else None}
    return {"test_id":"I2","status":status,"errors":errors,"trials":rows,
            "conditions":groups_summary,
            "false_negative_count":sum(r.get("false_negative",False) for r in rows),
            "false_positive_count":sum(r.get("false_positive",False) for r in rows),
            "restoration_failure_count":sum(r.get("restoration_failed",False) for r in rows),
            "counted_research":False,"qualification":"SUPPLIED_EVIDENCE_VALIDATION_ONLY"}

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    if a.evidence.resolve()==a.output.resolve():raise ValueError("cannot overwrite source evidence")
    result=validate(parse_json(a.evidence.read_text(encoding="utf-8")))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(f"I2_EVIDENCE_CHECK={result['status']} CODE_ONLY_SCORER=1")
    print(f"I2_RESULT={a.output}")
    return 0 if result["status"]=="PASS" else 2
if __name__=="__main__":
    try:raise SystemExit(main())
    except (OSError,ValueError,TypeError) as exc:
        print(f"ERROR={exc}",file=sys.stderr);raise SystemExit(1)
