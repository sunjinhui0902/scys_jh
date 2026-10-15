"""Incremental local processing. Never writes into source directories or old batches."""
from __future__ import annotations
import argparse, collections, datetime as dt, hashlib, json, logging, os
from pathlib import Path
import shutil, subprocess, sys, time, traceback

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / '竞品视频分析_2026-10-15'
BATCH = 'new_accounts_2026-10-16'
B = R / 'increments' / BATCH
SOURCE = ROOT / '00_对标与采集工具' / 'wx_channel' / 'downloads'
ACCOUNTS = ['失去壳的海龟', '闲不住De宝']
sys.path.insert(0, str(R))
import pipeline
pipeline.OUTPUT_DIR = B
import sample_run, align_segments, phase2_run
sample_run.OUTPUT_DIR = B
align_segments.OUTPUT_DIR = B
phase2_run.R = B

def now():
    return dt.datetime.now().astimezone().isoformat(timespec='seconds')

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def rows(p):
    return [json.loads(x) for x in Path(p).read_text(encoding='utf-8').splitlines() if x]

atomic_json, atomic_text, sha = pipeline.atomic_json, pipeline.atomic_text, pipeline.sha256

def update_job(**fields):
    p = R / 'manifest' / f'{BATCH}_job.json'
    obj = read(p); obj.update(fields); obj['updated_at'] = now(); atomic_json(p, obj)

def completed(v, root=B):
    try:
        s=read(root/'state'/f'{v}.json')
        ff=read(root/'frames'/v/'index.json')
        a=read(root/'segments'/f'{v}.aligned.json')
        text=(root/'transcripts'/f'{v}.txt').read_text(encoding='utf-8').strip()
        return (s.get('steps',{}).get('asr',{}).get('status')=='OK' and bool(text)
                and len(ff)==4 and all(Path(f['path']).is_file() for f in ff)
                and ''.join(z['text'] for z in a['segments'])==text
                and a.get('checks',{}).get('timestamps_in_range',False))
    except (OSError, ValueError, KeyError): return False

def materialize(x, canonical, canonical_root):
    v,c=x['video_id'],canonical['video_id']
    if completed(v): return
    if not completed(c, canonical_root): return
    (B/'transcripts').mkdir(parents=True,exist_ok=True)
    shutil.copyfile(canonical_root/'transcripts'/f'{c}.txt', B/'transcripts'/f'{v}.txt')
    for suffix in ['.json','.aligned.json']:
        obj=read(canonical_root/'segments'/f'{c}{suffix}');obj['video_id']=v;obj['reused_from']=c
        if 'source_transcript' in obj:obj['source_transcript']=str(B/'transcripts'/f'{v}.txt')
        if 'source_raw_segments' in obj:obj['source_raw_segments']=str(B/'segments'/f'{v}.json')
        atomic_json(B/'segments'/f'{v}{suffix}',obj)
    ff=[]
    for frame in read(canonical_root/'frames'/c/'index.json'):
        dest=B/'frames'/v/Path(frame['path']).name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(frame['path'],dest);ff.append({**frame,'path':str(dest)})
    atomic_json(B/'frames'/v/'index.json',ff)
    atomic_json(B/'state'/f'{v}.json',{'video_id':v,'source_path':x['source_path'],'account':x['account'],
        'started_at':now(),'status':'LOCAL_OK','reused_from':c,'reuse_source_root':str(canonical_root),
        'steps':{'asr':{'status':'OK','elapsed_s':0,'at':now(),'mode':'SHA256_IDENTICAL_REUSE'}},
        'alignment_status':read(B/'segments'/f'{v}.aligned.json').get('alignment_method')})

def inventory():
    if (B/'manifest'/'inventory_complete.json').exists():
        print('INVENTORY_RESUME_SKIP',flush=True);return
    current=dt.datetime.now(dt.timezone.utc)
    assert current >= dt.datetime.fromisoformat('2026-10-16T03:10:00+08:00'), 'Not before authorized time'
    update_job(status='LOCAL_RUNNING',basic_processing_started_at=now(),trigger_received_at='2026-10-16T03:10:15+08:00')
    started=time.monotonic(); old=rows(R/'manifest/manifest.jsonl');by_sha=collections.defaultdict(list)
    for x in old:by_sha[x['sha256']].append(x)
    old_plan=read(R/'manifest/phase2_plan.json')['canonical_by_video_id']
    frozen=[]
    for p in [R/'manifest/manifest.jsonl',R/'manifest/phase2_plan.json',R/'阅见生活_竞品视频分析_终版.xlsx',*sorted((R/'analysis_a').rglob('*.json')),*sorted((R/'analysis_a').rglob('*.md'))]:
        frozen.append({'path':str(p),'sha256':sha(p),'size_bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns})
    atomic_json(B/'manifest'/'historical_evidence_before.json',frozen)
    db={p.name:{'size_bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns,'sha256':sha(p)} for p in SOURCE.glob('records.db*') if p.is_file()}
    atomic_json(B/'manifest'/'database_before.json',{'at':now(),'database_opened':False,'files':db})
    sources=sorted((p for account in ACCOUNTS for p in (SOURCE/account).rglob('*') if p.is_file() and p.suffix.lower() in pipeline.EXTS),key=lambda p:p.as_posix())
    output=[]
    cache=B/'state'/'inventory'
    for i,p in enumerate(sources,1):
        st=p.stat();rel=p.relative_to(SOURCE).as_posix();v='v_'+hashlib.sha256(rel.encode('utf-8')).hexdigest()[:16]
        assert v not in {x['video_id'] for x in old}, 'New source id collides with historical ID'
        cp=cache/f'{v}.json'
        if cp.exists() and read(cp).get('size_bytes')==st.st_size and read(cp).get('mtime_ns')==st.st_mtime_ns:
            item=read(cp)
        else:
            meta={};error=None
            if time.time()-st.st_mtime<120:error='SOURCE_RECENTLY_MODIFIED_WAIT'
            if not error:
                try:meta=pipeline.probe(p)
                except Exception as exc:error=str(exc)
            item={'video_id':v,'account':p.relative_to(SOURCE).parts[0],'source_path':str(p),'source_relative_path':rel,
                'title':p.stem,'size_bytes':st.st_size,'mtime_ns':st.st_mtime_ns,'sha256':sha(p),
                'probe_ok':not bool(error),'probe_error':error,'db':None,**meta}
            after=p.stat()
            if (after.st_size,after.st_mtime_ns)!=(st.st_size,st.st_mtime_ns):
                item['probe_ok']=False;item['probe_error']='SOURCE_CHANGED_DURING_INVENTORY'
            atomic_json(cp,item)
        output.append(item)
        if i%10==0 or i==len(sources):print('INVENTORY',i,len(sources),flush=True)
    assert len({x['video_id'] for x in output})==len(output)
    canonical={};unique={};reused=[]
    for x in output:
        if not x['probe_ok'] or not x.get('has_audio') or x.get('duration_s',0)<=0:continue
        digest=x['sha256'];old_group=by_sha.get(digest,[])
        ref=next((z for z in old_group if old_plan.get(z['video_id'])==z['video_id'] and completed(z['video_id'],R)),None)
        if ref is None:ref=next((z for z in old_group if completed(z['video_id'],R)),None)
        if ref:
            canonical[x['video_id']]={'video_id':ref['video_id'],'root':'historical','source_sha256':digest}
            materialize(x,ref,R);reused.append(x['video_id'])
        else:
            chosen=unique.setdefault(digest,x)
            canonical[x['video_id']]={'video_id':chosen['video_id'],'root':'increment','source_sha256':digest}
    bins=[[],[]];loads=[0.,0.]
    for x in sorted(unique.values(),key=lambda x:x['duration_s'],reverse=True):
        w=min(range(2),key=lambda n:loads[n]);bins[w].append(x['video_id']);loads[w]+=x['duration_s']
    atomic_text(B/'manifest'/'manifest.jsonl',''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in output))
    atomic_json(B/'manifest'/'phase2_plan.json',{'created_at':now(),'worker_ids':bins,'worker_duration_s':loads,
        'canonical_by_video_id':canonical,'historical_reused_source_ids':reused,'new_inference_count':len(unique)})
    summary={'scanned_at':now(),'source_files':len(output),'accounts':dict(collections.Counter(x['account'] for x in output)),
        'probe_valid':sum(x['probe_ok'] and x.get('duration_s',0)>0 for x in output),
        'with_audio':sum(x['probe_ok'] and x.get('has_audio',False) for x in output),
        'unique_sha256':len({x['sha256'] for x in output}),
        'duplicates_within_new':len(output)-len({x['sha256'] for x in output}),
        'historical_reused_source_count':len(reused),'new_inference_count':len(unique),
        'total_duration_s':sum(x.get('duration_s',0) for x in output),
        'new_inference_duration_s':sum(x['duration_s'] for x in unique.values()),'inventory_elapsed_s':time.monotonic()-started,
        'database_opened':False,'video_integrity_scope':'ffprobe at inventory; decoded frame checks will be performed during processing; full video stream decode not tested'}
    atomic_json(B/'manifest'/'inventory_complete.json',summary)
    update_job(inventory=summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)

def package(x):
    v=x['video_id'];p=B/'handoff'/v/'READY.json'
    if p.exists():return
    assert completed(v),v
    root=p.parent;root.mkdir(parents=True,exist_ok=True)
    ff=read(B/'frames'/v/'index.json')
    obj={'schema_version':'increment-input-1.0','video_id':v,'account':x['account'],'duration_s':x['duration_s'],
        'source_video_path':x['source_path'],'source_sha256':x['sha256'],'transcript_path':str(B/'transcripts'/f'{v}.txt'),
        'segments_path':str(B/'segments'/f'{v}.aligned.json'),'frames':ff,'ai_status':'AI_PENDING','input_mode_pending_verification':True,'ready_at':now()}
    atomic_json(root/'input.json',obj)
    files=[root/'input.json',B/'transcripts'/f'{v}.txt',B/'segments'/f'{v}.json',B/'segments'/f'{v}.aligned.json',*[Path(f['path']) for f in ff]]
    atomic_json(p,{'schema_version':'increment-ready-1.0','video_id':v,'ready_at':now(),'files_complete':True,
        'files':[{'path':str(f),'sha256':sha(f),'size_bytes':f.stat().st_size} for f in files],
        'cloud_upload_performed_by_codex':False})

def worker(index):
    os.environ['MODELSCOPE_CACHE']=str(R/'models');os.environ['HF_HUB_OFFLINE']='1';os.environ['MODELSCOPE_OFFLINE']='1'
    os.environ['OMP_NUM_THREADS']='4';os.environ['MKL_NUM_THREADS']='4'
    lookup={x['video_id']:x for x in rows(B/'manifest/manifest.jsonl')}
    todo=[lookup[v] for v in read(B/'manifest/phase2_plan.json')['worker_ids'][index] if not completed(v)]
    state=B/'state'/f'worker_{index}.json'
    if not todo:atomic_json(state,{'status':'COMPLETE','at':now(),'model_load_skipped':True});return
    from funasr import AutoModel
    logging.getLogger().setLevel(logging.ERROR)
    models=R/'models'/'models'
    def mp(glob):return str(next(models.glob(glob+'/snapshots/master')))
    t=time.monotonic()
    model=AutoModel(model=mp('*seaco_paraformer*'),vad_model=mp('*fsmn_vad*'),punc_model=mp('*punc_ct*'),
        vad_kwargs={'max_single_segment_time':30000},device='cpu',ncpu=4,disable_update=True,trust_remote_code=False,disable_pbar=True)
    atomic_json(B/'manifest'/f'worker_{index}_environment.json',{'loaded_at':now(),'model_load_s':time.monotonic()-t,
        'model':mp('*seaco_paraformer*'),'vad':mp('*fsmn_vad*'),'punc':mp('*punc_ct*'),'offline':True,'ncpu':4})
    for i,x in enumerate(todo,1):
        v=x['video_id'];started=time.monotonic()
        atomic_json(state,{'status':'RUNNING','pid':os.getpid(),'video_id':v,'index':i,'total':len(todo),'at':now()})
        try:
            stat=Path(x['source_path']).stat();assert (stat.st_size,stat.st_mtime_ns)==(x['size_bytes'],x['mtime_ns'])
            sample_run.process_local([x],True)
            phase2_run.inference(x,model)
            if completed(v):package(x)
            print('COMPLETE',v,'elapsed_s',round(time.monotonic()-started,2),flush=True)
        except Exception as exc:
            p=B/'state'/f'{v}.json';obj=read(p) if p.exists() else {'video_id':v}
            obj.update(status='LOCAL_FAILED',error=str(exc),failed_at=now(),traceback=traceback.format_exc())
            atomic_json(p,obj);print('FAILED',v,str(exc),flush=True)
    atomic_json(state,{'status':'COMPLETE','pid':os.getpid(),'at':now(),'wall_seconds':time.monotonic()-t})

def finish():
    new=rows(B/'manifest/manifest.jsonl');lookup={x['video_id']:x for x in new};plan=read(B/'manifest/phase2_plan.json')
    for x in new:
        c=plan['canonical_by_video_id'].get(x['video_id'])
        if c and c['root']=='increment' and c['video_id']!=x['video_id']:materialize(x,lookup[c['video_id']],B)
        if completed(x['video_id']):package(x)
    ready=[x for x in new if completed(x['video_id'])]
    atomic_json(B/'manifest/local_completion.json',{'at':now(),'source_count':len(new),'local_ready':len(ready),
        'ai_status':'AI_PENDING','failed_video_ids':[x['video_id'] for x in new if x not in ready],
        'frames':len(ready)*4,'reused_sources':sum(bool(read(B/'state'/f'{x["video_id"]}.json').get('reused_from')) for x in ready)})
    print(json.dumps(read(B/'manifest/local_completion.json'),ensure_ascii=False))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('command',choices=['inventory','worker','finish']);ap.add_argument('--index',type=int,default=0);args=ap.parse_args()
    if args.command=='inventory':inventory()
    elif args.command=='worker':worker(args.index)
    else:finish()
