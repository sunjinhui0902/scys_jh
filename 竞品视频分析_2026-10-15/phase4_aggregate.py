import json, collections, re
from pipeline import OUTPUT_DIR as R, atomic_json, atomic_text, now
def read(p):return json.loads(p.read_text(encoding='utf-8'))
records=[read(p)for p in sorted((R/'manifest/phase4_records').glob('v_*.json'))]
original=read(R/'manifest/phase4_input_snapshot/account_summary.json');accounts=[]
for account in original['accounts']:
    rs=[z for z in records if z['account']==account];assert len(rs)in[4,5]
    intro=[z for z in rs if z['normalized']['bridge']['present']]
    shopping=[z for z in rs if z['normalized']['cta']['present']and re.search(r'橱窗|商品|链接|左下角|放下面',z['normalized']['cta']['text'])]
    accounts.append({'account':account,'sample_count':len(rs),'ai_ok':sum(z['status']=='AI_OK'for z in rs),'ai_review':sum(z['status']=='AI_REVIEW'for z in rs),'book_introduction_count':len(intro),'shopping_guidance_count':len(shopping),'sample_ids':[z['video_id']for z in rs],'introduction_evidence_ids':[z['video_id']for z in intro],'shopping_evidence_ids':[z['video_id']for z in shopping],'A_original_summary':original['accounts'][account],'checked_visual_style':'；'.join(dict.fromkeys(z['normalized']['visual_and_audio']['visual_type']for z in rs)),'policy':'仅25条目的抽样结构，不外推全账号商业比例；借阅/关注不等于购物引导，出现引导不等于真实销量'})
assert set(original['accounts'])=={r['account']for r in records}
atomic_json(R/'manifest/phase4_account_summary.json',{'at':now(),'A_declared_total':original['total_candidates_analyzed'],'actual_total':len(records),'accounts':accounts,'original_reference':str(R/'analysis_a/account_summary.json'),'status':'CORRECTED_DERIVED_SUMMARY'})
templates=[
 {'id':'T01','name':'情境难题→表达练习→阅读工具','status':'研究结构可用','audience':'推断：想改善临场表达的读者','books':'沟通/表达工具书','seconds':'90～150秒（测试建议）','hook':'呈现一个原创、具体的沟通难题','story':'两种回应方案对照→解释选择理由→展示可练习步骤','bridge':'由“怎样练习”转向经核实的书中练习栏目','cta':'展示目录或合法自摄内页，邀请查看详情；不承诺学会后必然成功','visual':'原创人物演绎＋自摄图书；音色另行确认','topic':'临时接到额外任务时，怎样把优先级问清楚？','refs':['v_183328bf0ee8b458','v_7c9d47c6f0bcb117'],'risk':'不可照搬劝酒/神回复、原角色及声线；区分借阅剧情与购物促单','note':'两个同账号样本，推广效果未验证；书名/版本须核对'},
 {'id':'T02','name':'人物选择→事实叙事→群像阅读','status':'研究结构可用','audience':'推断：关注科学史与家庭阅读的读者','books':'有可靠来源的传记/科学史','seconds':'180～300秒（测试建议）','hook':'提出一个可追溯的人物选择或研究难题','story':'交代背景→还原关键选择→说明结果与代价；事实逐项溯源','bridge':'从单个人物的资料缺口转向书中相关篇章','cta':'说明目录、阅读难度与适合场景，邀请比较后选择','visual':'已授权史料或明确示意插画＋自摄目录；不得伪造历史照片','topic':'一次研究分工怎样改变了团队的工作方式？','refs':['v_21f58ae8ccf2ac26','v_1b225d87255676fa'],'risk':'史实、人物言行与图像来源须核；不把视频叙述直接当史实','note':'不复制40位/隐姓埋名年数等书中范围，除非实际版本支持'},
 {'id':'T03','name':'地标问题→解释证据→延伸阅读','status':'AI_REVIEW：单样本草案','audience':'推断：古建/城市文化爱好者','books':'城市史/建筑图解','seconds':'120～240秒（测试建议）','hook':'提出一个可查证的地标问题','story':'用两三项可靠资料解释形制或空间变化','bridge':'说明短视频解释边界，指向书中可核实的地图或章节','cta':'邀请看目录；只有真实价格已确认时才作价格比较','visual':'自摄地标/已许可地图与书页；示意图注明性质','topic':'一座城门的位置变化，怎样记录城市边界？','refs':['v_d3f3bf3980928b72'],'risk':'不沿用十三朝/门票价等未经独立核实的具体事实或价格','note':'A另引“第1期山西古建”未给video_id，未计作有效第二来源'},
 {'id':'T04','name':'认知问题→场景对照→章节导读','status':'研究结构可用','audience':'推断：关注商业阅读与个人学习的读者','books':'有明确内容边界的商业/思维读物','seconds':'60～90秒（测试建议）','hook':'提出可讨论的问题，避免“穷人都是认知差”等定论','story':'用虚构或已核实的场景比较不同做法，指出适用条件','bridge':'展示书中一个框架及其限制，说明适合什么阅读需求','cta':'邀请阅读目录和样章，不承诺收入、人生巅峰或少走十年弯路','visual':'原创情景与自摄图书，不复刻原片角色或封面动画','topic':'只看营业额，会漏掉哪些经营成本？','refs':['v_b1d211336b0f5ebb','v_734ec81ff3d7343f'],'risk':'无收益或投资效果保证；两个样本为同账号近似改稿，独立结构证据有限','note':'保留比较结构，剔除原A模板中的绝对化收益措辞'},
 {'id':'T05','name':'风景清单→知识缺口→阅读延伸','status':'研究结构可用','audience':'推断：喜欢地理与旅行阅读的人群','books':'地理图文/文旅知识图书','seconds':'180～300秒（测试建议）','hook':'明确自拟清单的范围与选择标准，避免冒充权威排名','story':'依同一标准介绍地点→比较差异→提出一个知识问题','bridge':'用书中地图、图像或解释满足问题，展示使用方式','cta':'给出看目录/商品详情的路径，互动邀请与购物引导分开','visual':'自摄/许可风景或注明示意的原创插画＋图书内容展示','topic':'沿一条河读三座城：地形怎样影响街巷？','refs':['v_d00cee56eff9e90d','v_ac516db0b5dced62','v_849c3889a3d48662'],'risk':'不把地理与长寿作因果营销，不承诺健康功效；原A健康模板改为阅读结构','note':'前两条有图书/商品线索，第三条作无商品引导对照；不复制成篇榜单文案'}
]
for t in templates:
    t['reference_A_template']=str(R/'analysis_a/原创带货模板库.md');t['evidence']=[{'video_id':r['video_id'],'bridge':r['normalized']['bridge'],'cta':r['normalized']['cta'],'segments_path':str(R/'segments'/f'{r["video_id"]}.aligned.json'),'record_path':str(R/'manifest/phase4_records'/f'{r["video_id"]}.json')}for r in records if r['video_id']in t['refs']]
    assert len(t['evidence'])==len(t['refs'])
atomic_json(R/'manifest/phase4_templates.json',{'at':now(),'template_count':len(templates),'research_usable':4,'needs_more_evidence':1,'origin':'All five A template structures imported and reduced to original abstract methods; new example topics are Codex proposals, not proven results','templates':templates})
lines=['# Phase 4 导入更正与待补证清单','', 'A原始25份JSON、账号总结、5套模板均已读取，原件未修改。以下导入结果保留原件、快照、逐字段更正和证据。','', '## 账号样本结构复算','','|账号|样本|引书/阅读推荐|明确商品引导|AI_OK|AI_REVIEW|','|---|---:|---:|---:|---:|---:|']
lines += [f'|{a["account"]}|{a["sample_count"]}|{a["book_introduction_count"]}|{a["shopping_guidance_count"]}|{a["ai_ok"]}|{a["ai_review"]}|'for a in accounts]
lines+=['','统计分母仅为25条深度样本；无播放/成交指标，不评价效果。A原“商业率”混合阅读、借阅与购物指引，故作为原始描述保留，不直接作为统计事实。','','## 单视频更正与未决项','']
for r in records:
    lines += [f'### {r["video_id"]}｜{r["account"]}｜{r["status"]}','', '- 已处理：'+'；'.join(r['corrections']) if r['corrections']else'- 无字段更正。']
    lines += ['- 待补证：'+'；'.join(r['unresolved_issues'])if r['unresolved_issues']else'- 无当前核验范围内的关键未决项。']
lines+=['','## A 后续补证重点','','1. 三条native_video分析需给出实际受支持的输入方式及可追溯证据；赵健120秒实帧为题字特写，不能据此声称看见老人伏案写字；林睿指定画面中的茶水等细节未得到实帧支持。','2. v_183328bf0ee8b458的120.185秒帧不是书封；请修正封面/出版社证据指向。','3. 两条名人逝世叙事尚未由本项目核实，不能作为原创生产事实；如保留该选题需另查可靠来源。','4. T03第二来源须补充真实video_id；不得用没有映射的“第1期”充当证据。','5. 单条ASR尾段v_2fe34883cba71ae1仍待听核，未把非空文本当作逐字正确率。']
atomic_text(R/'reports/Phase4_导入更正与待补证清单.md','\n'.join(lines)+'\n')
print(json.dumps({'accounts':[{k:v for k,v in a.items()if k not in ['A_original_summary','sample_ids','introduction_evidence_ids','shopping_evidence_ids']}for a in accounts],'templates':len(templates)},ensure_ascii=False,indent=2))

