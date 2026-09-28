import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const target='lorawan-network-server-gateway/documentation/word-src/.manual-ch2-offline-screens-qa.docx';
const exe=path.join(process.env.USERPROFILE,'.rel-ai-mcp','extensions','.bin','officecli.exe');
let log=[];
function cli(...args){
 const x=spawnSync(exe,args,{encoding:'utf8',timeout:35000,maxBuffer:2500000});
 log.push({op:args[0],path:args[2],exit:x.status,error:(x.stderr||'').slice(0,220)});
 if(x.status!==0)throw Error(args[0]+' '+args[2]+': '+(x.stderr||x.stdout||x.error?.message));
 return (x.stdout||'').trim();
}
try{
 cli('set',target,'/body/p[5]','--prop','text=Working draft — Chapters 1–2 • illustrated offline setup');
 cli('set',target,'/body/p[76]','--prop','text=Inspect the final summary: approved custom Gateway OS image and the intended microSD (not your workstation SSD). Click Write only after confirming the erase target, then wait for the write AND verification to finish.');
 cli('set',target,'/body/p[75]','--prop','text=In Storage, select the removable microSD by capacity and reader name. Keep Exclude system drives enabled. If unsure which disk is your card, unplug the other removable drives before continuing.');
 cli('set',target,'/body/p[74]','--prop','text=Open Raspberry Pi Imager. Select Raspberry Pi 4; in the OS tab scroll to the bottom and choose Use Custom. Browse to the approved .img.gz that PASSED step 2.3. Do NOT select the example Raspberry Pi OS shown in the reference screenshot.');
 cli('set',target,'/body/p[63]','--prop','text=Expected result: IMAGE_VERIFIED=PASS. If the script reports FAIL, stop before flashing; do not guess or accept a newer unapproved image.');
 for(const i of [62,61,60,59,58])cli('remove',target,'/body/p['+i+']');
 const code=[
 "$Image = (Read-Host 'Full path to approved .img.gz').Trim('\\\"')",
 "$ExpectedName = 'chirpstack-gateway-os-4.12.0-base-bcm27xx-bcm2709-rpi-2-squashfs-factory.img.gz'",
 "$ExpectedHash = 'bafe8b97baf9353df2654b1c8b71fa53d2ff764cd264d0ed6c924dd25a5ec67d'",
 "if (-not (Test-Path -LiteralPath $Image -PathType Leaf)) {",
 "    throw 'FAIL: image not found. Do not flash.'",
 "}",
 "$File = Get-Item -LiteralPath $Image",
 "if ($File.Name -ne $ExpectedName -or $File.Length -ne 28900364) {",
 "    throw 'FAIL: wrong image name or size. Do not flash.'",
 "}",
 "$Hash = (Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash",
 "if ($Hash.ToLowerInvariant() -ne $ExpectedHash) {",
 "    throw 'FAIL: SHA-256 mismatch. Do not flash.'",
 "}",
 "'IMAGE_VERIFIED=PASS'"
 ].join('\n');
 cli('set',target,'/body/p[57]','--prop','text='+code);
 cli('save',target);
 cli('close',target);
 cli('validate',target);
 console.log('CHAPTER2_OFFLINE_TEXT_UPDATED');
}catch(e){console.error('CHAPTER2_OFFLINE_TEXT_FAILED '+e.message);process.exitCode=1}
finally{fs.writeFileSync('lorawan-network-server-gateway/documentation/word-src/.offline-update-log.json',JSON.stringify(log,null,2));}
