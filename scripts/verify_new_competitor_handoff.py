"""Independent input Schema, coverage, frame, source and final handoff checks."""
from __future__ import annotations
import argparse, collections, datetime as dt, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'竞品视频分析_2026-10-15';BATCH='new_accounts_2026-10-16';B=R/'increments'/BATCH;H=R/'handoff'/BATCH
sys.path.insert(0,str(ROOT/'.local/schema-validation'));sys.path.insert(0,str(R))
from jsonschema import Draft202012Validator, FormatChecker
from PIL import Image, ImageDraw, ImageFont
from pipeline import sha256 as file_sha256,atomic_json,atomic_text,now
def sha256(p):return file_sha256(Path(p))
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def rows(p):return [json.loads(z) for z in Path(p).read_text(encoding='utf-8').splitlines() if z]
def fingerprint(p):
    p=Path(p);s=p.stat();return {'path':str(p),'sha256':sha256(p),'size_bytes':s.st_size,'mtime_ns':s.st_mtime_ns}

def integrity():
    sources=rows(R/'manifest/manifest.jsonl')+rows(B/'manifest/manifest.jsonl');passed=[];failed=[]
    for i,x in enumerate(sources,1):
        p=Path(x['source_path']);s=p.stat()
        if s.st_size==x['size_bytes'] and s.st_mtime_ns==x['mtime_ns'] and sha256(p)==x['sha256']:passed.append(x['video_id'])
        else:failed.append(x['video_id'])
        if i%100==0:print('SOURCE_HASH_CHECK',i,len(sources),flush=True)
    expected={Path(x['source_path']).resolve() for x in sources}
    source=ROOT/'00_对标与采集工具/wx_channel/downloads'
    actual={p.resolve() for a in {x['account'] for x in sources} for p in (source/a).rglob('*') if p.is_file() and p.suffix.lower() in {'.mp4','.mov','.m4v','.mkv','.avi','.webm'}}
    db={p.name:{'size_bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns,'sha256':sha256(p)} for p in source.glob('records.db*') if p.is_file()}
    before=read(B/'manifest/database_before.json')['files'];frozen=read(B/'manifest/historical_evidence_before.json');historical=[]
    for ref in frozen:
        if ref['path'].endswith('阅见生活_竞品视频分析_终版.xlsx'):continue
        historical.append({'path':ref['path'],'unchanged':fingerprint(ref['path'])==ref})
    result={'at':now(),'status':'PASS' if not failed and expected==actual and all(x['unchanged'] for x in historical) and db==before else 'PARTIAL',
        'sources_checked':len(sources),'source_sha_size_mtime_unchanged':len(passed),'changed_video_ids':failed,'directory_membership_matches':expected==actual,
        'historical_A_and_manifests_unchanged':sum(x['unchanged'] for x in historical),'historical_files_checked':len(historical),
        'database_opened':False,'database_files_fingerprint_unchanged':db==before,'database_before':before,'database_after':db,
        'database_note':'WAL非空，本轮不重新打开或复制SQLite；只对文件指纹进行只读检查。变化时不得归因于本轮或宣称不变。'}
    atomic_json(B/'manifest/source_integrity.json',result);assert not failed and expected==actual and all(x['unchanged'] for x in historical),result
    print(json.dumps({k:v for k,v in result.items() if k not in ['database_before','database_after']},ensure_ascii=False),flush=True)

def quality():
    new=rows(B/'manifest/manifest.jsonl');validator=Draft202012Validator(read(H/'input_schema.json'),format_checker=FormatChecker())
    records={x['video_id']:x for x in read(H/'batch_plan.json')['records']};frames=0;units=0;issues=[]
    content_issues=read(B/'manifest/local_review_issues.json');risk_ids={z['video_id']+z['type'] for z in content_issues}
    for x in new:
        v=x['video_id'];obj=read(H/'video_inputs'/f'{v}.json');validator.validate(obj)
        parsed=dt.datetime.fromisoformat(obj['ready_at']);assert parsed.tzinfo is not None
        assert obj['video_id']==v and obj['account']==x['account'] and obj['source_sha256']==x['sha256']
        assert obj['source_video_path']==x['source_path'] and obj['duration_s']==x['duration_s']
        text=(B/'transcripts'/f'{v}.txt').read_text(encoding='utf-8').strip();aligned=read(B/'segments'/f'{v}.aligned.json')
        ss=aligned['segments'];assert ''.join(s['text'] for s in ss)==text and text
        assert all(0<=s['start_ms']<=s['end_ms']<=(x['duration_s']+2)*1000 for s in ss)
        refs=records[v]['text_units'];reconstructed=[]
        for unit in refs:
            assert sha256(unit['path'])==unit['sha256'];assert sha256(unit['text_path'])==unit['text_sha256']
            data=read(unit['path']);reconstructed+=data['segments'];units+=1
        assert ''.join(s['text'] for s in reconstructed)==text
        assert [s['segment_id'] for s in reconstructed]==[f's{i+1:06d}' for i in range(len(ss))]
        for frame in obj['frames']:
            assert 0<=frame['time_s']<x['duration_s']
            with Image.open(frame['path']) as im:im.verify()
            with Image.open(frame['path']) as im:assert im.width>10 and im.height>10
            frames+=1
        density=len(text)/x['duration_s']
        if density<1 or density>12:issues.append({'video_id':v,'issue':'ASR_DENSITY_REVIEW','chars_per_s':density})
        for kind,condition,note in [
            ('UNVERIFIED_CELEBRITY_DEATH',any(z in text[:400] for z in ['尤本昌','游本昌']) and any(z in text[:400] for z in ['离世','去世']),
             '素材含游本昌逝世叙事，本项目未核事实真伪；不可作为原创事实。帧中文字为游本昌/补拙记，ASR有同音异字，引用仍保留原ASR'),
            ('ASR_PROPER_NAME_REVIEW','中国历代政治得失' in x['title'] and any(z in text[:400] for z in ['钱目','钱木']),
             '帧内作者字样为钱穆，ASR开头有钱目/钱木等同音写法；原文不改，派生字段更正须标注帧证据，未做逐字听核')]:
            if condition and v+kind not in risk_ids:
                content_issues.append({'video_id':v,'account':x['account'],'type':kind,'issue':note,'evidence':str(B/'frames'/v/'index.json')})
                risk_ids.add(v+kind)
    selected=[]
    for account in sorted({x['account'] for x in new}):
        group=sorted([x for x in new if x['account']==account],key=lambda x:x['duration_s']);n=len(group)
        chosen=[group[round(i*(n-1)/4)] for i in range(5)]
        selected+=chosen
        canvas=Image.new('RGB',(1240,5*350),'#f2f5f8');draw=ImageDraw.Draw(canvas)
        font=ImageFont.load_default()
        for row,x in enumerate(chosen):
            ff=read(B/'frames'/x['video_id']/'index.json')
            for col,f in enumerate(ff):
                with Image.open(f['path']) as im:
                    image=im.convert('RGB');image.thumbnail((300,310));left=col*310+(300-image.width)//2;top=row*350+30
                    canvas.paste(image,(left,top));draw.text((col*310+5,row*350+5),f'{x["video_id"]} {f["time_s"]:.3f}s',fill='#172d42',font=font)
        dest=B/'reports'/f'sample_contact_{"1" if account=="失去壳的海龟" else "2"}.jpg';dest.parent.mkdir(parents=True,exist_ok=True);canvas.save(dest,quality=92)
    sample=[]
    for x in selected:
        v=x['video_id'];a=read(B/'segments'/f'{v}.aligned.json');t=(B/'transcripts'/f'{v}.txt').read_text(encoding='utf-8').strip();ss=a['segments']
        sample.append({'video_id':v,'account':x['account'],'duration_s':x['duration_s'],'chars':len(t),'first_excerpt':t[:130],
            'last_excerpt':t[-200:],'last_speech_s':max(s['end_ms'] for s in ss)/1000,
            'alignment':a['checks'],'human_word_error_rate':'NOT_MEASURED','frames_visual_review':'PENDING'})
    atomic_json(B/'manifest/sample_10_quality.json',{'at':now(),'scope':'5 per new account; duration strata; automatic checks and visual review, no word accuracy percentage','samples':sample})
    atomic_json(B/'manifest/input_qa.json',{'at':now(),'status':'PASS','input_schema_valid':len(new),'complete_transcripts_reconstructed':len(new),
        'frame_images_verified':frames,'text_units_coverage_verified':units,'density_review_issues':issues,'visual_review':'PENDING','human_asr_word_accuracy':'NOT_MEASURED'})
    atomic_json(B/'manifest/local_review_issues.json',content_issues)
    stats=read(B/'manifest/statistics_summary.json');stats['local_review_issues']=len(content_issues);atomic_json(B/'manifest/statistics_summary.json',stats)
    atomic_json(H/'local_review_issues.json',content_issues)
    plan=read(H/'batch_plan.json');plan['statistics']['local_review_issues']=len(content_issues);atomic_json(H/'batch_plan.json',plan)
    print('INPUT_QA_PASS',len(new),frames,units,flush=True)

def finalize():
    qa=read(B/'manifest/input_qa.json');book=read(B/'manifest/workbook_export.json')
    assert qa['status']=='PASS' and qa['visual_review']=='PASS' and book['visual_qa']=='PASS'
    assert read(B/'manifest/resume_test_result.json')['status']=='PASS'
    sources=read(B/'manifest/source_integrity.json');assert not sources['changed_video_ids'] and sources['directory_membership_matches']
    path=H/'READY.json'
    if path.exists():
        for f in read(path)['files']:assert sha256(f['path'])==f['sha256']
        print('HANDOFF_READY_RESUME_SKIP',flush=True);return
    prepared=read(H/'package_prepared.json');prepared.update(ready=True,validated_at=now());atomic_json(H/'package_prepared.json',prepared)
    files=set(p for p in H.rglob('*') if p.is_file() and p.name!='READY.json' and not p.name.endswith('.tmp'))
    for x in rows(B/'manifest/manifest.jsonl'):
        v=x['video_id'];local=B/'handoff'/v/'READY.json';files.add(local);files.add(B/'frames'/v/'index.json')
        for f in read(local)['files']:
            assert sha256(f['path'])==f['sha256'];files.add(Path(f['path']))
    refs=[{'path':str(p),'size_bytes':p.stat().st_size,'sha256':sha256(p)} for p in sorted(files)]
    atomic_json(path,{'schema_version':'new-account-handoff-ready-1.0','batch_id':BATCH,'ready_at':now(),'files_complete':True,
        'input_schema_passed':True,'text_units_coverage_passed':True,'files':refs,'video_count':83,
        'cloud_scope':'approved text and static frames only; no original video/audio upload','original_video_upload_performed':False,
        'text_semantic_verified':0,'deep_verified':0,'ai_status':'AI_PENDING','source_integrity_status':sources['status'],
        'database_fingerprint_caveat':'本轮未打开数据库；WAL/SHM变化原因未确认，见本批不变性记录'})
    print('HANDOFF_READY',len(refs),'files',flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['integrity','quality','finalize']);a=ap.parse_args()
    {'integrity':integrity,'quality':quality,'finalize':finalize}[a.command]()
