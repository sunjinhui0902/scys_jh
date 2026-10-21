import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
import json
from pathlib import Path

pdir = Path('03_视频成片与工程/05_杭州西湖_单集精讲')
d = json.load(open(pdir / 'asr_alignment.json', encoding='utf-8'))
for s in d['sentence_info']:
    txt = s['text']
    if any(k in txt for k in ['船', '岳', '塔', '庙', '印月']):
        print(f"{s['start']/1000:.2f}s - {s['end']/1000:.2f}s: {txt}")


