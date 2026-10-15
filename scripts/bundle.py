"""GitHub Release backups: deduplicated files, bounded ZIP parts, verified restore."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPO = 'sunjinhui0902/scys_jh'
MANIFEST = ROOT / 'config/bundle-manifest.json'
CHUNK = 256 * 1024 * 1024
PART = 512 * 1024 * 1024
MEDIA = {'.mp4','.mov','.mkv','.webm','.avi','.m4v','.mp3','.wav','.flac','.jpg','.jpeg','.png','.webp','.ttf','.ttc','.exe','.dll','.zip','.pt','.bin','.db'}
SECRETS = {'config.yaml','settings.json','hardware_fingerprint.json','auth.json','token.json'}
SKIP_DIRS = {'.git','.venv','venv','node_modules','__pycache__','.local','.bundle-cache'}


def digest(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(4*1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def gh(*args, capture=False):
    p = subprocess.run(['gh', *map(str,args)], capture_output=capture, text=True, encoding='utf-8', errors='replace')
    if p.returncode:
        raise RuntimeError(p.stderr if capture else f'GitHub operation failed: {args[0]}')
    return p.stdout


def assert_repository():
    info = json.loads(gh('repo','view',REPO,'--json','visibility,nameWithOwner',capture=True))
    if info.get('visibility') != 'PUBLIC' or info['nameWithOwner'] != REPO:
        raise RuntimeError('Repository identity/visibility differs from the user-authorized public repository')


def excluded(p):
    n=p.name.lower()
    rel=p.relative_to(ROOT)
    vendor_runtime = rel.parts[:2] == ('00_对标与采集工具','DouK-Downloader')
    if vendor_runtime and n == 'cacert.pem':
        data=p.read_bytes()
        return b'PRIVATE KEY' in data or b'BEGIN CERTIFICATE' not in data
    if n.endswith('.pyc'):return not vendor_runtime
    if rel.parts[0]=='00_对标与采集工具' and ('downloads' in rel.parts or '视频号下载成果' in rel.parts):return True
    if rel.parts[0]=='竞品视频分析_2026-10-15':
        if len(rel.parts)>1 and rel.parts[1]=='models':return True
        if p.suffix.lower() in {'.wav','.mp3','.flac'}:return True
    return (n in SECRETS or n.endswith(('.log','.db-wal','.db-shm','.pem','.key','.crt','.cer','.p12','.pfx'))
            or 'cookie' in n or ('auth' in n and 'qr' in n) or n == 'feishu-config-qr.png')


def group_for(rel):
    parts=rel.parts
    if parts[0]=='00_对标与采集工具':
        if 'downloads' in parts or '视频号下载成果' in parts:
            return 'reference'
        if len(parts)>1 and parts[1]=='DouK-Downloader': return 'software'
        if len(parts)>1 and parts[1]=='wx_channel' and not (rel.name=='README.md' or 'docs' in parts): return 'software'
    if parts[0]=='竞品视频分析_2026-10-15':
        if len(parts)>1 and parts[1]=='tools':return 'software'
        if len(parts)>1 and parts[1]=='models':return 'models'
        if rel.suffix.lower() in MEDIA:return 'analysis'
    if rel.suffix.lower() in MEDIA:return 'core'
    return None


def walk():
    for d,dirs,files in os.walk(ROOT,followlinks=False):
        dirs[:]=sorted(x for x in dirs if x not in SKIP_DIRS and not (Path(d)/x).is_junction() and not (Path(d)/x).is_symlink())
        for n in sorted(files):
            p=Path(d)/n
            if not p.is_symlink():yield p


def upload_one(tag,p):
    for attempt in range(4):
        try:
            gh('release','upload',tag,p,'--repo',REPO)
            print('UPLOADED',p.name,flush=True)
            return
        except RuntimeError:
            # An interrupted response can hide a completed upload. Accept only the same digest.
            data=json.loads(gh('release','view',tag,'--repo',REPO,'--json','assets',capture=True))
            remote=next((x for x in data['assets'] if x['name']==p.name),None)
            if remote:
                rd=remote.get('digest')
                if rd=='sha256:'+digest(p):return
                raise RuntimeError(f'Existing asset cannot be safely replaced: {p.name}')
            if attempt==3:raise
            time.sleep(2**attempt)


def pack(a):
    assert_repository() if a.upload else None
    if a.upload:
        # Never reuse a release tag: old manifests must remain reproducible.
        exists=subprocess.run(['gh','release','view',a.tag,'--repo',REPO],capture_output=True).returncode==0
        if exists:raise RuntimeError('Choose a new release tag; existing releases are immutable backups')
        gh('release','create',a.tag,'--repo',REPO,'--draft','--title',a.tag,'--notes','个人工作台恢复包，文件映射与 SHA-256 见同版本代码的 config/bundle-manifest.json。')
    cache=ROOT/'.bundle-cache'/a.tag
    cache.mkdir(parents=True,exist_ok=True)
    m={'version':1,'repository':REPO,'tag':a.tag,'created_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'files':[],'blobs':{},'archives':[],'excluded':[]}
    files=[]
    for p in walk():
        rel=p.relative_to(ROOT)
        if excluded(p):m['excluded'].append(rel.as_posix());continue
        g=group_for(rel)
        if g:files.append((g,p,rel))
    # Stabilize SQLite files without copying live WAL or login state.
    sources={}
    for g,p,rel in files:
        if p.suffix.lower()=='.db':
            dest=cache/('snapshot-'+hashlib.sha256(rel.as_posix().encode()).hexdigest()+'.db')
            src=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)
            tables=[x[0].lower() for x in src.execute("select name from sqlite_master where type='table'")]
            if any(any(s in t for s in ['cookie','token','session','credential','login']) for t in tables):
                src.close();m['excluded'].append(rel.as_posix());continue
            target=sqlite3.connect(dest);src.backup(target);target.close();src.close();sources[rel.as_posix()]=dest
    futures=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for group in ['core','software','analysis']:
            z=None;zp=None;index=0
            def close_archive():
                nonlocal z,zp
                if z is not None:
                    z.close()
                    info={'name':zp.name,'group':group,'size':zp.stat().st_size,'sha256':digest(zp)}
                    m['archives'].append(info)
                    print('PACKED',info['name'],info['size'],flush=True)
                    if a.upload:futures.append(pool.submit(upload_one,a.tag,zp))
                    z=None
            for g,p,rel in files:
                if g!=group or rel.as_posix() in m['excluded']:continue
                source=sources.get(rel.as_posix(),p)
                h=digest(source);size=source.stat().st_size
                m['files'].append({'path':rel.as_posix(),'size':size,'mtime_ns':p.stat().st_mtime_ns,'sha256':h,'group':g})
                key=g+':'+h
                if key in m['blobs']:continue
                parts=[];read_hash=hashlib.sha256()
                with source.open('rb') as f:
                    part_index=0
                    while True:
                        b=f.read(CHUNK)
                        if not b and (size or part_index):break
                        if z is None:
                            index+=1;zp=cache/f'{group}-{index:04d}.zip';z=zipfile.ZipFile(zp,'w',allowZip64=True)
                        entry=f'{h}/{part_index:04d}'
                        compression=zipfile.ZIP_STORED if p.suffix.lower() in {'.mp4','.mp3','.jpg','.png','.zip'} else zipfile.ZIP_DEFLATED
                        z.writestr(entry,b,compress_type=compression,compresslevel=1)
                        read_hash.update(b);parts.append({'archive':zp.name,'entry':entry,'size':len(b)})
                        part_index+=1
                        if zp.stat().st_size>=PART:close_archive()
                        if not b:break
                if read_hash.hexdigest()!=h:raise RuntimeError(f'File changed during backup: {rel}')
                m['blobs'][key]={'parts':parts}
            close_archive()
        for f in as_completed(futures):f.result()
    m['summary']={'files':len(m['files']),'unique_files':len(m['blobs']),'original_bytes':sum(f['size'] for f in m['files']),'archive_bytes':sum(f['size'] for f in m['archives'])}
    MANIFEST.parent.mkdir(exist_ok=True)
    MANIFEST.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    shutil.copyfile(MANIFEST,cache/'bundle-manifest.json')
    if a.upload:
        upload_one(a.tag,cache/'bundle-manifest.json')
        print('All assets uploaded. Commit manifest, then publish the draft release at the final commit.',flush=True)
    print(json.dumps(m['summary']),flush=True)


def safe_path(base,rel):
    p=(base/rel).resolve()
    if not p.is_relative_to(base.resolve()):raise ValueError('Unsafe path in manifest')
    return p


def restore(a):
    m=json.loads(MANIFEST.read_text(encoding='utf-8'))
    if m['repository']!=REPO:raise RuntimeError('Unexpected repository in manifest')
    groups=set(a.group or ['core','software'])
    if 'all' in groups:groups={x['group'] for x in m['archives']}
    base=Path(a.target).resolve() if a.target else ROOT
    base.mkdir(parents=True,exist_ok=True)
    cache=Path(a.cache).resolve() if a.cache else ROOT/'.bundle-cache'/m['tag']
    cache.mkdir(parents=True,exist_ok=True)
    for x in m['archives']:
        if x['group'] not in groups:continue
        p=safe_path(cache,x['name'])
        if not p.exists():
            if a.offline:raise FileNotFoundError(p)
            assert_repository()
            gh('release','download',m['tag'],'--repo',REPO,'--pattern',x['name'],'--dir',cache)
        if p.stat().st_size!=x['size'] or digest(p)!=x['sha256']:raise RuntimeError(f'Archive checksum failed: {p.name}')
    complete=0
    for x in m['files']:
        if x['group'] not in groups:continue
        dest=safe_path(base,x['path'])
        if dest.exists():
            if digest(dest)==x['sha256']:complete+=1;continue
            raise RuntimeError(f'Existing file differs; preserve it and resolve manually: {dest}')
        dest.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix='.restore-',dir=dest.parent);os.close(fd)
        try:
            with open(tmp,'wb') as out:
                for part in m['blobs'][x['group']+':'+x['sha256']]['parts']:
                    with zipfile.ZipFile(safe_path(cache,part['archive'])) as z:
                        with z.open(part['entry']) as inp:shutil.copyfileobj(inp,out,4*1024*1024)
            if Path(tmp).stat().st_size!=x['size'] or digest(tmp)!=x['sha256']:raise RuntimeError(f'File checksum failed: {dest}')
            os.replace(tmp,dest)
            if 'mtime_ns' in x:os.utime(dest,ns=(x['mtime_ns'],x['mtime_ns']))
            complete+=1
        finally:
            if Path(tmp).exists():Path(tmp).unlink()
    print(json.dumps({'restored_or_verified':complete,'groups':sorted(groups),'target':str(base)},ensure_ascii=False))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest='command',required=True)
    p=sub.add_parser('pack');p.add_argument('--tag',required=True);p.add_argument('--upload',action='store_true')
    p=sub.add_parser('restore');p.add_argument('--group',action='append',choices=['core','software','analysis','all']);p.add_argument('--target');p.add_argument('--cache');p.add_argument('--offline',action='store_true')
    a=ap.parse_args()
    pack(a) if a.command=='pack' else restore(a)


if __name__=='__main__':main()
