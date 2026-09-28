from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
p=Path(__file__).resolve().parent
W,H=1800,1180
im=Image.new('RGB',(W,H),'#ffffff')
d=ImageDraw.Draw(im)
fonts=Path('C:/Windows/Fonts')
bold=lambda n:ImageFont.truetype(str(fonts/'arialbd.ttf'),n)
reg=lambda n:ImageFont.truetype(str(fonts/'arial.ttf'),n)
dark='#173C4B';teal='#126877';muted='#45576A';pale='#EFF7F8';line='#CBDCE2'
d.rounded_rectangle((28,22,1770,1152),radius=35,outline=teal,width=5,fill='white')
d.text((73,70),'RAK5146  /  CONCENTRATORD',font=bold(65),fill=dark)
d.text((76,159),'Project configuration worksheet from the tracked Gateway OS overlay',font=reg(37),fill=muted)
d.text((76,219),'NOT A SCREENSHOT OF A LIVE OR POWERED GATEWAY',font=bold(32),fill='#A55B1A')
rows=[
 ('LuCI menu','ChirpStack  >  Concentratord'),
 ('Global  ·  Enabled','ON / checked'),
 ('Global  ·  Enabled chipset','SX1302 / SX1303'),
 ('SX1302  ·  Shield model','RAK - RAK5146   (rak_5146)'),
 ('SX1302  ·  Region','AS923   (plain / standard)'),
 ('SX1302  ·  Channel plan','as923'),
 ('SX1302  ·  Bus','SPI   (USB OFF)'),
 ('SX1302  ·  GNSS','ON  (if installed module has GNSS)'),
 ('SX1302  ·  Antenna gain','2 dBi tracked (check real antenna)'),
 ('SX1302  ·  Gateway ID','leave override EMPTY (read chip EUI)')
]
y=286
for i,(k,v) in enumerate(rows):
 d.rounded_rectangle((73,y,1724,y+70),radius=11,fill=pale if i%2==0 else '#FFFFFF',outline=line,width=2)
 d.text((104,y+16),k,font=bold(31),fill=dark)
 d.text((837,y+16),v,font=reg(32),fill=teal)
 y+=77
d.line((76,1070,1722,1070),fill=teal,width=3)
d.text((82,1084),'After Save & Apply ONCE: refresh; read Gateway EUI from running SX1303 (not SX1301 example).',font=reg(28),fill=dark)
im.save(p/'gateway-concentratord-verified-settings.png',optimize=True)
print('GRAPHIC',W,H,(p/'gateway-concentratord-verified-settings.png').stat().st_size)
