import fs from 'node:fs';import path from 'node:path';import {spawnSync} from 'node:child_process';
const d='lorawan-network-server-gateway/documentation/word-src/';
const file=d+'.manual-chapters1-6-screens-qa.docx',backup=d+'.manual-chapters1-6-before-ui-corrections.docx';
const exe=path.join(process.env.USERPROFILE,'.rel-ai-mcp','extensions','.bin','officecli.exe');
const py="from zipfile import ZipFile\nfrom xml.etree import ElementTree as E\nimport sys,json\nn='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'\nn14='{http://schemas.microsoft.com/office/word/2010/wordml}'\nroot=E.fromstring(ZipFile(sys.argv[1]).read('word/document.xml'))\nps=root.find(n+'body').findall(n+'p')\nprint(json.dumps([{'idx':i,'id':p.get(n14+'paraId'),'t':''.join(x.text or '' for x in p.iter(n+'t'))} for i,p in enumerate(ps,1)]))\n";
const x=spawnSync('py',['-3','-c',py,file],{encoding:'utf8',timeout:15000,maxBuffer:2000000});
if(x.status!==0)throw Error('Failed to inspect Word content '+x.stderr);
const ps=JSON.parse(x.stdout);
const edits=[
["Locate the gateway's Last seen, Events or Frames display.","On the gateway Dashboard, read Last seen; open LoRaWAN frames to inspect received frames."],
["Open the intended Application, then Device profiles for the device's assigned tenant.","In the tenant navigation, open Device Profiles; use the profile shown in Applications → dissertation-sensors → Devices to select the correct record."],
["Open the appropriate Application → Devices page and select the already registered device by its actual DevEUI, not only the friendly name.","Open Applications → dissertation-sensors → Devices and select the registered EMU-01 by DevEUI ac1f09fffe296d29. SEC-01 can remain intentionally unregistered and parked for security tests."],
["Gateways → Gateway-01 → Events","Gateways → Gateway-01 → LoRaWAN frames"],
["In Gateway-01's browser http://192.168.20.11/, open Network → Interfaces → lte.","In Gateway-01's browser, open Network → Interfaces, select Edit on the lte row, and view General Settings and Advanced Settings. Do not edit br-lan or wwan."]
];
const log=[];
function cli(...a){const r=spawnSync(exe,a,{encoding:'utf8',timeout:45000,maxBuffer:4500000,env:{...process.env,OFFICECLI_SKIP_UPDATE:'1'}});log.push({a:a[0],exit:r.status,msg:(r.stdout||r.stderr||'').slice(0,100)});if(r.status!==0)throw Error(a[0]+': '+(r.stderr||r.stdout));return (r.stdout||'').trim()}
try{
 fs.copyFileSync(file,backup);
 for(const [old,nw] of edits){
 const hits=ps.filter(p=>p.t.includes(old));
 if(hits.length!==1)throw Error('Expected 1 paragraph matching '+old+'; found '+hits.length);
 const p=hits[0],node=p.id?'/body/p[@paraId='+p.id+']':'/body/p['+p.idx+']';
 cli('set',file,node,'--prop','text='+p.t.replace(old,nw));
 }
 for(const prefix of ['Screen 6A —','Screen 6B —']){
 const hits=ps.filter(p=>p.t.startsWith(prefix));
 if(hits.length!==1)throw Error('Redundant caption not found '+prefix);
 const p=hits[0],node=p.id?'/body/p[@paraId='+p.id+']':'/body/p['+p.idx+']';
 cli('remove',file,node);
 }
 cli('save',file);cli('close',file);cli('validate',file);
 fs.writeFileSync(d+'UI-CORRECTIONS-LOG.json',JSON.stringify({edits:edits.length,redundantCaptionsRemoved:2,bytes:fs.statSync(file).size,log},null,2));
 console.log('UI_CORRECTIONS_PASS',fs.statSync(file).size);
}catch(e){fs.writeFileSync(d+'UI-CORRECTIONS-ERROR.txt',String(e.stack||e)+'\n'+JSON.stringify(log.slice(-8)));console.error('UI_CORRECTIONS_FAILED',e.message);process.exitCode=1}
