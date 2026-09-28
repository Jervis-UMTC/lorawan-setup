#!/usr/bin/env python3
"""I3 deterministic exact-payload Fabric source-bound anchor regressions.

No ledger, broker, database or sensor is contacted. Supports one/ten synthetic
baseline anchors, idempotent duplicate attempts, rejected conflicting bytes.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "i3_ledger_evidence.py"
spec = importlib.util.spec_from_file_location("i3_ledger_evidence", SCRIPT)
assert spec and spec.loader
i3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(i3)
TX = "a"*64


def data(index: int, temp: float) -> bytes:
    item = {"fixture": "I3_SYNTHETIC_NOT_AGRICULTURAL_EVIDENCE",
            "sensor": "EMU-01-mock", "test_sequence": index,
            "temperature_c": temp, "battery_v": 3.6}
    return json.dumps(item, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def query(key: str, phase: str, anchor: dict | None, count: int):
    return {"query_ref": f"fabric-query:{phase}:{key}",
            "authenticated_source_system_id": i3.SOURCE_SYSTEM,
            "source_record_id": key,
            "found": anchor is not None, "record_count": count,
            "anchor": copy.deepcopy(anchor)}


def response(key: str, label: str, payload: bytes, status: str, outcome: str):
    return {"authenticated_source_system_id": i3.SOURCE_SYSTEM,
            "source_record_id": key, "payload_sha256": digest(payload),
            "payload_length": len(payload), "request_ref": f"request:{label}:{key}",
            "response_ref": f"response:{label}:{key}",
            "status": status, "outcome": outcome,
            "response_time_ms": 7.5,
            "fabric_tx_id": TX if status == "COMMITTED" else None,
            "failure_category": i3.ERROR_CATEGORY if outcome == "REJECTED_CONFLICT" else "",
            "decision_source": "CHAINCODE" if outcome == "REJECTED_CONFLICT" else ""}


def anchor(key: str, payload: bytes) -> dict:
    return {"record_id": "hrc:" + key,
            "authenticated_source_system_id": i3.SOURCE_SYSTEM,
            "source_record_id": key,
            "digest_algorithm": "sha256", "digest": digest(payload),
            "payload_length": len(payload), "source_type": "lorawan-research-i3",
            "producer": "lorawan-gateway-evidence",
            "produced_at": "2026-09-21T00:00:00Z",
            "schema_version": "telemetry-attestation-v1"}


def fixture(n: int = 1, formal: bool = False) -> dict:
    phases = {p: [] for p in i3.PHASES}
    for index in range(1, n+1):
        key = f"i3-synthetic:{index:02d}"
        original, other = data(index, 24.5), data(index, 34.5)
        a = anchor(key, original)
        phases["BASELINE"].append({
            "phase": "BASELINE", "attempt": index, "trial_id": f"baseline:{index}",
            "source_record_id": key,
            "exact_payload_base64": base64.b64encode(original).decode(),
            "payload_sha256": digest(original),
            "anchor": copy.deepcopy(a),
            "pre_query": query(key, "baseline-pre", None, 0),
            "post_query": query(key, "baseline-post", a, 1),
            "response": response(key, "baseline", original, "COMMITTED", "CREATE"),
            "unrelated_fabric_outage": False})
        phases["DUPLICATE_SAME_HASH"].append({
            "phase": "DUPLICATE_SAME_HASH", "attempt": index,
            "trial_id": f"duplicate:{index}", "source_record_id": key,
            "exact_payload_base64": base64.b64encode(original).decode(),
            "payload_sha256": digest(original),
            "pre_query": query(key, "duplicate-pre", a, 1),
            "post_query": query(key, "duplicate-post", a, 1),
            "response": response(key, "duplicate", original, "COMMITTED", "IDEMPOTENT_RETRY"),
            "unrelated_fabric_outage": False})
        phases["CONFLICTING_OVERWRITE"].append({
            "phase": "CONFLICTING_OVERWRITE", "attempt": index,
            "trial_id": f"conflict:{index}", "source_record_id": key,
            "exact_payload_base64": base64.b64encode(other).decode(),
            "payload_sha256": digest(other),
            "pre_query": query(key, "conflict-pre", a, 1),
            "post_query": query(key, "conflict-post", a, 1),
            "response": response(key, "conflict", other, "REJECTED", "REJECTED_CONFLICT"),
            "unrelated_fabric_outage": False})
    return {"test_id": "I3", "formal": formal,
            "attempts_per_phase": n, "fixture_namespace": "i3-synthetic",
            "authenticated_source_system_id": i3.SOURCE_SYSTEM,
            "run_id": "I3-synthetic-offline", "run_manifest_sha256": "a"*64,
            "record_manifest_sha256": "b"*64,
            "fabric_export_ref": "synthetic:fixture-only",
            "phases": phases}


def row(e: dict, phase: str, i: int = 0) -> dict:
    return e["phases"][phase][i]


class I3OfflineTests(unittest.TestCase):
    def test_single_fixture_three_phases(self):
        checked = i3.validate(fixture())
        self.assertEqual(checked["status"], "PASS", checked)
        self.assertEqual(checked["baseline_fixtures"], 1)
        self.assertEqual(checked["mutation_attempts"], 2)
        self.assertEqual(checked["duplicate_effective_prevention_count"], 1)
        self.assertEqual(checked["conflict_rejection_count"], 1)
        self.assertEqual(checked["unauthorized_state_change_count"], 0)
        self.assertFalse(checked["counted_research"])

    def test_formal_ten_ten_ten_remains_uncounted(self):
        checked = i3.validate(fixture(10, True))
        self.assertEqual(checked["status"], "PASS")
        self.assertEqual(len(checked["trials"]), 30)
        self.assertEqual(checked["baseline_fixtures"], 10)
        self.assertEqual(checked["mutation_attempts"], 20)
        self.assertEqual(checked["duplicate_effective_prevention_count"], 10)
        self.assertEqual(checked["conflict_rejection_count"], 10)
        self.assertEqual(checked["original_hash_preservation_count"], 20)
        self.assertFalse(checked["counted_research"])

    def test_formal_shape_short_is_invalid(self):
        self.assertEqual(i3.validate(fixture(1, True))["status"], "INVALID")

    def test_missing_duplicate_result_invalid(self):
        item=fixture(2)
        item["phases"]["DUPLICATE_SAME_HASH"].pop()
        self.assertEqual(i3.validate(item)["status"], "INVALID")

    def test_duplicate_trial_id_invalid(self):
        item=fixture()
        row(item, "DUPLICATE_SAME_HASH")["trial_id"] = row(item, "BASELINE")["trial_id"]
        self.assertEqual(i3.validate(item)["status"], "INVALID")

    def test_duplicate_baseline_source_key_invalid(self):
        item=fixture(2)
        row(item, "BASELINE", 1)["source_record_id"]=row(item,"BASELINE",0)["source_record_id"]
        self.assertEqual(i3.validate(item)["status"],"INVALID")

    def test_baseline_preexisting_anchor_not_recreated(self):
        item=fixture()
        b=row(item,"BASELINE")
        b["pre_query"]=query(b["source_record_id"],"before-existing",b["anchor"],1)
        self.assertEqual(i3.validate(item)["trials"][0]["status"],"INVALID")

    def test_baseline_without_commit_fails(self):
        item=fixture()
        row(item,"BASELINE")["response"]["status"]="REJECTED"
        checked=i3.validate(item)
        self.assertEqual(checked["status"],"FAIL" if all(x["status"]!="INVALID" for x in checked["trials"]) else "INVALID")
        self.assertEqual(checked["trials"][0]["status"],"FAIL")

    def test_malformed_baseline_does_not_crash_later_phases(self):
        item=fixture()
        row(item,"BASELINE").pop("payload_sha256")
        checked=i3.validate(item)
        self.assertEqual(checked["status"],"INVALID")
        self.assertEqual(len(checked["trials"]),3)
        self.assertEqual([r["status"] for r in checked["trials"]],["INVALID"]*3)

    def test_wrong_original_payload_sha_invalid(self):
        item=fixture()
        row(item,"BASELINE")["payload_sha256"]="0"*64
        self.assertEqual(i3.validate(item)["trials"][0]["status"],"INVALID")

    def test_corrupted_exact_base64_invalid(self):
        item=fixture()
        row(item,"DUPLICATE_SAME_HASH")["exact_payload_base64"]="not/base64!"
        self.assertEqual(i3.validate(item)["trials"][1]["status"],"INVALID")

    def test_baseline_outbox_query_missing_invalid(self):
        item=fixture()
        row(item,"BASELINE")["post_query"]["query_ref"]=""
        self.assertEqual(i3.validate(item)["trials"][0]["status"],"INVALID")

    def test_missing_post_query_invalid(self):
        item=fixture()
        row(item,"CONFLICTING_OVERWRITE")["post_query"]["query_ref"]=""
        self.assertEqual(i3.validate(item)["trials"][2]["status"],"INVALID")

    def test_wrong_trace_id_invalid(self):
        item=fixture()
        row(item,"CONFLICTING_OVERWRITE")["source_record_id"]="i3-synthetic:wrong"
        self.assertEqual(i3.validate(item)["trials"][2]["status"],"INVALID")

    def test_same_digest_but_different_bytes_not_same_payload(self):
        item=fixture()
        du=row(item,"DUPLICATE_SAME_HASH")
        exact=b'{"claimed":"same","format":"different"}'
        du["exact_payload_base64"]=base64.b64encode(exact).decode()
        du["payload_sha256"]=digest(exact)
        du["response"]["payload_sha256"]=digest(exact)
        du["response"]["payload_length"]=len(exact)
        self.assertEqual(i3.validate(item)["trials"][1]["status"],"INVALID")

    def test_conflict_condition_with_same_bytes_invalid(self):
        item=fixture()
        du=row(item,"DUPLICATE_SAME_HASH")
        co=row(item,"CONFLICTING_OVERWRITE")
        co["exact_payload_base64"]=du["exact_payload_base64"]
        co["payload_sha256"]=du["payload_sha256"]
        co["response"]["payload_sha256"]=du["payload_sha256"]
        co["response"]["payload_length"]=du["response"]["payload_length"]
        self.assertEqual(i3.validate(item)["trials"][2]["status"],"INVALID")

    def test_idempotent_retry_is_not_false_duplicate_acceptance(self):
        item=fixture()
        checked=i3.validate(item)
        self.assertEqual(checked["trials"][1]["status"],"PASS")
        self.assertTrue(checked["trials"][1]["duplicate_effectively_prevented"])

    def test_explicit_duplicate_reject_is_allowed_if_state_unchanged(self):
        item=fixture()
        resp=row(item,"DUPLICATE_SAME_HASH")["response"]
        resp["status"]="REJECTED";resp["outcome"]="REJECTED_DUPLICATE";resp["fabric_tx_id"]=None
        resp["failure_category"]="DUPLICATE_ANCHOR";resp["decision_source"]="CHAINCODE"
        checked=i3.validate(item)
        self.assertEqual(checked["trials"][1]["status"],"PASS")
        self.assertEqual(checked["duplicate_explicit_rejection_count"],1)

    def test_rejected_duplicate_without_chaincode_proof_is_invalid(self):
        item=fixture()
        resp=row(item,"DUPLICATE_SAME_HASH")["response"]
        resp["status"]="REJECTED";resp["outcome"]="REJECTED_DUPLICATE"
        self.assertEqual(i3.validate(item)["trials"][1]["status"],"INVALID")

    def test_post_query_missing_anchor_fields_invalid(self):
        item=fixture()
        row(item,"CONFLICTING_OVERWRITE")["post_query"]["anchor"].pop("payload_length")
        self.assertEqual(i3.validate(item)["trials"][2]["status"],"INVALID")

    def test_duplicate_create_is_failure(self):
        item=fixture()
        row(item,"DUPLICATE_SAME_HASH")["response"]["outcome"]="CREATE"
        self.assertEqual(i3.validate(item)["trials"][1]["status"],"FAIL")

    def test_duplicate_multiplicity_increases_is_failure(self):
        item=fixture()
        row(item,"DUPLICATE_SAME_HASH")["post_query"]["record_count"]=2
        self.assertEqual(i3.validate(item)["trials"][1]["status"],"FAIL")

    def test_duplicate_changes_original_anchor_is_failure(self):
        item=fixture()
        row(item,"DUPLICATE_SAME_HASH")["post_query"]["anchor"]["digest"]="c"*64
        self.assertEqual(i3.validate(item)["trials"][1]["status"],"FAIL")

    def test_conflicting_anchor_committed_is_failure(self):
        item=fixture()
        co=row(item,"CONFLICTING_OVERWRITE")
        co["response"]["status"]="COMMITTED";co["response"]["outcome"]="CREATE"
        self.assertEqual(i3.validate(item)["trials"][2]["status"],"FAIL")

    def test_conflicting_rejected_but_state_changed_is_failure(self):
        item=fixture()
        row(item,"CONFLICTING_OVERWRITE")["post_query"]["anchor"]["digest"]="c"*64
        checked=i3.validate(item)
        self.assertEqual(checked["trials"][2]["status"],"FAIL")
        self.assertEqual(checked["unauthorized_state_change_count"],1)

    def test_conflicting_deleted_anchor_is_failure(self):
        item=fixture()
        co=row(item,"CONFLICTING_OVERWRITE")
        co["post_query"]=query(co["source_record_id"],"deleted",None,0)
        self.assertEqual(i3.validate(item)["trials"][2]["status"],"FAIL")

    def test_conflicting_unrelated_rejection_invalid(self):
        item=fixture()
        co=row(item,"CONFLICTING_OVERWRITE")["response"]
        co["failure_category"]="AUTHORIZATION_DENIED"
        self.assertEqual(i3.validate(item)["trials"][2]["status"],"INVALID")

    def test_conflicting_unrelated_fabric_outage_invalid(self):
        item=fixture()
        row(item,"CONFLICTING_OVERWRITE")["unrelated_fabric_outage"]=True
        self.assertEqual(i3.validate(item)["trials"][2]["status"],"INVALID")

    def test_missing_original_record_id_invalid(self):
        item=fixture()
        row(item,"BASELINE")["anchor"]["record_id"]=""
        self.assertEqual(i3.validate(item)["trials"][0]["status"],"INVALID")

    def test_fabric_query_source_identity_mismatch_invalid(self):
        item=fixture()
        row(item,"DUPLICATE_SAME_HASH")["post_query"]["authenticated_source_system_id"]="wrong"
        self.assertEqual(i3.validate(item)["trials"][1]["status"],"INVALID")

    def test_negative_latency_invalid(self):
        item=fixture()
        row(item,"CONFLICTING_OVERWRITE")["response"]["response_time_ms"]=-1
        self.assertEqual(i3.validate(item)["trials"][2]["status"],"INVALID")

    def test_cli_does_not_overwrite_source(self):
        with tempfile.TemporaryDirectory() as td:
            src,dst=Path(td)/"i3.json",Path(td)/"validated.json"
            src.write_text(json.dumps(fixture()),encoding="utf-8")
            before=src.read_bytes()
            result=subprocess.run([sys.executable,str(SCRIPT),"--evidence",str(src),
                                   "--output",str(dst)],
                                  capture_output=True,text=True,timeout=8)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(before,src.read_bytes())
            val=json.loads(dst.read_text(encoding="utf-8"))
            self.assertEqual(val["status"],"PASS")
            self.assertFalse(val["counted_research"])

    def test_cli_refuses_same_source_and_output(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/"i3.json"
            src.write_text(json.dumps(fixture()),encoding="utf-8")
            p=subprocess.run([sys.executable,str(SCRIPT),"--evidence",str(src),
                              "--output",str(src)],capture_output=True,text=True,timeout=8)
            self.assertNotEqual(p.returncode,0)
            self.assertEqual(json.loads(src.read_text())["test_id"],"I3")


if __name__=="__main__":
    unittest.main()
