"""Rebuild Chapter 1 project architecture PNG. Requires Pillow."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
out=Path(__file__).resolve().parent/"project-architecture-chapter1.png"
fdir=Path("/usr/share/fonts/truetype/dejavu")
win=Path("C:/Windows/Fonts")
reg=str((fdir/"DejaVuSans.ttf") if (fdir/"DejaVuSans.ttf").exists() else (win/"arial.ttf"))
bold=str((fdir/"DejaVuSans-Bold.ttf") if (fdir/"DejaVuSans-Bold.ttf").exists() else (win/"arialbd.ttf"))
im=Image.new("RGB",(2400,900),"#ffffff")
d=ImageDraw.Draw(im)
ft=ImageFont.truetype(bold,57); fh=ImageFont.truetype(bold,35)
fs=ImageFont.truetype(reg,28);fn=ImageFont.truetype(reg,28)
NAVY="#153B45"; TEAL="#146977";AMBER="#AD6929";LINE="#647986"
d.text((72,38),"SYSTEM ARCHITECTURE",font=ft,fill=NAVY)
d.text((75,110),"One physical uplink · two independently observed paths",font=fs,fill="#425968")
for x,y,width,label,color in [(763,159,1500,"TELEMETRY PATH",TEAL),(763,557,1500,"INDEPENDENT EVIDENCE & ANCHORING",AMBER)]:
 d.rounded_rectangle((x,y,x+width,y+55),radius=16,fill=color)
 d.text((x+24,y+10),label,font=fh,fill="white")
def box(x0,y0,x1,y1,main,sub="",edge=TEAL,fill="#F2F9FA",main_sz=33):
 d.rounded_rectangle((x0,y0,x1,y1),radius=19,fill=fill,outline=edge,width=5)
 font=ImageFont.truetype(bold,main_sz)
 w=d.textbbox((0,0),main,font=font)[2]
 sy=y0+38 if sub else y0+(y1-y0-36)//2
 d.text((x0+(x1-x0-w)/2,sy),main,font=font,fill=NAVY)
 if sub:
  sw=d.textbbox((0,0),sub,font=fs)[2]
  d.text((x0+(x1-x0-sw)/2,sy+50),sub,font=fs,fill="#4B6570")
def arrow(points,color=LINE,width=6):
 d.line(points,fill=color,width=width,joint="curve")
 a,b=points[-2],points[-1]
 if b[0]>a[0]:poly=[(b[0],b[1]),(b[0]-23,b[1]-13),(b[0]-23,b[1]+13)]
 elif b[0]<a[0]:poly=[(b[0],b[1]),(b[0]+23,b[1]-13),(b[0]+23,b[1]+13)]
 elif b[1]>a[1]:poly=[(b[0],b[1]),(b[0]-13,b[1]-23),(b[0]+13,b[1]-23)]
 else:poly=[(b[0],b[1]),(b[0]-13,b[1]+23),(b[0]+13,b[1]+23)]
 d.polygon(poly,fill=color)
box(50,392,330,565,"EMU-01","sensor",edge=TEAL,fill="#E7F4F6",main_sz=38)
box(400,392,680,565,"Gateway-01","RAK5146 / AS923",edge=TEAL,fill="#E7F4F6",main_sz=34)
arrow([(330,480),(400,480)],TEAL)
arrow([(680,464),(720,464),(720,317),(770,317)],TEAL)
arrow([(680,520),(720,520),(720,720),(770,720)],AMBER)
top=[(770,245,1080,387,"LTE + MQTT","cloud transport"),(1140,245,1450,387,"ChirpStack","LoRaWAN server"),(1510,245,1845,387,"Node-RED + SQL","telemetry writer"),(1905,245,2240,387,"Grafana","read-only charts")]
for args in top:box(*args,edge=TEAL,fill="#F0F8FA")
for x1,x2 in [(1080,1140),(1450,1510),(1845,1905)]:arrow([(x1,317),(x2,317)],TEAL)
bottom=[(770,646,1080,788,"Journal","original events"),(1140,646,1450,788,"SeaweedFS","raw evidence"),(1510,646,1845,788,"Verifier","match + decode"),(1905,646,2340,788,"OpenBao + Fabric","HRC anchor / digest")]
for args in bottom:box(*args,edge=AMBER,fill="#FFF8F1")
for x1,x2 in [(1080,1140),(1450,1510),(1845,1905)]:arrow([(x1,720),(x2,720)],AMBER)
d.text((72,840),"Evidence verification compares retained gateway observations with MQTT witnesses and stored telemetry.",font=fn,fill="#425968")
im.save(out,optimize=True)
print(str(out))
