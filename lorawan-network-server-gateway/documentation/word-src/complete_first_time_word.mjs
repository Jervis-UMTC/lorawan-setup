import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const dir='lorawan-network-server-gateway/documentation/';
const work=dir+'word-src/';
const doc=work+'.manual-full-setup-qa.docx';
const exe=path.join(process.env.USERPROFILE,'.rel-ai-mcp','extensions','.bin','officecli.exe');
const dump=JSON.parse(fs.readFileSync(work+'.body-full-setup.json','utf8').replace(/^\uFEFF/,''));
const rows=dump.data.results[0].children;
const text=x=>String(x.text||'');
const anchor=rows.find(x=>text(x).startsWith('6.2 Find the correct Gateway-01 entry'));
const sectionIndex=rows.findIndex(x=>text(x).startsWith('6.1A First-time cloud enrollment'));
if(!anchor || sectionIndex<0)throw Error('Cannot locate first-time setup section / 6.2 anchor');
const added=rows.slice(sectionIndex).filter(x=>x.type==='paragraph');
if(added.length<27||added.length>75)throw Error('Unexpected appended paragraph count '+added.length);
function widthProps(filename){
 const src=dir+'assets/live-chirpstack-20260922/'+filename;
 const b=fs.readFileSync(src);
 if(b.toString('ascii',1,4)!=='PNG'||b.length<18000)throw Error('Missing real PNG '+src);
 const w=b.readUInt32BE(16),h=b.readUInt32BE(20);
 return {src,width:'15.1cm',height:(15.1*h/w).toFixed(2)+'cm',alt:'Full real ChirpStack enrollment form'};
}
const pictureMap=new Map([
 ['[[CH6_ADD_GATEWAY_FULLPAGE]]','13-add-gateway-fullpage.png'],
 ['[[CH6_ADD_PROFILE_FULLPAGE]]','14-add-device-profile-fullpage.png'],
 ['[[CH6_EXISTING_PROFILE_FULLPAGE]]','15-existing-emu-profile-fullpage.png'],
 ['[[CH6_ADD_APPLICATION_FULLPAGE]]','16-add-application-fullpage.png'],
 ['[[CH6_ADD_DEVICE_FULLPAGE]]','12-add-device-fullpage.png']
]);
const commands=[];
for(const row of added)commands.push({command:'move',path:row.path,before:anchor.path});
let inserted=0;
for(const row of added){
 const t=text(row);
 if(pictureMap.has(t)){
   commands.push({command:'set',path:row.path,props:{text:' '}});
   commands.push({command:'add',parent:row.path,type:'picture',props:widthProps(pictureMap.get(t))});
   inserted++;
 }
 if(/^Screen 6[K-O]\./.test(t)){
   const repl=t.replace(/^Screen 6K\./,'Screen 6.1A-1.').replace(/^Screen 6L\./,'Screen 6.1A-2.').replace(/^Screen 6M\./,'Screen 6.1A-3.').replace(/^Screen 6N\./,'Screen 6.1A-4.').replace(/^Screen 6O\./,'Screen 6.1A-5.');
   commands.push({command:'set',path:row.path,props:{text:repl}});
 }
}
if(inserted!==5)throw Error('Expected 5 screenshot placeholders, got '+inserted);
const idx=rows.findIndex(x=>text(x).startsWith('Screen 6G.'));
if(idx<1||!rows[idx-1]?.path)throw Error('Existing partial Screen 6G not found');
commands.push({command:'set',path:rows[idx-1].path+'/r[2]',props:widthProps('08-applications-fullpage.png')});
commands.push({command:'set',path:rows[idx].path,props:{text:'Screen 6G. Applications list — select dissertation-sensors.'}});
const heading=rows.find(x=>text(x).startsWith('Chapter 6 — Open ChirpStack and Verify'));
if(heading)commands.push({command:'set',path:heading.path,props:{text:'Chapter 6 — Set Up ChirpStack and Register the Gateway and Sensors'}});
fs.writeFileSync(work+'FULL-SETUP-OFFICECLI-BATCH.json',JSON.stringify(commands,null,2));
const r=spawnSync(exe,['batch',doc,'--input',work+'FULL-SETUP-OFFICECLI-BATCH.json'],{encoding:'utf8',timeout:180000,maxBuffer:2500000,env:{...process.env,OFFICECLI_SKIP_UPDATE:'1'}});
fs.writeFileSync(work+'FULL-SETUP-OFFICECLI-RESULT.txt',(r.stdout||'')+'\n'+(r.stderr||''));
if(r.status!==0)throw Error('OfficeCLI batch: '+(r.stderr||r.stdout).slice(-2000));
for(const args of [['save',doc],['close',doc],['validate',doc]]){
 const a=spawnSync(exe,args,{encoding:'utf8',timeout:60000,env:{...process.env,OFFICECLI_SKIP_UPDATE:'1'}});
 if(a.status!==0)throw Error('OfficeCLI '+args[0]+': '+(a.stderr||a.stdout));
}
console.log('FULL_SETUP_WORD_QA_READY',added.length,inserted,fs.statSync(doc).size);
