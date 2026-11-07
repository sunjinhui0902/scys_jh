#!/usr/bin/env python3
"""Four-role replacement auditions; preserve V1 and two user-approved voices.

Default is preparation only. --generate makes the eight short paid requests.
Requests are checkpointed before sending; an uncertain request is never retried.
Voice Design results are previewed only, never sent to T2A for activation.
"""
import argparse
import hashlib
import html
import json
import shutil
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from voice_api_tts import ROOT, DEFAULT_CONFIG, load_config, resolve_api_key, synthesize_minimax
from assemble_voice_test import get_ffmpeg, run, probe_duration_ms, build_sequence

BASE = ROOT / '01_配音与音色库'
OLD = BASE / '六角色固定配音库_V1_20261107' / '试听交付_20261107_续做01'
OUT = BASE / '六角色换音试听_V2_20261107'
LABELS = {'boy': '男宝', 'dad': '爸爸', 'grandpa': '爷爷', 'grandma': '奶奶'}
COMMON = '你看，外面下雪了。我们一起去看看吧。'
TEXTS = {
    'boy': COMMON + '爷爷！爷爷！你看，我嘴冒烟了！爷爷，海水为什么这么咸呐？',
    'dad': COMMON + '孩子你还管不管啦！你先别急，咱们听孩子把话说完。',
    'grandpa': COMMON + '哟，再呼一口，爷爷看看。别怕，哪儿疼？伸过来让爷爷看看。',
    'grandma': COMMON + '那你走慢一点，看看月亮还跟不跟。哎哟我的小宝贝，快让奶奶抱抱。',
}
PLAN = [
    {'role': 'boy', 'option': 'A', 'voice_id': 'cute_boy', 'name': '可爱男童',
     'note': '官方童声候选；重点听男童辨识度、是否过于奶糯。'},
    {'role': 'boy', 'option': 'B', 'voice_id': 'Chinese (Mandarin)_Pure-hearted_Boy', 'name': '清澈邻家弟弟',
     'note': '官方标签为少年弟弟，可能偏大；作为清亮男声对照，不保证5—7岁感。'},
    {'role': 'dad', 'option': 'A', 'voice_id': 'Chinese (Mandarin)_Sincere_Adult', 'name': '真诚青年',
     'note': '目标：日常、自然接话；检查是否偏年轻。'},
    {'role': 'dad', 'option': 'B', 'voice_id': 'Chinese (Mandarin)_Reliable_Executive', 'name': '沉稳高管',
     'note': '官方中年男声；检查是否有过重的正式腔。'},
    {'role': 'grandpa', 'option': 'A', 'kind': 'design_preview', 'name': '爽朗微沙的爷爷（设计试听）',
     'prompt': '一位68岁中国爷爷的原创声音，男性，有清晰的老年声带纹理和少量自然沙哑，胸腔中低频适中，底气足。标准普通话，像在家和小孙子随口聊天，亲切爽朗，反应快，有轻微笑意和自然起伏。能温柔逗孩子，也能着急关心。不是播音员、不是纪录片旁白、不是卡通大爷，不压喉，不故意拖慢，不气若游丝。年龄感来自自然声带纹理，不靠夸张低音。',
     'note': '年龄与性格是设计目标，实际效果请试听。正式首次使用另收9.9元，此次不激活。'},
    {'role': 'grandpa', 'option': 'B', 'kind': 'design_preview', 'name': '温厚沉稳的爷爷（设计试听）',
     'prompt': '原创中文老年男性声音，72岁，温厚自然，有明显的岁月感、轻微颗粒感和松弛但有力的声带。音区比普通中年男性稍低但不低沉做作，标准普通话，居家聊天语气，吐字清晰，接话利索。面对孙女好奇时带着宠爱，面对磕碰时关切而不过度惊慌。避免播音腔、戏曲腔、喜剧卡通腔、青年低音炮、病弱颤抖和过慢节奏。',
     'note': '与A对照年龄感和生活感。正式首次使用另收9.9元，此次不激活。'},
    {'role': 'grandma', 'option': 'A', 'voice_id': 'Chinese (Mandarin)_Kind-hearted_Elder', 'name': '花甲奶奶',
     'note': '官方老年女声，优先检查真实年龄感、温暖和咬字。'},
    {'role': 'grandma', 'option': 'B', 'voice_id': 'Chinese (Mandarin)_Kind-hearted_Antie', 'name': '热心大婶',
     'note': '官方中年大婶声，作为生活感备选；年龄感可能不足。'},
]


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare():
    OUT.mkdir(exist_ok=True)
    (OUT / '单条试听').mkdir(exist_ok=True)
    report = json.loads((OLD / '试听报告.json').read_text(encoding='utf-8'))
    locked = {}
    for role, name in [('girl', '女宝'), ('mom', '妈妈')]:
        clips = [x for x in report['lines'] if x['role'] == role]
        locked[role] = {'name': name, 'status': 'approved_keep_voice',
                        'voice_id': clips[0]['voice_id'], 'source': '用户本轮明确保留',
                        'clips': [{'file': x['file'], 'sha256': x['sha256']} for x in clips]}
        sample = next(x for x in clips if x['file'].startswith('00_'))
        dst = OUT / '单条试听' / f'{name}_已保留.mp3'
        if not dst.exists():
            shutil.copyfile(OLD / '干声MP3' / sample['file'], dst)
        if digest(dst) != sample['sha256']:
            raise RuntimeError('Approved reference hash mismatch')
    write_json(OUT / '角色选择状态.json', {'approved': locked,
               'replace': {k: {'status': 'pending_selection', 'old_voice_rejected': True} for k in LABELS},
               'scope': '仅准备新音色短试听；选定后再换全套台词，原有配音保留'})
    write_json(OUT / '候选方案.json', [{**p, 'text': TEXTS[p['role']]} for p in PLAN])
    return report


def generate(cfg):
    # New dedicated output filenames prevent stale-cache substitution.
    cfg = {**cfg, 'max_retries': 1, 'model': 'speech-2.8-hd',
           'audio_setting': {'sample_rate': 32000, 'bitrate': 128000, 'format': 'mp3', 'channel': 1}}
    catalog = json.loads((ROOT / '.local/voice_reselect_20261107/system_voices.json').read_text(encoding='utf-8'))
    valid = {v['voice_id'] for v in catalog['system_voice']}
    for p in PLAN:
        if p.get('kind') != 'design_preview' and p['voice_id'] not in valid:
            raise RuntimeError('Voice ID absent from live system catalog')
    checkpoint = OUT / '请求记录.json'
    records = json.loads(checkpoint.read_text(encoding='utf-8')) if checkpoint.exists() else {}
    for p in PLAN:
        ident = p['role'] + '_' + p['option']
        target = OUT / '单条试听' / f"{LABELS[p['role']]}_{p['option']}.mp3"
        prior = records.get(ident)
        if prior:
            if prior['status'] == 'complete' and target.exists() and digest(target) == prior['sha256']:
                print('[复用本轮已完成]', ident, flush=True)
                continue
            raise RuntimeError(f'{ident} 已有未确认请求，不自动重复调用，请先核查请求记录')
        record = {**p, 'text': TEXTS[p['role']], 'status': 'request_started',
                  'started_at': datetime.now().astimezone().isoformat(), 'file': str(target.relative_to(OUT))}
        records[ident] = record
        write_json(checkpoint, records)
        print('[请求]', ident, p['name'], flush=True)
        try:
            if p.get('kind') == 'design_preview':
                # Only preview. Never pass this generated ID to synthesize_minimax.
                payload = {'prompt': p['prompt'], 'preview_text': record['text']}
                req = urllib.request.Request(str(cfg.get('base_url', 'https://api.minimaxi.com')).rstrip('/') + '/v1/voice_design',
                      data=json.dumps(payload).encode('utf-8'), headers={
                          'Authorization': 'Bearer ' + resolve_api_key(cfg), 'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=90) as response:
                    response_data = json.load(response)
                status = (response_data.get('base_resp') or {}).get('status_code')
                if status != 0 or not response_data.get('trial_audio') or not response_data.get('voice_id'):
                    raise RuntimeError('Design API did not return successful preview')
                target.write_bytes(bytes.fromhex(response_data['trial_audio']))
                record.update({'voice_id': response_data['voice_id'], 'activated_by_this_run': False,
                               'usage_characters': None, 'trial_price_per_10k': 2.0})
            else:
                line = {'voice_id': p['voice_id'], 'text': record['text'], 'speed': 1.0, 'pitch': 0, 'vol': 1.0}
                record['voice_setting'] = {k: line[k] for k in ('voice_id', 'speed', 'pitch', 'vol')}
                record['emotion'] = 'automatic_from_text'
                record.update(synthesize_minimax(cfg, line, target))
            record.update({'status': 'complete', 'sha256': digest(target)})
            print('[完成]', ident, flush=True)
        except Exception as exc:
            record.update({'status': 'failed_or_uncertain', 'error_type': type(exc).__name__})
            write_json(checkpoint, records)
            raise RuntimeError(f'{ident} 请求未完成，已停止且不会自动重试；详见本地请求记录') from None
        write_json(checkpoint, records)
    return records


def deliver(records):
    ffmpeg = get_ffmpeg()
    work = OUT / '标准WAV'
    work.mkdir(exist_ok=True)
    for ident, r in records.items():
        src = OUT / r['file']
        if r['status'] != 'complete' or digest(src) != r['sha256']:
            raise RuntimeError('Incomplete or mismatched source')
        r['duration_ms'] = probe_duration_ms(ffmpeg, src)
        dst = work / f'{ident}.wav'
        # Unified listening level for comparison; originals preserved untouched.
        run([ffmpeg, '-hide_banner', '-y', '-i', str(src), '-af', 'loudnorm=I=-18:TP=-2:LRA=11',
             '-ar', '44100', '-ac', '1', '-c:a', 'pcm_s16le', str(dst)])
    bundles = []
    for role, name in LABELS.items():
        dst = OUT / f'{name}_A然后B.wav'
        positions = build_sequence([work/f'{role}_A.wav', work/f'{role}_B.wav'], dst, 1300)
        run([ffmpeg, '-hide_banner', '-y', '-i', str(dst), '-c:a', 'libmp3lame', '-b:a', '192k', str(dst.with_suffix('.mp3'))])
        bundles.append({'role': role, 'file': dst.with_suffix('.mp3').name, 'starts_ms': positions})
    write_json(OUT/'试听报告.json', {'records': records, 'bundles': bundles, 'new_t2a_calls': 6,
               'new_design_preview_calls': 2, 'design_activation_calls': 0, 'human_acceptance': 'pending',
               'pricing': 'HD 3.5元/万计费字符；设计试听2元/万字符；选中设计声首次正式使用另9.9元/音色',
               'sources': ['https://platform.minimax.cn/docs/pricing/overview',
                           'https://platform.minimax.cn/docs/faq/system-voice-id'],
               'historical_parameters': 'V1 reference parameters inherited from V1 report'})
    render_page(records, bundles)


def render_page(records, bundles):
    esc = html.escape
    def audio(file):
        return f'<audio controls preload="none" src="{quote(Path(file).as_posix(), safe="/")}"></audio>'
    parts = ['<p class="notice">女宝、妈妈已保留。其余四位各听A、B两款，每款读相同台词，依次是日常句、钩子和接话。候选名称和说明是筛选方向，实际年龄与情绪请以听感为准。</p>',
             '<p>爷爷A/B是新设计音色的试听，尚未正式激活。若选中一款，首次正式合成另收一次9.9元。男宝B是少年、大婶B是中年备选，可能需要继续换。系统候选无这笔音色设计费。</p>',
             '<h2>已保留</h2><div class="grid">']
    for name in ['女宝', '妈妈']:
        parts.append(f'<article><h3>{name} · 已保留</h3>{audio("单条试听/"+name+"_已保留.mp3")}</article>')
    parts.append('</div>')
    for bundle in bundles:
        role, name = bundle['role'], LABELS[bundle['role']]
        parts.append(f'<h2>{name} · 先A后B</h2>{audio(bundle["file"])}<div class="grid">')
        for option in ['A', 'B']:
            r = records[role+'_'+option]
            parts.append(f'<article><h3>{option} · {esc(r["name"])}</h3>{audio(r["file"])}<p>{esc(r["note"])}</p><small>{esc(r["text"])}</small></article>')
        parts.append(f'</div><p><label>{name}选择 <select data-role="{role}"><option value="">待试听</option><option value="A">选A</option><option value="B">选B</option><option value="again">两款都换</option></select></label></p>')
    js = '''const key='family-voices-v2-20261107';let selections={};try{selections=JSON.parse(localStorage.getItem(key)||'{}')}catch(e){}
document.querySelectorAll('select[data-role]').forEach(s=>{s.value=selections[s.dataset.role]||'';s.addEventListener('change',()=>{selections[s.dataset.role]=s.value;try{localStorage.setItem(key,JSON.stringify(selections))}catch(e){}})});
document.addEventListener('play',e=>{if(e.target.tagName==='AUDIO')document.querySelectorAll('audio').forEach(a=>{if(a!==e.target)a.pause()})},true);
document.querySelector('#export').addEventListener('click',()=>{const data={girl:'keep',mom:'keep',...selections};const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='四角色试听选择.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)});'''
    doc = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>四角色换音试听 V2</title><style>body{margin:0;background:#f5f3ef;color:#242824;font:16px/1.75 system-ui,'Microsoft YaHei',sans-serif}main{max-width:960px;margin:auto;padding:32px 22px}h1{font-size:30px}h2{margin-top:36px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:18px}article{border:1px solid #ddd9ce;border-radius:14px;padding:18px;background:white}h3{margin:0 0 12px}audio{max-width:100%;width:350px}.notice{background:#e6eddc;padding:18px;border-radius:12px}select,button{font:inherit;padding:8px 14px}small{color:#62685f}button{margin-top:24px}</style><main><h1>四个角色重新选，两位声音已保留</h1>''' + ''.join(parts) + '<button id="export">导出四位的选择</button><p>也可以直接告诉我：男宝A、爸爸B、爷爷A、奶奶A；两款都不满意就说“都换”。页面选择仅保存在本机浏览器，不会自动传回对话。</p><script>'+js+'</script></main></html>'
    (OUT/'开始试听.html').write_text(doc, encoding='utf-8')
    (OUT/'试听选择.md').write_text('# 四角色换音试听 V2\n\n女宝、妈妈：按用户反馈保留。男宝、爸爸、爷爷、奶奶：待选，旧声音弃用。\n\n' + '\n'.join(f'- {LABELS[x["role"]]}：[先A后B]({quote(x["file"])})' for x in bundles) + '\n\n爷爷设计试听尚未激活，选中后首次正式合成另收9.9元/音色。\n试听页选择保存在本机，不自动传回对话。现有全套音频、主配置均未覆盖。\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generate', action='store_true')
    args = parser.parse_args()
    prepare()
    if not args.generate:
        chars = sum(sum(2 if '\u4e00' <= c <= '\u9fff' else 1 for c in TEXTS[p['role']]) for p in PLAN)
        print(json.dumps({'prepared': str(OUT.relative_to(ROOT)), 'max_calls': 8, 'estimated_upper_cost_cny': round(chars*3.5/10000, 4)}, ensure_ascii=False))
        return
    records = generate(load_config(DEFAULT_CONFIG))
    deliver(records)
    print('[交付完成]', str(OUT.relative_to(ROOT)), flush=True)


if __name__ == '__main__':
    main()
