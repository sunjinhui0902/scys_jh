import os
import sys
import re
import subprocess
from pathlib import Path

# UTF-8 编码安全保障
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path("d:/fuye")

updates = [
    {
        "code": "M7",
        "dir": ROOT / "03_视频成片与工程/M7_11-09_0700",
        "txt_replacements": [("《冷知识1000问》", "《冷门知识1000问》")],
        "md_replacements": [("《冷知识1000问》", "《冷门知识1000问》")],
        "jia": "冬天里的小问题",
        "yi": "随问随答长见识"
    },
    {
        "code": "N2",
        "dir": ROOT / "03_视频成片与工程/N2_11-04_1230",
        "txt_replacements": [("《冷知识1000问》", "《冷门知识1000问》")],
        "md_replacements": [("《冷知识1000问》", "《冷门知识1000问》")],
        "jia": "千年木塔的门道",
        "yi": "斗拱里藏着大智慧"
    },
    {
        "code": "N4",
        "dir": ROOT / "03_视频成片与工程/N4_11-06_1230",
        "txt_replacements": [("《冷知识1000问》", "《冷门知识1000问》")],
        "md_replacements": [("《冷知识1000问》", "《冷门知识1000问》")],
        "jia": "古人的排水智慧",
        "yi": "不用电的自动开关"
    },
    {
        "code": "N7",
        "dir": ROOT / "03_视频成片与工程/N7_11-09_1230",
        "txt_replacements": [("《冷知识1000问》", "《冷门知识1000问》")],
        "md_replacements": [("《冷知识1000问》", "《冷门知识1000问》")],
        "jia": "大广场为何不种树",
        "yi": "礼仪之地自有道理"
    },
    {
        "code": "M4",
        "dir": ROOT / "03_视频成片与工程/M4_11-05_0700",
        "txt_replacements": [
            ("撕下来还能贴墙上。橱窗里有，库存不多。", "取下来还能贴墙上。橱窗里有。"),
            ("撕下来还能贴墙上。橱窗里有。库存不多。", "取下来还能贴墙上。橱窗里有。"),
            ("撕下来还能贴墙上", "取下来还能贴墙上"),
            ("，库存不多", ""),
            ("。库存不多", "")
        ],
        "md_replacements": [
            ("撕下来还能贴墙上。橱窗里有，库存不多。", "取下来还能贴墙上。橱窗里有。"),
            ("撕下来还能贴墙上。橱窗里有。库存不多。", "取下来还能贴墙上。橱窗里有。"),
            ("撕下来还能贴墙上", "取下来还能贴墙上"),
            ("，库存不多", ""),
            ("。库存不多", "")
        ],
        "jia": "冬天陪孩子读首诗",
        "yi": "一天一首慢慢积累"
    }
]

for u in updates:
    txt_path = u["dir"] / "口播.txt"
    md_path = u["dir"] / "01_文案与分镜" / "口播文案.md"
    
    txt = txt_path.read_text(encoding="utf-8")
    for o, n in u["txt_replacements"]:
        txt = txt.replace(o, n)
    txt_path.write_text(txt, encoding="utf-8")
        
    md = md_path.read_text(encoding="utf-8")
    for o, n in u["md_replacements"]:
        md = md.replace(o, n)
        
    jia_text = u["jia"]
    yi_text = u["yi"]
    md = re.sub(r"【镜头01】（.*?导航标[：:]\s*[^/）\)]+.*?\）", f"【镜头01】（运镜: pull / 导航标: {jia_text}）", md)
    md = re.sub(r"【镜头02】（.*?导航标[：:]\s*[^/）\)]+.*?\）", f"【镜头02】（运镜: push / 导航标: {jia_text}）", md)
    md = re.sub(r"【镜头03】（.*?导航标[：:]\s*[^/）\)]+.*?\）", f"【镜头03】（运镜: push / 导航标: {jia_text}）", md)
    md = re.sub(r"【镜头04】（.*?导航标[：:]\s*[^/）\)]+.*?\）", f"【镜头04】（运镜: push / 导航标: {yi_text}）", md)
    md = re.sub(r"【镜头05】（.*?导航标[：:]\s*[^/）\)]+.*?\）", f"【镜头05】（运镜: pan_right / 导航标: {yi_text}）", md)
    md = re.sub(r"【镜头06】（.*?导航标[：:]\s*[^/）\)]+.*?\）", f"【镜头06】（运镜: push / 导航标: {yi_text}）", md)
    
    md_path.write_text(md, encoding="utf-8")
    print(f"Updated text and md for {u['code']}")

print("All updates written. Now synthesizing and building drafts...")
for u in updates:
    cmd = [sys.executable, str(ROOT / "scripts" / "fast_draft_pipeline.py"), "init", "--dir", str(u["dir"]), "--force-synth"]
    print(f"\n>>> Running pipeline for {u['code']} ...")
    subprocess.run(cmd, check=True)
