#!/usr/bin/env python3
"""A2 only: deterministic synthetic evidence and fail-closed CLI scorer tests."""
from __future__ import annotations
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("a2_fabric_endorsement_evidence.py")
spec = importlib.util.spec_from_file_location("a2_fabric_endorsement_evidence", SCRIPT)
assert spec and spec.loader
a2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a2)

HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64


def example(*, count=1, formal=False, origin="SYNTHETIC"):
    groups = {}
    for condition in a2.CONDITIONS:
        rows = []
        for i in range(1, count + 1):
            key = f"research:a2-unit:{condition.lower()}:{i}"
            violation = condition == "ENDORSEMENT_VIOLATION"
            rows.append({
                "condition": condition, "attempt": i,
                "trial_id": f"{condition}-{i}",
                "source_record_id": f"source:{condition}:{i}",
                "world_state_key": key,
                "policy_sha256": HEX_A,
                "payload_sha256": HEX_B,
                "authenticated_source_system_id": a2.AUTH_SOURCE,
                "identity_authorized": True,
                "record_schema_valid": True,
                "unrelated_fabric_outage": False,
                "required_endorsements_satisfied": not violation,
                "endorsement_probe_ref": f"endorsement-proof:{condition}:{i}",
                "attempt_ref": f"request:{condition}:{i}",
                "response_ref": f"response:{condition}:{i}",
                "response_time_ms": 5.5,
                "normalized_status": "REJECTED" if violation else "COMMITTED",
                "failure_category": "MISSING_REQUIRED_ENDORSEMENT" if violation else "",
                "fabric_tx_id": None if violation else HEX_B,
                "expected_world_state_sha256": None if violation else HEX_C,
                "pre": {"key": key, "exists": False, "state_sha256": None,
                        "query_ref": f"ledger-before:{condition}:{i}"},
                "post": {"key": key, "exists": not violation,
                         "state_sha256": None if violation else HEX_C,
                         "query_ref": f"ledger-after:{condition}:{i}"},
            })
        groups[condition] = rows
    return {
        "test_id": "A2", "run_id": "A2-synthetic-unit",
        "formal": formal, "attempts_per_condition": count,
        "evidence_origin": origin,
        "policy_ref": "policy-unit-test", "policy_sha256": HEX_A,
        "run_manifest_sha256": HEX_B, "record_manifest_sha256": HEX_C,
        "authenticated_source_system_id": a2.AUTH_SOURCE,
        "approved_fixture_ref": "synthetic-policy-fixture",
        "fixture_namespace": "research:a2-unit",
        "required_endorser": "fictional-endorser",
        "violation_injection_ref": "synthetic-missing-endorsement",
        "restoration_proof_ref": "synthetic-restored-endorsement",
        "conditions": groups,
    }


class A2OfflineTests(unittest.TestCase):
    def test_three_conditions_synthetic_rehearsal(self):
        res = a2.validate(example())
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(len(res["trials"]), 3)
        self.assertFalse(res["counted_research"])
        self.assertEqual(res["unauthorized_state_change_count"], 0)

    def test_exact_formal_shape_but_not_counted_research(self):
        res = a2.validate(example(count=10, formal=True, origin="FABRIC_SIDE"))
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(len(res["trials"]), 30)
        self.assertFalse(res["counted_research"])
        self.assertTrue(res["requires_fabric_provenance_review"])

    def test_synthetic_cannot_claim_formal_fabric_evidence(self):
        self.assertEqual(a2.validate(example(count=10, formal=True))["status"], "INVALID")

    def test_formal_count_drift_cannot_pass(self):
        item = example(formal=True, origin="FABRIC_SIDE")
        self.assertEqual(a2.validate(item)["status"], "INVALID")

    def test_missing_endorsement_probe_invalid_not_denominator(self):
        item = example()
        item["conditions"]["ENDORSEMENT_VIOLATION"][0]["required_endorsements_satisfied"] = True
        self.assertEqual(a2.validate(item)["trials"][1]["status"], "INVALID")

    def test_unrelated_outage_cannot_masquerade_policy_rejection(self):
        item = example()
        item["conditions"]["ENDORSEMENT_VIOLATION"][0]["unrelated_fabric_outage"] = True
        self.assertEqual(a2.validate(item)["trials"][1]["status"], "INVALID")

    def test_unrelated_rejection_cannot_masquerade_endorsement(self):
        item = example()
        item["conditions"]["ENDORSEMENT_VIOLATION"][0]["failure_category"] = "PERMISSION_DENIED"
        self.assertEqual(a2.validate(item)["trials"][1]["status"], "INVALID")

    def test_proven_unauthorized_acceptance_remains_failure(self):
        item = example()
        trial = item["conditions"]["ENDORSEMENT_VIOLATION"][0]
        trial["normalized_status"] = "COMMITTED"
        trial["post"]["exists"] = True
        trial["post"]["state_sha256"] = HEX_C
        res = a2.validate(item)
        self.assertEqual(res["status"], "FAIL")
        self.assertEqual(res["unauthorized_state_change_count"], 1)
        self.assertEqual(res["trials"][1]["status"], "FAIL")

    def test_unexpected_valid_rejection_is_failure_not_invalid(self):
        item = example()
        item["conditions"]["RESTORED"][0]["normalized_status"] = "REJECTED"
        self.assertEqual(a2.validate(item)["trials"][2]["status"], "FAIL")

    def test_fabric_query_mandatory_even_if_client_says_rejected(self):
        item = example()
        item["conditions"]["ENDORSEMENT_VIOLATION"][0]["post"]["query_ref"] = ""
        self.assertEqual(a2.validate(item)["trials"][1]["status"], "INVALID")

    def test_unchanged_hash_required_on_violation_existing_state(self):
        item = example()
        t = item["conditions"]["ENDORSEMENT_VIOLATION"][0]
        t["pre"]["exists"] = True
        t["pre"]["state_sha256"] = HEX_A
        t["post"]["exists"] = True
        t["post"]["state_sha256"] = HEX_B
        res = a2.validate(item)
        self.assertEqual(res["trials"][1]["status"], "FAIL")
        self.assertEqual(res["unauthorized_state_change_count"], 1)

    def test_valid_commit_requires_readback_of_expected_state(self):
        item = example()
        item["conditions"]["NORMAL"][0]["post"]["state_sha256"] = HEX_B
        self.assertEqual(a2.validate(item)["trials"][0]["status"], "FAIL")

    def test_duplicate_world_state_key_is_invalid(self):
        item = example()
        item["conditions"]["RESTORED"][0]["world_state_key"] = item["conditions"]["NORMAL"][0]["world_state_key"]
        self.assertEqual(a2.validate(item)["status"], "INVALID")

    def test_wrong_source_system_and_missing_exact_payload_rejected(self):
        item = example()
        t = item["conditions"]["NORMAL"][0]
        t["authenticated_source_system_id"] = "unapproved-source"
        t["payload_sha256"] = None
        res = a2.validate(item)
        self.assertEqual(res["trials"][0]["status"], "INVALID")
        self.assertTrue(any("source-system" in e for e in res["trials"][0]["errors"]))
        self.assertTrue(any("exact-payload" in e for e in res["trials"][0]["errors"]))

    def test_missing_join_manifest_digest_rejected(self):
        item = example()
        item["record_manifest_sha256"] = ""
        self.assertEqual(a2.validate(item)["status"], "INVALID")

    def test_nonfinite_latency_is_invalid(self):
        for value in (float("nan"), float("inf"), -1):
            with self.subTest(value=value):
                item = example()
                item["conditions"]["NORMAL"][0]["response_time_ms"] = value
                self.assertEqual(a2.validate(item)["trials"][0]["status"], "INVALID")

    def test_json_cli_writes_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / "original.json", Path(folder) / "check.json"
            source.write_text(json.dumps(example()), encoding="utf-8")
            original = source.read_bytes()
            cp = subprocess.run([sys.executable, str(SCRIPT), "--evidence", str(source),
                                 "--output", str(output)], capture_output=True, text=True, timeout=8)
            self.assertEqual(cp.returncode, 0, cp.stderr)
            self.assertEqual(source.read_bytes(), original)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["qualification"], "SUPPLIED_EVIDENCE_VALIDATION_ONLY")
            self.assertFalse(result["counted_research"])

    def test_cli_refuses_to_overwrite_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "original.json"
            source.write_text(json.dumps(example()), encoding="utf-8")
            cp = subprocess.run([sys.executable, str(SCRIPT), "--evidence", str(source),
                                 "--output", str(source)], capture_output=True, text=True, timeout=8)
            self.assertNotEqual(cp.returncode, 0)
            self.assertEqual(json.loads(source.read_text(encoding="utf-8"))["test_id"], "A2")


if __name__ == "__main__":
    unittest.main()
