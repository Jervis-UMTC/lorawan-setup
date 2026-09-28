#!/usr/bin/env python3
"""I1 synthetic scorer and exact Node-RED JavaScript gate qualification."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BASE=Path(__file__).parent
TARGET=BASE/"i1_evidence.py"
spec=importlib.util.spec_from_file_location("i1_evidence",TARGET)
assert spec and spec.loader
i1=importlib.util.module_from_spec(spec)
spec.loader.exec_module(i1)

def compact(v):
    return json.dumps(v,ensure_ascii=False,separators=(",",":"))
def trial(cond,i):
    altered=cond=="ALTERED"
    key=f"emu-i1-{cond.lower()}-{i:02d}"
    initial={"test_id":key,"dev_eui":i1.DEV_EUI,"f_cnt":i+100,
             "sensor_type":"temperature","sensor_value":24.5,"unit":"Cel",
             "event_time":"2026-09-21T01:00:00Z"}
    final={**initial,"sensor_value":34.5 if altered else 24.5}
    before,after=compact(initial),compact(final)
    return {"condition":cond,"attempt":i,"source_test_id":key,"test_sequence":i+(10 if altered else 0),
            "gate_observation_ref":f"flow-log:{key}",
            "gate":{"test_id":key,"test_sequence":i+(10 if altered else 0),
                    "dev_eui":i1.DEV_EUI,
                    "hash_scope":i1.SCOPE,
                    "initial_record_json":before,"final_record_json":after,
                    "initial_hash":hashlib.sha256(before.encode()).hexdigest(),
                    "final_hash":hashlib.sha256(after.encode()).hexdigest(),
                    "altered":altered,"match":not altered,
                    "status":"QUARANTINE" if altered else "ALLOW",
                    "observed_at_utc":"2026-09-21T01:00:01Z"},
            "pre_storage":{"uplinks":0,"outbox":0,"query_ref":f"pre-db:{key}"},
            "post_storage":{"uplinks":0 if altered else 1,"outbox":0 if altered else 1,
                            "query_ref":f"post-db:{key}"},
            "storage_ref":"" if altered else f"storage:{key}",
            "quarantine_ref":f"quarantine:{key}" if altered else "",
            "verification_time_ms":8.2}
def fixture(count=1,formal=False):
    gate_hash=hashlib.sha256((BASE/"i1_node_red_gate.function.js").read_bytes()).hexdigest()
    return {"test_id":"I1","formal":formal,"attempts_per_condition":count,
            "flow_export_sha256":"a"*64,"flow_export_ref":"offline-node-red-mock",
            "test_gate_sha256":gate_hash,
            "conditions":{c:[trial(c,i) for i in range(1,count+1)] for c in i1.CONDITIONS}}

class I1OfflineTests(unittest.TestCase):
    def test_exact_node_red_gate_vm_regressions(self):
        cp=subprocess.run(["node","--test",str(BASE/"test_i1_node_red_gate.cjs")],
                          capture_output=True,text=True,timeout=15)
        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
        self.assertIn("tests 13",cp.stdout)
        self.assertIn("pass 13",cp.stdout)
        print("I1_NODE_RED_JAVASCRIPT_VM=PASS tests=13",flush=True)

    def test_one_per_condition_rehearsal_scoring(self):
        out=i1.validate(fixture())
        self.assertEqual(out["status"],"PASS")
        self.assertFalse(out["counted_research"])
        self.assertEqual(len(out["trials"]),2)

    def test_formal_10_plus_10_is_code_only(self):
        out=i1.validate(fixture(10,True))
        self.assertEqual(out["status"],"PASS")
        self.assertEqual(len(out["trials"]),20)
        self.assertFalse(out["counted_research"])

    def test_formal_count_drift_invalid(self):
        self.assertEqual(i1.validate(fixture(1,True))["status"],"INVALID")

    def test_wrong_original_hash_invalid(self):
        x=fixture();x["conditions"]["UNCHANGED"][0]["gate"]["initial_hash"]="b"*64
        self.assertEqual(i1.validate(x)["trials"][0]["status"],"INVALID")

    def test_modified_json_without_resealing_invalid(self):
        x=fixture();x["conditions"]["ALTERED"][0]["gate"]["final_record_json"] += " "
        self.assertEqual(i1.validate(x)["trials"][1]["status"],"INVALID")

    def test_unexpected_field_mutation_invalid(self):
        x=fixture();t=x["conditions"]["ALTERED"][0]
        record=json.loads(t["gate"]["final_record_json"])
        record["unit"]="Fahrenheit"
        s=compact(record)
        t["gate"]["final_record_json"]=s
        t["gate"]["final_hash"]=hashlib.sha256(s.encode()).hexdigest()
        self.assertEqual(i1.validate(x)["trials"][1]["status"],"INVALID")

    def test_wrong_control_value_invalid(self):
        x=fixture();t=x["conditions"]["UNCHANGED"][0]
        post=json.loads(t["gate"]["final_record_json"])
        post["sensor_value"]=34.5
        s=compact(post);t["gate"]["final_record_json"]=s
        t["gate"]["final_hash"]=hashlib.sha256(s.encode()).hexdigest()
        self.assertEqual(i1.validate(x)["trials"][0]["status"],"INVALID")

    def test_actual_alteration_not_quarantined_is_failure(self):
        x=fixture();t=x["conditions"]["ALTERED"][0]
        t["gate"]["status"]="ALLOW"
        out=i1.validate(x)
        self.assertEqual(out["status"],"FAIL")
        self.assertEqual(out["false_negative_count"],1)

    def test_unauthorized_storage_is_failure(self):
        x=fixture();x["conditions"]["ALTERED"][0]["post_storage"]["uplinks"]=1
        out=i1.validate(x)
        self.assertEqual(out["status"],"FAIL")
        self.assertEqual(out["unauthorized_storage_count"],1)

    def test_missing_db_readback_invalid(self):
        x=fixture();x["conditions"]["ALTERED"][0]["post_storage"]["query_ref"]=""
        self.assertEqual(i1.validate(x)["trials"][1]["status"],"INVALID")

    def test_missing_quarantine_observation_invalid(self):
        x=fixture();x["conditions"]["ALTERED"][0]["quarantine_ref"]=""
        self.assertEqual(i1.validate(x)["trials"][1]["status"],"INVALID")

    def test_missing_storage_for_control_invalid(self):
        x=fixture();x["conditions"]["UNCHANGED"][0]["storage_ref"]=""
        self.assertEqual(i1.validate(x)["trials"][0]["status"],"INVALID")

    def test_preexisting_event_makes_trial_invalid(self):
        x=fixture();x["conditions"]["ALTERED"][0]["pre_storage"]["outbox"]=1
        self.assertEqual(i1.validate(x)["trials"][1]["status"],"INVALID")

    def test_duplicate_source_id_and_sequence_invalid(self):
        x=fixture();x["conditions"]["ALTERED"][0]["source_test_id"]=x["conditions"]["UNCHANGED"][0]["source_test_id"]
        self.assertEqual(i1.validate(x)["status"],"INVALID")
        x=fixture();x["conditions"]["ALTERED"][0]["test_sequence"]=1
        self.assertEqual(i1.validate(x)["status"],"INVALID")

    def test_nonfinite_processing_time_invalid(self):
        x=fixture();x["conditions"]["UNCHANGED"][0]["verification_time_ms"]=float("nan")
        self.assertEqual(i1.validate(x)["trials"][0]["status"],"INVALID")

    def test_missing_gate_fails_closed(self):
        x=fixture();del x["conditions"]["UNCHANGED"][0]["gate"]
        self.assertEqual(i1.validate(x)["trials"][0]["status"],"INVALID")

    def test_cli_writes_without_overwriting_source(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/"evidence.json";out=Path(td)/"result.json"
            source.write_text(json.dumps(fixture()),encoding="utf-8")
            original=source.read_bytes()
            cp=subprocess.run([sys.executable,str(TARGET),"--evidence",str(source),
                              "--output",str(out)],capture_output=True,text=True,timeout=8)
            self.assertEqual(cp.returncode,0,cp.stderr)
            self.assertEqual(source.read_bytes(),original)
            self.assertEqual(json.loads(out.read_text())["status"],"PASS")
            self.assertFalse(json.loads(out.read_text())["counted_research"])

if __name__=="__main__":
    unittest.main()
