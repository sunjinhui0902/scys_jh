# A执行任务：317份全文轻量分析，服务旅行地理选题库

## 范围和入口

共享目录：`D:\fuye\竞品视频分析_2026-10-15`。先校验`D:\fuye\竞品视频分析_2026-10-15\handoff\text_light_v1\READY.json`，再读取batch_plan.json和analysis_schema.json。
本轮逐篇分析317份SHA独立文字稿（保留332来源映射由Codex维护），不对317条视频逐镜头拆解。现有25条深度样本不抵扣本轮全文阅读；补充10条视频的任务可后置，如正在处理先完成当前单条原子落盘。

输入只含文字、原始标题、模型估计时间和书名规则提示，没有视频、音频或截图。仅在此前确认的文字输入范围和额度内工作，不新增API Key、收费API或外传授权。不得为了此次文字任务读取或上传原视频、音频、图片。遇额度/输入限制记录真实未完成项并暂停，不冒充完成。

## 按批次读全文

batch_plan列出全部批次。优先旅行地理候选和相关账号，最终必须覆盖全部317份。每个batch最多10个单元且核心全文不超过约18000字符；超长稿拆成多个单元，每个核心段最多约6000字符。不能只看标题、开头结尾或目录就填整篇标签。

读取batches/<batch_id>.json后，逐项核对inputs/<unit_id>.json的SHA-256。每个单元包含完整core_text和可回溯segment_id。邻接context只辅助理解，不重复计入核心覆盖。逐单元完整阅读、落盘；同视频全部单元完成后再合并成单视频结果，不丢掉长稿尾部。若某篇包含多个话题，保留主要话题及覆盖限制，不把第一段当全文。

## 每条轻量字段

按analysis_schema.json输出，建议单视频摘要控制在约400～700个汉字（不含必要证据与长稿覆盖记录），不写逐镜头、配乐或声线分析：

1. theme、最多5个topic_tags；audience_inferred明确为推断。
2. books逐项区分仅引用、明确阅读推荐、明确购物引导、普通词误判、未知；另标ASR／仅标题／两者皆有。书名候选不是事实，“对答如流”可能只是普通词；不能把标题标签算进口播。
3. opening仅摘真实文本开头、分类其写法，scope固定“文本开头摘录，不等于真实0～3秒音频钩子”。后续长稿单元没有全文开头时写空并解释。
4. narrative_pattern用简明结构描述全文；bridge写present（true/false/null）、type、quote、evidence及scope=ASR；false仅表示完整转录中未找到，不声称视频没有视觉引导。未读全不得判全片无。
5. cta分开：购物／阅读建议／借阅剧情／关注／下一集／互动／其他。每项要短引文及分段证据，不能混成购物CTA。
6. value_claims逐项写claim、provenance（素材明确声称或AI推断）、verification_status（未核实／无法判断）；不替素材背书。
7. original_angles最多2条，是新问题、新场景或新观察角度，不能沿用独特竞品开头或拼接整段文案。
8. risks记录ASR专名问题、名人叙事、历史数据或商品歧义；travel_relevance为高/中/低/无法判断，属于主题适配推断，不是效果评分。

evidence每项必须有unit_id、核心segment_ids和不超过100字的原文短摘录，时间仅沿用对应模型时间。quote必须确实存在于这些分段拼接文本中，不自行润色原话。未知留空/标未知，有关键冲突用AI_REVIEW；未完成为AI_PENDING。模型说法、书名、历史与地理事实均未被本任务自动证实。

## 保存、校验与恢复

只写`D:\fuye\竞品视频分析_2026-10-15\analysis_a\text_light_v1`：
- units/<unit_id>.json：record_kind=unit；unit_ids只含该单元。
- videos/<video_id>.json：record_kind=video；必须列出该视频全部unit_ids及各输入SHA，all_assigned_text_read=true才可申报AI_OK。
- batches/<batch_id>.json：本批计划、实际完成、状态、文件SHA、错误及实际运行时间。

先写同目录临时文件，合法JSON和Schema校验通过后原子重命名。Schema只是结构检查，不能替代证据核对。断点恢复跳过输入哈希一致且已校验的最终结果；不读写半成品，不伪造分析时间。旧analysis_a原件、supplement_01、manifest、transcripts、frames、clusters、reports、content_library及Excel均不可修改。

## 全部可处理条目完成后

仍只在text_light_v1输出：
1. 全量文字规律.json：实际逐篇完成数、AI_OK/REVIEW/PENDING、主题/文本结构/引用/荐书/购物分别计数，聚合保留video_id列表和分母，不混入全部332来源重复计数。
2. 旅行地理选题增补.json：优先“大美中国／365日走遍中国类”读物。可只读`D:\fuye\竞品视频分析_2026-10-15\content_library\旅行地理选题库.json`避免重复；为既有30题提供有据的支持/调整/删除建议，每项带source_video_ids和证据角色（结构参考、素材声称、已核事实不得混用）。确有新角度再补最多10题，不凑数、不覆写Codex选题库。
3. 文本模块结构库.json：开头、故事推进、引书、CTA分别抽象成结构及原创示例，原话仅短摘作证据，不把竞品段落当可直接发布素材。
4. 完成清单.json：317个video_id逐项状态、单元覆盖、最终路径、SHA、限制、失败和真实运行时间，最后原子落盘。未完成不能计入完成。

本轮只做文字分析和选题增补，不写成稿、不制作或发布视频、不扩大为全量视频拆解。完成后暂停，报告落盘数量和路径，由Codex核验后更新文案参考库、模块库与单个7-Sheet总表。
