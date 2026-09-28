import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const root='lorawan-network-server-gateway/documentation/';
const target=root+'LoRaWAN-Operator-Manual-WIP.docx';
const stage=root+'word-src/.visual-steps-refine-qa.docx';
const exe=path.join(process.env.USERPROFILE,'.rel-ai-mcp','extensions','.bin','officecli.exe');
const ops=[];
function run(...args) {
 const p=spawnSync(exe,args,{encoding:'utf8',timeout:40000,maxBuffer:3e6});
 ops.push({command:args[0],path:args[2],exit:p.status,stderr:(p.stderr||'').slice(0,330)});
 if(p.status!==0)throw Error(args[0]+' '+args[2]+': '+(p.stderr||p.stdout||p.error?.message));
 return p.stdout||'';
}
try{
 if(!fs.existsSync(target))throw Error('canonical Word file missing');
 if(fs.existsSync(stage)){try{run('close',stage)}catch(e){}fs.unlinkSync(stage);}
 fs.copyFileSync(target,stage);
 const pics=[
 {path:'/body/p[@paraId=001001C3]/r[2]',src:'raspberrypi-imager-use-custom-actual-reference.png',width:'14.0cm',height:'9.90cm',alt:'Actual Raspberry Pi Imager 2.0 screenshot showing Use custom selected at bottom of OS list. Other OSes are not the gateway image.'},
 {path:'/body/p[@paraId=001001BF]/r[2]',src:'raspberrypi-imager-windows-card-selection-reference.png',width:'14.0cm',height:'10.24cm',alt:'Actual Raspberry Pi Imager 2.0 Windows storage screen with 59.5 GB removable Generic STORAGE DEVICE and checked Exclude system drives; choose your own card.'}
 ];
 for(const p of pics){
 const full=root+'assets/'+p.src;
 if(!fs.existsSync(full))throw Error('missing verified web image: '+full);
 run('set',stage,p.path,'--prop','src='+full,'--prop','width='+p.width,'--prop','height='+p.height,'--prop','alt='+p.alt);
 }
 run('set',stage,'/body/p[69]','--prop','text=Open Raspberry Pi Imager. Select Raspberry Pi 4, open OS, scroll to the bottom, click Use custom as shown in Figure 2.2, then open only the custom .img.gz that PASSED step 2.3.');
 run('set',stage,'/body/p[71]','--prop','text=Figure 2.2. Click the highlighted Use custom entry — not Raspberry Pi OS. Real Raspberry Pi Imager 2.0 example from Onefinity CNC; the Gateway OS image itself is provided separately by this project.','--prop','size=9pt');
 run('set',stage,'/body/p[74]','--prop','text=Figure 2.3. Select YOUR removable microSD, checking name and capacity; keep Exclude system drives checked. Windows Imager 2.0 example (59.5 GB Generic USB reader) from SunFounder; your reader name may differ.','--prop','size=9pt');
 run('set',stage,'/body/p[77]','--prop','text=Figure 2.4. Confirm the erase-warning target is YOUR microSD before selecting I understand, erase and write. Official Raspberry Pi example displays an Apple SDXC reader, which is NOT a required device or the project workstation.','--prop','size=9pt');
 run('save',stage);
 run('close',stage);
 run('validate',stage);
 console.log('EXACT_SCREENSHOTS_STAGE_BYTES='+fs.statSync(stage).size);
}catch(e){console.error('STAGE_FAILED: '+e.message);process.exitCode=1}
finally{fs.writeFileSync(root+'word-src/.visual-refine-ops.json',JSON.stringify(ops,null,2)+'\n');}
