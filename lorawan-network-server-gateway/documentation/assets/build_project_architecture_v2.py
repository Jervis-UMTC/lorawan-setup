"""Deterministic exact LoRaWAN project diagram for Word Chapter 1."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
root=Path(__file__).resolve().parent
out=root/'project-architecture-chapter1-v2.png'
ff=Path('C:/Windows/Fonts')
reg=str(ff/'arial.ttf');bold=str(ff/'arialbd.ttf')
im=Image.new('RGB',(2700,1090),'white');d=ImageDraw.Draw(im)
NAVY='#163C49';TEAL='#13677A';AMBER='#A65F24';SLATE='#49616C'
def font(sz,heavy=False):return ImageFont.truetype(bold if heavy else reg,sz)
def txtcenter(box,text,sz,heavy=False,color=NAVY):
 x0,y0,x1,y1=box
 while sz>23 and d.textbbox((0,0),text,font=font(sz,heavy))[2]>x1-x0-24:sz-=1
 bbox=d.textbbox((0,0),text,font=font(sz,heavy));ww=bbox[2]-bbox[0];hh=bbox[3]-bbox[1]
 d.text((x0+(x1-x0-ww)/2,y0+(y1-y0-hh)/2-bbox[1]),text,font=font(sz,heavy),fill=color)
def box(x0,x1,y0,y1,name,sub,edge,bg):
 d.rounded_rectangle((x0,y0,x1,y1),radius=19,fill=bg,outline=edge,width=5)
 txtcenter((x0+8,y0+21,x1-8,y0+89),name,43,True)
 txtcenter((x0+8,y0+98,x1-8,y1-12),sub,33,False,SLATE)
def arrow(pts,color,w=6):
 d.line(pts,fill=color,width=w,joint='curve')
 a,b=pts[-2:]
 if b[0]>a[0]:q=[b,(b[0]-23,b[1]-12),(b[0]-23,b[1]+12)]
 elif b[0]<a[0]:q=[b,(b[0]+23,b[1]-12),(b[0]+23,b[1]+12)]
 else:q=[b,(b[0]-12,b[1]-23),(b[0]+12,b[1]-23)]
 d.polygon(q,fill=color)
d.text((52,34),'EMU-01 → GATEWAY-01 → CLOUD + VERIFIED EVIDENCE',font=font(62,True),fill=NAVY)
d.text((54,113),'Exact project roles • plain AS923 • one RF uplink, two observation paths',font=font(36),fill=SLATE)
d.rounded_rectangle((687,181,2643,245),radius=15,fill=TEAL)
d.text((709,193),'TELEMETRY  |  receive → forward → normalize → store',font=font(42,True),fill='white')
d.rounded_rectangle((687,653,1815,716),radius=15,fill=AMBER)
d.text((709,665),'EVIDENCE  |  observe → retain → verify → anchor',font=font(38,True),fill='white')
box(42,305,425,599,'EMU-01','RAK4631 / AS923',TEAL,'#EEF8FA')
box(358,639,425,599,'Gateway-01','RAK5146 / OS Base',TEAL,'#EEF8FA')
arrow([(305,511),(358,511)],TEAL)
arrow([(639,468),(666,468),(666,357),(696,357)],TEAL)
arrow([(639,555),(666,555),(666,821),(696,821)],AMBER)
xs=[(696,1016),(1069,1389),(1442,1762),(1815,2135),(2188,2640)]
tp=[('Local MQTT','LTE · wwan0'),('Cloud MQTT','ULC-01 + ULC-02'),('ChirpStack','application uplink'),('Node-RED A','sole SQL writer'),('PostgreSQL','Grafana read-only')]
bt=[('Journal','independent RF'),('Upload + ingest','HTTPS / mTLS'),('SeaweedFS','exact raw objects'),('Verifier','journal + MQTT + SQL'),('Fabric + HRC','Transit / digest MATCH')]
for (x0,x1),(title,detail) in zip(xs,tp):box(x0,x1,279,433,title,detail,TEAL,'#F0F9FB')
for (x0,x1),(title,detail) in zip(xs,bt):box(x0,x1,744,899,title,detail,AMBER,'#FFF7EE')
for (_,x1),(x2,_) in zip(xs[:-1],xs[1:]):
 arrow([(x1,355),(x2,355)],TEAL)
 arrow([(x1,821),(x2,821)],AMBER)
# Both independent cloud broker sessions contribute collector witnesses to verification.
# The evidence banner intentionally ends before this cross-lane connection.
d.line([(1227,433),(1227,556),(1960,556),(1960,744)],fill=AMBER,width=5)
d.polygon([(1960,744),(1948,722),(1972,722)],fill=AMBER)
d.rounded_rectangle((1310,518,1900,592),radius=12,fill='white',outline=AMBER,width=3)
txtcenter((1318,519,1892,592),'MQTT witness: BOTH brokers',35,True,AMBER)
d.text((55,947),'VERIFY: journal segment + cloud MQTT witnesses + trusted decoder + normalized SQL fields.',font=font(37),fill=NAVY)
d.text((55,1009),'ANCHOR: only verified v2 payload → OpenBao Transit → HRC commit, Query and digest MATCH.',font=font(36),fill=NAVY)
im.save(out,optimize=True)
print('EXACT_DIAGRAM',out.stat().st_size)
