import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const base='lorawan-network-server-gateway/documentation/';
const dir=base+'word-src/';
const original=base+'LoRaWAN-Operator-Manual-WIP.docx';
const candidate=dir+'.manual-chirpstack-screen-by-screen-qa.docx';
const exe=path.join(process.env.USERPROFILE,'.rel-ai-mcp','extensions','.bin','officecli.exe');
const screens=[
 ['04-gateway-list-clean.png','001004E3','6C','Gateways: find Gateway-01 and confirm EUI 0016c001f139a1cb.'],
 ['05-gateway-detail-focused.png','001004E5','6D','Gateway-01 dashboard: check the region and last-seen time.'],
 ['06-gateway-frames-clean.png','001004E7','6E','LoRaWAN frames: inspect received frames and timestamps for this gateway.'],
 ['07-device-profiles-clean.png','001004EF','6F','Device profiles: open EMU-01 RAK4631 AS923.'],
 ['08-applications-clean.png','001004F9','6G','Applications: select dissertation-sensors.'],
 ['09-application-devices-clean.png','001004FB','6H','Application devices: select the exact EMU-01 DevEUI.'],
 ['10-emu-overview-clean.png','001004FD','6I','EMU-01 overview: compare its profile and last-seen time.'],
 ['11-emu-events-clean.png','001004FF','6J','EMU-01 Events: identify the up event and its received timestamp.']
];
const actions=[];
function cli(...args){
 const r=spawnSync(exe,args,{encoding:'utf8',timeout:45000,maxBuffer:2500000,env:{...process.env,OFFICECLI_SKIP_UPDATE:'1'}});
 actions.push({action:args[0],status:r.status,summary:(r.stdout||r.stderr||'').slice(0,130)});
 if(r.status!==0)throw Error('OfficeCLI '+args[0]+': '+(r.stderr||r.stdout||r.error?.message));
 return (r.stdout||'').trim();
}
try{
 if(!fs.existsSync(original)||fs.statSync(original).size<2500000)throw Error('Current complete manual missing');
 if(fs.existsSync(candidate)){try{cli('close',candidate)}catch{}fs.unlinkSync(candidate)}
 fs.copyFileSync(original,candidate);
 let count=0;
 for(const [name,anchor,label,title] of screens){
  const src=base+'assets/live-chirpstack-20260922/'+name;
  if(!fs.existsSync(src)||fs.statSync(src).size<30000)throw Error('Real rendered capture absent '+src);
  const target='/body/p[@paraId='+anchor+']';
  const added=cli('add',candidate,'/body','--type','paragraph','--prop','text= ','--prop','align=center','--prop','keepNext=true','--prop','spaceBefore=8pt');
  const picturePara=added.match(/\/body\/p\[[^\]]+\]/)?.[0];
  if(!picturePara)throw Error('OfficeCLI paragraph ID missing '+added);
  cli('add',candidate,picturePara,'--type','picture','--prop','src='+src,'--prop','width=14.4cm','--prop','height='+(name==='05-gateway-detail-focused.png'?'7.65cm':'9.0cm'),'--prop','alt='+title);
  cli('move',candidate,picturePara,'--before',target);
  const addedCaption=cli('add',candidate,'/body','--type','paragraph','--prop','text=Screen '+label+'. '+title,'--prop','size=8.6pt','--prop','italic=true','--prop','align=center','--prop','color=#475569','--prop','keepLines=true','--prop','spaceAfter=9pt');
  const captionPara=addedCaption.match(/\/body\/p\[[^\]]+\]/)?.[0];
  if(!captionPara)throw Error('OfficeCLI caption ID missing '+addedCaption);
  cli('move',candidate,captionPara,'--after',picturePara);
  count++;
 }
 cli('save',candidate);cli('close',candidate);
 cli('validate',candidate);
 fs.writeFileSync(dir+'CHAPTER6-ACTUAL-SCREENS-INSERT-LOG.json',JSON.stringify({count,screens:screens.map(x=>x[0]),bytes:fs.statSync(candidate).size,actions},null,2));
 console.log('CH6_REAL_SCREENS_INSERTED',count,fs.statSync(candidate).size);
}catch(e){
 fs.writeFileSync(dir+'CHAPTER6-ACTUAL-SCREENS-INSERT-ERROR.txt',String(e.stack||e)+'\n'+JSON.stringify(actions.slice(-6),null,2));
 console.error('CH6_SCREEN_INSERT_FAILED',e.message);process.exitCode=1;
}
