import importlib.util
import pathlib
import unittest

PATH=pathlib.Path(__file__).with_name("research_contract.py")
spec=importlib.util.spec_from_file_location("research_contract",PATH)
rc=importlib.util.module_from_spec(spec); spec.loader.exec_module(rc)

class ContractTests(unittest.TestCase):
    def test_static(self):
        rc.validate_static_contract()
    def test_p1_formal_denominator(self):
        self.assertEqual(rc.FORMAL["P1"]["duration_seconds"],1800)
        self.assertEqual(rc.FORMAL["P1"]["source_interval_seconds"],15)
        self.assertEqual(rc.FORMAL["P1"]["planned_attempts_per_run"],120)

    def test_p2_counts(self):
        self.assertEqual([rc.p2_planned_records(x) for x in rc.FORMAL["P2"]["rates_tps"]],[20,300,1500,3000])
        self.assertEqual(sum(rc.p2_planned_records(x) for x in rc.FORMAL["P2"]["rates_tps"])*3,14460)
    def test_a1(self):
        self.assertEqual(len(rc.A1_CONDITIONS),9)
        self.assertEqual(rc.FORMAL["A1"]["total_attempts"],90)
    def test_traceability(self):
        self.assertEqual(rc.FORMAL["T1"]["records"]+rc.FORMAL["T2"]["records"],60)
        self.assertEqual(rc.FORMAL["T1"]["trials"]+rc.FORMAL["T2"]["sequences"],20)
    def test_s2_blocked(self):
        self.assertTrue(rc.FORMAL["S2"]["blocked_by_methodology"])

if __name__=="__main__":
    unittest.main()
