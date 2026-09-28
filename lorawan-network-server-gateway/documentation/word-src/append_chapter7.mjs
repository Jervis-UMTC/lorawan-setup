import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const base='lorawan-network-server-gateway/documentation/';
const dir=base+'word-src/';
const canonical=base+'LoRaWAN-Operator-Manual-WIP.docx';
const candidate=dir+'.manual-chapter7-qa.docx';
const source=dir+'07-emu01-wisblock-sensor.md';
const exe=path.join(process.env.USERPROFILE,'.rel-ai-mcp','extensions','.bin','officecli.exe');
const calls=[];

function cli(...args){
  const r=spawnSync(exe,args,{encoding:'utf8',timeout:50000,maxBuffer:4500000,
    env:{...process.env,OFFICECLI_SKIP_UPDATE:'1'}});
  calls.push({action:args[0],status:r.status,msg:(r.stdout||r.stderr||'').slice(0,180)});
  if(r.status!==0)throw Error(args[0]+': '+(r.stderr||r.stdout||r.error?.message));
  return (r.stdout||'').trim();
}
function addPicture(file,width,alt){
  if(!fs.existsSync(file)||fs.statSync(file).size<5000)throw Error('Missing image '+file);
  const res=cli('add',candidate,'/body','--type','paragraph','--prop','text= ',
    '--prop','align=center','--prop','keepNext=true','--prop','spaceBefore=6pt');
  const p=res.match(/\/body\/p\[[^\]]+\]/)?.[0];
  if(!p)throw Error('Picture paragraph missing: '+res);
  cli('add',candidate,p,'--type','picture','--prop','src='+file,
    '--prop','width='+width,'--prop','alt='+alt);
}
try{
  if(!fs.existsSync(canonical)||fs.statSync(canonical).size<3000000)throw Error('Canonical manual missing');
  const md=fs.readFileSync(source,'utf8');
  if(!md.startsWith('# Chapter 7'))throw Error('Unexpected Chapter 7 source');
  if(/AppKey\s*[:=]\s*[0-9a-f]{16,}/i.test(md))throw Error('Possible secret in source');
  if(fs.existsSync(candidate)){try{cli('close',candidate)}catch{}fs.unlinkSync(candidate)}
  fs.copyFileSync(canonical,candidate);

  const marker=/<!-- (?:EMU_RAK19001_VENDOR|EMU_SLOT_MAP|EMU_RAK4631_ANTENNA|EMU_SERIAL_PORT_REAL|EMU_SENSOR_SOURCE_REAL) -->/;
  const block=/~~~(?:powershell|text)\r?\n[\s\S]*?\r?\n~~~/;
  const splitter=new RegExp('('+marker.source+'|'+block.source+')','g');
  let parts=0,images=0,blocks=0;
  for(const piece of md.split(splitter)){
    if(!piece||!piece.trim())continue;
    if(piece.startsWith('<!-- ')){
      if(piece.includes('EMU_RAK19001_VENDOR')){
        addPicture(base+'assets/vendor-rakwireless-sensor/rak19001-overview.png','12.8cm',
          'Official RAK19001 reference board image from RAKwireless documentation'); images++;
      } else if(piece.includes('EMU_SLOT_MAP')){
        addPicture(base+'assets/sensor-chapter/emu01-slot-map.png','14.7cm',
          'Project EMU-01 RAK19001 fixed sensor slot map'); images++;
      } else if(piece.includes('EMU_RAK4631_ANTENNA')){
        addPicture(base+'assets/vendor-rakwireless-sensor/rak4631-antenna-label.png','11.8cm',
          'Official RAK4631 antenna connector label reference'); images++;
      } else if(piece.includes('EMU_SERIAL_PORT_REAL')){
        addPicture(base+'assets/sensor-chapter/serial-port-identity.png','14.5cm',
          'Actual read-only Windows serial-port identity snapshot for EMU-01 and SEC-01'); images++;
      } else if(piece.includes('EMU_SENSOR_SOURCE_REAL')){
        addPicture(base+'assets/sensor-chapter/emu01-sensor-source-real.png','14.5cm',
          'Historical real EMU-01 operator sensor source screen'); images++;
      }
      continue;
    }
    if(piece.startsWith('~~~')){
      const code=piece.replace(/^~~~(?:powershell|text)\r?\n/,'').replace(/\r?\n~~~$/,'');
      cli('add',candidate,'/body','--type','paragraph','--prop','text='+code,
        '--prop','font=Consolas','--prop','size=8.7pt','--prop','leftIndent=0.2cm',
        '--prop','shd=F1F5F9','--prop','spaceBefore=4pt','--prop','spaceAfter=7pt',
        '--prop','keepLines=false');
      blocks++;continue;
    }
    const file=dir+'.ch7-section-'+(++parts)+'.md';
    fs.writeFileSync(file,piece.trim()+'\n','utf8');
    cli('add',candidate,'/','--type','markdown','--prop','src='+file);
  }

  cli('save',candidate);cli('close',candidate);
  const scanPy=[
    'from zipfile import ZipFile',
    'from xml.etree import ElementTree as E',
    'import sys,json',
    "w='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'",
    'r=E.fromstring(ZipFile(sys.argv[1]).read("word/document.xml"))',
    "p=r.find(w+'body').findall(w+'p')",
    'for i,e in enumerate(p,1):',
    " t=''.join(x.text or '' for x in e.iter(w+'t'))",
    " if t.startswith('Chapter 7') or t.startswith('Working draft'): print(i, 'CH7' if t.startswith('Chapter 7') else 'COVER', t)"
  ].join('\n');
  const q=spawnSync('py',['-3','-c',scanPy,candidate],{encoding:'utf8',timeout:12000,maxBuffer:500000});
  if(q.status!==0)throw Error('Paragraph scan failed: '+q.stderr);
  const lines=q.stdout.trim().split(/\r?\n/);
  const h=lines.find(x=>x.includes(' CH7 '));
  const c=lines.find(x=>x.includes(' COVER '));
  if(!h||!c)throw Error('Chapter 7 or cover missing: '+q.stdout);
  const heading=Number(h.split(' ')[0]),cover=Number(c.split(' ')[0]);
  cli('set',candidate,'/body/p['+heading+']','--prop','pageBreakBefore=true','--prop','keepNext=true');
  cli('set',candidate,'/body/p['+cover+']','--prop','text=Working draft — Chapters 1–7 — 28 September 2026');
  cli('save',candidate);cli('close',candidate);cli('validate',candidate);
  fs.writeFileSync(dir+'CHAPTER7-BUILD-LOG.json',JSON.stringify({
    sourceSections:parts,codeBlocks:blocks,images,heading,cover,
    bytes:fs.statSync(candidate).size,calls
  },null,2)+'\n');
  console.log('CHAPTER7_QA_READY',fs.statSync(candidate).size,'heading',heading,'images',images,'blocks',blocks);
}catch(e){
  fs.writeFileSync(dir+'CHAPTER7-BUILD-ERROR.txt',String(e.stack||e)+'\n'+JSON.stringify(calls.slice(-10),null,2));
  console.error('CHAPTER7_BUILD_FAILED',e.message);process.exitCode=1;
}
