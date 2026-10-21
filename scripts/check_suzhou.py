# -*- coding: utf-8 -*-
import json
with open('03_视频成片与工程/04_苏州拙政园_单集精讲/asr_alignment.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
for s in d.get('sentence_info', []):
    t = s['text']
    if any(k in t for k in ['北寺塔', '出现', '稳稳', '花园', '屋檐', '借景']):
        print(f"{s['start']/1000.0:.2f}s - {s['end']/1000.0:.2f}s: {t}")
