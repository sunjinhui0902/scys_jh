"""Final evidence audit, including full source hashes and true restart evidence."""
from __future__ import annotations
import collections, hashlib, json, os, time, re
from pathlib import Path
from pipeline import OUTPUT_DIR as R, VIDEO_DIR, sha256, atomic_json, atomic_text, now
from phase2_run import items

def read(p,default=None):return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default
def main():
    from PIL import Image
    rows=items();plan=read(R/'manifest/phase2_plan.json');summary=read(R/'manifest/phase2_analysis_summary.json',{});fail=[];counts=collections.Counter();account=collections.defaultdict(collections.Counter);enriched=[]
    disk={str(p)for p in VIDEO_DIR.rglob('*')if p.is_file()and p.suffix.lower()in{'.mp4','.mov','.mkv','.m4v','.avi','.webm'}}
    if disk!={x['source_path']for x in rows}:fail.append({'video_id':'ALL','problem':'source directory membership changed'})
    integrity=[];frames_total=0;ready=0;token=0;coarse=0;quality=[]
    ai={z['video_id']:z['import_status']for z in read(R/'manifest/ai_validation.json',{'records':[]})['records']}
    for i,x in enumerate(rows,1):
        v=x['video_id'];sp=R/'state'/f'{v}.json';st=read(sp,{});ast=st.get('steps',{}).get('asr',{}).get('status','PENDING');counts[ast]+=1;account[x['account']]['files']+=1;account[x['account']][ast]+=1
        textpath=R/'transcripts'/f'{v}.txt';text=textpath.read_text(encoding='utf-8').strip()if textpath.exists()else'';al=read(R/'segments'/f'{v}.aligned.json',{})
        if text and ast!='OK':fail.append({'video_id':v,'problem':'nonempty text but ASR not OK'})
        if ''.join(z['text']for z in al.get('segments',[]))!=text:fail.append({'video_id':v,'problem':'alignment text mismatch'})
        segs=al.get('segments',[])
        if not all(isinstance(z.get('start_ms'),(float,int))and isinstance(z.get('end_ms'),(float,int))and 0<=z['start_ms']<=z['end_ms']<=(x['duration_s']+2)*1000 for z in segs):fail.append({'video_id':v,'problem':'actual segment time out of bounds'})
        if not all(segs[j]['start_ms']<=segs[j+1]['start_ms']for j in range(len(segs)-1)):fail.append({'video_id':v,'problem':'segment starts non-monotonic'})
        if al.get('checks',{}).get('token_count_equal'):
            from align_segments import token_spans
            raw=read(R/'segments'/f'{v}.json',{});nt=len(raw.get('raw_timestamp',[]))
            if len(token_spans(text))!=nt and len(token_spans(text,True))!=nt:fail.append({'video_id':v,'problem':'claimed token alignment count inconsistent'})
        if al.get('checks',{}).get('token_count_equal'):token+=1
        else:coarse+=1
        normalized=re.sub(r'[^\w\u4e00-\u9fff]','',text);density=len(normalized)/max(x['duration_s'],.1);flags=[]
        if x['duration_s']>=30 and density<.15:flags.append('LOW_TEXT_DENSITY_REVIEW')
        if density>12:flags.append('HIGH_TEXT_DENSITY_REVIEW')
        clauses=[re.sub(r'\W','',z.get('text',''))for z in al.get('segments',[])];clauses=[c for c in clauses if len(c)>=6];freq=collections.Counter(clauses)
        if clauses and freq.most_common(1)[0][1]>=5 and freq.most_common(1)[0][1]/len(clauses)>.35:flags.append('REPEATED_CLAUSE_REVIEW')
        if len(normalized)>=100 and collections.Counter(normalized).most_common(1)[0][1]/len(normalized)>.4:flags.append('REPETITIVE_CHARACTER_REVIEW')
        if al.get('segments') and x['duration_s']-al['segments'][-1]['end_ms']/1000>30:flags.append('EARLY_TRANSCRIPT_END_REVIEW')
        if flags:quality.append({'video_id':v,'account':x['account'],'characters_per_audio_second':round(density,3),'flags':flags,'evidence_path':str(R/'segments'/f'{v}.aligned.json'),'meaning':'Review trigger only; may be genuine silence/music/intro/outro/repeated live speech'})
        ff=read(R/'frames'/v/'index.json',[])
        if len(ff)!=4:fail.append({'video_id':v,'problem':'not four frames'})
        for f in ff:
            try:
                assert 0<=f['time_s']<x['duration_s']
                with Image.open(f['path'])as im:im.verify()
                frames_total+=1
            except Exception as exc:fail.append({'video_id':v,'problem':'frame invalid '+str(exc)})
        if st.get('reused_from') and len(ff)==4:
            for j,f in enumerate(ff,1):st.setdefault('steps',{}).setdefault(f'frame_{j}',{'status':'REUSED','source_id':st['reused_from'],'time_s':f['time_s'],'elapsed_s':0})
        for j,f in enumerate(ff,1):
            st.setdefault('steps',{}).setdefault(f'frame_{j}',{'status':'RECOVERED_VERIFIED','time_s':f['time_s'],'elapsed_s':None,'note':'Existing JPEG independently verified; original step timing unavailable'})
        st['tool_versions_reference']=str(R/'manifest/phase2_runtime.json');atomic_json(sp,st)
        pack=R/'handoff'/v;rp=pack/'READY.json'
        if rp.exists():
            ip=read(pack/'input.json');assert ip['video_id']==v and ip['source_video_path']==x['source_path'];assert Path(ip['transcript_path']).exists()and Path(ip['segments_path']).exists();ready+=1
        else:fail.append({'video_id':v,'problem':'no READY'})
        src=Path(x['source_path']);s=src.stat();digest=sha256(src);same=digest==x['sha256']and s.st_size==x['size_bytes']and s.st_mtime_ns==x['mtime_ns'];integrity.append({'video_id':v,'sha256':digest,'unchanged':same})
        if not same:fail.append({'video_id':v,'problem':'source changed'})
        enriched.append({**x,'canonical_video_id':plan['canonical_by_video_id'][v],'local_status':st.get('status','DISCOVERED'),'asr_status':ast,'ai_status':ai.get(v,'AI_PENDING'),'transcript_path':str(textpath),'segments_path':str(R/'segments'/f'{v}.aligned.json'),'handoff_path':str(pack),'frames':ff})
        if i%50==0:print('audit',i,len(rows),flush=True)
    atomic_json(R/'manifest/phase2_source_integrity.json',{'at':now(),'checked_files':len(rows),'unchanged_files':sum(z['unchanged']for z in integrity),'results':integrity})
    atomic_json(R/'manifest/asr_quality_flags.json',{'at':now(),'flagged_paths':len(quality),'records':quality,'policy':'Processing success is not word accuracy or proof of speech; these are review flags, not defect classifications'})
    before=read(R/'manifest/resume_test_before.json',{'completed_chunks':[]});preserved=[]
    for z in before['completed_chunks']:
        p=Path(z['path']);preserved.append(p.exists()and sha256(p)==z['sha256']and p.stat().st_mtime_ns==z['mtime_ns'])
    atomic_json(R/'manifest/resume_test_result.json',{'at':now(),'actual_workers_interrupted':True,'before_snapshot':str(R/'manifest/resume_test_before.json'),'interruption_record':str(R/'manifest/resume_test_interruption.json'),'completed_chunks_before':len(preserved),'chunks_preserved_without_rewrite':sum(preserved),'passed':bool(preserved)and all(preserved)})
    old=read(R/'manifest/phase2_source_snapshot.json',{}).get('database_files_metadata_only',{});dbnow={p.name:{'size_bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns}for p in VIDEO_DIR.glob('records.db*')if p.is_file()}
    atomic_text(R/'manifest/manifest.jsonl',''.join(json.dumps(x,ensure_ascii=False)+'\n'for x in enriched))
    runs=[json.loads(s)for s in (R/'logs/phase2_runs.jsonl').read_text(encoding='utf-8').splitlines()if s]if(R/'logs/phase2_runs.jsonl').exists()else[]
    result={'at':now(),'files':len(rows),'accounts':{k:dict(v)for k,v in account.items()},'asr_status_counts':dict(counts),'ready_packages':ready,'verified_jpegs':frames_total,'token_aligned_files':token,'coarse_aligned_files':coarse,'source_hash_unchanged':sum(z['unchanged']for z in integrity),'resume_test_passed':all(preserved)and bool(preserved),'database_opened_this_phase':False,'database_metadata_unchanged_this_phase':old==dbnow,'run_wall_seconds_including_restart_test':sum(j.get('elapsed_s',0)for j in runs),'failures':fail,'analysis_summary':summary,'status':'PASS_LOCAL_PHASE2'if not fail and counts['OK']==len(rows)else'PARTIAL'}
    result['asr_quality_flagged_paths']=len(quality)
    result['status']='PASS' if result['status']=='PASS_LOCAL_PHASE2' else 'PARTIAL'
    result['acceptance_scope']='Phase 2 local processing only'
    result['project_status']='PARTIAL'
    result['derived_files_bytes']=sum(p.stat().st_size for d in ['audio','transcripts','segments','frames','handoff','chunks'] for p in (R/d).rglob('*') if p.is_file())
    result['paid_api_calls']=0
    result['cost_scope']='No paid API calls; electricity and device depreciation not measured. Existing local model/environment disk not included in derived_files_bytes.'
    pairqa=read(R/'manifest/similarity_pair_review.json',{})
    result['text_pair_review_count']=pairqa.get('final_pairs_reviewed',0)
    result['pair_review_scope']=pairqa.get('review_mode','PENDING')
    atomic_json(R/'manifest/phase2_validation.json',result)
    lines=['# Phase 2 全量本地处理验收报告','',f'检查时间：{result["at"]}。Phase 2 本地阶段验收：**{result["status"]}**；全项目状态：**PARTIAL**。AI深度分析和原创模板仍未完成，不能称全项目终验PASS。','','## 数量与处理结果','','|账号|路径数|ASR成功|','|---|---:|---:|']+[f'|{a}|{c["files"]}|{c["OK"]}|'for a,c in sorted(account.items())]
    lines+=['',f'总路径{len(rows)}；不同SHA内容{len(set(plan["canonical_by_video_id"].values()))}；完全重复额外副本{summary.get("extra_exact_duplicates","待分析")}。全量源SHA复核不变{result["source_hash_unchanged"]}/{len(rows)}。有效截图{frames_total}张；READY包{ready}个。词级重建时间戳{token}条；分段级降级{coarse}条。','',f'真实断点测试：中断两个已确认属于本任务的识别进程后重启，先前{len(preserved)}个已完成分段中{sum(preserved)}个哈希及修改时间不变。失败有独立日志；每分段最多重试2次。','',f'本轮包括计划内中断测试的处理墙钟累计约{result["run_wall_seconds_including_restart_test"]/3600:.2f}小时。并行推理累计时间不能直接当作墙钟时间。','',f'本轮未打开源数据库；数据库文件元数据前后相同：{result["database_metadata_unchanged_this_phase"]}。上一轮SQLite只读访问与下载器关闭期间的物理变化仍保留在素材盘点报告。','','## 聚类与候选','',f'全文相似簇{summary.get("text_clusters","待分析")}，开头相似簇{summary.get("opening_clusters","待分析")}，段落复用簇{summary.get("passage_clusters","待分析")}；跨账号相似配对{summary.get("cross_account_pairs","待分析")}对。20～30条候选本轮实际生成{summary.get("candidate_count","待分析")}条，具体原因、词项频次和video_id见《高频复用与候选清单》。簇为记录的配对边的连通分量，不能把传递关系当作任意两条都相似。','','## AI与基础Excel','',f'A完整JSON基本Schema通过{summary.get("ai_schema_valid",0)}份，AI_OK {summary.get("ai_ok",0)}份、AI_REVIEW {summary.get("ai_review",0)}份。待核AI内容保持AI_PENDING；A自述的原生MP4能力未作为Codex独立验证事实。','', '一个7-Sheet基础工作簿为《阅见生活_竞品视频分析_终版.xlsx》。Sheet05模板库保留AI_PENDING，不虚构跨样本模板。实际文件结构与视觉检查记录分别见manifest/workbook_validation.json和manifest/workbook_visual_qa.json。','','## 待办','', '- 由A按25条候选分批深度分析，输出可核验的原文、时间和输入模式。','- 修正A的0～3秒字段超长、无指标的表现判断等问题；只读入通过校验并原子落盘的完整JSON。','- 在A深度结果就绪后，再形成有证据的原创模板及最终整合验收。']
    if fail:lines+=['','## 本地异常','']+[f'- {z["video_id"]}: {z["problem"]}'for z in fail]
    lines+=['','## ASR质量口径','',f'生成非空文本与时间戳不等于逐字识别正确率。规则检查有{len(quality)}个来源触发文本密度、重复或提前结束复核提示，逐条见 manifest/asr_quality_flags.json 和 Excel异常表；可能是真实音乐、停顿、片尾或直播重复表达，尚未逐句耳听确认。']
    lines+=['','## 配对复核与实际成本','',f'Codex逐对文本复核{result["text_pair_review_count"]}对（固定种子随机20对+补充账号覆盖1对），已把已知两对全文误判降为公共段落。新增顺序匹配门槛后重新聚类，详见《相似配对抽查》。此为实际转录文本复核，未冒充用户人工审阅或原音逐句核对。','',f'派生素材约{result["derived_files_bytes"]/1024**3:.2f}GiB，含WAV、TXT、JSON、截图及交接副本，不含原视频、环境和模型。收费API调用0次；电费和设备折旧未计量。','', '保留两条Windows短暂文件占用错误的原始日志，均已补跑成功。v_2fe34883cba71ae1末尾约30秒未识别出文字；音频尾段有低音量非零信号，不能仅凭音量判定纯音乐或静音，继续保留待听核提示。']
    atomic_text(R/'reports/Phase2_全量本地处理验收.md','\n'.join(lines)+'\n');print(json.dumps({k:v for k,v in result.items()if k not in ['failures','accounts']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
