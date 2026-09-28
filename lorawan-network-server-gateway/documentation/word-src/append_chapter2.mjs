import fs from "node:fs";
import path from "node:path";
import {spawnSync} from "node:child_process";
const root="lorawan-network-server-gateway/documentation/";
const src=root+"word-src/";
const target=root+"LoRaWAN-Operator-Manual-WIP.docx";
const stage=src+".manual-with-chapter2-qa.docx";
const old=src+"02-gateway-os.md";
const asset=root+"assets/rak5146-official-mount-reference.png";
const exe=path.join(process.env.USERPROFILE,".rel-ai-mcp","extensions",".bin","officecli.exe");
const ops=[];
function run(...args) {
 const r=spawnSync(exe,args,{encoding:"utf8",timeout:35000,maxBuffer:2500000});
 const output=(r.stdout||"").trim(), err=(r.stderr||"").trim();
 ops.push({verb:args[0],exit:r.status,summary:output.slice(0,800),err:err.slice(0,320)});
 if(r.status!==0) throw Error(args[0]+": "+(err||output||r.error?.message));
 return output;
}
try{
 if(!fs.existsSync(target)||fs.statSync(target).size<15000)throw Error("Canonical Chapter 1 Word file missing");
 if(!fs.existsSync(asset)||fs.statSync(asset).size<100000)throw Error("Official image missing");
 if(fs.readFileSync(src+'CHAPTER-PROGRESS.md','utf8').includes('## Completed: Chapter 2'))throw Error('Chapter 2 already incorporated into the canonical Word manual. Do not append twice.');
 const text=fs.readFileSync(old,"utf8");
 const parts=text.split(/<!-- RAK_IMAGE:[^\n]+-->/);
 if(parts.length!==2)throw Error("Expected one image marker in Chapter 2");
 const a=src+".chapter2-before-figure.md",b=src+".chapter2-after-figure.md";
 fs.writeFileSync(a,parts[0].trimEnd()+"\n");
 fs.writeFileSync(b,parts[1].trimStart());
 try{run("close",target)}catch(e){}
 if(fs.existsSync(stage)){try{run("close",stage)}catch(e){}fs.unlinkSync(stage);}
 fs.copyFileSync(target,stage);
 run("add",stage,"/","--type","markdown","--prop","src="+a);
 let result=run("add",stage,"/body","--type","paragraph","--prop","text= ","--prop","align=center","--prop","keepLines=true");
 let p=result.match(/\/body\/p\[[^\]]+\]/);
 if(!p)throw Error("Image paragraph not found: "+result);
 run("add",stage,p[0],"--type","picture","--prop","src="+asset,"--prop","width=14.8cm","--prop","height=8.035cm","--prop","alt=RAKwireless official RAK5146 concentrator Pi HAT mounting illustration; reference hardware, not a photograph of the installed SIM7600 gateway");
 run("add",stage,"/body","--type","paragraph","--prop","text=Figure 2.1. RAKwireless RAK5146 Pi HAT mounting reference (manufacturer illustration, not this gateway's SIM7600 assembly).","--prop","size=8.5pt","--prop","italic=true","--prop","color=#475569","--prop","align=center","--prop","keepNext=true");
 run("add",stage,"/","--type","markdown","--prop","src="+b);
 run("save",stage);run("close",stage);run("validate",stage);
 if(fs.statSync(stage).size<fs.statSync(target).size+100000)throw Error("Embedded image seems missing; candidate suspiciously small");
 console.log("CHAPTER2_QA_BUILT "+fs.statSync(stage).size);
}catch(e){console.error("CHAPTER2_QA_FAILED "+e.message);process.exitCode=1;}
finally{fs.writeFileSync(src+"CHAPTER2-BUILD-LOG.json",JSON.stringify(ops,null,2)+"\n");}
