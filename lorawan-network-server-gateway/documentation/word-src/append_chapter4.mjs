import fs from "node:fs";
import path from "node:path";
import {spawnSync} from "node:child_process";
const base="lorawan-network-server-gateway/documentation/";
const dir=base+"word-src/";
const original=base+"LoRaWAN-Operator-Manual-WIP.docx";
const candidate=dir+".manual-chapter4-qa.docx";
const textSource=dir+"04-sim7600-lte.md";
const exe=path.join(process.env.USERPROFILE,".rel-ai-mcp","extensions",".bin","officecli.exe");
const log=[];
function cli(...a){
 const r=spawnSync(exe,a,{encoding:"utf8",timeout:34000,maxBuffer:2800000});
 const msg=(r.stdout||"").trim(),err=(r.stderr||"").trim();
 log.push({verb:a[0],exit:r.status,ref:a[2],out:msg.slice(0,230),error:err.slice(0,260)});
 if(r.status!==0)throw Error(a[0]+": "+(err||msg||r.error?.message));
 return msg;
}
function insertImage(name,cap,width,height,no){
 const p=base+"assets/"+name;
 if(!fs.existsSync(p)||fs.statSync(p).size<40000)throw Error("Missing visual "+p);
 const out=cli("add",candidate,"/body","--type","paragraph","--prop","text= ","--prop","align=center","--prop","keepLines=true");
 const para=out.match(/\/body\/p\[[^\]]+\]/)?.[0];
 if(!para)throw Error("No picture paragraph "+out);
 cli("add",candidate,para,"--type","picture","--prop","src="+p,"--prop","width="+width,"--prop","height="+height,"--prop","alt="+cap);
 cli("add",candidate,"/body","--type","paragraph","--prop","text=Figure "+no+". "+cap,"--prop","size=8.5pt","--prop","italic=true","--prop","align=center","--prop","color=#475569","--prop","keepNext=true");
}
try{
 if(!fs.existsSync(original)||fs.statSync(original).size<700000)throw Error("Original canonical Chapters 1-3 not found");
 if(fs.readFileSync(dir+"CHAPTER-PROGRESS.md","utf8").includes("## Completed: Chapter 4"))throw Error("Refuse duplicate Chapter 4");
 if(fs.existsSync(candidate)){try{cli("close",candidate)}catch(e){}fs.unlinkSync(candidate)}
 fs.copyFileSync(original,candidate);
 const t=fs.readFileSync(textSource,"utf8");
 if(t.includes("jervis128662120269"))throw Error("Secret in Word source");
 const regex=/(<!--[\s]*(?:LTE_DONGLE_PHOTO|LTE_UCI_WORKSHEET|LTE_FLOW_IMAGE):[^\n]*-->|~~~sh\n[\s\S]*?~~~|`{3}sh\n[\s\S]*?`{3})/g;
 let pieces=t.split(regex);
 const pic={
 LTE_DONGLE_PHOTO:["waveshare-sim7600g-h-dongle-physical-illustration.png","SIM7600G-H 4G USB dongle physical outline matching the photographed manufacturer model: USB to the Pi, ANT for LTE, PWR/STA/NET LEDs. Project-drawn illustration based on Waveshare product documentation, not a photo of this unplugged unit.","15.0cm","8.46cm","4.1"],
 LTE_UCI_WORKSHEET:["lte-qmi-project-settings-worksheet.png","Exact Gateway-01 QMI configuration from the project overlay: lte, /dev/cdc-wdm0, DITO internet.dito.ph, no netifd default/DHCP child, peer DNS on, wwan0 metric 10 by lte-route-health. Worksheet, NOT a live LuCI screenshot.","15.0cm","9.77cm","4.2"],
 LTE_FLOW_IMAGE:["lte-route-exact-project.png","Exact field backhaul: local MQTT to SIM7600 / wwan0 metric 10 to the cloud MQTT:8883; br-lan RJ45 is management-only; local MQTT buffer/journal remain during LTE loss. Project diagram, not a live result.","15.0cm","8.13cm","4.3"]
 };
 let j=0;
 for(const part of pieces){
  if(!part.trim())continue;
  const match=part.match(/<!--\s*(LTE_DONGLE_PHOTO|LTE_UCI_WORKSHEET|LTE_FLOW_IMAGE):/);
  if(match){insertImage(...pic[match[1]]);continue;}
  if(part.startsWith("```sh\n")){
   let cmds=part.replace(/^```sh\n/,"").replace(/\n```$/,"").trim();
   cli("add",candidate,"/body","--type","paragraph","--prop","text="+cmds,"--prop","font=Consolas","--prop","size=9.2pt","--prop","leftIndent=0.20cm","--prop","shd=F1F5F9","--prop","spaceBefore=5pt","--prop","spaceAfter=7pt","--prop","keepLines=false");
   continue;
  }
  const file=dir+".ch4-part-"+(++j)+".md";fs.writeFileSync(file,part.trim()+"\n");
  cli("add",candidate,"/","--type","markdown","--prop","src="+file);
 }
 cli("save",candidate);cli("close",candidate);
 const script="from zipfile import ZipFile\nfrom xml.etree import ElementTree as E\nimport sys\np=sys.argv[1];n='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}';r=E.fromstring(ZipFile(p).read('word/document.xml'));ll=r.find(n+'body').findall(n+'p');print(' '.join(str(i) for i,x in enumerate(ll,1) if ''.join(z.text or '' for z in x.iter(n+'t')).startswith('Chapter 4 — Set Up')))\n";
 const p=spawnSync("python",["-c",script,candidate],{encoding:"utf8",timeout:12000});
 const i=Number((p.stdout||"").trim());
 if(!Number.isInteger(i)||i<=100)throw Error("Cannot locate Chapter 4 heading: "+(p.stdout||"")+" "+(p.stderr||""));
 cli("set",candidate,"/body/p["+i+"]","--prop","pageBreakBefore=true","--prop","keepNext=true");
 cli("save",candidate);cli("close",candidate);cli("validate",candidate);
 console.log("CHAPTER4_READY",fs.statSync(candidate).size,"heading",i,"sections",j);
}catch(e){console.error("CHAPTER4_FAILED",e.message);process.exitCode=1}
finally{fs.writeFileSync(dir+"CHAPTER4-BUILD-LOG.json",JSON.stringify(log,null,2)+"\n");}
