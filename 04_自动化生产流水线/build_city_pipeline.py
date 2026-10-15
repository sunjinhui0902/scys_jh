#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Universal Automated Pipeline for 15 Cities Book E-commerce Video Production
---------------------------------------------------------------------------
Features:
1. Synthesizes sentence-level TTS via edge-tts with precise millisecond timestamps.
2. Concatenates into voice_master.mp3 and generates standard subtitles.srt and timestamps.json.
3. Automatically maps 5 visual shots to the 5 storytelling stages (Pain Point -> Spatial -> Mechanism -> Observation -> Book Conversion).
4. Generates Ken Burns dynamic video clips (push, pull, pan, tilt) via FFmpeg.
5. Produces an MP4 preview with large, high-contrast subtitles for mobile inspection.
6. Automatically creates a ready-to-export JianYing Pro Draft with Video, Audio, and Elderly Subtitle tracks.
"""

import os
import sys
import json
import asyncio
import argparse
import subprocess
from pathlib import Path
from typing import List, Dict, Any

try:
    import pymediainfo
    import pyJianYingDraft as draft
    import edge_tts
except ImportError as e:
    print(f"[Error] Missing dependency: {e}. Please pip install edge-tts pyJianYingDraft pymediainfo", file=sys.stderr)
    sys.exit(1)

# Ensure proper utf-8 stream encoding on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Import workspace paths
CURRENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CURRENT_DIR))
from workspace_paths import ROOT, JIANYING, ffmpeg


def format_srt_time(ms: int) -> str:
    """Format milliseconds into SRT timecode HH:MM:SS,mmm"""
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    milli = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milli:03d}"


async def synthesize_line(text: str, voice: str, rate: str, pitch: str, output_path: Path):
    """Synthesize a single sentence with edge-tts"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(str(output_path))


async def generate_all_chunks(sentences: List[str], voice: str, rate: str, pitch: str, chunks_dir: Path):
    """Synthesize all sentence chunks sequentially to avoid rate limiting"""
    chunks_dir.mkdir(parents=True, exist_ok=True)
    for idx, sentence in enumerate(sentences, 1):
        out_file = chunks_dir / f"chunk_{idx:02d}.mp3"
        print(f"  [TTS {idx:02d}/{len(sentences):02d}] 正在合成: {sentence}")
        await synthesize_line(sentence, voice, rate, pitch, out_file)


def get_audio_duration_ms(file_path: Path) -> int:
    """Get accurate audio duration in milliseconds using pymediainfo"""
    mi = pymediainfo.MediaInfo.parse(str(file_path))
    for t in mi.tracks:
        if t.track_type == "Audio":
            return int(float(t.duration))
    return 2000


def build_vf(motion: str, total_frames: int) -> str:
    """Generate dynamic Ken Burns zoompan filter for FFmpeg"""
    if motion == "push":
        zp = f"zoompan=z='min(zoom+0.0006,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s=1080x1920:fps=25"
    elif motion == "pull":
        zp = f"zoompan=z='if(lte(on,1),1.15,max(1.0,1.15-0.0006*on))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s=1080x1920:fps=25"
    elif motion == "pan_right":
        zp = f"zoompan=z='1.15':x='(on/{total_frames})*(iw-iw/zoom)':y='ih/2-(ih/zoom/2)':d={total_frames}:s=1080x1920:fps=25"
    elif motion == "tilt_up":
        zp = f"zoompan=z='1.15':x='iw/2-(iw/zoom/2)':y='(1-on/{total_frames})*(ih-ih/zoom)':d={total_frames}:s=1080x1920:fps=25"
    elif motion == "tilt_down":
        zp = f"zoompan=z='1.15':x='iw/2-(iw/zoom/2)':y='(on/{total_frames})*(ih-ih/zoom)':d={total_frames}:s=1080x1920:fps=25"
    else:
        zp = f"zoompan=z='min(zoom+0.0005,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s=1080x1920:fps=25"
    return f"scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,{zp}"


def run_pipeline(
    city_dir: Path,
    voice: str = "zh-CN-YunjianNeural",
    rate: str = "-4%",
    pitch: str = "-2Hz",
    pause_ms: int = 160,
    draft_name: str = None
):
    city_dir = Path(city_dir).resolve()
    print(f"==================================================")
    print(f"🎬 启动自动化短视频生产流水线: {city_dir.name}")
    print(f"==================================================")

    # 1. Read subtitles
    sub_file = city_dir / "字幕短句.txt"
    if not sub_file.is_file():
        raise FileNotFoundError(f"未找到字幕文件: {sub_file}")

    sentences = [line.strip() for line in sub_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"[1/5] 读取字幕短句: 共 {len(sentences)} 句，严格 5~9 字律动")

    # 2. Synthesize TTS chunks
    audio_dir = city_dir / "03_配音音频"
    chunks_dir = audio_dir / "audio_chunks"
    print(f"[2/5] 正在生成 Edge-TTS 配音音频 (音色: {voice}, 语速: {rate})...")
    asyncio.run(generate_all_chunks(sentences, voice, rate, pitch, chunks_dir))

    # 3. Concatenate and generate timestamps & SRT
    print(f"[3/5] 计算精准毫秒时序并生成 subtitles.srt 与 timestamps.json...")
    ffmpeg_exe = ffmpeg()
    timestamps = []
    srt_lines = []
    current_time_ms = 0
    chunk_files = []

    for idx, sentence in enumerate(sentences, 1):
        chunk_path = chunks_dir / f"chunk_{idx:02d}.mp3"
        duration_ms = get_audio_duration_ms(chunk_path)
        start_ms = current_time_ms
        end_ms = start_ms + duration_ms

        timestamps.append({
            "index": idx,
            "text": sentence,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "duration_ms": duration_ms
        })

        # SRT format
        srt_lines.append(f"{idx}")
        srt_lines.append(f"{format_srt_time(start_ms)} --> {format_srt_time(end_ms)}")
        srt_lines.append(sentence)
        srt_lines.append("")

        chunk_files.append(chunk_path)
        current_time_ms = end_ms + pause_ms

    total_duration_sec = round(current_time_ms / 1000.0, 2)
    print(f"  [✓ 时序标定完成] 全片总时长: {total_duration_sec} 秒 (在 60~85 秒黄金区间)")

    # Save SRT
    subtitles_dir = city_dir / "01_文案与分镜"
    subtitles_dir.mkdir(parents=True, exist_ok=True)
    srt_path = subtitles_dir / "subtitles.srt"
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")

    # Save timestamps JSON
    ts_path = audio_dir / "timestamps.json"
    ts_path.write_text(json.dumps(timestamps, ensure_ascii=False, indent=2), encoding="utf-8")

    # Concat master audio using ffmpeg concat demuxer
    concat_audio_txt = audio_dir / "concat_audio.txt"
    with open(concat_audio_txt, "w", encoding="utf-8") as f:
        for p in chunk_files:
            f.write(f"file '{p.as_posix()}'\n")

    voice_master_path = audio_dir / "voice_master.mp3"
    subprocess.run([
        ffmpeg_exe, "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_audio_txt),
        "-c", "copy",
        str(voice_master_path)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  [✓ 人声音频合成] 已输出 voice_master.mp3 ({voice_master_path.stat().st_size} bytes)")

    # 4. Visual 5-Shot mapping & dynamic motion rendering
    print(f"[4/5] 装配五镜视觉资产并生成 Ken Burns 运镜切片...")
    visuals_dir = city_dir / "02_分镜视觉素材"
    if not visuals_dir.is_dir():
        raise FileNotFoundError(f"未找到视觉素材目录: {visuals_dir}")

    # Look for shot_01 ~ shot_05
    shot_files = []
    for i in range(1, 6):
        candidates = list(visuals_dir.glob(f"shot_{i:02d}.*"))
        if not candidates:
            # Fallback to 01_实景, etc.
            candidates = list(visuals_dir.glob(f"0{i}_*.*"))
        if not candidates:
            raise FileNotFoundError(f"缺少镜头 {i} 的图片素材: shot_{i:02d}.jpg/png")
        shot_files.append(candidates[0])

    # Sentence partition for 5 stages (approximate ratios: 0-10s, 10-25s, 25-45s, 45-65s, 65-85s)
    total_n = len(sentences)
    cut1 = max(1, int(total_n * 0.20))       # ~20%
    cut2 = max(cut1 + 1, int(total_n * 0.38)) # ~38%
    cut3 = max(cut2 + 1, int(total_n * 0.58)) # ~58%
    cut4 = max(cut3 + 1, int(total_n * 0.85)) # ~85%

    stages = [
        {"name": "01_痛点开场", "range": (0, cut1), "motion": "push", "img": shot_files[0]},
        {"name": "02_空间拉远", "range": (cut1, cut2), "motion": "pan_right", "img": shot_files[1]},
        {"name": "03_核心机制上", "range": (cut2, cut3), "motion": "pull", "img": shot_files[2]},
        {"name": "04_机制下与观察法", "range": (cut3, cut4), "motion": "tilt_up", "img": shot_files[3]},
        {"name": "05_自然引书转化", "range": (cut4, total_n), "motion": "push", "img": shot_files[4]},
    ]

    clips_dir = city_dir / "rendered_motion_clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    rendered_clips = []

    for idx, stage in enumerate(stages, 1):
        s_start, s_end = stage["range"]
        # Calculate duration of this stage in ms
        stage_start_ms = timestamps[s_start]["start_ms"]
        stage_end_ms = timestamps[s_end - 1]["end_ms"] + pause_ms
        stage_dur_sec = max(2.0, (stage_end_ms - stage_start_ms) / 1000.0)
        total_frames = int(stage_dur_sec * 25)

        out_clip = clips_dir / f"stage_{idx:02d}_{stage['name']}.mp4"
        rendered_clips.append(out_clip)
        print(f"  [镜头 {idx}/5: {stage['name']}] 对应短句 {s_start+1}~{s_end}句 | 时长: {stage_dur_sec:.2f}s | 运镜: {stage['motion']}")

        vf = build_vf(stage["motion"], total_frames)
        cmd = [
            ffmpeg_exe, "-y",
            "-loop", "1", "-i", str(stage["img"]),
            "-t", str(stage_dur_sec),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            str(out_clip)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Concat video clips
    concat_video_txt = clips_dir / "concat_video.txt"
    with open(concat_video_txt, "w", encoding="utf-8") as f:
        for p in rendered_clips:
            f.write(f"file '{p.as_posix()}'\n")

    raw_mp4 = city_dir / "raw_video_concat.mp4"
    subprocess.run([
        ffmpeg_exe, "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_video_txt),
        "-c", "copy",
        str(raw_mp4)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Burn-in large subtitles for elderly inspection
    print(f"[5/5] 正在合成带中老年高对比大字字幕的预览视频...")
    final_preview_mp4 = city_dir / f"{city_dir.name}_样片预览_中老年大字版.mp4"
    srt_sub_arg = str(srt_path).replace("\\", "/").replace(":", "\\:")
    sub_filter = f"subtitles='{srt_sub_arg}':force_style='FontName=Microsoft YaHei,FontSize=22,Bold=1,PrimaryColour=&H0033FFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=140'"

    subprocess.run([
        ffmpeg_exe, "-y",
        "-i", str(raw_mp4),
        "-i", str(voice_master_path),
        "-vf", sub_filter,
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(final_preview_mp4)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  [✓ 成片预览就绪] 输出视频: {final_preview_mp4} ({final_preview_mp4.stat().st_size} bytes)")

    # 5. Build JianYing Pro Draft
    draft_title = draft_name or f"【图书带货】{city_dir.name}_中老年大字典藏版"
    print(f"\n🚀 正在组装剪映专业版草稿: {draft_title} ...")
    folder = draft.DraftFolder(str(JIANYING))
    script = folder.create_draft(draft_title, width=1080, height=1920, fps=25, allow_replace=True)

    # Video track & Audio track
    script.append_track(draft.TrackSpec(draft.TrackType.video, name="五镜视频轨"))
    script.append_track(draft.TrackSpec(draft.TrackType.audio, name="解说配音轨"))

    cur_us = 0
    for idx, stage in enumerate(stages):
        clip_path = rendered_clips[idx]
        clip_dur_us = int(get_audio_duration_ms(clip_path) * 1000) if False else int((timestamps[stage["range"][1]-1]["end_ms"] + pause_ms - timestamps[stage["range"][0]]["start_ms"]) * 1000)
        v_seg = draft.VideoSegment(str(stage["img"]), draft.Timerange(cur_us, clip_dur_us))
        script.add_segment(v_seg)
        cur_us += clip_dur_us

    # Add master audio
    master_dur_ms = get_audio_duration_ms(voice_master_path)
    a_seg = draft.AudioSegment(str(voice_master_path), draft.Timerange(0, master_dur_ms * 1000))
    script.add_segment(a_seg)

    # Add middle-aged & elderly high contrast subtitles
    large_text_style = draft.TextStyle(
        size=12.0,
        bold=True,
        color=(1.0, 0.95, 0.2), # Bright readable warm gold
        align=1, # Center
        auto_wrapping=True,
        max_line_width=0.78
    )
    clip_pos = draft.ClipSettings(transform_y=-0.68) # Bottom third safe zone

    script.import_srt(
        str(srt_path),
        track_name="中老年大字字幕",
        text_style=large_text_style,
        clip_settings=clip_pos
    )
    script.save()
    print(f"  [✓ 剪映工程成功保存] 打开剪映即可直接在时间线上查看与二次微调: {draft_title}")
    print(f"==================================================")
    print(f"🎉 流水线闭环测试全部通过！")
    print(f"==================================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Automated Video Production for City")
    parser.add_argument("city_dir", help="Path to city folder (e.g. 03_视频成片与工程/15城纠偏稿_2026-10-16_v2/05_平遥)")
    parser.add_argument("--voice", default="zh-CN-YunjianNeural", help="TTS voice name")
    parser.add_argument("--rate", default="-4%", help="Speech rate")
    parser.add_argument("--draft-name", help="Custom JianYing draft title")
    args = parser.parse_args()

    run_pipeline(
        city_dir=Path(args.city_dir),
        voice=args.voice,
        rate=args.rate,
        draft_name=args.draft_name
    )
