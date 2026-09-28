// Complete Part 01 after build_part01.mjs. Uses OfficeCLI only; no research or infrastructure changes.
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
const exe=path.join(process.env.USERPROFILE,".rel-ai-mcp","extensions",".bin","officecli.exe");
const doc="lorawan-network-server-gateway/documentation/LoRaWAN-Operator-Manual-WIP.docx";
const src="lorawan-network-server-gateway/documentation/word-src/";
function office(...args){
 const r=spawnSync(exe,args,{encoding:"utf8",timeout:60000,maxBuffer:2e6});
 if(r.status!==0)throw Error(`officecli ${args[0]} failed: ${r.stderr||r.stdout}`);
 return r.stdout||"";
}
if(!fs.existsSync(doc))throw Error("Word document not found.");
const existing=office("query",doc,"style");
for(const [id,label,size,color] of [
 ["Heading1","Heading 1","18pt","#12636A"],
 ["Heading2","Heading 2","13pt","#12636A"],
 ["Title","Title","27pt","#12636A"],
 ["Subtitle","Subtitle","16pt","#334155"]
]){
 if(existing.includes(`/styles/${id} `))continue;
 office("add",doc,"/styles","--type","style",
   "--prop",`id=${id}`,"--prop",`name=${label}`,
   "--prop","type=paragraph","--prop","basedOn=Normal",
   "--prop",`size=${size}`,"--prop","bold=true",
   "--prop",`color=${color}`,"--prop","spaceBefore=10pt",
   "--prop","spaceAfter=5pt","--prop","qFormat=true");
}
const styles=JSON.parse(fs.readFileSync(src+"part01-style-batch.json","utf8"));
for(const o of styles){
 office("set",doc,o.path,...Object.entries(o.props).flatMap(([k,v])=>["--prop",`${k}=${v}`]));
}
let rows=0;
for(const [i,count] of [9,8,11,9].entries()){
 for(let j=1;j<=count;j++){
   const args=["set",doc,`/body/tbl[${i+1}]/tr[${j}]`,"--prop","cantSplit=true"];
   if(j===1)args.push("--prop","header=true");
   office(...args);rows++;
 }
}
office("refresh",doc);
office("validate",doc);
console.log(`PART01_FINISH_PASS styles=${styles.length} protected_table_rows=${rows} bytes=${fs.statSync(doc).size}`);
