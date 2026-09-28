import fs from "node:fs";
import path from "node:path";
import {spawnSync} from "node:child_process";
const root="lorawan-network-server-gateway/documentation/";
const src=root+"word-src/";
const target=root+"LoRaWAN-Operator-Manual-WIP.docx";
const candidate=root+"LoRaWAN-Operator-Manual-revised.docx";
const backup=src+".pre-simplification-20260921.docx";
const exe=path.join(process.env.USERPROFILE,".rel-ai-mcp","extensions",".bin","officecli.exe");
const steps=[];
function run(...args){
 const r=spawnSync(exe,args,{encoding:"utf8",timeout:27000,maxBuffer:2000000});
 const out=(r.stdout||"").trim(),err=(r.stderr||"").trim();
 steps.push({verb:args[0],exit:r.status,result:out.slice(0,800),warnings:err.slice(0,500)});
 if(r.status!==0)throw Error(args[0]+": "+(err||out||r.error?.message));
 return out;
}
try{
 if(fs.existsSync(candidate))run("close",candidate);
 if(fs.existsSync(candidate))fs.unlinkSync(candidate);
 run("create",candidate);
 run("set",candidate,"/section[1]","--prop","pageWidth=21cm","--prop","pageHeight=29.7cm","--prop","marginTop=1.95cm","--prop","marginBottom=1.8cm","--prop","marginLeft=2.35cm","--prop","marginRight=2.35cm","--prop","titlePage=true");
 // Explicit real heading styles ensure a functional Word navigation pane and TOC.
 for(const [id,name,size,color] of [["Heading1","Heading 1","19pt","#12636A"],["Heading2","Heading 2","12pt","#12636A"]]){
   try{run("add",candidate,"/styles","--type","style","--prop","id="+id,"--prop","name="+name,"--prop","type=paragraph","--prop","basedOn=Normal","--prop","size="+size,"--prop","color="+color,"--prop","spaceBefore=11pt","--prop","spaceAfter=6pt","--prop","keepNext=true")}catch(e){if(!String(e.message).includes("already exists"))throw e;}
 }
 run("add",candidate,"/","--type","markdown","--prop","src="+src+"00-cover.md");
 run("add",candidate,"/","--type","markdown","--prop","src="+src+"01-chapter-1.md");
 run("set",candidate,"/body/p[7]","--prop","pageBreakBefore=true");
 run("add",candidate,"/","--type","footer","--prop","text=LoRaWAN Infrastructure Setup Manual  |  ","--prop","field=page","--prop","align=center","--prop","size=9pt","--prop","color=#64748B");
 run("set",candidate,"/body/p[1]","--prop","align=center","--prop","size=26pt","--prop","bold=true","--prop","color=#12636A","--prop","spaceBefore=115pt","--prop","spaceAfter=25pt");
 run("set",candidate,"/body/p[2]","--prop","align=center","--prop","size=14pt","--prop","color=#334155","--prop","spaceAfter=25pt");
 run("batch",candidate,"--input",src+"layout-fixes.json");
 run("set",candidate,"/body/p[23]","--prop","pageBreakBefore=true","--prop","keepNext=true");
 run("save",candidate);run("close",candidate);run("validate",candidate);
 if(!fs.existsSync(candidate)||fs.statSync(candidate).size<9000)throw Error("Insufficient candidate DOCX size");
 if(fs.existsSync(target)&&!fs.existsSync(backup))fs.copyFileSync(target,backup);
 fs.copyFileSync(candidate,target);
 console.log("SIMPLIFIED_WORD_DOCX="+fs.statSync(target).size+" bytes");
}catch(e){console.error("WORD_REFINE_FAILED "+e.message);process.exitCode=1;}
finally{fs.writeFileSync(src+"PART01-REVISED-BUILD-LOG.json",JSON.stringify(steps,null,2)+"\n");}
