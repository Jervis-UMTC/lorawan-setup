#!/usr/bin/env python3
"""I2 synthetic saved-evidence tests; no live SQL, Fabric or sensor access."""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).parent
GO_VECTOR=HERE.parents[2]/"evidence-services/cloud/internal/fabricadapter/vectors.go"
spec=importlib.util.spec_from_file_location("i2_evidence",HERE/"i2_evidence.py")
assert spec and spec.loader
i2=importlib.util.module_from_spec(spec)
spec.loader.exec_module(i2)
TX="b"*64

def stable(v):
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)
def digest(raw):
    return hashlib.sha256(raw.encode()).hexdigest()
def production_vector():
    src=GO_VECTOR.read_text(encoding="utf-8")
    canonical=re.search(r'v1VectorCanonical\s*=\s*\x60([^\x60]+)\x60',src)
    frozen=re.search(r'v1VectorDigest\s*=\s*"([0-9a-f]{64})"',src)
    assert canonical and frozen
    return canonical.group(1),frozen.group(1)
def canonical_for(key,temp):
    frozen,_=production_vector()
    obj=json.loads(frozen)
    obj["event_key"]="uplink:"+key
    obj["source_event_key"]=key
    obj["source"]["dev_eui"]=i2.EUI
    obj["payload"]["decoded_payload"]["temperature_c"]=temp
    return stable(obj)
def snapshot(key,temp,phase):
    doc=json.loads(canonical_for(key,temp))
    src=doc["source"]
    lo=doc["lorawan"]
    payload=doc["payload"]
    return {"source_query_ref":f"read-only-source:{key}:{phase}",
        "outbox_query_ref":f"read-only-outbox:{key}:{phase}",
        "schema_version":i2.SCHEMA,
        "event_key":"uplink:"+key,"source_event_key":key,
        "event_type":"lorawan_uplink_accepted","observed_at":doc["observation"]["observed_at"],
        "source":{"received_at":doc["observation"]["received_at"],
                  "application_id":src["application_id"],"device_id":src["device_id"],
                  "device_model":src["device_model"],"decoder_version":payload["decoder_version"],
                  "dev_eui":src["dev_eui"],"gateway_id":src["gateway_id"],"region":src["region"],
                  "f_port":lo["f_port"],"f_cnt":lo["f_cnt"],"confirmed":lo["confirmed"],
                  "raw_data_base64":payload["raw_data_base64"],
                  "payload_json":payload["decoded_payload"],"temperature_c":temp}}
def phase(key,temp,name):
    raw=stable(snapshot(key,temp,name))
    canonical=canonical_for(key,temp)
    return {"source_snapshot_json":raw,
        "recomputed":{"qualification":i2.QUAL,"counted_research":False,
            "source_snapshot_sha256":digest(raw),
            "event_key":"uplink:"+key,"source_event_key":key,
            "schema_version":i2.SCHEMA,
            "source_query_ref":f"read-only-source:{key}:{name}",
            "outbox_query_ref":f"read-only-outbox:{key}:{name}",
            "canonical_json":canonical,"digest_sha256":digest(canonical)}}
def trial(cond,i):
    key=f"i2-synthetic:{cond.lower()}:{i:02d}"
    original=canonical_for(key,24.5); original_hash=digest(original)
    tamper=cond=="TAMPERED"
    return {"condition":cond,"attempt":i,"source_event_key":key,"event_key":"uplink:"+key,
        "test_sequence":i+(10 if tamper else 0),
        "original_seal":{"event_key":"uplink:"+key,"source_event_key":key,
            "schema_version":i2.SCHEMA,"canonical_json":original,
            "digest_sha256":original_hash,"counted_research":False,
            "signing_key_id":"openbao-test-key","signature_ref":f"seal:{key}",
            "outbox_status":"confirmed","outbox_query_ref":f"sealed-outbox:{key}",
            "fabric_tx_id":TX},
        "fabric_anchor":{"source_event_key":key,"fabric_tx_id":TX,
            "before_digest_sha256":original_hash,"after_digest_sha256":original_hash,
            "before_query_ref":f"fabric-before:{key}","after_query_ref":f"fabric-after:{key}",
            "new_commits_for_key":0},
        "outbox_post_digest_sha256":original_hash,
        "outbox_post_canonical_json":original,
        "baseline":phase(key,24.5,"baseline"),
        "current":phase(key,34.5 if tamper else 24.5,"current"),
        **({"restored":phase(key,24.5,"restored")} if tamper else {}),
        "verification_time_ms":12.5}
def fixture(n=1,formal=False):
    return {"test_id":"I2","schema_version":i2.SCHEMA,
            "formal":formal,"attempts_per_condition":n,
            "conditions":{c:[trial(c,i) for i in range(1,n+1)] for c in i2.CONDITIONS}}

class I2OfflineTests(unittest.TestCase):
    def test_production_v1_vector_exact_digest(self):
        exact,expected=production_vector()
        self.assertEqual(digest(exact),expected)
        self.assertEqual(expected,"c2952e8cddc7f39a17522cb49dd3292c9af75c00fdc37172f74bb3dc955f3a5c")
        self.assertEqual(json.loads(exact)["schema_version"],i2.SCHEMA)

    def test_live_v2_schema_fails_closed_not_misreported_as_v1_integrity(self):
        # Real EMU-01 Fabric outbox on 2026-09-21 is telemetry-attestation-v2.
        # A passing synthetic v1 scorer is never proof of the v2 exact-payload
        # anchor or its mandatory verified gateway lineage.
        current=fixture()
        current["schema_version"]="telemetry-attestation-v2"
        result=i2.validate(current)
        self.assertEqual(result["status"],"INVALID")
        self.assertFalse(result["counted_research"])
        current=fixture()
        record=current["conditions"]["TAMPERED"][0]
        record["original_seal"]["schema_version"]="telemetry-attestation-v2"
        self.assertEqual(i2.validate(current)["trials"][1]["status"],"INVALID")

    def test_synthetic_unchanged_and_tampered(self):
        out=i2.validate(fixture())
        self.assertEqual(out["status"],"PASS")
        self.assertEqual(len(out["trials"]),2)
        self.assertFalse(out["counted_research"])

    def test_formal_shape_remains_uncounted(self):
        out=i2.validate(fixture(10,True))
        self.assertEqual(out["status"],"PASS")
        self.assertEqual(len(out["trials"]),20)
        self.assertFalse(out["counted_research"])

    def test_incomplete_formal_shape_invalid(self):
        self.assertEqual(i2.validate(fixture(1,True))["status"],"INVALID")

    def test_wrong_original_canonical_digest_invalid(self):
        x=fixture()
        x["conditions"]["UNCHANGED"][0]["original_seal"]["digest_sha256"]="a"*64
        self.assertEqual(i2.validate(x)["trials"][0]["status"],"INVALID")

    def test_mutated_current_canonical_without_digest_invalid(self):
        x=fixture();t=x["conditions"]["TAMPERED"][0]
        t["current"]["recomputed"]["canonical_json"]+=" "
        self.assertEqual(i2.validate(x)["trials"][1]["status"],"INVALID")

    def test_source_snapshot_digest_invalid(self):
        x=fixture();t=x["conditions"]["TAMPERED"][0]
        t["current"]["source_snapshot_json"]+=" "
        self.assertEqual(i2.validate(x)["trials"][1]["status"],"INVALID")

    def test_stale_source_snapshot_cannot_masquerade_current(self):
        x=fixture();t=x["conditions"]["TAMPERED"][0]
        t["current"]["recomputed"]["canonical_json"]=t["baseline"]["recomputed"]["canonical_json"]
        t["current"]["recomputed"]["digest_sha256"]=t["baseline"]["recomputed"]["digest_sha256"]
        self.assertEqual(i2.validate(x)["trials"][1]["status"],"INVALID")

    def test_convenience_column_payload_mismatch_invalid(self):
        x=fixture();t=x["conditions"]["TAMPERED"][0]
        source=json.loads(t["current"]["source_snapshot_json"])
        source["source"]["temperature_c"]=24.5
        raw=stable(source)
        t["current"]["source_snapshot_json"]=raw
        t["current"]["recomputed"]["source_snapshot_sha256"]=digest(raw)
        self.assertEqual(i2.validate(x)["trials"][1]["status"],"INVALID")

    def test_outbox_seal_mutation_invalid(self):
        x=fixture();t=x["conditions"]["TAMPERED"][0]
        t["outbox_post_digest_sha256"]="a"*64
        self.assertEqual(i2.validate(x)["trials"][1]["status"],"FAIL")

    def test_fabric_anchor_changed_invalid(self):
        x=fixture();t=x["conditions"]["TAMPERED"][0]
        t["fabric_anchor"]["after_digest_sha256"]="a"*64
        self.assertEqual(i2.validate(x)["trials"][1]["status"],"FAIL")

    def test_new_fabric_commit_is_fail_not_invalid(self):
        x=fixture();t=x["conditions"]["TAMPERED"][0]
        t["fabric_anchor"]["new_commits_for_key"]=1
        self.assertEqual(i2.validate(x)["trials"][1]["status"],"FAIL")

    def test_independent_fabric_query_mandatory(self):
        x=fixture();t=x["conditions"]["TAMPERED"][0]
        t["fabric_anchor"]["after_query_ref"]=""
        self.assertEqual(i2.validate(x)["trials"][1]["status"],"INVALID")

    def test_duplicate_source_event_keys_invalid(self):
        x=fixture(2)
        x["conditions"]["UNCHANGED"][1]["source_event_key"]=x["conditions"]["UNCHANGED"][0]["source_event_key"]
        self.assertEqual(i2.validate(x)["status"],"INVALID")

    def test_restoration_mismatch_is_failure_not_success(self):
        x=fixture();t=x["conditions"]["TAMPERED"][0]
        t["restored"]=phase(t["source_event_key"],34.5,"restored")
        result=i2.validate(x)
        self.assertEqual(result["trials"][1]["status"],"FAIL")
        self.assertEqual(result["restoration_failure_count"],1)

    def test_unrelated_payload_mutation_invalid(self):
        x=fixture();t=x["conditions"]["TAMPERED"][0]
        altered=json.loads(t["current"]["recomputed"]["canonical_json"])
        altered["payload"]["decoded_payload"]["battery_v"]=4.0
        raw=stable(altered)
        t["current"]["recomputed"]["canonical_json"]=raw
        t["current"]["recomputed"]["digest_sha256"]=digest(raw)
        src=json.loads(t["current"]["source_snapshot_json"])
        src["source"]["payload_json"]["battery_v"]=4.0
        st=stable(src);t["current"]["source_snapshot_json"]=st
        t["current"]["recomputed"]["source_snapshot_sha256"]=digest(st)
        self.assertEqual(i2.validate(x)["trials"][1]["status"],"INVALID")

    def test_same_value_not_a_tamper_invalid(self):
        x=fixture();t=x["conditions"]["TAMPERED"][0]
        t["current"]=phase(t["source_event_key"],24.5,"current")
        self.assertEqual(i2.validate(x)["trials"][1]["status"],"INVALID")

    def test_missing_read_only_recompute_invalid(self):
        x=fixture();x["conditions"]["TAMPERED"][0]["current"].pop("recomputed")
        self.assertEqual(i2.validate(x)["trials"][1]["status"],"INVALID")

    def test_cli_writes_without_overwriting_source(self):
        with tempfile.TemporaryDirectory() as temp:
            src=Path(temp)/"source.json";dest=Path(temp)/"checked.json"
            src.write_text(json.dumps(fixture()),encoding="utf-8")
            original=src.read_bytes()
            p=subprocess.run([sys.executable,str(HERE/"i2_evidence.py"),"--evidence",str(src),
                              "--output",str(dest)],capture_output=True,text=True,timeout=8)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(src.read_bytes(),original)
            self.assertEqual(json.loads(dest.read_text())["status"],"PASS")
            self.assertFalse(json.loads(dest.read_text())["counted_research"])

if __name__=="__main__":unittest.main()
