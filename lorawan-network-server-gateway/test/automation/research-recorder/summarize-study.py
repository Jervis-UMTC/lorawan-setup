#!/usr/bin/env python3
"""Build Chapter-IV table-ready study summaries strictly from sealed recorder evidence.

Rules:
- smoke, rehearsal, underscore-prefixed support directories, errored runs, and INVALID_PILOT runs never count.
- missing observations remain NOT_MEASURED; no value is inferred from prose.
- normal-operation latency is explicitly application-event -> database unless another measured boundary is recorded.
"""
from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "chapter4-results"
OUT = ROOT / "summaries"
OUT.mkdir(parents=True, exist_ok=True)

GROUP_ALIASES = {
    "normal-operation": ["normal-operation"],
    "authentication": ["authentication", "authentication-access-control"],
    "replay-spoofing": ["replay-spoofing", "replay", "spoofing"],
    "integrity": ["integrity", "data-integrity"],
    "traceability": ["traceability"],
    "flooding": ["dos-flooding", "flooding", "dos"],
    "resilience": ["resilience-recovery", "resilience", "recovery"],
}

REQUIREMENTS = {
    "normal-operation": {"unit":"runs", "required":3, "records":"~120 scheduled uplinks/run", "method":"3 x 30 min"},
    "authentication": {"unit":"trials", "required":90, "records":"3 layers x 3 conditions x 10", "method":"90 decisions"},
    "replay-spoofing": {"unit":"trials", "required":40, "records":"10 legitimate + 10 replay + 10 genuine + 10 invalid-MIC", "method":"40 decisions"},
    "integrity": {"unit":"trials", "required":40, "records":"10 unchanged app + 10 altered app + 10 unchanged stored + 10 tampered stored", "method":"40 verifications"},
    "traceability": {"unit":"trials", "required":20, "records":"20 trials / 60 records", "method":"10 individual + 10 histories x 5"},
    "flooding": {"unit":"runs", "required":18, "records":"2 attack types x 3 levels x 3 repetitions", "method":"18 x (5 min load + 5 min recovery)"},
    "resilience": {"unit":"runs", "required":3, "records":"~480 uplinks/run", "method":"3 x (30m normal + 60m outage + 30m recovery)"},
}

AUTH_CONDITIONS = [
    ("LoRaWAN","correct OTAA"),("LoRaWAN","wrong AppKey"),("LoRaWAN","unregistered DevEUI"),
    ("MQTT","allowed"),("MQTT","wrong password"),("MQTT","prohibited topic"),
    ("Fabric","authorized"),("Fabric","non-writer"),("Fabric","invalid identity"),
]
REPLAY_CONDITIONS = [("replay/spoofing",x) for x in ("legitimate","replay","genuine","invalid-MIC")]
INTEGRITY_CONDITIONS = [("application", "unchanged"),("application","altered"),("stored","unchanged"),("stored","tampered")]
FLOOD_CONDITIONS = [(attack, level) for attack in ("invalid connection flood","invalid application-message flood") for level in ("normal 0/s","moderate 10/s","high 50/s")]
RESILIENCE_PERIODS = ["normal","Fabric outage","recovery"]


def read_text(path: Path) -> str:
    try: return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError: return ""


def read_json(path: Path):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return {}


def read_csv(path: Path):
    if not path.exists(): return []
    with path.open(newline="", encoding="utf-8-sig") as f: return list(csv.DictReader(f))


def parse_time(s: str):
    s=(s or "").strip().replace("Z","+00:00")
    try: return datetime.fromisoformat(s)
    except Exception: return None


def mean_sd(vals):
    vals=[float(x) for x in vals if x not in (None,"")]
    if not vals: return ("","")
    return (sum(vals)/len(vals), statistics.stdev(vals) if len(vals)>1 else 0.0)


def pct(n,d):
    return "" if not d else 100.0*n/d


def marker_invalid(run: Path) -> bool:
    for f in [run/"raw"/"markers.csv", run/"raw"/"markers.txt", run/"metadata"/"markers.txt"]:
        if "INVALID_PILOT" in read_text(f): return True
    # generic bounded scan of marker-like files only
    for f in run.rglob("*marker*"):
        if f.is_file() and "INVALID_PILOT" in read_text(f): return True
    return False


def is_valid_run(run: Path) -> tuple[bool,str]:
    status=read_text(run/"derived"/"run-status.txt")
    if not status: return False,"NO_RUN_STATUS"
    if status == "RECORDED_WITH_ERRORS": return False,"RECORDED_WITH_ERRORS"
    if (run/"metadata"/"stop-errors.txt").exists(): return False,"STOP_ERRORS_PRESENT"
    if marker_invalid(run): return False,"INVALID_PILOT"
    if not (run/"metadata"/"SHA256SUMS.csv").exists(): return False,"UNSEALED"
    return True,status


def group_dirs(name):
    out=[]
    for alias in GROUP_ALIASES[name]:
        d=ROOT/alias
        if d.exists():
            out.extend(x for x in d.iterdir() if x.is_dir() and not x.name.startswith("_") and "rehearsal" not in x.name.lower())
    return sorted(set(out))


def valid_group(name):
    return [(r,reason) for r in group_dirs(name) for ok,reason in [is_valid_run(r)] if ok]


def all_run_inventory():
    rows=[]
    for group in REQUIREMENTS:
        for r in group_dirs(group):
            ok, reason=is_valid_run(r)
            trials=read_csv(r/"derived"/"trial-results.csv")
            rows.append({"group":group,"run_id":r.name,"countable":"YES" if ok else "NO","reason":reason,"trial_rows":len(trials),"path":str(r.relative_to(ROOT))})
    return rows


def write_csv(name, fields, rows):
    path=OUT/name
    with path.open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    return path


def normal_rows():
    rows=[]
    for run,_ in valid_group("normal-operation"):
        s=read_json(run/"derived"/"run-summary.json")
        meta=read_json(run/"metadata"/"run-meta.json")
        start=parse_time(meta.get("start_utc") or read_text(run/"metadata"/"start-utc.txt"))
        end=parse_time(read_text(run/"metadata"/"end-utc.txt"))
        minutes=(end-start).total_seconds()/60 if start and end and end>start else None
        source=s.get("source",{}); corr=s.get("correlation",{}); tel=s.get("telemetry",{}); fab=s.get("fabric_outbox",{}); res=s.get("resources",{})
        attempts=corr.get("eligible_source_attempts_in_db_export_window") or source.get("attempts") or 0
        accepted=corr.get("eligible_exact_payload_matches") or corr.get("exact_payload_matches") or 0
        formal_pdr=tel.get("formal_chapter3_pdr_percent")
        pdr_status=tel.get("formal_chapter3_pdr_status") or "WITHHELD_NOT_DERIVED"
        # authoritative submitted means an actual submission boundary is represented by submitted_at or a confirmed row.
        outbox=read_csv(run/"raw"/"fabric-outbox.csv")
        submitted=[x for x in outbox if (x.get("submitted_at") or x.get("committed_at") or (x.get("status") or "").lower()=="confirmed")]
        confirmed=[x for x in outbox if (x.get("status") or "").lower()=="confirmed" and x.get("committed_at")]
        latency=tel.get("application_event_to_db_ms",{})
        rows.append({
            "run_id":run.name,"duration_minutes":round(minutes,3) if minutes else "",
            "scheduled_source_attempts":attempts,"unique_legitimate_stored":accepted,
            "formal_chapter3_pdr_percent":round(float(formal_pdr),3) if formal_pdr is not None else "",
            "database_delivery_percent":round(pct(accepted,attempts),3) if attempts else "",
            "pdr_status":pdr_status,
            "latency_boundary":"application_event_to_database","mean_latency_ms":latency.get("mean",""),"latency_sd_ms":latency.get("sd_sample",""),
            "fabric_submitted":len(submitted),"fabric_confirmed":len(confirmed),"fabric_tsr_percent":round(pct(len(confirmed),len(submitted)),3) if submitted else "",
            "throughput_unique_stored_per_min":round(accepted/minutes,3) if minutes else "",
            "server_ulc01_cpu_mean_percent":res.get("ulc01",{}).get("cpu_percent",{}).get("mean",""),
            "server_ulc01_memory_mean_percent":res.get("ulc01",{}).get("memory_percent",{}).get("mean",""),
            "gateway_cpu_mean_percent":res.get("gateway",{}).get("cpu_percent",{}).get("mean",""),
            "gateway_memory_mean_percent":res.get("gateway",{}).get("memory_percent",{}).get("mean",""),
            "rssi_mean_dbm":tel.get("rssi_dbm",{}).get("mean",""),"snr_mean_db":tel.get("snr_db",{}).get("mean",""),
            "duplicates":tel.get("duplicate_event_rows",""),"evidence_manifest":"metadata/SHA256SUMS.csv",
        })
    return rows


def trial_rows(group):
    rows=[]
    for run,_ in valid_group(group):
        for r in read_csv(run/"derived"/"trial-results.csv"):
            r=dict(r); r["run_id"]=run.name
            try: r["obs"]=json.loads(r.get("observations_json") or "{}")
            except Exception: r["obs"]={}
            rows.append(r)
    return rows


def status_counts(rows):
    c=Counter((r.get("status") or "").strip().lower() for r in rows)
    fa=sum(v for k,v in c.items() if k in {"false_acceptance","false-acceptance","fa"})
    fr=sum(v for k,v in c.items() if k in {"false_rejection","false-rejection","fr"})
    correct=sum(v for k,v in c.items() if k in {"pass","correct","allowed","rejected","match"})
    return c,correct,fa,fr


def yn_count(rows,key):
    vals=[r.get(key,"").strip().lower() for r in rows]
    yes=sum(v in {"yes","true","1","allowed","accepted","created","reached"} for v in vals)
    no=sum(v in {"no","false","0","rejected","blocked","not_created","not_reached"} for v in vals)
    return yes,no


def obs_sum(rows,key):
    vals=[]
    for r in rows:
        v=r.get("obs",{}).get(key)
        if isinstance(v,bool): vals.append(int(v))
        elif isinstance(v,(int,float)): vals.append(v)
    return sum(vals) if vals else ""


def obs_true(rows,key):
    vals=[r.get("obs",{}).get(key) for r in rows if key in r.get("obs",{})]
    if not vals: return ""
    return sum(v is True or str(v).lower() in {"true","yes","1","pass","match"} for v in vals)


def decision_stats(rows):
    vals=[]
    for r in rows:
        try:
            if r.get("decision_time_seconds") not in (None,""): vals.append(float(r["decision_time_seconds"]))
        except Exception: pass
    m,sd=mean_sd(vals); return m,sd


def aggregate_by_condition(group, templates, table):
    trs=trial_rows(group); out=[]
    for area,cond in templates:
        selected=[r for r in trs if cond.lower() in (r.get("test_condition") or "").lower() and (area.lower() in (r.get("test_condition") or "").lower() or area in {"replay/spoofing","application","stored"})]
        # fallback exact condition match if operator used concise condition text
        if not selected: selected=[r for r in trs if (r.get("test_condition") or "").strip().lower()==cond.lower()]
        c,correct,fa,fr=status_counts(selected); m,sd=decision_stats(selected)
        if table==12:
            allowed,_=yn_count(selected,"chirpstack_accepted"); rejected_yes,_=yn_count(selected,"chirpstack_rejected")
            unauth=obs_sum(selected,"unauthorized_state_change")
            out.append({"test_layer":area,"condition":cond,"trials":len(selected),"required_trials":10,"expected":selected[0].get("expected_result","") if selected else "NOT_MEASURED","allowed":allowed,"rejected":rejected_yes,"correct_decisions":correct,"correct_percent":round(pct(correct,len(selected)),3) if selected else "","false_acceptance":fa,"false_rejection":fr,"unauthorized_state_change":unauth,"mean_response_seconds":m,"sd_response_seconds":sd,"status":"COMPLETE" if len(selected)>=10 else "NOT_MEASURED"})
        elif table==13:
            gw,_=yn_count(selected,"gateway_received"); acc,_=yn_count(selected,"chirpstack_accepted"); rej,_=yn_count(selected,"chirpstack_rejected"); app,_=yn_count(selected,"application_reached"); db,_=yn_count(selected,"database_created"); ob,_=yn_count(selected,"outbox_created")
            out.append({"test":area,"condition":cond,"trials":len(selected),"required_trials":10,"expected":selected[0].get("expected_result","") if selected else "NOT_MEASURED","received_gateway":gw,"accepted_chirpstack":acc,"rejected_chirpstack":rej,"reached_application":app,"database_created":db,"fabric_tx_created":ob,"correct_decisions":correct,"correct_percent":round(pct(correct,len(selected)),3) if selected else "","false_acceptance":fa,"false_rejection":fr,"mean_decision_seconds":m,"sd_decision_seconds":sd,"status":"COMPLETE" if len(selected)>=10 else "NOT_MEASURED"})
        elif table==14:
            hm=obs_true(selected,"hash_match"); hmis=obs_true(selected,"hash_mismatch"); unauth=obs_sum(selected,"unauthorized_storage")
            out.append({"test_area":area,"condition":cond,"trials":len(selected),"required_trials":10,"expected":selected[0].get("expected_result","") if selected else "NOT_MEASURED","hash_match":hm,"hash_mismatch":hmis,"correct_decisions":correct,"correct_percent":round(pct(correct,len(selected)),3) if selected else "","false_positive":fa,"false_negative":fr,"unauthorized_storage":unauth,"mean_verification_seconds":m,"sd_verification_seconds":sd,"status":"COMPLETE" if len(selected)>=10 else "NOT_MEASURED"})
    return out


def traceability_rows():
    trs=trial_rows("traceability"); grouped=defaultdict(list)
    for r in trs: grouped[(r.get("test_condition") or "traceability").strip()].append(r)
    if not grouped: grouped={"individual record":[],"five-record history":[]}
    out=[]
    for cond,rows in grouped.items():
        m,sd=decision_stats(rows)
        records=obs_sum(rows,"records_tested"); retrieved=obs_sum(rows,"records_retrieved"); complete=obs_true(rows,"complete"); links=obs_sum(rows,"correct_db_fabric_links"); chrono=obs_true(rows,"chronology_correct"); missing=obs_sum(rows,"missing"); dup=obs_sum(rows,"duplicate")
        required=10
        out.append({"test":cond,"trials":len(rows),"required_trials":required,"records_tested":records,"successfully_retrieved":retrieved,"retrieval_percent":round(pct(retrieved,records),3) if isinstance(records,(int,float)) and records else "","complete":complete,"correct_db_fabric_links":links,"chronology_correct":chrono,"missing":missing,"duplicate":dup,"mean_retrieval_seconds":m,"sd_retrieval_seconds":sd,"status":"COMPLETE" if len(rows)>=required else "NOT_MEASURED"})
    return out


def flooding_rows():
    trs=trial_rows("flooding"); out=[]
    for attack,level in FLOOD_CONDITIONS:
        selected=[r for r in trs if attack.lower() in (r.get("test_condition") or "").lower() and level.split()[0].lower() in (r.get("test_condition") or "").lower()]
        valid=obs_sum(selected,"valid_delivered"); valid_expected=obs_sum(selected,"valid_expected"); invrej=obs_sum(selected,"invalid_rejected"); invgen=obs_sum(selected,"invalid_generated"); rec=[]
        for r in selected:
            v=r.get("obs",{}).get("recovery_seconds")
            if isinstance(v,(int,float)): rec.append(v)
        rm,rsd=mean_sd(rec)
        def om(k):
            vals=[r.get("obs",{}).get(k) for r in selected if isinstance(r.get("obs",{}).get(k),(int,float))]
            return mean_sd(vals)[0]
        out.append({"test_area":attack,"condition":level,"runs":len(selected),"required_runs":3,"valid_messages_delivered":valid,"valid_expected":valid_expected,"valid_delivery_percent":round(pct(valid,valid_expected),3) if isinstance(valid,(int,float)) and isinstance(valid_expected,(int,float)) and valid_expected else "","invalid_traffic_rejected":invrej,"invalid_generated":invgen,"invalid_rejection_percent":round(pct(invrej,invgen),3) if isinstance(invrej,(int,float)) and isinstance(invgen,(int,float)) and invgen else "","mean_latency_ms":om("mean_latency_ms"),"mean_server_cpu_percent":om("server_cpu_percent"),"mean_server_memory_percent":om("server_memory_percent"),"mean_gateway_cpu_percent":om("gateway_cpu_percent"),"mean_gateway_memory_percent":om("gateway_memory_percent"),"service_available_count":obs_true(selected,"service_available"),"unauthorized_records":obs_sum(selected,"unauthorized_records"),"mean_recovery_seconds":rm,"sd_recovery_seconds":rsd,"status":"COMPLETE" if len(selected)>=3 else "NOT_MEASURED"})
    return out


def resilience_rows():
    trs=trial_rows("resilience"); out=[]
    for period in RESILIENCE_PERIODS:
        selected=[r for r in trs if period.lower() in (r.get("test_condition") or "").lower()]
        def sm(k): return obs_sum(selected,k)
        rec=[]
        for r in selected:
            v=r.get("obs",{}).get("recovery_seconds")
            if isinstance(v,(int,float)): rec.append(v)
        rm,rsd=mean_sd(rec)
        lat=[r.get("obs",{}).get("mean_latency_ms") for r in selected if isinstance(r.get("obs",{}).get("mean_latency_ms"),(int,float))]
        lm,lsd=mean_sd(lat)
        out.append({"period":period,"runs":len(selected),"required_runs":3,"duration_minutes_across_runs":sm("duration_minutes"),"expected_readings":sm("expected_readings"),"db_stored":sm("db_stored"),"db_stored_percent":round(pct(sm("db_stored"),sm("expected_readings")),3) if isinstance(sm("expected_readings"),(int,float)) and sm("expected_readings") else "","missing":sm("missing"),"duplicate":sm("duplicate"),"local_services_available":obs_true(selected,"local_services_available"),"fabric_queued":sm("fabric_queued"),"fabric_confirmed_after_recovery":sm("fabric_confirmed_after_recovery"),"mean_latency_ms":lm,"sd_latency_ms":lsd,"mean_recovery_seconds":rm,"sd_recovery_seconds":rsd,"status":"COMPLETE" if len(selected)>=3 else "NOT_MEASURED"})
    return out


def main():
    inventory=all_run_inventory()
    write_csv("run-inventory.csv",["group","run_id","countable","reason","trial_rows","path"],inventory)

    normal=normal_rows()
    write_csv("normal-operation.csv",["run_id","duration_minutes","scheduled_source_attempts","unique_legitimate_stored","formal_chapter3_pdr_percent","database_delivery_percent","pdr_status","latency_boundary","mean_latency_ms","latency_sd_ms","fabric_submitted","fabric_confirmed","fabric_tsr_percent","throughput_unique_stored_per_min","server_ulc01_cpu_mean_percent","server_ulc01_memory_mean_percent","gateway_cpu_mean_percent","gateway_memory_mean_percent","rssi_mean_dbm","snr_mean_db","duplicates","evidence_manifest"],normal)

    t12=aggregate_by_condition("authentication",AUTH_CONDITIONS,12)
    t13=aggregate_by_condition("replay-spoofing",REPLAY_CONDITIONS,13)
    t14=aggregate_by_condition("integrity",INTEGRITY_CONDITIONS,14)
    t15=traceability_rows(); t16=flooding_rows(); t17=resilience_rows()
    write_csv("table-12-authentication.csv",list(t12[0].keys()),t12)
    write_csv("table-13-replay-spoofing.csv",list(t13[0].keys()),t13)
    write_csv("table-14-integrity.csv",list(t14[0].keys()),t14)
    write_csv("table-15-traceability.csv",list(t15[0].keys()),t15)
    write_csv("table-16-flooding.csv",list(t16[0].keys()),t16)
    write_csv("table-17-resilience.csv",list(t17[0].keys()),t17)

    counted={
        "normal-operation":len(normal),
        "authentication":len(trial_rows("authentication")),
        "replay-spoofing":len(trial_rows("replay-spoofing")),
        "integrity":len(trial_rows("integrity")),
        "traceability":len(trial_rows("traceability")),
        "flooding":sum(1 for r,_ in valid_group("flooding")),
        "resilience":sum(1 for r,_ in valid_group("resilience")),
    }
    ready=[]
    for group,req in REQUIREMENTS.items():
        n=counted[group]; need=req["required"]
        ready.append({"test_area":group,"count_unit":req["unit"],"required":need,"countable_completed":n,"remaining":max(0,need-n),"status":"COMPLETE" if n>=need else "INCOMPLETE","methodology":req["method"],"record_basis":req["records"]})
    write_csv("test-readiness.csv",["test_area","count_unit","required","countable_completed","remaining","status","methodology","record_basis"],ready)
    (OUT/"study-summary.json").write_text(json.dumps({"requirements":REQUIREMENTS,"counted":counted,"readiness":ready,"normal_runs":normal},indent=2),encoding="utf-8")
    print(f"STUDY_SUMMARY_DIR={OUT}")
    for r in ready: print(f"{r['test_area']}|{r['countable_completed']}/{r['required']}|{r['status']}")

if __name__ == "__main__": main()
