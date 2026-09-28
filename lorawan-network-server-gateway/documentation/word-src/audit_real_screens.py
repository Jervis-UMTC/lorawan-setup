from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
root=Path('lorawan-network-server-gateway/documentation/assets/live-gateway-20260922')
fs=sorted(root.glob('*.png'))
w=800; h=560
sheet=Image.new('RGB',(w*2,h*((len(fs)+1)//2)),'white')
d=ImageDraw.Draw(sheet)
for i,f in enumerate(fs):
 im=Image.open(f).convert('RGB')
 im.thumbnail((w-20,h-58))
 x=(i%2)*w+10;y=(i//2)*h+25
 sheet.paste(im,(x,y))
 d.text((x,y-19),f.name,fill='black')
 print(f.name,Image.open(f).size,f.stat().st_size)
sheet.save(root/'00-contact-sheet-qa.jpg',quality=86)
