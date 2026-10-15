import json, time, hashlib, re, difflib
from pathlib import Path
from pipeline import OUTPUT_DIR as R, atomic_json, now
from align_segments import token_spans

def norm(t):return ''.join(c.lower() for c in str(t)if c.isalnum())
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    rows=[json.loads(s)for s in (R/'manifest/manifest.jsonl').read_text(encoding='utf-8').splitlines()if s];lookup={x['video_id']:x for x in rows}
    expected={c['video_id']for c in read(R/'clusters/deep_candidates.json')};out=R/'manifest/phase4_input_snapshot';out.mkdir(exist_ok=True)
    snap=[]
    for p in sorted((R/'analysis_a').iterdir()):
        if not p.is_file()or p.suffix not in ['.json','.md']:continue
        a=p.stat();raw=p.read_bytes();time.sleep(.02);b=p.stat();assert (a.st_size,a.st_mtime_ns)==(b.st_size,b.st_mtime_ns),'A input still changing'
        target=out/p.name
        if not target.exists()or target.read_bytes()!=raw:target.write_bytes(raw)
        snap.append({'source':str(p),'snapshot':str(target),'sha256':hashlib.sha256(raw).hexdigest(),'size_bytes':a.st_size,'mtime_ns':a.st_mtime_ns})
    atomic_json(R/'manifest/phase4_input_snapshot.json',{'at':now(),'files':snap,'source_read_only':True,'landing_contract':'User confirmed complete; only final filenames read; stable stat/bytes snapshot, no temporary files imported'})
    records=[]
    for p in sorted(out.glob('v_*.json')):
        d=read(p);v=d.get('video_id');x=lookup.get(v);errors=[]
        for k in ['schema_version','video_id','input_mode','analyzed_at','fields','evidence','limitations','status']:
            if k not in d:errors.append('MISSING_'+k)
        if not x or p.stem!=v:errors.append('IDENTITY')
        if not x:continue
        if d.get('account')!=x['account']or d.get('source_video_path')!=x['source_path']:errors.append('SOURCE_IDENTITY')
        f=d.get('fields',{});t=(R/'transcripts'/f'{v}.txt').read_text(encoding='utf-8').strip();raw=read(R/'segments'/f'{v}.json');ss=token_spans(t)
        if len(ss)!=len(raw['raw_timestamp']):ss=token_spans(t,True)
        localhook=''.join(z[2]for z,ts in zip(ss,raw['raw_timestamp'])if ts[0]<3000)
        rec={'video_id':v,'account':x['account'],'mode':d.get('input_mode'),'schema_errors':errors,'theme':f.get('theme'),'books':f.get('mentioned_books'),'recommended':f.get('recommended_book'),'hook_A':f.get('hook',{}).get('text_0_3s'),'hook_local':localhook,'hook_times':f.get('hook',{}).get('time_range_0_3s',f.get('hook',{}).get('time_range')),'visual':f.get('visual_and_audio',{}),'evidence':d.get('evidence')}
        al=read(R/'segments'/f'{v}.aligned.json')['segments']
        for kind in ['bridge','cta']:
            z=f.get(kind,{});a=z.get('start_time_s');b=z.get('end_time_s');q=z.get('text','');window=''.join(s['text']for s in al if isinstance(a,(int,float))and isinstance(b,(int,float))and s['end_ms']/1000>=a-1 and s['start_ms']/1000<=b+1)
            matcher=difflib.SequenceMatcher(None,norm(q),norm(window),autojunk=False);coverage=sum(bl.size for bl in matcher.get_matching_blocks())/max(len(norm(q)),1)
            rec[kind]={'present':z.get('has_'+kind),'start':a,'end':b,'quote':q,'window':window,'quote_coverage_in_window':round(coverage,3)}
        records.append(rec)
    actual={r['video_id']for r in records}
    atomic_json(R/'manifest/phase4_initial_inspection.json',{'at':now(),'expected':sorted(expected),'actual':sorted(actual),'missing':sorted(expected-actual),'unexpected':sorted(actual-expected),'records':records})
    print(json.dumps({'files':len(records),'missing':sorted(expected-actual),'unexpected':sorted(actual-expected)},ensure_ascii=False))
    for r in records:print(json.dumps({k:v for k,v in r.items()if k not in ['visual','evidence']},ensure_ascii=False))
if __name__=='__main__':main()
