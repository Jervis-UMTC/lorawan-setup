#!/usr/bin/env python3
"""LoRaWAN-side shared-manifest utility for synchronized Fabric research tests."""
from __future__ import annotations
import argparse,base64,hashlib,importlib.util,json,os
from datetime import datetime,timezone,timedelta
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[3]
CONTRACT=ROOT/"test"/"automation"/"research_contract.py"
def _load_contract():
 spec=importlib.util.spec_from_file_location("research_contract",CONTRACT)
 if spec is None or spec.loader is None: raise RuntimeError("cannot import research contract")
 m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
RC=_load_contract(); RC.validate_static_contract()
SCHEMA_VERSION="1.0"; STUDY_ID="zacharias-lorawan-fabric"; AUTH_SOURCE="lorawan-gateway-evidence"
JOINT={"P1","P2","R1","R2","A1","A2","I1","I2","I3","T1","T2"}
REQUIRED={"P1","P2","R2","A2","I1","I2","I3","T1","T2"}
STATUSES={"COMMITTED","REJECTED","UNAVAILABLE","DUPLICATE_SAME_HASH","CONFLICT_REJECTED","UNKNOWN"}

def now()->str:return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z")
def canonical(v:Any)->bytes:return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def write_json(p:Path,v:Any)->None:
 p.parent.mkdir(parents=True,exist_ok=True); t=p.with_suffix(p.suffix+".tmp")
 t.write_text(json.dumps(v,indent=2,sort_keys=True)+"\n",encoding="utf-8"); os.replace(t,p)
def seal(p:Path,v:Any)->str:
 write_json(p,v); d=sha(canonical(v)); p.with_suffix(p.suffix+".sha256").write_text(d+"\n",encoding="ascii"); return d
def load(p:Path)->Any:return json.loads(p.read_text(encoding="utf-8"))
def verify(p:Path)->str:
 d=sha(canonical(load(p))); e=p.with_suffix(p.suffix+".sha256").read_text(encoding="ascii").strip()
 if d!=e: raise RuntimeError(f"manifest SHA mismatch: {p}")
 return d

def prepare_run(a)->int:
 tid=a.test_id.upper()
 if tid not in JOINT: raise RuntimeError(f"unsupported joint test {tid}")
 rid=a.run_id or f"{tid}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
 d=Path(a.run_dir) if a.run_dir else ROOT/"chapter4-results"/"joint-fabric"/rid
 d.mkdir(parents=True,exist_ok=False); (d/"markers").mkdir()
 m={"schema_version":SCHEMA_VERSION,"study_id":STUDY_ID,"test_id":tid,"run_id":rid,
    "repetition":a.repetition,"created_at_utc":now(),"duration_seconds":a.duration_seconds,
    "workload":{"target_tps":a.target_tps,"interval_ms":(1000/a.target_tps if a.target_tps else None),
                "planned_record_count":a.planned_record_count,"schedule_epoch_utc":a.schedule_epoch_utc},
    "requested_fabric_action":a.fabric_action,"authenticated_source_system_id":AUTH_SOURCE,
    "fabric_required":tid in REQUIRED,"formal":bool(a.formal)}
 h=seal(d/"run-manifest.json",m); write_json(d/"records-working.json",{"records":[]})
 print(f"RUN_DIR={d}\nRUN_ID={rid}\nRUN_MANIFEST_SHA256={h}"); return 0

def register(a)->int:
 d=Path(a.run_dir); verify(d/"run-manifest.json"); w=load(d/"records-working.json")
 if a.payload_file: payload=Path(a.payload_file).read_bytes()
 elif a.payload_base64: payload=base64.b64decode(a.payload_base64,validate=True)
 else: payload=canonical(json.loads(a.payload_json))
 r={"trial_id":a.trial_id,"source_record_id":a.source_record_id,"authenticated_source_system_id":AUTH_SOURCE,
    "source_type":a.source_type,"producer":a.producer,"produced_at_utc":a.produced_at_utc or now(),
    "schema_version":a.record_schema_version,"exact_payload_base64":base64.b64encode(payload).decode(),
    "payload_sha256":sha(payload),"expected_fabric_status":a.expected_fabric_status}
 if any(x["trial_id"]==r["trial_id"] or x["source_record_id"]==r["source_record_id"] for x in w["records"]):
  raise RuntimeError("duplicate trial_id/source_record_id")
 w["records"].append(r); write_json(d/"records-working.json",w); print(json.dumps(r,sort_keys=True)); return 0

def seal_records(a)->int:
 d=Path(a.run_dir); rh=verify(d/"run-manifest.json"); rows=load(d/"records-working.json")["records"]
 if not rows and not a.allow_empty: raise RuntimeError("cannot seal empty records")
 if len({r["trial_id"] for r in rows})!=len(rows) or len({r["source_record_id"] for r in rows})!=len(rows):
  raise RuntimeError("duplicate record identity")
 v={"schema_version":SCHEMA_VERSION,"study_id":STUDY_ID,"run_manifest_sha256":rh,
    "sealed_at_utc":now(),"record_count":len(rows),"records":rows}
 h=seal(d/"record-manifest.json",v); print(f"RECORD_COUNT={len(rows)}\nRECORD_MANIFEST_SHA256={h}"); return 0

def marker(a)->int:
 d=Path(a.run_dir); m=load(d/"run-manifest.json"); rh=verify(d/"run-manifest.json")
 v={"schema_version":SCHEMA_VERSION,"study_id":STUDY_ID,"test_id":m["test_id"],"run_id":m["run_id"],
    "phase":a.phase,"event":a.event,"at_utc":now(),"run_manifest_sha256":rh}
 name=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")+f"-{a.phase}-{a.event}.json"
 p=d/"markers"/name; seal(p,v); print(f"MARKER={p}"); return 0

def p2_payload(session,pair,n,rate,rep)->bytes:
 return canonical({"kind":"P2_FABRIC_BENCHMARK","schema_version":"1.0","session_id":session,
  "pair_id":pair,"sequence":n,"target_tps":rate,"repetition":rep,
  "sensor":{"device_id":"P2-SYNTHETIC","soil_moisture_pct":40+(n%200)/100,
            "temperature_c":25+(n%100)/100}})

def prepare_p2(a)->int:
 formal=not a.rehearsal
 rates=tuple(RC.FORMAL["P2"]["rates_tps"])
 if formal:
  if a.seconds!=RC.FORMAL["P2"]["duration_seconds"] or a.repetitions!=RC.FORMAL["P2"]["repetitions"]:
   raise RuntimeError("formal P2 is locked to 300 seconds x 3 repetitions; use --rehearsal for shortened commissioning")
 else:
  if a.seconds < 1 or a.repetitions < 1: raise RuntimeError("rehearsal seconds/repetitions must be >=1")
 session=a.session_id or "P2-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
 root=Path(a.output_root)/session; root.mkdir(parents=True,exist_ok=False); pairs=[]
 for rate in rates:
  count=max(1,int(round(rate*a.seconds)))
  for rep in range(1,a.repetitions+1):
   label="0p0667" if rate<1 else str(int(rate)); pid=f"{session}-r{label}-rep{rep}"; d=root/pid; d.mkdir()
   epoch=datetime.now(timezone.utc)+timedelta(seconds=5)
   if formal:
    order=tuple(x.lower() for x in RC.P2_PAIR_ORDER[rep])
   else:
    order=("control","fabric") if rep % 2 else ("fabric","control")
   rm={"schema_version":SCHEMA_VERSION,"study_id":STUDY_ID,"test_id":"P2","run_id":pid,"repetition":rep,
       "created_at_utc":now(),"duration_seconds":a.seconds,
       "workload":{"target_tps":rate,"interval_ms":1000/rate,"planned_record_count":count,
                   "schedule_epoch_utc":epoch.isoformat(timespec="milliseconds").replace("+00:00","Z"),
                   "pair_order":order},"requested_fabric_action":"P2_MATCHED_CONTROL_AND_FABRIC",
       "authenticated_source_system_id":AUTH_SOURCE,"fabric_required":True,"formal":formal}
   rh=seal(d/"run-manifest.json",rm); rows=[]
   for i in range(count):
    payload=p2_payload(session,pid,i+1,rate,rep)
    rows.append({"trial_id":f"{pid}-t{i+1:05d}","source_record_id":f"research:p2:{pid}:{i+1:05d}",
      "authenticated_source_system_id":AUTH_SOURCE,"source_type":"research-benchmark","producer":"lorawan-research-p2",
      "produced_at_utc":(epoch+timedelta(seconds=i/rate)).isoformat(timespec="milliseconds").replace("+00:00","Z"),
      "schema_version":"1.0","exact_payload_base64":base64.b64encode(payload).decode(),"payload_sha256":sha(payload),
      "expected_fabric_status":"COMMITTED"})
   mh=seal(d/"record-manifest.json",{"schema_version":SCHEMA_VERSION,"study_id":STUDY_ID,"run_manifest_sha256":rh,
        "sealed_at_utc":now(),"record_count":len(rows),"records":rows})
   pairs.append({"pair_id":pid,"rate_tps":rate,"repetition":rep,"pair_order":order,
                 "planned_record_count":count,"run_manifest_sha256":rh,"record_manifest_sha256":mh})
 total=sum(x["planned_record_count"] for x in pairs)
 if formal and total != 14460: raise RuntimeError(f"formal P2 record total drifted: {total}")
 h=seal(root/"p2-session.json",{"schema_version":SCHEMA_VERSION,"study_id":STUDY_ID,"test_id":"P2",
       "session_id":session,"formal":formal,"seconds":a.seconds,"repetitions":a.repetitions,"pairs":pairs})
 print(f"P2_SESSION_DIR={root}\nP2_SESSION_SHA256={h}\nP2_FORMAL={int(formal)}\nP2_PAIR_COUNT={len(pairs)}\nP2_TOTAL_RECORDS={total}"); return 0

def ndjson(p:Path)->list[dict]:
 out=[]
 for n,line in enumerate(p.read_text(encoding="utf-8").splitlines(),1):
  if line.strip():
   try: out.append(json.loads(line))
   except Exception as e: raise RuntimeError(f"{p}:{n}: {e}") from e
 return out

def verify_export(a)->int:
 d=Path(a.run_dir); run=load(d/"run-manifest.json"); rh=verify(d/"run-manifest.json")
 rec=load(d/"record-manifest.json"); mh=verify(d/"record-manifest.json"); exp={x["source_record_id"]:x for x in rec["records"]}
 rows=ndjson(Path(a.transactions)); seen={}; errors=[]
 for x in rows:
  sid=x.get("source_record_id")
  if sid not in exp: errors.append(f"unknown source_record_id {sid}"); continue
  if sid in seen: errors.append(f"duplicate result row {sid}"); continue
  seen[sid]=x; e=exp[sid]
  for k in ("trial_id","payload_sha256"):
   if x.get(k)!=e.get(k): errors.append(f"{sid}: {k} mismatch")
  if x.get("run_id")!=run["run_id"]: errors.append(f"{sid}: run_id mismatch")
  if x.get("normalized_status") not in STATUSES: errors.append(f"{sid}: invalid status")
  if a.enforce_expected_status and e.get("expected_fabric_status") and x.get("normalized_status")!=e["expected_fabric_status"]:
   errors.append(f"{sid}: expected {e['expected_fabric_status']} got {x.get('normalized_status')}")
 missing=sorted(set(exp)-set(seen))
 if missing and not a.allow_missing: errors.append(f"missing {len(missing)} expected records")
 v={"schema_version":SCHEMA_VERSION,"study_id":STUDY_ID,"test_id":run["test_id"],"run_id":run["run_id"],
    "verified_at_utc":now(),"run_manifest_sha256":rh,"record_manifest_sha256":mh,
    "expected_records":len(exp),"fabric_rows":len(rows),"matched_records":len(seen),"missing_records":missing,
    "status":"PASS" if not errors else "FAIL","errors":errors}
 seal(d/"fabric-import-validation.json",v); print(f"FABRIC_IMPORT_STATUS={v['status']} EXPECTED={len(exp)} MATCHED={len(seen)} MISSING={len(missing)}")
 if errors:
  [print("ERROR="+x,file=__import__("sys").stderr) for x in errors]; return 2
 return 0

def main()->int:
 ap=argparse.ArgumentParser(); sp=ap.add_subparsers(dest="cmd",required=True)
 p=sp.add_parser("prepare-run"); p.add_argument("--test-id",required=True); p.add_argument("--run-id"); p.add_argument("--run-dir")
 p.add_argument("--repetition",type=int,default=1); p.add_argument("--duration-seconds",type=float); p.add_argument("--target-tps",type=float); p.add_argument("--formal",action="store_true")
 p.add_argument("--planned-record-count",type=int); p.add_argument("--schedule-epoch-utc"); p.add_argument("--fabric-action",default="OBSERVE"); p.set_defaults(func=prepare_run)
 p=sp.add_parser("register-record"); p.add_argument("--run-dir",required=True); p.add_argument("--trial-id",required=True); p.add_argument("--source-record-id",required=True)
 p.add_argument("--source-type",required=True); p.add_argument("--producer",required=True); p.add_argument("--produced-at-utc"); p.add_argument("--record-schema-version",default="1.0")
 g=p.add_mutually_exclusive_group(required=True); g.add_argument("--payload-file"); g.add_argument("--payload-base64"); g.add_argument("--payload-json")
 p.add_argument("--expected-fabric-status"); p.set_defaults(func=register)
 p=sp.add_parser("seal-records"); p.add_argument("--run-dir",required=True); p.add_argument("--allow-empty",action="store_true"); p.set_defaults(func=seal_records)
 p=sp.add_parser("marker"); p.add_argument("--run-dir",required=True); p.add_argument("--phase",required=True); p.add_argument("--event",choices=("START","END","MARK"),default="MARK"); p.set_defaults(func=marker)
 p=sp.add_parser("prepare-p2"); p.add_argument("--output-root",default=str(ROOT/"chapter4-results"/"joint-fabric")); p.add_argument("--session-id"); p.add_argument("--seconds",type=int,default=300); p.add_argument("--repetitions",type=int,default=3); p.add_argument("--rehearsal",action="store_true"); p.set_defaults(func=prepare_p2)
 p=sp.add_parser("verify-fabric-export"); p.add_argument("--run-dir",required=True); p.add_argument("--transactions",required=True); p.add_argument("--allow-missing",action="store_true"); p.add_argument("--enforce-expected-status",action="store_true"); p.set_defaults(func=verify_export)
 args=ap.parse_args()
 return int(args.func(args) or 0)
if __name__=="__main__":
 try: raise SystemExit(main())
 except Exception as e: print(f"ERROR={e}",file=__import__("sys").stderr); raise SystemExit(1)
