from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json

base=Path('lorawan-network-server-gateway/documentation/assets')
out=base/'sensor-chapter'
out.mkdir(parents=True,exist_ok=True)

def f(sz,bold=False):
    for p in ([Path('C:/Windows/Fonts/arialbd.ttf'),Path('C:/Windows/Fonts/calibrib.ttf')] if bold else [Path('C:/Windows/Fonts/arial.ttf'),Path('C:/Windows/Fonts/calibri.ttf')]):
        if p.exists(): return ImageFont.truetype(str(p),sz)
    return ImageFont.load_default()

# EMU-01 fixed slot map
W,H=1600,1000
im=Image.new('RGB',(W,H),'white'); d=ImageDraw.Draw(im)
d.text((55,30),'EMU-01 - RAK19001 Fixed WisBlock Slot Map',font=f(46,True),fill=(18,28,45))
d.text((55,90),'Commissioned project layout | RAK4631 Core A | plain AS923 | power OFF before moving modules',font=f(24),fill=(60,72,90))
d.rounded_rectangle((110,160,1490,875),radius=28,fill=(244,247,251),outline=(71,85,105),width=4)
d.rounded_rectangle((555,205,1045,345),radius=18,fill=(224,242,254),outline=(14,116,144),width=3)
d.text((690,228),'WisBlock Core',font=f(25,True),fill=(15,23,42)); d.text((665,272),'RAK4631 Core A',font=f(34,True),fill=(8,47,73))
slots=[
 ('Sensor A','RAK1903 OPT3001 light','WB_IO1',(155,400,555,515)),
 ('Sensor B','RAK12010 VEML7700 light','I2C; WB_IO2 = shared 3V3_S enable',(600,400,1000,515)),
 ('Sensor C','RAK12019 LTR390 UV','WB_IO3',(1045,400,1445,515)),
 ('Sensor D','RAK12011 barometer / temperature','WB_IO5',(155,550,555,665)),
 ('Sensor E','RAK1906 BME680 environment','I2C; WB_IO4 reserved for soil',(600,550,1000,665)),
 ('Sensor F','EMPTY / reserve','WB_IO6 reserved for rain',(1045,550,1445,665)),
 ('WisIO 1','RAK12023 -> RAK12035 soil probe','WB_IO4',(250,715,775,830)),
 ('WisIO 2','RAK12005 -> RAK12030 rain pad','WB_IO6',(825,715,1350,830)),
]
fill=[(238,246,255),(238,250,244),(255,249,234),(249,242,255),(239,253,250),(248,250,252),(255,245,234),(255,245,234)]
for i,(name,mod,io,r) in enumerate(slots):
    d.rounded_rectangle(r,radius=16,fill=fill[i],outline=(102,117,138),width=2)
    d.text((r[0]+16,r[1]+12),name,font=f(23,True),fill=(15,23,42))
    d.text((r[0]+16,r[1]+45),mod,font=f(19,True),fill=(30,41,59))
    d.text((r[0]+16,r[1]+78),io,font=f(16),fill=(71,85,105))
d.rounded_rectangle((110,900,1490,975),radius=12,fill=(255,248,230),outline=(178,125,20),width=2)
d.text((140,922),'STOP: disconnect USB, battery, and solar power before you remove or reseat any WisBlock module.',font=f(23,True),fill=(122,72,8))
im.save(out/'emu01-slot-map.png')

# Serial ports actual read-only snapshot
j=Path('lorawan-network-server-gateway/documentation/word-src/.serial-ports-now.json')
rows=json.loads(j.read_text(encoding='utf-8-sig')) if j.exists() else []
im=Image.new('RGB',(1500,500),(20,25,35)); d=ImageDraw.Draw(im)
d.text((36,25),'Windows serial-port identity - read-only snapshot',font=f(34,True),fill=(239,246,255))
d.text((36,74),'Rediscover ports after reset or DFU. Do not hard-code COM numbers.',font=f(21),fill=(184,200,220))
y=140
for x in rows:
    role='EMU-01' if x.get('DeviceID')=='COM11' else ('SEC-01' if x.get('DeviceID')=='COM16' else 'Unknown')
    d.rounded_rectangle((36,y,1460,y+120),radius=12,fill=(31,41,55),outline=(74,94,118),width=2)
    d.text((56,y+15),f"{role}   {x.get('DeviceID','?')}",font=f(26,True),fill=(147,231,185))
    d.text((56,y+50),x.get('Description',''),font=f(20),fill=(226,232,240))
    d.text((56,y+80),x.get('PNPDeviceID',''),font=f(17),fill=(187,199,214))
    y+=135
im.save(out/'serial-port-identity.png')
print('CREATED',out/'emu01-slot-map.png',out/'serial-port-identity.png')
