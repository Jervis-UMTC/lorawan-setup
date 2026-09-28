#!/usr/bin/env python3
"""Hardware-free A1 LoRaWAN trial-evidence tests; never open serial/SSH."""
from __future__ import annotations

import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TARGET = Path(__file__).with_name("a1_lorawan_harness.py")
spec = importlib.util.spec_from_file_location("a1_lorawan_harness", TARGET)
assert spec is not None and spec.loader is not None
a1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a1)


def join_payload(dev: str = a1.LEGIT_DEV_EUI, join: str = a1.LEGIT_JOIN_EUI) -> bytes:
    return bytes([0]) + bytes.fromhex(join)[::-1] + bytes.fromhex(dev)[::-1] + b"\x01\x02" + b"\x00\x00\x00\x00"


def record(seq: int, payload: bytes | None = None) -> dict:
    p = payload if payload is not None else join_payload()
    return {"sequence": seq, "payload": p, "body": {"sequence": seq}}


class JoinEvidenceTests(unittest.TestCase):
    def test_rui3_echo_does_not_mask_real_query_value(self):
        with patch.object(a1, "sec_command", return_value=["AT+VER=?", "AT+VER=RUI_4.2.4_RAK4631", "OK"]):
            self.assertEqual(a1.query_value("AT+VER=?", "AT+VER="), "RUI_4.2.4_RAK4631")
        with patch.object(a1, "sec_command", return_value=["AT+NJS=?", "AT+NJS=0", "OK"]):
            self.assertEqual(a1.query_value("AT+NJS=?", "AT+NJS="), "0")
        with patch.object(a1, "sec_command", return_value=["AT+VER=?", "OK"]):
            with self.assertRaisesRegex(RuntimeError, "did not return a value"):
                a1.query_value("AT+VER=?", "AT+VER=")

    def matches(self, records, watermark=1, dev=a1.LEGIT_DEV_EUI, join=a1.LEGIT_JOIN_EUI):
        return a1.matching_join_requests(records, watermark, dev, join)

    def test_exact_join_matches(self):
        rows = self.matches([record(2)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["join_eui"], a1.LEGIT_JOIN_EUI)
        self.assertEqual(rows[0]["dev_eui"], a1.LEGIT_DEV_EUI)
        self.assertEqual(rows[0]["phy_sha256"], hashlib.sha256(join_payload()).hexdigest())

    def test_stale_sequence_rejected(self):
        self.assertEqual(self.matches([record(1)]), [])
        self.assertEqual(self.matches([record(0)]), [])

    def test_different_join_eui_rejected(self):
        self.assertEqual(self.matches([record(2, join_payload(join="0000000000000001"))]), [])

    def test_different_dev_eui_rejected(self):
        self.assertEqual(self.matches([record(2, join_payload(dev=a1.UNREGISTERED_DEV_EUI))]), [])

    def test_non_join_mhdr_rejected(self):
        self.assertEqual(self.matches([record(2, b"\x40" + join_payload()[1:])]), [])

    def test_truncated_and_appended_frame_rejected(self):
        self.assertEqual(self.matches([record(2, join_payload()[:-1]), record(3, join_payload() + b"\x00")]), [])

    def test_no_pre_journal_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "watermark missing"):
            a1.max_gateway_sequence([])

    def test_pre_journal_watermark(self):
        self.assertEqual(a1.max_gateway_sequence([record(12), record(7)]), 12)

    def test_wrong_key_rejection_requires_real_packet_and_stable_registered_state(self):
        dev = a1.LEGIT_DEV_EUI
        state = {"registered": "1", "dev_eui": dev, "last_seen_at": "t0",
                 "dev_addr": "aabbccdd", "session_fingerprint": "sha", "f_cnt_up": "5"}
        with (
            tempfile.TemporaryDirectory() as td,
            patch.object(a1, "chirp_state", side_effect=[dict(state), dict(state)]),
            patch.object(a1, "gateway_records", side_effect=[[record(5)], [record(5), record(6)]]),
            patch.object(a1, "set_sec_identity"),
            patch.object(a1, "sec_join_attempt", return_value=(["JOIN FAILED"], False)),
            patch.object(a1, "park_sec")
        ):
            row = a1.invalid_trial("LORAWAN_WRONG_APPKEY", 1, dev, a1.LEGIT_JOIN_EUI,
                                   a1.WRONG_APP_KEY, Path(td))
        self.assertEqual(row["actual_decision"], "REJECT")
        self.assertTrue(row["correct_decision"])
        self.assertEqual(row["join_request_count"], 1)
        self.assertGreaterEqual(row["join_observation_ms"], 0)

    def test_missing_registration_state_not_falsely_rejected(self):
        dev = a1.LEGIT_DEV_EUI
        with (
            tempfile.TemporaryDirectory() as td,
            patch.object(a1, "chirp_state", side_effect=[{"registered": "1"}, {"registered": "1"}]),
            patch.object(a1, "gateway_records", side_effect=[[record(5)], [record(5), record(6)]]),
            patch.object(a1, "set_sec_identity"),
            patch.object(a1, "sec_join_attempt", return_value=(["JOIN FAILED"], False)),
            patch.object(a1, "park_sec")
        ):
            row = a1.invalid_trial("LORAWAN_WRONG_APPKEY", 1, dev, a1.LEGIT_JOIN_EUI,
                                   a1.WRONG_APP_KEY, Path(td))
        self.assertEqual(row["actual_decision"], "INVALID_STATE_UNVERIFIED")
        self.assertFalse(row["correct_decision"])
        self.assertFalse(row["chirpstack_state_verified"])

    def test_missing_received_join_is_invalid_not_rejection(self):
        with (
            tempfile.TemporaryDirectory() as td,
            patch.object(a1, "chirp_state", side_effect=[{"registered": "0"}, {"registered": "0"}]),
            patch.object(a1, "gateway_records", side_effect=[[record(5)], [record(5)]]),
            patch.object(a1, "set_sec_identity"),
            patch.object(a1, "sec_join_attempt", return_value=(["JOIN FAILED"], False)),
            patch.object(a1, "park_sec")
        ):
            row = a1.invalid_trial("LORAWAN_UNREGISTERED_DEVEUI", 1,
                                   a1.UNREGISTERED_DEV_EUI, a1.UNREGISTERED_JOIN_EUI,
                                   a1.UNREGISTERED_APP_KEY, Path(td))
        self.assertEqual(row["actual_decision"], "INVALID")
        self.assertFalse(row["correct_decision"])

    def test_unregistered_join_does_not_count_server_state_change_as_rejection(self):
        with (
            tempfile.TemporaryDirectory() as td,
            patch.object(a1, "chirp_state", side_effect=[{"registered": "0"}, {"registered": "1"}]),
            patch.object(a1, "gateway_records", side_effect=[
                [record(5)],
                [record(5), record(6, join_payload(
                    dev=a1.UNREGISTERED_DEV_EUI, join=a1.UNREGISTERED_JOIN_EUI))]
            ]),
            patch.object(a1, "set_sec_identity"),
            patch.object(a1, "sec_join_attempt", return_value=(["JOIN FAILED"], False)),
            patch.object(a1, "park_sec")
        ):
            row = a1.invalid_trial("LORAWAN_UNREGISTERED_DEVEUI", 1,
                                   a1.UNREGISTERED_DEV_EUI, a1.UNREGISTERED_JOIN_EUI,
                                   a1.UNREGISTERED_APP_KEY, Path(td))
        self.assertEqual(row["actual_decision"], "FAIL_STATE_CHANGED")
        self.assertFalse(row["correct_decision"])

    def test_legitimate_join_missing_session_is_not_accepted(self):
        dev = a1.LEGIT_DEV_EUI
        with (
            tempfile.TemporaryDirectory() as td,
            patch.object(a1, "chirp_state", side_effect=[
                {"registered": "1", "dev_eui": dev, "session_fingerprint": ""},
                {"registered": "1", "dev_eui": dev}
            ]),
            patch.object(a1, "gateway_records", side_effect=[[record(5)], [record(5), record(6)]]),
            patch.object(a1, "flash_emu", return_value="COM-MOCK"),
            patch.object(a1, "observe_emu_join", return_value=([], True, True))
        ):
            row = a1.valid_trial(1, Path("mock.zip"), Path(td))
        self.assertFalse(row["chirpstack_state_verified"])
        self.assertEqual(row["actual_decision"], "REJECT")
        self.assertFalse(row["correct_decision"])

    def test_legitimate_join_with_matching_new_session_accepted(self):
        dev = a1.LEGIT_DEV_EUI
        with (
            tempfile.TemporaryDirectory() as td,
            patch.object(a1, "chirp_state", side_effect=[
                {"registered": "1", "dev_eui": dev, "session_fingerprint": "old"},
                {"registered": "1", "dev_eui": dev, "session_fingerprint": "new"}
            ]),
            patch.object(a1, "gateway_records", side_effect=[[record(5)], [record(5), record(6)]]),
            patch.object(a1, "flash_emu", return_value="COM-MOCK"),
            patch.object(a1, "observe_emu_join", return_value=([], True, True))
        ):
            row = a1.valid_trial(1, Path("mock.zip"), Path(td))
        self.assertTrue(row["chirpstack_state_verified"])
        self.assertEqual(row["actual_decision"], "ALLOW")
        self.assertGreaterEqual(row["join_observation_ms"], 0)

    def test_real_packet_wrong_join_eui_is_invalid(self):
        with (
            tempfile.TemporaryDirectory() as td,
            patch.object(a1, "chirp_state", side_effect=[{"registered": "0"}, {"registered": "0"}]),
            patch.object(a1, "gateway_records", side_effect=[
                [record(5)],
                [record(5), record(6, join_payload(dev=a1.UNREGISTERED_DEV_EUI,
                                                  join=a1.LEGIT_JOIN_EUI))]
            ]),
            patch.object(a1, "set_sec_identity"),
            patch.object(a1, "sec_join_attempt", return_value=(["JOIN FAILED"], False)),
            patch.object(a1, "park_sec")
        ):
            row = a1.invalid_trial("LORAWAN_UNREGISTERED_DEVEUI", 1,
                                   a1.UNREGISTERED_DEV_EUI, a1.UNREGISTERED_JOIN_EUI,
                                   a1.UNREGISTERED_APP_KEY, Path(td))
        self.assertEqual(row["actual_decision"], "INVALID")


if __name__ == "__main__":
    unittest.main()
