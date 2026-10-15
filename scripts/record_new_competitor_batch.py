"""One-batch report/library/control reconciliation. A data remains AI_PENDING."""
from __future__ import annotations
import collections, datetime as dt, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'竞品视频分析_2026-10-15';BATCH='new_accounts_2026-10-16';B=R/'increments'/BATCH;H=R/'handoff'/BATCH
sys.path.insert(0,str(R))
from pipeline import atomic_json,atomic_text,sha256,now
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def rows(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf-8').splitlines() if s]
def main():
    at=now();jobpath=R/'manifest'/f'{BATCH}_job.json';job=read(jobpath);new=rows(B/'manifest/manifest.jsonl')
    if job.get('verified_text_semantic',0) or job.get('verified_representative_deep',0):
        raise RuntimeError('Base-only recorder: A results have been accepted; adapt an integration recorder rather than resetting verified counts')
    job['inventory']=read(B/'manifest/inventory_complete.json')
    stats=read(B/'manifest/statistics_summary.json');qa=read(B/'manifest/input_qa.json');book=read(B/'manifest/workbook_export.json')
    source=read(B/'manifest/source_integrity.json');resume=read(B/'manifest/resume_test_result.json');plan=read(H/'batch_plan.json')
    assert (H/'READY.json').is_file() and book['visual_qa']=='PASS' and qa['visual_review']=='PASS'
    if job.get('basic_processing_completed_at') is None:job['basic_processing_completed_at']=at
    job['status']='A_HANDED_OFF' if job.get('handoff_at') else ('HANDOFF_BLOCKED' if job.get('handoff_status') in ['DESKTOP_LOCKED','WAITING_A_AVAILABLE','HANDOFF_NOT_SENT'] else 'LOCAL_COMPLETE_READY_FOR_A')
    job.update(updated_at=at,local_ready_count=len(new),local_frames=len(new)*4,new_candidates=stats['candidates'],
        handoff_ready_path=str(H/'READY.json'),workbook_sha256=book['workbook_sha256'],local_qa_report=str(R/'reports'/f'{BATCH}_基础处理与交接验收.md'))
    atomic_json(jobpath,job)
    features=read(B/'clusters/video_features.json');clusters=read(B/'clusters/current_text_clusters.json');index=[]
    batchof={x['video_id']:batch['batch_id'] for batch in plan['text_batches'] for x in batch['videos']}
    recs={x['video_id']:x for x in plan['records']}
    for x in new:
        v=x['video_id'];text=(B/'transcripts'/f'{v}.txt').read_text(encoding='utf-8').strip()
        index.append({'video_id':v,'account':x['account'],'sha256':x['sha256'],'all_source_mappings':[{'video_id':v,'account':x['account'],'source_path':x['source_path']}],
            'duration_s':x['duration_s'],'source_title':Path(x['source_path']).stem,'transcript_path':str(B/'transcripts'/f'{v}.txt'),
            'segments_path':str(B/'segments'/f'{v}.aligned.json'),'text_characters':len(text),'opening_asr_excerpt':text[:120],
            'book_rule_candidates':features[v]['book_candidates'],'rule_cluster_ids':[c['cluster_id'] for c in clusters if v in c['new_video_ids']],
            'legacy_deep_status':'AI_PENDING','latest_deep_status':'AI_PENDING','latest_deep_record':None,'text_semantic_status':'AI_PENDING',
            'semantic_output_path':str(R/'analysis_a'/BATCH/batchof[v]/f'{v}.json'),'unit_ids':[z['unit_id'] for z in recs[v]['text_units']],
            'facts_verified':False,'sales_performance_verified':False,'latest_local_batch':BATCH})
    library=R/'content_library';subset=library/BATCH
    subset.mkdir(parents=True,exist_ok=True)
    atomic_text(subset/'文案索引.jsonl',''.join(json.dumps(z,ensure_ascii=False)+'\n' for z in index))
    fulltext=['# 新两账号83份ASR全文参考\n',
        f'本地处理完成于：{job["basic_processing_completed_at"]}。以下保留原ASR文字，供研究和溯源；未完成全文AI语义验收，不是原创成稿或已核实事实。专名、书名版本及逝世叙事等问题见本批质量清单。\n',
        '[索引](文案索引.jsonl) · [本批入口](开始使用.md)\n']
    for x in new:
        v=x['video_id'];fulltext += [f'\n## {x["account"]} · {v}\n',f'来源文件名：{Path(x["source_path"]).name}\n',
            f'时长：{x["duration_s"]:.3f}秒；文字语义：AI_PENDING。\n',
            (B/'transcripts'/f'{v}.txt').read_text(encoding='utf-8').strip()+'\n']
    full_path=subset/'全文参考库.md';full_content='\n'.join(fulltext)
    if not full_path.exists() or full_path.read_text(encoding='utf-8')!=full_content:atomic_text(full_path,full_content)
    main_index=library/'文案索引.jsonl';oldidx=rows(main_index);oldids={z['video_id'] for z in oldidx}
    add=[z for z in index if z['video_id'] not in oldids]
    if add:
        assert not oldids&{z['video_id'] for z in add}
        with main_index.open('ab') as f:f.write(''.join(json.dumps(z,ensure_ascii=False)+'\n' for z in add).encode('utf-8'))
    assert len(rows(main_index))==stats['combined_unique_contents']
    atomic_text(subset/'开始使用.md',f'''# 新两账号文案参考入口\n\n更新于：{at}。新增83份ASR全文及时间戳已就绪，**文字语义与代表深拆全部AI_PENDING**。这不是原创成稿库。\n\n- 失去壳的海龟50份，闲不住De宝33份；单份文字、分段、来源与SHA见[索引](文案索引.jsonl)。\n- [给A的任务](../../handoff/{BATCH}/发给A_两个新账号执行指令.md)覆盖全部全文，长稿按单元完整阅读；代表候选25条另行深拆。\n- [本批验收报告](../../reports/{BATCH}_基础处理与交接验收.md)；[同一7-Sheet总表](../../阅见生活_竞品视频分析_终版.xlsx)。\n- 原稿仅作研究与溯源；规则命中不等于已推荐/挂载商品，更不证明史实、版本或销量。选题和制作继续按项目当前内容执行标准及具体实书核验。\n''')
    entry=library/'开始使用.md';text=entry.read_text(encoding='utf-8')
    text=text.replace('317份全文已转录并建立索引；全量语义仍AI_PENDING，不能用基础统计代替逐篇理解。','400份独立内容全文已转录并建立索引（旧317＋新增83）；全量语义验收仍为0，不能用基础统计代替逐篇理解。')
    marker='## 2026-10-16 新两账号增量'
    if marker not in text:text+=f'\n\n{marker}\n\n[新增83份文案与A任务]({BATCH}/开始使用.md)已就绪；代表候选25条，AI尚未验收。现有35条深拆与6套模板沿用原口径。\n'
    atomic_text(entry,text)
    subset_entry=subset/'开始使用.md';se=subset_entry.read_text(encoding='utf-8')
    if '全文参考库.md' not in se:atomic_text(subset_entry,se+'\n[直接阅读83份完整ASR原文](全文参考库.md)，可按video_id、书名或关键词搜索；保留原始误识别，不当作可发布文案。\n')
    books=read(B/'clusters/book_frequencies.json');entities=read(B/'clusters/story_entity_frequencies.json');candidates=read(B/'clusters/deep_candidates.json')
    states=[read(B/'state'/f'{x["video_id"]}.json') for x in new]
    asr=sum(s['steps']['asr'].get('elapsed_s',0) for s in states)
    local=sum(sum(step.get('elapsed_s',0) or 0 for key,step in s['steps'].items() if key!='asr') for s in states)
    wall=(dt.datetime.fromisoformat(job['basic_processing_completed_at'])-dt.datetime.fromisoformat(job['basic_processing_started_at'])).total_seconds()
    timing={'started_at':job['basic_processing_started_at'],'finished_at':job['basic_processing_completed_at'],'pipeline_wall_seconds':wall,
        'source_duration_seconds':job['inventory']['total_duration_s'],'successful_chunk_inference_seconds_sum':asr,
        'audio_and_frame_steps_seconds_sum':local,'successful_asr_rtf':asr/job['inventory']['total_duration_s'],
        'note':'进程并行，步骤累计不等于墙钟；真实墙钟包含准备、模型重载、断点测试、排队与验收，未记录的中断中计算不冒充零成本',
        'additional_paid_api_calls_by_Codex':0,'A_cost':'未核；仅允许既有入口与已批准范围'}
    atomic_json(B/'manifest/timing_summary.json',timing)
    report=f'''# 两个新账号｜基础处理与交接验收\n\n更新于：{at}。**转录/截图/输入Schema门禁PASS；不变性核验PARTIAL（SQLite辅助文件指纹变化）；全项目PARTIAL。新增A文字与代表深拆验收均为0，不能称83条已完成AI分析。**\n\n## 盘点与覆盖\n\n|账号|来源文件|有效媒体信息/音轨|SHA独立内容|本地转录就绪|4帧|文字语义验收|代表深拆验收|\n|---|---:|---:|---:|---:|---:|---:|---:|\n|失去壳的海龟|50|50|50|50|200|0|0|\n|闲不住De宝|33|33|33|33|132|0|0|\n\n本批83份均无批内或对旧317份的SHA完全重复；现合计415来源、400独立内容。旧来源video_id和全部映射保留；原manifest保持历史版本，当前联合清单为`manifest/current_manifest.jsonl`。有效性核验包含ffprobe、音频抽取与4帧解码，不等于全视频逐帧播放验收。\n\n## 实际运行与成本\n\n- 素材累计{timing['source_duration_seconds']/3600:.2f}小时；本地流水线实际墙钟{wall/60:.2f}分钟，起止见[运行记录](../increments/{BATCH}/manifest/timing_summary.json)。03:10已触发接续，流水线计时从清单建立起算。\n- 成功分块ASR累计{asr/60:.2f}分钟，系数{timing['successful_asr_rtf']:.4f}×素材时长；音频/帧步骤累计{local/60:.2f}分钟。两个CPU进程并行；累计推理时间不等于墙钟，不含未落盘中断中的计算。\n- 复用Python3.10/FunASR1.4.16/Torch2.14.1与本机模型、FFmpeg，不新增视频分析框架；另在被忽略的.local/schema-validation内放置轻量JSONSchema校验依赖，未更改ASR环境。Codex未调用额外收费API，也未上传原视频/音频。A既有服务费用本轮未核。\n\n## 真实验收\n\n- 输入Schema {qa['input_schema_valid']}份、逐段重建全文{qa['complete_transcripts_reconstructed']}份、全文单元{qa['text_units_coverage_verified']}个均核对；所有{qa['frame_images_verified']}张图均可解码。\n- 10条分层样本按新两账号各5条抽取，文本首尾、时间、帧图记录见[10条样本](../increments/{BATCH}/manifest/sample_10_quality.json)。**未人工逐字听核，不提供字错误率或伪造识别准确率**；已见专名同音错字和未核实逝世叙事，具体见质量清单，不能直接作为原创事实。\n- 真实停止本批worker0并重启：重启前77个已落盘检查点SHA/大小/mtime不变，中断视频从缓存完成，见[续跑证据](../increments/{BATCH}/manifest/resume_test_result.json)。未模拟断电或原子重命名中的硬故障。\n- 原视频{source['source_sha_size_mtime_unchanged']}/{source['sources_checked']}个SHA/大小/mtime保持，目录成员核对结果为{source['directory_membership_matches']}；冻结旧A/manifest {source['historical_A_and_manifests_unchanged']}/{source['historical_files_checked']}保持。主库指纹保持，WAL和SHM哈希有变化，原因未确认；本轮脚本未打开或改写数据库，不能据此宣称数据库辅助文件不变。\n- 同一7-Sheet总表415行，380 AI_PENDING、31限定范围AI_OK、4 AI_REVIEW；旧字段与链接保留，Sheet05旧6套模板未增加虚构新模板。程序核对与6个变更视图静态渲染已完成；未执行原生Excel交互验收。\n\n## 重复与候选\n\n新相关配对：全文相似{stats['new_fulltext_pairs']}、开头相似{stats['new_opening_pairs']}、共享段落{stats['new_passage_pairs']}；跨账号配对{stats['new_cross_account_pairs']}。类型可能重合，不能相加为唯一视频数。涉及新素材的簇按类型为{stats['clusters_touching_new_by_kind']}，当前联合簇为{stats['current_cluster_count_by_kind']}。连通分量可传递，公共片段也可能是CTA；**不等于语义同稿或爆款、销量证据**。旧317语料的旧边保留，新边在当前语料计算，口径详见[方法](../increments/{BATCH}/clusters/methodology.json)。\n\n25条代表候选：失去壳的海龟13、闲不住De宝12。按书名候选差异、购物词线索、相似线索与低购物词对照选取；推荐/商品入口、内容价值仍待A全文判断。\n\n|video_id|账号|候选原因|\n|---|---|---|\n'''
    report+='\n'.join(f'|{c["video_id"]}|{c["account"]}|{c["reason"].replace("|","/") }|' for c in candidates)
    report+='\n\n## 高频书名候选与故事线索\n\n书名是出现或来源标题线索，尚未认定为推荐书、挂载商品或真实版次；不同词项可在同一条出现，不相加计算视频数。\n\n|候选词|涉及新独立视频|ASR命中|仅来源标题|\n|---|---:|---:|---:|\n'
    report+='\n'.join(f'|{z["term"]}|{z["new_unique_video_count"]}|{z["asr_video_count"]}|{z["title_only_video_count"]}|' for z in books[:20])
    report+='\n\n实体/故事线索前列：'+ '；'.join(f'{z["term"]} {z["new_unique_video_count"]}份' for z in entities[:15])+'。这些是词典出现数，不是已核实的完整故事计数。\n'
    report+=f'''\n## 交接与下一步\n\n- 全量文字：83视频、{qa['text_units_coverage_verified']}阅读单元、{len(plan['text_batches'])}小批；先5条自检，再顺序完成其余文字与25条代表候选深拆。全部未验收AI字段保留AI_PENDING。\n- [READY包](../handoff/{BATCH}/READY.json)；[A指令](../handoff/{BATCH}/发给A_两个新账号执行指令.md)。只用已批准的文本/静态帧范围，A独占analysis_a/{BATCH}/独立子批次。\n- 当前桌面交接状态：**{job['handoff_status']}**；真实handoff_at：{job.get('handoff_at')}；审核到期：{job.get('review_due_at')}。没有成功交接证据时不启动3小时审核计时。\n- [同一总表](../阅见生活_竞品视频分析_终版.xlsx)、[文案索引](../content_library/{BATCH}/开始使用.md)、[协作总控](../../docs/竞品分析协作总控.md)。\n- 原创生产可借鉴“具体问题→事实/故事→实书可补充的内容→阅读场景”方法，需按自己商品目录/样页独立写；本批不直接复刻竞品长稿，也不把素材声称的销量/版本/史实当已核事实。\n'''
    report+='\n\n渲染说明：程序保存全部预览后退出码为1；保存的PNG与XLSX已独立核验，未将此过程当作原生Excel交互验证。\n'
    report+='\n## 新增质量问题明细\n\n'
    report+='\n'.join(f'- `{z["video_id"]}`（{z["account"]}）：{z["issue"]}' for z in read(B/'manifest/local_review_issues.json'))
    report+=f'\n\n逐帧/分段证据见[质量清单](../increments/{BATCH}/manifest/local_review_issues.json)；数据库前后指纹见[不变性记录](../increments/{BATCH}/manifest/source_integrity.json)。\n'
    reportpath=R/'reports'/f'{BATCH}_基础处理与交接验收.md';atomic_text(reportpath,report)
    statepath=R/'manifest/collaboration_state.json';state=read(statepath)
    state.update(updated_at=at,latest_batch=BATCH+'_local',latest_accepted_deep_batch='supplement_01',
        source_paths=415,unique_contents=400,pending_source_paths=380,unique_outside_deep_scope=365,
        workbook_sha256=book['workbook_sha256'],workbook_validation=book)
    state['current_account_source_counts']=stats['combined_account_sources']
    state['latest_source_integrity']=source
    state['text_semantic']['pending_unique']=400
    state['text_semantic']['old_prepared_scope']='units=328,batches=38 are the historical text_light_v1 scope (317 contents)'
    state['text_semantic']['new_batch']={'batch_id':BATCH,'pending_unique':83,'units':qa['text_units_coverage_verified'],'batches':len(plan['text_batches']),'verified_complete':0}
    state['scheduled_increment'].update(status=job['status'],handoff_status=job['handoff_status'],handoff_at=job.get('handoff_at'),review_due_at=job.get('review_due_at'),review_automation_id=job.get('review_automation_id'))
    state['current_local_batch']={'batch_id':BATCH,'at':job['basic_processing_completed_at'],'new_sources':83,'new_unique':83,'local_ready':83,'frames':332,
        'text_semantic_verified':0,'deep_verified':0,'candidates':25,'report':str(reportpath),'source_integrity':str(B/'manifest/source_integrity.json')}
    state['next_A']='优先按new_accounts_2026-10-16的READY做83全文轻分析及25代表候选深拆，先5条自检；旧317待办保留，不自动启动'
    state['next_Codex']=f'实际交接后3小时审核；当前交接{job["handoff_status"]}；到期{job.get("review_due_at")}；仅接收原子最终文件并独立校验Schema、SHA、引用与覆盖'
    state['entry_paths']['latest_report']=str(reportpath);atomic_json(statepath,state)
    current=R/'reports/最终验收报告.md';history=R/'reports/history/最终验收报告_新两账号之前_2026-10-16.md'
    if not history.exists():atomic_text(history,current.read_text(encoding='utf-8'))
    unresolved='\n'.join(f'- `{z["video_id"]}`（{z["account"]}）：'+ '；'.join(z['issues']) for z in state['unresolved_samples'])
    atomic_text(current,f'''# 阅见生活竞品分析｜当前最终验收报告\n\n更新于：{at}。**全项目PARTIAL；新增两账号的本地基础门禁PASS，A结果待验收。**\n\n## 当前口径\n\n- 415来源、400个SHA独立内容；全量本地转录/时间戳及1660帧已就绪。旧332来源＋新增83，全部保留video_id与来源映射。\n- 代表深拆仍35条，31限定范围可用、4待核；380来源AI_PENDING。新增83尚无已验收深拆，不把25个候选计入完成数。\n- 全文语义验收0/400；旧317待办保留，新增83优先交A，按实际完整阅读、证据与Schema核验计数。\n- 新批本地运行、来源指纹、断点测试、25候选与高频线索详见[本批验收]({reportpath.name})。\n- 原创选题、试做及15城v2沿用各自任务状态，本批未新增原创成稿或可发布视频。\n- 结构模板仍6套，5研究参考＋1单样本草案；不以规则统计替代新模板分析，不证明营销效果。\n\n## 当前交接\n\n状态：{job['handoff_status']}；handoff_at={job.get('handoff_at')}；review_due_at={job.get('review_due_at')}。成功交接后3小时独立审核A的合格最终文件，再判断是否扩批。\n\n## 保留的旧未决项\n\n{unresolved}\n\n历史A原子交付过程/真实耗时证据缺项、ASR专名/尾段逐字听核未量化、历史数据库SHM差异仍保留；本批指纹一致不能消除这些历史限制。新增本地质量待核{stats['local_review_issues']}项详见增量异常清单。\n\n## 入口\n\n- [同一7-Sheet总表](../阅见生活_竞品视频分析_终版.xlsx)\n- [400份独立文案索引](../content_library/文案索引.jsonl)\n- [协作总控](../../docs/竞品分析协作总控.md)\n- [新批前的历史验收](history/{history.name})\n''')
    current_text=current.read_text(encoding='utf-8').replace('新增两账号的本地基础门禁PASS','新增转录/截图/Schema门禁PASS，数据库辅助指纹变化待核')
    atomic_text(current,current_text)
    control=ROOT/'docs/竞品分析协作总控.md';text=control.read_text(encoding='utf-8')
    text=text.replace('|原素材|332来源／317SHA内容；全量本地基础处理已完成|','|原素材|415来源／400SHA内容；旧332＋新增83来源，全量本地基础就绪|')
    text=text.replace('|全量文字轻分析|0/317已验收；328单元／38批就绪，AI_PENDING；不以代表深拆抵扣|',f'|全量文字轻分析|0/400已验收；旧317待办保留，新增83（{qa["text_units_coverage_verified"]}单元/{len(plan["text_batches"])}批）优先，均AI_PENDING|')
    text=text.replace('## 2026-10-16 03:10｜新增两账号的定时接续','## 2026-10-16 03:10｜新增两账号的定时接续（历史计划登记）')
    start='<!-- NEW_ACCOUNTS_2026_10_16_STATUS_START -->';end='<!-- NEW_ACCOUNTS_2026_10_16_STATUS_END -->'
    block=f'''{start}\n## 新两账号｜最新执行状态\n\n更新于：{at}。本地基础83/83就绪，新增332帧，候选25；旧35条深拆/31可用/4待核保留。**全项目PARTIAL，新增文字与代表AI验收均0。**\n\n- 失去壳的海龟50、闲不住De宝33，SHA无批内或跨旧完全重复。合计415来源/400独立内容；全文索引400份。\n- 当前A交接：{job['handoff_status']}；实际交接{job.get('handoff_at')}；审核到期{job.get('review_due_at')}。\n- [本批验收](../竞品视频分析_2026-10-15/reports/{reportpath.name})；[READY](../竞品视频分析_2026-10-15/handoff/{BATCH}/READY.json)；[新增文库](../竞品视频分析_2026-10-15/content_library/{BATCH}/开始使用.md)。\n- Codex只导入稳定最终文件；A按独立子批次执行；旧317全文待办不在本次启动。无新A验收，不添加模板或原创成稿完成数。\n{end}'''
    if start in text:text=text[:text.index(start)]+block+text[text.index(end)+len(end):]
    else:text+='\n\n'+block+'\n'
    new_risks='\n本批质量待核（独立于旧4条深拆AI_REVIEW）：\n'+ '\n'.join(f'- `{z["video_id"]}`：{z["issue"]}' for z in read(B/'manifest/local_review_issues.json'))+'\n- 下载主库指纹保持；WAL/SHM本轮哈希变化，原因未确认，脚本未打开数据库。\n'
    text=text.replace(end,new_risks+end)
    atomic_text(control,text)
    runbook=ROOT/'docs/竞品分析_新账号夜间接续_2026-10-16.md';rt=runbook.read_text(encoding='utf-8')
    rt=rt.replace('## 当前安排','## 00:23登记的原定安排')
    rs='<!-- NIGHT_RUN_LATEST_START -->';re='<!-- NIGHT_RUN_LATEST_END -->'
    result=f'{rs}\n## 最新执行结果\n\n更新于{at}：83条本地处理/332帧/101全文单元/25候选已就绪，总表415来源、400独立内容。新A验收仍0；质量与数据库辅助指纹问题见当前验收报告。A状态{job["handoff_status"]}，实际交接{job.get("handoff_at")}，审核安排{job.get("review_scheduled_for")}，审核任务{job.get("review_automation_id")}。\n\n`scripts/record_new_competitor_batch.py`只适配基础处理及交接记录；A验收后应按真实数据适配，不能复跑重置AI计数。\n{re}'
    if rs in rt:rt=rt[:rt.index(rs)]+result+rt[rt.index(re)+len(re):]
    else:rt+='\n\n'+result+'\n'
    atomic_text(runbook,rt)
    events=R/'manifest/analysis_batches.jsonl';ids={x['batch_id'] for x in rows(events)}
    event_id=BATCH+'_local'
    if event_id not in ids:
        event={'batch_id':event_id,'at':job['basic_processing_completed_at'],'event_type':'LOCAL_BASE_COMPLETED','status':'PARTIAL','local_gate':'PASS',
            'new_sources':83,'new_unique_contents':83,'local_ready':83,'frames':332,'new_samples':0,'reviews':0,'sample_count':35,'ai_ok':31,'ai_review':4,
            'text_semantic_verified':0,'deep_verified':0,'workbook_sha256':book['workbook_sha256'],'note':'新增两账号完成基础处理/全文分包/25候选，A字段全AI_PENDING；不计新增深拆或原创'}
        event['local_gate']='PARTIAL_DATABASE_AUX_CHANGED'
        event['transcript_frames_schema_gate']='PASS'
        with events.open('a',encoding='utf-8',newline='') as f:f.write(json.dumps(event,ensure_ascii=False)+'\n')
        with (ROOT/'05_爆款知识库与复盘/06_竞品分析更新日志.md').open('a',encoding='utf-8',newline='') as f:f.write(f'\n\n## {event["at"]}｜新增两账号本地基础完成\n\n失去壳的海龟50＋闲不住De宝33，83来源/83SHA独立，转录/时间戳/332帧就绪，25代表候选，全文语义与深拆验收新增0。累计415来源/400内容；旧35深拆、31可用/4待核保留。全项目PARTIAL，实际交接与3小时审核时间以[总控](../docs/竞品分析协作总控.md)为准。[本批报告](../竞品视频分析_2026-10-15/reports/{reportpath.name})。\n')
    handoff_event_id=BATCH+'_handoff'
    if job.get('handoff_at') and handoff_event_id not in ids:
        event={'batch_id':handoff_event_id,'at':job['handoff_at'],'event_type':'A_HANDOFF_CONFIRMED','status':'A_HANDED_OFF',
            'new_samples':0,'reviews':0,'sample_count':35,'ai_ok':31,'ai_review':4,
            'A_conversation_title':job['A_conversation_title'],'A_conversation_id':job['A_conversation_id'],
            'review_scheduled_for':job['review_scheduled_for'],'review_automation_id':job['review_automation_id'],
            'note':'真实桌面新对话已接收并显示Working；新增AI验收仍0，不改变35条深拆口径'}
        with events.open('a',encoding='utf-8',newline='') as f:f.write(json.dumps(event,ensure_ascii=False)+'\n')
        with (ROOT/'05_爆款知识库与复盘/06_竞品分析更新日志.md').open('a',encoding='utf-8',newline='') as f:
            f.write(f'\n\n## {job["handoff_at"]}｜A桌面交接已确认\n\nAntigravity的fuye项目中新建“{job["A_conversation_title"]}”，界面已显示Working并读取总控。83全文/25候选已交接，新增AI验收仍0。一次性审核安排{job["review_scheduled_for"]}，任务{job["review_automation_id"]}；原03:10启动任务已暂停。\n')
    atomic_json(B/'manifest/batch_closeout.json',{'at':at,'status':'RECORDED','source_count':415,'unique_contents':400,'indexed_contents':len(rows(main_index)),
        'workbook_sha256':book['workbook_sha256'],'new_deep_verified':0,'new_text_verified':0,'handoff_status':job['handoff_status']})
    print('CLOSEOUT_RECORDED',job['status'],flush=True)

if __name__=='__main__':main()
