import fs from "node:fs";
import path from "node:path";
import {spawnSync} from "node:child_process";
const d="lorawan-network-server-gateway/documentation/";
const source=d+"LoRaWAN-Operator-Manual-WIP.docx";
const stage=d+"word-src/.screenflow-chapter2-qa.docx";
const cliExe=path.join(process.env.USERPROFILE,".rel-ai-mcp","extensions",".bin","officecli.exe");
const ops=[];
function cli(...args){
 const p=spawnSync(cliExe,args,{encoding:"utf8",timeout:35000,maxBuffer:3000000});
 const output=(p.stdout||"").trim(),err=(p.stderr||"").trim();
 ops.push({verb:args[0],position:args[2],exit:p.status,out:output.slice(0,400),error:err.slice(0,400)});
 if(p.status!==0)throw Error(args[0]+": "+(err||output||p.error?.message));
 return output;
}
function figure(afterIndex,file,cap,w,h){
 const img=d+"assets/"+file;
 if(!fs.existsSync(img)||fs.statSync(img).size<15000)throw Error("Image missing: "+file);
 const result=cli("add",stage,"/body","--type","paragraph","--after","/body/p["+afterIndex+"]","--prop","text= ","--prop","align=center","--prop","keepLines=true");
 const p=result.match(/\/body\/p\[[^\]]+\]/)?.[0];
 if(!p)throw Error("new paragraph path missing: "+result);
 cli("add",stage,p,"--type","picture","--prop","src="+img,"--prop","width="+w,"--prop","height="+h,"--prop","alt="+cap);
 cli("add",stage,"/body","--type","paragraph","--after",p,"--prop","text="+cap,"--prop","size=9pt","--prop","italic=true","--prop","align=center","--prop","color=#475569","--prop","keepNext=true");
}
try{
 if(!fs.existsSync(source)||fs.statSync(source).size<1300000)throw Error("Canonical 19-page original missing");
 if(fs.existsSync(stage)){try{cli("close",stage)}catch(e){}fs.unlinkSync(stage);}
 fs.copyFileSync(source,stage);
 const summary="SCREEN 2B — STOP/CHECK EXAMPLE (official Raspberry Pi Imager Writing tab). This real reference screen shows Raspberry Pi 5, stock Raspberry Pi OS and Apple SDXC: all are WRONG for this project. On YOUR screen require Raspberry Pi 4, the approved Gateway OS .img.gz filename and YOUR identified microSD; click BACK if they differ. Source: Raspberry Pi official documentation.";
 const device="SCREEN 2A — SELECT RASPBERRY PI 4. Real Raspberry Pi Imager v2.0.7 screenshot with Raspberry Pi 4 highlighted. Click Next. Source: PiNEXUS Instructables example (video-player strip belongs to original reference, not Imager).";
 // Insert at later position first; earlier insertion must not change the later anchor before it is used.
 figure(75,"imager-writing-summary-reference.png",summary,"14.6cm","9.65cm");
 figure(69,"imager-device-actual-pi4-selected.png",device,"14.6cm","10.2cm");
 cli("save",stage);cli("close",stage);cli("validate",stage);
 console.log("CH2_SCREENFLOW_QA_READY",fs.statSync(stage).size,"ops",ops.length);
}catch(e){console.error("SCREENFLOW_FAILED",e.message);process.exitCode=1;}
finally{fs.writeFileSync(d+"word-src/CHAPTER2-SCREENFLOW-OPS.json",JSON.stringify(ops,null,2)+"\n");}
