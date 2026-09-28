from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
import tempfile, os, shutil

p=Path('lorawan-network-server-gateway/documentation/word-src/.manual-chapter7-qa.docx')
if not p.exists(): raise SystemExit('candidate missing')
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
ET.register_namespace('w',W)
with ZipFile(p,'r') as z:
    xml=z.read('word/document.xml')
root=ET.fromstring(xml)
tables=root.findall('.//{%s}tbl'%W)
for table in tables:
    rows=table.findall('{%s}tr'%W)
    for i,row in enumerate(rows):
        trPr=row.find('{%s}trPr'%W)
        if trPr is None:
            trPr=ET.Element('{%s}trPr'%W); row.insert(0,trPr)
        if trPr.find('{%s}cantSplit'%W) is None:
            trPr.append(ET.Element('{%s}cantSplit'%W))
        if i==0 and trPr.find('{%s}tblHeader'%W) is None:
            trPr.append(ET.Element('{%s}tblHeader'%W))
newxml=ET.tostring(root,encoding='utf-8',xml_declaration=True)
fd,tmp=tempfile.mkstemp(suffix='.docx'); os.close(fd)
with ZipFile(p,'r') as zin, ZipFile(tmp,'w',ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data=newxml if item.filename=='word/document.xml' else zin.read(item.filename)
        zout.writestr(item,data)
shutil.move(tmp,p)
print('TABLE_ROWS_FIXED',len(tables))
