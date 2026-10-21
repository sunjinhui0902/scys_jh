#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wang Liqun Zero-Shot Voice Clone & Concatenation Pipeline
Using open-source E2-F5-TTS (ZeroGPU / Gradio Client)
100% Free, No API Key needed, Zero cost.
"""

import os
import sys
import re
import time
import shutil
import subprocess
from pathlib import Path
from gradio_client import Client, handle_file
import imageio_ffmpeg

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

REF_AUDIO = list((ROOT / "01_配音与音色库").glob("王立群*.mp3"))[0]
REF_TEXT = "人生在世，遇到挫折时要懂得反省，遇到成功时要懂得谦逊。这就像古人说的，福祸相依，得失相生。一个人"

SCRIPT_FILE = ROOT / "03_视频成片与工程" / "01_平遥古城_单集精讲" / "01_文案与分镜" / "口播文案.md"
OUT_MASTER = ROOT / "03_视频成片与工程" / "01_平遥古城_单集精讲" / "03_配音音频" / "voice_master.mp3"
TEMP_DIR = ROOT / "01_配音与音色库" / ".temp_wangliqun_chunks"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


def get_sentences(text: str):
    """按标点分割为适合 F5-TTS 的语义句段（30~60字）"""
    raw_sents = re.split(r"([。！？\n]+)", text)
    chunks = []
    cur = ""
    for p in raw_sents:
        if not p:
            continue
        if p in "。！？\n":
            cur += p.strip()
            if len(cur) >= 30:
                chunks.append(cur)
                cur = ""
        else:
            cur += p
    if cur.strip():
        chunks.append(cur.strip())
    
    # 对超长句进一步按逗号分
    final_chunks = []
    for c in chunks:
        if len(c) <= 70:
            final_chunks.append(c)
        else:
            sub = re.split(r"([，；]+)", c)
            sub_cur = ""
            for sp in sub:
                sub_cur += sp
                if len(sub_cur) >= 35:
                    final_chunks.append(sub_cur)
                    sub_cur = ""
            if sub_cur.strip():
                final_chunks.append(sub_cur)
    return [c for c in final_chunks if c.strip()]


def synthesize_all():
    print(f"🎬 启动王立群 AI 原声全篇零成本克隆流水线...")
    print(f"📦 参考音频: {REF_AUDIO.name}")
    print(f"📦 参考台词: {REF_TEXT}")

    content = SCRIPT_FILE.read_text(encoding="utf-8")
    m = re.search(r"## 纯净口播文案\s*[\n\r]+([^\n\r#].*?)(?=\n## |\Z)", content, re.DOTALL)
    if not m:
        raise ValueError("未找到纯净口播文案")
    
    pure_text = m.group(1).strip()
    sentences = get_sentences(pure_text)
    print(f"📝 拆解为 {len(sentences)} 个语义句段，开始调用 E2-F5-TTS...")

    client = Client("mrfakename/E2-F5-TTS")
    generated_wavs = []

    for idx, sent in enumerate(sentences, 1):
        chunk_file = TEMP_DIR / f"chunk_{idx:03d}.wav"
        if chunk_file.exists() and chunk_file.stat().st_size > 1024:
            print(f"  [{idx}/{len(sentences)}] 已存在缓存，直接跳过", flush=True)
            generated_wavs.append(chunk_file)
            continue

        print(f"  [{idx}/{len(sentences)}] 正在合成 ({len(sent)}字): {sent[:25]}...", flush=True)
        retry = 0
        while retry < 3:
            try:
                res = client.predict(
                    ref_audio=handle_file(str(REF_AUDIO)),
                    ref_text=REF_TEXT,
                    gen_text=sent,
                    remove_silence=False,
                    api_name="/predict"
                )
                # 跨盘复制到 chunk_file
                shutil.copy(str(res), str(chunk_file))
                generated_wavs.append(chunk_file)
                print(f"    ✓ 句段 {idx} 合成完成 ({chunk_file.stat().st_size} bytes)", flush=True)
                break
            except Exception as e:
                retry += 1
                print(f"    ⚠️ 句段 {idx} 失败重试 ({retry}/3): {e}", flush=True)
                time.sleep(2)

    if len(generated_wavs) != len(sentences):
        print(f"❌ 部分句段合成失败，成功 {len(generated_wavs)}/{len(sentences)}")
        return False

    # 合并所有 wav
    concat_list = TEMP_DIR / "concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for w in generated_wavs:
            f.write(f"file '{w.as_posix()}'\n")

    print(f"🔗 正在用 FFmpeg 无损拼接全篇母带...")
    cmd = [
        FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-c:a", "libmp3lame",
        "-b:a", "320k",
        "-ar", "44100",
        str(OUT_MASTER)
    ]
    subprocess.run(cmd, check=True)
    print(f"🎉 【王立群全篇配音母带就绪】: {OUT_MASTER} ({OUT_MASTER.stat().st_size} bytes)")
    return True


if __name__ == "__main__":
    synthesize_all()
