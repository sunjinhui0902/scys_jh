# -*- coding: utf-8 -*-
import json
from pathlib import Path

p = Path("03_视频成片与工程/01_平遥古城_单集精讲/asr_alignment.json")
with open(p, "r", encoding="utf-8") as f:
    data = json.load(f)

print("Keys:", list(data.keys()))
sentences = data.get("sentence_info", [])
print(f"Total sentences: {len(sentences)}")

for s in sentences:
    t = s.get("text", "")
    if "说到这儿" in t or "肚子里的词" in t or "神龟" in t or "乌鬼" in t:
        print(f"{s['start']/1000.0:.3f}s - {s['end']/1000.0:.3f}s (dur={s['end']-s['start']}ms): {t}")
