#!/usr/bin/env python3
"""Hardware-free P2 pair and measurement-window qualification."""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

DIR = Path(__file__).resolve().parent
TARGET = DIR / "p2_pair_runner.py"
spec = importlib.util.spec_from_file_location("p2_pair_runner", TARGET)
assert spec and spec.loader
p2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p2)
PREPARE = DIR.parent / "fabric-sync" / "fabric_sync.py"


class P2OfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        proc = subprocess.run(
            [sys.executable, str(PREPARE), "prepare-p2", "--output-root", cls.tmp.name,
             "--session-id", "P2-offline-fixture", "--seconds", "15",
             "--repetitions", "1", "--rehearsal"],
            capture_output=True, text=True, timeout=20, check=False,
        )
        if proc.returncode:
            raise RuntimeError(proc.stderr or proc.stdout)
        cls.folder = Path(cls.tmp.name) / "P2-offline-fixture"
        cls.session = p2.load_json(cls.folder / "p2-session.json")
        cls.pair = cls.session["pairs"][0]
        cls.run_manifest_path = cls.folder / cls.pair["pair_id"] / "run-manifest.json"
        cls.record_path = cls.folder / cls.pair["pair_id"] / "record-manifest.json"
        cls.run_manifest = p2.load_json(cls.run_manifest_path)
        cls.records = p2.load_json(cls.record_path)
        cls.run_manifest_hash = p2.verify_json_sidecar(cls.run_manifest_path)
        cls.record_hash = p2.verify_json_sidecar(cls.record_path)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def summary(self, mode="control"):
        start = datetime(2026, 9, 1, tzinfo=timezone.utc)
        sec = float(self.run_manifest["duration_seconds"])
        return {
            "status": "PASS", "schema_version": "1.0",
            "study_id": "zacharias-lorawan-fabric", "formal": self.run_manifest["formal"],
            "test_id": "P2", "run_id": self.run_manifest["run_id"],
            "mode": mode, "target_tps": self.run_manifest["workload"]["target_tps"],
            "measurement_seconds": sec, "measurement_start_utc": start.isoformat(),
            "measurement_end_utc": (start + timedelta(seconds=sec)).isoformat(),
            "wall_end_utc_including_drain": (start + timedelta(seconds=sec + 1)).isoformat(),
            "wall_seconds_including_drain": sec + 1,
            "planned_records": self.pair["planned_record_count"],
            "attempted_records": self.pair["planned_record_count"],
            "committed_records": self.pair["planned_record_count"] if mode == "fabric" else 0,
            "failed_records": 0, "unknown_records": 0, "max_queue_delay_ms": 0,
            "mean_client_operation_latency_ms": 0, "mean_commit_latency_ms": 0,
            "achieved_attempt_tps": self.pair["planned_record_count"] / sec,
            "achieved_commit_tps": (self.pair["planned_record_count"] / sec if mode == "fabric" else 0),
        }

    def test_real_generator_produces_consistent_pair_manifest(self):
        p2.validate_session_pairs(self.session)
        p2.validate_pair_manifests(self.pair, self.run_manifest, self.records,
                                   self.run_manifest_hash, self.record_hash, 15)
        self.assertEqual(len(self.session["pairs"]), 4)

    def test_repeated_pair_cannot_hide_missing_workload(self):
        s = copy.deepcopy(self.session)
        s["pairs"][1] = dict(s["pairs"][0], pair_id="different-name")
        with self.assertRaisesRegex(RuntimeError, "duplicate rate/repetition"):
            p2.validate_session_pairs(s)

    def test_session_missing_pair_or_wrong_count_rejected(self):
        s = copy.deepcopy(self.session)
        s["pairs"].pop()
        with self.assertRaisesRegex(RuntimeError, "pair count"):
            p2.validate_session_pairs(s)
        s = copy.deepcopy(self.session)
        s["pairs"][0]["planned_record_count"] += 1
        with self.assertRaisesRegex(RuntimeError, "planned count"):
            p2.validate_session_pairs(s)

    def test_formal_duration_drift_rejected(self):
        s = copy.deepcopy(self.session)
        s["formal"] = True
        with self.assertRaisesRegex(RuntimeError, "formal P2"):
            p2.validate_session_pairs(s)

    def test_pair_digest_and_row_mismatch_rejected(self):
        pair = dict(self.pair, record_manifest_sha256="0" * 64)
        with self.assertRaisesRegex(RuntimeError, "digest join"):
            p2.validate_pair_manifests(pair, self.run_manifest, self.records,
                                       self.run_manifest_hash, self.record_hash, 15)
        records = copy.deepcopy(self.records)
        records["records"].append(dict(records["records"][0]))
        with self.assertRaisesRegex(RuntimeError, "manifest count"):
            p2.validate_pair_manifests(self.pair, self.run_manifest, records,
                                       self.run_manifest_hash, self.record_hash, 15)

    def test_control_and_fabric_measurement_summaries(self):
        for phase in ("control", "fabric"):
            p2.validate_summary(self.summary(phase), phase,
                                self.pair["planned_record_count"], run=self.run_manifest)

    def test_mislabeled_phase_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
            p2.validate_summary(self.summary("fabric"), "control",
                                self.pair["planned_record_count"], run=self.run_manifest)

    def test_wrong_end_time_rejected(self):
        value = self.summary()
        value["measurement_end_utc"] = value["wall_end_utc_including_drain"]
        with self.assertRaisesRegex(RuntimeError, "window/drain mismatch"):
            p2.validate_summary(value, "control", self.pair["planned_record_count"], run=self.run_manifest)

    def test_drain_before_measurement_end_rejected(self):
        value = self.summary()
        value["wall_end_utc_including_drain"] = value["measurement_start_utc"]
        with self.assertRaisesRegex(RuntimeError, "window/drain mismatch"):
            p2.validate_summary(value, "control", self.pair["planned_record_count"], run=self.run_manifest)

    def test_fabric_missing_commit_and_queue_overrun_rejected(self):
        value = self.summary("fabric")
        value["committed_records"] -= 1
        with self.assertRaisesRegex(RuntimeError, "committed_records mismatch"):
            p2.validate_summary(value, "fabric", self.pair["planned_record_count"], run=self.run_manifest)
        value = self.summary()
        value["max_queue_delay_ms"] = self.run_manifest["workload"]["interval_ms"] + 1
        with self.assertRaisesRegex(RuntimeError, "queue exceeded"):
            p2.validate_summary(value, "control", self.pair["planned_record_count"], run=self.run_manifest)


    def test_run_session_formal_identity_mismatch_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "formal/rehearsal identity mismatch"):
            p2.validate_pair_manifests(
                self.pair, self.run_manifest, self.records,
                self.run_manifest_hash, self.record_hash, 15, formal=True,
            )

    def test_interval_must_match_target_tps(self):
        run = copy.deepcopy(self.run_manifest)
        run["workload"]["interval_ms"] *= 2
        with self.assertRaisesRegex(RuntimeError, "interval_ms inconsistent"):
            p2.validate_pair_manifests(
                self.pair, run, self.records,
                self.run_manifest_hash, self.record_hash, 15,
            )

    def test_exact_payload_digest_checked_even_when_manifest_is_sealed(self):
        records = copy.deepcopy(self.records)
        records["records"][0]["payload_sha256"] = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "exact payload SHA-256"):
            p2.validate_pair_manifests(
                self.pair, self.run_manifest, records,
                self.run_manifest_hash, self.record_hash, 15,
            )

    def test_missing_or_falsified_performance_metrics_rejected(self):
        summary = self.summary("fabric")
        del summary["achieved_attempt_tps"]
        with self.assertRaisesRegex(RuntimeError, "missing/invalid performance"):
            p2.validate_summary(summary, "fabric", self.pair["planned_record_count"], run=self.run_manifest)
        summary = self.summary("fabric")
        summary["achieved_commit_tps"] += 1
        with self.assertRaisesRegex(RuntimeError, "achieved_commit_tps inconsistent"):
            p2.validate_summary(summary, "fabric", self.pair["planned_record_count"], run=self.run_manifest)
        summary = self.summary("fabric")
        summary["wall_seconds_including_drain"] += 5
        with self.assertRaisesRegex(RuntimeError, "wall duration/drain"):
            p2.validate_summary(summary, "fabric", self.pair["planned_record_count"], run=self.run_manifest)

    def test_control_cannot_claim_fabric_commit(self):
        summary = self.summary("control")
        summary["committed_records"] = 1
        with self.assertRaisesRegex(RuntimeError, "committed_records mismatch"):
            p2.validate_summary(summary, "control", self.pair["planned_record_count"], run=self.run_manifest)

    def test_summary_formal_identity_cannot_be_changed(self):
        summary = self.summary()
        summary["formal"] = not self.run_manifest["formal"]
        with self.assertRaisesRegex(RuntimeError, "formal identity mismatch"):
            p2.validate_summary(summary, "control", self.pair["planned_record_count"], run=self.run_manifest)

    def test_rounded_rehearsal_count_is_not_measurement_duration(self):
        # The Go source is not compiled here (no Go on Windows/WSL). Guard the
        # documented fix until the benchmark can be rebuilt and commissioned.
        rate, seconds = (1 / 15), 20
        self.assertNotEqual(max(1, round(rate * seconds)) / rate, seconds)
        source = (DIR.parents[2] / "evidence-services" / "cloud" /
                  "cmd" / "research-fabric-benchmark" / "main.go").read_text(encoding="utf-8")
        self.assertIn('measurement := number(run, "duration_seconds")', source)


if __name__ == "__main__":
    unittest.main()
