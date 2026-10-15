"""Record and verify an actual stopped-worker restart without altering checkpoints."""
from pathlib import Path
import hashlib, json, sys, datetime as dt
ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'竞品视频分析_2026-10-15'/'increments'/'new_accounts_2026-10-16'
def now():return dt.datetime.now().astimezone().isoformat(timespec='seconds')
def fingerprint(p):
    return {'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'mtime_ns':p.stat().st_mtime_ns,'size_bytes':p.stat().st_size}
target=B/'manifest/resume_test_before.json'
if sys.argv[1]=='before':
    if target.exists():raise SystemExit('Test already recorded; do not stop another worker')
    state=json.loads((B/'state/worker_0.json').read_text(encoding='utf-8'))
    current=list((B/'chunks'/state['video_id']).glob('[0-9][0-9][0-9].json'))
    assert current,'Wait for at least one completed chunk'
    paths=list((B/'chunks').glob('*/*.json'))+list((B/'handoff').glob('*/READY.json'))+list((B/'transcripts').glob('*.txt'))+list((B/'segments').glob('*.json'))
    target.write_text(json.dumps({'at':now(),'worker':state,'active_completed_chunks':len(current),'files':[fingerprint(p) for p in paths]},ensure_ascii=False,indent=2),encoding='utf-8')
    print('SNAPSHOT_OK',state['pid'],state['video_id'],len(current),len(paths))
else:
    obj=json.loads(target.read_text(encoding='utf-8'));checks=[]
    for f in obj['files']:
        current=fingerprint(ROOT/f['path']);assert current==f,f['path'];checks.append(f['path'])
    v=obj['worker']['video_id'];assert (B/'handoff'/v/'READY.json').exists(),'Active video not yet finished after restart'
    (B/'manifest/resume_test_result.json').write_text(json.dumps({'status':'PASS','verified_at':now(),'files_sha_size_mtime_preserved':len(checks),
        'interrupted_video_id':v,'completed_chunks_before_stop':obj['active_completed_chunks'],'active_video_ready_after_restart':True,
        'test_scope':'actual worker termination and new worker invocation; completed chunk/result reuse verified; power-loss during atomic rename not simulated'},ensure_ascii=False,indent=2),encoding='utf-8')
    print('RESUME_PASS',len(checks),v)
