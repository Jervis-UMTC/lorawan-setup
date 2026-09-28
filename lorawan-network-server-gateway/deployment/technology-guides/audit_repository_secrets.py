#!/usr/bin/env python3
"""Privacy-preserving scan of non-archived project Markdown. Output locations, never values."""
from pathlib import Path
import json,re,datetime
project=Path(__file__).resolve().parents[2]
out=Path(__file__).resolve().parent/"FINAL-REPOSITORY-MARKDOWN-SECRET-SCAN.json"
excluded={"chapter4-results",".dev-cache",".git","node_modules",".venv","archive"}
known=re.compile(r"(?i)jervis\d{8,}")
pem=re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE KEY-----")
uri=re.compile(r"(?i)\b(?:postgresql?|redis|rediss|mqtts?)://[^\s:/@]+:([^\s/@]+)@")
assignment=re.compile(r"(?i)\b(?:appkey|nwkkey|secret_id|client_secret|access_key|authorization)\s*[:=]\s*['\"]?([a-z0-9+/_=.\-]{24,})")
hits=[];files=0
for p in project.rglob("*.md"):
 if any(x in excluded for x in p.parts):continue
 files+=1
 for i,line in enumerate(p.read_text(encoding="utf-8-sig",errors="replace").splitlines(),1):
  k=[]
  if known.search(line):k.append("credential-like-literal")
  if pem.search(line):k.append("private-key-header")
  for m in uri.finditer(line):
   if not(m.group(1).startswith("<") and m.group(1).endswith(">")):k.append("inline-uri-credential")
  for m in assignment.finditer(line):
   if not(m.group(1).startswith("<") and m.group(1).endswith(">")):k.append("sensitive-assignment")
  for reason in sorted(set(k)):hits.append({"file":str(p.relative_to(project)).replace("\\","/"),"line":i,"type":reason})
out.write_text(json.dumps({"generated_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),"files_scanned":files,"potential_unredacted_matches":len(hits),"findings":hits,"values_disclosed":False,"scope":"non-archived Markdown excluding vendor/cache/raw counted evidence; does not inspect Git history"},indent=2)+"\n",encoding="utf-8")
print("REPOSITORY_MARKDOWN_SECRET_AUDIT_WRITTEN")
