import fs from "node:fs";
import path from "node:path";
import {spawnSync} from "node:child_process";
const root="lorawan-network-server-gateway/documentation/";
const src=root+"word-src/";
const doc=root+"LoRaWAN-Operator-Manual-Ch1-QA.docx";
const original=src+"01-chapter-1.md";
const image=root+"assets/project-architecture-chapter1.png";
const exe=path.join(process.env.USERPROFILE,".rel-ai-mcp","extensions",".bin","officecli.exe");
const log=[];
function run(...args) {
 const p=spawnSync(exe,args,{encoding:"utf8",timeout:32000,maxBuffer:2500000});
 log.push({action:args[0],exit:p.status,output:(p.stdout||"").slice(0,1100),stderr:(p.stderr||"").slice(0,450)});
 if(p.status!==0)throw Error(args[0]+": "+(p.stderr||p.stdout||p.error?.message));
 return (p.stdout||"").trim();
}
try {
 const text=fs.readFileSync(original,"utf8");
 const parts=text.split(/<!-- ARCHITECTURE_DIAGRAM:[^\n]+-->/);
 if(parts.length!==2)throw Error("Exactly one architecture marker required");
 const fragmentA=src+".chapter1-before-figure.md";
 const fragmentB=src+".chapter1-after-figure.md";
 fs.writeFileSync(fragmentA,parts[0].trimEnd()+"\n");
 fs.writeFileSync(fragmentB,parts[1].trimStart());
 if(!fs.existsSync(image)||fs.statSync(image).size<60000)throw Error("Architecture image absent");
 if(fs.existsSync(doc)){try{run("close",doc)}catch(e){}fs.unlinkSync(doc);}
 run("create",doc);
 run("set",doc,"/section[1]","--prop","pageWidth=21cm","--prop","pageHeight=29.7cm","--prop","marginTop=1.95cm","--prop","marginBottom=1.8cm","--prop","marginLeft=2.35cm","--prop","marginRight=2.35cm","--prop","titlePage=true");
 for(const [id,name,size] of [["Heading1","Heading 1","19pt"],["Heading2","Heading 2","12pt"]]) {
  run("add",doc,"/styles","--type","style","--prop","id="+id,"--prop","name="+name,"--prop","type=paragraph","--prop","basedOn=Normal","--prop","size="+size,"--prop","color=#146977","--prop","spaceBefore=11pt","--prop","spaceAfter=6pt","--prop","keepNext=true");
 }
 run("add",doc,"/","--type","markdown","--prop","src="+src+"00-cover.md");
 run("add",doc,"/","--type","markdown","--prop","src="+fragmentA);
 let para=run("add",doc,"/body","--type","paragraph","--prop","text= ","--prop","align=center","--prop","keepLines=true");
 let match=para.match(/\/body\/p\[[^\]]+\]/);
 if(!match)throw Error("Picture paragraph path missing: "+para);
 run("add",doc,match[0],"--type","picture","--prop","src="+image,"--prop","width=15.5cm","--prop","height=5.8125cm","--prop","alt=Project architecture showing EMU-01 and Gateway-01 branching into telemetry and independent evidence verification then HRC Fabric");
 run("add",doc,"/body","--type","paragraph","--prop","text=Figure 1.1. Project telemetry and independently verified gateway-evidence paths.","--prop","size=9pt","--prop","italic=true","--prop","align=center","--prop","color=#425968","--prop","keepNext=true");
 run("add",doc,"/","--type","markdown","--prop","src="+fragmentB);
 run("add",doc,"/","--type","footer","--prop","text=LoRaWAN Infrastructure Setup Manual | ","--prop","field=page","--prop","align=center","--prop","size=9pt","--prop","color=#64748B");
 run("set",doc,"/body/p[1]","--prop","align=center","--prop","size=26pt","--prop","bold=true","--prop","color=#12636A","--prop","spaceBefore=115pt","--prop","spaceAfter=25pt");
 run("set",doc,"/body/p[2]","--prop","align=center","--prop","size=14pt","--prop","color=#334155","--prop","spaceAfter=25pt");
 run("batch",doc,"--input",src+"layout-fixes.json");
 run("set",doc,"/body/p[7]","--prop","pageBreakBefore=true");
 run("save",doc);run("close",doc);run("validate",doc);
 console.log("CHAPTER1_QA_CREATED bytes="+fs.statSync(doc).size);
}catch(e){console.error("CHAPTER1_QA_FAILED "+e.message);process.exitCode=1}
finally {fs.writeFileSync(src+"CHAPTER1-DIAGRAM-BUILD-LOG.json",JSON.stringify(log,null,2)+"\n");}
