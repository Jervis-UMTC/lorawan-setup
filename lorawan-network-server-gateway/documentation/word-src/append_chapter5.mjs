import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const base='lorawan-network-server-gateway/documentation/';
const dir=base+'word-src/';
const original=base+'LoRaWAN-Operator-Manual-WIP.docx';
const candidate=dir+'.manual-chapter5-qa.docx';
const src=dir+'05-local-mqtt-buffer-and-bridges.md';
const exe=path.join(process.env.USERPROFILE,'.rel-ai-mcp','extensions','.bin','officecli.exe');
const record=[];
function cli(...args){
 const r=spawnSync(exe,args,{env:{...process.env,OFFICECLI_SKIP_UPDATE:'1'},encoding:'utf8',timeout:35000,maxBuffer:3000000});
 record.push({action:args[0],status:r.status,message:(r.stdout||r.stderr||'').slice(0,150)});
 if(r.status!==0) throw Error(args[0]+': '+(r.stderr||r.stdout||r.error?.message));
 return (r.stdout||'').trim();
}
try{
 if(!fs.existsSync(original)||fs.statSync(original).size<1000000)throw Error('Missing canonical manual');
 const md=fs.readFileSync(src,'utf8');
 if(!md.startsWith('# Chapter 5')||md.includes('jervis128662120269'))throw Error('Unexpected source');
 const old=fs.readFileSync(original);
 if(fs.existsSync(candidate)){try{cli('close',candidate)}catch{}fs.unlinkSync(candidate)}
 fs.copyFileSync(original,candidate);
 let ix=0;
 for(const piece of md.split(/(```sh\r?\n[\s\S]*?\r?\n```)/g)){
  if(!piece.trim())continue;
  if(piece.startsWith('```sh')){
   const code=piece.replace(/^```sh\r?\n/,'').replace(/\r?\n```$/,'');
   cli('add',candidate,'/body','--type','paragraph','--prop','text='+code,'--prop','font=Consolas','--prop','size=9pt','--prop','leftIndent=0.20cm','--prop','shd=F1F5F9','--prop','spaceBefore=4pt','--prop','spaceAfter=7pt','--prop','keepLines=false');
  }else{
   const part=dir+'.ch5-section-'+(++ix)+'.md';
   fs.writeFileSync(part,piece.trim()+'\n');
   cli('add',candidate,'/','--type','markdown','--prop','src='+part);
  }
 }
 cli('save',candidate);cli('close',candidate);
 const py=`from zipfile import ZipFile
from xml.etree import ElementTree as E
import sys
n='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
r=E.fromstring(ZipFile(sys.argv[1]).read('word/document.xml'))
p=r.find(n+'body').findall(n+'p')
for i,e in enumerate(p,1):
 t=''.join(z.text or '' for z in e.iter(n+'t'))
 if t.startswith('Chapter 5') or t.startswith('Working draft'):
  print(i, 'CH5' if t.startswith('Chapter 5') else 'COVER')
`;
 const q=spawnSync('py',['-3','-c',py,candidate],{encoding:'utf8',timeout:15000});
 if(q.status!==0)throw Error('Paragraph scan failed: '+q.stderr);
 const lines=q.stdout.trim().split(/\r?\n/).map(x=>x.split(' '));
 const heading=Number(lines.find(x=>x[1]==='CH5')?.[0]),cover=Number(lines.find(x=>x[1]==='COVER')?.[0]);
 if(!heading||!cover||heading<220)throw Error('Cannot locate Chapter5/cover: '+q.stdout);
 cli('set',candidate,'/body/p['+heading+']','--prop','pageBreakBefore=true','--prop','keepNext=true');
 cli('set',candidate,'/body/p['+cover+']','--prop','text=Working draft — Chapters 1–5 — 22 September 2026');
 cli('save',candidate);cli('close',candidate);cli('validate',candidate);
 fs.writeFileSync(dir+'CHAPTER5-BUILD-LOG.json',JSON.stringify({chapterHeading:heading,cover:cover,sourceSections:ix,steps:record},null,2)+'\n');
 console.log('CHAPTER5_QA_CREATED',candidate,fs.statSync(candidate).size,'heading',heading,'cover',cover,'markdownSections',ix);
}catch(e){
 fs.writeFileSync(dir+'CHAPTER5-BUILD-ERROR.log',String(e.stack||e)+'\n'+JSON.stringify(record.slice(-8),null,2));
 console.error('CHAPTER5_BUILD_FAILED',e.message);process.exitCode=1;
}
