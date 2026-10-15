"""V4 Phase 2: local, bounded, resumable processing; never opens source DB."""
from __future__ import annotations
import argparse, collections, contextlib, datetime, hashlib, json, logging, os
from pathlib import Path
import shutil, subprocess, sys, time, traceback
from pipeline import OUTPUT_DIR as R, VIDEO_DIR, atomic_json, atomic_text, now, sha256
from sample_run import process_local
from align_segments import align

def items():
    return [json.loads(s) for s in (R/'manifest/manifest.jsonl').read_text(encoding='utf-8').splitlines() if s]

def complete(x):
    v=x['video_id']; p=R/'state'/f'{v}.json'
    if not p.exists(): return False
    s=json.loads(p.read_text(encoding='utf-8'))
    ok=s.get('steps',{}).get('asr',{}).get('status')=='OK' and all((R/f).exists() for f in [f'transcripts/{v}.txt',f'segments/{v}.aligned.json',f'frames/{v}/index.json'])
    if not ok:return False
    frames=json.loads((R/'frames'/v/'index.json').read_text(encoding='utf-8'))
    return len(frames)==4 and all(Path(f['path']).is_file() and Path(f['path']).stat().st_size>0 for f in frames)

def prep(workers):
    rows=items(); paths={str(p) for p in VIDEO_DIR.rglob('*') if p.is_file() and p.suffix.lower() in {'.mp4','.mov','.mkv','.m4v','.avi','.webm'}}
    assert paths=={x['source_path'] for x in rows}, 'Source membership changed; review before processing'
    for x in rows:
        s=Path(x['source_path']).stat()
        assert s.st_size==x['size_bytes'] and s.st_mtime_ns==x['mtime_ns'], f'Source changed: {x["video_id"]}'
    groups=collections.defaultdict(list)
    for x in rows: groups[x['sha256']].append(x)
    previous_path=R/'manifest/phase2_plan.json'
    previous=json.loads(previous_path.read_text(encoding='utf-8')).get('canonical_by_video_id',{}) if previous_path.exists() else {}
    mapping={}; canonical=[]
    for digest, group in groups.items():
        prior={previous.get(x['video_id'])for x in group}
        chosen=next((x for x in group if len(prior)==1 and x['video_id'] in prior),None)
        if chosen is None:chosen=sorted(group,key=lambda x:(not complete(x),not bool(x.get('db')),x['video_id']))[0]
        canonical.append(chosen)
        for x in group: mapping[x['video_id']]=chosen['video_id']
    bins=[[] for _ in range(workers)]; loads=[0]*workers
    for x in sorted(canonical,key=lambda x:x.get('duration_s',0),reverse=True):
        w=min(range(workers),key=lambda j:loads[j]);bins[w].append(x['video_id']);loads[w]+=0 if complete(x) else x.get('duration_s',0)
    atomic_json(R/'manifest/phase2_plan.json',{'created_at':now(),'files':len(rows),'canonical_count':len(canonical),'canonical_by_video_id':mapping,'worker_ids':bins,'worker_duration_s':loads})
    db={p.name:{'size_bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in VIDEO_DIR.glob('records.db*') if p.is_file()}
    if not(R/'manifest/phase2_source_snapshot.json').exists():atomic_json(R/'manifest/phase2_source_snapshot.json',{'at':now(),'video_count':len(rows),'database_files_metadata_only':db,'database_opened':False})
    if not(R/'manifest/g1_user_confirmation.json').exists():atomic_json(R/'manifest/g1_user_confirmation.json',{'confirmed_at':now(),'source':'User message authorizing V4 Phase 2','sample_accepted':True,'phase2_authorized':True,'input_scope_confirmed_by_user':True,'scope_details_not_restated':True,'automatic_cloud_uploads_performed':False})
    return rows,mapping

def package(x):
    v=x['video_id']; sp=R/'state'/f'{v}.json';s=json.loads(sp.read_text(encoding='utf-8'))
    frames=json.loads((R/'frames'/v/'index.json').read_text(encoding='utf-8'))
    aligned=R/'segments'/f'{v}.aligned.json'; assert aligned.exists() and len(frames)==4
    root=R/'handoff'/v;root.mkdir(parents=True,exist_ok=True)
    # Do not rewrite an already complete package while A may be reading it.
    if (root/'READY.json').exists():
        s['status']='HANDOFF_READY';atomic_json(sp,s);return
    (root/'frames').mkdir(exist_ok=True);ff=[]
    for f in frames:
        dest=root/'frames'/Path(f['path']).name;shutil.copyfile(f['path'],dest);ff.append({'time_s':f['time_s'],'path':str(dest)})
    shutil.copyfile(R/'transcripts'/f'{v}.txt',root/'transcript.txt')
    atomic_text(root/'original_video.path.txt',x['source_path']+'\n')
    atomic_json(root/'input.json',{'schema_version':'1.0','video_id':v,'account':x['account'],'duration_s':x['duration_s'],'source_video_path':x['source_path'],'source_sha256':x['sha256'],'transcript_path':str(root/'transcript.txt'),'segments_path':str(aligned),'raw_segments_path':str(R/'segments'/f'{v}.json'),'frames':ff,'ready_at':now(),'input_mode_pending_verification':True,'ai_status':'AI_PENDING','source_reuse':s.get('reused_from')})
    atomic_json(root/'READY.json',{'schema_version':'1.0','video_id':v,'ready_at':now(),'files_complete':True,'user_confirmation_reference':str(R/'manifest/g1_user_confirmation.json'),'cloud_upload_performed_by_codex':False})
    s['status']='HANDOFF_READY';s['handoff_ready_at']=now();atomic_json(sp,s)

def boundaries(wav,duration):
    import soundfile as sf
    import numpy as np
    cuts=[0.0]
    while duration-cuts[-1]>360:
        target=cuts[-1]+300
        # Pick a quiet 200 ms interval around the desired boundary to avoid cutting a word.
        lo=max(cuts[-1]+270,target-10);hi=min(duration,target+10)
        data,sr=sf.read(wav,start=int(lo*16000),stop=int(hi*16000),dtype='float32')
        window=3200;n=len(data)//window
        rms=np.mean(data[:n*window].reshape(n,window)**2,axis=1) if n else np.array([1.0])
        cut=lo+(int(np.argmin(rms))+.5)*.2
        cuts.append(round(cut,3))
    cuts.append(duration);return cuts

def inference(x,model):
    import soundfile as sf
    v=x['video_id'];statepath=R/'state'/f'{v}.json';s=json.loads(statepath.read_text(encoding='utf-8'))
    wav=R/'audio'/f'{v}.wav';q=R/'chunks'/v;q.mkdir(parents=True,exist_ok=True)
    bp=q/'boundaries.json'
    if bp.exists(): cuts=json.loads(bp.read_text(encoding='utf-8'))['cuts_s']
    else:
        info=sf.info(wav);cuts=boundaries(wav,info.duration);atomic_json(bp,{'cuts_s':cuts,'method':'quiet 200 ms near each 300 s; no overlap','audio_duration_s':info.duration})
    total=time.monotonic();results=[]
    for j,(a,b) in enumerate(zip(cuts,cuts[1:])):
        cp=q/f'{j:03d}.json'
        if cp.exists(): results.append(json.loads(cp.read_text(encoding='utf-8')));continue
        error=None
        for attempt in range(1,3):
            started=time.monotonic()
            try:
                data,sr=sf.read(wav,start=round(a*16000),stop=round(b*16000),dtype='float32')
                rr=model.generate(input=data,fs=sr,batch_size_s=60,batch_size_threshold_s=30,sentence_timestamp=False,disable_pbar=True)
                raw=rr[0] if rr else {}; stamps=[[round(a*1000+t[0]),round(a*1000+t[1])] for t in raw.get('timestamp',[])]
                out={'chunk':j,'start_s':a,'end_s':b,'text':raw.get('text','') or '','timestamp':stamps,'elapsed_s':time.monotonic()-started,'attempts':attempt,'at':now()}
                atomic_json(cp,out);results.append(out);error=None;break
            except Exception as exc:
                error=str(exc);atomic_json(q/f'{j:03d}.error.json',{'at':now(),'attempt':attempt,'error':error})
        if error: raise RuntimeError(f'chunk {j} failed twice: {error}')
        s['chunk_progress']={'done':j+1,'total':len(cuts)-1,'at':now()};atomic_json(statepath,s)
    text=''.join(z['text'] for z in results);stamps=[t for z in results for t in z['timestamp']]
    atomic_text(R/'transcripts'/f'{v}.txt',text+'\n')
    atomic_json(R/'segments'/f'{v}.json',{'video_id':v,'duration_s':x['duration_s'],'sentence_info':[],'raw_timestamp':stamps,'checks':{'nonempty':bool(text.strip()),'chunk_count':len(results)},'model':'local SeACo Paraformer + FSMN VAD + CT punctuation','time_unit':'milliseconds','chunks':str(q),'generated_at':now()})
    try: aligned=align(v)
    except Exception as exc:
        # Honest coarse fallback, not invented token-to-character alignment.
        aligned={'video_id':v,'duration_s':x['duration_s'],'segments':[{'start_ms':round(z['start_s']*1000),'end_ms':round(z['end_s']*1000),'text':z['text']} for z in results if z['text']],'alignment_method':'CHUNK_LEVEL_FALLBACK','alignment_warning':str(exc),'checks':{'text_reconstructed_exactly':True,'token_count_equal':False,'timestamps_in_range':True,'timestamp_starts_monotonic':True},'generated_at':now()}
    atomic_json(R/'segments'/f'{v}.aligned.json',aligned)
    s=json.loads(statepath.read_text(encoding='utf-8'));s.setdefault('steps',{})['asr']={'status':'OK' if text.strip() else 'NO_SPEECH','elapsed_s':sum(z['elapsed_s'] for z in results),'resume_wall_s':time.monotonic()-total,'attempts':max(z['attempts'] for z in results),'at':now(),'chunks':len(results)}
    s['alignment_status']='TOKEN_ALIGNED' if aligned['checks'].get('token_count_equal') else 'CHUNK_ALIGNED'
    if 'error' in s:
        s.setdefault('failure_history',[]).append({k:s[k]for k in ['error','traceback','failed_at']if k in s})
        for k in ['error','traceback','failed_at']:s.pop(k,None)
    s['status']='LOCAL_OK' if text.strip() else 'NO_SPEECH';atomic_json(statepath,s)

def worker(index,nworkers):
    os.environ.setdefault('MODELSCOPE_CACHE',str(R/'models'));os.environ['HF_HUB_OFFLINE']='1';os.environ['MODELSCOPE_OFFLINE']='1'
    os.environ['OMP_NUM_THREADS']='4';os.environ['MKL_NUM_THREADS']='4'
    from funasr import AutoModel
    logging.getLogger().setLevel(logging.ERROR)
    root=R/'models/models'
    def mp(pattern): return str(next(root.glob(pattern+'/snapshots/master')))
    started=time.monotonic()
    model=AutoModel(model=mp('*seaco_paraformer*'),vad_model=mp('*fsmn_vad*'),punc_model=mp('*punc_ct*'),vad_kwargs={'max_single_segment_time':30000},device='cpu',ncpu=4,disable_update=True,trust_remote_code=False,disable_pbar=True)
    atomic_json(R/'state'/f'worker_{index}.json',{'status':'RUNNING','pid':os.getpid(),'started_at':now(),'model_load_s':time.monotonic()-started})
    plan=json.loads((R/'manifest/phase2_plan.json').read_text(encoding='utf-8'));lookup={x['video_id']:x for x in items()}
    for v in plan['worker_ids'][index]:
        x=lookup[v]
        if complete(x):package(x);continue
        atomic_json(R/'state'/f'worker_{index}.json',{'status':'RUNNING','pid':os.getpid(),'video_id':v,'duration_s':x['duration_s'],'at':now()})
        try:
            process_local([x],True)
            inference(x,model)
            s=json.loads((R/'state'/f'{v}.json').read_text(encoding='utf-8'))
            if s['steps']['asr']['status']=='OK':package(x)
        except Exception as exc:
            p=R/'state'/f'{v}.json';s=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {'video_id':v}
            s['status']='LOCAL_FAILED';s['error']=str(exc);s['traceback']=traceback.format_exc();s['failed_at']=now();atomic_json(p,s)
            atomic_json(R/'logs/failures'/f'{v}_{time.time_ns()}.json',s)
        print('COMPLETE',v,flush=True)
    atomic_json(R/'state'/f'worker_{index}.json',{'status':'COMPLETE','pid':os.getpid(),'at':now()})

def duplicate(x,canonical):
    v=x['video_id'];c=canonical['video_id']
    if v==c or complete(x): return
    if not complete(canonical):return
    shutil.copyfile(R/'transcripts'/f'{c}.txt',R/'transcripts'/f'{v}.txt')
    for suffix in ['.json','.aligned.json']:
        d=json.loads((R/'segments'/f'{c}{suffix}').read_text(encoding='utf-8'));d['video_id']=v;d['reused_from']=c
        if 'source_transcript' in d:d['source_transcript']=str(R/'transcripts'/f'{v}.txt')
        atomic_json(R/'segments'/f'{v}{suffix}',d)
    dest=R/'frames'/v;dest.mkdir(parents=True,exist_ok=True);ff=[]
    for f in json.loads((R/'frames'/c/'index.json').read_text(encoding='utf-8')):
        p=dest/Path(f['path']).name;shutil.copyfile(f['path'],p);ff.append({**f,'path':str(p)})
    atomic_json(dest/'index.json',ff)
    atomic_json(R/'state'/f'{v}.json',{'video_id':v,'account':x['account'],'source_path':x['source_path'],'reused_from':c,'reuse_basis':'SHA256_EXACT','status':'LOCAL_OK','steps':{'asr':{'status':'OK','elapsed_s':0,'at':now()},'audio':{'status':'REUSED','source_id':c}},'at':now()})
    package(x)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--worker',type=int);ap.add_argument('--workers',type=int,default=2);args=ap.parse_args()
    if args.worker is not None:worker(args.worker,args.workers);return
    jobpath=R/'state/phase2_job.json'
    if jobpath.exists():
        old=json.loads(jobpath.read_text(encoding='utf-8'))
        if old.get('status')=='RUNNING':
            import ctypes
            handle=ctypes.windll.kernel32.OpenProcess(0x1000,False,int(old['pid']))
            if handle:
                exitcode=ctypes.c_ulong();ctypes.windll.kernel32.GetExitCodeProcess(handle,ctypes.byref(exitcode));ctypes.windll.kernel32.CloseHandle(handle)
                if exitcode.value==259:raise RuntimeError(f'Existing confirmed-live Phase 2 process {old["pid"]}; do not start another writer')
    rows,mapping=prep(args.workers);(R/'logs').mkdir(exist_ok=True)
    started=time.monotonic();children=[]
    for i in range(args.workers):
        log=(R/'logs'/f'phase2_worker_{i}.log').open('a',encoding='utf-8')
        p=subprocess.Popen([sys.executable,str(Path(__file__)),'--worker',str(i),'--workers',str(args.workers)],stdout=log,stderr=log,cwd=str(R));children.append((p,log))
    atomic_json(R/'state/phase2_job.json',{'status':'RUNNING','pid':os.getpid(),'worker_pids':[p.pid for p,_ in children],'started_at':now()})
    while any(p.poll() is None for p,_ in children):
        done=sum(complete(x) for x in rows);print(f'PHASE2 {done}/{len(rows)} files complete; elapsed {time.monotonic()-started:.0f}s',flush=True);time.sleep(20)
    for p,log in children:log.close()
    lookup={x['video_id']:x for x in rows}
    for x in rows:duplicate(x,lookup[mapping[x['video_id']]])
    done=sum(complete(x) for x in rows)
    atomic_json(R/'state/phase2_job.json',{'status':'COMPLETE' if done==len(rows) else 'PARTIAL','pid':os.getpid(),'worker_exit_codes':[p.returncode for p,_ in children],'completed_files':done,'total_files':len(rows),'elapsed_s':time.monotonic()-started,'finished_at':now()})
    with (R/'logs/phase2_runs.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(json.loads((R/'state/phase2_job.json').read_text(encoding='utf-8')),ensure_ascii=False)+'\n')
    print('PHASE2 END',done,len(rows),flush=True)

if __name__=='__main__':main()
