"""Validate a completed A batch, preserve originals, and derive traceable records."""
import argparse
import collections
import copy
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / '竞品视频分析_2026-10-15'
sys.path.insert(0, str(R))
from align_segments import token_spans
from phase4_import import process, excerpt


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def stamp():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec='seconds')


def fingerprint(p):
    p = Path(p)
    return {'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
            'size': p.stat().st_size, 'mtime_ns': p.stat().st_mtime_ns}


def atomic(p, value):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(tmp, p)


def validate(value, schema, loc='$'):
    """Apply every validation keyword declared by this small, local V4 schema."""
    errors = []
    types = {'object': dict, 'array': list, 'string': str, 'null': type(None)}
    typ = schema.get('type')
    if typ:
        accepted = typ if isinstance(typ, list) else [typ]
        if not any(isinstance(value, types[t]) for t in accepted):
            return [loc + ':type']
    if 'enum' in schema and value not in schema['enum']:
        errors.append(loc + ':enum')
    if isinstance(value, str):
        if 'pattern' in schema and not re.search(schema['pattern'], value):
            errors.append(loc + ':pattern')
        if schema.get('format') == 'date-time':
            try:
                assert dt.datetime.fromisoformat(value.replace('Z', '+00:00')).utcoffset() is not None
            except (ValueError, AssertionError):
                errors.append(loc + ':date-time')
    if isinstance(value, dict):
        errors += [loc + ':missing:' + k for k in schema.get('required', []) if k not in value]
        for k, sub in schema.get('properties', {}).items():
            if k in value:
                errors += validate(value[k], sub, loc + '.' + k)
    if isinstance(value, list) and 'items' in schema:
        for i, item in enumerate(value):
            errors += validate(item, schema['items'], f'{loc}[{i}]')
    return errors


# These ranges were chosen after reading the ten complete transcripts and model-aligned segments.
FIXES = {
    'v_2ad33b07cfad615d': (['把话说的恰到好处'], (192.19, 212.535), (288.31, 291.015, '借阅剧情'), False),
    'v_325a2849484e6f15': (['闲谈高手'], (157.63, 173.49), (244.54, 245.475, '阅读推荐'), False),
    'v_f43b6f1228c21749': (['写给孩子的漫画经济学'], (130.62, 143.445), (207.44, 213.065, '软购买/共读建议'), False),
    'v_b2bbecb4fc6ef0e9': (['把话说的恰到好处', '把事做的恰到好处'], (217.98, 242.634), (289.15, 290.685, '剧情阅读回应'), False),
    'v_74a64cf3aca9595d': (['把话说的恰到好处'], (95.85, 117.905), (153.6, 166.315, '阅读与用途推荐'), False),
    'v_d66d5d68290f0e95': (['闲谈高手'], (150.79, 174.98), (209.68, 221.555, '阅读与用途推荐'), False),
    'v_38eb65b8de747391': (['国之脊梁'], (411.63, 442.465), (442.92, 451.075, '明确商品链接/下单'), True),
    'v_4ed4d46352185f2f': (['史记', '山海经'], None, (422.12, 432.125, '连载/关注'), False),
    'v_5ae6f6253ad7b999': (['人一生要看的100个博物馆〔仅标题〕'], None, (357.31, 364.995, '连载/关注'), False),
    'v_7e0d1a4f77167eb4': (['道德经〔引用〕'], None, None, False),
}


def normalize(v, row, path, policy, schema):
    raw = read(path)
    errors = validate(raw, schema)
    assert not errors, (v, errors)
    assert raw['video_id'] == v and raw.get('account') == row['account']
    identity = []
    source = raw.get('source_video_path')
    if isinstance(source, dict) and source.get('source_path') == row['source_path']:
        identity.append('A源路径误存为来源对象；导入版从manifest恢复字符串，原件保留')
    else:
        assert source == row['source_path'], (v, 'source mismatch')
    rec = process(v, row, path, policy)
    # The original schema permits an extra source field; identity checking is a separate gate.
    rec['schema_errors'] = [e for e in rec['schema_errors'] if e != '身份/来源不匹配']
    rec['raw_schema_errors'] = errors
    rec['raw_identity_issues'] = identity
    rec['corrections'] += identity
    rec['source_A_path'] = str(R / 'analysis_a/supplement_01' / path.parent.name / path.name)
    rec['snapshot_path'] = str(path)
    rec['source_video_path'] = row['source_path']
    rec['A_input_mode_verified'] = 'text_only'
    rec['delivery_protocol'] = 'A操作记录为直接写最终文件，原子交付未证明；本次完成清单哈希一致、两次稳定读取后由Codex原子冻结并按Schema校验再导入'
    rec['analyzed_at_note'] = 'A自报时间，不用于推算真实耗时；该批实际开始结束时间未提供'
    rec['acceptance_scope'] = 'Codex核对全文ASR、模型时间及所见4帧；A读取截图的过程未证明；未验证全片声音、史实、SKU或效果'
    n = rec['normalized']
    n['visual_and_audio']['audio_style'] = '无法确认（本轮依据文字/静帧，未听核音色、配乐或笑声掌声）'
    n['visual_and_audio']['review_method'] = 'Codex逐条查看既有4帧；新10条40帧已查看；仅说明所见画面'
    rec['corrections'].append('A输入按可追溯文字限定；音色/原声/笑声掌声结论撤回，Codex静帧核查另列')
    if v in FIXES:
        books, bridge, closing, shop = FIXES[v]
        ss = read(R / 'segments' / f'{v}.aligned.json')['segments']
        n['mentioned_books'] = books
        n['recommended_book'] = ('未知（口播候选：' + books[0] + '；SKU/版本未核）') if bridge else '无明确阅读推荐'
        if v == 'v_38eb65b8de747391':
            n['recommended_book'] = '国之脊梁（口播与449.241秒书封一致，版本未核）'
        n['bridge'] = {'present': bool(bridge), 'start_s': None, 'end_s': None, 'text': '完整转录未见明确引书', 'type': '无'}
        if bridge:
            n['bridge'].update(excerpt(ss, *bridge), type='情境/故事转阅读推荐', source='本地ASR分段，模型估计时间')
        n['cta'] = {'present': bool(closing), 'start_s': None, 'end_s': None, 'text': '完整转录未见明确行动引导', 'type': '无'}
        if closing:
            a, b, typ = closing
            n['cta'].update(excerpt(ss, a, b), type=typ, source='本地ASR分段，模型估计时间')
        rec['explicit_shopping_entry'] = shop
        rec['soft_purchase_suggestion'] = v == 'v_f43b6f1228c21749'
        rec['corrections'] += ['Bridge/结尾按全文与实际分段重新定位，原A时间与引文另存', '按引用/标题/阅读/借阅/商品入口分口径更正书名及CTA']
        rec['schema_errors'] = []
        rec['unresolved_issues'] = []
        if v == 'v_f43b6f1228c21749':
            rec['unresolved_issues'].append('实体商品正式书名、版本与书封待核；末帧为内页；经济学解释及教育效果仅为素材声称')
            n['narrative_structure'] = '生活提问→大人初答不足→孩子以阅读解释→漫画读物→家长共读/软购买建议'
        if v == 'v_38eb65b8de747391':
            rec['corrections'].append('449.241秒既有帧可读国之脊梁，撤销缺书封申请；不能据此确认与其他篇目同一ISBN/SKU')
            n['visual_and_audio']['book_appearance'] = '449.241秒帧可见国之脊梁书封；出版社/ISBN/版次未核'
        if v == 'v_7e0d1a4f77167eb4':
            n['visual_and_audio'].update(visual_type='人物出镜/讲述式画面；真实性与声音未核', subtitle_style='白字字幕', book_appearance='四帧未见商品书封')
        if v in ['v_4ed4d46352185f2f', 'v_5ae6f6253ad7b999']:
            n['visual_and_audio'].update(visual_type='历史/文物风格插画与场景混剪；所见有生成内容提示', book_appearance='四帧未见商品书封；标题书名不等于荐书')
        rec['incremental_findings_A'] = copy.deepcopy(raw.get('incremental_findings', {}))
        rec['incremental_acceptance'] = ('单样本结构草案，非已验证独立模板' if v == 'v_f43b6f1228c21749'
                                        else '表达方式候选，效果未知' if v == 'v_38eb65b8de747391' else '暂未见新的独立带货结构；保留引用/连载对照价值')
    rec['A_original_window_checks'] = rec.pop('evidence_checks', {})
    rec['evidence_checks'] = {}
    for key in ['bridge', 'cta']:
        z = n[key]
        if z['present']:
            assert 0 <= z['start_s'] < z['end_s'] <= row['duration_s'] + 0.001
        rec['evidence_checks'][key] = {'final_imported': copy.deepcopy(z),
                                       'scope': '最终导入区段；A原时间窗口的初检单独保留在A_original_window_checks',
                                       'segments_path': str(R / 'segments' / f'{v}.aligned.json')}
    rec['schema_valid'] = not rec['schema_errors']
    rec['status'] = 'AI_REVIEW' if rec['schema_errors'] or rec['unresolved_issues'] else 'AI_OK'
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--interrupt-after', type=int)
    args = ap.parse_args()
    a = R / 'analysis_a/supplement_01'
    snapshot = R / 'manifest/supplement_01_input_snapshot'
    complete = read(a / '完成清单.json')
    plan = read(R / 'handoff/supplement_01/batch_plan.json')
    expected = {e['video_id']: 'videos' for e in plan['new_videos']}
    expected.update({e['video_id']: 'reviews' for e in plan['reviews']})
    listed = {e['video_id']: e for e in complete['items']}
    assert set(listed) == set(expected) and len(listed) == 15
    metadata = []
    for p in sorted(a.rglob('*')):
        if not p.is_file() or p.suffix not in ['.json', '.md']:
            continue
        first = fingerprint(p)
        data = p.read_bytes()
        assert fingerprint(p) == first
        rel = p.relative_to(a)
        if p.name.startswith('v_'):
            vid = p.stem
            assert p.parent.name == expected[vid]
            assert first['sha256'] == listed[vid]['sha256']
        target = snapshot / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            tmp = target.with_name(target.name + '.tmp')
            tmp.write_bytes(data)
            os.replace(tmp, target)
        assert hashlib.sha256(target.read_bytes()).hexdigest() == first['sha256']
        metadata.append(first)
    assert len(metadata) == 19
    for e in plan['new_videos'] + plan['reviews']:
        for ref in e['input_snapshot']:
            assert fingerprint(ref['path'])['sha256'] == ref['sha256']
    rows = [json.loads(s) for s in (R / 'manifest/manifest.jsonl').read_text(encoding='utf-8').splitlines()]
    lookup = {r['video_id']: r for r in rows}
    policy = fingerprint(__file__)['sha256']
    out = R / 'manifest/supplement_01_records'
    schema = read(R / 'handoff/analysis_schema.json')
    new_count = skipped = 0
    checkpoints = []
    for vid, kind in sorted(expected.items()):
        src, target = snapshot / kind / f'{vid}.json', out / f'{vid}.json'
        old = read(target) if target.exists() else {}
        if old.get('input_sha256') == fingerprint(src)['sha256'] and old.get('policy_sha256') == policy:
            skipped += 1
            continue
        rec = normalize(vid, lookup[vid], src, policy, schema)
        atomic(target, rec)
        new_count += 1
        checkpoints.append(fingerprint(target))
        if args.interrupt_after and new_count == args.interrupt_after:
            atomic(R / 'manifest/supplement_01_resume_before.json', {'at': stamp(), 'checkpoints': checkpoints})
            os._exit(75)
    if new_count == 0 and (R / 'manifest/supplement_01_import_summary.json').exists():
        print(json.dumps({'status': 'RESUME_SKIP', 'records_unchanged': skipped}))
        return
    combined = {p.stem: read(p) for p in (R / 'manifest/phase4_records').glob('v_*.json')}
    combined.update({p.stem: read(p) for p in out.glob('v_*.json')})
    assert len(combined) == 35
    for vid, rec in combined.items():
        n = rec['normalized']
        if 'explicit_shopping_entry' not in rec:
            rec['explicit_shopping_entry'] = bool(n['cta']['present'] and re.search(r'左下|下方.{0,4}链接|放下面|商品橱窗|主页.{0,5}橱窗', n['cta']['text']))
        rec.setdefault('soft_purchase_suggestion', False)
        rec['record_path'] = str(out / f'{vid}.json' if vid in expected else R / 'manifest/phase4_records' / f'{vid}.json')
    statuses = dict(collections.Counter(z['status'] for z in combined.values()))
    accounts = []
    for account in sorted({r['account'] for r in rows}):
        rs = [z for z in combined.values() if z['account'] == account]
        rr = [r for r in rows if r['account'] == account]
        accounts.append({'account': account, 'source_count': len(rr), 'unique_count': len({r['sha256'] for r in rr}),
                         'sample_count': len(rs), 'ai_ok': sum(z['status'] == 'AI_OK' for z in rs),
                         'ai_review': sum(z['status'] == 'AI_REVIEW' for z in rs),
                         'book_introduction_count': sum(z['normalized']['bridge']['present'] for z in rs),
                         'shopping_entry_count': sum(z['explicit_shopping_entry'] for z in rs),
                         'soft_purchase_count': sum(z['soft_purchase_suggestion'] for z in rs),
                         'sample_ids': [z['video_id'] for z in rs]})
    resume = read(R / 'manifest/supplement_01_resume_before.json')
    preserved = sum(fingerprint(c['path']) == c for c in resume['checkpoints'])
    summary = {'at': stamp(), 'status': 'PARTIAL', 'new_samples': 10, 'reviews': 5,
               'raw_schema_pass': 15, 'source_identity_repairs': 10, 'A_source_files': metadata,
               'combined_sample_count': 35, 'combined_status_counts': statuses,
               'source_path_ai_pending': len(rows) - 35, 'unique_outside_deep_scope': 317 - 35,
               'accounts': accounts, 'records': combined,
               'resume': {'first_exit_code': 75, 'checkpoints': len(resume['checkpoints']), 'preserved': preserved, 'skipped': skipped},
               'full_text_semantic_done': 0, 'full_text_semantic_pending': 317,
               'delivery_atomicity_proven': False, 'delivery_protocol_note': '19个文件冻结且哈希与交付清单核对后再校验；A原子交付过程和真实耗时仍未证明'}
    atomic(R / 'manifest/supplement_01_import_summary.json', summary)
    print(json.dumps({k: summary[k] for k in ['status', 'combined_sample_count', 'combined_status_counts', 'source_path_ai_pending', 'resume']}, ensure_ascii=True))


if __name__ == '__main__':
    main()
