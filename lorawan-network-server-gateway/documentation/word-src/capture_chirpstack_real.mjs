import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
const out='lorawan-network-server-gateway/documentation/assets/live-chirpstack-20260922';
fs.mkdirSync(out,{recursive:true});
const port=19224, sleep=ms=>new Promise(r=>setTimeout(r,ms));
const profile=fs.mkdtempSync(path.join(os.tmpdir(),'lorawan-cloud-manual-'));
const proc=spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',['--headless=new','--no-first-run','--disable-gpu','--remote-allow-origins=*','--remote-debugging-port='+port,'--window-size=1440,980','--user-data-dir='+profile,'https://smartagri-chirpstack.duckdns.org/'],{stdio:'ignore',windowsHide:true});
let ws,id=0;const pending=new Map();
function cmd(method,params={}){const seq=++id;return new Promise((resolve,reject)=>{const t=setTimeout(()=>{pending.delete(seq);reject(Error(method+' timeout'))},16000);pending.set(seq,{resolve,reject,t});ws.send(JSON.stringify({id:seq,method,params}))})}
async function run(js){const r=await cmd('Runtime.evaluate',{expression:js,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error('JS: '+js.slice(0,55));return r.result?.value}
async function shot(name){await sleep(420);const r=await cmd('Page.captureScreenshot',{format:'png'});const p=path.join(out,name+'.png');fs.writeFileSync(p,Buffer.from(r.data,'base64'));console.log('CAPTURED',name,fs.statSync(p).size)}
async function link(label,last=false){
 const js="(()=>{const a=[...document.querySelectorAll('a')].filter(x=>x.textContent?.trim()==="+JSON.stringify(label)+");const x="+(last?'a[a.length-1]':'a[0]')+";if(!x)return false;x.click();return true;})()";
 const ok=await run(js);await sleep(1350);console.log('LINK',label,ok);return ok;
}
async function tap(label){
 const js="(()=>{const a=[...document.querySelectorAll('[role=tab],a,button')].find(x=>x.textContent?.trim()==="+JSON.stringify(label)+");if(!a)return false;a.click();return true;})()";
 const ok=await run(js);await sleep(1150);console.log('TAB',label,ok);return ok;
}
async function findLink(part){
 const js="(()=>{let a=[...document.querySelectorAll('a[href]')].find(x=>x.textContent?.includes("+JSON.stringify(part)+"));if(a){a.click();return true}return false})()";
 const ok=await run(js);await sleep(1250);console.log('FIND',part,ok);return ok;
}
try{
 let pages;for(let i=0;i<40;i++){try{pages=await (await fetch('http://127.0.0.1:'+port+'/json/list')).json();if(pages.some(x=>x.type==='page'))break}catch{}await sleep(350)}
 const tab=pages?.find(x=>x.type==='page'&&x.webSocketDebuggerUrl);if(!tab)throw Error('No browser tab');
 ws=new WebSocket(tab.webSocketDebuggerUrl);ws.onmessage=e=>{const m=JSON.parse(e.data),q=pending.get(m.id);if(q){clearTimeout(q.t);pending.delete(m.id);m.error?q.reject(Error(m.error.message)):q.resolve(m.result||{})}};
 await new Promise((ok,fail)=>{ws.onopen=ok;ws.onerror=fail;setTimeout(()=>fail(Error('socket timeout')),12000)});
 await cmd('Page.enable');await cmd('Runtime.enable');await sleep(2300);
 await shot('01-cloud-login');
 if(!process.env.CHIRP_AUTH)throw Error('CHIRP_AUTH required');
 await run("(()=>{const xs=document.querySelectorAll('input');const u=document.querySelector('input[type=text]'),p=document.querySelector('input[type=password]');if(!u||!p)return false;const setter=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;setter.call(u,'admin');u.dispatchEvent(new Event('input',{bubbles:true}));setter.call(p,"+JSON.stringify(process.env.CHIRP_AUTH)+");p.dispatchEvent(new Event('input',{bubbles:true}));const b=document.querySelector('button[type=submit]');if(b)b.click();else p.closest('form')?.requestSubmit();return true})()");
 for(let i=0;i<28;i++){await sleep(550);if(await run("document.body.innerText.includes('Gateways') && !document.body.innerText.includes('ChirpStack login')"))break;}
 console.log('PAGE_AFTER_LOGIN',await run('document.title'),await run('location.href'));
 if(!(await run("document.body.innerText.includes('Tenants')")))throw Error('Cloud login did not complete');
 await shot('02-tenant-dashboard');
 if(await link('Gateways')){await shot('03-gateway-list');if(await link('0016c001f139a1cb')){await shot('04-gateway-detail');if(await tap('Events'))await shot('05-gateway-events');if(await tap('Frames'))await shot('05b-gateway-frames')}}
 if(await link('Device Profiles',true)){await shot('06-device-profiles-list');const s=await run("document.body.innerText.slice(-700)");console.log('PROFILES_LAST_700',s.replace(/[\\r\\n]+/g,' ').slice(0,500))}
 if(await link('Applications')){await shot('07-applications-list'); const a=await run("[...document.querySelectorAll('a[href]')].filter(x=>x.getAttribute('href')?.includes('/applications/')&&x.textContent.trim().length>2).map(x=>x.textContent.trim()).slice(0,6)");console.log('APPLICATION_LINKS',JSON.stringify(a));if(a?.length&&await findLink(a[0])){await shot('08-application-devices');const b=await run("[...document.querySelectorAll('a[href]')].filter(x=>x.getAttribute('href')?.includes('/devices/')&&x.textContent.trim().length>1).map(x=>x.textContent.trim()).slice(0,8)");console.log('DEVICE_LINKS',JSON.stringify(b));if(b?.length&&await findLink(b.find(x=>/EMU|SEC/i.test(x))||b[0])){await shot('09-device-detail');if(await tap('Events'))await shot('10-device-events')}}}
}catch(e){console.error('CLOUD_CAPTURE_INCOMPLETE',e.message);process.exitCode=1}
finally{try{ws?.close()}catch{}try{proc.kill()}catch{}}
