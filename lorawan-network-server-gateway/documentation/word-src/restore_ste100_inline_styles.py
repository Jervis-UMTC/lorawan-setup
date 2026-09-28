import sys
import json
import difflib
from copy import deepcopy
from pathlib import Path

base=Path('lorawan-network-server-gateway/documentation')
word=base/'word-src'
sys.path.insert(0,str(word/'.docx-tools'))
from docx import Document
from docx.oxml.ns import qn

old=Document(base/'LoRaWAN-Operator-Manual-WIP.docx')
candidate_path=word/'.manual-ste100-qa.docx'
new=Document(candidate_path)
edits=[]
for name in ('ste-edits-ch1-3.json','ste-edits-ch4-5.json','ste-edits-ch6.json','ste-edits-supplement.json'):
    edits.extend(json.loads((word/name).read_text(encoding='utf-8')))
if len(edits)!=101 or len(old.paragraphs)!=len(new.paragraphs):
    raise RuntimeError('Paragraphs missing or candidate changed')
changed=0
emphasis_restored=0
for item in edits:
    i=item['index']
    a=old.paragraphs[i]
    b=new.paragraphs[i]
    if b.text != item['text']:
        raise RuntimeError(f'OfficeCLI text differs at paragraph {i}: {b.text[:80]!r}')
    if a._p.xpath('./w:drawing') or a._p.xpath('./w:hyperlink'):
        raise RuntimeError(f'Paragraph {i} contains a special element; skip unsafe rewrite')
    oldstyles=[]
    for run in a.runs:
        emph=bool(run.bold or run.italic or run.underline)
        prop=deepcopy(run._r.rPr) if emph and run._r.rPr is not None else None
        oldstyles.extend([prop]*len(run.text))
    if len(oldstyles)!=len(a.text):
        raise RuntimeError(f'Original run text mismatch in paragraph {i}')
    newstyles=[None]*len(b.text)
    match=difflib.SequenceMatcher(None,a.text,b.text,autojunk=False)
    for tag,a0,a1,b0,b1 in match.get_opcodes():
        if tag!='equal':continue
        for k in range(a1-a0):
            if oldstyles[a0+k] is not None:
                newstyles[b0+k]=oldstyles[a0+k]
    text=b.text
    b.clear()  # Keeps w:pPr, paragraph style, page-break and spacing.
    if not text:
        raise RuntimeError('Empty edited paragraph')
    pos=0
    while pos<len(text):
        props=newstyles[pos]
        key=props.xml if props is not None else None
        nxt=pos+1
        while nxt<len(text):
            other=newstyles[nxt]
            if (other.xml if other is not None else None)!=key:break
            nxt+=1
        run=b.add_run(text[pos:nxt])
        if props is not None:
            run._r.insert(0,deepcopy(props))
            emphasis_restored+=1
        pos=nxt
    if b.text!=text:raise RuntimeError(f'Unexpected formatting rewrite of paragraph {i}')
    changed+=1
new.save(candidate_path)
probe=Document(candidate_path)
for item in edits:
    if probe.paragraphs[item['index']].text!=item['text']:
        raise RuntimeError('Round trip text mismatch')
assets=probe.inline_shapes
if len(assets)!=41:raise RuntimeError(f'Images lost: {len(assets)} (expected 41)')
(word/'STE100-FORMAT-RESTORE.json').write_text(
    json.dumps({'paragraphs':changed,'styledSegmentsRestored':emphasis_restored,
                'images':len(assets),'paragraphsTotal':len(probe.paragraphs)},indent=2),
    encoding='utf-8')
print('STE100_FORMAT_RESTORED',changed,emphasis_restored,'images',len(assets))
