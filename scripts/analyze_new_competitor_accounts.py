"""Deterministic incremental text statistics and evidence-bounded A handoff."""
from __future__ import annotations
import collections, difflib, hashlib, json, re, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'竞品视频分析_2026-10-15'
BATCH='new_accounts_2026-10-16'
B=R/'increments'/BATCH
H=R/'handoff'/BATCH
sys.path.insert(0,str(R))
from pipeline import atomic_json, atomic_text, sha256, now
from phase2_analyze import comp, norm, original_excerpt

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def rows(p):return [json.loads(z) for z in Path(p).read_text(encoding='utf-8').splitlines() if z]
def txroot(v,newids):return B if v in newids else R

def main():
    start=time.monotonic();new=rows(B/'manifest/manifest.jsonl');old=rows(R/'manifest/manifest.jsonl')
    newids={x['video_id'] for x in new};lookup={x['video_id']:x for x in old+new}
    assert read(B/'manifest/local_completion.json')['local_ready']==len(new), 'Finish local processing first'
    oldplan=read(R/'manifest/phase2_plan.json')['canonical_by_video_id']
    newplan=read(B/'manifest/phase2_plan.json')['canonical_by_video_id']
    ids=sorted(set(oldplan.values())|{z['video_id'] for z in newplan.values()})
    texts={v:(txroot(v,newids)/'transcripts'/f'{v}.txt').read_text(encoding='utf-8').strip() for v in ids}
    cleans=[norm(texts[v]) for v in ids]
    from sklearn.feature_extraction.text import TfidfVectorizer
    tv=TfidfVectorizer(analyzer='char',ngram_range=(2,4),min_df=2,max_features=70000,sublinear_tf=True)
    mat=tv.fit_transform(cleans);cos=(mat@mat.T).toarray()
    hv=TfidfVectorizer(analyzer='char',ngram_range=(2,4),min_df=1,max_features=40000,sublinear_tf=True)
    hm=hv.fit_transform([s[:100] for s in cleans]);head=(hm@hm.T).toarray()
    pairs=[]
    for i,a in enumerate(ids):
        for j in range(i+1,len(ids)):
            b=ids[j]
            if a not in newids and b not in newids:continue
            f,h=float(cos[i,j]),float(head[i,j])
            if f<.38 and h<.65:continue
            lr=min(len(cleans[i]),len(cleans[j]))/max(1,max(len(cleans[i]),len(cleans[j])))
            sm=difflib.SequenceMatcher(None,cleans[i],cleans[j],autojunk=False);match=sm.find_longest_match()
            ratio=sm.ratio() if f>=.76 and lr>=.6 else None;kinds=[]
            if f>=.76 and lr>=.6 and ratio>=.65:kinds.append('FULL_TEXT')
            if h>=.8 and min(len(cleans[i]),len(cleans[j]))>=25:kinds.append('OPENING')
            if match.size>=80 and (f>=.45 or match.size/max(1,min(len(cleans[i]),len(cleans[j])))>=.3):kinds.append('STORY_PASSAGE')
            if kinds:
                pairs.append({'left':a,'right':b,'full_cosine':round(f,5),'opening_cosine':round(h,5),
                    'ordered_match_ratio':round(ratio,5) if ratio is not None else None,'length_ratio':round(lr,5),
                    'longest_common_chars':match.size,'kinds':kinds,'cross_account':lookup[a]['account']!=lookup[b]['account'],
                    'left_quote':original_excerpt(texts[a],match.a,min(match.size,160)),
                    'right_quote':original_excerpt(texts[b],match.b,min(match.size,160)),
                    'left_transcript_path':str(txroot(a,newids)/'transcripts'/f'{a}.txt'),
                    'right_transcript_path':str(txroot(b,newids)/'transcripts'/f'{b}.txt')})
    prior=rows(R/'clusters/similarity_pairs.jsonl')
    allpairs=prior+pairs;clusters=[]
    for kind,label in [('FULL_TEXT','TEXT'),('OPENING','HOOK'),('STORY_PASSAGE','PASSAGE')]:
        groups=comp([e for e in allpairs if kind in e['kinds']],label)
        for g in groups:
            g['accounts']=sorted({lookup[v]['account'] for v in g['video_ids']})
            g['new_video_ids']=sorted(set(g['video_ids'])&newids)
            g['incremental']=bool(g['new_video_ids'])
        clusters+=groups
    atomic_text(B/'clusters/incremental_similarity_pairs.jsonl',''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in pairs))
    atomic_json(B/'clusters/current_text_clusters.json',clusters)
    methodology={'at':now(),'population':len(ids),'compared_pairs':'all pairs containing at least one new SHA-canonical video',
        'old_edges':'preserved from historical 317-content corpus; no old values rewritten',
        'new_edges':'TFIDF char 2-4 grams over current 400-content corpus; no semantic inference',
        'thresholds':{'FULL_TEXT':'cosine>=0.76, length ratio>=0.6, ordered match>=0.65',
            'OPENING':'first 100 normalized chars cosine>=0.8, both>=25 chars',
            'STORY_PASSAGE':'longest contiguous normalized match>=80 and (cosine>=0.45 or match/shorter>=0.3); prefilter full cosine>=0.38 or opening cosine>=0.65'},
        'cluster_method':'connected components per kind; transitive members need not all be pairwise similar',
        'caveat':'shared passages may be introductions or CTAs; not verified same story, plagiarism, views, or conversion'}
    atomic_json(B/'clusters/methodology.json',methodology)
    known={x['term'] for x in read(R/'clusters/book_frequencies.json')}
    known|={'大美中国','365日走遍中国','故宫日历','永乐大典','中国国家地理','中国最美的100个地方','中国历史名城','中国古建筑','中国最美的100个博物馆','人一生要看的100个博物馆'}
    title_books={}
    for x in new:
        stem=Path(x['source_path']).stem
        if x['account']=='失去壳的海龟' and '｜' in stem:
            left,right=stem.split('｜',1)
            book_part=right if re.fullmatch(r'第\s*\d+\s*集',left.strip()) else left
            term=re.split('[，,。！？#、]',book_part)[0].strip('《》 ')
            if 2<=len(term)<=28:known.add(term);title_books[x['video_id']]=term
    def matches(t,term):return term in t or norm(term) in norm(t)
    previous_issues=read(B/'manifest/local_review_issues.json') if (B/'manifest/local_review_issues.json').exists() else []
    frequencies=[];features={};issues=[z for z in previous_issues if z['type'] in ['UNVERIFIED_CELEBRITY_DEATH','ASR_PROPER_NAME_REVIEW']];entities=[]
    story_terms=['奥古斯丁','海德格尔','残雪','康德','黑格尔','尼采','苏格拉底','柏拉图','亚里士多德','孔子','王阳明','福柯','陀思妥耶夫斯基','五牛图','千里江山图','清明上河图','汝窑','敦煌','故宫','三星堆','兵马俑','曾侯乙','秦始皇','乾隆','国宝','山西','古建筑']
    segments={x['video_id']:read(B/'segments'/f'{x["video_id"]}.aligned.json')['segments'] for x in new}
    for x in new:
        v=x['video_id'];t=texts[newplan[v]['video_id']];ss=segments[v]
        books=sorted(term for term in known if matches(t,term) or title_books.get(v)==term)
        rec=[s for s in ss if re.search('推荐|这本|这套|一本叫|翻到一本|书里|这部',s['text'])]
        buy=[s for s in ss if re.search('橱窗|左下角|下单|链接|购买|买一|买这|购物车|小黄车',s['text'])]
        features[v]={'book_candidates':books,'book_mention_rule':bool(books),'recommendation_rule':bool(rec),
            'shopping_prompt_rule':bool(buy),'recommendation_hits':[{'segment_id':f's{ss.index(s)+1:06d}',**s} for s in rec[:8]],
            'shopping_hits':[{'segment_id':f's{ss.index(s)+1:06d}',**s} for s in buy[:8]],
            'recommendation_count':len(rec),'shopping_count':len(buy),'title_book_candidate':title_books.get(v),
            'rule_scope':'lexical cues only; recommendation/product/SKU identity remains AI_PENDING'}
        a=read(B/'segments'/f'{v}.aligned.json');end=max((s['end_ms'] for s in ss),default=0)/1000
        if not a.get('checks',{}).get('token_count_equal'):
            issues.append({'video_id':v,'account':x['account'],'type':'CHUNK_LEVEL_ALIGNMENT','issue':'词时间戳未能精确配对，保留真实分块级时间；不得当作逐词精确时间','evidence':str(B/'segments'/f'{v}.aligned.json')})
        if x['duration_s']-end>30:
            issues.append({'video_id':v,'account':x['account'],'type':'EARLY_LAST_SPEECH_REVIEW','issue':f'末次语音时间比视频尾部早{x["duration_s"]-end:.1f}秒，可能为静音/音乐或漏识别，待听核','evidence':str(B/'segments'/f'{v}.aligned.json')})
    for term in sorted(known):
        hits=[]
        for x in new:
            v=x['video_id'];t=texts[newplan[v]['video_id']]
            if term not in features[v]['book_candidates']:continue
            evidence=next(({'segment_id':f's{i+1:06d}','start_ms':s['start_ms'],'end_ms':s['end_ms'],'quote':s['text'][:180]} for i,s in enumerate(segments[v]) if matches(s['text'],term)),None)
            hits.append({'video_id':v,'account':x['account'],'source':'ASR' if evidence else 'SOURCE_TITLE_ONLY','evidence':evidence,'title_candidate':title_books.get(v)==term})
        if hits:frequencies.append({'term':term,'new_unique_video_count':len(hits),'account_count':len({h['account'] for h in hits}),
            'asr_video_count':sum(h['source']=='ASR' for h in hits),'title_only_video_count':sum(h['source']=='SOURCE_TITLE_ONLY' for h in hits),
            'relation':'BOOK_NAME_CANDIDATE; mentioned/recommended/product target and edition not yet AI verified','evidence':hits})
    frequencies.sort(key=lambda x:(-x['new_unique_video_count'],x['term']))
    current_books=[];normalized=dict(zip(ids,cleans));new_canonical={z['video_id'] for z in newplan.values()}
    for term in sorted(known):
        nt=norm(term);hits=[]
        for v in ids:
            source_title=((lookup[v].get('db') or {}).get('title') or Path(lookup[v]['source_path']).stem)
            in_asr=nt in normalized[v];in_title=term in source_title
            if not in_asr and not in_title:continue
            pos=texts[v].find(term)
            hits.append({'video_id':v,'account':lookup[v]['account'],'source':'ASR' if in_asr else 'SOURCE_TITLE_ONLY',
                'quote':texts[v][max(0,pos-20):pos+len(term)+70] if pos>=0 else source_title[:160] if in_title else None,
                'transcript_path':str(txroot(v,newids)/'transcripts'/f'{v}.txt'),'new_batch':v in new_canonical})
        if hits:current_books.append({'term':term,'video_count':len(hits),'new_video_count':sum(z['new_batch'] for z in hits),
            'historical_video_count':sum(not z['new_batch'] for z in hits),'account_count':len({z['account'] for z in hits}),
            'relation':'current dictionary occurrence over all SHA-canonical content; title-only evidence is not spoken recommendation','evidence':hits})
    current_books.sort(key=lambda x:(-x['video_count'],x['term']));atomic_json(B/'clusters/current_book_frequencies.json',current_books)
    for term in story_terms:
        hits=[{'video_id':x['video_id'],'account':x['account'],'evidence':next(({'segment_id':f's{i+1:06d}','quote':s['text'][:180],'start_ms':s['start_ms'],'end_ms':s['end_ms']} for i,s in enumerate(segments[x['video_id']]) if term in s['text']),None)} for x in new if term in texts[newplan[x['video_id']]['video_id']]]
        if hits:entities.append({'term':term,'new_unique_video_count':len(hits),'account_count':len({h['account'] for h in hits}),
            'meaning':'实体/故事线索词出现，不等于已核实同一故事或史实','evidence':hits})
    entities.sort(key=lambda x:-x['new_unique_video_count'])
    atomic_json(B/'clusters/book_frequencies.json',frequencies);atomic_json(B/'clusters/story_entity_frequencies.json',entities)
    atomic_json(B/'clusters/video_features.json',features);atomic_json(B/'manifest/local_review_issues.json',issues)
    by_video=collections.defaultdict(list)
    for c in clusters:
        if c['incremental']:
            for v in c['new_video_ids']:by_video[v].append(c['cluster_id'])
    candidates=[];used_books=set()
    for account in ['失去壳的海龟','闲不住De宝']:
        pool=[x for x in new if x['account']==account]
        def score(x):
            v=x['video_id'];f=features[v];t=texts[newplan[v]['video_id']]
            relevant=[z for z in ['旅行','中国','博物馆','国宝','地理','古建','文物'] if z in t]
            return len(relevant)*2+bool(f['shopping_count'])*2+bool(f['recommendation_count'])+bool(by_video[v])
        ordered=sorted(pool,key=lambda x:(-score(x),x['video_id']));chosen=[]
        target=13 if account=='失去壳的海龟' else 12
        for x in ordered:
            key=title_books.get(x['video_id']) or x['video_id']
            if key in used_books:continue
            chosen.append(x);used_books.add(key)
            if len(chosen)>=target-2:break
        controls=[x for x in reversed(ordered) if x not in chosen]
        chosen+=controls[:target-len(chosen)]
        for x in chosen:
            v=x['video_id'];f=features[v];reasons=[f'{account}代表；时长{x["duration_s"]:.1f}秒']
            if f['title_book_candidate']:reasons.append('来源标题标示书名候选：'+f['title_book_candidate'])
            if f['shopping_count']:reasons.append(f'含{f["shopping_count"]}处购物词规则命中，待分清真实商品入口')
            elif x in chosen[-2:]:reasons.append('低购物词命中对照，不假定必然售书')
            if by_video[v]:reasons.append('存在文本相似线索：'+','.join(by_video[v]))
            if account=='闲不住De宝':reasons.append('旅行/文博结构与当前选题方向的相关性待A全文复核')
            candidates.append({'video_id':v,'account':account,'rank':len(candidates)+1,'reason':'；'.join(reasons),
                'source_path':x['source_path'],'ai_status':'AI_PENDING','input_mode_allowed':['text_only','text_plus_frames']})
    pending={a:[c for c in candidates if c['account']==a] for a in ['闲不住De宝','失去壳的海龟']};candidates=[]
    while any(pending.values()):
        for account in pending:
            if pending[account]:candidates.append(pending[account].pop(0))
    for i,c in enumerate(candidates,1):c['rank']=i
    atomic_json(B/'clusters/deep_candidates.json',candidates)
    summary={'at':now(),'new_files':len(new),'new_unique_contents':len({x['sha256'] for x in new}),
        'combined_source_paths':len(old)+len(new),'combined_unique_contents':len({x['sha256'] for x in old+new}),
        'new_fulltext_pairs':sum('FULL_TEXT' in p['kinds'] for p in pairs),'new_opening_pairs':sum('OPENING' in p['kinds'] for p in pairs),
        'new_passage_pairs':sum('STORY_PASSAGE' in p['kinds'] for p in pairs),
        'new_cross_account_pairs':sum(p['cross_account'] for p in pairs),
        'current_cluster_count_by_kind':dict(collections.Counter(c['kind'] for c in clusters)),
        'clusters_touching_new_by_kind':dict(collections.Counter(c['kind'] for c in clusters if c['incremental'])),
        'candidates':len(candidates),'candidate_accounts':dict(collections.Counter(x['account'] for x in candidates)),
        'book_terms':len(frequencies),'story_entity_terms':len(entities),'local_review_issues':len(issues),
        'current_book_terms':len(current_books),'combined_account_sources':dict(collections.Counter(x['account'] for x in old+new)),
        'elapsed_seconds':time.monotonic()-start,'text_semantic_verified':0,'representative_deep_verified':0,'ai_status':'AI_PENDING'}
    atomic_json(B/'manifest/statistics_summary.json',summary)
    atomic_text(R/'manifest/current_manifest.jsonl',''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in old+new))
    atomic_json(R/'manifest/current_source_index.json',{'at':now(),'historical_manifest':'manifest/manifest.jsonl',
        'increment_manifest':str((B/'manifest/manifest.jsonl').relative_to(R)).replace('\\','/'),
        'combined_manifest':'manifest/current_manifest.jsonl','sources':len(old)+len(new),
        'unique_contents':summary['combined_unique_contents'],'accounts':summary['combined_account_sources'],'historical_ids_preserved':True})
    prepare_handoff(new,features,candidates,segments,summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)

def prepare_handoff(new,features,candidates,segments,summary):
    # Each unit repeats original clauses exactly, with stable clause ids and offsets.
    if (H/'READY.json').exists():
        print('HANDOFF_ALREADY_FROZEN',flush=True);return
    task_records=[];all_units=[]
    for x in new:
        v=x['video_id'];ss=segments[v];units=[];buf=[];count=0
        input_obj=read(B/'handoff'/v/'input.json')
        input_obj.update(schema_version='new-account-input-1.0',ready_at=now(),local_checkpoint_ready=str(B/'handoff'/v/'READY.json'))
        atomic_json(H/'video_inputs'/f'{v}.json',input_obj)
        for i,s in enumerate(ss):
            if buf and count+len(s['text'])>4500:
                units.append(buf);buf=[];count=0
            buf.append({'segment_id':f's{i+1:06d}','start_ms':s['start_ms'],'end_ms':s['end_ms'],'text':s['text']});count+=len(s['text'])
        if buf:units.append(buf)
        unit_refs=[]
        for i,group in enumerate(units,1):
            unit_id=f'{v}_u{i:03d}';p=H/'text_units'/f'{unit_id}.json'
            obj={'schema_version':'text-unit-1.0','unit_id':unit_id,'video_id':v,'account':x['account'],
                'unit_index':i,'unit_count':len(units),'duration_s':x['duration_s'],
                'alignment_method':read(B/'segments'/f'{v}.aligned.json')['alignment_method'],
                'full_read_required':True,'segments':group,'source_transcript_sha256':sha256(B/'transcripts'/f'{v}.txt')}
            atomic_json(p,obj);ref={'unit_id':unit_id,'path':str(p),'sha256':sha256(p),'first_segment_id':group[0]['segment_id'],
                'last_segment_id':group[-1]['segment_id'],'char_count':sum(len(s['text']) for s in group)}
            text_path=p.with_suffix('.txt')
            atomic_text(text_path,f'{unit_id} | {i}/{len(units)} | read every segment through {group[-1]["segment_id"]}\n'+
                '\n'.join(f'[{s["segment_id"]}] {s["text"]}' for s in group)+'\n')
            ref.update(text_path=str(text_path),text_sha256=sha256(text_path))
            unit_refs.append(ref);all_units.append(ref)
        task_records.append({'video_id':v,'account':x['account'],'source_video_path':x['source_path'],'source_sha256':x['sha256'],
            'duration_s':x['duration_s'],'local_ready':str(B/'handoff'/v/'READY.json'),'input_json':str(H/'video_inputs'/f'{v}.json'),
            'text_units':unit_refs,'segments_count':len(ss),'expected_first_segment_id':f's{1:06d}',
            'expected_last_segment_id':f's{len(ss):06d}','deep_candidate':any(c['video_id']==v for c in candidates),'ai_status':'AI_PENDING'})
    # Interleave the accounts; first batch has five videos and both accounts.
    aa={a:[x for x in task_records if x['account']==a] for a in sorted({x['account'] for x in new})};ordered=[]
    while any(aa.values()):
        for account in aa:
            if aa[account]:ordered.append(aa[account].pop(0))
    batches=[{'batch_id':f'text_{i//5+1:02d}','videos':ordered[i:i+5]} for i in range(0,len(ordered),5)]
    for batch in batches:
        path=H/'tasks'/f'{batch["batch_id"]}.json';atomic_json(path,{'schema_version':'new-account-work-unit-1.0','kind':'text',**batch});batch['batch_file']=str(path)
    for i in range(0,len(candidates),5):
        chosen=candidates[i:i+5];path=H/'tasks'/f'deep_{i//5+1:02d}.json'
        atomic_json(path,{'schema_version':'new-account-work-unit-1.0','kind':'deep','batch_id':f'deep_{i//5+1:02d}',
            'videos':[{**c,'input_json':str(H/'video_inputs'/f'{c["video_id"]}.json')} for c in chosen]})
    atomic_json(H/'batch_plan.json',{'schema_version':'new-account-plan-1.0','created_at':now(),'records':task_records,
        'text_batches':batches,'representative_candidates':candidates,'statistics':summary,'output_root':str(R/'analysis_a'/BATCH)})
    schema={'$schema':'https://json-schema.org/draft/2020-12/schema','title':'Per-video full-text semantic analysis',
        'type':'object','required':['schema_version','video_id','account','input_mode','source_sha256','started_at','finished_at','coverage','fields','evidence','limitations','status'],
        'properties':{'schema_version':{'const':'new-account-text-1.0'},'video_id':{'type':'string','pattern':'^v_[0-9a-f]{16}$'},
            'account':{'enum':['失去壳的海龟','闲不住De宝']},'input_mode':{'const':'text_only'},'source_sha256':{'type':'string','pattern':'^[0-9a-f]{64}$'},
            'started_at':{'type':'string','format':'date-time'},'finished_at':{'type':'string','format':'date-time'},
            'coverage':{'type':'object','required':['read_all_units','unit_ids','first_segment_id','last_segment_id','missing_ranges'],
                'properties':{'read_all_units':{'type':'boolean'},'unit_ids':{'type':'array','items':{'type':'string'},'minItems':1},
                    'first_segment_id':{'type':'string'},'last_segment_id':{'type':'string'},'missing_ranges':{'type':'array'}}},
            'fields':{'type':'object','required':['theme','category','story_points','book_relations','hook','bridge','cta','reusable_method','original_topic_angles'],
                'properties':{'theme':{'type':'string'},'category':{'type':'string'},'story_points':{'type':'array'},'book_relations':{'type':'array'},
                    'hook':{'type':'object'},'bridge':{'type':'object'},'cta':{'type':'object'},'reusable_method':{'type':'string'},'original_topic_angles':{'type':'array'}}},
            'evidence':{'type':'array','minItems':1,'items':{'type':'object','required':['segment_id','quote','supports'],
                'properties':{'segment_id':{'type':'string'},'quote':{'type':'string','minLength':1,'maxLength':200},'supports':{'type':'string'}}}},
            'limitations':{'type':'array','items':{'type':'string'}},'status':{'enum':['AI_OK','AI_REVIEW','AI_PENDING']}}}
    atomic_json(H/'text_analysis_schema.json',schema)
    input_schema={'$schema':'https://json-schema.org/draft/2020-12/schema','type':'object',
        'required':['schema_version','video_id','account','duration_s','source_video_path','source_sha256','transcript_path','segments_path','frames','ready_at','ai_status'],
        'properties':{'schema_version':{'const':'new-account-input-1.0'},'video_id':{'type':'string','pattern':'^v_[0-9a-f]{16}$'},
            'account':{'enum':['失去壳的海龟','闲不住De宝']},'duration_s':{'type':'number','exclusiveMinimum':0},
            'source_video_path':{'type':'string'},'source_sha256':{'type':'string','pattern':'^[0-9a-f]{64}$'},
            'transcript_path':{'type':'string'},'segments_path':{'type':'string'},'ready_at':{'type':'string','format':'date-time'},
            'ai_status':{'const':'AI_PENDING'},'frames':{'type':'array','minItems':4,'maxItems':4,
                'items':{'type':'object','required':['time_s','path'],'properties':{'time_s':{'type':'number','minimum':0},'path':{'type':'string'}}}}}}
    atomic_json(H/'input_schema.json',input_schema)
    deep=read(R/'handoff/analysis_schema.json')
    deep['required']+=['account','source_video_path','source_sha256']
    deep['properties'].update(account={'enum':['失去壳的海龟','闲不住De宝']},source_video_path={'type':'string'},
        source_sha256={'type':'string','pattern':'^[0-9a-f]{64}$'},input_mode={'enum':['text_plus_frames','text_only']},
        status={'enum':['AI_OK','AI_REVIEW','AI_PENDING']})
    atomic_json(H/'deep_analysis_schema.json',deep)
    file_ref={'type':'object','required':['path','sha256'],'properties':{'path':{'type':'string'},'sha256':{'type':'string','pattern':'^[0-9a-f]{64}$'}}}
    completion_schema={'$schema':'https://json-schema.org/draft/2020-12/schema','type':'object',
        'required':['batch_id','kind','started_at','finished_at','inputs','outputs','unresolved'],
        'properties':{'batch_id':{'type':'string'},'kind':{'enum':['text','deep','summary','revision']},
            'started_at':{'type':'string','format':'date-time'},'finished_at':{'type':'string','format':'date-time'},
            'inputs':{'type':'array','minItems':1,'items':file_ref},'outputs':{'type':'array','minItems':1,'items':file_ref},'unresolved':{'type':'array'}}}
    atomic_json(H/'completion_schema.json',completion_schema)
    instruction=f'''# 发给Antigravity：两个新账号全文轻分析及代表深拆\n\n本批次：{BATCH}。先读项目AGENTS、共享总控、这个包的READY、batch_plan和两个Schema。\n\n## 输入范围与角色\n\n全量{len(new)}份新增独立内容、{len(all_units)}个文字单元；原视频只留在本机。沿用用户已批准的文本/4帧输入范围，禁止新收费API、原视频/音频上传、读取凭据或绕过官方额度。不要运行项目其他API脚本。输出只写`analysis_a/{BATCH}/<子批次>/`；不改总表、原文、Codex状态或旧A原件。\n\n## 执行顺序\n\n1. 先做text_01中的5条：逐条读完所有text_units，不能只看开头或标题，必须包含末单元末段。按text_analysis_schema输出每视频JSON。自校验合法JSON、Schema、身份、输入SHA、原文引句和覆盖后，在同目录临时写入，再原子改名。\n2. 自检通过后以5条为一批按text_02等顺序继续全文轻分析，每小批独立落盘，不等全量结束。发现输入缺失/系统性识别问题就标AI_REVIEW并明确问题，不填造出来的内容。\n3. 全文就绪后分批做25条代表候选的text_plus_frames分析，每批5条。按deep_analysis_schema，逐条确实读取原文本、所有单元和4帧。模式必须符合真实输入；4帧无法证明完整音乐/运镜/全部镜头，未知就填未知。若候选重复、无法增加结构或额度不足，可缩减并写明原因，不能把其余AI_PENDING算完成。\n4. 每个子批次附完成清单（实际开始/结束ISO时间、每个输入/输出SHA、文件列表、未决问题）。所有最终文件写完后再原子写COMPLETED.json；禁止覆盖旧子批次，修订新建revision子批次。\n\n## 字段规则\n\n- coverage.unit_ids必须列出该视频全部真实单元ID；首末段ID对得上，missing_ranges有缺项就不能AI_OK。输出每条输入source_sha256。\n- 字段中提到的书籍使用book_relations区分mentioned/recommended/product_target/uncertain，每项含书名、relation、证据segment_id；版次/ISBN/出版社未知，不凭常识补。\n- Hook/Bridge/CTA存在则给真实短引句、segment_id与实际时间；不存在标present=false；从故事到推荐和购物入口分开，借阅、关注、下集预告不能当购买。单元内时间为模型估计，若标CHUNK_LEVEL_FALLBACK，不能输出逐词精确0～3秒。\n- evidence短引句必须逐字来自本视频对应段，单条不超过200字，不复制长篇竞品稿。保留事实声称与已核实事实的区别。\n- 原创方向重写具体问题和表达，不改几个字复刻；优先判断哪些方法能迁移到大美中国/365日走遍中国类选题，但不得凭竞品推定目标实书内容。\n- 不得把高频/重复认定为爆款、销量或转化；没有指标就未知。\n\n## 汇总\n\n按两个账号分别总结新出现的方法、常见书籍关系、适用/不适用的选题形式、与旧结构的增量，并列证据ID；模板不足就少给，单来源标草案。文字轻分析数、代表深拆数、原创建议数分别计。Codex会在真实交接后约3小时独立审核落盘，只接受Schema、SHA、证据与覆盖都通过的文件。\n'''
    instruction+='\n每批的简短任务文件在tasks/text_01.json等；batch_plan按字段读取，避免把整份大清单打印进上下文。每个unit提供紧凑TXT供全文阅读（带段ID），JSON供精确时间回查。每条视频的全部text_units仍必须读全，不能只依赖工具默认前200行；要核对首末段ID，长稿尾段不能遗漏。每小批COMPLETED.json必须符合completion_schema.json；输出类型text/deep分开，不能以视频深拆抵扣全文语义覆盖。每小批开始时先用本机时钟在自己的目录写开始记录，完成时再取本机时钟记录结束，不倒填统一固定日期；真实墙钟区间与模型推理耗时分清。\n'
    instruction+='\n先读local_review_issues.json：原ASR不改，专名按看得清的字幕作派生更正并引用帧证据；未核实的游本昌逝世叙事不得当作原创事实，也不因Schema通过而结案。\n'
    instruction=instruction.replace(f'analysis_a/{BATCH}',f'{R.name}/analysis_a/{BATCH}')
    atomic_text(H/'发给A_两个新账号执行指令.md',instruction)
    atomic_text(H/'桌面交接短指令.md',f'''请在当前fuye项目开始竞品分析新批次 {BATCH}。先核验 `竞品视频分析_2026-10-15/handoff/{BATCH}/READY.json` 的文件哈希，再读取同目录《发给A_两个新账号执行指令.md》和对应Schema。\n\n本批只包含失去壳的海龟50、闲不住De宝33，共83份新文字及25条代表候选。先按tasks/text_01.json做5条全文轻分析，自检后分小批持续推进其余全文，再做代表深拆；每份长稿全部单元读完，核对尾段，真实引用和时间，未知留待核。只使用已批准文本/4静态帧，不上传原视频或音频，不调用新收费API，不运行其他API工程，不重跑旧317任务，也不干扰已有原创制作任务。\n\n只写 `analysis_a/{BATCH}/<独立子批次>/`；JSON合法及Schema通过后同目录原子改名，完成清单记录真实时间和输入/输出SHA，COMPLETED.json最后写。不得改总表、Codex清单、文库或旧A原件。请现在开始并逐小批真实落盘；Codex会在本次实际交接约3小时后独立审核并决定后续批次。\n''')
    desktop_path=H/'桌面交接短指令.md'
    atomic_text(desktop_path,desktop_path.read_text(encoding='utf-8').replace(f'analysis_a/{BATCH}',f'{R.name}/analysis_a/{BATCH}'))
    # Package finalization is performed after workbook/report/integrity QA.
    atomic_json(H/'package_prepared.json',{'at':now(),'text_videos':len(new),'text_units':len(all_units),'text_batches':len(batches),
        'deep_candidates':len(candidates),'ready':False,'note':'READY withheld until independent local QA and workbook completion'})

if __name__=='__main__':main()
