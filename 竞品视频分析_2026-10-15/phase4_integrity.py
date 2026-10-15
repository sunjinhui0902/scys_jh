import json, time
from pathlib import Path
from pipeline import OUTPUT_DIR as R, VIDEO_DIR, sha256, now, atomic_json

rows=[json.loads(s)for s in (R/'manifest/manifest.jsonl').read_text(encoding='utf-8').splitlines()if s]
disk={str(p)for p in VIDEO_DIR.rglob('*')if p.is_file()and p.suffix.lower()in{'.mp4','.mov','.mkv','.m4v','.avi','.webm'}}
baseline={x['source_path']for x in rows};records=[];start=time.monotonic()
for i,x in enumerate(rows,1):
    p=Path(x['source_path']);s=p.stat();h=sha256(p)
    records.append({'video_id':x['video_id'],'sha256':h,'unchanged':h==x['sha256']and s.st_size==x['size_bytes']and s.st_mtime_ns==x['mtime_ns']})
    if i%75==0:print('source hashes',i,len(rows),flush=True)
a=[]
for z in json.loads((R/'manifest/phase4_input_snapshot.json').read_text(encoding='utf-8'))['files']:
    p=Path(z['source']);a.append({'path':str(p),'unchanged':p.exists()and sha256(p)==z['sha256']and p.stat().st_mtime_ns==z['mtime_ns']})
old=json.loads((R/'manifest/phase2_source_snapshot.json').read_text(encoding='utf-8'))['database_files_metadata_only']
db={p.name:{'size_bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns}for p in VIDEO_DIR.glob('records.db*')if p.is_file()}
chunks=json.loads((R/'manifest/resume_test_before.json').read_text(encoding='utf-8'))['completed_chunks']
preserved=sum(Path(z['path']).exists()and sha256(Path(z['path']))==z['sha256']and Path(z['path']).stat().st_mtime_ns==z['mtime_ns']for z in chunks)
result={'at':now(),'status':'PASS'if disk==baseline and all(z['unchanged']for z in records)and all(z['unchanged']for z in a)and old==db else'PARTIAL','source_files':len(rows),'source_membership_matches':disk==baseline,'added_paths':sorted(disk-baseline),'missing_paths':sorted(baseline-disk),'unchanged_source_files':sum(z['unchanged']for z in records),'sources':records,'A_files':a,'A_unchanged':sum(z['unchanged']for z in a),'database_opened':False,'database_metadata_unchanged_since_phase2':old==db,'previous_ASR_completed_chunks':len(chunks),'previous_ASR_chunks_hash_mtime_unchanged':preserved,'elapsed_s':time.monotonic()-start}
atomic_json(R/'manifest/phase4_source_integrity.json',result)
print(json.dumps({k:v for k,v in result.items()if k not in ['sources','A_files']},ensure_ascii=False,indent=2))
