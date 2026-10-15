"""Publish one validated batch into the shared status, journal and document entries."""
import argparse
import collections
import json
import re
from pathlib import Path

from integrate_competitor_supplement import ROOT, R, atomic, fingerprint, read, stamp


def text(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(value, encoding='utf-8')
    tmp.replace(path)


def link(path, label):
    return f'[{label}]({Path(path).as_posix()})'


def archive(path, label):
    p = Path(path)
    out = R / 'reports/history' / label
    if p.exists() and not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(p.read_bytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--batch-id', required=True)
    ap.add_argument('--summary', required=True, type=Path)
    args = ap.parse_args()
    if args.batch_id != 'supplement_01':
        raise SystemExit('This report adapter is for supplement_01. Adapt the new batch facts before appending the shared journal; do not replay historical counts.')
    summary = read(args.summary)
    export = read(R / f'manifest/{args.batch_id}_export_state.json')
    verification = read(R / f'manifest/{args.batch_id}_workbook_validation.json')
    integrity = read(R / f'manifest/{args.batch_id}_integrity.json')
    assert verification['status'] == 'PASS'
    workbook = R / '阅见生活_竞品视频分析_终版.xlsx'
    assert fingerprint(workbook)['sha256'] == export['workbook_sha256']
    records = summary['records']
    templates = read(R / 'manifest/latest_templates.json')
    journal_path = R / 'manifest/analysis_batches.jsonl'
    entries = [json.loads(s) for s in journal_path.read_text(encoding='utf-8').splitlines()] if journal_path.exists() else []
    if any(e.get('input_digest') == export['input_digest'] and e.get('workbook_sha256') == export['workbook_sha256'] for e in entries):
        print('RECORD_RESUME_SKIP: shared state and journal already record this batch')
        return
    if not entries:
        baseline = read(R / 'manifest/phase4_final_acceptance.json')
        entries.append({'batch_id': 'phase4_baseline', 'at': baseline['at'], 'new_samples': 25, 'reviews': 0,
                        'sample_count': 25, 'ai_ok': 20, 'ai_review': 5, 'status': 'PARTIAL',
                        'note': '历史Phase4验收，按当时口径保留；后续更正不回写旧结论'})
    now = stamp()
    draft_file = ROOT / '05_爆款知识库与复盘/05_五条试做稿.md'
    drafts = len(re.findall(r'^## S\d{2}｜', draft_file.read_text(encoding='utf-8'), re.M))
    ideas = read(R / 'content_library/旅行地理选题库.json')
    ledger_path = ROOT / '05_爆款知识库与复盘/00_两账号80条筛选台账.jsonl'
    ledger = [json.loads(s) for s in ledger_path.read_text(encoding='utf-8').splitlines()]
    pending = [{'video_id': v, 'account': z['account'], 'issues': z['unresolved_issues']}
               for v, z in records.items() if z['status'] == 'AI_REVIEW']
    counts = summary['combined_status_counts']
    entry = {'batch_id': args.batch_id, 'at': now, 'new_samples': summary['new_samples'], 'reviews': summary['reviews'],
             'sample_count': len(records), 'ai_ok': counts.get('AI_OK', 0), 'ai_review': counts.get('AI_REVIEW', 0),
             'status': 'PARTIAL', 'input_digest': export['input_digest'], 'workbook_sha256': export['workbook_sha256'],
             'note': '原件冻结后导入；修正路径/时间/书名/CTA；补齐T03文本第二来源；T06为单样本草案'}
    entries.append(entry)
    text(journal_path, ''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in entries))
    central = ROOT / 'docs/竞品分析协作总控.md'
    log_md = ROOT / '05_爆款知识库与复盘/06_竞品分析更新日志.md'
    report = R / 'reports/补充批次01_验收与更正报告.md'
    state = {'schema_version': 'collaboration-state-1.0', 'updated_at': now, 'project_status': 'PARTIAL',
             'latest_batch': args.batch_id, 'source_paths': 332, 'unique_contents': 317,
             'deep_sample_count': len(records), 'deep_status_counts': counts, 'pending_source_paths': summary['source_path_ai_pending'],
             'unique_outside_deep_scope': summary['unique_outside_deep_scope'],
             'text_semantic': {'verified_complete': 0, 'pending_unique': 317, 'units': 328, 'batches': 38,
                               'A_files_received': len(list((R / 'analysis_a/text_light_v1').glob('**/*.json')))},
             'targeted_screening': {'rows': len(ledger), 'scope': '林睿50＋锦绣30', 'include': 68, 'exclude': 12,
                                    'status': '定向筛选，不能替代逐篇语义标注'},
             'production': {'original_topic_drafts': len(ideas), 'single_point_candidates': 10,
                            'original_script_drafts': drafts, 'publish_ready_scripts': 0,
                            'note': '30题与10个单点候选可能重合，不相加为40个唯一选题；5稿来源于独立工作，不称本轮新写'},
             'templates': {'total': templates['template_count'], 'research_usable': templates['research_usable'], 'drafts': templates['drafts']},
             'unresolved_samples': pending,
             'primary_book_directions': ['大美中国类', '365日走遍中国类'],
             'product_status': '正式SKU、年份/版次、ISBN、目录/展示页和挂载尚待核实',
             'next_A': '按text_light_v1的READY与38批计划做317份全文轻分析，先旅行地理相关；不用重新拆35条视频',
             'next_Codex': '校验A文字输出的覆盖、原文、书名关系和状态；入库、更新总表/总控/日志；商品确认后再推进样片',
             'entry_paths': {'control': str(central), 'journal': str(log_md), 'workbook': str(workbook),
                             'latest_report': str(report), 'script_drafts': str(draft_file)},
             'workbook_sha256': export['workbook_sha256'], 'workbook_validation': verification,
             'source_integrity': integrity}
    atomic(R / 'manifest/collaboration_state.json', state)
    archive(R / 'reports/最终验收报告.md', '最终验收报告_Phase4_20261015.md')
    archive(R / 'reports/原创带货模板库_验收整理版.md', '原创带货模板库_Phase4_20261015.md')
    archive(R / 'README.md', '分析README_补充01前.md')
    account_table = ['|账号|来源/SHA唯一|深度样本|AI_OK|待核|引书/阅读|明确商品入口|软购买建议|', '|---|---|---:|---:|---:|---:|---:|---:|']
    for a in summary['accounts']:
        account_table.append(f"|{a['account']}|{a['source_count']}/{a['unique_count']}|{a['sample_count']}|{a['ai_ok']}|{a['ai_review']}|{a['book_introduction_count']}|{a['shopping_entry_count']}|{a['soft_purchase_count']}|")
    pending_md = '\n'.join(f"- `{p['video_id']}`（{p['account']}）：{'；'.join(p['issues'])}" for p in pending)
    batch_report = f'''# 补充批次01｜验收与更正报告

更新于：{now}。**本批已整合；项目状态PARTIAL。** A原始19文件保留，15份单视频结构满足现有Schema；10份源路径对象错误由导入版恢复为manifest中的字符串。Schema通过不代表证据正确。

## 完成范围

- 新增10条，复核旧5条；旧5条不重复计数。累计35条代表样本，31条限定范围AI_OK、4条AI_REVIEW；其他297来源／282独立内容未做深拆。
- 原25条中的20条沿用既有验收，旧5条和新10条本轮复核。新10条完整ASR及40张既有截图均由Codex读取核对；时间为模型估计，未全量逐句听核。
- 317份全文轻语义分析目前0条已验收，328单元／38批已准备。两账号80条是定向筛选（68纳入、12暂排除），不能计作80条AI_OK。

## 关键更正

1. 新10条的source_video_path误写为来源对象。原件未动，导入版恢复真实字符串并保留原值。
2. 0～3秒改为词级时间戳重建，避免整句越界。Bridge和结尾依据全文及可读分段重定位；原A字段保留。
3. 钱学森稿的书籍链接实际在442.920秒附近，原A写380秒。449.241秒既有帧可读《国之脊梁》，其缺书封申请撤销；同一ISBN/版本仍未证明。
4. v_2ad33b07cfad615d读物候选为“把话说的恰到好处”，借阅结尾288.310～291.015秒；不能当购物CTA。
5. v_74a64cf3aca9595d的书名候选同为“把话说的恰到好处”，不是A所写“闲谈高手”。v_b2bbecb4fc6ef0e9还有“把事做的恰到好处”配套候选。
6. v_f43b6f1228c21749在135.550秒附近提“写给孩子的漫画经济学”，207.440秒起为准备一套/共读建议。A模板新增的“点左下角链接”未获转录支持，不采纳。
7. 史记/山海经、道德经按引用记录；“对答如流”在钱学森稿中是普通词语；博物馆书名只在标题标签中，均不自动算销售。
8. 借阅、阅读推荐、连载/关注、软购买、明确商品入口分开。35条中引书/阅读17，明确入口9，软购买1；这些不是成交率、销量或收入。
9. A“成功降低完播门槛”“带货转化为0”“真实实景”等无证据判断撤回。A读图过程未证明，按可追溯文字限定；Codex所见静帧另列，音色/音乐/笑声掌声均未听核。

## 模板更新

- T01新增5个同账号变体，仅补充边界，不凑新模板。
- T02新增可试的反差表达方式；效果未知，竞品独特原句不进入可直接发布文案库。
- T03补入`v_b199dcc6960a2707`贵阳稿526.280秒引书和594.880秒附近入口证据。该稿来自80条定向筛选，未增加A深度计数；其访谈/数字仍未核实。原“第1期”未映射记录保留为历史问题，不冒认已找到。
- T05旅行阅读参考以大美中国稿、365日历书稿及无商品对照为准；`v_d00cee56eff9e90d`实际导向《超越百岁》，不作旅行图书SKU依据。
- T06“生活问题→解释对照→共读延伸”保留单样本草案。合计6套，5套可作研究参考、1套草案；均非效果已验证。

## 账号对账

{chr(10).join(account_table)}

## 当前4条待核

{pending_md}

## 交付与不变性

- 15份JSON与完成清单哈希一致，19文件两次稳定读取并由Codex原子冻结后校验导入。A执行记录为直接写最终文件，不能声称A已完成原子交付；真实分析耗时缺失，自报固定时间不作耗时证据。
- 332/332源视频SHA、大小、mtime及目录成员一致；原A28＋新19共47文件SHA/mtime不变；既有20个ASR断点文件不变。
- 数据库未打开。主库和WAL元数据与历史一致，SHM修改时间变化，原因未知；未把它记为历史全不变。
- 实际导入子进程退出75后恢复，3/3检查点哈希/mtime不变；重复导入/导出跳过记录见机器验收。工作簿独立校验7表、332行、长ID及3375个本地链接。
- 预览已生成并查看9张、覆盖7表；Windows渲染进程随后异常退出，实际退出码为{verification['render_exit_code']}。PNG和保存的XLSX均独立核验通过；不把渲染过程当原生Excel交互验证。

当前总入口：{link(central, '竞品分析协作总控')}。机器状态：`manifest/collaboration_state.json`；历史Phase4报告保存在reports/history，未抹去旧时间口径。
'''
    text(report, batch_report)
    text(R / 'reports/最终验收报告.md', f'''# 阅见生活竞品分析｜当前最终验收报告

更新于：{now}。**全项目：PARTIAL。当前总表已合并35条样本，31条限定范围可用、4条待核。**

本报告取代“当前25条”的旧入口，历史验收保留于reports/history。31条可用不代表史实、SKU、完整音画或营销效果已验证。

## 已完成与未完成

- 全量本地：332来源、317SHA独立内容、转录/分段/1328帧与来源映射已保留。
- 代表深拆：原25＋新10；旧5复核不重复计数。来源AI_PENDING297，独立未深拆282。
- 全文语义：317份仍待A分批执行，当前无文字轻分析落盘；80条定向筛选单列。
- 原创生产：30条旅行地理选题、10个单点候选、已有5份试做稿；两份选题库可能重合，5稿均为审阅稿、0条判为可发布。
- 模板：6套，5套研究结构参考、1套单样本草案；书籍SKU、目录、展示页等仍须按实物核对。

## 当前未决

{pending_md}

另有A交付未证明原子写入、真实耗时缺失，ASR专名/尾段未量化听核；数据库SHM历史mtime变化。不能将Schema通过或文件非空当终验PASS。

## 验证结果

- 332源视频SHA/大小/mtime一致，47份A原件不变，数据库未打开；主库/WAL元数据一致，SHM变化单列。
- 新10全文及40帧对照；15JSON结构通过后逐字段更正，原A观点与导入版分离。
- 真实中断恢复3/3检查点不变；重复执行跳过。
- 单个7-Sheet工作簿独立结构、来源、状态、精确长ID、公式注入和本地链接校验通过；渲染过程实际退出情况与视觉检查见机器记录，不将预览当原生Excel交互验证。

账号明细、更正和证据见{link(report, '补充批次01验收报告')}；后续工作以{link(central, '协作总控')}为入口。当前工作簿：{link(workbook, '7-Sheet总表')}。
''')
    template_md = ['# 原创结构模板库｜当前验收整理版', '', f'更新于：{now}。6套：5套研究参考、1套单样本草案。均非发布成稿或效果证明。', '']
    for t in templates['templates']:
        template_md += [f"## {t['id']} {t['name']}｜{t['status']}", '', f"- 受众：{t['audience']}；书籍范围：{t['books']}",
                        f"- 开头：{t['hook']}", f"- 展开：{t['story']}", f"- 引书：{t['bridge']}", f"- CTA：{t['cta']}",
                        f"- 视觉：{t['visual']}；时长：{t['seconds']}", f"- 原创建议：{t['topic']}", f"- 参考：{', '.join(t['refs'])}",
                        f"- 边界：{t['note']}", f"- 风险：{t['risk']}", '']
    text(R / 'reports/原创带货模板库_验收整理版.md', '\n'.join(template_md))
    history_lines = ['# 竞品分析更新日志', '', '按完成批次追加；本页由机器批次台账生成。当前状态看协作总控，历史条目保留当时口径。', '',
                     '|时间|批次|新增/旧复核|累计样本|可用/待核|项目状态|说明|', '|---|---|---|---:|---|---|---|']
    for e in entries:
        history_lines.append(f"|{e['at']}|{e['batch_id']}|{e['new_samples']}/{e['reviews']}|{e['sample_count']}|{e['ai_ok']}/{e['ai_review']}|{e['status']}|{e['note']}|")
    history_lines += ['', f'当前报告：{link(report, "补充01验收与更正")}；总入口：{link(central, "协作总控")}。', '']
    text(log_md, '\n'.join(history_lines))
    current = f'''# 竞品分析协作总控｜Codex与A共同入口

更新于：{now}。**当前项目PARTIAL；本页＋manifest/collaboration_state.json为最新状态。历史报告按其时间理解。**

## 一眼看当前

|项目|状态与数量|
|---|---|
|原素材|332来源／317SHA内容；全量本地基础处理已完成|
|代表深拆|35条（原25＋新10），31条限定范围可用、4条待核|
|全量文字轻分析|0/317已验收；328单元／38批就绪，AI_PENDING；不以代表深拆抵扣|
|定向筛选|林睿50＋锦绣30，共80；68纳入、12暂排除，未冒充80条全文语义完成|
|原创内容|30条旅行地理选题＋10个单点候选（可能重合）；5份试做稿，0份可发布|
|结构模板|6套：5研究参考、1单样本草案；均未证明营销效果|
|选品方向|以大美中国类、365日走遍中国类为主；历史名城/山西古建为相关研究方向，尚未认定实际SKU|

## 我们已经决定的事

1. 全量做文字轻分析，按需拆代表视频；不把所有视频逐镜头深拆。接下来优先旅行地理与两重点账号，仍按原计划覆盖317份全文。
2. 文案参考库用于查证与研究；结构库提炼方法；原创选题另写；完整口播和分镜以实际商品内容为依据。选题数不计作成稿数。
3. 原视频、下载数据库不改动、不上传；云端输入沿用用户已确认范围和额度，不默认新增收费API。Git只同步结果与代码。
4. 竞品分析任务中A只写独立analysis_a/<batch>/，Codex负责冻结、校验、总表和记录。原创生产按另行授权的独立工程目录执行。已验收批次原件冻结；修订另开批次，不覆盖原件。

## 最新批次和更正

{link(report, 'supplement_01：10新增＋5复核报告')}。原始19文件SHA保留，原子交付过程和真实耗时缺项已注明。

重点：书籍入口在442.920秒、449.241秒已有国之脊梁封面；路径对象/多处时段/书名已更正；借阅、阅读、连载、软购买与商品入口分开；T03已补真实文本第二来源，T06单样本暂存。

## 当前待核

{pending_md}

主库/WAL元数据不变，SHM历史mtime变化原因未核。ASR专名及尾段听核仍按原异常表保留；不影响先做独立选题和审阅草稿。

## 下一步分工

**A**：先读本页，再按`竞品视频分析_2026-10-15/handoff/text_light_v1/READY.json`和对应任务文件执行317全文轻分析。输出只写analysis_a/text_light_v1。逐单元读全、长稿不丢尾，真实记录时间；合法JSON及Schema校验后同目录临时文件原子重命名，完成清单带输入/输出SHA。不要重做35条或沿用错误时间。补证若有新材料另开修订批次。

**Codex**：只从完整最终文件冻结、校验并导入；核对原文、时间、身份、来源、书名与CTA口径，错误留痕；每批完成后更新下列入口并同步本任务结果。

**用户后续提供**：选定具体商品时再给正式书名/年份/版次、目录和可展示样页。现有5稿可先试读、核时长；SKU/事实/素材齐备后再做可发布审查。

## 固定收尾约定（每批都做）

1. A完成清单＋单文件SHA＋真实时间＋未决项；不得把PENDING/REVIEW算验收通过。
2. Codex原子冻结→Schema/身份/证据→逐条验收→保留来源及原值。
3. 更新同一个7-Sheet Excel、当前验收报告、相关文库/选题/稿件索引。
4. 更新collaboration_state.json及analysis_batches.jsonl，再刷新本页和更新日志；不回写历史计数。
5. 收尾时只提交本任务差异、检查凭据、按项目约定同步私有结果仓库。没有新批次时重复运行应跳过，不重复记账。

## 资料入口

- {link(log_md, '每批更新日志')}
- {link(workbook, '单个7-Sheet总表')}
- {link(R / 'reports/最终验收报告.md', '当前最终验收报告')}
- {link(R / 'reports/原创带货模板库_验收整理版.md', '当前6套结构与边界')}
- {link(R / 'content_library/01_竞品文案参考库.md', '317份文案参考库')}
- {link(R / 'content_library/02_旅行地理原创选题库_30条.md', '30条旅行地理选题')}
- {link(ROOT / '05_爆款知识库与复盘/01_钩子与引书结构库.md', '80条定向研究的钩子与引书结构')}
- {link(ROOT / '05_爆款知识库与复盘/02_单点选题排期.md', '10个单点候选与排期')}
- {link(draft_file, '5份原创试做稿与审阅状态')}
- {link(ROOT / '05_爆款知识库与复盘/03_短片生产SOP.md', '短片制作SOP')}
- {link(R / 'handoff/text_light_v1/发给A_全量文字轻分析.md', 'A的317份全文任务')}

收尾由Codex执行：本批使用`scripts/record_competitor_batch.py`。该版本仅适配supplement_01；新批次必须先按真实验收结果适配，再追加同一台账，不能直接套旧计数。工具不代替内容分析与证据校验；没有合格工作簿验收记录会拒绝收尾。
'''
    text(central, current)
    # Refresh existing human entry points without changing frozen A materials or long-form drafts.
    libguide = R / 'content_library/开始使用.md'
    text(libguide, f'''# 文案库与原创生产｜当前入口

更新于：{now}。请先读{link(central, '竞品分析协作总控')}，查看当前数量、待办和责任分工。

- 317份全文已转录并建立索引；全量语义仍AI_PENDING，不能用基础统计代替逐篇理解。
- 已合并35份代表样本：31限定范围可用、4待核；当前结构库6套，5研究参考＋1单样本草案。
- 30条旅行地理选题保留为原创提议，另有10个单点候选；两库可能重合，不相加计唯一题数。
- 最新工作区已有5份完整试做稿，均处审阅阶段、0份可发布。早期“成稿数0”的准备验收只代表当时时点。

生产流程：**商品与读者问题→原创选题→事实/内容核实→完整口播→分镜/字幕→样片→真实数据复盘。**

文案参考库保留竞品来源；结构模块抽象表达方法；选题和成稿用自己的资料、问题、场景与表达。原稿和30个标题都不当发布成稿。大美中国与365日类的具体版本、目录和展示页先按实书核对；超越百岁稿仅可作结构对照，不作旅行图书SKU证据。

入口：{link(R / 'content_library/01_竞品文案参考库.md', '317条文案参考')}；{link(R / 'content_library/02_旅行地理原创选题库_30条.md', '30条选题')}；{link(draft_file, '5份试做稿')}；{link(R / 'handoff/text_light_v1/发给A_全量文字轻分析.md', 'A文字任务')}。

每次竞品批次完成后由Codex更新总表、当前报告、总控和日志，A原件及历史证据保留。完整分工和收尾步骤统一维护在总控页。
''')
    idx_path = R / 'content_library/01_竞品文案参考库.md'
    idx = idx_path.read_text(encoding='utf-8').replace('历史深度状态', '最新深度状态')
    for v, rec in records.items():
        pattern = r'(?m)^(\|\[' + re.escape(v) + r'\].*\|)(AI_OK|AI_REVIEW|AI_PENDING)(\|AI_PENDING\|)$'
        idx = re.sub(pattern, lambda m: m.group(1) + rec['status'] + m.group(3), idx)
    idx = idx.replace('25条历史视频深度结果单列', '35条当前代表深度结果单列')
    text(idx_path, idx)
    text(R / 'README.md', f'''# 阅见生活竞品分析｜当前工作区

更新于：{now}。先读{link(central, '竞品分析协作总控')}；每批结束更新同一总表、状态和日志。

- 332来源／317SHA基础处理完成；35条代表样本整合，31条限定范围可用、4条待核，项目PARTIAL。
- 317份全文语义尚未执行，38批已就绪；80条定向筛选不是80条语义完成。
- 6套结构、30个旅行地理选题、另10个单点候选、已有5份试做稿（0可发布）；以各自定义计数。
- 原视频和下载数据库只读；不上传原视频。A只写analysis_a独立批次，Codex负责其余数据/报告/工作簿。

当前入口：{link(workbook, '7-Sheet总表')}；{link(R / 'reports/最终验收报告.md', '当前验收报告')}；{link(report, '补充01更正明细')}；{link(log_md, '批次日志')}；{link(R / 'content_library/开始使用.md', '文库与生产')}。

后续A任务：handoff/text_light_v1/，沿用已确认文字输入范围与额度，完整读取317份文字，不新增全量视频拆解。

历史Phase2命令和旧状态保存在reports/history/分析README_补充01前.md。不要运行旧phase2_export.py或phase4_export.py覆盖当前35条整合表；本批恢复使用scripts/integrate_competitor_supplement.py和scripts/export_competitor_supplement.py，具体版本以批次记录为准。

机器入口：manifest/collaboration_state.json；追加台账：manifest/analysis_batches.jsonl；当前导入：manifest/supplement_01_records/；A冻结：manifest/supplement_01_input_snapshot/。历史phase4_*保持当时证据，不当作最新状态。
''')
    for p in [ROOT / '05_爆款知识库与复盘/README.md', ROOT / '05_爆款知识库与复盘/01_钩子与引书结构库.md']:
        original = p.read_text(encoding='utf-8')
        if '## 竞品分析当前总控' not in original:
            text(p, original.rstrip() + f'\n\n## 竞品分析当前总控\n\n{link(central, "当前数量、最新批次与下一步分工")}；{link(log_md, "每批更新日志")}。原80条定向研究、来源和审阅稿保留；新批次证据与未决项统一见总控。\n')
    ag = ROOT / 'AGENTS.md'
    old = ag.read_text(encoding='utf-8')
    if '## 竞品分析协作收尾' not in old:
        text(ag, old.rstrip() + '\n\n## 竞品分析协作收尾\n\n- 每次竞品分析或A结果整合前，先读 `docs/竞品分析协作总控.md` 和 `竞品视频分析_2026-10-15/manifest/collaboration_state.json`。\n- 每批完成后，Codex更新同一7-Sheet总表、当前验收报告、相关文库索引、协作总控和追加批次日志，再按同步约定保存结果；历史证据保留原时点。\n- A只写独立 `analysis_a/<批次>/`，已验收原件冻结；修订另开批次。全量基础处理、文字语义、代表深拆、定向筛选和原创成稿分口径计数。\n')
    readme = ROOT / 'README.md'
    old = readme.read_text(encoding='utf-8')
    if '竞品分析协作总控' not in old:
        text(readme, old.replace('## 资料入口', '## 竞品分析协作总控\n\n先读 [当前状态与分工](docs/竞品分析协作总控.md)，每批做完更新 [批次日志](05_爆款知识库与复盘/06_竞品分析更新日志.md)。\n\n## 资料入口', 1))
    daily = ROOT / 'docs/换电脑与日常使用.md'
    old = daily.read_text(encoding='utf-8')
    if '竞品分析协作总控' not in old:
        text(daily, old.replace('## 继续视频开发', '## 竞品分析接续\n\n每次先读 [竞品分析协作总控](竞品分析协作总控.md) 与其机器状态，按最新批次继续。每批结束由Codex更新总表、报告、文库索引、总控及追加日志，再同步本任务结果；A不得覆盖已验收批次。\n\n## 继续视频开发', 1))
    print(json.dumps({'state': str(central), 'batch': args.batch_id, 'sample_count': len(records), 'drafts': drafts}, ensure_ascii=True))


if __name__ == '__main__':
    main()
