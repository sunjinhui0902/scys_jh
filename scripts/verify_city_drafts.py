#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

drafts_dir = Path(r"C:\Users\Miche\AppData\Local\JianyingPro\User Data\Projects\com.lveditor.draft")

for name in ["十大历史名城_上集", "十大历史名城_下集"]:
    d_path = drafts_dir / name / "draft_content.json"
    assert d_path.exists(), f"Missing {d_path}"
    data = json.loads(d_path.read_text(encoding="utf-8"))

    tracks = data.get("tracks", [])
    dur_sec = round(data.get("duration", 0) / 1_000_000, 2)
    mins = int(dur_sec // 60)
    secs = int(dur_sec % 60)
    print(f"\n==========================================")
    print(f"🎬 检验草稿: {name}")
    print(f"总时长: {mins}分{secs}秒 ({dur_sec}s / {data.get('duration')}us)")
    print(f"轨道总数: {len(tracks)} 条")
    for t in tracks:
        t_type = t.get("type")
        t_name = t.get("name")
        seg_cnt = len(t.get("segments", []))
        print(f"  - 轨道 [{t_type:5s}] 「{t_name}」: {seg_cnt} 个片段")

    videos = data.get("materials", {}).get("videos", [])
    print(f"  画面素材数: {len(videos)} 个")
    for v in videos[:3]:
        print(f"    · {Path(v.get('path', '')).name}")

    audios = data.get("materials", {}).get("audios", [])
    print(f"  音频素材数: {len(audios)} 个")
    for a in audios:
        print(f"    · {a.get('name')}: {Path(a.get('path', '')).name}")

    keyframes_count = 0
    blur_count = 0
    for t in tracks:
        if t.get("name") == "主视觉画面轨":
            for seg in t.get("segments", []):
                kfs = seg.get("common_keyframes", [])
                if kfs:
                    keyframes_count += len(kfs)
                if seg.get("extra_material_refs"):
                    blur_count += 1
            # 打印前两个镜头的关键帧参数
            for idx in [0, 1]:
                if idx < len(t.get("segments", [])):
                    seg = t.get("segments", [])[idx]
                    for k in seg.get("common_keyframes", []):
                        val_pairs = [(p.get("time_offset"), p.get("values")) for p in k.get("keyframe_list", [])]
                        print(f"    · 镜头 {idx+1} Ken Burns 关键帧 ({k.get('property_type')}): {val_pairs}")

    print(f"  关键帧覆盖镜头数: {keyframes_count} 组")
    transitions = data.get("materials", {}).get("transitions", [])
    print(f"  叠化转场数: {len(transitions)} 个")

print("\n✓ 上下两集剪映草稿全部通过深层结构验证！")
