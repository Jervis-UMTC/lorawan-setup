import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const base='lorawan-network-server-gateway/documentation/';
const dir=base+'word-src/';
const source=base+'LoRaWAN-Operator-Manual-WIP.docx';
const candidate=dir+'.manual-ste100-qa.docx';
const expected='C8CF715BF6447C9E7AB19EC49CB87980571135DF683D64E0326F03A35C721CA2';
const office=path.join(process.env.USERPROFILE,'.rel-ai-mcp','extensions','.bin','officecli.exe');
const groups=['ste-edits-ch1-3.json','ste-edits-ch4-5.json','ste-edits-ch6.json','ste-edits-supplement.json'];
const edits=groups.flatMap(file=>JSON.parse(fs.readFileSync(dir+file,'utf8')));
if(edits.length!==101)throw Error('Expected 101 STE paragraph replacements; got '+edits.length);
if(new Set(edits.map(x=>x.index)).size!==edits.length)throw Error('Duplicate paragraph edit');
const sha=spawnSync('powershell.exe',['-NoProfile','-Command','(Get-FileHash "'+source+'" -Algorithm SHA256).Hash'],{encoding:'utf8'});
if(sha.status!==0||sha.stdout.trim().toUpperCase()!==expected)throw Error('Canonical modified concurrently; abort');
if(fs.existsSync(candidate)){try{spawnSync(office,['close',candidate],{encoding:'utf8',timeout:8000})}catch{}fs.unlinkSync(candidate)}
fs.copyFileSync(source,candidate);
const py=[
'from zipfile import ZipFile',
'from xml.etree import ElementTree as E',
'import sys,json',
"w='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'",
"n14='{http://schemas.microsoft.com/office/word/2010/wordml}'",
"x=E.fromstring(ZipFile(sys.argv[1]).read('word/document.xml'))",
"p=x.find(w+'body').findall(w+'p')",
"print(json.dumps([{'index':i,'id':q.get(n14+'paraId'),'text':''.join(t.text or '' for t in q.iter(w+'t'))} for i,q in enumerate(p)]))"
].join('\n');
const scan=spawnSync('py',['-3','-c',py,source],{encoding:'utf8',timeout:12000,maxBuffer:2500000});
if(scan.status!==0)throw Error('Paragraph scan failed: '+scan.stderr);
const paras=JSON.parse(scan.stdout);
const issues=[];
const tech=s=>[...s.matchAll(/(?:\b\d{4,16}\b|\b\d+(?:\.\d+){1,3}\b|\/dev\/[A-Za-z0-9_-]+|(?:AS923|LoRaWAN|QoS|OTAA|AppKey|NwkKey|MQTT|LTE|GNSS|SX1302|SX1303|RAK5146))/g)].map(x=>x[0]);
for(const item of edits){
 const p=paras[item.index];if(!p||!p.id||!p.text)throw Error('Missing Word paragraph '+item.index);
 if(item.text===p.text)throw Error('No change in paragraph '+item.index);
 const missing=[...new Set(tech(p.text).filter(x=>!item.text.includes(x)))];
 if(missing.length)issues.push({index:item.index,old:p.text.slice(0,110),missing});
}
fs.writeFileSync(dir+'STE100-TECHNICAL-DIFF-REVIEW.json',JSON.stringify({total:edits.length,possibleLostTokens:issues},null,2)+'\n');
const summary=[];
for(let i=0;i<groups.length;i++){
 const payload=JSON.parse(fs.readFileSync(dir+groups[i],'utf8')).map(item=>{
 const p=paras[item.index];return {command:'set',path:'/body/p[@paraId='+p.id+']',props:{text:item.text}};
 });
 const file=dir+'.ste-batch-'+i+'.json';fs.writeFileSync(file,JSON.stringify(payload,null,2)+'\n');
 const run=spawnSync(office,['batch',candidate,'--input',file],{encoding:'utf8',timeout:115000,maxBuffer:3500000,env:{...process.env,OFFICECLI_SKIP_UPDATE:'1'}});
 summary.push({group:groups[i],count:payload.length,status:run.status,msg:(run.stdout||run.stderr||'').slice(0,320)});
 if(run.status!==0){fs.writeFileSync(dir+'STE100-BUILD-ERROR.json',JSON.stringify(summary,null,2));throw Error('OfficeCLI failed '+groups[i]+': '+(run.stderr||run.stdout||run.error?.message));}
}
for(const a of [['save',candidate],['close',candidate],['validate',candidate]]){
 const run=spawnSync(office,a,{encoding:'utf8',timeout:60000,maxBuffer:3500000,env:{...process.env,OFFICECLI_SKIP_UPDATE:'1'}});
 summary.push({command:a[0],status:run.status,msg:(run.stdout||run.stderr||'').slice(0,220)});
 if(run.status!==0)throw Error(a[0]+' failed '+(run.stderr||run.stdout||run.error?.message));
}
fs.writeFileSync(dir+'STE100-BUILD-LOG.json',JSON.stringify({edits:edits.length,possibleLostTokens:issues.length,candidateBytes:fs.statSync(candidate).size,summary},null,2)+'\n');
console.log('STE100_OFFICECLI_CANDIDATE',edits.length,issues.length,fs.statSync(candidate).size);
