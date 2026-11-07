#!/usr/bin/env python3
"""Free Edge grandfather auditions, preserving the five approved family voices.

No MiniMax generation, design, cloning, or activation calls are made.
"""
import hashlib
import html
import json
import shutil
from pathlib import Path
from urllib.parse import quote

from voice_api_tts import ROOT, synthesize_edge
from assemble_voice_test import get_ffmpeg, run, build_sequence, probe_duration_ms

BASE = ROOT / '01_配音与音色库'
PREVIOUS = BASE / '六角色换音试听_V2_20261107'
OUT = BASE / '爷爷免费候选_V3_20261107'
TEXT = '你看，外面下雪了。我们一起去看看吧。哟，再呼一口，爷爷看看。别怕，哪儿疼？伸过来让爷爷看看。'
CANDIDATES = [
    {'option': 'A', 'name': '沉厚版', 'edge_voice': 'zh-CN-YunjianNeural', 'edge_rate': '-10%', 'edge_pitch': '-8Hz',
     'note': '目标是沉厚、有底气；重点听是否仍有解说腔。'},
    {'option': 'B', 'name': '亲切版', 'edge_voice': 'zh-CN-YunxiNeural', 'edge_rate': '-12%', 'edge_pitch': '-12Hz',
     'note': '目标是亲切、接话自然；可能仍偏年轻。降低音调不能保证老年感。'},
]
LABELS = {'boy': '男宝', 'girl': '女宝', 'dad': '爸爸', 'mom': '妈妈', 'grandma': '奶奶'}


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=True)
    audio_dir = OUT / '单条试听'
    audio_dir.mkdir(exist_ok=True)
    previous = json.loads((PREVIOUS / '试听报告.json').read_text(encoding='utf-8'))['records']
    original_state = json.loads((PREVIOUS / '角色选择状态.json').read_text(encoding='utf-8'))
    chosen = {}
    for role, option in [('boy', 'A'), ('dad', 'B'), ('grandma', 'B')]:
        rec = previous[role+'_'+option]
        src = PREVIOUS / rec['file']
        assert digest(src) == rec['sha256']
        dst = audio_dir / f'{LABELS[role]}_已选{option}.mp3'
        if not dst.exists():
            shutil.copyfile(src, dst)
        assert digest(dst) == rec['sha256']
        chosen[role] = {'name': LABELS[role], 'status': 'approved', 'option': option,
                        'engine': 'minimax', 'voice_id': rec['voice_id'], 'speed': 1.0, 'pitch': 0,
                        'sample': dst.relative_to(OUT).as_posix(), 'sha256': rec['sha256'],
                        'source': '用户明确选择', 'billing': '系统音色无额外音色费，新台词合成按字计费'}
    for role in ['girl', 'mom']:
        src = PREVIOUS / '单条试听' / f'{LABELS[role]}_已保留.mp3'
        dst = audio_dir / src.name
        if not dst.exists():
            shutil.copyfile(src, dst)
        assert digest(dst) == digest(src)
        chosen[role] = {'name': LABELS[role], 'status': 'approved_keep_voice', 'engine': 'minimax',
                        'voice_id': original_state['approved'][role]['voice_id'],
                        'sample': dst.relative_to(OUT).as_posix(), 'sha256': digest(src),
                        'source': '用户明确保留', 'billing': '系统音色无额外音色费，新台词合成按字计费'}
    decision = {'approved': chosen, 'grandpa': {'status': 'pending_free_candidate_selection',
                'cancelled_voice_id': previous['grandpa_A']['voice_id'],
                'reason': '用户取消额外收费的设计音色', 'design_activation_authorized': False},
                'cost_policy': '本轮仅免费Edge试听，不发起任何MiniMax付费调用；选中的是声音，未授权新设计音色费用',
                'sample_root': OUT.relative_to(ROOT).as_posix()}
    write(OUT/'角色选择状态.json', decision)
    state_path = ROOT/'config/voice_api/role_selections.json'
    write(state_path, decision)
    records = []
    ffmpeg = get_ffmpeg()
    wavs = []
    for candidate in CANDIDATES:
        file = audio_dir / f'爷爷_免费{candidate["option"]}.mp3'
        if not file.exists():
            synthesize_edge({}, {**candidate, 'text': TEXT}, file)
        run([ffmpeg, '-v', 'error', '-i', str(file), '-f', 'null', '-'])
        wav = OUT / f'爷爷_免费{candidate["option"]}.wav'
        run([ffmpeg, '-hide_banner', '-y', '-i', str(file), '-af', 'loudnorm=I=-18:TP=-2:LRA=11',
             '-ac', '1', '-ar', '44100', '-c:a', 'pcm_s16le', str(wav)])
        wavs.append(wav)
        records.append({**candidate, 'engine': 'edge', 'text': TEXT, 'file': file.relative_to(OUT).as_posix(),
                        'sha256': digest(file), 'duration_ms': probe_duration_ms(ffmpeg, file)})
        print('[完成免费试听]', candidate['option'], flush=True)
    master = OUT/'爷爷_免费A然后B.wav'
    positions = build_sequence(wavs, master, 1300)
    run([ffmpeg, '-hide_banner', '-y', '-i', str(master), '-c:a', 'libmp3lame', '-b:a', '192k', str(master.with_suffix('.mp3'))])
    report = {'approved': chosen, 'candidates': records, 'new_minimax_calls': 0, 'new_voice_design_calls': 0,
              'voice_activation_calls': 0, 'sequence_starts_ms': positions, 'age_acceptance': 'pending_human_audition'}
    write(OUT/'试听报告.json', report)
    def player(file):
        return '<audio controls preload="none" src="'+quote(file, safe='/')+'"></audio>'
    parts = ['<p class="notice">收费的爷爷A已取消，未激活。本轮新试听只用Edge，没有MiniMax付费调用。下方免费A/B与上一轮爷爷A/B是不同音色。</p>',
             '<h2>爷爷：免费A → 免费B</h2>'+player('爷爷_免费A然后B.mp3')+'<div class="grid">']
    for r in records:
        parts.append('<article><h3>免费'+r['option']+' · '+r['name']+'</h3>'+player(r['file'])+'<p>'+html.escape(r['note'])+'</p></article>')
    parts.append('</div><p>听完直接回复“免费A”或“免费B”，都不满意也可以继续换。Edge没有独立的老年男声标签，实际年龄感需要试听确认。</p><h2>这五位已经选定</h2><div class="grid">')
    for role in ['boy', 'girl', 'dad', 'mom', 'grandma']:
        r=chosen[role]
        parts.append('<article><h3>'+r['name']+' · 已保留'+r.get('option','')+'</h3>'+player(r['sample'])+'</article>')
    parts.append('</div><p>上面五位仍是MiniMax系统音色：没有额外音色设计费，新台词合成仍按字收费。本轮只复制已生成样本。原有声音库和配置未覆盖。</p>')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>爷爷免费候选 V3</title><style>body{background:#f5f3ef;color:#242824;font:16px/1.75 system-ui,'Microsoft YaHei',sans-serif;margin:0}main{max-width:950px;margin:auto;padding:32px 22px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px}article{background:white;border:1px solid #ddd9ce;border-radius:12px;padding:18px}audio{width:350px;max-width:100%}.notice{background:#e6eddc;border-radius:12px;padding:18px}h2{margin-top:34px}h3{margin-top:0}</style><main><h1>爷爷改用免费候选，其他五位保留</h1>'''+''.join(parts)+'''<script>document.addEventListener('play',e=>{if(e.target.tagName==='AUDIO')document.querySelectorAll('audio').forEach(a=>{if(a!==e.target)a.pause()})},true)</script></main></html>'''
    (OUT/'开始试听.html').write_text(page,encoding='utf-8')
    print('[完成]',OUT.relative_to(ROOT),flush=True)


if __name__=='__main__':
    main()
