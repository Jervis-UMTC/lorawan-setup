import fs from "node:fs";
import path from "node:path";
import {spawnSync} from "node:child_process";
const root="lorawan-network-server-gateway/documentation/";
const src=root+"word-src/";
const target=root+"LoRaWAN-Operator-Manual-WIP.docx";
const stage=src+".manual-chapter3-qa.docx";
const source=src+"03-rak5146-as923.md";
const exe=path.join(process.env.USERPROFILE,".rel-ai-mcp","extensions",".bin","officecli.exe");
let ops=[];
function run(...a){
 const p=spawnSync(exe,a,{encoding:"utf8",timeout:42000,maxBuffer:3000000});
 const out=(p.stdout||"").trim(),err=(p.stderr||"").trim();
 ops.push({op:a[0],path:a[2],exit:p.status,output:out.slice(0,350),stderr:err.slice(0,400)});
 if(p.status!==0)throw Error(a[0]+" "+a[2]+": "+(err||out||p.error?.message));
 return out;
}
function image(asset,width,height,number,caption){
 const file=root+"assets/"+asset;
 if(!fs.existsSync(file)||fs.statSync(file).size<35000)throw Error("Missing image "+asset);
 const q=run("add",stage,"/body","--type","paragraph","--prop","text= ","--prop","align=center","--prop","keepLines=true");
 const para=q.match(/\/body\/p\[[^\]]+\]/)?.[0];
 if(!para)throw Error("Cannot locate new image paragraph: "+q);
 run("add",stage,para,"--type","picture","--prop","src="+file,"--prop","width="+width,"--prop","height="+height,"--prop","alt="+caption);
 run("add",stage,"/body","--type","paragraph","--prop","text=Figure "+number+". "+caption,"--prop","size=8.5pt","--prop","italic=true","--prop","color=#475569","--prop","align=center","--prop","keepNext=true");
}
try{
 if(!fs.existsSync(target)||fs.statSync(target).size<400000)throw Error("Canonical Chapter1-2 Word file missing");
 if(fs.readFileSync(src+"CHAPTER-PROGRESS.md","utf8").includes("## Completed: Chapter 3"))throw Error("Chapter 3 already appended; refuse duplicate");
 let t=fs.readFileSync(source,"utf8");
 if(t.includes("jervis128662120269"))throw Error("Secret leakage in Word source");
 const parts=t.split(/<!-- (?:RAK_PINOUT_IMAGE|CONFIG_WORKSHEET_IMAGE):[^\n]+-->/);
 if(parts.length!==3)throw Error("Expected two visual insertion markers, got "+parts.length);
 const files=[".ch3-a.md",".ch3-b.md",".ch3-c.md"];
 files.forEach((n,i)=>fs.writeFileSync(src+n,parts[i].trim()+"\n"));
 if(fs.existsSync(stage)){try{run("close",stage)}catch(e){}fs.unlinkSync(stage)}
 fs.copyFileSync(target,stage);
 run("add",stage,"/","--type","markdown","--prop","src="+src+files[0]);
 image("rak5146-pihat-official-spi-header-pinout.png","15.0cm","11.3cm","3.1","Official RAKwireless RAK2287/RAK5146 Pi HAT 40-pin connection map. SPI uses the HAT header; verify full 40-pin seating before power. Manufacturer reference, not our installed Gateway-01 photograph.");
 run("add",stage,"/","--type","markdown","--prop","src="+src+files[1]);
 image("gateway-concentratord-verified-settings.png","15.1cm","9.9cm","3.2","Gateway-01 approved SX1302/RAK5146/AS923 options, reproduced from the tracked project UCI overlay. Configuration worksheet, NOT a current LuCI screenshot.");
 run("add",stage,"/","--type","markdown","--prop","src="+src+files[2]);
 run("save",stage);run("close",stage);
 const script="from zipfile import ZipFile\nfrom xml.etree import ElementTree as E\nimport sys\np=sys.argv[1];n='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}';root=E.fromstring(ZipFile(p).read('word/document.xml'));l=root.find(n+'body').findall(n+'p');a=[i for i,x in enumerate(l,1) if ''.join(z.text or '' for z in x.iter(n+'t')).startswith('Chapter 3')];print(a[-1] if len(a)==1 else 'FAIL')\n";
 const p=spawnSync("python",["-c",script,stage],{encoding:"utf8",timeout:10000});
 const i=Number((p.stdout||"").trim());
 if(p.error||p.status!==0)throw Error('Cannot inspect DOCX heading through Python: '+(p.stderr||p.error?.message));
 if(!Number.isInteger(i)||i<50)throw Error("Cannot locate Chapter 3 heading: "+p.stdout+" "+p.stderr);
 run("set",stage,"/body/p["+i+"]","--prop","pageBreakBefore=true","--prop","keepNext=true");
 run("save",stage);run("close",stage);run("validate",stage);
 console.log("CHAPTER3_STAGED bytes="+fs.statSync(stage).size+" headingParagraph="+i);
}catch(e){console.error("CHAPTER3_BUILD_FAILED: "+e.message);process.exitCode=1;}
finally{fs.writeFileSync(src+"CHAPTER3-BUILD-LOG.json",JSON.stringify(ops,null,2)+"\n");}
