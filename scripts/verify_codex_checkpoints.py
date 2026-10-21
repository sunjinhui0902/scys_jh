# -*- coding: utf-8 -*-
import json
from pathlib import Path

base_dir = Path("03_视频成片与工程")
targets = {
    "01_平遥古城_单集精讲": ["说到这儿", "肚子里的词儿就不够用了"],
    "02_延安宝塔山_单集精讲": ["说到这儿"],
    "03_开封清明上河园_单集精讲": ["就全印在孩子脑子里了"],
    "04_苏州拙政园_单集精讲": ["居然稳稳地出现在了"],
    "05_杭州西湖_单集精讲": ["不知道怎么把苏东坡"],
}

for proj, phrases in targets.items():
    p = base_dir / proj / "asr_alignment.json"
    with open(p, "r", encoding="utf-8") as f:
        d = json.load(f)
    print(f"=== {proj} ===")
    sentences = d.get("sentence_info", [])
    for phrase in phrases:
        found = False
        for s in sentences:
            if phrase in s["text"]:
                print(f"  Sentence match '{phrase}': {s['start']/1000.0:.2f}s - {s['end']/1000.0:.2f}s: {s['text']}")
                found = True
        if not found:
            # search character timestamps
            txt = d.get("text", "")
            if phrase in txt:
                idx = txt.index(phrase)
                # find timestamps for clean chars
                clean_idx = 0
                stamps = d.get("timestamp", [])
                for i, c in enumerate(txt):
                    if i == idx:
                        break
                    if c not in "，。！？；、… \n\r":
                        clean_idx += 1
                if clean_idx < len(stamps):
                    print(f"  Char match '{phrase}': start={stamps[clean_idx][0]/1000.0:.2f}s")
