import json,subprocess,sys,tempfile,unittest
from pathlib import Path
SCRIPT=Path(__file__).with_name("fabric_sync.py")
class T(unittest.TestCase):
 def cli(self,*a,ok=True):
  c=subprocess.run([sys.executable,str(SCRIPT),*a],text=True,capture_output=True)
  if ok and c.returncode:self.fail(c.stdout+"\n"+c.stderr)
  return c
 def test_manifest_join(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t)/"r"; self.cli("prepare-run","--test-id","P1","--run-id","P1-unit","--run-dir",str(d))
   self.cli("register-record","--run-dir",str(d),"--trial-id","t1","--source-record-id","s1","--source-type","unit","--producer","unit","--payload-json",'{"v":1}',"--expected-fabric-status","COMMITTED")
   self.cli("seal-records","--run-dir",str(d)); rec=json.loads((d/"record-manifest.json").read_text())["records"][0]
   tx=Path(t)/"tx.ndjson"; tx.write_text(json.dumps({"run_id":"P1-unit","trial_id":"t1","source_record_id":"s1","payload_sha256":rec["payload_sha256"],"normalized_status":"COMMITTED"})+"\n")
   self.cli("verify-fabric-export","--run-dir",str(d),"--transactions",str(tx),"--enforce-expected-status")
   bad=Path(t)/"bad.ndjson"; bad.write_text(json.dumps({"run_id":"P1-unit","trial_id":"t1","source_record_id":"s1","payload_sha256":"0"*64,"normalized_status":"COMMITTED"})+"\n")
   self.assertNotEqual(self.cli("verify-fabric-export","--run-dir",str(d),"--transactions",str(bad),ok=False).returncode,0)
 def test_p2_shape(self):
  with tempfile.TemporaryDirectory() as t:
   c=self.cli("prepare-p2","--output-root",t,"--session-id","P2-unit","--seconds","15","--repetitions","1","--rehearsal")
   self.assertIn("P2_PAIR_COUNT=4",c.stdout); idx=json.loads((Path(t)/"P2-unit"/"p2-session.json").read_text())
   self.assertEqual([x["planned_record_count"] for x in idx["pairs"]],[1,15,75,150])
if __name__=="__main__":unittest.main()
