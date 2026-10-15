from __future__ import annotations
import concurrent.futures, hashlib, html, io, json, os, re, time, urllib.parse, urllib.request
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parent
HEADERS={'User-Agent':'CityCultureWorkshop/1.0 (source attribution and license preservation)'}
def request(url):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=HEADERS),timeout=50) as r:return r.read()
        except Exception:
            if attempt==3:raise
            time.sleep(2*(attempt+1))
def plain(value):return html.unescape(re.sub('<[^>]+>',' ',value or '')).strip()
def fetch(city):
    dest=ROOT/(city['id']+'_'+city['city']);dest.mkdir(exist_ok=True)
    if (dest/'实景来源.json').exists() and len(json.loads((dest/'实景来源.json').read_text(encoding='utf-8')))==4:return city['city']+' cached'
    params={'action':'query','format':'json','generator':'search','gsrsearch':city['query']+' filetype:bitmap','gsrnamespace':6,'gsrlimit':35,'prop':'imageinfo','iiprop':'url|size|extmetadata','iiurlwidth':1600}
    data=json.loads(request('https://commons.wikimedia.org/w/api.php?'+urllib.parse.urlencode(params)))
    pages=sorted(data.get('query',{}).get('pages',{}).values(),key=lambda p:p.get('index',999))
    records=[];seen=set()
    for p in pages:
        infos=p.get('imageinfo',[])
        if not infos:continue
        info=infos[0];meta=info.get('extmetadata',{})
        get=lambda key:plain(meta.get(key,{}).get('value',''))
        license=get('LicenseShortName')
        if not (license.startswith('CC BY') or license in ('CC0','Public domain','PDM')):continue
        if info.get('width',0)<1000 or info.get('height',0)<650:continue
        title=p['title']
        if not re.search(r'\.(jpe?g|png)$',title,re.I):continue
        if re.search(r'\b(map|drawing|plan|painting|engraving|AI.generated|illustration)\b',title,re.I):continue
        url=info.get('thumburl',info['url']).split('?')[0]
        try:
            raw=request(url)
            im=Image.open(io.BytesIO(raw));im.load()
            if min(im.size)<650:continue
            digest=hashlib.sha256(raw).hexdigest()
            if digest in seen:continue
            seen.add(digest)
            suffix='.png' if im.format=='PNG' else '.jpg'
            filename=f'{len(records)+1:02d}_实景'+suffix
            (dest/filename).write_bytes(raw)
            records.append({'file':filename,'commons_title':title,'description':get('ImageDescription'),'artist':get('Artist'),'credit':get('Credit'),'license':license,'license_url':get('LicenseUrl'),'source_page':info['descriptionurl'],'download_url':url,'original_url':info['url'],'dimensions':list(im.size),'sha256':digest,'modification':'未裁切、未修饰；下载图库提供的尺寸版本','date_taken':get('DateTimeOriginal')})
            print(city['city'],filename,title,flush=True)
            if len(records)==4:break
        except Exception as ex:print('SKIP',city['city'],type(ex).__name__,str(ex)[:100],flush=True)
    (dest/'实景来源.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if len(records)!=4:raise RuntimeError(city['city']+': only '+str(len(records)))
    return city['city']+' 4 photos'
def contact():
    fontpath=Path(os.environ['WINDIR'])/'Fonts'
    font=ImageFont.truetype(str(fontpath/'msyh.ttc'),20)
    cities=json.loads((ROOT/'城市内容.json').read_text(encoding='utf-8'))
    for start in (0,5,10):
        subset=cities[start:start+5];sheet=Image.new('RGB',(1400,5*220),'#f2f0e9');draw=ImageDraw.Draw(sheet)
        for row,c in enumerate(subset):
            d=ROOT/(c['id']+'_'+c['city']);draw.text((8,row*220+5),c['city'],font=font,fill='black')
            pics=sorted(d.glob('0[1-5]_*.jpg'))+sorted(d.glob('0[1-5]_*.png'))
            pics=sorted(pics,key=lambda p:p.name)
            for col,p in enumerate(pics):
                with Image.open(p) as im:thumb=ImageOps.contain(im.convert('RGB'),(265,175))
                x=col*280+8;y=row*220+36;sheet.paste(thumb,(x,y));draw.text((x,y+176),p.stem,font=font,fill='black')
        sheet.save(ROOT/f'预览_{start//5+1:02d}.jpg',quality=88)
if __name__=='__main__':
    import sys
    if len(sys.argv)>1 and sys.argv[1]=='contact':contact()
    else:
        cities=json.loads((ROOT/'城市内容.json').read_text(encoding='utf-8'))
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            for result in pool.map(fetch,cities):print(result,flush=True)
        contact()
