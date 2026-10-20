"""Copy selected AI renders, normalize delivery size, verify and package assets."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import zipfile
from PIL import Image, ImageOps, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def copy_safe(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if sha(source) != sha(target):
            raise FileExistsError(target)
    else:
        shutil.copy2(source, target)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--generated-root', type=Path, required=True)
    ap.add_argument('--book-source-root', type=Path, required=True)
    a = ap.parse_args()
    spec = json.loads((ROOT / 'prompts.json').read_text(encoding='utf-8'))
    records = []
    for row in spec['images']:
        source = a.generated_root / row['generated_file']
        original = ROOT / 'originals_ai' / (row['id'] + '.png')
        copy_safe(source, original)
        target = ROOT / (row['id'][:3] + '_assets') / (row['id'] + '.png')
        target.parent.mkdir(exist_ok=True)
        if target.exists():
            raise FileExistsError(target)
        with Image.open(original) as im:
            original_size = im.size
            # Mechanical export sizing only; scene content was made with image_gen.
            ImageOps.fit(im.convert('RGB'), (1080, 1920), Image.Resampling.LANCZOS).save(target)
        records.append({'path':target.relative_to(ROOT).as_posix(), 'kind':'AI atmosphere',
                        'width':1080, 'height':1920, 'native_size':original_size,
                        'sha256':sha(target), 'native_sha256':sha(original)})
    book_sources = [
        ('be97b96c-e158-4c99-9f15-83e6e3f2feda','book_01','provided cover product graphic'),
        ('c8fe342a-2444-45da-8834-c88e631aed92','book_02','provided contents product graphic'),
        ('14a9b2ef-0fc6-4945-98e8-944633cb98fc','book_03','provided physical-book photograph'),
        ('6dc8f6b5-2727-40ee-8e81-08d501eda32e','book_extra_01','provided scenic product graphic'),
    ]
    for token, name, kind in book_sources:
        source = a.book_source_root / ('codex-clipboard-' + token + '.png')
        dest = ROOT / ('book_extra' if 'extra' in name else 'book_assets') / (name + '.png')
        copy_safe(source, dest)
        assert sha(source) == sha(dest)
        with Image.open(dest) as im:
            dims = im.size
        records.append({'path':dest.relative_to(ROOT).as_posix(),'kind':kind,
                        'width':dims[0],'height':dims[1],'sha256':sha(dest),
                        'unchanged_source':True})
    reuse = ['ep1_02','ep1_04','ep1_06','ep1_08','ep1_10']
    for i, name in enumerate(reuse, 1):
        src = ROOT / 'ep1_assets' / (name + '.png')
        dest = ROOT / 'ep2_reuse' / (f'flash_{i:02d}_' + name + '.png')
        copy_safe(src, dest)
        records.append({'path':dest.relative_to(ROOT).as_posix(),'kind':'reuse',
                        'source':'ep1_assets/' + name + '.png','width':1080,'height':1920,
                        'sha256':sha(dest)})
    manifest = {'date':'2026-10-20','ai_unique_count':22,'book_main_count':3,
                'book_extra_count':1,'flash_reuse_count':5,'files':records,
                'note':'AI scenes are illustrative, not site or artifact documentation. Books kept byte-identical at original size by user request.'}
    (ROOT / 'asset_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # A labeled overview is a separate review aid, never a replacement for the images.
    paths = [ROOT/r['path'] for r in records if r['kind'] != 'reuse']
    sheet = Image.new('RGB', (6*204, 5*390), '#f4f1e9')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=18)
    for i, p in enumerate(paths):
        x, y = (i % 6)*204, (i // 6)*390
        with Image.open(p) as im:
            thumb = ImageOps.contain(im.convert('RGB'),(188,344),Image.Resampling.LANCZOS)
            sheet.paste(thumb,(x+8+(188-thumb.width)//2,y+8+(344-thumb.height)//2))
        draw.text((x+8,y+358),p.stem,fill='#252525',font=font)
    sheet.save(ROOT / 'contact_sheet.jpg',quality=92)
    archive = ROOT / '大美中国_上下集图片包.zip'
    if archive.exists():
        raise FileExistsError(archive)
    include = [ROOT/r['path'] for r in records] + [ROOT/n for n in
        ['README.md','prompts.json','asset_manifest.json','contact_sheet.jpg']]
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in include:
            z.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for r in records:
            assert hashlib.sha256(z.read(r['path'])).hexdigest() == r['sha256']
    (ROOT / 'zip_sha256.txt').write_text(sha(archive)+'  '+archive.name+'\n',encoding='utf-8')
    assert len(list((ROOT/'ep1_assets').glob('ep1_*.png'))) == 11
    assert len(list((ROOT/'ep2_assets').glob('ep2_*.png'))) == 11
    assert len(list((ROOT/'book_assets').glob('book_*.png'))) == 3
    print(json.dumps({'ai':22,'book_main':3,'book_extra':1,'reused':5,
                      'zip_mb':round(archive.stat().st_size/1048576,1),
                      'zip_verified':True},ensure_ascii=False))

if __name__ == '__main__':
    main()
