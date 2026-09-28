import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const base='lorawan-network-server-gateway/documentation/';
const dir=base+'word-src/';
const original=base+'LoRaWAN-Operator-Manual-WIP.docx';
const candidate=dir+'.manual-remaining-fullpage-qa.docx';
const asset=base+'assets/live-gateway-fullpage-headless-20260922/';
const exe=path.join(process.env.USERPROFILE,'.rel-ai-mcp','extensions','.bin','officecli.exe');
const calls=[];
function cli(...a){
 const r=spawnSync(exe,a,{encoding:'utf8',timeout:48000,maxBuffer:3400000,env:{...process.env,OFFICECLI_SKIP_UPDATE:'1'}});
 calls.push({verb:a[0],exit:r.status,msg:(r.stdout||r.stderr||'').slice(0,150)});
 if(r.status!==0)throw Error('officecli '+a[0]+': '+(r.stderr||r.stdout||r.error?.message));
 return (r.stdout||'').trim();
}
function dimensions(src){
 const r=spawnSync('py',['-3','-c','from PIL import Image;import sys;im=Image.open(sys.argv[1]);print(*im.size)',src],{encoding:'utf8',timeout:8000});
 if(r.status!==0)throw Error('Missing image dimensions: '+src+' '+r.stderr);
 const [w,h]=r.stdout.trim().split(/\s+/).map(Number);if(!w||!h)throw Error('Bad dimensions '+src);
 return {w,h};
}
const pic=[
 ['00100571','01-luci-login.png','Actual gateway login, all visible controls.'],
 ['0010056D','09-backup-flash.png','Gateway OS full backup and flash actions; generate an archive without resetting firmware.'],
 ['00100569','02-concentratord-global.png','Concentratord global setting and selected SX1302/SX1303 chipset.'],
 ['00100565','03-concentratord-sx1302-as923.png','RAK5146 SPI, plain AS923, antenna gain and gateway EUI override.'],
 ['00100561','04b-mqtt-forwarder-top.png','MQTT Forwarder upper form: AS923 topic prefix and local broker address.'],
 ['0010055D','06-network-interfaces.png','OpenWrt complete Network/Interfaces overview; edit the lte row.'],
 ['00100559','07-lte-interface-general.png','LTE General Settings: modem, DITO APN, authentication and PDP selector.'],
 ['00100555','07b-lte-interface-advanced.png','LTE Advanced Settings upper form: default gateway and peer DNS controls; lower fields require UCI inspection.'],
 ['00100551','04b-mqtt-forwarder-top.png','MQTT Forwarder upper form: the radio sends to the local Mosquitto broker.']
];
const textEdit=[
 ['00100563','Screen 3C. MQTT Forwarder: confirm as923 and tcp://127.0.0.1:1883. Continue to the next screen for QoS.'],
 ['00100553','Screen 5A. Local MQTT destination. Continue to Screen 5B for QoS and session settings.'],
 ['00100557','Screen 4C. Advanced Settings: default route OFF and peer DNS ON. For fields below the visible form, use the effective UCI checks in this chapter.'],
 ['0010031E','Set the APN for the commissioned DITO SIM to internet.dito.ph. Use QMI Cellular with control device /dev/cdc-wdm0 and no authentication. The approved effective UCI pdptype is IP; the live LuCI menu can display IPv4/IPv6, so verify the effective UCI result before changing a working modem. Do not substitute an APN from another carrier.'],
 ['001003F5','uname -n']
];
function appendScreen(src,caption,anchor,position,alt,width=14.25){
 const d=dimensions(src),height=(width*d.h/d.w);
 if(height>20.1)throw Error('Image too tall, must split: '+src+' '+height);
 const q=cli('add',candidate,'/body','--type','paragraph','--prop','text= ','--prop','align=center','--prop','keepNext=true','--prop','spaceBefore=5pt');
 const node=q.match(/\/body\/p\[[^\]]+\]/)?.[0];if(!node)throw Error('No image paragraph '+q);
 cli('add',candidate,node,'--type','picture','--prop','src='+src,'--prop','width='+width+'cm','--prop','height='+height.toFixed(2)+'cm','--prop','alt='+alt);
 cli('move',candidate,node,'--'+position,'/body/p[@paraId='+anchor+']');
 const c=cli('add',candidate,'/body','--type','paragraph','--prop','text='+caption,'--prop','align=center','--prop','italic=true','--prop','size=8.6pt','--prop','color=#475569','--prop','spaceAfter=8pt','--prop','keepLines=true');
 const cap=c.match(/\/body\/p\[[^\]]+\]/)?.[0];if(!cap)throw Error('No caption paragraph '+c);
 cli('move',candidate,cap,'--after',node);
}
try{
 if(!fs.existsSync(original)||fs.statSync(original).size<3400000)throw Error('Incomplete or absent canonical');
 if(fs.existsSync(candidate)){try{cli('close',candidate)}catch{}fs.unlinkSync(candidate)}
 fs.copyFileSync(original,candidate);
 for(const [id,file,alt] of pic){
  const src=asset+file;
  if(!fs.existsSync(src)||fs.statSync(src).size<20000)throw Error('Missing actual screenshot '+src);
  const {w,h}=dimensions(src);
  const width=14.25,height=width*h/w;
  if(height>19.5)throw Error('Replace image must split '+file);
  cli('set',candidate,'/body/p[@paraId='+id+']/r[2]','--prop','src='+src,'--prop','width='+width+'cm','--prop','height='+height.toFixed(2)+'cm','--prop','alt='+alt);
 }
 for(const [id,text] of textEdit)cli('set',candidate,'/body/p[@paraId='+id+']','--prop','text='+text);
 appendScreen(asset+'04c-mqtt-forwarder-bottom.png','Screen 3D. MQTT Forwarder lower form: confirm QoS 1; leave existing client settings unchanged.','00100563','after','Real lower part of MQTT Forwarder form');
 appendScreen(asset+'04c-mqtt-forwarder-bottom.png','Screen 5B. MQTT Forwarder lower form: QoS 1 and clean-session option.','00100553','after','Real lower part of MQTT Forwarder form');
 appendScreen(asset+'gateway-lte-readonly-output.png','Screen 4D. Actual read-only LTE output. No default route appeared at this sample time; recheck before recording LTE routing PASS.','0010037C','after','Read-only gateway LTE command output from the actual commissioned hardware');
 appendScreen(asset+'gateway-mosquitto-readonly-output.png','Screen 5C. Actual broker process, loopback-only listener, persistence and queue configuration.','0010041F','before','Read-only gateway Mosquitto command output transcribed faithfully from the device');
 appendScreen(asset+'gateway-bridges-readonly-output.png','Screen 5D. Actual bridge identities, directions, and cloud sockets. No private-key contents shown.','0010044D','before','Read-only gateway bridge command output transcribed faithfully from the device');
 cli('save',candidate);cli('close',candidate);cli('validate',candidate);
 fs.writeFileSync(dir+'REMAINING-FULLPAGE-BUILD-LOG.json',JSON.stringify({imagesReplaced:pic.length,imagesAdded:5,paragraphsCorrected:textEdit.length,bytes:fs.statSync(candidate).size,calls},null,2));
 console.log('FULLPAGE_REVIEW_READY',fs.statSync(candidate).size);
}catch(e){fs.writeFileSync(dir+'REMAINING-FULLPAGE-BUILD-ERROR.txt',String(e.stack||e)+'\n'+JSON.stringify(calls.slice(-10),null,2));console.error('FULLPAGE_REVIEW_FAILED',e.message);process.exitCode=1;}
