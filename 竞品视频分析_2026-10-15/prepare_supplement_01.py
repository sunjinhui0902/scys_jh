import collections
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BATCH = ROOT / 'handoff' / 'supplement_01'
NOW = dt.datetime.now().astimezone().isoformat(timespec='seconds')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    path = Path(path)
    return {'path': str(path), 'size': path.stat().st_size,
            'mtime_ns': path.stat().st_mtime_ns,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(content, encoding='utf-8')
    os.replace(tmp, path)


def write_json(path, value):
    atomic(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


rows = [json.loads(line) for line in
        (ROOT / 'manifest' / 'manifest.jsonl').read_text(encoding='utf-8-sig').splitlines()]
by_id = {row['video_id']: row for row in rows}
features = read(ROOT / 'clusters' / 'video_features.json')
clusters = read(ROOT / 'clusters' / 'text_clusters.json')
old = read(ROOT / 'clusters' / 'deep_candidates.json')
old_ids = {row['video_id'] for row in old}

selection = [
    ('v_2ad33b07cfad615d', '补齐TEXT_01795f4877与HOOK_01795f4877：饭局发言情境→表达练习→借阅结尾；与已分析的对话类模板比较新增价值。'),
    ('v_325a2849484e6f15', '补齐TEXT_14748f9bf8与HOOK_d91c41a7b7：后备箱情境→解释话外意→荐书；仅研究结构，不照搬其处世建议。'),
    ('v_f43b6f1228c21749', '补齐TEXT_914c67a0da：亲子购物问答→经济学/财商读物；正式书名待确认，价值主张不得当作已证实效果。'),
    ('v_b2bbecb4fc6ef0e9', '补齐TEXT_fa51f98c2b与HOOK_fa51f98c2b：供应商对接连续场景→引书；检查是否只是既有模板换情节。'),
    ('v_74a64cf3aca9595d', '补齐TEXT_61825f8623：较短的场景问答合集→荐书；与长剧情样本比较引书位置和推荐方式。'),
    ('v_d66d5d68290f0e95', '补齐TEXT_c47727307b：场景问答合集的另一全文簇；若仅换句/拼接或沿用相同荐书尾段，明确判为低增量。'),
    ('v_4ed4d46352185f2f', '未覆盖书名候选对照：史记/山海经出现在历史叙述中，区分引用典籍、阅读推荐和实际购物；历史内容本身未核实。'),
    ('v_38eb65b8de747391', '跨账号及候选误判对照：钱学森叙事；核对“对答如流”是否普通词语，实际引书是否国之脊梁，避免把词频当书籍销售。'),
    ('v_7e0d1a4f77167eb4', '未覆盖书名候选对照：道德经引用与认知表达；检验是否缺少实际荐书/购物环节，名人引语均须保留未核实属性。'),
    ('v_5ae6f6253ad7b999', '未覆盖主题对照：博物馆/文物流失叙事；书名可能仅在标题标签中，核对实际Bridge与CTA；作为T03/T05的适用边界对照，不强行计作第二来源。'),
]
reviews = {
    'v_183328bf0ee8b458': '按可验证输入重做：撤回无证明的native_video/完整声音结论；120.185秒帧是饭局人物，不能作为书封或出版社证据；没有真实封面证据则填未知。',
    'v_30cc827b5d5dd936': '按文本+实际截图限定结论：120秒实帧为题字特写，不能据此声称老人伏案写字；撤回无输入链证明的完整音画结论。',
    'v_7e9d12d17d945cb4': '按文本+实际截图限定结论：撤回缺证据的茶水等画面细节与完整声音结论；无需重做MP4能力测试。',
    'v_2a38fc92b95504f3': '名人逝世叙事未核实：仅记录素材声称与表达结构，明确不作为原创事实依据；保留AI_REVIEW，不要求为了结案而寻找或编造佐证。',
    'v_e24346b823344654': '名人逝世叙事未核实：仅记录素材声称与表达结构，明确不作为原创事实依据；保留AI_REVIEW，不要求为了结案而寻找或编造佐证。',
}
assert len(selection) == 10 and len({v for v, _ in selection}) == 10
assert not old_ids.intersection(v for v, _ in selection)
assert len({by_id[v]['sha256'] for v, _ in selection}) == 10
assert not {by_id[v]['sha256'] for v, _ in selection}.intersection(by_id[v]['sha256'] for v in old_ids)
assert all(by_id[v].get('canonical_video_id', v) == v for v, _ in selection)
assert set(reviews).issubset(old_ids)
assert not BATCH.exists(), 'Batch already exists; preserve it and inspect instead of overwriting.'

# Snapshot existing deliverables and A originals; prepare this handoff without changing them.
protected = [ROOT / '阅见生活_竞品视频分析_终版.xlsx',
             ROOT / 'reports' / '最终验收报告.md',
             ROOT / 'reports' / 'Phase4_导入更正与待补证清单.md',
             ROOT / 'manifest' / 'manifest.jsonl',
             ROOT / 'clusters' / 'deep_candidates.json',
             ROOT / 'handoff' / 'analysis_schema.json']
protected += sorted(path for path in (ROOT / 'analysis_a').iterdir() if path.is_file())
before = {str(path): digest(path) for path in protected}
source_before = {row['source_path']: (Path(row['source_path']).stat().st_size,
                                      Path(row['source_path']).stat().st_mtime_ns) for row in rows}


def package_entry(video_id, reason, is_review=False):
    row = by_id[video_id]
    package = ROOT / 'handoff' / video_id
    ready = read(package / 'READY.json')
    inp = read(package / 'input.json')
    assert ready['video_id'] == inp['video_id'] == video_id and ready['files_complete']
    refs = [package / 'READY.json', package / 'input.json', Path(inp['transcript_path']),
            Path(inp['segments_path']), Path(inp['raw_segments_path'])]
    refs += [Path(frame['path']) for frame in inp['frames']]
    assert len(inp['frames']) == 4 and all(path.is_file() for path in refs)
    assert Path(inp['source_video_path']).resolve() == Path(row['source_path']).resolve()
    matches = [c for c in clusters if video_id in c['video_ids']]
    sources = [{'video_id': r['video_id'], 'account': r['account'], 'source_path': r['source_path']}
               for r in rows if r['sha256'] == row['sha256']]
    output_sub = 'reviews' if is_review else 'videos'
    return {
        'video_id': video_id, 'account': row['account'], 'duration_s': row['duration_s'],
        'source_sha256': row['sha256'], 'all_source_mappings': sources,
        'handoff_path': str(package), 'reason': reason,
        'book_candidates': features[video_id]['book_candidates'],
        'book_candidates_are_not_confirmed_products': True,
        'cluster_ids': [c['cluster_id'] for c in matches],
        'expected_output': str(ROOT / 'analysis_a' / 'supplement_01' / output_sub / f'{video_id}.json'),
        'input_snapshot': [digest(path) for path in refs],
    }


new_entries = [package_entry(v, reason) for v, reason in selection]
review_entries = [package_entry(v, reason, True) for v, reason in reviews.items()]
selected_ids = {v for v, _ in selection}
coverage = {}
for kind in ['TEXT', 'HOOK', 'PASSAGE']:
    all_clusters = [c for c in clusters if c['kind'] == kind]
    coverage[kind] = {
        'total': len(all_clusters),
        'selected_before': sum(bool(set(c['video_ids']) & old_ids) for c in all_clusters),
        'selected_after_if_new_batch_completed': sum(bool(set(c['video_ids']) & (old_ids | selected_ids)) for c in all_clusters),
        'note': 'Membership coverage only; does not establish semantic novelty or statistical representativeness.'}

plan = {
    'schema_version': 'supplement_plan_1.0', 'batch_id': 'supplement_01', 'prepared_at': NOW,
    'status': 'PREPARED_NOT_ANALYZED',
    'scope': 'V4流程的可选补充批次；原25条保留。新10条完成后累计35条，超过原默认20～30条；复制执行指令才启动补充分析。',
    'new_video_count': 10, 'review_video_count': 5,
    'permission_scope': 'Does not add upload/API/model permissions; retain previously confirmed input scope and quota.',
    'new_videos': new_entries, 'reviews': review_entries, 'cluster_membership_coverage': coverage,
    'account_counts': dict(collections.Counter(e['account'] for e in new_entries)),
    'schema_path': str(ROOT / 'handoff' / 'analysis_schema.json'),
}
write_json(BATCH / 'batch_plan.json', plan)

instruction = f'''# 发给 Antigravity：5条复核＋10条补充深度分析

共享目录：`{ROOT}`。
本轮沿用V4的分工、分析字段、证据要求和原有输入授权。原默认20～30条已经分析25条；本轮是额外补充10条，完成后累计35条，另有5条旧样本复核。不得扩为全库深度分析。

## 先读取

1. `{BATCH / 'READY.json'}` 与 `{BATCH / 'batch_plan.json'}`。
2. `{ROOT / 'handoff' / 'analysis_schema.json'}`。
3. `{ROOT / 'reports' / 'Phase4_导入更正与待补证清单.md'}`。
4. `{ROOT / 'reports' / '原创带货模板库_验收整理版.md'}`。

逐条核对清单中的input_snapshot哈希和video_id。只读取已有READY且与快照一致的交接包；输入变化则记录该条待核，不读取半写入文件。视频清单由Codex确定，不自行扩大或替换。

## 第一部分：复核5条旧样本

严格按照batch_plan.reviews的reason逐项回应。以Codex更正清单为复核起点，保留真实0～3秒、已更正的书名、Bridge/CTA及其他已核对结果。可只读对应`manifest/phase4_records/<video_id>.json`了解验收记录。

三条原生视频能力存疑样本，按实际可验证的文本和截图重做；未独立证明完整视频输入时使用text_plus_frames或text_only，撤回完整声音、音乐节奏、全部镜头和没有实际截图的细节判断。不要再声称仅凭路径读懂了MP4。没有封面/出版社证据即填未知。

两条名人逝世叙事只记录“素材声称”，保留AI_REVIEW及不能作为原创事实依据的限制。本轮不要求新闻事实核查，不为结案虚构证明。

每条仍输出满足analysis_schema.json的完整单视频JSON，并增加review_response数组，逐项记录原问题、处理、支持证据、未解决项。输出至batch_plan中reviews对应expected_output，不覆盖旧原件。

## 第二部分：新增10条

仅处理batch_plan.new_videos的10条，分两批、每批5条，完成一条即落盘。每条严格执行V4 Phase 3全部字段，特别是：

- 0～3秒真实口播依据词级时间戳，不拿前三句话代替；无语音明确标记。ASR疑似误识标待核，不编造原话。
- 首次书名出现、首次真正引书Bridge、推荐与购物CTA分别记录原文及实际时间范围，不能互相替代。借阅对话、关注账号、下一集引导与购物分别分类；没有则填无。
- 书名规则候选不等于正式书名、实际推荐或商品。对答如流可能是普通词语；史记/道德经可能只是引用；标题标签不等于口播荐书。必须核对。
- 视觉只依据实际读取的截图并标路径和时间；无法确认的完整音乐、声线、镜头节奏和画面真实性留空/未知，并注明输入限制。没有补帧不得凭推断声称书封可见；需要补帧写入申请清单，由Codex补充。
- 名人引语、历史数字、经济效果等视为素材声称；不作为已核实事实。不虚构平台播放、成交、转化效果。
- 每条增加incremental_findings对象：comparison_video_ids、new_hook、new_narrative、new_bridge、new_cta、new_visual、new_book_scenario、adds_new_usable_structure、reason、evidence。没有增量则明确写false及原因，不强凑新模板。
- 字段未知必须留空/标未知及限制；未完成状态为AI_PENDING，有关键证据缺口为AI_REVIEW，结构Schema通过不等于业务验收通过。

原稿与独特表达仅用短摘录作证据，输出抽象结构和独立原创选题，不生成竞品整篇复制稿。本轮不制作、不发布成片。

## 写入与断点

你只能写入`{ROOT / 'analysis_a' / 'supplement_01'}`，其中新样本写videos/、旧样本复核写reviews/。其他目录、原25份JSON、旧account_summary、旧模板、Excel、原视频和数据库均不得改动。无需重新转录全量、安装框架、申请API Key或调用收费API；不扩大此前批准的素材输入范围与额度。

每份JSON先写同目录临时文件；完成合法JSON及Schema校验后原子重命名为对应video_id.json。已完成且输入哈希一致的条目可跳过；保留失败原因和实际分析时间，不捏造已听看情况。运行中断后据已验证最终文件恢复。

## 批次汇总

全部可处理项落盘后，仅在同一supplement_01输出目录生成：

1. `account_summary.json`：新增10条与原25条分开统计；合并参考Codex验收后的数据，避免沿用A原始误判。原始35条样本、实际可用数、待核数、各统计分母明确，不外推全账号。
2. `原创带货模板库_增量.md`：说明新增/修订结构及参考video_id；没有新模板如实写明。T03缺第二来源时仍标单样本草案，不能凭同主题硬凑。
3. `补帧与待补证清单.md`：video_id、所需时间点/范围、问题、用途；没有则写无。不要自行写Codex的frames/或reports/。
4. `完成清单.json`：10条新增和5条复核逐项列出最终状态、输出相对路径、SHA-256、输入快照引用、错误/未决项、实际开始结束时间；最后原子落盘。不得把AI_PENDING/AI_REVIEW计作已验收通过。

完成后暂停，回复实际落盘数量、未完成项和绝对路径；由Codex再次校验、整合单个7-Sheet Excel与验收报告。不要声称项目已经PASS，也不要自行启动下一轮。
'''
atomic(BATCH / '发给A_执行指令.md', instruction)

md = ['# 补充批次01：选样说明', '',
      '状态：仅准备交接，尚未执行新增AI分析。原25条不变；新增10条为可选扩展，执行后累计35条。', '',
      '六条用于补齐尚未入选的全文相似簇，四条用于书名引用、普通词误判、标题标签和叙事场景对照。部分簇非常接近，A必须报告是否真的有新增结构。', '',
      '本批不重新覆盖六账号：原批已覆盖六账号，本批按缺口选择四账号。不代表随机抽样或全账号效果。', '',
      '|序号|video_id|账号|时长(分)|选取原因|', '|---:|---|---|---:|---|']
for index, entry in enumerate(new_entries, 1):
    md.append(f"|{index}|{entry['video_id']}|{entry['account']}|{entry['duration_s']/60:.2f}|{entry['reason']}|")
md += ['', '## 预计覆盖（只有完成并验收后才成立）', '',
       '|簇口径|原25条已选代表|原25＋新10条的代表覆盖|总簇数|', '|---|---:|---:|---:|']
for kind, c in coverage.items():
    md.append(f"|{kind}|{c['selected_before']}|{c['selected_after_if_new_batch_completed']}|{c['total']}|")
md += ['', '覆盖只表示簇中至少一条入选，不等于发现相同数量的新模板。', '', '## 复核5条', '']
md.extend(f"- {v}：{reason}" for v, reason in reviews.items())
atomic(BATCH / '选样说明.md', '\n'.join(md) + '\n')

after = {str(path): digest(path) for path in protected}
source_after = {row['source_path']: (Path(row['source_path']).stat().st_size,
                                     Path(row['source_path']).stat().st_mtime_ns) for row in rows}
assert before == after and source_before == source_after
checks = {
    'checked_at': NOW, 'new_ids': len(new_entries), 'review_ids': len(review_entries),
    'new_sha_unique': 10, 'overlap_with_original_25': 0,
    'all_15_individual_READY_and_input_snapshots_valid': True,
    'protected_file_count': len(protected), 'protected_sha_size_mtime_unchanged': True,
    'source_path_count': len(source_before), 'source_size_mtime_unchanged': True,
    'source_content_rehashed_this_step': False, 'db_opened': False,
    'external_uploads': 0, 'AI_analysis_executed': False,
    'new_account_counts': plan['account_counts'], 'cluster_membership_coverage': coverage,
}
write_json(BATCH / '准备校验.json', checks)
files = ['batch_plan.json', '发给A_执行指令.md', '选样说明.md', '准备校验.json']
write_json(BATCH / 'READY.json', {
    'schema_version': 'supplement_ready_1.0', 'batch_id': 'supplement_01', 'ready_at': NOW,
    'new_video_count': 10, 'review_count': 5, 'files_complete': True,
    'files': [digest(BATCH / name) for name in files],
    'new_video_ids': [e['video_id'] for e in new_entries], 'review_video_ids': list(reviews),
    'does_not_expand_prior_input_authorization': True,
    'status': 'PREPARED_NOT_ANALYZED',
})
print(json.dumps({'path': str(BATCH), 'new_count': 10, 'review_count': 5,
                  'new_account_counts': plan['account_counts'], 'coverage': coverage,
                  'video_minutes': round(sum(e['duration_s'] for e in new_entries)/60, 2),
                  'existing_deliverables_unchanged': True}, ensure_ascii=True))
