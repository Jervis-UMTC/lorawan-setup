import fs from 'node:fs';import path from 'node:path';import {spawnSync} from 'node:child_process';
const base='lorawan-network-server-gateway/documentation/', dir=base+'word-src/';
const original=dir+'.manual-chapter6-qa.docx',candidate=dir+'.manual-chapters1-6-screens-qa.docx';
const exe=path.join(process.env.USERPROFILE,'.rel-ai-mcp','extensions','.bin','officecli.exe');
const log=[];
function cli(...a){const r=spawnSync(exe,a,{encoding:'utf8',timeout:48000,maxBuffer:4500000,env:{...process.env,OFFICECLI_SKIP_UPDATE:'1'}});log.push({action:a[0],status:r.status,msg:(r.stdout||r.stderr||'').slice(0,150)});if(r.status!==0)throw Error(a[0]+': '+(r.stderr||r.stdout||r.error?.message));return (r.stdout||'').trim()}
const root=base+'assets/live-gateway-20260922/';
const screens=[
[94,'01-luci-login.png','Screen 2C. Gateway-01 LuCI sign-in at the management address.'],
[108,'09-backup-flash.png','Screen 2D. System → Backup / Flash Firmware: choose Generate archive, not Reset or Flash image.'],
[133,'02-concentratord-global.png','Screen 3A. Concentratord → Global configuration: enabled, SX1302 / SX1303.'],
[133,'03-concentratord-sx1302-as923.png','Screen 3B. SX1302 / SX1303: RAK5146, AS923 and SPI/USB unchecked.'],
[158,'04b-mqtt-forwarder-configuration.png','Screen 3C. MQTT Forwarder → MQTT configuration: topic prefix as923 and loopback broker.'],
[194,'06-network-interfaces.png','Screen 4A. Network → Interfaces: choose Edit on lte, not br-lan or wwan.'],
[194,'07-lte-interface-general.png','Screen 4B. lte → General Settings: QMI Cellular and the DITO APN.'],
[194,'07b-lte-interface-advanced.png','Screen 4C. lte → Advanced Settings: check default-route and DNS controls.'],
[243,'04b-mqtt-forwarder-configuration.png','Screen 5A. MQTT Forwarder publishes to the local broker; use the shell checks below for Mosquitto buffer and bridge status.']
];
try{
 if(!fs.existsSync(original)||fs.statSync(original).size<1900000)throw Error('Chapters 1–6 base not present');
 if(fs.existsSync(candidate)){try{cli('close',candidate)}catch{}fs.unlinkSync(candidate)}
 fs.copyFileSync(original,candidate);
 for(const [idx,file,caption] of [...screens].reverse()){
  const fn=root+file;if(!fs.existsSync(fn)||fs.statSync(fn).size<8000)throw Error('Missing captured screenshot '+fn);
  const r=cli('add',candidate,'/body','--type','paragraph','--prop','text= ','--prop','align=center','--prop','keepNext=true','--prop','spaceBefore=5pt');
  const pic=r.match(/\/body\/p\[[^\]]+\]/)?.[0];if(!pic)throw Error('No paragraph path '+r);
  cli('add',candidate,pic,'--type','picture','--prop','src='+fn,'--prop','width=14.7cm','--prop','height=10cm','--prop','alt='+caption);
  cli('move',candidate,pic,'--before','/body/p['+idx+']');
  const q=cli('add',candidate,'/body','--type','paragraph','--prop','text='+caption,'--prop','size=8.6pt','--prop','align=center','--prop','color=#475569','--prop','keepLines=true','--prop','spaceAfter=7pt');
  const cap=q.match(/\/body\/p\[[^\]]+\]/)?.[0];if(!cap)throw Error('No caption paragraph '+q);
  cli('move',candidate,cap,'--after',pic);
 }
 cli('save',candidate);cli('close',candidate);cli('validate',candidate);
 fs.writeFileSync(dir+'SCREEN-BY-SCREEN-INSERT-LOG.json',JSON.stringify({screens:screens.length,bytes:fs.statSync(candidate).size,log},null,2));
 console.log('SCREENS_QA_READY',screens.length,fs.statSync(candidate).size);
}catch(e){fs.writeFileSync(dir+'SCREEN-BY-SCREEN-INSERT-ERROR.txt',String(e.stack||e)+'\n'+JSON.stringify(log.slice(-8),null,2));console.error('SCREENS_QA_FAILED',e.message);process.exitCode=1}
