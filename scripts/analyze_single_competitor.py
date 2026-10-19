"""Prepare one explicitly requested source using the existing offline ASR stack."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / '竞品视频分析_2026-10-15'

def now():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec='seconds')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--match', required=True); ap.add_argument('--batch', required=True)
    args = ap.parse_args()
    if not args.batch.replace('_','').replace('-','').isalnum(): raise ValueError('Use a bounded batch key')
    b = R / 'increments' / args.batch
    sources = [p for p in (ROOT / '00_对标与采集工具/wx_channel/downloads').rglob('*.mp4') if args.match in p.name]
    assert len(sources) == 1, 'Expected exactly one matching source'
    source = sources[0]; started = time.monotonic()
    sys.path.insert(0, str(R)); import pipeline
    source_stat = source.stat(); digest = pipeline.sha256(source)
    time.sleep(.5); assert source.stat().st_size == source_stat.st_size and source.stat().st_mtime_ns == source_stat.st_mtime_ns
    v = 'v_' + digest[:16]
    old = [json.loads(s) for s in (R / 'manifest/current_manifest.jsonl').read_text(encoding='utf-8').splitlines() if s]
    reused = [x for x in old if x['sha256'] == digest]
    if reused:
        marker=b/'manifest/local_complete.json'
        if marker.exists() and all(z['video_id']==v for z in reused):
            previous=json.loads(marker.read_text(encoding='utf-8'))
            for ref in previous['files']:assert pipeline.sha256(Path(ref['path']))==ref['sha256']
            print('SINGLE_LOCAL_RESUME_SKIP',v,flush=True);return
        raise RuntimeError('Existing matching SHA; reuse the existing transcript instead of rerunning ASR')
    meta = pipeline.probe(source); assert meta['has_audio'] and meta['duration_s'] > 0
    row = {'video_id':v,'source_path':str(source),'account':source.parent.name,'sha256':digest,
           'size_bytes':source_stat.st_size,'mtime_ns':source_stat.st_mtime_ns,**meta,'probe_ok':True,'probe_error':None,
           'source_title':source.stem,'db':None,'canonical_video_id':v,
           'scope_note':'Only the requested file was inventoried; not a fresh inventory of all download directories.'}
    pipeline.OUTPUT_DIR = b
    import sample_run, align_segments, phase2_run
    sample_run.OUTPUT_DIR = b; align_segments.OUTPUT_DIR = b; phase2_run.R = b
    atomic = pipeline.atomic_json
    atomic(b / 'manifest/source.json', row)
    marker = b / 'manifest/local_complete.json'
    if marker.exists():
        previous = json.loads(marker.read_text(encoding='utf-8'))
        for ref in previous['files']: assert pipeline.sha256(Path(ref['path'])) == ref['sha256']
        print('SINGLE_LOCAL_RESUME_SKIP',v,flush=True); return
    os.environ.update(MODELSCOPE_CACHE=str(R/'models'),HF_HUB_OFFLINE='1',MODELSCOPE_OFFLINE='1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4')
    sample_run.process_local([row], True)
    from funasr import AutoModel
    logging.getLogger().setLevel(logging.ERROR)
    modelroot = R / 'models/models'
    def mp(pattern): return str(next(modelroot.glob(pattern+'/snapshots/master')))
    t = time.monotonic()
    model = AutoModel(model=mp('*seaco_paraformer*'),vad_model=mp('*fsmn_vad*'),punc_model=mp('*punc_ct*'),
                      vad_kwargs={'max_single_segment_time':30000},device='cpu',ncpu=4,disable_update=True,trust_remote_code=False,disable_pbar=True)
    atomic(b/'manifest/environment.json',{'at':now(),'offline':True,'model_load_s':time.monotonic()-t,
                                        'model':mp('*seaco_paraformer*'),'source_database_opened':False})
    phase2_run.inference(row,model)
    aligned_path = b/'segments'/f'{v}.aligned.json'
    aligned = json.loads(aligned_path.read_text(encoding='utf-8'))
    text = (b/'transcripts'/f'{v}.txt').read_text(encoding='utf-8').strip()
    assert ''.join(s['text'] for s in aligned['segments']) == text
    assert aligned['checks']['timestamps_in_range']
    for i,s in enumerate(aligned['segments'],1): s['segment_id']=f's{i:06d}'
    atomic(aligned_path,aligned)
    readable='\n'.join(f"[{s['segment_id']} {s['start_ms']/1000:.3f}-{s['end_ms']/1000:.3f}s] {s['text']}" for s in aligned['segments'])+'\n'
    pipeline.atomic_text(b/'transcripts'/f'{v}.timed.txt',readable)
    assert pipeline.sha256(source)==digest and source.stat().st_size==source_stat.st_size and source.stat().st_mtime_ns==source_stat.st_mtime_ns
    frames=json.loads((b/'frames'/v/'index.json').read_text(encoding='utf-8'))
    refs=[b/'manifest/source.json',b/'manifest/environment.json',b/'transcripts'/f'{v}.txt',b/'transcripts'/f'{v}.timed.txt',
          aligned_path,b/'segments'/f'{v}.json',*[Path(f['path']) for f in frames]]
    atomic(marker,{'at':now(),'video_id':v,'status':'LOCAL_READY','duration_s':meta['duration_s'],'characters':len(text),
                   'segments':len(aligned['segments']),'alignment_method':aligned['alignment_method'],'elapsed_s':time.monotonic()-started,
                   'source_fingerprint_unchanged':True,'old_global_manifest_sha256':pipeline.sha256(R/'manifest/current_manifest.jsonl'),
                   'files':[{'path':str(p),'sha256':pipeline.sha256(p),'size_bytes':p.stat().st_size} for p in refs]})
    print('SINGLE_LOCAL_READY',v,'chars',len(text),'elapsed_s',round(time.monotonic()-started,2),flush=True)

if __name__=='__main__': main()
