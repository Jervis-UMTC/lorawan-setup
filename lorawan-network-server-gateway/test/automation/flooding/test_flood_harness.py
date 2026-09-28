#!/usr/bin/env python3
"""F1/F2 result-validation regression tests; does not generate network traffic."""
from __future__ import annotations
import importlib.util
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

import flood_session as fs

TARGET=Path(__file__).with_name("flood_harness.py")
spec=importlib.util.spec_from_file_location("flood_harness",TARGET)
assert spec and spec.loader
f=importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)

def window(delivered=1,unauthorized=0):
    return {"VALID_DELIVERED":str(delivered),"UNAUTHORIZED_UPLINKS":str(unauthorized),
            "UNAUTHORIZED_OUTBOX":str(unauthorized)}

def guard(emu=1,fake=0):
    return {"FAKE_UPLINKS_TOTAL":str(fake),"FAKE_OUTBOX_TOTAL":str(fake),
            "EMU_LAST_2M":str(emu)}

def f1(rate=10,seconds=5):
    target=rate*seconds
    return {"planned":target,"launched":target,"accepted":0,"rejected":target,
            "target_observed":target,"local_errors":0}

def f2(rate=10,seconds=5):
    target=rate*seconds
    return {"planned":target,"generated":target,"published":target,"received":target,
            "rejected":target,"accepted":0}

class FloodOfflineTests(unittest.TestCase):
    def test_f1_zero_rate_baseline(self):
        self.assertEqual(f.validate_run("F1",0,5,f1(0),window(),guard(),False),[])

    def test_f1_positive_workload_counts(self):
        self.assertEqual(f.validate_run("F1",10,5,f1(),window(),guard(),False),[])

    def test_f1_unobserved_broker_connections_rejected(self):
        load=f1();load["target_observed"]-=1
        self.assertTrue(any("broker-observed" in x for x in
            f.validate_run("F1",10,5,load,window(),guard(),False)))

    def test_f1_accepted_invalid_or_local_errors_rejected(self):
        load=f1();load["accepted"]=1;load["local_errors"]=1
        errors=f.validate_run("F1",10,5,load,window(),guard(),False)
        self.assertTrue(any("accepted invalid" in x for x in errors))
        self.assertTrue(any("local/unobserved" in x for x in errors))

    def test_f2_zero_rate_baseline(self):
        self.assertEqual(f.validate_run("F2",0,5,f2(0),window(),guard(),False),[])

    def test_f2_positive_workload_counts(self):
        self.assertEqual(f.validate_run("F2",10,5,f2(),window(),guard(),False),[])

    def test_f2_missing_generator_or_target_records_rejected(self):
        load=f2(); load["generated"]-=1;load["received"]-=1
        errors=f.validate_run("F2",10,5,load,window(),guard(),False)
        self.assertTrue(any("generated" in x for x in errors))
        self.assertTrue(any("received" in x for x in errors))

    def test_unapproved_db_rows_rejected_for_both_tests(self):
        for test, load in (("F1",f1()),("F2",f2())):
            with self.subTest(test=test):
                errors=f.validate_run(test,10,5,load,window(unauthorized=1),guard(fake=1),False)
                self.assertTrue(any("unauthorized uplinks" in x for x in errors))
                self.assertTrue(any("global fake outbox" in x for x in errors))

    def test_no_legitimate_telemetry_fails_both_tests(self):
        for test,load in (("F1",f1()),("F2",f2())):
            with self.subTest(test=test):
                errors=f.validate_run(test,10,5,load,window(delivered=0),guard(emu=0),True)
                self.assertIn("no recent legitimate EMU-01 telemetry",errors)
                self.assertIn("no legitimate EMU-01 delivery during flood window",errors)

    def test_missing_guard_evidence_fails_closed(self):
        for test,load in (("F1",f1()),("F2",f2())):
            with self.subTest(test=test):
                self.assertTrue(f.validate_run(test,10,5,load,window(),{},False))

    def test_completed_rehearsal_recovery_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            stamp="20260921-143817"
            for rate in (0,10,50):
                run_id=f"F2-rehearsal-r{rate}-n1-{stamp}"
                rd=base/run_id
                (rd/"derived").mkdir(parents=True)
                (rd/"metadata").mkdir()
                (rd/"raw").mkdir()
                (rd/"raw"/"source.txt").write_text(f"real-proof-{rate}",encoding="utf-8")
                with (rd/"metadata"/"SHA256SUMS.csv").open("w",newline="",encoding="utf-8") as handle:
                    writer=csv.writer(handle)
                    writer.writerow(("relative_path","sha256","bytes"))
                    data=(rd/"raw"/"source.txt").read_bytes()
                    writer.writerow(("raw/source.txt",hashlib.sha256(data).hexdigest(),len(data)))
                (rd/"derived"/"run-status.txt").write_text("RECORDED_UNCLASSIFIED\n",encoding="utf-8")
                result={"run_id":run_id,"rate_per_second":rate,"repetition":1,"formal":False,
                        "duration_seconds":30,"recovery_seconds":30,"status":"PASS","errors":[],
                        "recorder_returncode":0,"load":f2(rate,30),"window":window(),
                        "db_guard":guard()}
                (rd/"derived"/"flood-harness-result.json").write_text(json.dumps(result),encoding="utf-8")
            data=fs.recover("F2",stamp,check_cleanup=False,results_dir=base)
            self.assertEqual(data["status"],"WINDOWS_PASS_OPERATOR_TIMEOUT")
            self.assertEqual(data["operator_exit_code"],None)
            self.assertFalse(data["counted_research"])
            self.assertEqual(data["manifest_files_verified"],3)
            self.assertEqual(len(data["results"]),3)
            (base/f"F2-rehearsal-r10-n1-{stamp}"/"raw"/"source.txt").write_text("modified",encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError,"tampered evidence"):
                fs.recover("F2",stamp,check_cleanup=False,results_dir=base)

    def test_recovery_missing_rate_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError,"incomplete rehearsal"):
                fs.recover("F2","20260921-143817",check_cleanup=False,
                           results_dir=Path(temp))

    def test_session_checkpoints_first_rate_if_next_window_fails(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as patches:
            patches.enter_context(mock.patch.object(f,"ROOT",Path(temp)))
            patches.enter_context(mock.patch.object(f,"require_files"))
            patches.enter_context(mock.patch.object(f.RC,"validate_static_contract"))
            patches.enter_context(mock.patch.object(f.RC,"validate_flood_profile"))
            actions=patches.enter_context(mock.patch.object(f,"action",return_value="OK"))
            patches.enter_context(mock.patch.object(f,"start_tunnel",return_value=object()))
            stop=patches.enter_context(mock.patch.object(f,"stop_tunnel"))
            one=patches.enter_context(mock.patch.object(f,"one_run",
                         side_effect=[{"run_id":"first","status":"PASS","errors":[]},
                                      RuntimeError("second-window-failure")]))
            patches.enter_context(mock.patch.object(sys,"argv",["flood_harness.py","F2",
                                    "--rehearsal-seconds","30"]))
            with self.assertRaisesRegex(RuntimeError,"second-window-failure"):
                f.main()
            sessions=list((Path(temp)/"chapter4-results"/"dos-flooding"/"_sessions").glob("F2-*.json"))
            self.assertEqual(len(sessions),1)
            j=json.loads(sessions[0].read_text(encoding="utf-8"))
            self.assertEqual(j["status"],"INCOMPLETE")
            self.assertEqual(j["operator_exit_code"],2)
            self.assertEqual(len(j["results"]),1)
            self.assertEqual(j["results"][0]["run_id"],"first")
            self.assertIn("second-window-failure",j["failure"])
            stop.assert_called_once()
            self.assertIn(mock.call(f.ULC01,"flood-listener-stop"),actions.call_args_list)
            self.assertIn(mock.call(f.ULC03,"flood-branch-remove"),actions.call_args_list)

    def test_completed_session_written_only_after_cleanup(self):
        with tempfile.TemporaryDirectory() as temp, ExitStack() as patches:
            patches.enter_context(mock.patch.object(f,"ROOT",Path(temp)))
            patches.enter_context(mock.patch.object(f,"require_files"))
            patches.enter_context(mock.patch.object(f.RC,"validate_static_contract"))
            patches.enter_context(mock.patch.object(f.RC,"validate_flood_profile"))
            patches.enter_context(mock.patch.object(f,"action",return_value="OK"))
            patches.enter_context(mock.patch.object(f,"start_tunnel",return_value=object()))
            patches.enter_context(mock.patch.object(f,"stop_tunnel"))
            patches.enter_context(mock.patch.object(f,"one_run",side_effect=[
                {"run_id":f"rate-{rate}","status":"PASS","errors":[]} for rate in (0,10,50)]))
            patches.enter_context(mock.patch.object(sys,"argv",["flood_harness.py","F2",
                                    "--rehearsal-seconds","30"]))
            self.assertEqual(f.main(),0)
            session=next((Path(temp)/"chapter4-results"/"dos-flooding"/"_sessions").glob("F2-*.json"))
            j=json.loads(session.read_text(encoding="utf-8"))
            self.assertEqual(j["status"],"COMPLETE")
            self.assertEqual(j["operator_exit_code"],0)
            self.assertEqual(j["expected_runs"],3)
            self.assertEqual(len(j["results"]),3)

if __name__=="__main__":
    unittest.main()
