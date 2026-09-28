#!/usr/bin/env python3
"""Offline T1/T2 scoring tests: entirely synthetic observations, no live readers."""
from __future__ import annotations
import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

TARGET = Path(__file__).with_name("traceability_harness.py")
spec = importlib.util.spec_from_file_location("traceability_harness", TARGET)
assert spec and spec.loader
tr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tr)

def uplink(seq: int):
    when=datetime(2026,9,21,tzinfo=timezone.utc)+timedelta(seconds=seq*15)
    return {"event_key":f"event-{seq}", "time":when.isoformat(), "dev_eui":tr.DEV_EUI,
            "gateway_id":"gateway-01", "f_cnt":str(seq), "test_sequence":str(seq)}

def measurements(seq: int):
    return [{"event_key":f"event-{seq}", "metric_name":name,
             "unit":"1", "metric_value":str(seq), "metric_text":"", "metric_bool":""}
            for name in sorted(tr.EXPECTED_SENSOR_METRICS)]

def outbox(seq: int):
    return {"source_event_key":f"event-{seq}","status":"confirmed",
            "digest_sha256":"a"*64,"fabric_tx_id":"b"*64,
            "committed_at":"2026-09-21T01:00:00Z"}

class TraceOfflineTests(unittest.TestCase):
    def test_exact_thirteen_sensor_metrics_and_fabric_link(self):
        ok,errors,detail=tr.score_record(uplink(1),measurements(1),[outbox(1)],{1})
        self.assertTrue(ok,errors)
        self.assertTrue(detail["fabric_linked"])
        self.assertEqual(detail["measurement_count"],13)

    def test_usb_powered_battery_null_has_explicit_invalid_quality(self):
        rows=measurements(1)
        battery=next(m for m in rows if m["metric_name"]=="battery_v")
        battery.update({"unit":"V","metric_value":"","metric_text":"","metric_bool":"",
                        "quality":"invalid","source_field":"battery_v"})
        ok,errors,detail=tr.score_record(uplink(1),rows,[outbox(1)],{1})
        self.assertTrue(ok,errors)
        self.assertEqual(detail["known_unavailable_measurements"],["battery_v"])
        self.assertEqual(detail["measurement_values_available_count"],12)
        battery_detail=next(m for m in detail["sensor_measurements"] if m["type"]=="battery_v")
        self.assertIsNone(battery_detail["value"])
        self.assertEqual(battery_detail["quality"],"invalid")

    def test_unqualified_missing_battery_or_other_measurement_fails(self):
        rows=measurements(1)
        battery=next(m for m in rows if m["metric_name"]=="battery_v")
        battery.update({"metric_value":"","quality":"invalid","source_field":""})
        ok,errors,_=tr.score_record(uplink(1),rows,[outbox(1)],{1})
        self.assertFalse(ok)
        self.assertIn("measurement value missing:battery_v",errors)
        battery.update({"unit":"V","source_field":"battery_v"})
        other=next(m for m in rows if m["metric_name"]=="soil_moisture_percent")
        other.update({"metric_value":"","quality":"invalid","source_field":"soil_moisture_percent"})
        ok,errors,_=tr.score_record(uplink(1),rows,[outbox(1)],{1})
        self.assertFalse(ok)
        self.assertIn("measurement value missing:soil_moisture_percent",errors)

    def test_duplicate_metric_not_masked_by_count(self):
        rows=measurements(1)
        rows[0]["metric_name"]=rows[1]["metric_name"]
        ok,errors,_=tr.score_record(uplink(1),rows,[outbox(1)],{1})
        self.assertFalse(ok)
        self.assertIn("duplicate measurement metric names",errors)

    def test_missing_required_metric_not_masked_by_unknown_name(self):
        rows=measurements(1)
        rows[0]["metric_name"]="invented_sensor"
        ok,errors,_=tr.score_record(uplink(1),rows,[outbox(1)],{1})
        self.assertFalse(ok)
        self.assertTrue(any("required sensor metrics" in e for e in errors))

    def test_missing_unit_or_source_sequence_rejected(self):
        rows=measurements(1)
        rows[0]["unit"]=""
        ok,errors,_=tr.score_record(uplink(1),rows,[outbox(1)],set())
        self.assertFalse(ok)
        self.assertTrue(any("unit missing" in e for e in errors))
        self.assertIn("matching SENSOR_TX source sequence missing",errors)

    def test_fabric_mismatched_or_duplicate_outbox_rejected(self):
        bad=outbox(1)
        bad["source_event_key"]="other-event"
        ok,errors,_=tr.score_record(uplink(1),measurements(1),[bad],{1})
        self.assertFalse(ok)
        self.assertIn("DB/Fabric source_event_key mismatch",errors)
        ok,errors,_=tr.score_record(uplink(1),measurements(1),[outbox(1),outbox(1)],{1})
        self.assertFalse(ok)
        self.assertTrue(any("outbox rows=2" in e for e in errors))

    def test_t1_duplicate_selected_events_cannot_pass(self):
        with patch.object(tr,"select_rows",return_value=(
            [uplink(1),uplink(1)],{}, {},{1}
        )):
            with self.assertRaisesRegex(RuntimeError,"duplicated event keys"):
                tr.t1_score(Path("offline"),2,"mock-node")

    def test_t1_reused_sensor_sequence_cannot_pass(self):
        rows=[uplink(1),uplink(2)]
        rows[1]["test_sequence"]="1"
        with patch.object(tr,"select_rows",return_value=(rows,{}, {},{1,2})):
            with self.assertRaisesRegex(RuntimeError,"reuse source sequence"):
                tr.t1_score(Path("offline"),2,"mock-node")

    def test_t2_clean_five_record_chronology(self):
        rows=[uplink(i) for i in range(1,6)]
        all_ms=[m for i in range(1,6) for m in measurements(i)]
        bundle={"uplinks":rows,"measurements":all_ms,
                "outbox":[outbox(i) for i in range(1,6)]}
        with (patch.object(tr,"select_rows",return_value=(rows,{}, {},set(range(1,6)))),
              patch.object(tr,"retrieval_bundle",return_value=(bundle,0.01))):
            result=tr.t2_score(Path("offline"),1,"mock-node")
        self.assertEqual(result["status"],"PASS")
        self.assertEqual(result["records_complete"],5)
        self.assertEqual(result["chronological_order_accuracy_percent"],100.0)

    def test_t2_nonconsecutive_sequence_fails(self):
        rows=[uplink(i) for i in range(1,6)]
        rows[2]["test_sequence"]="9"
        all_ms=[m for i in range(1,6) for m in measurements(i)]
        bundle={"uplinks":rows,"measurements":all_ms,
                "outbox":[outbox(i) for i in range(1,6)]}
        with (patch.object(tr,"select_rows",return_value=(rows,{}, {},set(range(1,10)))),
              patch.object(tr,"retrieval_bundle",return_value=(bundle,0.01))):
            result=tr.t2_score(Path("offline"),1,"mock-node")
        self.assertEqual(result["status"],"FAIL")
        self.assertTrue(any("not consecutive" in e for e in result["sequences"][0]["errors"]))

if __name__=="__main__":
    unittest.main()
