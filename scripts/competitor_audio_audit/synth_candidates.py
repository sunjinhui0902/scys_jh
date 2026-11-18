# -*- coding: utf-8 -*-
"""合成候选音色池（用于反推竞品口播用的是哪款公共 TTS）。

两个来源：
  Edge 公共音色  —— 免密钥，可调 pitch/rate，天然带"同一说话人的不同变体"，
                     可用于给说话人嵌入做阈值自校准
  MiniMax 系统音色 —— 走自有开放平台 key（config/voice_api/config.yaml，被 gitignore）

用法：
    python scripts/competitor_audio_audit/synth_candidates.py --engine edge
    python scripts/competitor_audio_audit/synth_candidates.py --engine minimax
"""
import argparse
import asyncio
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

import edge_tts

from common import SCRATCH, VOICE_API_CFG, ensure_dirs

EDGE_OUT = SCRATCH / "voice_candidates"
MINIMAX_OUT = SCRATCH / "minimax_candidates"

# 与本批次比对时使用的同一段文本，保证跨引擎可比
TEXT = ("各位老朋友大家好，今天咱们接着上回的话题继续往下讲。"
        "这座城市已经有三千多年的历史，从城墙到街巷，每一块砖石都记着故事。"
        "有人说，看一个地方要看它的名气；其实更要看它的日常，"
        "看看人们怎么过日子，看看那些留下来的手艺和讲究，那才是真正的根。")

EDGE_VOICES = [
    ("zh-CN-YunjianNeural", "+0Hz", "+0%", "云健_新闻播音严肃"),
    ("zh-CN-YunyangNeural", "+0Hz", "+0%", "云扬_新闻播音专业"),
    ("zh-CN-YunxiNeural", "+0Hz", "+0%", "云希_活泼男声"),
    ("zh-CN-YunxiaNeural", "+0Hz", "+0%", "云夏_少年男声"),
    ("zh-CN-YunjianNeural", "-6Hz", "-8%", "云健_我们的黄金音_-6Hz_-8%"),
    ("zh-CN-YunyangNeural", "-6Hz", "-8%", "云扬_-6Hz_-8%"),
    ("zh-CN-YunjianNeural", "+10Hz", "+0%", "云健_+10Hz"),
    ("zh-CN-YunyangNeural", "+10Hz", "+0%", "云扬_+10Hz"),
    ("zh-CN-YunxiNeural", "-8Hz", "+0%", "云希_-8Hz"),
]

MINIMAX_VOICE_IDS = [
    "Chinese (Mandarin)_Male_Announcer",
    "male-qn-badao",
    "male-qn-qingse",
    "male-qn-jingying",
    "male-qn-daxuesheng",
    "audiobook_male_1",
    "audiobook_male_2",
    "Chinese (Mandarin)_Gentleman",
]


async def synth_edge(voice, pitch, rate, out):
    kw = {}
    if pitch != "+0Hz":
        kw["pitch"] = pitch
    if rate != "+0%":
        kw["rate"] = rate
    last = None
    for attempt in range(5):
        try:
            await edge_tts.Communicate(TEXT, voice, **kw).save(str(out))
            if out.exists() and out.stat().st_size > 10000:
                return True
            last = RuntimeError("空文件")
        except Exception as e:
            last = e
        await asyncio.sleep(3 + attempt * 3)
    print("   FAIL", voice, pitch, rate, str(last)[:120])
    return False


def synth_minimax(voice_id, out, cfg):
    base = str(cfg.get("base_url") or "https://api.minimaxi.com").rstrip("/")
    key = os.environ.get("MINIMAX_API_KEY") or str(cfg.get("api_key") or "").strip()
    if not key:
        raise SystemExit("没有可用密钥：环境变量 MINIMAX_API_KEY 或 config/voice_api/config.yaml")
    payload = {
        "model": cfg.get("model") or "speech-2.8-hd",
        "text": TEXT, "stream": False,
        "language_boost": cfg.get("language_boost", "auto"),
        "output_format": "hex",
        "voice_setting": {"voice_id": voice_id, "speed": 1.0, "vol": 1.0, "pitch": 0},
        "audio_setting": dict(cfg.get("audio_setting") or {}),
    }
    req = urllib.request.Request(
        f"{base}/v1/t2a_v2",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                out_json = json.loads(resp.read().decode("utf-8"))
            base_resp = out_json.get("base_resp") or {}
            if base_resp.get("status_code") not in (0, None):
                raise RuntimeError(f"T2A {base_resp.get('status_code')} {base_resp.get('status_msg')}")
            audio_hex = (out_json.get("data") or {}).get("audio") or ""
            if not audio_hex:
                raise RuntimeError("无音频数据")
            out.write_bytes(bytes.fromhex(audio_hex))
            return True
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code} {e.read().decode('utf-8', 'replace')[:120]}"
        except Exception as e:
            last = str(e)[:180]
        time.sleep(3 + attempt * 3)
    print("   FAIL", voice_id, last)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["edge", "minimax", "all"], default="all")
    args = ap.parse_args()

    if args.engine in ("edge", "all"):
        ensure_dirs(EDGE_OUT)
        for voice, pitch, rate, label in EDGE_VOICES:
            tag = f"{label}_{voice}"
            path = EDGE_OUT / (tag + ".mp3")
            if path.exists() and path.stat().st_size > 10000:
                print("[DONE]", tag)
                continue
            asyncio.run(synth_edge(voice, pitch, rate, path))
            print("[OK]", tag, path.stat().st_size if path.exists() else 0)

    if args.engine in ("minimax", "all"):
        if not VOICE_API_CFG.exists():
            print("[SKIP] 无 config/voice_api/config.yaml，跳过 MiniMax")
            return
        import yaml
        cfg = yaml.safe_load(VOICE_API_CFG.read_text(encoding="utf-8")) or {}
        ensure_dirs(MINIMAX_OUT)
        for vid in MINIMAX_VOICE_IDS:
            tag = vid.replace(" ", "_").replace("(", "").replace(")", "")
            path = MINIMAX_OUT / (tag + ".mp3")
            if path.exists() and path.stat().st_size > 10000:
                print("[DONE]", tag)
                continue
            synth_minimax(vid, path, cfg)
            print("[OK]", tag, path.stat().st_size if path.exists() else 0)
            time.sleep(1.5)


if __name__ == "__main__":
    main()
