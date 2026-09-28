import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
const chrome="C:/Program Files/Google/Chrome/Application/chrome.exe";
const dir=fs.mkdtempSync(path.join(os.tmpdir(),"lorawan-grafana-cdp-"));
const target=path.resolve("lorawan-network-server-gateway/documentation/assets/grafana-login-20260921.png");
const args=["--headless=new","--disable-gpu","--no-first-run","--no-default-browser-check","--disable-extensions","--remote-debugging-port=0",`--user-data-dir=${dir}`,"--window-size=1440,900","about:blank"];
let child=spawn(chrome,args,{stdio:"ignore",windowsHide:true});
const pause=t=>new Promise(r=>setTimeout(r,t));
const until=Date.now()+14000;
let ws;
try {
 let info;
 while(Date.now()<until){if(child.exitCode!==null)throw Error("Chrome exited");if(fs.existsSync(path.join(dir,"DevToolsActivePort"))){info=fs.readFileSync(path.join(dir,"DevToolsActivePort"),"utf8").split(/\r?\n/);break;}await pause(180);}
 if(!info)throw Error("CDP port unavailable");
 const port=Number(info[0]);
 let list=await (await fetch(`http://127.0.0.1:${port}/json`)).json();
 let page=list.find(x=>x.type==="page");
 if(!page) throw Error("No page");
 ws=new WebSocket(page.webSocketDebuggerUrl);
 await new Promise((resolve,reject)=>{ws.addEventListener("open",resolve,{once:true});ws.addEventListener("error",reject,{once:true})});
 let n=0,pending=new Map();
 ws.addEventListener("message",e=>{const msg=JSON.parse(e.data);if(msg.id&&pending.has(msg.id)){let {resolve,reject}=pending.get(msg.id);pending.delete(msg.id);msg.error?reject(Error(msg.error.message)):resolve(msg.result)}});
 const send=(method,params={})=>new Promise((resolve,reject)=>{let id=++n;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}))});
 await send("Page.enable");await send("Runtime.enable");await send("Emulation.setDeviceMetricsOverride",{width:1440,height:900,deviceScaleFactor:1,mobile:false});
 await send("Page.navigate",{url:"http://127.0.0.1:3000/login"});
 let text="";
 for(let i=0;i<35;i++){await pause(500);let v=await send("Runtime.evaluate",{expression:"document.body ? document.body.innerText : ''",returnByValue:true});text=v.result?.value||"";if(text.includes("Welcome to Grafana")&&text.includes("Grafana v"))break;}
 if(!text.includes("Welcome to Grafana")||!text.includes("Grafana v"))throw Error("Login page not loaded: "+text.slice(0,80));
 await pause(800);
 const capture=await send("Page.captureScreenshot",{format:"png",captureBeyondViewport:false,fromSurface:true});
 const data=Buffer.from(capture.data,"base64");if(data.length<12000)throw Error("Suspiciously small screenshot "+data.length);
 fs.writeFileSync(target,data);
 console.log("VALID_GRAFANA_SCREENSHOT_BYTES="+data.length+" TEXT="+text.replace(/\s+/g," ").slice(0,94));
}finally{if(ws)ws.close();child.kill();try{fs.rmSync(dir,{recursive:true,force:true,maxRetries:2})}catch(e){}}
