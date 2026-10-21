import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import json
from pathlib import Path

draft_path = Path(r"C:\Users\Miche\AppData\Local\JianyingPro\User Data\Projects\com.lveditor.draft\【图书带货】带孙辈长见识：第10名·山西平遥_音字对齐修订_20261022\draft_content.json")
data = json.loads(draft_path.read_text(encoding="utf-8"))

print("=== 1. TRACKS OVERVIEW ===")
tracks = data.get("tracks", [])
for t in tracks:
    print(f"Track: type={t.get('type')}, name={t.get('name')}, segments={len(t.get('segments', []))}")

print("\n=== 2. AUDIO & BGM VOLUMES & FADES ===")
for t in tracks:
    if t.get("name") in ["解说人声轨(+3dB)", "国风背景音乐(-13dB)"]:
        print(f"Track: {t.get('name')}")
        for s in t.get("segments", []):
            vol = s.get("volume")
            fade = s.get("fade")
            source_tr = s.get("source_timerange")
            target_tr = s.get("target_timerange")
            print(f"  Segment: start={target_tr['start']/1e6:.2f}s, dur={target_tr['duration']/1e6:.2f}s, vol={vol}, fade={fade}")

print("\n=== 3. SUBTITLE SAMPLING & AUDIT ===")
texts_dict = {t["id"]: t for t in data.get("materials", {}).get("texts", [])}
for t in tracks:
    if t.get("name") == "中老年大字底字幕":
        segs = t.get("segments", [])
        print(f"Total Subtitles: {len(segs)}")
        # Check first 5
        print("--- First 5 Subtitles ---")
        for s in segs[:5]:
            mat_id = s.get("material_id")
            content_json = texts_dict.get(mat_id, {}).get("content", "{}")
            txt = json.loads(content_json).get("text", "")
            tr = s.get("target_timerange")
            print(f"  [{tr['start']/1e6:.2f}s - {(tr['start']+tr['duration'])/1e6:.2f}s] ({tr['duration']/1e6:.2f}s) {txt}")
            
        print("--- Problem Checkpoints in Pingyao ---")
        for s in segs:
            mat_id = s.get("material_id")
            content_json = texts_dict.get(mat_id, {}).get("content", "{}")
            txt = json.loads(content_json).get("text", "")
            if any(k in txt for k in ["说到这儿", "词儿", "肚子", "祖国", "明清", "神龟"]):
                tr = s.get("target_timerange")
                print(f"  [{tr['start']/1e6:.2f}s - {(tr['start']+tr['duration'])/1e6:.2f}s] ({tr['duration']/1e6:.2f}s) {txt}")
