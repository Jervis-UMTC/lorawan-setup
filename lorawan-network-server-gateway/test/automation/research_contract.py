#!/usr/bin/env python3
"""Authoritative machine-readable Chapter 3 research-test contract."""
from __future__ import annotations

TEST_IDS=("PRE","P1","P2","R1","R2","A1","A2","S1","S2","F1","F2","I1","I2","I3","T1","T2")
CLASSIFICATIONS=("PASS","FAIL","INVALID","BLOCKED")
JOINT_FABRIC_TESTS=frozenset({"P1","P2","R2","A2","I1","I2","I3","T1","T2"})
FABRIC_DOWNSTREAM_OPTIONAL=frozenset({"R1","A1"})
FABRIC_REQUIRED=JOINT_FABRIC_TESTS
FABRIC_OPTIONAL=FABRIC_DOWNSTREAM_OPTIONAL
FABRIC_JOIN_FIELDS=("run_id","trial_id","source_record_id","payload_sha256")

P2_PAIR_ORDER={
    1:("CONTROL","FABRIC"),
    2:("FABRIC","CONTROL"),
    3:("CONTROL","FABRIC"),
}

FORMAL={
 "PRE":{"kind":"gate"},
 "P1":{"repetitions":3,"duration_seconds":1800,"source_interval_seconds":15,"planned_attempts_per_run":120},
 "P2":{"rates_tps":(1/15,1.0,5.0,10.0),"duration_seconds":300,"repetitions":3,
       "matched_control":True,"stable_between_runs_seconds":60,"open_loop_required":True,
       "planned_with_fabric_records":14460},
 "R1":{"repetitions":3,"normal_seconds":1800,"outage_seconds":3600,"recovery_seconds":1800,
       "total_seconds":7200,"source_interval_seconds":15,"lte_route_required":True,
       "alternate_wan_forbidden":True},
 "R2":{"normal_records":10,"outage_records":10,"reconcile_same_records":10},
 "A1":{"attempts_per_condition":10,"conditions":(
     "LORAWAN_VALID_OTAA","LORAWAN_WRONG_APPKEY","LORAWAN_UNREGISTERED_DEVEUI",
     "MQTT_ALLOWED","MQTT_WRONG_PASSWORD","MQTT_PROHIBITED_TOPIC",
     "FABRIC_AUTHORIZED_WRITER","FABRIC_VALID_NONWRITER","FABRIC_UNTRUSTED_IDENTITY")},
 "A2":{"attempts_per_condition":10,"conditions":("NORMAL","ENDORSEMENT_VIOLATION","RESTORED")},
 "S1":{"legitimate_replay_controls":10,"received_replays":10,"genuine_spoof_controls":10,
       "received_spoofs":10,"counted_attempts":40,"gateway_reception_required":True,
       "gateway_reception_required_for_attack":True},
 "S2":{"blocked_by_methodology":True},
 "F1":{"rates_per_second":(0,10,50),"duration_seconds":300,"repetitions":3,"recovery_seconds":300},
 "F2":{"rates_per_second":(0,10,50),"duration_seconds":300,"repetitions":3,"recovery_seconds":300},
 "I1":{"controls":10,"altered":10,"trusted_pre_alteration_hash_required":True},
 "I2":{"controls":10,"tampered":10,"pre_tamper_anchor_required":True,
       "fabric_state_must_remain_unchanged":True},
 "I3":{"baseline":10,"duplicate_same_hash":10,"conflicting_overwrite":10,"post_attempt_query_required":True},
 "T1":{"trials":10,"records":10},
 "T2":{"trials":10,"sequences":10,"records_per_trial":5,"records":50,"non_overlapping":True},
}
A1_CONDITIONS=FORMAL["A1"]["conditions"]
FORMAL["A1"]["total_attempts"]=len(FORMAL["A1"]["conditions"])*FORMAL["A1"]["attempts_per_condition"]
FORMAL["A2"]["total_attempts"]=len(FORMAL["A2"]["conditions"])*FORMAL["A2"]["attempts_per_condition"]

def p2_planned_records(rate_tps:float,duration_seconds:int=300)->int:
    return int(round(float(rate_tps)*int(duration_seconds)))

def traceability_totals()->dict[str,int]:
    return {"trials":FORMAL["T1"]["trials"]+FORMAL["T2"]["trials"],
            "records":FORMAL["T1"]["records"]+FORMAL["T2"]["records"]}

def validate_static_contract()->None:
    if p2_planned_records(1/15)!=20: raise RuntimeError("P2 1/15 s count drift")
    if p2_planned_records(1)!=300 or p2_planned_records(5)!=1500 or p2_planned_records(10)!=3000:
        raise RuntimeError("P2 rate/count mapping drift")
    total=sum(p2_planned_records(r)*FORMAL["P2"]["repetitions"] for r in FORMAL["P2"]["rates_tps"])
    if total!=FORMAL["P2"]["planned_with_fabric_records"]: raise RuntimeError("P2 total record count drift")
    if FORMAL["A1"]["total_attempts"]!=90 or FORMAL["A2"]["total_attempts"]!=30:
        raise RuntimeError("authentication/endorsement attempt count drift")
    if FORMAL["S1"]["counted_attempts"]!=40: raise RuntimeError("S1 count drift")
    if traceability_totals()!={"trials":20,"records":60}: raise RuntimeError("traceability totals drift")

def assert_formal(test_id:str, **actual)->None:
    test_id=test_id.upper()
    if test_id=="S2": raise RuntimeError("S2 is BLOCKED_BY_METHODOLOGY")
    if test_id not in FORMAL: raise RuntimeError(f"unknown test_id {test_id}")
    spec=FORMAL[test_id]
    for key,value in actual.items():
        if key not in spec: continue
        expected=spec[key]
        if isinstance(expected,tuple):
            if tuple(value)!=expected: raise RuntimeError(f"{test_id} {key} drift: {value!r} != {expected!r}")
        elif value!=expected:
            raise RuntimeError(f"{test_id} {key} drift: {value!r} != {expected!r}")


def validate_flood_profile(test_id:str, rates, duration_seconds:int, repetitions:int, recovery_seconds:int, formal:bool)->None:
    if test_id not in {"F1","F2"}: raise RuntimeError(f"invalid flood test {test_id}")
    if formal:
        assert_formal(test_id, rates_per_second=tuple(rates), duration_seconds=duration_seconds,
                      repetitions=repetitions, recovery_seconds=recovery_seconds)
    elif duration_seconds < 1 or repetitions < 1 or recovery_seconds < 0:
        raise RuntimeError("invalid flooding rehearsal profile")


def validate_r2_profile(target_records_per_phase:int, formal:bool)->None:
    if formal:
        assert_formal("R2", normal_records=target_records_per_phase,
                      outage_records=target_records_per_phase,
                      reconcile_same_records=target_records_per_phase)
    elif target_records_per_phase < 1:
        raise RuntimeError("R2 rehearsal requires at least one record per phase")


def validate_trace_profile(test_id:str, required:int, formal:bool)->None:
    if test_id=="T1":
        if formal: assert_formal("T1", trials=required, records=required)
        elif required < 1: raise RuntimeError("T1 rehearsal requires at least one trial")
    elif test_id=="T2":
        if formal: assert_formal("T2", trials=required, records_per_trial=5, records=required*5)
        elif required < 1: raise RuntimeError("T2 rehearsal requires at least one sequence")
    else:
        raise RuntimeError(f"invalid traceability test {test_id}")


validate_static_contract()

if __name__=="__main__":
    validate_static_contract()
    print("RESEARCH_CONTRACT=PASS")
    print(f"P2_WITH_FABRIC_RECORDS={FORMAL['P2']['planned_with_fabric_records']}")
    totals=traceability_totals()
    print(f"TRACEABILITY_TRIALS={totals['trials']} TRACEABILITY_RECORDS={totals['records']}")
