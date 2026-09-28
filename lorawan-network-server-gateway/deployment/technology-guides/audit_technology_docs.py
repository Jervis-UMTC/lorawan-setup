#!/usr/bin/env python3
"""Non-mutating technology-documentation audit. Never copies potential secret values into output."""
from __future__ import annotations
import json, re, hashlib, datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]
MD=sorted(ROOT.glob("*.md"))
NUM=[p for p in MD if re.match(r"^(?:0[1-9]|1[0-9]|2[01])-.*\.md$",p.name)]
issues=[]
stats={"files":len(MD),"numbered_guides":len(NUM),"code_blocks":0,"executable_blocks":0,"template_lines":0,"link_targets":0,"files_with_fences":0,"secret_candidates":0}
def flag(category,p,line,detail):
    issues.append({"category":category,"file":p.name,"line":line,"detail":detail})
for p in MD:
    data=p.read_text(encoding="utf-8-sig"); ls=data.splitlines()
    fences=[(i,l) for i,l in enumerate(ls,1) if re.match(r"^\s*(~~~|```)",l)]
    if fences:stats["files_with_fences"]+=1
    stack=None
    for i,l in fences:
        d=re.match(r"^\s*(~~~|```)(\w+)?",l)
        if stack is None:stack=(i,d.group(1),d.group(2) or "")
        elif d.group(1)==stack[1]:
            stats["code_blocks"]+=1
            if stack[2].lower() in ("bash","sh","powershell","ps1","sql"):
                stats["executable_blocks"]+=1
                for j in range(stack[0]+1,i):
                    line=ls[j-1]
                    if re.search(r"<[A-Z][A-Z0-9_\- .]*>",line) and not line.lstrip().startswith(("#","--")):
                        stats["template_lines"]+=1
                    if re.search(r"grep\s+(?:-\w+\s+)*['\"]`",line):
                        flag("invalid-quoted-regex",p,j,"Regex begins with a backtick rather than an anchor")
                    if re.search(r"(?:^|\s)(?:rm\s+-rf|docker\s+(?:system|volume)\s+prune|FLUSHALL|pg_resetwal|bao\s+operator\s+init)(?:\s|$)",line,re.I):
                        pre=" ".join(ls[max(0,j-5):j]).lower()
                        if not any(z in pre for z in ("never","do not","fresh","only","do not run","not runnable")):
                            flag("destructive-command-review",p,j,"Potentially disruptive command in operative block")
            stack=None
    if stack is not None:flag("unclosed-fence",p,stack[0],"Unclosed Markdown code block")
    for i,line in enumerate(ls,1):
        for hit in re.finditer(r"(?<!!)\[[^]]*\]\(([^)]+)\)",line):
            ref=hit.group(1).split("#",1)[0]
            if not ref or re.match(r"^[a-z][a-z0-9+.-]*://",ref,re.I) or ref.startswith(("mailto:","#")):continue
            stats["link_targets"]+=1
            if not (p.parent/ref).exists():flag("missing-relative-link",p,i,"Relative target does not exist")
        if "-----BEGIN" in line and "PRIVATE KEY" in line:
            stats["secret_candidates"]+=1;flag("private-key-material",p,i,"Possible PEM private key heading")
        elif re.search(r"(?i)\b(?:password|passwd|appkey|nwkkey|secret_id|client_secret|access_key|authorization)\s*[:=]\s*['\"]?(?!<|\$|\{|protected|redacted|example|none|not\s)([A-Za-z0-9+/=_\-.]{12,})",line):
            stats["secret_candidates"]+=1;flag("secret-value-review",p,i,"Possible credential assignment; value intentionally omitted")
        elif re.search(r"(?i)(?:postgres(?:ql)?|redis|rediss|mqtts?)://[^\s/@:]+:[^\s/@]+@",line):
            stats["secret_candidates"]+=1;flag("url-secret-review",p,i,"Possible inline URI password; value intentionally omitted")
        if re.search(r"(?i)wifi is (?:automatic(?:ally)? )?fallback|wi-fi is automatic fallback",line):
            flag("wifi-fallback-claim",p,i,"Check against tracked no-assumed-Wi-Fi fallback")
        if re.search(r"(?i)(?:latest|current|today).*\b(?:2026-09-1[0-9]|2026-09-21)\b",line) and p.name not in ("GUIDE-OVERSIGHT-AUDIT-2026-09-21.md","CURRENT-DOCUMENTATION-BASELINE.md"):
            if any(k in line.lower() for k in ("gate","health","status","panel","dashboard","readiness","snapshot")):
                flag("dated-current-language",p,i,"Dated operational claim; verify or label checkpoint")
from collections import Counter
output={
 "generated_utc":datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
 "scope":"deployment/technology-guides/*.md only; excludes protected env, deployment binaries and research raw results",
 "stats":stats,
 "categories":dict(Counter(i["category"] for i in issues)),
 "findings":issues,
 "command_validation":"static parsing/heuristics only; no executable command was run against production",
 "secret_handling":"Potential secret values never included in this report",
}
(ROOT/"FINAL-STATIC-AUDIT.json").write_text(json.dumps(output,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print("FINAL_STATIC_AUDIT_WRITTEN")
