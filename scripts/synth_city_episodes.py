#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Synthesize master voiceovers for Top 10 Historical Cities (Episode 1 & Episode 2)
Voice: 01_央视纪录片·沧桑历史男声 (zh-CN-YunjianNeural, rate=-8%, pitch=-6Hz)
"""

import sys
import asyncio
from pathlib import Path
import edge_tts
import pymediainfo

# Set encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
EP_BASE = ROOT / "03_视频成片与工程" / "十大历史名城_带孙辈长见识"

VOICE = "zh-CN-YunjianNeural"
RATE = "-8%"
PITCH = "-6Hz"

def extract_clean_text(md_path: Path) -> str:
    content = md_path.read_text(encoding="utf-8")
    # Take text under "## 纯净口播文案（直接用于配音/提词）"
    marker = "## 纯净口播文案（直接用于配音/提词）"
    if marker in content:
        text = content.split(marker, 1)[1].strip()
    else:
        text = content.strip()
    return text

def get_audio_info(file_path: Path):
    mi = pymediainfo.MediaInfo.parse(str(file_path))
    for t in mi.tracks:
        if t.track_type == "Audio":
            dur_sec = float(t.duration) / 1000.0
            return dur_sec
    return 0.0

async def synth_episode(ep_name: str):
    ep_dir = EP_BASE / ep_name
    script_path = ep_dir / "01_文案与分镜" / "口播文案.md"
    audio_dir = ep_dir / "03_配音音频"
    audio_dir.mkdir(parents=True, exist_ok=True)
    out_audio = audio_dir / "voice_master.mp3"

    print(f"\n==========================================")
    print(f"🎙️ 开始合成: {ep_name}")
    print(f"音色: {VOICE} | 语速: {RATE} | 音调: {PITCH}")
    text = extract_clean_text(script_path)
    print(f"文本字数: {len(text)} 字")

    comm = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH)
    await comm.save(str(out_audio))

    dur = get_audio_info(out_audio)
    mins = int(dur // 60)
    secs = int(dur % 60)
    print(f"✓ 合成完成: {out_audio.name} ({out_audio.stat().st_size} 字节, 时长: {mins}分{secs}秒 / {dur:.1f}s)")

async def main():
    await synth_episode("上集_第10至第6名")
    await synth_episode("下集_前五名揭晓")
    print("\n🎉 上下两集央视01配音音频合成全部完成！")

if __name__ == "__main__":
    asyncio.run(main())
