import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const d='lorawan-network-server-gateway/documentation/';
const input=d+'word-src/.visual-steps-refine-qa.docx';
const output=d+'word-src/.exact-visuals-final-qa.docx';
const exe=path.join(process.env.USERPROFILE,'.rel-ai-mcp','extensions','.bin','officecli.exe');
const log=[];
function run(...args){
 const p=spawnSync(exe,args,{encoding:'utf8',timeout:32000,maxBuffer:2e6});
 log.push({op:args[0],at:args[2],status:p.status,stderr:(p.stderr||'').slice(0,270)});
 if(p.status!==0)throw Error(args[0]+' '+args[2]+' '+(p.stderr||p.stdout||p.error?.message));
 return p.stdout||'';
}
try{
 if(!fs.existsSync(input))throw Error('Prior visual QA input missing');
 if(fs.existsSync(output)){try{run('close',output)}catch(e){}fs.unlinkSync(output)}
 fs.copyFileSync(input,output);
 let arch=d+'assets/project-architecture-chapter1-v2.png';
 let rak=d+'assets/rak5146-pihat-step2-exact-product-photo.png';
 if(!fs.existsSync(arch)||!fs.existsSync(rak))throw Error('Missing authentic visual');
 run('set',output,'/body/p[@paraId=00100016]/r[2]','--prop','src='+arch,'--prop','width=15.5cm','--prop','height=6.37cm','--prop','alt=Project architecture: EMU-01 to Gateway-01; telemetry local MQTT and LTE to both cloud brokers then ChirpStack, one Node-RED SQL writer and Grafana; independent gateway journal uploads retained raw evidence to SeaweedFS; both cloud-broker witnesses feed verifier; verified eligible source payload enters OpenBao-signed Fabric HRC path.');
 run('set',output,'/body/p[@paraId=001000F1]/r[2]','--prop','src='+rak,'--prop','width=11.3cm','--prop','height=8.88cm','--prop','alt=Real RAKwireless product photo of RAK5146 SPI module seated on black Pi HAT; top edge ports marked LoRa and GPS; example not photo of installed gateway.');
 run('set',output,'/body/p[13]','--prop','text=Figure 1.1. Exact project flow: AS923 EMU-01 RF reaches Gateway-01; local MQTT/LTE and both cloud brokers carry telemetry; the independent journal, both MQTT witnesses and PostgreSQL are compared by the verifier before eligible Fabric anchoring.');
 run('set',output,'/body/p[49]','--prop','text=Figure 2.1. Actual RAK5146 Pi HAT product photo by RAKwireless. Seat the concentrator on its Pi HAT; connect the antenna to the port labeled LoRa (not GPS). The gateway SIM7600 is a separate USB dongle, not shown.');
 run('set',output,'/body/p[75]','--prop','text=If Imager offers Raspberry Pi OS customisation, skip it for the approved custom OpenWrt Gateway OS: the stock setup fields are not the commissioned gateway settings. At the Writing summary, verify BOTH the approved custom .img.gz filename and YOUR microSD. Click Write only after matching both. On the erase dialog, read the actual device name and click I understand, erase and write only for YOUR card. Do not boot until writing AND verification pass.');
 run('set',output,'/body/p[77]','--prop','text=Figure 2.4. Only the erase-confirmation operation is illustrated. Check YOUR microSD name in the red warning before selecting I UNDERSTAND, ERASE AND WRITE. This official generic screenshot says Apple SDXC and depicts Raspberry Pi OS setup fields; neither is a required device nor a gateway customisation step.');
 run('save',output);run('close',output);run('validate',output);
 console.log('EXACT_VISUAL_STAGE_READY_BYTES='+fs.statSync(output).size);
}catch(e){console.error('EXACT_VISUAL_STAGE_FAILED '+e.message);process.exitCode=1;}
finally{fs.writeFileSync(d+'word-src/.exact-visual-final-ops.json',JSON.stringify(log,null,2)+'\n');}
