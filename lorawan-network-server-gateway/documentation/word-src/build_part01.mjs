import fs from "node:fs";
import path from "node:path";
import {spawnSync} from "node:child_process";
const f="lorawan-network-server-gateway/documentation/LoRaWAN-Operator-Manual-WIP.docx";
const src="lorawan-network-server-gateway/documentation/word-src/";
const img="lorawan-network-server-gateway/documentation/assets/grafana-login-20260921.png";
const exe=path.join(process.env.USERPROFILE,".rel-ai-mcp","extensions",".bin","officecli.exe");
const log=[];
function run(...args){
 const r=spawnSync(exe,args,{encoding:"utf8",timeout:25000,maxBuffer:2e6});
 const out=(r.stdout||"").trim(),err=(r.stderr||"").trim();
 log.push({cmd:args[0],exit:r.status,output:out.slice(0,900),error:err.slice(0,900)});
 if(r.status!==0)throw Error(`OfficeCLI ${args[0]} failed: ${err||out||r.error?.message}`);
 if(!fs.existsSync(f))throw Error(`DOCX unexpectedly absent after ${args[0]}`);
 return out;
}
try{
 if(!fs.existsSync(f))throw Error("Missing empty OfficeCLI-created DOCX");
 if(!fs.existsSync(img)||fs.statSync(img).size<12000)throw Error("Reviewed screenshot missing or blank");
 run("set",f,"/section[1]","--prop","pageWidth=21cm","--prop","pageHeight=29.7cm","--prop","marginTop=2.2cm","--prop","marginBottom=2.1cm","--prop","marginLeft=2.45cm","--prop","marginRight=2.35cm","--prop","titlePage=true");
 run("add",f,"/","--type","markdown","--prop",`src=${src}00-cover.md`);
 run("add",f,"/body","--type","paragraph","--prop","text=CONTENTS","--prop","pageBreakBefore=true","--prop","align=center","--prop","bold=true","--prop","size=18pt","--prop","color=#12636A");
 run("add",f,"/","--type","toc","--prop","levels=1-2","--prop","hyperlinks=true","--prop","pageNumbers=true");
 run("add",f,"/body","--type","paragraph","--prop","text=PART I | SYSTEM ORIENTATION","--prop","pageBreakBefore=true","--prop","size=11pt","--prop","color=#12636A");
 run("add",f,"/","--type","markdown","--prop",`src=${src}01-chapter-1.md`);
 const para=run("add",f,"/body","--type","paragraph","--prop","text= ","--prop","align=center","--prop","keepLines=true");
 const match=para.match(/\/body\/p\[[^\]]+\]/);
 if(!match)throw Error("Unexpected OfficeCLI paragraph response: "+para);
 run("add",f,match[0],"--type","picture","--prop",`src=${img}`,"--prop","width=15.8cm","--prop","height=9.875cm","--prop","alt=Real Grafana login with empty username and password and v13.2.0 footer");
 run("add",f,"/","--type","markdown","--prop",`src=${src}01-chapter-1-after-figure.md`);
 run("add",f,"/","--type","footer","--prop","text=LoRaWAN Infrastructure | WORKING MANUAL | ","--prop","field=page","--prop","align=center","--prop","size=9pt","--prop","color=#64748B");
 run("save",f);
 run("close",f);
 run("validate",f);
 const finish=spawnSync(process.execPath,[src+"finish_part01.mjs"],{encoding:"utf8",timeout:100000,maxBuffer:2e6});
 if(finish.status!==0)throw Error("OfficeCLI finish stage failed: "+(finish.stderr||finish.stdout));
 console.log("PART01_BUILT_BYTES="+fs.statSync(f).size+" STEPS="+log.length+" "+(finish.stdout||"").trim());
}catch(e){console.error("PART01_FAILED: "+e.message);process.exitCode=1}
finally{fs.writeFileSync(src+"PART01-BUILD-LOG.json",JSON.stringify(log,null,2));}
