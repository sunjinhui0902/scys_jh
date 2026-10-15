"""Independent, resumable review of the October 16 scoped A delivery."""
from __future__ import annotations
import argparse
import collections
import datetime as dt
import hashlib
import json
import pathlib
import re
import shutil
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
R = ROOT / '竞品视频分析_2026-10-15'
BATCH = 'new_accounts_2026-10-16'
H = R / 'handoff' / BATCH
A = R / 'analysis_a' / BATCH
Q = R / 'reviews' / 'new_accounts_2026-10-16_0738'
sys.path.insert(0, str(ROOT / '.local/schema-validation'))

def now():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec='seconds')

def sha(path):
    h = hashlib.sha256()
    with pathlib.Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def strict(path):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError('Duplicate JSON key: ' + k)
            result[k] = v
        return result
    def invalid(value):
        raise ValueError('Nonstandard JSON constant: ' + value)
    return json.loads(pathlib.Path(path).read_text(encoding='utf-8-sig'), parse_constant=invalid, object_pairs_hook=pairs)

def write(path, data):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(path)

def fp(path):
    s = path.stat()
    return {'path': path.relative_to(ROOT).as_posix(), 'size': s.st_size, 'mtime_ns': s.st_mtime_ns, 'sha256': sha(path)}

def checked_path(value, roots):
    p = pathlib.Path(value).resolve()
    if not any(p.is_relative_to(x.resolve()) for x in roots):
        raise ValueError('Out of approved path scope: ' + str(value))
    return p

def snapshot():
    from jsonschema import Draft202012Validator, FormatChecker
    if (Q / 'structural_gate.json').exists():
        saved = strict(Q / 'structural_gate.json')
        for ref in saved['source_fingerprints']:
            assert fp(ROOT / ref['path']) == ref, ref['path']
        for ref in saved['frozen_files']:
            assert sha(Q / 'frozen' / ref['relative_path']) == ref['sha256'], ref
        print('SNAPSHOT_RESUME_SKIP', len(saved['frozen_files']))
        return
    files = sorted(p for p in A.rglob('*') if p.is_file() and p.suffix.lower() in {'.json', '.md'})
    before = [fp(p) for p in files]
    # A stable final marker and matching hashes are observable; historical rename syscalls are not.
    time.sleep(2)
    assert before == [fp(p) for p in files], 'A files changed during snapshot'
    validators = {name: Draft202012Validator(strict(H / file), format_checker=FormatChecker())
                  for name, file in [('completion', 'completion_schema.json'), ('text', 'text_analysis_schema.json'), ('deep', 'deep_analysis_schema.json')]}
    completions = []; gates = []; referenced = set(); valid_paths = set()
    for p in [x for x in files if x.name == 'COMPLETED.json']:
        errors = []; d = None
        try:
            d = strict(p); validators['completion'].validate(d)
            start = dt.datetime.fromisoformat(d['started_at']); end = dt.datetime.fromisoformat(d['finished_at'])
            assert start.tzinfo and end.tzinfo and start <= end <= dt.datetime.now(dt.timezone.utc), 'Invalid completion time order'
            for ref in d['inputs']:
                src = checked_path(ref['path'], [H, R / 'increments' / BATCH]); assert sha(src) == ref['sha256'], 'Input SHA mismatch: ' + str(src)
            for ref in d['outputs']:
                out = checked_path(ref['path'], [A]); assert sha(out) == ref['sha256'], 'Output SHA mismatch: ' + str(out)
                referenced.add(out)
            valid_paths.add(p)
        except Exception as exc:
            errors.append(str(exc)[:2000])
        completions.append({'path': p.relative_to(A).as_posix(), 'pass': not errors, 'errors': errors,
                            'kind': d.get('kind') if isinstance(d, dict) else None,
                            'started_at': d.get('started_at') if isinstance(d, dict) else None,
                            'finished_at': d.get('finished_at') if isinstance(d, dict) else None,
                            'input_count': len(d.get('inputs', [])) if isinstance(d, dict) else 0,
                            'output_count': len(d.get('outputs', [])) if isinstance(d, dict) else 0})
    for p in [x for x in files if x.name.startswith('v_') and x.suffix == '.json']:
        errors = []; kind = p.parent.name.split('_')[0]
        try:
            assert p in referenced, 'No matching final completion reference'
            assert (p.parent / 'COMPLETED.json') in valid_paths, 'Parent completion failed'
            d = strict(p); validators[kind].validate(d)
            assert d['video_id'] == p.stem, 'Filename/ID mismatch'
            valid_paths.add(p)
        except Exception as exc:
            errors.append(str(exc)[:2000])
        gates.append({'path': p.relative_to(A).as_posix(), 'kind': kind, 'video_id': p.stem, 'pass': not errors, 'errors': errors})
    # Summary has no supplied output Schema. Retain only as unaccepted metadata for independent review.
    for p in files:
        if p.parent == A and p.name != 'COMPLETED.json' and p in referenced:
            if p.suffix == '.json': strict(p)
            valid_paths.add(p)
    frozen = []
    for p in sorted(valid_paths):
        dest = Q / 'frozen' / p.relative_to(A)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists(): assert sha(dest) == sha(p), 'Frozen file must not be overwritten'
        else: shutil.copy2(p, dest)
        frozen.append({'relative_path': p.relative_to(A).as_posix(), 'sha256': sha(dest), 'semantic_acceptance': 'NOT_YET_REVIEWED'})
    assert before == [fp(p) for p in files], 'A changed during validation'
    report = {'review_id': Q.name, 'observed_at': now(), 'status': 'STRUCTURAL_ONLY',
              'completion_gates': completions, 'video_gates': gates, 'source_fingerprints': before,
              'frozen_files': frozen, 'historical_atomic_rename_observed': False,
              'atomic_boundary_note': 'Final COMPLETED markers, a stable 2-second snapshot, and all declared SHA values were independently checked; rename syscall history is not observable after the fact.',
              'summary_schema': 'NOT_SUPPLIED; summary is unaccepted metadata, not independent analysis proof'}
    write(Q / 'structural_gate.json', report)
    print(json.dumps({'completion': collections.Counter(x['pass'] for x in completions),
                      'video_schema': collections.Counter((x['kind'], x['pass']) for x in gates).__repr__(),
                      'frozen': len(frozen), 'errors': [x for x in completions + gates if not x['pass']]}, ensure_ascii=False))

def evidence_audit():
    gates = strict(Q / 'structural_gate.json')
    records = {x['video_id']: x for x in strict(H / 'batch_plan.json')['records']}
    reports = []
    for item in gates['video_gates']:
        if not item['pass']:
            continue
        p = Q / 'frozen' / item['path']; d = strict(p); v = records[d['video_id']]
        units = [strict(ref['path']) for ref in v['text_units']]
        segments = {s['segment_id']: s for u in units for s in u['segments']}
        issues = []; tests = {}
        for k in ['video_id', 'account', 'source_sha256']:
            if d[k] != v[k]: issues.append({'code': 'IDENTITY_MISMATCH', 'field': k})
        if item['kind'] == 'deep' and d['source_video_path'] != v['source_video_path']:
            issues.append({'code': 'SOURCE_PATH_MISMATCH'})
        if item['kind'] == 'text':
            coverage = d['coverage']
            expected = [u['unit_id'] for u in units]
            tests['coverage_declaration_matches'] = (coverage['unit_ids'] == expected and coverage['first_segment_id'] == v['expected_first_segment_id']
                and coverage['last_segment_id'] == v['expected_last_segment_id'] and coverage['read_all_units'] and not coverage['missing_ranges'])
            if not tests['coverage_declaration_matches']: issues.append({'code': 'COVERAGE_DECLARATION_MISMATCH'})
            if d['fields']['story_points'] and all(isinstance(x, str) and x.startswith('叙事节点（') for x in d['fields']['story_points']):
                issues.append({'code': 'EVENLY_SAMPLED_SEGMENTS_NOT_SEMANTIC_SUMMARY', 'points': len(d['fields']['story_points'])})
            if d['started_at'] == d['finished_at']:
                issues.append({'code': 'NO_RECORDED_ANALYSIS_INTERVAL', 'note': 'Equal timestamps prove no positive analysis interval is recorded; they alone do not prove analysis did not happen.'})
            completion = strict(p.parent / 'COMPLETED.json')
            if dt.datetime.fromisoformat(d['finished_at']) > dt.datetime.fromisoformat(completion['finished_at']):
                issues.append({'code': 'ANALYSIS_FINISH_AFTER_COMPLETION_MARKER', 'analysis_finished': d['finished_at'], 'completion_finished': completion['finished_at']})
        all_evidence = []
        if isinstance(d['evidence'], list):
            all_evidence += [('evidence', e) for e in d['evidence'] if isinstance(e, dict)]
        for key in ['hook', 'bridge', 'cta']:
            f = d['fields'][key]
            if f.get('present'): all_evidence.append(('fields.' + key, f))
        if item['kind'] == 'text':
            all_evidence += [('fields.book_relations', {**b, 'quote': b.get('evidence_quote', '')}) for b in d['fields']['book_relations'] if isinstance(b, dict)]
        quote_pass = 0; time_pass = 0
        for field, e in all_evidence:
            sid = e.get('segment_id'); s = segments.get(sid); quote = e.get('quote', '')
            if s is None:
                issues.append({'code': 'UNKNOWN_SEGMENT', 'field': field, 'segment_id': sid}); continue
            if not quote or quote not in s['text']:
                issues.append({'code': 'QUOTE_NOT_IN_CITED_SEGMENT', 'field': field, 'segment_id': sid, 'quote': quote, 'actual': s['text']})
            else: quote_pass += 1
            if 'start_s' in e and 'end_s' in e:
                actual = [s['start_ms'] / 1000, s['end_ms'] / 1000]
                if abs(e['start_s'] - actual[0]) > .05 or abs(e['end_s'] - actual[1]) > .05:
                    issues.append({'code': 'TIME_NOT_CITED_SEGMENT_RANGE', 'field': field, 'segment_id': sid,
                                   'claimed': [e['start_s'], e['end_s']], 'actual': actual})
                else: time_pass += 1
        if item['kind'] == 'deep':
            visual = d['fields']['visual_and_audio']
            desc = str(visual.get('visual_frames_observed', ''))
            if '画面包含关键文字标题/历史文物或实景插图展示' in desc:
                issues.append({'code': 'GENERIC_FRAME_DESCRIPTION_WITHOUT_SPECIFIC_EVIDENCE', 'note': 'Repeated generic caption is not proof that the four actual images were observed.'})
            if '微动' in desc:
                issues.append({'code': 'MOTION_NOT_PROVABLE_FROM_STATIC_FRAMES'})
            tests['input_mode_claim'] = d['input_mode']
        tests.update({'quote_checks': len(all_evidence), 'quote_pass': quote_pass, 'matching_time_ranges': time_pass,
                      'expected_unit_ids': [u['unit_id'] for u in units], 'expected_tail': list(segments.values())[-1]})
        reports.append({**item, 'A_status': d['status'], 'tests': tests, 'issues': issues,
                        'review_status': 'AI_REVIEW' if issues or d['status'] != 'AI_OK' else 'NEEDS_INDEPENDENT_CONTENT_REVIEW'})
    output = {'at': now(), 'scope': 'All 108 structurally valid per-video outputs; reference checks do not certify complete model reading',
              'results': reports, 'issue_counts': dict(collections.Counter(e['code'] for r in reports for e in r['issues']))}
    write(Q / 'evidence_checks.json', output)
    print(json.dumps({'files': len(reports), 'status': collections.Counter(x['review_status'] for x in reports),
                      'issues': output['issue_counts'], 'no_automatic_issues': [x['path'] for x in reports if not x['issues']]}, ensure_ascii=False))

def integrity():
    start = time.perf_counter(); sources = [json.loads(x) for x in (R / 'manifest/current_manifest.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
    changes = []
    for d in sources:
        p = pathlib.Path(d['source_path']); s = p.stat()
        if (s.st_size, s.st_mtime_ns, sha(p)) != (d['size_bytes'], d['mtime_ns'], d['sha256']): changes.append(d['video_id'])
    history = strict(R / 'increments' / BATCH / 'manifest/historical_evidence_before.json')
    history = [x for x in history if not x['path'].endswith('.xlsx')]
    history_changes = [x['path'] for x in history if fp_absolute(x['path']) != x]
    stage = strict(Q / 'structural_gate.json'); a_changes = [x['path'] for x in stage['source_fingerprints'] if fp(ROOT / x['path']) != x]
    ready = strict(H / 'READY.json')
    # The existing ready verifier records paths directly; no source video/audio is uploaded or rewritten.
    ready_bad = []
    for ref in ready['files']:
        p = pathlib.Path(ref['path'])
        if sha(p) != ref['sha256'] or p.stat().st_size != ref['size_bytes']: ready_bad.append(ref['path'])
    result = {'at': now(), 'source_files_checked': len(sources), 'source_sha_size_mtime_unchanged': len(sources) - len(changes),
              'changed_video_ids': changes, 'historical_files_checked': len(history), 'historical_files_changed': history_changes,
              'reviewed_A_files_checked': len(stage['source_fingerprints']), 'reviewed_A_files_changed': a_changes,
              'handoff_ready_refs_checked': len(ready['files']), 'handoff_ready_refs_changed': ready_bad,
              'database_opened': False, 'database_current_rehash': False,
              'database_note': 'The prior local run observed changed WAL/SHM SHA with unknown cause; this review neither opens SQLite nor repeats the DB fingerprint check, and makes no new DB invariance claim.',
              'elapsed_s': round(time.perf_counter()-start, 3)}
    assert not changes and not history_changes and not a_changes and not ready_bad, result
    result['status'] = 'PASS_FOR_LISTED_FILES'; write(Q / 'integrity.json', result); print(json.dumps(result, ensure_ascii=False))

def fp_absolute(path):
    p = pathlib.Path(path); s = p.stat()
    return {'path': str(p), 'size_bytes': s.st_size, 'mtime_ns': s.st_mtime_ns, 'sha256': sha(p)}

def prepare_revision():
    dest = R / 'handoff' / (BATCH + '_revision_01')
    if (dest / 'READY.json').exists():
        for ref in strict(dest / 'READY.json')['files']:
            assert sha(ref['path']) == ref['sha256']
        print('REVISION_READY_RESUME_SKIP'); return
    task = strict(H / 'tasks/text_01.json')
    task.update(batch_id='revision_text_01', replaces='text_01', revision_reason='Independent evidence/time/semantic review failed; only these five may be revised before another Codex acceptance.')
    task['output_directory'] = str(A / 'revision_text_01')
    checks = strict(Q / 'evidence_checks.json')
    write(dest / 'task.json', task)
    write(dest / 'first_five_findings.json', {'reviewed_at': checks['at'], 'rows': [x for x in checks['results'] if x['path'].startswith('text_01/')],
                                           'batch_issue_counts': checks['issue_counts'],
                                           'unchanged_originals': True, 'accepted_text': 0, 'accepted_deep': 0})
    instruction = '''# 给A：只修5条文字样本，完成后停下

本轮Codex已独立核验原交付：23个完成清单、108个单视频JSON均合法并通过Schema与声明SHA，但内容验收0通过。78条文字的story_points是等距摘句，不能替代逐篇语义概括；25条深拆都是通用帧描述并含静态帧不能证明的微动；首批5条有13处时间不符，3条finished_at晚于本批COMPLETED。不得把生成文件/校验用时充作阅读分析用时。

## 本次唯一任务

读取本目录READY.json、task.json与first_five_findings.json，只重新分析task中5条文字。输出仅写竞品视频分析_2026-10-15/analysis_a/new_accounts_2026-10-16/revision_text_01/，不覆盖任何旧文件，不修改总表、文库或Codex状态。只做文字；不要继续剩余78条或25条深拆。5条落盘后停止，等Codex明确验收，不自行扩批。

1. 使用现有Antigravity模型逐条真实阅读全文，包括全部单元、最后单元和尾段。不得用Python规则、标题、等距段落、固定账号模板或循环拼句冒充语义分析。代码仅用于读取、按段回查时间、校验与落盘。单个工具显示被截断就按范围补读，不能仅凭unit_ids/read_all_units勾选自证。
2. 开始阅读前，先在本次独立目录原子写入本机实时时钟STARTED.json，列计划5个ID；实际完成再取时钟。单视频started_at/finished_at记录真实阅读工作的区间，不能统一写生成瞬间、未来时间或倒填整分钟。未记录的历史时间说明未知，不编造。COMPLETED只记录本批真实起止，不能早于单视频完成。
3. 每视频按原handoff包的text_analysis_schema.json产出。story_points概括这篇真实的具体论点/故事推进，并给本视频段ID依据；不得只抄每隔N段的碎句。以每单元的具体要点和尾段内容说明unit确实读全，可在coverage补unit_notes（unit_id、specific_summary、tail_segment_id），Schema允许附加字段。
4. Hook/Bridge/CTA引用必须是该段原文，start_s/end_s严格读取对应单元JSON的start_ms/end_ms后除以1000；不能凭时长估算、末尾凑齐或按常识补。主Hook不在0～3秒就如实标明；不把连续句全段冒充精确0～3秒。引用如果跨段，给segment_ids和每段范围，不伪装单段引句。
5. Bridge特指由内容转到阅读推荐/商品价值的连接，不把随意风景、转场或“作者说”当引书；不存在就present=false并说明。CTA分购买、借阅、收藏、关注、下集和出游号召；没有购买证据不得写购买。只能说“本次文本中未见明确购买CTA”，没有实际挂载信息不能断言“无挂车/无商品链接”。
6. book_relations区分提到、建议阅读和实际商品目标；讲解一本书不自动等于推荐或带货。不要从源文件名截一段当正式书名。派生规范书名保留ASR原引句，版本、ISBN与挂载未知。v_5d5e6d383a0f923f的钱目/钱木问题保留，纯文字输入引用Codex已核帧说明时须标“来自Codex质量清单”，不能声称自己本次看了图。
7. 原创迁移必须针对这篇具体结构提出独立问题；不复制竞品整篇，不凭竞品推定《大美中国》《365日走遍中国》实际版本、目录或不存在的分册。史实、地点消费数字、作者声称与已核事实分开，不做对外求证或新增云输入。
8. 自检合法JSON（拒绝NaN/Infinity/重复键）、Schema、身份/源SHA、所有unit、原引句、毫秒换算、书名/CTA分类。每文件先临时写入，校验后同目录原子改名。5条最终文件齐备后最后原子写符合completion_schema的COMPLETED.json（kind=text,batch_id=revision_text_01），列任务、Schema、所有原文单元及输出SHA、真实起止与未决。没有通过自检标AI_REVIEW；原问题不删。

仍限原先批准的本地文字/静态帧范围；此次仅文字。不得新收费API、原视频/音频上传、读取凭据、修改权限或操作无关工程。本次不要求生成新模板或账号总结；完成后停下。
'''
    (dest / '发给A_仅修订首批5条.md').write_text(instruction, encoding='utf-8', newline='\n')
    refs = [dest / 'task.json', dest / 'first_five_findings.json', dest / '发给A_仅修订首批5条.md',
            H / 'text_analysis_schema.json', H / 'completion_schema.json']
    refs += [pathlib.Path(u['path']) for v in task['videos'] for u in v['text_units']]
    refs += [pathlib.Path(u['text_path']) for v in task['videos'] for u in v['text_units']]
    write(dest / 'READY.json', {'schema_version': 'codex-revision-ready-1.0', 'ready_at': now(), 'batch_id': 'revision_text_01',
                              'scope': 'Exactly five text-only revisions; stop after delivery', 'files': [{'path': str(p), 'sha256': sha(p), 'size_bytes': p.stat().st_size} for p in refs]})
    print('REVISION_READY', len(task['videos']), len(refs))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['snapshot', 'evidence', 'integrity', 'revision'])
    args = parser.parse_args()
    {'snapshot': snapshot, 'evidence': evidence_audit, 'integrity': integrity, 'revision': prepare_revision}[args.phase]()
