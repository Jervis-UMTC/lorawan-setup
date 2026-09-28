#!/usr/bin/env python3
"""Offline Chapter 3 research-code checks. NEVER performs a live research run.

Only tests explicitly mapped here can report CODE_ONLY_PASS. A hardware-free
mock cannot establish reception, sensor performance, MQTT isolation, or Fabric
ledger integrity. Always use the live commissioning gates for those claims.
"""
from __future__ import annotations

import argparse
import py_compile
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent

OFFLINE_SUITES = {
    "A1": {
        "sources": (
            "research_contract.py",
            "authentication/a1_lorawan_harness.py",
            "authentication/a1_mqtt_harness.py",
        ),
        "tests": (
            (HERE, "test_research_contract.py"),
            (HERE / "authentication", "test_a1_*.py"),
        ),
        "minimum_tests": 30,
    },
    "A2": {
        "sources": (
            "research_contract.py",
            "authentication/a2_fabric_endorsement_evidence.py",
        ),
        "tests": (
            (HERE, "test_research_contract.py"),
            (HERE / "authentication", "test_a2_fabric_endorsement_evidence.py"),
        ),
        "minimum_tests": 24,
    },
    "I1": {
        "sources": (
            "research_contract.py",
            "integrity/i1_evidence.py",
        ),
        "tests": (
            (HERE, "test_research_contract.py"),
            (HERE / "integrity", "test_i1_evidence.py"),
        ),
        "minimum_tests": 24,
    },
    "I2": {
        "sources": (
            "research_contract.py",
            "integrity/i2_evidence.py",
        ),
        "tests": (
            (HERE, "test_research_contract.py"),
            (HERE / "integrity", "test_i2_evidence.py"),
        ),
        "minimum_tests": 25,
    },
    "I3": {
        "sources": (
            "research_contract.py",
            "integrity/i3_ledger_evidence.py",
        ),
        "tests": (
            (HERE, "test_research_contract.py"),
            (HERE / "integrity", "test_i3_ledger_evidence.py"),
        ),
        "minimum_tests": 39,
    },
    "P2": {
        "sources": (
            "research_contract.py",
            "fabric-sync/fabric_sync.py",
            "fabric-performance/p2_pair_runner.py",
        ),
        "tests": (
            (HERE, "test_research_contract.py"),
            (HERE / "fabric-sync", "test_fabric_sync.py"),
            (HERE / "fabric-performance", "test_p2_pair_runner.py"),
        ),
        "minimum_tests": 25,
    },
    "R2": {
        "sources": (
            "research_contract.py",
            "resilience/r2_fabric_reconciliation.py",
        ),
        "tests": (
            (HERE, "test_research_contract.py"),
            (HERE / "resilience", "test_r2_fabric_reconciliation.py"),
        ),
        "minimum_tests": 15,
    },
    "S1": {
        "sources": (
            "research_contract.py",
            "research-recorder/sec02_replay.py",
        ),
        "tests": (
            (HERE, "test_research_contract.py"),
            (HERE / "research-recorder", "test_sec02_replay.py"),
        ),
        "minimum_tests": 17,
    },
    "F1": {
        "sources": (
            "research_contract.py",
            "flooding/flood_harness.py",
            "flooding/flood_session.py",
        ),
        "tests": (
            (HERE, "test_research_contract.py"),
            (HERE / "flooding", "test_flood_harness.py"),
        ),
        "minimum_tests": 16,
    },
    "F2": {
        "sources": (
            "research_contract.py",
            "flooding/flood_harness.py",
            "flooding/flood_session.py",
        ),
        "tests": (
            (HERE, "test_research_contract.py"),
            (HERE / "flooding", "test_flood_harness.py"),
        ),
        "minimum_tests": 16,
    },
    "T1": {
        "sources": (
            "research_contract.py",
            "traceability/traceability_harness.py",
        ),
        "tests": (
            (HERE, "test_research_contract.py"),
            (HERE / "traceability", "test_traceability_harness.py"),
        ),
        "minimum_tests": 15,
    },
    "T2": {
        "sources": (
            "research_contract.py",
            "traceability/traceability_harness.py",
        ),
        "tests": (
            (HERE, "test_research_contract.py"),
            (HERE / "traceability", "test_traceability_harness.py"),
        ),
        "minimum_tests": 15,
    },
    "R1": {
        "sources": (
            "research_contract.py",
            "resilience/r1_internet_route_gate.py",
        ),
        "tests": (
            (HERE, "test_research_contract.py"),
            (HERE / "resilience", "test_r1_internet_route_gate.py"),
        ),
        "minimum_tests": 20,
    },
}


def run(test_id: str) -> int:
    spec = OFFLINE_SUITES[test_id]
    for relative in spec["sources"]:
        py_compile.compile(str(HERE / relative), doraise=True)
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for directory, pattern in spec["tests"]:
        suite.addTests(loader.discover(str(directory), pattern=pattern))
    if suite.countTestCases() < spec["minimum_tests"]:
        print(
            f"OFFLINE_TEST={test_id} RESULT=FAIL reason=missing_test_discovery "
            f"found={suite.countTestCases()} minimum={spec['minimum_tests']}",
            file=sys.stderr,
        )
        return 2
    result = unittest.TextTestRunner(verbosity=1, stream=sys.stdout).run(suite)
    passed = result.wasSuccessful()
    print(
        f"OFFLINE_TEST={test_id} RESULT={'CODE_ONLY_PASS' if passed else 'FAIL'} "
        f"TESTS={result.testsRun} HARDWARE_USED=NO "
        "RESEARCH_SAMPLES=0 LIVE_QUALIFICATION=NOT_PROVEN"
    )
    return 0 if passed else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("test_id", choices=sorted(OFFLINE_SUITES))
    args = parser.parse_args()
    return run(args.test_id)


if __name__ == "__main__":
    raise SystemExit(main())
