"""Reproducible random pair inspection selection; judgments are recorded separately."""
import json, random
from pipeline import OUTPUT_DIR as R, atomic_json, now
from phase2_run import items

rows=items(); lookup={x['video_id']:x for x in rows}
pairs=[json.loads(z)for z in (R/'clusters/similarity_pairs.jsonl').read_text(encoding='utf-8').splitlines()if z]
chosen=random.Random(20261015).sample(pairs,min(20,len(pairs)))
for kind in ['FULL_TEXT','OPENING','STORY_PASSAGE']:
    if not any(kind in p['kinds']for p in chosen):
        extra=next((p for p in pairs if kind in p['kinds']),None)
        if extra:chosen.append(extra)
if not any(p['cross_account']for p in chosen):
    extra=next((p for p in pairs if p['cross_account']),None)
    if extra:chosen.append(extra)
for account in sorted({lookup[p['left']]['account']for p in pairs}):
    if not any(lookup[p['left']]['account']==account for p in chosen):
        chosen.append(max((p for p in pairs if lookup[p['left']]['account']==account),key=lambda p:p['full_cosine']))
for i,p in enumerate(chosen,1):
    p['review_number']=i
    for side in ['left','right']:
        v=p[side];p[side+'_account']=lookup[v]['account'];p[side+'_title']=(lookup[v].get('db')or{}).get('title')or lookup[v]['source_path'];t=(R/'transcripts'/f'{v}.txt').read_text(encoding='utf-8').strip();p[side+'_opening']=t[:220];p[side+'_ending']=t[-240:]
atomic_json(R/'manifest/similarity_review_selection.json',{'at':now(),'random_seed':20261015,'random_pairs':min(20,len(pairs)),'additional_coverage_pairs':len(chosen)-min(20,len(pairs)),'total_population':len(pairs),'pairs':chosen})
print(json.dumps({'random_pairs':min(20,len(pairs)),'total_selected':len(chosen),'population':len(pairs),'selection_path':str(R/'manifest/similarity_review_selection.json')},ensure_ascii=False))
