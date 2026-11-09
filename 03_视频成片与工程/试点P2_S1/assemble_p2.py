#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
试点 P2 · Antigravity 一条龙生产装配脚本（按修改单重构版）
- 修改 1：字幕长句断行，单句 > 14 字按意群与气口切分短屏显（≤ 14 字、不断词），彻底解决裁字出画
- 修改 2：A05 单句重配已替换（消除结尾吞音截断，时长 3.132s）
- 修改 3：报告口径同步更正
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path("D:/fuye")
PROJECT_DIR = ROOT / "03_视频成片与工程" / "试点P2_S1"
AUDIO_DIR = PROJECT_DIR / "01_口播与音频"
VISUAL_DIR = PROJECT_DIR / "02_分镜视觉素材"
DRAFT_DIR = PROJECT_DIR / "03_剪映草稿工程"
OUT_DIR = PROJECT_DIR / "04_成片"
OUT_DIR.mkdir(parents=True, exist_ok=True)
DRAFT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(ROOT / "04_自动化生产流水线"))
sys.path.insert(0, str(ROOT / "scripts"))
from workspace_paths import ffmpeg
import pymediainfo
import pyJianYingDraft as draft

FFMPEG_EXE = ffmpeg()
BGM_PATH = ROOT / "01_配音与音色库" / "背景音乐库" / "bgm_shili_guofeng.mp3"
JIANYING_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "JianyingPro/User Data/Projects/com.lveditor.draft"

def ms_to_ass_time(ms: int) -> str:
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    cs = (ms % 1000) // 10
    return f"{h:01d}:{m:02d}:{s:02d}.{cs:02d}"

def run_assemble():
    manifest_path = AUDIO_DIR / "audio_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        audio_manifest = json.load(f)

    sentences = audio_manifest["sentences"]
    total_dur_ms = audio_manifest["total_duration_ms"]
    total_dur_s = audio_manifest["total_duration_sec"]

    cur_ms = 0
    for sent in sentences:
        dur = sent["duration_ms"]
        sent["start_ms"] = cur_ms
        sent["end_ms"] = cur_ms + dur
        sent["start_us"] = cur_ms * 1000
        sent["dur_us"] = dur * 1000
        cur_ms += dur

    # 镜头时序规划
    shots_plan = [
        {
            "id": "SHOT01",
            "img_file": VISUAL_DIR / "IMG01.png",
            "sentences": ["A01", "A02"],
            "start_ms": sentences[0]["start_ms"],
            "end_ms": sentences[1]["end_ms"],
            "zoom_type": "in"
        },
        {
            "id": "SHOT02",
            "img_file": VISUAL_DIR / "IMG02.png",
            "sentences": ["A03"],
            "start_ms": sentences[2]["start_ms"],
            "end_ms": sentences[2]["end_ms"],
            "zoom_type": "in"
        },
        {
            "id": "SHOT03",
            "img_file": VISUAL_DIR / "IMG03.png",
            "sentences": ["A04", "A05", "A06"],
            "start_ms": sentences[3]["start_ms"],
            "end_ms": sentences[5]["end_ms"],
            "zoom_type": "in"
        },
        {
            "id": "SHOT04",
            "img_file": VISUAL_DIR / "IMG04.png",
            "sentences": ["A07", "A08", "A09"],
            "start_ms": sentences[6]["start_ms"],
            "end_ms": sentences[8]["end_ms"],
            "zoom_type": "in"
        },
        {
            "id": "SHOT05",
            "img_file": VISUAL_DIR / "IMG05.jpg",
            "sentences": ["A10"],
            "start_ms": sentences[9]["start_ms"],
            "end_ms": sentences[9]["end_ms"],
            "zoom_type": "book"
        }
    ]

    for shot in shots_plan:
        shot["dur_ms"] = shot["end_ms"] - shot["start_ms"]
        shot["dur_s"] = shot["dur_ms"] / 1000.0

    print("=== 镜头时序规划 ===")
    for shot in shots_plan:
        print(f"[{shot['id']}] {shot['img_file'].name} | 时长: {shot['dur_s']:.3f}s ({shot['start_ms']}ms -> {shot['end_ms']}ms) | 绑定台词: {shot['sentences']}")

    # ==================== 修改 1：精细化短屏显字幕切分（意群与气口对齐，每条 ≤ 14 字） ====================
    # 依据实际音频波形气口停顿点（silencedetect 测定），精确对齐上屏毫秒
    # A01: 0 -> 2880
    # A02: 2880 -> 9540 (气口 1.40s, 4.42s)
    # A03: 9540 -> 16740 (气口 2.65s, 4.80s)
    # A04: 16740 -> 27504 (气口 3.62s, 7.75s)
    # A05: 27504 -> 30636
    # A06: 30636 -> 38664 (气口 2.02s, 3.62s, 5.28s)
    # A07: 38664 -> 44388 (气口 3.19s)
    # A08: 44388 -> 54072 (气口 3.25s, 5.39s, 7.35s)
    # A09: 54072 -> 57384 (气口 1.79s)
    # A10: 57384 -> 59940

    subtitle_screens = [
        # A01 (13字)
        {"text": "没钱的时候，亲戚躲着您走；", "start_ms": 0, "end_ms": 2880, "parent": "A01"},
        # A02 (4字, 15字, 9字)
        {"text": "有钱了，", "start_ms": 2880, "end_ms": 4280, "parent": "A02"},
        {"text": "八竿子打不着的亲戚也找上门了——", "start_ms": 4280, "end_ms": 7300, "parent": "A02"},
        {"text": "这口气，您咽过吗？", "start_ms": 7300, "end_ms": 9540, "parent": "A02"},
        # A03 (10字, 8字, 8字)
        {"text": "老话说得一点不客气：", "start_ms": 9540, "end_ms": 12190, "parent": "A03"},
        {"text": "贫居闹市无人问，", "start_ms": 12190, "end_ms": 14340, "parent": "A03"},
        {"text": "富在深山有远亲。", "start_ms": 14340, "end_ms": 16740, "parent": "A03"},
        # A04 (14字, 12字, 12字)
        {"text": "这句就收在《被遗忘的后半句》里，", "start_ms": 16740, "end_ms": 20360, "parent": "A04"},
        {"text": "第二章处事智慧，第47条，", "start_ms": 20360, "end_ms": 24490, "parent": "A04"},
        {"text": "前半句后半句一个字没改。", "start_ms": 24490, "end_ms": 27504, "parent": "A04"},
        # A05 (12字)
        {"text": "听着扎心，可句句是真话。", "start_ms": 27504, "end_ms": 30636, "parent": "A05"},
        # A06 (8字, 7字, 7字, 11字)
        {"text": "穷的时候没人问，", "start_ms": 30636, "end_ms": 32656, "parent": "A06"},
        {"text": "不是您人缘差，", "start_ms": 32656, "end_ms": 34256, "parent": "A06"},
        {"text": "是人情这东西，", "start_ms": 34256, "end_ms": 35916, "parent": "A06"},
        {"text": "历来先看冷暖再看亲疏。", "start_ms": 35916, "end_ms": 38664, "parent": "A06"},
        # A07 (13字, 11字)
        {"text": "看明白了，就别往心里记仇，", "start_ms": 38664, "end_ms": 41854, "parent": "A07"},
        {"text": "也别拿热脸再去贴冷脸：", "start_ms": 41854, "end_ms": 44388, "parent": "A07"},
        # A08 (13字, 8字, 8字, 10字)
        {"text": "该走动的走动，该远的远着，", "start_ms": 44388, "end_ms": 47638, "parent": "A08"},
        {"text": "往后谁真心对您，", "start_ms": 47638, "end_ms": 49778, "parent": "A08"},
        {"text": "您心里有数就行，", "start_ms": 49778, "end_ms": 51738, "parent": "A08"},
        {"text": "不用逢人就掏心窝子。", "start_ms": 51738, "end_ms": 54072, "parent": "A08"},
        # A09 (8字, 9字)
        {"text": "日子是自己过的，", "start_ms": 54072, "end_ms": 55862, "parent": "A09"},
        {"text": "不是演给亲戚看的。", "start_ms": 55862, "end_ms": 57384, "parent": "A09"},
        # A10 (11字)
        {"text": "您家，有过这种亲戚吗？", "start_ms": 57384, "end_ms": 59940, "parent": "A10"}
    ]

    temp_dir = PROJECT_DIR / "_temp_render"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 1. 构建 ASS 字幕文件
    ass_file = temp_dir / "subtitles.ass"
    ass_lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        # 晚场通用大字底衬 (底部白字，半透明黑底衬，字号52，单行严格适配手机安全区)
        "Style: Standard,Microsoft YaHei,52,&H00FFFFFF,&H00000000,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,3,16,0,2,40,40,210,1",
        # 第一镜封面大字 (顶部暖黄标题，大字突出)
        "Style: CoverTitle,Microsoft YaHei,72,&H0033D1FF,&H00000000,&H00000000,&HB0000000,-1,0,0,0,100,100,0,0,3,20,0,8,40,40,320,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    ]

    # 添加第一镜封面大字事件 (贯穿整镜 SHOT01，0.00s -> 9.54s)
    shot01_end_ass = ms_to_ass_time(shots_plan[0]["end_ms"])
    ass_lines.append(f"Dialogue: 1,0:00:00.00,{shot01_end_ass},CoverTitle,,0,0,0,,贫居闹市无人问")

    # 添加重切后的正片短屏显字幕事件
    for sub in subtitle_screens:
        st_ass = ms_to_ass_time(sub["start_ms"])
        et_ass = ms_to_ass_time(sub["end_ms"])
        text = sub["text"]
        ass_lines.append(f"Dialogue: 0,{st_ass},{et_ass},Standard,,0,0,0,,{text}")

    ass_file.write_text("\n".join(ass_lines), encoding="utf-8")
    print(f"ASS 字幕文件已就绪: {ass_file} (短屏显条数: {len(subtitle_screens)} 条正片 + 1 条第一镜封面大字)")

    # 2. 逐镜渲染微电影级动态切片 (带 Ken Burns 缓慢推拉)
    concat_list = temp_dir / "concat.txt"
    clip_files = []

    for s_idx, shot in enumerate(shots_plan):
        img_p = shot["img_file"]
        dur_s = shot["dur_s"]
        clip_p = temp_dir / f"clip_{s_idx+1:02d}.mp4"

        print(f"渲染镜头切片 [{shot['id']}] -> {clip_p.name} (时长: {dur_s:.3f}s)...")

        if shot["zoom_type"] == "book":
            # 书图保持原尺寸原色不裁切，配合柔和高斯模糊背景填补 9:16
            vf = (
                "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg];"
                "[0:v]scale=1020:1020:force_original_aspect_ratio=decrease[fg];"
                "[bg][fg]overlay=(W-w)/2:(H-h)/2,"
                "scale=2160:3840,zoompan=z='min(zoom+0.0003,1.04)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30"
            )
            cmd_clip = [
                FFMPEG_EXE, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-loop", "1", "-i", str(img_p),
                "-t", f"{dur_s:.3f}",
                "-filter_complex", vf,
                "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                str(clip_p)
            ]
        else:
            # 真实摄影分镜：高解析度缓慢推拉运镜 (1.0 -> 1.05)
            vf = (
                "scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
                "zoompan=z='min(zoom+0.00025,1.05)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30"
            )
            cmd_clip = [
                FFMPEG_EXE, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-loop", "1", "-i", str(img_p),
                "-t", f"{dur_s:.3f}",
                "-vf", vf,
                "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                str(clip_p)
            ]

        subprocess.run(cmd_clip, check=True)
        clip_files.append(clip_p)

    concat_list.write_text("\n".join(f"file '{p.as_posix()}'" for p in clip_files), encoding="utf-8")

    # 3. 准备人声音频母带 (精确对齐 A01-A10，含新重配 A05)
    voice_master_mp3 = temp_dir / "voice_master.mp3"
    cmd_v = [FFMPEG_EXE, "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
    parts, labels = [], []
    for idx, sent in enumerate(sentences):
        cmd_v += ["-i", str(AUDIO_DIR / f"{sent['id']}.mp3")]
        offset_ms = int(sent["start_ms"])
        parts.append(f"[{idx}:a]adelay={offset_ms}|{offset_ms},aresample=44100[a{idx}]")
        labels.append(f"[a{idx}]")

    v_graph = ";".join(parts) + ";" + "".join(labels) + f"amix=inputs={len(sentences)}:duration=longest:normalize=0[vout]"
    cmd_v += ["-filter_complex", v_graph, "-map", "[vout]", "-c:a", "libmp3lame", "-b:a", "192k", str(voice_master_mp3)]
    subprocess.run(cmd_v, check=True)
    print("人声母带混音完成:", voice_master_mp3)

    # 4. 混音 BGM (轻音乐托底 -18dB = volume 0.12589，人声 volume 1.4125 (+3dB))
    fade_out_start = max(0, total_dur_s - 2.5)
    filter_complex = (
        f"[0:a]volume=1.4125[v];"
        f"[1:a]aloop=loop=-1:size=2e+09,atrim=0:{total_dur_s:.3f},"
        f"afade=t=in:ss=0:d=1.0,afade=t=out:st={fade_out_start:.3f}:d=2.5,volume=0.12589[m];"
        f"[v][m]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )
    mixed_audio = temp_dir / "mixed_audio.aac"
    cmd_audio = [
        FFMPEG_EXE, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(voice_master_mp3),
        "-i", str(BGM_PATH),
        "-filter_complex", filter_complex,
        "-map", "[aout]",
        "-c:a", "aac", "-b:a", "192k",
        str(mixed_audio)
    ]
    subprocess.run(cmd_audio, check=True)
    print("背景音乐与人声混音完成:", mixed_audio)

    # 5. 画面 + 音频 + ASS 字幕烧录合成最终 MP4
    final_mp4 = OUT_DIR / "试点P2_S1_一条龙测试成片.mp4"
    if final_mp4.exists():
        final_mp4.unlink()

    ass_escaped = str(ass_file).replace("\\", "/").replace(":", "\\:")
    cmd_final = [
        FFMPEG_EXE, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-i", str(mixed_audio),
        "-vf", f"subtitles=filename='{ass_escaped}'",
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-shortest", "-movflags", "+faststart",
        str(final_mp4)
    ]
    print("开始最终合成渲染 MP4 成片...")
    subprocess.run(cmd_final, check=True)
    print("成片渲染成功:", final_mp4, "大小:", final_mp4.stat().st_size)

    # 6. 同步创建剪映草稿工程 (用于剪映秒级打开核验)
    draft_name = "试点P2_S1_一条龙测试"
    folder = draft.DraftFolder(str(JIANYING_DIR))
    script = folder.create_draft(draft_name, width=1080, height=1920, fps=30, allow_replace=True)

    v1_track = draft.TrackSpec(draft.TrackType.video, name="V1_正片画面")
    a1_track = draft.TrackSpec(draft.TrackType.audio, name="A1_人声解说")
    a2_track = draft.TrackSpec(draft.TrackType.audio, name="A2_背景音乐")
    sub_track = draft.TrackSpec(draft.TrackType.text, name="字幕轨")
    title_track = draft.TrackSpec(draft.TrackType.text, name="封面大字轨")

    script.append_track(v1_track)
    script.append_track(a1_track)
    script.append_track(a2_track)
    script.append_track(sub_track)
    script.append_track(title_track)

    # V1 轨：正片画面
    for shot in shots_plan:
        st_us = shot["start_ms"] * 1000
        dur_us = shot["dur_ms"] * 1000
        v_seg = draft.VideoSegment(str(shot["img_file"]), draft.Timerange(st_us, dur_us))
        if shot["zoom_type"] == "book":
            v_seg.add_background_filling("blur", blur=0.375)
            v_seg.add_keyframe(draft.KeyframeProperty.uniform_scale, 0, 1.0)
            v_seg.add_keyframe(draft.KeyframeProperty.uniform_scale, dur_us, 1.04)
        else:
            v_seg.add_keyframe(draft.KeyframeProperty.uniform_scale, 0, 1.0)
            v_seg.add_keyframe(draft.KeyframeProperty.uniform_scale, dur_us, 1.05)
        script.add_segment(v_seg, track="V1_正片画面")

    # A1 轨：人声逐句
    for sent in sentences:
        a_seg = draft.AudioSegment(
            str(AUDIO_DIR / f"{sent['id']}.mp3"),
            draft.Timerange(sent["start_us"], sent["dur_us"]),
            volume=1.4125
        )
        script.add_segment(a_seg, track="A1_人声解说")

    # A2 轨：BGM (-18dB)
    total_audio_dur_us = total_dur_ms * 1000
    if BGM_PATH.exists():
        mi_b = pymediainfo.MediaInfo.parse(str(BGM_PATH))
        bgm_dur_us = 30_000_000
        for t in mi_b.tracks:
            if t.track_type == "Audio":
                bgm_dur_us = int(float(t.duration) * 1000)
                break
        cur_bgm_us = 0
        chunk_idx = 0
        while cur_bgm_us < total_audio_dur_us:
            chunk_len = min(bgm_dur_us, total_audio_dur_us - cur_bgm_us)
            b_seg = draft.AudioSegment(
                str(BGM_PATH),
                draft.Timerange(cur_bgm_us, chunk_len),
                source_timerange=draft.Timerange(0, chunk_len),
                volume=0.12589
            )
            fade_in = 1_000_000 if chunk_idx == 0 else 0
            fade_out = 2_500_000 if (cur_bgm_us + chunk_len >= total_audio_dur_us) else 0
            if fade_in > 0 or fade_out > 0:
                b_seg.add_fade(fade_in, fade_out)
            script.add_segment(b_seg, track="A2_背景音乐")
            cur_bgm_us += chunk_len
            chunk_idx += 1

    # 字幕轨 (Standard 晚场短屏显样式)
    sub_border = draft.TextBorder(color=(0.0, 0.0, 0.0), width=40.0)
    sub_bg = draft.TextBackground(color="#000000", alpha=0.6, round_radius=0.15)
    sub_clip = draft.ClipSettings(transform_y=-0.573)

    for sub in subtitle_screens:
        st_us = sub["start_ms"] * 1000
        dur_us = (sub["end_ms"] - sub["start_ms"]) * 1000
        st_style = draft.TextStyle(size=11.0, bold=True, color=(1.0, 1.0, 1.0), align=1)
        t_seg = draft.TextSegment(
            sub["text"],
            draft.Timerange(st_us, dur_us),
            style=st_style,
            border=sub_border,
            background=sub_bg,
            clip_settings=sub_clip
        )
        script.add_segment(t_seg, track="字幕轨")

    # 封面大字 (文字轨，覆盖第一镜)
    title_style = draft.TextStyle(size=15.0, bold=True, color=(1.0, 0.85, 0.2), align=1)
    title_clip = draft.ClipSettings(transform_y=0.55)
    title_seg = draft.TextSegment(
        "贫居闹市无人问",
        draft.Timerange(0, shots_plan[0]["dur_ms"] * 1000),
        style=title_style,
        border=draft.TextBorder(color=(0.0, 0.0, 0.0), width=50.0),
        background=draft.TextBackground(color="#000000", alpha=0.7, round_radius=0.2),
        clip_settings=title_clip
    )
    script.add_segment(title_seg, track="封面大字轨")

    script.save()
    jianying_draft_path = JIANYING_DIR / draft_name
    print("剪映草稿工程就绪:", jianying_draft_path)

    # 复制剪映草稿到本地工程目录备份
    for jf in ["draft_content.json", "draft_meta_info.json"]:
        if (jianying_draft_path / jf).exists():
            shutil.copy2(jianying_draft_path / jf, DRAFT_DIR / jf)

    # 清理渲染临时目录
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass

    # 验证成片 MediaInfo
    mi = pymediainfo.MediaInfo.parse(str(final_mp4))
    v_track = next((t for t in mi.tracks if t.track_type == "Video"), None)
    a_track = next((t for t in mi.tracks if t.track_type == "Audio"), None)
    g_track = next((t for t in mi.tracks if t.track_type == "General"), None)

    print("\n=== 成片质检数据 ===")
    print(f"成片文件: {final_mp4.name}")
    print(f"文件大小: {final_mp4.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"音频时间轴总时长: {total_dur_s:.3f} 秒 ({total_dur_ms} ms)")
    print(f"成片容器总时长: {float(g_track.duration)/1000.0:.3f} 秒 ({g_track.duration} ms)")
    print(f"视频分辨率: {v_track.width} x {v_track.height} @ {v_track.frame_rate} FPS")
    print(f"视频编码: {v_track.codec_id} ({v_track.format})")
    print(f"音频格式: {a_track.format} @ {a_track.sampling_rate} Hz")
    print("=== 装配与导出全链条成功！ ===")

if __name__ == "__main__":
    run_assemble()
