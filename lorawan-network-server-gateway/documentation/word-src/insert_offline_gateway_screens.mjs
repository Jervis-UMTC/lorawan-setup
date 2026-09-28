import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const root='lorawan-network-server-gateway/documentation/';
const doc=root+'word-src/.manual-ch2-offline-screens-qa.docx';
const exe=path.join(process.env.USERPROFILE,'.rel-ai-mcp','extensions','.bin','officecli.exe');
const log=[];
function run(...a){
 let p=spawnSync(exe,a,{encoding:'utf8',timeout:38000,maxBuffer:2e6});
 log.push({action:a[0],path:a[2],exit:p.status,error:(p.stderr||'').slice(0,300)});
 if(p.status!==0)throw Error(a[0]+' '+a[2]+' '+(p.stderr||p.stdout||p.error?.message));
 return (p.stdout||'').trim();
}
function figure(afterIndex,img,number,text,width,height){
 let res=run('add',doc,'/body','--type','paragraph','--after', '/body/p['+afterIndex+']','--prop','text= ','--prop','align=center','--prop','keepLines=true');
 let pa=res.match(/\/body\/p\[[^\]]+\]/)?.[0];
 if(!pa)throw Error('No new paragraph id: '+res);
 run('add',doc,pa,'--type','picture','--prop','src='+root+'assets/'+img,'--prop','width='+width,'--prop','height='+height,'--prop','alt='+text);
 run('add',doc,'/body','--type','paragraph','--after',pa,'--prop','text=Figure '+number+'. '+text+' Source: Raspberry Pi documentation.','--prop','size=9pt','--prop','italic=true','--prop','align=center','--prop','color=#475569','--prop','keepNext=false');
}
try {
 for(const name of ['raspberrypi-imager-os-selection-reference.png','raspberrypi-imager-storage-reference.png','raspberrypi-imager-erase-warning-reference.png']){
  if(!fs.existsSync(root+'assets/'+name)||fs.statSync(root+'assets/'+name).size<20000)throw Error('Reference screenshot missing '+name);
 }
 const code=[
 "$Image = (Read-Host 'Full path to approved .img.gz').Trim([char]34)",
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
 run('set',doc,'/body/p[57]','--prop','text='+code,'--prop','font=Consolas','--prop','size=9.25pt','--prop','leftIndent=0.2cm','--prop','shd=F1F5F9','--prop','keepLines=false');
 figure(71,'raspberrypi-imager-erase-warning-reference.png','2.4','Official erase warning; stop if the shown device is not your intended microSD. The example reader is not this workstation.',14.8+'cm',9.79+'cm');
 figure(70,'raspberrypi-imager-storage-reference.png','2.3','Official storage tab; select your own removable microSD and keep system-drive exclusion enabled.',14.8+'cm',9.79+'cm');
 figure(69,'raspberrypi-imager-os-selection-reference.png','2.2','Official OS tab; scroll to Use Custom. The pictured Raspberry Pi OS is NOT our approved custom Gateway OS.',14.8+'cm',9.79+'cm');
 run('save',doc);
 run('close',doc);
 run('validate',doc);
 console.log('GATEWAY_OFFLINE_SCREENSHOTS_EMBEDDED size='+fs.statSync(doc).size);
}catch(e){console.error('GATEWAY_OFFLINE_SCREENSHOTS_FAILED: '+e.message);process.exitCode=1}
finally{fs.writeFileSync(root+'word-src/.offline-images-log.json',JSON.stringify(log,null,2)+'\n');}
