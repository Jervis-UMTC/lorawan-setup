#!/usr/bin/env python3
"""Small read-only, credential-redacted live checkpoint; never starts/stops services or experiments."""
from __future__ import annotations
import datetime,json,subprocess,shutil,re,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent
key=Path.home()/".ssh"/"id_ed25519_research_recorder"
hosts={"ulc01":"opsadmin@143.198.205.54","ulc02":"opsadmin@165.22.253.127","ulc03":"opsadmin@159.223.50.57","gateway":"root@192.168.20.11"}
result={"generated_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),"method":"restricted SSH forced-command read-only; no admin SSH, no live mutation; values are sanitized","hosts":{},"grafana":{}}
def run(host,verb,timeout=12):
 if not key.is_file() or not shutil.which("ssh"):return (False,"CLIENT_KEY_OR_SSH_UNAVAILABLE","")
 cmd=["ssh","-T","-i",str(key),"-o","BatchMode=yes","-o","StrictHostKeyChecking=yes","-o","ConnectTimeout=4","-o","ConnectionAttempts=1",hosts[host],verb]
 try:
  p=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=timeout)
  if p.returncode:return(False,"SSH_OR_REMOTE_COMMAND_FAILED",str(p.returncode))
  return(True,p.stdout,"")
 except subprocess.TimeoutExpired:return(False,"TIMEOUT","")
 except (OSError,ValueError):return(False,"SSH_INVOKE_FAILED","")
for host in hosts:
 d=result["hosts"][host]={}
 ok,s,_=run(host,"version");d["restricted_ssh"]=bool(ok);d["wrapper_version"]=s.strip()[:80] if ok else s
 if not ok:continue
 ok,s,_=run(host,"snapshot",timeout=22)
 d["snapshot_status"]="PASS" if ok else s
 if ok:
  vals=dict(re.findall(r"(?m)^(timestamp_utc|hostname)=(.+)$",s))
  d["timestamp_utc"]=vals.get("timestamp_utc")
  d["observed_hostname"]=vals.get("hostname")
  if host=="gateway":
   d["cloud_tcp_probe"]=re.search(r"tcp_8883=(REACHABLE|UNREACHABLE|PROBE_TOOL_MISSING)",s).group(1) if re.search(r"tcp_8883=(REACHABLE|UNREACHABLE|PROBE_TOOL_MISSING)",s) else "NOT_REPORTED"
   d["established_cloud_bridge_sockets"]=len(re.findall(r"(?m)^tcp\s+\d+\s+\d+\s+\S+\s+\S+:8883\s+ESTABLISHED",s))
   d["lte_route"]=bool(re.search(r"(?m)^default\s+.*\bwwan0\b|^129\.212\.208\.168\s+.*\bwwan0\b",s))
   d["lte_interface_present"]="--- wwan0 ---" in s and bool(re.search(r"\bwwan0\b",s))
  else:
   docker=s.split("--- docker ---",1)[-1].split("--- listeners ---",1)[0]
   d["docker_container_names"]=sorted(set(re.findall(r"(?m)^([a-zA-Z0-9_.-]+)\|",docker)))[:50]
   d["docker_containers_reported"]=len(d["docker_container_names"])
 if host!="gateway":
  ok,s,_=run(host,"db-role");d["db_role"]=s.strip()[:25] if ok else "UNVERIFIED:"+s
  ok,s,_=run(host,"evidence-ready");d["evidence_ready_status"]="PASS" if ok and "NOT_READY" not in s else "UNVERIFIED_OR_FAIL"
  if ok:d["evidence_ready_services"]=[x.split("|")[1] for x in s.splitlines() if x.startswith("READY|")]
# Grafana loopback tunnel is a separate optional read-only check; API is deliberately unauthenticated health only.
try:
 with urllib.request.urlopen("http://127.0.0.1:3000/api/health",timeout=3) as r:
  v=json.load(r);result["grafana"]={"local_tunnel_api_health_http":r.status,"database":v.get("database"),"version":v.get("version"),"dashboard_uid_and_panel_count":"NOT_VERIFIED_WITH_AUTHENTICATED_API"}
except Exception:result["grafana"]={"local_tunnel_api_health_http":"NOT_REACHABLE","dashboard_uid_and_panel_count":"NOT_VERIFIED_WITH_AUTHENTICATED_API"}
(ROOT/"LIVE-READONLY-CHECKPOINT.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print("LIVE_READONLY_CHECKPOINT_WRITTEN")
