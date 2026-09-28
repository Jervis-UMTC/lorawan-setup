from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json, textwrap
base=Path('lorawan-network-server-gateway/documentation/assets/live-gateway-fullpage-headless-20260922')
source=json.loads((base/'read-only-gateway-operator-output.json').read_text(encoding='utf-8'))
src=base/'04b-mqtt-forwarder-configuration.png'
im=Image.open(src).convert('RGB')
if im.width<1100 or im.height<1650: raise RuntimeError(f'MQTT original unexpectedly incomplete: {im.size}')
im.crop((0,0,im.width,1000)).save(base/'04b-mqtt-forwarder-top.png')
im.crop((0,900,im.width,im.height)).save(base/'04c-mqtt-forwarder-bottom.png')
font_file=Path('C:/Windows/Fonts/consola.ttf')
font=ImageFont.truetype(str(font_file),20) if font_file.exists() else ImageFont.load_default()
font_bold_file=Path('C:/Windows/Fonts/consolab.ttf')
bold=ImageFont.truetype(str(font_bold_file),24) if font_bold_file.exists() else font
panels={
 'lte':('Gateway-01 | QMI / LTE inspection', 'gateway-lte-readonly-output.png'),
 'mosquitto':('Gateway-01 | Mosquitto persistence / local listener','gateway-mosquitto-readonly-output.png'),
 'bridges':('Gateway-01 | MQTT bridges and cloud sockets','gateway-bridges-readonly-output.png')
}
for name,(title,file) in panels.items():
    raw=source['checks'][name]['stdout']
    lines=[line.rstrip('\r') for line in raw.splitlines() if line.strip()]
    if any('-----BEGIN' in l for l in lines): raise RuntimeError('key material in output')
    chunks=[]
    for l in lines:
        if len(l)>113:
            chunks+=textwrap.wrap(l,width=108,break_long_words=False,break_on_hyphens=False,subsequent_indent='    ')
        else:chunks.append(l)
    line_h=28
    h=max(340,min(1360,92+len(chunks)*line_h+46))
    out=Image.new('RGB',(1450,h),(20,25,35))
    d=ImageDraw.Draw(out)
    d.text((32,20),title,font=bold,fill=(237,243,250))
    d.line((32,60,1410,60),fill=(75,88,108),width=2)
    y=78
    for line in chunks:
        if y+line_h>h-28:raise RuntimeError(f'{name} overflowed pane')
        d.text((34,y),line,font=font,fill=(186,231,193) if line.startswith('--') else (228,235,244))
        y+=line_h
    out.save(base/file)
    print(file,out.size,'lines',len(chunks))
print('CROPPED_MQTT',im.size)
