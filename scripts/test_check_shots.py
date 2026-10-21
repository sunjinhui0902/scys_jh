import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
import json
from pathlib import Path
from scripts.fast_draft_pipeline import parse_gemini_markdown

projects = [
    '01_平遥古城_单集精讲',
    '02_延安宝塔山_单集精讲',
    '03_开封清明上河园_单集精讲',
    '04_苏州拙政园_单集精讲',
    '05_杭州西湖_单集精讲'
]

for p in projects:
    pdir = Path('03_视频成片与工程') / p
    md = open(pdir / '01_文案与分镜/口播文案.md', encoding='utf-8').read()
    v, secs, m = parse_gemini_markdown(md)
    print(f'=== {p} ({len(secs)} shots) ===')
    for s in secs:
        char_count = sum(len(c) for c in s['clauses'])
        if char_count < 15:
            print(f"  Shot {s['shot_index']}: {char_count} chars, top_bar={s.get('top_bar')}, clauses={s['clauses']}")
