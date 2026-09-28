import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const base='lorawan-network-server-gateway/documentation/';
const dir=base+'word-src/';
const canonical=base+'LoRaWAN-Operator-Manual-WIP.docx';
const chapter5=dir+'.manual-chapter5-qa.docx';
const candidate=dir+'.manual-chapter6-qa.docx';
const source=dir+'06-chirpstack-cloud.md';
const exe=path.join(process.env.USERPROFILE,'.rel-ai-mcp','extensions','.bin','officecli.exe');
const calls=[];
function cli(...a) {
 const r=spawnSync(exe,a,{encoding:'utf8',timeout:40000,maxBuffer:4500000,env:{...process.env,OFFICECLI_SKIP_UPDATE:'1'}});
 calls.push({action:a[0],status:r.status,text:(r.stdout||r.stderr||'').slice(0,180)});
 if(r.status!==0)throw Error(a[0]+': '+(r.stderr||r.stdout||r.error?.message));
 return (r.stdout||'').trim();
}
function picture(filename,cap,alt) {
 const file=base+'assets/'+filename;
 if(!fs.existsSync(file)||fs.statSync(file).size<8000)throw Error('Missing actual screenshot '+file);
 const res=cli('add',candidate,'/body','--type','paragraph','--prop','text= ','--prop','align=center','--prop','keepNext=true');
 const p=res.match(/\/body\/p\[[^\]]+\]/)?.[0];
 if(!p)throw Error('Picture paragraph missing');
 cli('add',candidate,p,'--type','picture','--prop','src='+file,'--prop','width=15.0cm','--prop','alt='+alt);
 cli('add',candidate,'/body','--type','paragraph','--prop','text='+cap,'--prop','size=8.5pt','--prop','italic=true','--prop','align=center','--prop','color=#475569','--prop','keepNext=false');
}
try {
 if(!fs.existsSync(canonical)||!fs.existsSync(chapter5))throw Error('Canonical/chapter 5 candidate absent');
 const src=fs.readFileSync(source,'utf8');
 if(!src.startsWith('# Chapter 6')||src.includes('jervis128662120269'))throw Error('Bad chapter 6 source');
 const hasChapter5=spawnSync('py',['-3','-c',"from zipfile import ZipFile;import sys;d=ZipFile(sys.argv[1]).read('word/document.xml').decode('utf8');print('YES' if 'Chapter 5' in d else 'NO')",chapter5],{encoding:'utf8'});
 if(hasChapter5.status!==0||!hasChapter5.stdout.includes('YES'))throw Error('Chapter 5 missing in base candidate');
 if(fs.existsSync(candidate)){try{cli('close',candidate)}catch{}fs.unlinkSync(candidate)}
 fs.copyFileSync(chapter5,candidate);
 let partIndex=0,blocks=0,images=0;
 for(const piece of src.split(/(<!--[ ]*CHIRPSTACK_(?:LOGIN|OPERATOR)_REAL[ ]*-->|\x60\x60\x60(?:bash|powershell)\r?\n[\s\S]*?\r?\n\x60\x60\x60)/g)){
  if(!piece.trim())continue;
  if(piece.includes('<!-- CHIRPSTACK_LOGIN_REAL')) {
   picture('chirpstack-login-zoomed-20260922.png','Screen 6A. ChirpStack sign-in. Check the site address and enter your approved account.','Actual project ChirpStack login page, password not visible'); images++;continue;
  }
  if(piece.includes('<!-- CHIRPSTACK_OPERATOR_REAL')) {
   picture('chirpstack-operator-20260922.png','Screen 6B. ChirpStack tenant dashboard after login. Check the tenant and left navigation.','Actual project ChirpStack operator page'); images++;continue;
  }
  if(/^\x60\x60\x60(?:bash|powershell)/.test(piece)) {
   const code=piece.replace(/^\x60\x60\x60(?:bash|powershell)\r?\n/,'').replace(/\r?\n\x60\x60\x60$/,'');
   cli('add',candidate,'/body','--type','paragraph','--prop','text='+code,'--prop','font=Consolas','--prop','size=9pt','--prop','leftIndent=0.2cm','--prop','shd=F1F5F9','--prop','spaceBefore=4pt','--prop','spaceAfter=7pt','--prop','keepLines=false');
   blocks++;continue;
  }
  const part=dir+'.ch6-section-'+(++partIndex)+'.md';
  fs.writeFileSync(part,piece.trim()+'\n');
  cli('add',candidate,'/','--type','markdown','--prop','src='+part);
 }
 cli('save',candidate);cli('close',candidate);
 const probe=`from zipfile import ZipFile
from xml.etree import ElementTree as E
import sys
n='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
r=E.fromstring(ZipFile(sys.argv[1]).read('word/document.xml'))
p=r.find(n+'body').findall(n+'p')
for i,e in enumerate(p,1):
 t=''.join(z.text or '' for z in e.iter(n+'t'))
 if t.startswith('Chapter 6') or t.startswith('Working draft'):
  print(i,'CH6' if t.startswith('Chapter 6') else 'COVER')
`;
 const scan=spawnSync('py',['-3','-c',probe,candidate],{encoding:'utf8',timeout:12000});
 if(scan.status!==0)throw Error('Paragraph probe: '+scan.stderr);
 const indices=scan.stdout.trim().split(/\r?\n/).map(x=>x.split(' '));
 const heading=Number(indices.find(x=>x[1]==='CH6')?.[0]);
 const cover=Number(indices.find(x=>x[1]==='COVER')?.[0]);
 if(!heading||!cover||heading<239)throw Error('No Chapter6/cover '+scan.stdout);
 cli('set',candidate,'/body/p['+heading+']','--prop','pageBreakBefore=true','--prop','keepNext=true');
 cli('set',candidate,'/body/p['+cover+']','--prop','text=Working draft — Chapters 1–6 — 22 September 2026');
 cli('save',candidate);cli('close',candidate);cli('validate',candidate);
 fs.writeFileSync(dir+'CHAPTER6-BUILD-LOG.json',JSON.stringify({heading,cover,images,blocks,sourceSections:partIndex,candidateBytes:fs.statSync(candidate).size,calls},null,2)+'\n');
 console.log('CHAPTER6_CREATED',fs.statSync(candidate).size,heading,images,blocks);
}catch(e){
 fs.writeFileSync(dir+'CHAPTER6-BUILD-ERROR.log',String(e.stack||e)+'\n'+JSON.stringify(calls.slice(-8),null,2));
 console.error('CHAPTER6_FAILED',e.message);process.exitCode=1;
}
