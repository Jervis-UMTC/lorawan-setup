from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
p=Path(__file__).resolve().parent
im=Image.new('RGB',(1770,960),'white');d=ImageDraw.Draw(im)
fp=Path('C:/Windows/Fonts')
bf=lambda n: ImageFont.truetype(str(fp/'arialbd.ttf'),n)
rf=lambda n: ImageFont.truetype(str(fp/'arial.ttf'),n)
nav='#163A48';tel='#126977';warn='#A55E23'
d.rounded_rectangle((25,24,1740,933),radius=28,outline=tel,width=5)
d.text((68,57),'GATEWAY-01  |  INTERNET PATH CHECK',font=bf(57),fill=nav)
d.text((72,139),'Commissioned LTE routing; not a live gateway screenshot',font=rf(35),fill='#4D6471')
def box(x,y,w,h,h1,h2,fill):
 d.rounded_rectangle((x,y,x+w,y+h),radius=20,fill=fill,outline=tel,width=4)
 d.text((x+24,y+22),h1,font=bf(34),fill=nav)
 d.text((x+24,y+87),h2,font=rf(29),fill='#385666')
def arrow(x0,y0,x1,y1,c=tel):
 d.line((x0,y0,x1,y1),fill=c,width=7)
 d.polygon([(x1,y1),(x1-24,y1-13),(x1-24,y1+13)],fill=c)
box(72,260,465,182,'LOCAL MQTT','127.0.0.1:1883 · QoS 1','#E9F6F6')
box(648,260,477,182,'SIM7600 → wwan0','DITO 4G · health metric 10','#E9F6F6')
box(1250,260,421,182,'CLOUD MQTT',':8883 · two bridges','#E9F6F6')
arrow(540,351,645,351);arrow(1130,351,1245,351)
d.rounded_rectangle((95,525,1675,711),radius=19,fill='#FFF7ED',outline=warn,width=4)
d.text((143,554),'MANAGEMENT ETHERNET: br-lan 192.168.20.11/24',font=bf(42),fill=nav)
d.text((143,618),'SSH / LuCI only. Never route production MQTT through RJ45.',font=rf(36),fill=warn)
d.rounded_rectangle((96,754,1672,885),radius=18,fill='#F1F5F9',outline=tel,width=4)
d.text((142,777),'LTE down? Keep loopback Mosquitto + gateway journal.',font=bf(33),fill=nav)
d.text((142,822),'Do not delete queued uplinks, evidence or change the network default.',font=rf(32),fill=nav)
q=p/'lte-route-exact-project.png';im.save(q,optimize=True)
print('CREATED',q.stat().st_size)
