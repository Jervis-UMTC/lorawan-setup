#!/usr/bin/env python3
"""Offline A1 MQTT parser/contract regressions (not live broker qualification)."""
from __future__ import annotations
import importlib.util
import unittest
from pathlib import Path

TARGET = Path(__file__).with_name("a1_mqtt_harness.py")
spec = importlib.util.spec_from_file_location("a1_mqtt_harness", TARGET)
assert spec and spec.loader
a1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a1)

class A1MQTTContractTests(unittest.TestCase):
    def row(self, condition: str, trial: int, actual: str, delivered: int, *, expected: str | None = None, ms: int = 8) -> str:
        expected = a1.EXPECTED[condition] if expected is None else expected
        return f"AUTH_TRIAL|{condition}|{trial}|{expected}|{actual}|{ms}|{delivered}"

    def normal_rows(self):
        return a1.parse_trials("\n".join(
            self.row(condition, trial, a1.EXPECTED[condition], int(condition == "MQTT_ALLOWED"))
            for condition in a1.CONDITIONS for trial in range(1, 11)
        ))

    def test_full_thirty_trial_contract(self):
        rows = self.normal_rows()
        self.assertEqual(len(rows), 30)
        self.assertEqual(a1.validate(rows, 10), [])
        self.assertEqual(sum(r["delivered_to_observer"] for r in rows), 10)
        self.assertEqual(sum(r["unauthorized_state_change"] for r in rows), 0)

    def test_prohibited_delivery_is_recorded_as_state_change(self):
        rows = self.normal_rows()
        rows[-1]["delivered_to_observer"] = True
        rows[-1]["unauthorized_state_change"] = True
        rows[-1]["actual_decision"] = "ALLOW"
        rows[-1]["correct_decision"] = False
        rows[-1]["false_acceptance"] = True
        self.assertTrue(a1.validate(rows, 10))

    def test_forged_expected_decision_rejected(self):
        rows = self.normal_rows()
        rows[-1]["expected_decision"] = "ALLOW"
        rows[-1]["actual_decision"] = "ALLOW"
        rows[-1]["correct_decision"] = True
        self.assertIn("invalid expected decision", " ".join(a1.validate(rows, 10)))

    def test_incomplete_trials_rejected(self):
        rows = self.normal_rows()
        self.assertTrue(a1.validate(rows[:-1], 10))

    def test_invalid_observation_format_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "delivery proof"):
            a1.parse_trials(self.row("MQTT_ALLOWED", 1, "ALLOW", 2))
        with self.assertRaisesRegex(RuntimeError, "malformed"):
            a1.parse_trials("AUTH_TRIAL|MQTT_ALLOWED|1|ALLOW|ALLOW|10")

    def test_negative_latency_rejected(self):
        rows = self.normal_rows()
        rows[0]["response_time_ms"] = -1
        self.assertIn("negative response time", " ".join(a1.validate(rows, 10)))

if __name__ == "__main__":
    unittest.main()
