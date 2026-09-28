#!/usr/bin/env python3
"""Pure parse-only Bash/PowerShell audit of Markdown fenced operator blocks. Never runs block content."""
from pathlib import Path
import subprocess,json,re,tempfile,shutil,datetime
root=Path(__file__).resolve().parent
blocks=[]
for f in root.glob("*.md"):
 lines=f.read_text(encoding="utf-8-sig").splitlines()
 opening=None
 for i,line in enumerate(lines,1):
  m=re.match(r"^\s*(~~~|```)([A-Za-z0-9_-]*)",line)
  if not m: continue
  if opening is None:opening=(i,m.group(1),m.group(2).lower())
  elif opening[1]==m.group(1):
   line0,fence,lang=opening
   if lang in ("bash","sh","powershell","ps1"):blocks.append({"file":f.name,"start":line0,"lang":lang,"source":"\n".join(lines[line0:i-1])+"\n"})
   opening=None
report={"generated_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),"scope":"Markdown bash/sh/PowerShell blocks; syntax only, no command execution","total_blocks":len(blocks),"bash":{"total":0,"parsed":0,"failed":[],"tool_unavailable":False},"powershell":{"total":0,"parsed":0,"failed":[],"tool_unavailable":False}}
bash_supported=False
try:
 bash_check=subprocess.run([shutil.which("bash"),"-n"],input="echo syntax_only\\n",capture_output=True,text=True,timeout=4) if shutil.which("bash") else None
 bash_supported=bool(bash_check is not None and bash_check.returncode==0)
except (subprocess.TimeoutExpired,OSError,TypeError):pass
for b in blocks:
 if b["lang"] in ("bash","sh"):
  d=report["bash"];d["total"]+=1
  if not bash_supported: d["tool_unavailable"]=True;continue
  try:
   p=subprocess.run(["bash","-n"],input=b["source"],capture_output=True,text=True,timeout=4)
   if p.returncode==0:d["parsed"]+=1
   else:d["failed"].append({"file":b["file"],"start":b["start"],"kind":"SHELL_PARSE_FAILED"})
  except (subprocess.TimeoutExpired,OSError):d["failed"].append({"file":b["file"],"start":b["start"],"kind":"SHELL_PARSE_UNAVAILABLE"})
ps=[b for b in blocks if b["lang"] in ("powershell","ps1")]
report["powershell"]["total"]=len(ps)
if ps and shutil.which("powershell"):
 with tempfile.TemporaryDirectory(prefix="lorawan_doc_parse_") as td:
  inp=Path(td)/"blocks.json";out=Path(td)/"parse.json"
  inp.write_text(json.dumps(ps),encoding="utf-8")
  script=Path(td)/"parse.ps1"
  script.write_text("""
param([string]$InputPath,[string]$OutputPath)
$blocks=Get-Content -LiteralPath $InputPath -Raw | ConvertFrom-Json
$results=@()
foreach($b in $blocks) {
 $tokens=$null; $errors=$null
 $null=[System.Management.Automation.Language.Parser]::ParseInput([string]$b.source,[ref]$tokens,[ref]$errors)
 if($errors.Count -gt 0) {
    $results+=@{file=$b.file;start=$b.start;kind='POWERSHELL_PARSE_FAILED';errors=$errors.Count}
 } else { $results+=@{file=$b.file;start=$b.start;kind='PASS'} }
}
ConvertTo-Json -InputObject @($results) -Depth 4 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
""",encoding="utf-8")
  try:
   proc=subprocess.run(["powershell","-NoProfile","-NonInteractive","-File",str(script),"-InputPath",str(inp),"-OutputPath",str(out)],capture_output=True,text=True,timeout=40)
   if proc.returncode==0 and out.is_file():
    r=json.loads(out.read_text(encoding="utf-8-sig"));r=r if isinstance(r,list) else [r]
    report["powershell"]["parsed"]=sum(x["kind"]=="PASS" for x in r)
    report["powershell"]["failed"]=[x for x in r if x["kind"]!="PASS"]
   else:report["powershell"]["tool_unavailable"]=True
  except (subprocess.TimeoutExpired,OSError,ValueError):report["powershell"]["tool_unavailable"]=True
else:report["powershell"]["tool_unavailable"]=bool(ps)
ast_file=root/"FINAL-POWERSHELL-AST-AUDIT.json"
if ast_file.is_file():
 try:
  a=json.loads(ast_file.read_text(encoding="utf-8-sig"))
  report["powershell"]={"total":a["total"],"parsed":a["parsed"],"failed":a["failed"],"tool_unavailable":False,"method":"host PowerShell AST Parser.ParseInput direct -Command; no block execution"}
 except (OSError,ValueError,KeyError):pass
(root/"FINAL-COMMAND-SYNTAX-AUDIT.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
print("COMMAND_SYNTAX_AUDIT_WRITTEN")
