import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from pipeline import OUTPUT_DIR as R
rows=[json.loads(s)for s in (R/'manifest/manifest.jsonl').read_text(encoding='utf-8').splitlines()if s];lookup={x['video_id']:x for x in rows}
ids=[c['video_id']for c in json.loads((R/'clusters/deep_candidates.json').read_text(encoding='utf-8'))]
font=ImageFont.truetype(r'C:\Windows\Fonts\msyh.ttc',15)
out=R/'reports/phase4_visual_review';out.mkdir(exist_ok=True)
for batch in range(5):
    page=Image.new('RGB',(1120,5*530),'#eff4f8');draw=ImageDraw.Draw(page)
    for k,v in enumerate(ids[batch*5:batch*5+5]):
        y=k*530;draw.text((5,y+2),f'{batch*5+k+1}. {v}  {lookup[v]["account"]}',font=font,fill='black')
        ff=json.loads((R/'frames'/v/'index.json').read_text(encoding='utf-8'))
        for j,f in enumerate(ff):
            with Image.open(f['path'])as im:
                im=im.convert('RGB');im.thumbnail((275,485));page.paste(im,(j*280+(275-im.width)//2,y+40))
            draw.text((j*280+5,y+23),f'{f["time_s"]:.3f}s',font=font,fill='black')
    dest=out/f'contact_{batch+1}.jpg';page.save(dest,quality=90);print(dest)
