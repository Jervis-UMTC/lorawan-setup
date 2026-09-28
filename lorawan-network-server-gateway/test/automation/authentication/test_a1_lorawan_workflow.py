#!/usr/bin/env python3
"""Offline A1 LoRaWAN orchestration tests: all remote/USB/radio calls are mocked."""
from __future__ import annotations

import csv
import importlib.util
import io
from contextlib import redirect_stderr, redirect_stdout
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TARGET = Path(__file__).with_name("a1_lorawan_harness.py")
spec = importlib.util.spec_from_file_location("a1_lorawan_harness_workflow", TARGET)
assert spec is not None and spec.loader is not None
a1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a1)


class WorkflowTests(unittest.TestCase):
    def run_simulation(self, *, fail_condition: str = "", restore_error: bool = False):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            invalid_calls = []
            valid_calls = []
            park_calls = []

            def fake_remote(host, command, timeout=25):
                if command != "version":
                    raise AssertionError(f"unexpected remote action {command}")
                if host == a1.SERVER:
                    return "research-recorder-server-v10\n"
                if host == a1.GATEWAY:
                    return "research-recorder-gateway-v3\n"
                raise AssertionError(f"unexpected host {host}")

            def fake_invalid(condition, trial, dev, join, key, output_dir):
                invalid_calls.append((condition, trial))
                actual = "INVALID" if condition == fail_condition else "REJECT"
                return {
                    "condition": condition, "trial": trial,
                    "expected_decision": "REJECT", "actual_decision": actual,
                    "correct_decision": actual == "REJECT",
                }

            def fake_valid(trial, package, output_dir):
                valid_calls.append(trial)
                return {
                    "condition": "LORAWAN_VALID_OTAA", "trial": trial,
                    "expected_decision": "ALLOW", "actual_decision": "ALLOW",
                    "correct_decision": True,
                }

            def fake_emu_port(pid):
                return "MOCK-DFU" if restore_error and pid == a1.EMU_DFU_PID else None

            with (
                patch.object(a1, "RESULTS", out),
                patch.object(a1, "RECORDER_KEY", TARGET),
                patch.object(a1, "remote", side_effect=fake_remote),
                patch.object(a1, "build_material", return_value=(
                    {"upload_package_sha256": "a" * 64}, Path("mock.zip"))),
                patch.object(a1, "sec_baseline", return_value={"njs": "0"}),
                patch.object(a1, "identity_guard", return_value="A1_LORAWAN_GUARD=PASS\n"),
                patch.object(a1, "enter_emu_dfu", return_value="MOCK-DFU"),
                patch.object(a1, "invalid_trial", side_effect=fake_invalid),
                patch.object(a1, "valid_trial", side_effect=fake_valid),
                patch.object(a1, "park_sec", side_effect=lambda: park_calls.append("park")),
                patch.object(a1, "emu_port", side_effect=fake_emu_port),
                patch.object(a1, "flash_emu", side_effect=RuntimeError("mock restore failed")),
                patch("sys.argv", ["a1_lorawan_harness.py", "--rehearsal"])
            ):
                # Expected negative-path log lines are captured; the outer suite
                # should show PASS/FAIL for the offline unit test, not mock errors.
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    code = a1.main()

            summaries = list(out.glob("*/a1-lorawan-summary.json"))
            self.assertEqual(len(summaries), 1)
            summary = json.loads(summaries[0].read_text(encoding="utf-8"))
            trials_csv = summaries[0].with_name("a1-lorawan-trials.csv")
            with trials_csv.open(newline="", encoding="utf-8") as fh:
                csv_rows = list(csv.DictReader(fh))
            return code, summary, csv_rows, invalid_calls, valid_calls, park_calls

    def test_successful_rehearsal_persists_exactly_three_trials_and_cleanup(self):
        code, summary, csv_rows, invalid, valid, parks = self.run_simulation()
        self.assertEqual(code, 0)
        self.assertEqual(summary["status"], "PASS")
        self.assertFalse(summary["formal"])
        self.assertFalse(summary["counted_research"])
        self.assertEqual(summary["attempts_per_condition"], 1)
        self.assertEqual([condition for condition, _ in invalid],
                         ["LORAWAN_WRONG_APPKEY", "LORAWAN_UNREGISTERED_DEVEUI"])
        self.assertEqual(valid, [1])
        self.assertEqual(len(summary["trials"]), 3)
        self.assertEqual(len(csv_rows), 3)
        self.assertEqual(summary["sec_cleanup"], "PASS")
        self.assertEqual(summary["emu_cleanup"], "PASS")
        self.assertGreaterEqual(len(parks), 2)

    def test_invalid_result_stops_counting_and_still_saves_failure(self):
        code, summary, csv_rows, invalid, valid, parks = self.run_simulation(
            fail_condition="LORAWAN_WRONG_APPKEY")
        self.assertNotEqual(code, 0)
        self.assertEqual(summary["status"], "FAIL")
        self.assertEqual(len(summary["trials"]), 1)
        self.assertEqual(len(csv_rows), 1)
        self.assertEqual(valid, [])
        self.assertEqual(summary["sec_cleanup"], "PASS")
        self.assertTrue(parks)

    def test_failed_dfu_restore_cannot_be_published_as_pass(self):
        code, summary, csv_rows, invalid, valid, parks = self.run_simulation(
            restore_error=True)
        self.assertNotEqual(code, 0)
        self.assertEqual(summary["status"], "FAIL")
        self.assertIn("mock restore failed", summary["emu_cleanup"])
        self.assertEqual(len(csv_rows), 3)


if __name__ == "__main__":
    unittest.main()
