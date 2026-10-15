import json,collections
from pipeline import OUTPUT_DIR as R
from phase2_run import items,complete
rows=items();plan=json.loads((R/'manifest/phase2_plan.json').read_text(encoding='utf-8'));canonical=set(plan['canonical_by_video_id'].values());lookup={x['video_id']:x for x in rows};done=[x for x in rows if complete(x)];donecanon=[lookup[v]for v in canonical if complete(lookup[v])]
seconds=sum(x['duration_s']for x in donecanon);chunks=0
for v in canonical:
    if complete(lookup[v]):continue
    for p in (R/'chunks'/v).glob('[0-9][0-9][0-9].json'):
        d=json.loads(p.read_text(encoding='utf-8'));seconds+=d['end_s']-d['start_s'];chunks+=1
failed=[];coarse=[]
for p in (R/'state').glob('v_*.json'):
    s=json.loads(p.read_text(encoding='utf-8'))
    if s.get('status')=='LOCAL_FAILED':failed.append(s.get('video_id'))
    if s.get('alignment_status')=='CHUNK_ALIGNED':coarse.append(s.get('video_id'))
print(json.dumps({'completed_paths':len(done),'canonical_completed':len(donecanon),'processed_audio_hours_including_saved_chunks':round(seconds/3600,2),'total_unique_audio_hours':round(sum(lookup[v]['duration_s']for v in canonical)/3600,2),'current_saved_chunks':chunks,'failed':failed,'coarse_alignments':coarse},ensure_ascii=False))
