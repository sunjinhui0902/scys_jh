"""Rebuild only coarse alignments when an exact alternative tokenization exists."""
import json
from pipeline import OUTPUT_DIR as R,atomic_json,now
from align_segments import align

def main():
    log=R/'manifest/alignment_repairs.json'
    previous=json.loads(log.read_text(encoding='utf-8')).get('results',[]) if log.exists()else[]
    results=[]
    for p in (R/'state').glob('v_*.json'):
        s=json.loads(p.read_text(encoding='utf-8'))
        if s.get('alignment_status')!='CHUNK_ALIGNED':continue
        v=s['video_id']
        try:
            a=align(v);atomic_json(R/'segments'/f'{v}.aligned.json',a);s['alignment_status']='TOKEN_ALIGNED';s['alignment_repaired_at']=now();atomic_json(p,s);results.append({'video_id':v,'status':'TOKEN_ALIGNMENT_RECOVERED','tokenization':a.get('tokenization')})
        except Exception as exc:results.append({'video_id':v,'status':'COARSE_RETAINED','reason':str(exc)})
    merged={z['video_id']:z for z in previous+results}
    atomic_json(log,{'at':now(),'results':list(merged.values())});print(json.dumps(results,ensure_ascii=False))
if __name__=='__main__':main()
