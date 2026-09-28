#!/usr/bin/env python3
"""S1 SEC replay helper regression: mocked USB, no network or RF transmission."""
from __future__ import annotations
import base64
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from contextlib import redirect_stdout
from io import StringIO

TARGET=Path(__file__).with_name("sec02_replay.py")
spec=importlib.util.spec_from_file_location("sec02_replay",TARGET)
assert spec and spec.loader
s1=importlib.util.module_from_spec(spec)
spec.loader.exec_module(s1)

PAYLOAD=b"\x40"+b"\x00"*11

def fixture(payload=PAYLOAD):
    return {"fixture_version":"sec02-exact-lorawan-replay-v1",
            "phy_payload_hex":payload.hex().upper(),
            "phy_payload_sha256":hashlib.sha256(payload).hexdigest(),
            "frequency_hz":923200000,"spreading_factor":7,"bandwidth_hz":125000,
            "rui3_coding_rate_parameter":0,"preamble_symbols":8,
            "tx_power_dbm":14,"syncword_hex":"3444","iq_inversion":0}

class S1OfflineTests(unittest.TestCase):
    def test_valid_data_uplink_only(self):
        self.assertTrue(s1.valid_data_up(PAYLOAD))
        self.assertFalse(s1.valid_data_up(b"\x40"))
        self.assertFalse(s1.valid_data_up(b"\x00"+b"\x00"*11))

    def test_parse_journal_ignores_corrupted_envelopes(self):
        valid=json.dumps({"record_body":{"sequence":5,
                "phy_payload_base64":base64.b64encode(PAYLOAD).decode()}})
        rows=s1.parse_journal_records("bad json\n"+valid+"\n"+
                json.dumps({"record_body":{"phy_payload_base64":"!!!"}}))
        self.assertEqual(len(rows),1)
        self.assertEqual(s1.data_up_record(rows)["payload"],PAYLOAD)

    def test_no_acceptable_uplink_fails(self):
        with self.assertRaisesRegex(RuntimeError,"no LoRaWAN data-uplink"):
            s1.data_up_record([{"payload":b"\x40","body":{"sequence":1}}])

    def test_radio_parameters_parsed(self):
        log="Frame received, uplink_id: 17, count_us: 100, freq: 923200000, bw: 125000, mod: LORA, dr: SF7"
        val=s1.parse_radio_rows(log)
        self.assertEqual(val["17"]["frequency_hz"],923200000)
        self.assertEqual(val["17"]["bandwidth_hz"],125000)

    def run_mock_send(self, value, *, dry=True, park_error=False):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"fixture.json"
            path.write_text(json.dumps(value),encoding="utf-8")
            args=SimpleNamespace(fixture=str(path),result="",dry_run=dry)
            ser=MagicMock()
            ser.is_open=True
            with (patch.object(s1,"ensure_result_path",side_effect=lambda p:p),
                  patch.object(s1,"find_sec_port",return_value="COM-MOCK") as port,
                  patch.object(s1.serial,"Serial",return_value=ser) as serial_open,
                  patch.object(s1,"at_fresh",return_value=["OK"]),
                  patch.object(s1,"park_sec",return_value=(
                      ["PARK_ERROR AT+NWM=1: RuntimeError"] if park_error else ["VERIFY AT+NWM=1"])),
                  redirect_stdout(StringIO()) as output):
                result=s1.cmd_send(args)
                status=json.loads(path.with_name("fixture-send.json").read_text()) if not dry else {}
                return result,status,output.getvalue(),port.call_count,serial_open.call_count

    def test_hash_tampering_rejected_pre_usb(self):
        value=fixture();value["phy_payload_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"SHA-256 mismatch"):
            self.run_mock_send(value)

    def test_short_payload_rejected_pre_usb(self):
        with self.assertRaisesRegex(ValueError,"complete LoRaWAN"):
            self.run_mock_send(fixture(b"\x40"))

    def test_non_uplink_payload_rejected_pre_usb(self):
        with self.assertRaisesRegex(ValueError,"complete LoRaWAN"):
            self.run_mock_send(fixture(b"\x00"+b"\x00"*11))

    def test_unsupported_spreading_factor_rejected(self):
        value=fixture();value["spreading_factor"]=13
        with self.assertRaisesRegex(ValueError,"RF values"):
            self.run_mock_send(value)

    def test_dry_run_never_opens_usb(self):
        rc,_,output,port_calls,open_calls=self.run_mock_send(fixture())
        self.assertEqual(rc,0)
        self.assertEqual(port_calls,0)
        self.assertEqual(open_calls,0)
        self.assertIn("AT+PSEND=<PHYPAYLOAD sha256=",output)

    def test_parking_failure_cannot_claim_success(self):
        rc,result,output,_,open_calls=self.run_mock_send(fixture(),dry=False,park_error=True)
        self.assertEqual(rc,2)
        self.assertEqual(result["restored_state"],"FAILED")
        self.assertTrue(result["txp2p_done"])
        self.assertIn("SEC_REPLAY_SENT=FAIL",output)
        self.assertEqual(open_calls,0)  # USB owned only by at_fresh, not cmd_send

    def test_parking_ack_produces_qualified_mock_result(self):
        rc,result,output,_,_=self.run_mock_send(fixture(),dry=False)
        self.assertEqual(rc,0)
        self.assertEqual(result["restored_state"],"VERIFIED")
        self.assertIn("SEC_REPLAY_SENT=PASS",output)

    def test_unsupported_rui3_command_fails_promptly(self):
        ser=MagicMock()
        ser.readline.side_effect=[b"AT+PCRYPT=0\r\n",b"AT_COMMAND_NOT_FOUND\r\n"]
        with self.assertRaisesRegex(RuntimeError,"AT_COMMAND_NOT_FOUND"):
            s1.at(ser,"AT+PCRYPT=0",timeout=.6)
        self.assertEqual(ser.readline.call_count,2)

    def test_forge_invalid_mic_preserves_devaddr_and_never_writes_keys(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/"captured.json";out=Path(td)/"forged.json"
            original=fixture();original["gateway_uplink_id"]="controlled-1"
            original["accepted_fcnt"]=4
            src.write_text(json.dumps(original),encoding="utf-8")
            rows=[{"dev_eui":s1.EMU_DEV_EUI,"uplink_id":"controlled-1",
                   "phy_payload_sha256":original["phy_payload_sha256"],
                   "event_key":"legitimate-key","f_cnt":"4"},
                  {"dev_eui":s1.EMU_DEV_EUI,"uplink_id":"later-accepted",
                   "phy_payload_sha256":"f"*64,"event_key":"later-key","f_cnt":"12"}]
            with (patch.object(s1,"ensure_result_path",side_effect=lambda p:Path(p)),
                  patch.object(s1,"packetflow_rows",return_value=rows),
                  redirect_stdout(StringIO())):
                rc=s1.cmd_forge_invalid_mic(SimpleNamespace(fixture=str(src),output=str(out)))
            self.assertEqual(rc,0)
            forged=json.loads(out.read_text(encoding="utf-8"))
            before=bytes.fromhex(original["phy_payload_hex"])
            after=bytes.fromhex(forged["phy_payload_hex"])
            self.assertEqual(before[1:5],after[1:5])
            self.assertEqual(int.from_bytes(after[6:8],"little"),44)
            self.assertEqual(after[-1],before[-1]^1)
            self.assertEqual(forged["source_control_event_key"],"legitimate-key")
            self.assertEqual(hashlib.sha256(after).hexdigest(),forged["phy_payload_sha256"])
            self.assertEqual(json.loads(src.read_text(encoding="utf-8"))["phy_payload_hex"],
                             original["phy_payload_hex"])

    def test_forge_without_accepted_control_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/"captured.json";out=Path(td)/"forged.json"
            original=fixture();original["gateway_uplink_id"]="controlled-1"
            src.write_text(json.dumps(original),encoding="utf-8")
            with (patch.object(s1,"ensure_result_path",side_effect=lambda p:Path(p)),
                  patch.object(s1,"packetflow_rows",return_value=[])):
                with self.assertRaisesRegex(RuntimeError,"not uniquely bound"):
                    s1.cmd_forge_invalid_mic(SimpleNamespace(fixture=str(src),output=str(out)))
            self.assertFalse(out.exists())

if __name__=="__main__":
    unittest.main()
