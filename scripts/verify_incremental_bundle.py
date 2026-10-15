"""Bounded local archive regression: old/new release references and byte restore."""
import argparse, hashlib, importlib.util, json, shutil, tempfile, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('bundle_under_test',ROOT/'scripts/bundle.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
base=Path(tempfile.mkdtemp(prefix='incremental-bundle-',dir=ROOT/'.local')).resolve()
assert base.is_relative_to((ROOT/'.local').resolve())
module.ROOT=base;module.MANIFEST=base/'config/bundle-manifest.json';module.MANIFEST.parent.mkdir()
oldpath=base/'竞品视频分析_2026-10-15/frames/old.jpg';oldpath.parent.mkdir(parents=True);oldpath.write_bytes(b'old image bytes')
prefix='竞品视频分析_2026-10-15/increments/test/frames'
newpath=base/prefix/'new.jpg';newpath.parent.mkdir(parents=True);newpath.write_bytes(b'new image bytes')
oldhash=module.digest(oldpath);oldcache=base/'.bundle-cache/old-release';oldcache.mkdir(parents=True)
archive=oldcache/'analysis-0001.zip'
with zipfile.ZipFile(archive,'w') as z:z.writestr(oldhash+'/0000',oldpath.read_bytes())
old={'version':1,'repository':module.REPO,'tag':'old-release','files':[{'path':oldpath.relative_to(base).as_posix(),'size':oldpath.stat().st_size,'sha256':oldhash,'group':'analysis'}],
    'blobs':{'analysis:'+oldhash:{'parts':[{'archive':archive.name,'entry':oldhash+'/0000','size':oldpath.stat().st_size}]}},
    'archives':[{'name':archive.name,'group':'analysis','size':archive.stat().st_size,'sha256':module.digest(archive)}],'excluded':[]}
module.MANIFEST.write_text(json.dumps(old),encoding='utf-8');before=module.digest(archive)
module.pack(argparse.Namespace(tag='new-release',upload=False,incremental_prefix=prefix))
current=json.loads(module.MANIFEST.read_text(encoding='utf-8'))
assert current['archives'][0]['release_tag']=='old-release' and module.digest(archive)==before
assert current['files'][0]==old['files'][0] and current['blobs']['analysis:'+oldhash]==old['blobs']['analysis:'+oldhash]
downloads=[]
def fake_gh(*args,**kwargs):
    assert args[:2]==('release','download')
    tag=args[2];name=args[args.index('--pattern')+1];dest=Path(args[args.index('--dir')+1]);dest.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(base/'.bundle-cache'/tag/name,dest/name);downloads.append((tag,name))
module.gh=fake_gh;module.assert_repository=lambda:None
module.restore(argparse.Namespace(group=['analysis'],target=str(base/'restored'),cache=str(base/'restore-cache'),offline=False))
assert (base/'restored'/oldpath.relative_to(base)).read_bytes()==oldpath.read_bytes()
assert (base/'restored'/newpath.relative_to(base)).read_bytes()==newpath.read_bytes()
assert {x[0] for x in downloads}=={'old-release','new-release'}
result={'status':'PASS','network_calls':0,'old_archive_bytes_unchanged':True,'old_manifest_file_and_blob_preserved':True,
    'restored_old_and_new_images_exactly':True,'release_routing':downloads,'test_directory':str(base.relative_to(ROOT))}
(ROOT/'.local/incremental_bundle_test_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
