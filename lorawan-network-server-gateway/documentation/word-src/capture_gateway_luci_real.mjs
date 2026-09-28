import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
const out='lorawan-network-server-gateway/documentation/assets/live-gateway-20260922';
fs.mkdirSync(out,{recursive:true});
const port=19223;
const profile=fs.mkdtempSync(path.join(os.tmpdir(),'lorawan-manual-cdp-'));
const child=spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',['--headless=new','--no-first-run','--disable-gpu','--ignore-certificate-errors','--remote-allow-origins=*','--remote-debugging-port='+port,'--window-size=1440,980','--user-data-dir='+profile,'https://192.168.20.11/cgi-bin/luci/'],{stdio:'ignore',windowsHide:true});
const sleep=(ms)=>new Promise(r=>setTimeout(r,ms));let ws,seq=0;const pending=new Map();
function cmd(method,params={}){
 const id=++seq;return new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>{pending.delete(id);reject(Error(method+' timeout'))},15000);
  pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));
 });
}
async function evaluate(expression){
 const r=await cmd('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});
 if(r.exceptionDetails)throw Error('Page script: '+expression.slice(0,70));
 return r.result?.value;
}
async function capture(name){
 await sleep(350);const s=await cmd('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
 const p=path.join(out,name+'.png');fs.writeFileSync(p,Buffer.from(s.data,'base64'));
 console.log('ACTUAL_SCREEN',name,fs.statSync(p).size);
}
async function click(label){
 const found=await evaluate("(()=>{let a=[...document.querySelectorAll('a,button')].find(x=>x.textContent?.trim()==="+JSON.stringify(label)+");if(a){a.click();return true;}return false;})()");
 await sleep(1700);console.log('NAVIGATION',label,found);return found;
}
try{
 let pages;for(let i=0;i<45;i++){try{pages=await (await fetch('http://127.0.0.1:'+port+'/json/list')).json();if(pages.some(x=>x.type==='page'))break}catch{}await sleep(300)}
 const tab=pages?.find(x=>x.type==='page'&&x.webSocketDebuggerUrl);if(!tab)throw Error('Chrome debugger not reachable');
 ws=new WebSocket(tab.webSocketDebuggerUrl);
 ws.onmessage=e=>{const m=JSON.parse(e.data),q=pending.get(m.id);if(q){clearTimeout(q.timer);pending.delete(m.id);m.error?q.reject(Error(m.error.message)):q.resolve(m.result||{})}};
 await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;setTimeout(()=>reject(Error('Socket timed out')),12000)});
 await cmd('Page.enable');await cmd('Runtime.enable');
 for(let i=0;i<18;i++){if(await evaluate("document.readyState==='complete'"))break;await sleep(400)}
 await sleep(1000);await capture('01-luci-login');
 if(!process.env.GATEWAY_AUTH)throw Error('GATEWAY_AUTH environment variable required');
 const form="(()=>{const u=document.querySelector('input[name=username],input[name=luci_username],input[type=text]');const p=document.querySelector('input[type=password]');if(!p)return false;if(u)u.value='root';p.value="+JSON.stringify(process.env.GATEWAY_AUTH)+";p.dispatchEvent(new Event('input',{bubbles:true}));const b=document.querySelector('button[type=submit],input[type=submit]');if(b)b.click();else p.form?.requestSubmit();return true;})()";
 await evaluate(form);await sleep(2300);
 if(!(await evaluate("document.body.innerText.includes('Concentratord')")))throw Error('Gateway login not accepted');
 await capture('02-concentratord-global');
 await evaluate("(()=>{let a=[...document.querySelectorAll('a')].find(x=>x.textContent.trim()==='SX1302 / SX1303');if(!a)return false;a.click();a.scrollIntoView({block:'start'});return true;})()");
 await sleep(700);await capture('03-concentratord-sx1302-as923');
 if(await click('MQTT Forwarder')){for(let i=0;i<6&&await evaluate("document.body.innerText.includes('Loading view…')");i++)await sleep(1000);await capture('04-mqtt-forwarder');if(await click('MQTT configuration'))await capture('04b-mqtt-forwarder-configuration')}
 if(await click('Network')){await capture('05-network-menu');if(await click('Interfaces')){await capture('06-network-interfaces');const did=await evaluate("(()=>{const b=[...document.querySelectorAll('a,button')].filter(x=>x.textContent?.trim()==='Edit');if(b[2]){b[2].click();return true;}return false;})()");if(did){await sleep(1350);await capture('07-lte-interface-general');if(await click('Advanced Settings'))await capture('07b-lte-interface-advanced')}}}
 if(await click('System')){await capture('08-system-menu');if(await click('Backup / Flash Firmware'))await capture('09-backup-flash')}
}catch(e){console.error('SCREEN_CAPTURE_INCOMPLETE',e.message);process.exitCode=1}
finally{try{ws?.close()}catch{}try{child.kill()}catch{}}
