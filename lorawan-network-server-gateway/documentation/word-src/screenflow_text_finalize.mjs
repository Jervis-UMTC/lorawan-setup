import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const doc='lorawan-network-server-gateway/documentation/word-src/.screenflow-chapter2-qa.docx';
const exe=path.join(process.env.USERPROFILE,'.rel-ai-mcp','extensions','.bin','officecli.exe');
const edits=[
[69,'Open Raspberry Pi Imager. In Device select Raspberry Pi 4 and click Next (SCREEN 2A). Next, in OS click Use custom (Figure 2.2), locate the approved Gateway OS .img.gz from the image-verification step, and click Next. Never choose Raspberry Pi 5 or stock Raspberry Pi OS.'],
[77,'If Imager offers Raspberry Pi OS customisation, skip it for our custom OpenWrt Gateway OS. At Writing / Summary check Raspberry Pi 4, the exact approved .img.gz and YOUR removable microSD. SCREEN 2B is intentionally WRONG and illustrates when you must click Back. When all three fields match, click Write; on the erase warning check the actual SD reader and choose I understand, erase and write. Let writing and verification finish; do not boot after failure.']
];
for(const [id,t] of edits){
 const r=spawnSync(exe,['set',doc,'/body/p['+id+']','--prop','text='+t],{encoding:'utf8',timeout:27000});
 if(r.status!==0)throw Error('Set '+id+': '+(r.stderr||r.stdout||r.error?.message));
}
const r=spawnSync(exe,['validate',doc],{encoding:'utf8',timeout:35000});
if(r.status!==0)throw Error('DOCX validate failed '+(r.stderr||r.stdout));
console.log('SCREENFLOW_PARAGRAPHS_UPDATED');
