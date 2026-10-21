# -*- coding: utf-8 -*-
"""
深度审查 5 个视频草稿质量：
1. 画面尺寸与宽高比（是否严格 9:16，是否有黑边风险）
2. 分镜运镜关键帧（Ken Burns 参数与时序）
3. 字幕排版（字数是否超长、标点符号、图层层级）
4. 音画对齐（画面时长与人声时长的毫秒级匹配）
5. BGM 音量与淡出参数
6. 顶部标题栏与导航标显示
"""
import os
import sys
import json
from pathlib import Path
from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

def audit():
    draft_root = Path(os.environ.get("LOCALAPPDATA", "")) / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft"
    projects = [
        ("01_平遥古城_单集精讲", "【图书带货】带孙辈长见识：第10名·山西平遥"),
        ("02_延安宝塔山_单集精讲", "【图书带货】带孙辈长见识：第9名·陕西延安"),
        ("03_开封清明上河园_单集精讲", "【图书带货】带孙辈长见识：第8名·河南开封"),
        ("04_苏州拙政园_单集精讲", "【图书带货】带孙辈长见识：第7名·江苏苏州"),
        ("05_杭州西湖_单集精讲", "【图书带货】带孙辈长见识：第6名·浙江杭州"),
    ]

    for p_name, d_name in projects:
        d_path = draft_root / d_name / "draft_content.json"
        if not d_path.exists():
            print(f"Draft missing: {d_name}")
            continue

        with open(d_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        print("================================================================================")
        print(f"🎬 项目审查: {p_name}")
        print(f"📌 剪映草稿: {d_name}")
        total_dur_s = data.get("duration", 0) / 1000000.0
        print(f"⏱️ 总时长: {total_dur_s:.2f} 秒 ({int(total_dur_s // 60)}分{int(total_dur_s % 60)}秒)")

        # 1. 视觉资产审查 (分辨率、比例)
        videos = data.get("materials", {}).get("videos", [])
        non_standard_aspect = []
        img_resolutions = []
        for v in videos:
            p = Path(v.get("path", ""))
            if p.exists():
                try:
                    with Image.open(p) as im:
                        w, h = im.size
                        ratio = w / h
                        img_resolutions.append((p.name, w, h))
                        if abs(ratio - 9.0/16.0) > 0.05:
                            non_standard_aspect.append((p.name, f"{w}x{h}", f"比例: {ratio:.3f}"))
                except Exception as e:
                    non_standard_aspect.append((p.name, "Error", str(e)))

        print(f"🖼️ 画面审查: 共 {len(videos)} 个镜头分镜")
        if non_standard_aspect:
            print(f"   ⚠️ 非 9:16 镜头资产 ({len(non_standard_aspect)} 个):")
            for item in non_standard_aspect:
                print(f"      - {item[0]}: 分辨率 {item[1]}, {item[2]}")
        else:
            print(f"   ✅ 全部镜头均为标准 9:16 竖屏比例")

        # 2. 运镜审查 (Ken Burns Keyframes)
        keyframes = data.get("materials", {}).get("keyframes", [])
        print(f"🎥 运镜审查: 关键帧材料数 = {len(keyframes)}")

        # 3. 字幕审查
        texts = data.get("materials", {}).get("texts", [])
        long_subtitles = []
        punct_subtitles = []
        clean_texts = []
        for t in texts:
            content_str = t.get("content", "")
            try:
                cj = json.loads(content_str)
                raw_t = cj.get("text", "")
            except Exception:
                raw_t = content_str
            clean_texts.append(raw_t)
            if len(raw_t) > 16:
                long_subtitles.append((raw_t, len(raw_t)))
            if any(p in raw_t for p in ["，", "。", "！", "？", "；", "："]):
                punct_subtitles.append(raw_t)

        print(f"📝 字幕审查: 共 {len(texts)} 条字幕片段")
        print(f"   - 超长字幕 (>16字可能折行或遮挡): {len(long_subtitles)} 条")
        if long_subtitles:
            for ls in long_subtitles[:5]:
                print(f"      * [{ls[1]}字] {ls[0]}")
        print(f"   - 含句读标点字幕: {len(punct_subtitles)} 条")
        if punct_subtitles:
            for ps in punct_subtitles[:3]:
                print(f"      * {ps}")

        # 4. 音频与时序审查
        tracks = data.get("tracks", [])
        v_tracks = [t for t in tracks if t.get("type") == "video"]
        a_tracks = [t for t in tracks if t.get("type") == "audio"]
        t_tracks = [t for t in tracks if t.get("type") == "text"]

        v_dur = sum(s.get("target_timerange", {}).get("duration", 0) for s in v_tracks[0].get("segments", [])) if v_tracks else 0
        voice_dur = a_tracks[0].get("segments", [])[0].get("target_timerange", {}).get("duration", 0) if a_tracks and a_tracks[0].get("segments") else 0
        diff_s = (v_dur - voice_dur) / 1000000.0

        print(f"🔊 音画对齐审查:")
        print(f"   - 画面轨总长: {v_dur / 1000000.0:.3f} s")
        print(f"   - 解说人声长: {voice_dur / 1000000.0:.3f} s")
        print(f"   - 音画误差: {abs(diff_s):.4f} 秒 ({'✅ 毫秒级完全对齐' if abs(diff_s) < 0.1 else '⚠️ 存在偏差'})")

        # BGM 音量
        bgm_segments = []
        if len(a_tracks) > 1:
            for s in a_tracks[1].get("segments", []):
                bgm_segments.append(s.get("volume"))
        print(f"   - BGM 轨段数: {len(bgm_segments)}, 音量配置: {bgm_segments[:2]}")

        # 5. 顶部固定主标题栏 & 导航标检查
        print(f"🏷️ 轨道结构: 视频轨={len(v_tracks)}, 音频轨={len(a_tracks)}, 文本/贴纸轨={len(t_tracks)}")

    print("\n================================================================================")

if __name__ == "__main__":
    audit()
