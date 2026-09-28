#!/usr/bin/env python3
"""Generate a fail-closed implementation/oversight status for every research test."""
from __future__ import annotations
import importlib.util, json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CONTRACT=ROOT/"test"/"automation"/"research_contract.py"
RUNNER=ROOT/"test"/"automation"/"research-manual"/"run_test.py"
OUT_JSON=ROOT/"test"/"automation"/"research-manual"/"OVERSIGHT-STATUS.json"
OUT_MD=ROOT/"test"/"automation"/"research-manual"/"OVERSIGHT-STATUS.md"

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def contains(path,*tokens):
    if not path.is_file():
        return False
    text=path.read_text(encoding="utf-8",errors="replace")
    return all(t in text for t in tokens)

def main():
    rc=load(CONTRACT,"research_contract")
    rc.validate_static_contract()
    runner=load(RUNNER,"research_manual_runner")
    checks={
      "contract_self_validation": True,
      "p2_sync_manifest_and_bad_hash_guard": contains(ROOT/"test"/"automation"/"fabric-sync"/"fabric_sync.py","prepare-p2","verify-fabric-export","payload_sha256","duplicate result row"),
      "p2_open_loop_frozen": rc.FORMAL["P2"]["open_loop_required"] is True,
      "p2_pair_order_frozen": rc.P2_PAIR_ORDER=={1:("CONTROL","FABRIC"),2:("FABRIC","CONTROL"),3:("CONTROL","FABRIC")},
      "r1_lte_no_fallback_contract": rc.FORMAL["R1"]["lte_route_required"] and rc.FORMAL["R1"]["alternate_wan_forbidden"],
      "r1_live_route_gate_implemented": contains(ROOT/"test"/"automation"/"resilience"/"r1_internet_route_gate.py","alternate_default_routes","cloud route is not wwan0","management LAN route"),
      "r2_exact_same_set_guard": contains(ROOT/"test"/"automation"/"resilience"/"r2_fabric_reconciliation.py","frozen_outage_source_event_keys"),
      "r2_query_before_resubmit_source_guard": contains(ROOT/"test"/"automation"/"resilience"/"r2_fabric_reconciliation.py","query < verify < status < retry","same_prepared_tx_retry_after_status"),
      "a1_nine_conditions": len(rc.A1_CONDITIONS)==9 and rc.FORMAL["A1"]["total_attempts"]==90,
      "a2_counts_frozen": rc.FORMAL["A2"]["total_attempts"]==30,
      "s1_gateway_reception_required": rc.FORMAL["S1"]["gateway_reception_required_for_attack"] is True,
      "s2_blocked": rc.FORMAL["S2"]["blocked_by_methodology"] is True,
      "f1_target_broker_counter_source": contains(ROOT/"test"/"automation"/"flooding"/"flood_harness.py","target_observed_rate_per_second","broker-observed CONNACK responses","local_errors"),
      "f2_generator_target_rates": contains(ROOT/"test"/"automation"/"flooding"/"flood_harness.py","generator_achieved_rate_per_second","target_observed_rate_per_second"),
      "i1_pre_alteration_hash_required": rc.FORMAL["I1"]["trusted_pre_alteration_hash_required"] is True,
      "i2_pre_tamper_anchor_required": rc.FORMAL["I2"]["pre_tamper_anchor_required"] is True,
      "i3_post_attempt_query_required": rc.FORMAL["I3"]["post_attempt_query_required"] is True,
      "t1_formal_count": rc.FORMAL["T1"]["records"]==10,
      "t2_non_overlap_guard": contains(ROOT/"test"/"automation"/"traceability"/"traceability_harness.py","duplicate event keys; sequences would overlap"),
      "traceability_totals": rc.FORMAL["T1"]["records"]+rc.FORMAL["T2"]["records"]==60,
    }
    failed=[k for k,v in checks.items() if not v]
    if failed:
        raise RuntimeError("oversight invariant failure: "+", ".join(failed))
    level={
      "PRE":"READY","P1":"READY","P2":"SYNC_READY_INJECTOR_PENDING",
      "R1":"CONTRACT_READY_HARNESS_PENDING","R2":"HARNESS_READY_LIVE_COMMISSIONING_PENDING",
      "A1":"MQTT_LIVE_COMMISSIONED_LORAWAN_FABRIC_PENDING","A2":"CONTRACT_READY_FABRIC_FIXTURE_PENDING",
      "S1":"VALIDITY_RULE_FROZEN_ORCHESTRATOR_PENDING","S2":"BLOCKED_BY_METHODOLOGY",
      "F1":"HARNESS_READY_LIVE_COMMISSIONING_PENDING","F2":"HARNESS_READY_LIVE_COMMISSIONING_PENDING",
      "I1":"CONTRACT_READY_HARNESS_PENDING","I2":"CONTRACT_READY_HARNESS_PENDING",
      "I3":"CONTRACT_READY_FABRIC_FIXTURE_PENDING","T1":"HARNESS_READY_LIVE_COMMISSIONING_PENDING",
      "T2":"HARNESS_READY_LIVE_COMMISSIONING_PENDING",
    }
    report={"generated_utc":datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z"),
            "status":"PASS","checks":checks,
            "tests":{tid:{"runner_status":runner.STATUS[tid][0],"detail":runner.STATUS[tid][1],
                          "implementation_level":level[tid]} for tid in rc.TEST_IDS}}
    OUT_JSON.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    lines=["# Research Test Oversight Status","",f"Generated UTC: {report['generated_utc']}","",
           "Oversight invariants: PASS","","| Test | Implementation level | Runner status |","|---|---|---|"]
    for tid in rc.TEST_IDS:
        row=report["tests"][tid]
        lines.append(f"| {tid} | {row['implementation_level']} | {row['runner_status']} |")
    lines += ["","This table is deliberately conservative. READY means the exact operator path is qualified. A prepared or existing harness is not promoted until its non-counted live commissioning passes."]
    OUT_MD.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("OVERSIGHT_AUDIT=PASS")
    for tid in rc.TEST_IDS:
        print(f"{tid}={level[tid]}")
    return 0

if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"OVERSIGHT_AUDIT=FAIL ERROR={exc}",file=sys.stderr)
        raise SystemExit(1)
