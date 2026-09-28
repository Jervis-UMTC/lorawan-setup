from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
p=Path(__file__).resolve().parent
W,H=1750,1140
im=Image.new('RGB',(W,H),'#ffffff');d=ImageDraw.Draw(im)
fonts=Path('C:/Windows/Fonts')
b=lambda n:ImageFont.truetype(str(fonts/'arialbd.ttf'),n)
r=lambda n:ImageFont.truetype(str(fonts/'arial.ttf'),n)
navy='#163A48';teal='#126977';pale='#EDF8F8'
d.rounded_rectangle((24,22,W-25,H-20),radius=24,outline=teal,width=5)
d.text((65,65),'SIM7600  |  QMI LTE INTERFACE',font=b(62),fill=navy)
d.text((65,150),'Gateway-01 tracked OpenWrt network defaults',font=r(33),fill='#475569')
d.text((65,212),'CONFIGURATION WORKSHEET — NOT A LIVE LUCi SCREENSHOT',font=b(30),fill='#AA5D1A')
rows=[
('LuCI interface','Network → Interfaces → lte'),
('Protocol','QMI Cellular'),
('Modem control device','/dev/cdc-wdm0'),
('APN (commissioned DITO SIM)','internet.dito.ph'),
('Authentication','none'),
('PDP type','IP / IPv4'),
('Create lte_4 DHCP child','NO  (dhcp=0)'),
('Auto default route (netifd)','NO  (defaultroute=0)'),
('Use peer DNS','YES  (peerdns=1)'),
('System default-route owner','/usr/sbin/lte-route-health'),
('LTE production route','wwan0  /  metric 10'),
('RJ45 management Ethernet','br-lan  /  192.168.20.11/24')
]
y=283
for i,(l,v) in enumerate(rows):
  d.rounded_rectangle((61,y,1686,y+64),radius=9,fill=pale if i%2==0 else 'white',outline='#D1E2E8',width=2)
  d.text((89,y+14),l,font=b(28),fill=navy)
  d.text((838,y+14),v,font=r(28),fill=teal)
  y+=67
d.text((65,1094),'Inspect first. Do not overwrite a working gateway just to reproduce this picture.',font=r(27),fill=navy)
o=p/'lte-qmi-project-settings-worksheet.png'
im.save(o,optimize=True)
print(o,o.stat().st_size)
