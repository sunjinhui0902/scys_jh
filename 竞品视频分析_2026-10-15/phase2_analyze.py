"""Local deterministic statistics, separate similarity definitions and candidates."""
from __future__ import annotations
import collections, datetime, difflib, hashlib, json, math, re, time, unicodedata
from pathlib import Path
from pipeline import OUTPUT_DIR as R, atomic_json, atomic_text, now
from phase2_run import items

BOOK_ALIASES={'国之脊梁':['国之激烈','国之几两','国值脊梁'],'人性的弱点':['人性弱点'],'黄帝内经':['黄帝內经'],'365日走遍中国':['三百六十五日走遍中国']}
EXCLUDED_BOOK_PHRASES={'技术':'泛指桥梁技术','处事思路':'泛指处理事情的方法','地基从唐朝一直管到今天':'地基描述','编钟一出土':'文物事件','思路的升级版':'方法描述','沟全长十二点六公里':'排水沟描述','编钟藏在湖北省博物馆':'文物位置','编钟出土之前':'文物事件','清明上河图':'绘画作品，不能直接认定图书','世界遗产名录':'名录资源，不能直接认定图书','闲谈':'短片段嵌入闲谈高手，不单列书名','国值脊梁里面':'保留原始命中，书名歧义另核'}
def norm(t):return ''.join(c.lower() for c in t if c.isalnum())
def read(p,default=None):return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
def title(x):return (x.get('db')or{}).get('title') or Path(x['source_path']).stem
def excerpt(t,term,n=45):
    i=t.find(term);return t[max(0,i-15):i+len(term)+n] if i>=0 else ''
def original_excerpt(t,start,length):
    positions=[i for i,c in enumerate(t)if c.isalnum()]
    return t[positions[start]:positions[min(len(positions)-1,start+max(1,length)-1)]+1] if start<len(positions)else''
def comp(edges,kind):
    parent={}
    def find(a):
        parent.setdefault(a,a)
        if parent[a]!=a:parent[a]=find(parent[a])
        return parent[a]
    for e in edges:
        a,b=find(e['left']),find(e['right']);parent[b]=a
    groups=collections.defaultdict(list)
    for a in parent:groups[find(a)].append(a)
    return [{'cluster_id':kind+'_'+hashlib.sha256('|'.join(sorted(g)).encode()).hexdigest()[:10],'kind':kind,'video_ids':sorted(g),'group_method':'connected components of recorded pair edges; not every pair is necessarily similar'} for g in groups.values() if len(g)>1]

def ai_validate(lookup):
    rows=[]
    for p in sorted((R/'analysis_a').glob('v_*.json')):
        if not re.fullmatch(r'v_[0-9a-f]{16}\.json',p.name):continue
        stat=p.stat();raw=p.read_bytes()
        if stat.st_size!=p.stat().st_size or stat.st_mtime_ns!=p.stat().st_mtime_ns:continue
        errors=[];issues=[];data={}
        try:data=json.loads(raw)
        except Exception as exc:errors.append('JSON_PARSE: '+str(exc))
        if not isinstance(data,dict):errors.append('TOP_LEVEL_NOT_OBJECT');data={}
        for k in ['video_id','input_mode','analyzed_at','fields','evidence','limitations','status','schema_version']:
            if k not in data:errors.append('MISSING_'+k)
        vid=data.get('video_id') if isinstance(data.get('video_id'),str) else None;x=lookup.get(vid)
        if p.stem!=vid:errors.append('FILENAME_VIDEO_ID_MISMATCH')
        if not x:errors.append('UNKNOWN_VIDEO_ID')
        if data.get('input_mode') not in ['native_video','text_plus_frames','text_only']:errors.append('INVALID_INPUT_MODE')
        if not isinstance(data.get('fields'),dict):errors.append('FIELDS_NOT_OBJECT')
        if not isinstance(data.get('evidence'),(list,dict)):errors.append('EVIDENCE_WRONG_TYPE')
        try:datetime.datetime.fromisoformat(data.get('analyzed_at',''))
        except:errors.append('BAD_ANALYSIS_DATE')
        fields=data.get('fields')if isinstance(data.get('fields'),dict)else{}
        if not isinstance(data.get('schema_version'),str):errors.append('SCHEMA_VERSION_NOT_STRING')
        if not isinstance(data.get('limitations'),(str,list)):errors.append('LIMITATIONS_WRONG_TYPE')
        for key in ['theme','category','mentioned_books','recommended_book','hook','narrative_structure','bridge','cta','visual_and_audio']:
            if key not in fields:errors.append('FIELDS_MISSING_'+key)
        if 'mentioned_books' in fields and (not isinstance(fields['mentioned_books'],list) or not all(isinstance(z,str)for z in fields['mentioned_books'])):errors.append('BOOKS_NOT_STRING_ARRAY')
        for key in ['hook','bridge','cta','visual_and_audio']:
            if key in fields and not isinstance(fields[key],dict):errors.append('FIELDS_'+key.upper()+'_NOT_OBJECT')
        for key in ['theme','category','narrative_structure']:
            if key in fields and not isinstance(fields[key],str):errors.append('FIELDS_'+key.upper()+'_NOT_STRING')
        if fields.get('recommended_book')is not None and not isinstance(fields.get('recommended_book'),str):errors.append('RECOMMENDED_BOOK_WRONG_TYPE')
        if data.get('status')not in ['AI_OK','AI_REVIEW','AI_PENDING','COMPLETE']:errors.append('INVALID_STATUS')
        if isinstance(data.get('evidence'),dict) and data['evidence'].get('exact_timestamps_source'):
            ref=data['evidence']['exact_timestamps_source'];ep=R/ref if isinstance(ref,str)else None
            if ep is None or not ep.is_file() or not vid or vid not in ep.name:errors.append('TIMESTAMP_EVIDENCE_PATH_INVALID')
        if x:
            if data.get('account')not in [None,x['account']]:errors.append('ACCOUNT_MISMATCH')
            hook=fields.get('hook')if isinstance(fields.get('hook'),dict)else{};tr=hook.get('time_range','');tr=tr if isinstance(tr,str)else''
            nums=re.findall(r'(\d+):(\d+(?:\.\d+)?)',tr)
            if nums and float(nums[-1][0])*60+float(nums[-1][1])>3.15:issues.append('HOOK_0_3S_CONTAINS_AUDIO_AFTER_3S')
            for k in ['bridge','cta']:
                z=fields.get(k)if isinstance(fields.get(k),dict)else{}
                for f in ['start_time_s','end_time_s']:
                    v=z.get(f)
                    if v is not None and (not isinstance(v,(float,int)) or not 0<=v<=x['duration_s']+1):issues.append(k.upper()+'_TIME_RANGE_INVALID')
            if data.get('source_video_path') not in [None,x['source_path']]:errors.append('SOURCE_PATH_MISMATCH')
        if data.get('input_mode')=='native_video':issues.append('NATIVE_VIDEO_CAPABILITY_IS_A_SELF_REPORT_NOT_INDEPENDENTLY_VERIFIED')
        if re.search('高口碑|高完播|强转发|100%',raw.decode('utf-8')):issues.append('UNSUPPORTED_PERFORMANCE_OR_ABSOLUTE_CLAIM')
        rows.append({'video_id':vid,'path':str(p),'sha256':hashlib.sha256(raw).hexdigest(),'schema_valid':not errors,'schema_errors':errors,'content_issues':issues,'import_status':'AI_REJECTED' if errors else ('AI_REVIEW' if issues else 'AI_OK'),'reported_status':data.get('status'),'fields':fields if not errors else {},'evidence':data.get('evidence') if not errors else None})
    atomic_json(R/'manifest/ai_validation.json',{'at':now(),'schema_reference':str(R/'handoff/analysis_schema.json'),'records':rows,'policy':'Do not alter A files. AI_REVIEW data kept out of finalized AI fields; pending fields are AI_PENDING.'})
    return rows

def main():
    from sklearn.feature_extraction.text import TfidfVectorizer
    import numpy as np
    rows=items();lookup={x['video_id']:x for x in rows};plan=read(R/'manifest/phase2_plan.json')
    ids=sorted(set(plan['canonical_by_video_id'].values()))
    docs=[];available=[]
    for v in ids:
        p=R/'transcripts'/f'{v}.txt'
        if p.exists() and p.read_text(encoding='utf-8').strip():available.append(v);docs.append(p.read_text(encoding='utf-8').strip())
    if len(available)!=len(ids):print('WARNING incomplete canonical transcripts',len(available),'/',len(ids),flush=True)
    clean=[];similarity_alias_hits=[]
    for v,t in zip(available,docs):
        working=t
        for canonical,variants in BOOK_ALIASES.items():
            for alias in variants:
                # Equal-length aliases preserve original character offsets for quotations.
                if len(alias)==len(canonical) and alias in working and canonical in title(lookup[v]):
                    working=working.replace(alias,canonical);similarity_alias_hits.append({'video_id':v,'alias':alias,'canonical':canonical,'support':'canonical in source title'})
        clean.append(norm(working))
    atomic_json(R/'clusters/similarity_alias_applications.json',{'rules':'Equal-length, source-title-supported aliases only; raw transcripts and quotation offsets unchanged','hits':similarity_alias_hits})
    idx={v:i for i,v in enumerate(available)};texts=dict(zip(available,docs))
    tv=TfidfVectorizer(analyzer='char',ngram_range=(2,4),min_df=2,max_features=70000,sublinear_tf=True)
    mat=tv.fit_transform(clean);full=(mat@mat.T).toarray()
    hv=TfidfVectorizer(analyzer='char',ngram_range=(2,4),min_df=1,max_features=40000,sublinear_tf=True)
    hm=hv.fit_transform([t[:100] for t in clean]);head=(hm@hm.T).toarray()
    atomic_json(R/'clusters/methodology.json',{'generated_at':now(),'population':'SHA256-canonical transcripts only; all source paths retained separately','normalization':'lowercase alphanumeric; supported equal-length book aliases applied only in derived comparison text','full_vectorizer':{'analyzer':'char','ngram_range':[2,4],'min_df':2,'max_features':70000,'sublinear_tf':True,'norm':'l2'},'opening_vectorizer':{'first_normalized_characters':100,'analyzer':'char','ngram_range':[2,4],'min_df':1,'max_features':40000,'sublinear_tf':True},'thresholds':{'FULL_TEXT':'cosine>=.76 and shorter/longer length>=.6 and ordered SequenceMatcher ratio>=.65','OPENING':'opening cosine>=.8, both >=25 normalized characters','STORY_PASSAGE':'longest contiguous normalized common substring>=80 and (cosine>=.45 or common/shorter>=.3)'},'cluster_method':'connected components per edge type; transitive membership does not imply all pairs meet threshold','passage_caveat':'Common paragraph may be a generic CTA; semantic story identity requires A/manual review'})
    pairs=[];full_edges=[];head_edges=[];story_edges=[]
    for i,a in enumerate(available):
        for j in range(i+1,len(available)):
            b=available[j];f=float(full[i,j]);h=float(head[i,j])
            if f<.38 and h<.65:continue
            ratio=min(len(clean[i]),len(clean[j]))/max(1,max(len(clean[i]),len(clean[j])))
            matcher=difflib.SequenceMatcher(None,clean[i],clean[j],autojunk=False)
            match=matcher.find_longest_match()
            ordered=matcher.ratio() if f>=.76 and ratio>=.6 else None
            common=clean[i][match.a:match.a+match.size]
            kinds=[]
            if f>=.76 and ratio>=.6 and ordered>=.65:kinds.append('FULL_TEXT')
            if h>=.8 and len(clean[i][:100])>=25 and len(clean[j][:100])>=25:kinds.append('OPENING')
            if match.size>=80 and (f>=.45 or match.size/min(len(clean[i]),len(clean[j]))>=.3):kinds.append('STORY_PASSAGE')
            if not kinds:continue
            edge={'left':a,'right':b,'full_cosine':round(f,5),'opening_cosine':round(h,5),'length_ratio':round(ratio,5),'longest_common_chars':match.size,'common_excerpt_normalized':common[:160],'left_quote':original_excerpt(docs[i],match.a,min(match.size,160)),'right_quote':original_excerpt(docs[j],match.b,min(match.size,160)),'left_transcript_path':str(R/'transcripts'/f'{a}.txt'),'right_transcript_path':str(R/'transcripts'/f'{b}.txt'),'kinds':kinds,'cross_account':lookup[a]['account']!=lookup[b]['account']}
            edge['ordered_match_ratio']=round(ordered,5) if ordered is not None else None
            pairs.append(edge)
            if 'FULL_TEXT'in kinds:full_edges.append(edge)
            if 'OPENING'in kinds:head_edges.append(edge)
            if 'STORY_PASSAGE'in kinds:story_edges.append(edge)
    clusters=comp(full_edges,'TEXT')+comp(head_edges,'HOOK')+comp(story_edges,'PASSAGE')
    hashes=collections.defaultdict(list)
    for x in rows:hashes[x['sha256']].append(x['video_id'])
    exact=[{'cluster_id':'SHA_'+sha[:10],'kind':'SHA256_EXACT','video_ids':vs,'sha256':sha} for sha,vs in hashes.items() if len(vs)>1]
    for c in exact+clusters:c['accounts']=sorted({lookup[v]['account'] for v in c['video_ids']});c['account_count']=len(c['accounts'])
    for c in exact:
        canonical=plan['canonical_by_video_id'][c['video_ids'][0]];c['sample_quote']=texts.get(canonical,'')[:100];c['sample_quote_video_id']=canonical;c['similarity_basis']='SHA-256 identical bytes';c['sources']=[{'video_id':v,'account':lookup[v]['account'],'source_path':lookup[v]['source_path']}for v in c['video_ids']]
    for c in clusters:
        members=set(c['video_ids']);kind={'TEXT':'FULL_TEXT','HOOK':'OPENING','PASSAGE':'STORY_PASSAGE'}[c['kind']];ee=[p for p in pairs if p['left']in members and p['right']in members and kind in p['kinds']]
        ee.sort(key=lambda p:-(p['opening_cosine']if kind=='OPENING'else p['full_cosine']));c['sample_quote']=ee[0]['left_quote']if ee else'';c['sample_quote_video_id']=ee[0]['left']if ee else None;c['evidence_pairs']=[{'left':p['left'],'right':p['right'],'full_cosine':p['full_cosine'],'opening_cosine':p['opening_cosine'],'longest_common_chars':p['longest_common_chars']}for p in ee];c['similarity_basis']=kind+' thresholds documented in report; pair-level quotes in similarity_pairs.jsonl';c['shared_passage_may_be_CTA_or_story']=kind=='STORY_PASSAGE'
    atomic_json(R/'clusters/exact_duplicates.json',exact);atomic_json(R/'clusters/text_clusters.json',clusters)
    atomic_text(R/'clusters/similarity_pairs.jsonl',''.join(json.dumps(p,ensure_ascii=False)+'\n' for p in sorted(pairs,key=lambda e:(not e['cross_account'],-e['full_cosine']))))
    # Source-derived book/entity lexicons; a name mention is not a product recommendation.
    lex={'资治通鉴','黄帝内经','国之脊梁','闲谈高手','隐形的契约','沉思录','对答入流','呼啸山庄','人一生要看的100个博物馆','人性的弱点','道德经','论语','史记','山海经','四库全书','红楼梦','西游记','365日走遍中国','大美中国'}
    atomic_json(R/'clusters/book_lexicon_source_additions.json',[{'term':'365日走遍中国','video_id':'v_5ddb5a8ad7ccdb86','basis':'Source title hashtag plus ASR: 我前阵子翻到一本叫三百六十五日走遍中国的日历书','status':'BOOK_NAME_CANDIDATE; edition unverified'},{'term':'大美中国','video_id':'v_8dd105b9b996aea3','basis':'ASR: 前阵子我翻到一本书...叫大美中国人一生要去的一百零一个地方','status':'BOOK_NAME_CANDIDATE; full formal title/edition unverified'}])
    phrase_groups=collections.defaultdict(list);raw_phrase_hits=[]
    generic=('会','能','让','很','真','特别','不仅','就是','图书','书籍','好书','小书','大书','实在','里面','先','就','我','你','您','这','那','系统','身','来','一套','一本')
    for v,t in texts.items():
        for phrase in re.findall(r'(?:这本|这套)(?!书)([^，。！？；]{2,16})(?=[，。！？；])',t):
            raw_phrase=phrase.strip('《》“” ')
            raw_phrase_hits.append({'video_id':v,'account':lookup[v]['account'],'raw_phrase':raw_phrase,'quote':excerpt(t,raw_phrase)})
            phrase=re.sub(r'^(?:(?:亲笔签名的?|签名版的?|代表作))+','',raw_phrase)
            phrase=re.sub(r'(?:来推荐给大家|啊呃这本书|就知道了|里面|啊|呀|哦|吧)$','',phrase)
            if phrase.startswith(generic)or not re.fullmatch(r'[\u4e00-\u9fffA-Za-z0-9]{2,12}',phrase)or any(z in phrase for z in ['可以','想请教','推荐给','这本书','一样样']):continue
            if phrase in EXCLUDED_BOOK_PHRASES:continue
            phrase_groups[phrase].append({'video_id':v,'account':lookup[v]['account'],'raw_phrase':raw_phrase,'quote':excerpt(t,raw_phrase)})
    for phrase in phrase_groups:
        if phrase in [a for variants in BOOK_ALIASES.values()for a in variants]:continue
        lex.add(phrase)
    atomic_json(R/'clusters/book_phrase_raw_hits.json',raw_phrase_hits)
    atomic_json(R/'clusters/book_phrase_candidates.json',[{'phrase':k,'video_count':len({z['video_id']for z in ev}),'account_count':len({z['account']for z in ev}),'evidence':ev,'classification':'Unconfirmed ASR book-like phrase, may contain trailing description rather than a formal title'}for k,ev in sorted(phrase_groups.items(),key=lambda z:-len({e['video_id']for e in z[1]}))])
    for x in rows:
        lex.update(z for z in re.findall(r'《([^》]{2,20})》',title(x)) if not re.search(r'[，,！？]|告诉|告诉您',z))
    lex.difference_update(EXCLUDED_BOOK_PHRASES)
    atomic_json(R/'clusters/book_phrase_exclusions.json',{'basis':'Codex read actual quoted contexts; exclusions concern title extraction, not A semantic conclusions','excluded':EXCLUDED_BOOK_PHRASES,'raw_hits_preserved':str(R/'clusters/book_phrase_raw_hits.json')})
    people=set()
    for x in rows:
        if x['account']=='文汇书香苑':
            m=re.match(r'^([\u4e00-\u9fff]{2,4})(?:\s|[_：:])',title(x))
            if m:people.add(m.group(1))
    people.update(['毛泽东','许广平','林徽因','杨绛','蒋英','刘思礼','李善长','王阳明','曾国藩','朱元璋','江澄波'])
    aliases=BOOK_ALIASES
    atomic_json(R/'clusters/book_alias_rules.json',{'status':'Candidate normalization only; original transcript unchanged','rules':aliases,'policy':'ASR alias alone is insufficient; require the canonical name in source title for supported normalization'})
    book_stats=[];entity_stats=[];tags=collections.defaultdict(set);book_by=collections.defaultdict(list);entity_by=collections.defaultdict(list)
    for v in available:
        x=lookup[v];t=texts[v];tt=title(x);al=read(R/'segments'/f'{v}.aligned.json',{'segments':[]})['segments']
        for tag in re.findall(r'#([^#\s]+)',tt):tags[tag].add(v)
        for term in sorted(lex):
            matched_alias=next((a for a in aliases.get(term,[])if a in t and term in tt),None)
            text_hit=term in t and not any(term!=longer and term in longer and longer in t for longer in lex)
            title_hit=term in tt and not any(term!=longer and term in longer and longer in tt for longer in lex)
            if not text_hit and not title_hit and not matched_alias:continue
            mentions=[{'start_ms':z['start_ms'],'end_ms':z['end_ms'],'text':z['text'][:130]} for z in al if term in z['text'] or (matched_alias and matched_alias in z['text'])]
            record={'video_id':v,'account':x['account'],'source':'ASR' if text_hit else ('ASR_ALIAS_WITH_TITLE_SUPPORT' if matched_alias else 'TITLE_ONLY'),'matched_alias':matched_alias,'quote':excerpt(t,term if text_hit else matched_alias) if text_hit or matched_alias else excerpt(tt,term),'time_evidence':mentions[:4]}
            book_by[term].append(record)
        for term in sorted(people):
            if term in t or term in tt:entity_by[term].append({'video_id':v,'account':x['account'],'title_focus':term in tt.split('#')[0],'quote':excerpt(t,term) if term in t else excerpt(tt,term)})
    for term,ev in book_by.items():book_stats.append({'term':term,'video_count':len(ev),'account_count':len({e['account'] for e in ev}),'evidence':ev,'classification':'BOOK_NAME_CANDIDATE; mention != recommendation; title may refer to artwork/other resource'})
    for term,ev in entity_by.items():entity_stats.append({'term':term,'video_count':len(ev),'title_focus_count':sum(e['title_focus'] for e in ev),'account_count':len({e['account'] for e in ev}),'evidence':ev,'classification':'PERSON_STORY_CANDIDATE; no historical fact verification'})
    book_stats.sort(key=lambda d:(-d['account_count'],-d['video_count'],d['term']));entity_stats.sort(key=lambda d:(-d['title_focus_count'],-d['video_count']))
    atomic_json(R/'clusters/book_frequencies.json',book_stats);atomic_json(R/'clusters/story_entity_frequencies.json',entity_stats)
    atomic_json(R/'clusters/topic_tags.json',[{'tag':k,'video_count':len(v),'account_count':len({lookup[z]['account'] for z in v}),'video_ids':sorted(v)} for k,v in sorted(tags.items(),key=lambda kv:-len(kv[1]))])
    import jieba.analyse
    keywords=collections.defaultdict(list)
    for v,t in texts.items():
        for word in jieba.analyse.extract_tags(title(lookup[v])+' '+t,topK=8,allowPOS=('nr','ns','nt','nz','n')):
            keywords[word].append({'video_id':v,'account':lookup[v]['account'],'quote':excerpt(t,word) or excerpt(title(lookup[v]),word)})
    atomic_json(R/'clusters/keyword_frequencies.json',[{'keyword':k,'video_count':len(ev),'account_count':len({e['account']for e in ev}),'evidence':ev,'classification':'TF-IDF noun/name candidate; not verified topic/entity'}for k,ev in sorted(keywords.items(),key=lambda z:-len(z[1]))])
    features={};similar_members=collections.defaultdict(list)
    for c in clusters:
        for v in c['video_ids']:similar_members[v].append(c['cluster_id'])
    book_terms={v:[b['term'] for b in book_stats if any(e['video_id']==v for e in b['evidence'])] for v in available}
    for v in available:
        t=texts[v];intro=re.search(r'这本|这套|推荐.{0,15}书|读完这本|橱窗|小黄车|下单|点击.{0,8}商品',t)
        rec=re.search(r'推荐.{0,30}(?:这本|这套|书)|读完这本|买.{0,8}这本书',t);purchase=re.search(r'橱窗|小黄车|下单|购买|点击.{0,8}商品',t)
        timed=read(R/'segments'/f'{v}.aligned.json',{'segments':[]})['segments']
        marker_evidence=[{'start_s':z['start_ms']/1000,'end_s':z['end_ms']/1000,'text':z['text'][:150]}for z in timed if re.search(r'这本|这套|推荐|橱窗|小黄车|下单|购买',z['text'])]
        features[v]={'video_id':v,'account':lookup[v]['account'],'duration_s':lookup[v]['duration_s'],'book_candidates':book_terms[v],'book_mention_rule':bool(book_terms[v]),'recommendation_rule':bool(rec),'shopping_prompt_rule':bool(purchase),'book_marker_count':len(re.findall(r'这本|这套|推荐|读完|书里',t)),'purchase_marker_count':len(re.findall(r'橱窗|小黄车|下单|购买|点击.{0,8}商品',t)),'engagement_marker_count':len(re.findall(r'点赞|关注|收藏|转发|评论区',t)),'similarity_clusters':similar_members[v],'book_marker_excerpt':t[max(0,intro.start()-15):intro.start()+100] if intro else '', 'marker_time_evidence':marker_evidence[:10],'classification':'RULE_HINTS_ONLY; book mention, recommendation wording and shopping wording are separate; absence does not prove absent visual CTA'}
    for v,f in features.items():
        f['cross_account_book_topics']=[{'term':b['term'],'account_count':b['account_count'],'video_count':b['video_count']}for b in book_stats if b['account_count']>1 and any(e['video_id']==v for e in b['evidence'])]
        f['title_story_topics']=[{'term':b['term'],'title_focus_count':b['title_focus_count'],'account_count':b['account_count']}for b in entity_stats if any(e['video_id']==v and e['title_focus']for e in b['evidence'])]
        f['book_marker_rate_per_minute']=round(f['book_marker_count']*60/max(f['duration_s'],1),3)
    atomic_json(R/'clusters/video_features.json',features)
    selected=[];used=set()
    def add(v,reason):
        if v not in used:used.add(v);selected.append({'rank':len(selected)+1,**features[v],'reason':reason,'source_path':lookup[v]['source_path'],'sha256':lookup[v]['sha256'],'handoff_path':str(R/'handoff'/v)})
    # 4 per account for diversity; preserve the three A calibration examples.
    pinned=['v_183328bf0ee8b458','v_30cc827b5d5dd936','v_7e9d12d17d945cb4']
    for a in sorted({x['account'] for x in rows}):
        pool=[v for v in available if lookup[v]['account']==a and lookup[v]['duration_s']<=1500]
        if len(pool)<4:pool=[v for v in available if lookup[v]['account']==a]
        for v in pinned:
            if v in pool:add(v,'已有 A 小批量试标注；用于字段与证据格式校准，A 结论仍须校验')
        strategies=[('荐书/购物措辞密度或弱Bridge对照',lambda v:((features[v]['purchase_marker_count']*5+features[v]['book_marker_count'])*60/max(lookup[v]['duration_s'],30),len(book_terms[v]))),('同账号相似结构；无相似时选同人物高频对照',lambda v:(bool(similar_members[v]),len(similar_members[v]),max([p['full_cosine'] for p in pairs if v in [p['left'],p['right']]]or[0]),max([z['title_focus_count']for z in features[v]['title_story_topics']]or[0]))),('账号内较长时长对照',lambda v:(lookup[v]['duration_s'] if lookup[v]['duration_s']<=1500 else 0,0)),('低重复对照',lambda v:(-len(similar_members[v]),-abs(lookup[v]['duration_s']-180)))]
        for label,key in strategies:
            if sum(features[z]['account']==a for z in used)>=4:break
            candidate=max([v for v in pool if v not in used],key=key)
            detail=''
            if label.startswith('同账号')and not similar_members[candidate]:
                topics=features[candidate]['title_story_topics'];top=max(topics,key=lambda z:z['title_focus_count'])if topics else None
                detail=('；未命中文案相似，标题主讲'+top['term']+'共'+str(top['title_focus_count'])+'条'if top else'；未命中文案相似，保留账号特色对照')
            add(candidate,label+detail+'；仅规则候选，需 A 复核实际 Bridge/CTA 与画面')
    extras=[v for v in available if v not in used and lookup[v]['duration_s']<=1500]
    if extras:
        v=max(extras,key=lambda v:(len({lookup[e['right']if e['left']==v else e['left']]['account'] for e in pairs if v in[e['left'],e['right']] and e['cross_account']}),max([z['account_count']for z in features[v]['cross_account_book_topics']]or[0]),max([z['video_count']for z in features[v]['cross_account_book_topics']]or[0]),features[v]['book_marker_rate_per_minute']))
        cross_accounts={lookup[e['right']if e['left']==v else e['left']]['account']for e in pairs if v in[e['left'],e['right']]and e['cross_account']}
        topic=max(features[v]['cross_account_book_topics'],key=lambda z:(z['account_count'],z['video_count']))if features[v]['cross_account_book_topics']else None
        reason='补充跨账号相似，涉及'+str(len(cross_accounts))+'个其他账号'if cross_accounts else ('跨账号书名提及对照：'+topic['term']+'，'+str(topic['account_count'])+'账号/'+str(topic['video_count'])+'内容；非同稿证据'if topic else'补充账号特色/荐书词线索对照')
        add(v,reason+'；保持总计25条')
    atomic_json(R/'clusters/deep_candidates.json',selected)
    if all((R/'handoff'/c['video_id']/'READY.json').exists()for c in selected):
        atomic_json(R/'handoff/deep_candidates.READY.json',{'schema_version':'1.0','ready_at':now(),'candidate_count':len(selected),'candidate_file':str(R/'clusters/deep_candidates.json'),'video_ids':[c['video_id']for c in selected],'all_individual_READY_exist':True})
    ai=ai_validate(lookup)
    report=['# 高频复用与深度候选清单（Phase 2）','','口径：332条来源路径、317个SHA内容；统计按不同SHA内容去重，保留全部来源。字符TF-IDF只是口播相似；同书名/同人物另列，不代表销量或转化。','',f'完全重复：{len(exact)}簇，额外副本{sum(len(c["video_ids"])-1 for c in exact)}个；全文相似：{len(comp(full_edges,"T"))}簇；开头相似：{len(comp(head_edges,"H"))}簇；段落复用：{len(comp(story_edges,"P"))}簇；相似配对：{len(pairs)}对，跨账号{sum(e["cross_account"] for e in pairs)}对。','','方法：中文/英文做字母数字清洗与有标题支持的等长别名归一（保留原文），字符2～4gram TF-IDF余弦。全文≥0.76且长度比≥0.6、顺序匹配比例≥0.65；开头前100字余弦≥0.80；连续公共片段≥80字且全文余弦≥0.45或覆盖短文≥30%。簇为边的连通分量，不声称簇内任意两条都相似。完整分数、证据短摘和ID在 clusters/similarity_pairs.jsonl。','','## 书名候选（提及不等于推荐）','']
    report+=['来源为标题括号、初始词典与转录“这本/这套”片段。可能包含书系、作品名或尾随描述；这些是待A核实的名称候选，不等于正式商品名。别名规则及原始命中片段分别保存在 book_alias_rules.json、book_phrase_candidates.json。已依据真实上下文排除“技术/处事思路/编钟描述”等非书名，并按最长命中抑制嵌套短词重复计数；排除明细见 book_phrase_exclusions.json，原始命中仍保留。','','|词项|不同内容数|账号数|','|---|---:|---:|']+[f'|{z["term"]}|{z["video_count"]}|{z["account_count"]}|' for z in book_stats[:20]]
    report+=['','## 人物/故事候选（标题主讲与文中提及分列）','','|词项|标题主讲数|提及内容数|账号数|','|---|---:|---:|---:|']+[f'|{z["term"]}|{z["title_focus_count"]}|{z["video_count"]}|{z["account_count"]}|' for z in entity_stats[:20]]
    report+=['','## 25条深度候选','','不是按重复数单一排名；每账号至少4条，覆盖荐书词、重复结构、不同长度与低重复对照。本轮深度候选限25分钟以内，荐书/购物措辞按时长归一；超长访谈保留全量基础结果，避免原始词频偏向两小时视频。','','|序号|ID|账号|秒|候选原因|','|---:|---|---|---:|---|']+[f'|{z["rank"]}|{z["video_id"]}|{z["account"]}|{z["duration_s"]:.1f}|{z["reason"]}；荐书词{z["book_marker_count"]}次、购买词{z["purchase_marker_count"]}次、相似簇{len(z["similarity_clusters"])}个|' for z in selected]
    report+=['','## A 导入校验','',f'完整JSON {len(ai)}份；基本Schema通过{sum(x["schema_valid"] for x in ai)}份；AI_OK {sum(x["import_status"]=="AI_OK" for x in ai)}份；AI_REVIEW {sum(x["import_status"]=="AI_REVIEW" for x in ai)}份。0～3秒字段超长、绝对化/表现判断无指标、原生MP4能力仅有自报，均不直接变为已核结论。原A文件不修改。']
    atomic_text(R/'reports/高频复用与候选清单.md','\n'.join(report)+'\n')
    instruction=['# Antigravity Phase 3：25条候选深度分析任务','',f'共享目录：{R}。用户已确认G1并授权Phase2。请遵循用户已确认的具体输入范围；Codex未自动上传任何素材。','', '先读 clusters/deep_candidates.json、reports/高频复用与候选清单.md、reports/A_结果校验反馈.md 与 handoff/analysis_schema.json。只处理下列25条中已有 READY.json 的交接包，建议每批5条。不要扩为全部332条深度分析。','', '先修正现有3份试标注：0～3秒字段不得包含延伸到5～7秒的全文；无平台指标不得写高口碑、高完播、强转发或销量结论。原生视频输入能力须有实际受支持输入和可追溯证据；若只能可靠读取文字与4帧，使用text_plus_frames，并把完整音乐/全部镜头判断留空。','', '每条输出选题/书名候选与实际推荐书名、真实0～3秒口播、叙事、Bridge原话与时间、CTA原话与时间、明确价值主张与推断、画面特征、重复簇引用及抽象原创结构建议。没有Bridge/CTA明确写无；无法确认的书名写未知。受众和心理机制等推断须明确标注。','', '只写analysis_a/<video_id>.json。先写临时文件，完成合法JSON与Schema校验后原子重命名。不要修改Codex的manifest/state/transcripts/segments/frames/clusters/reports或Excel。完成单条即落盘，不必等全批。分析完成后再在analysis_a/生成账号总结和3～8套有证据的原创结构模板；不足不凑数，不复制竞品成篇文案。','', '|序号|video_id|账号|候选理由|','|---:|---|---|---|']
    instruction += [f'|{c["rank"]}|{c["video_id"]}|{c["account"]}|{c["reason"]}|'for c in selected]
    atomic_text(R/'reports/Antigravity_Phase3_25条任务指令.md','\n'.join(instruction)+'\n')
    summary={'at':now(),'canonical_transcripts':len(available),'total_paths':len(rows),'exact_clusters':len(exact),'extra_exact_duplicates':sum(len(c['video_ids'])-1 for c in exact),'text_clusters':len(comp(full_edges,'T')),'opening_clusters':len(comp(head_edges,'H')),'passage_clusters':len(comp(story_edges,'P')),'similarity_pairs':len(pairs),'cross_account_pairs':sum(e['cross_account'] for e in pairs),'candidate_count':len(selected),'candidate_accounts':dict(collections.Counter(c['account'] for c in selected)),'ai_schema_valid':sum(a['schema_valid'] for a in ai),'ai_ok':sum(a['import_status']=='AI_OK' for a in ai),'ai_review':sum(a['import_status']=='AI_REVIEW' for a in ai)}
    atomic_json(R/'manifest/phase2_analysis_summary.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()


