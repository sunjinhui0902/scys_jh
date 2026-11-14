#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Synthesize D1 (早/午/晚) TTS via MiniMax speech-2.8-hd with edge trimming and exact pauses."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from assemble_voice_test import get_ffmpeg, probe_duration_ms  # noqa: E402
from voice_api_tts import load_config, synthesize_minimax, throttle  # noqa: E402

FFMPEG = get_ffmpeg()

WORK = ROOT / "03_视频成片与工程" / "第三周_D1验证"

D1_SPECS = {
    "D1早": [
        # (id, role_key, text, pause_after_ms, speed_delta, pitch_delta)
        ("A01", "grandma", "又哭了？这盘棋输了，眼泪比棋子掉得还快。", 400, -0.02, 0),
        ("A02", "grandpa", "先别急着哄。", 500, -0.05, -1),
        ("A03", "grandpa", "难过可以，眼泪也可以流，可棋子不能摔，棋盘不能推——先把棋子收好，收棋，就是认这盘的结果。", 500, -0.03, 0),
        ("A04", "grandma", "可他说，爷爷故意赢他，不跟他玩了。", 300, 0.0, 0),
        ("A05", "grandpa", "我要是故意让，他赢十盘也学不会。", 400, -0.02, 0),
        ("A06", "grandpa", "孙子，听好：下棋跟过日子一样，输了先认，不摔、不赖、不笑话人。", 600, -0.05, 0),
        ("A07", "grandma", "那下次呢？", 300, 0.0, 1),
        ("A08", "grandpa", "下次开局前先说好三条：不摔棋子，不许悔棋，赢了不笑话人。", 400, -0.02, 0),
        ("A09", "grandpa", "做不到，今天就不下了。", 500, -0.05, -1),
        ("A10", "grandma", "行，规矩说在前面，比输了再讲道理管用。", 400, 0.0, 0),
        ("A11", "grandma", "等他心平了，再陪他看看这盘输在哪一步。", 600, -0.03, -1),
    ],
    "D1午": [
        ("A01", "grandpa", "您见过轻轨从居民楼里穿过去的吗？", 500, 0.0, 1),
        ("A02", "grandpa", "在重庆李子坝，列车从居民楼中间几层钻进钻出，站就设在楼里，车站和住户各走各的门，互不打扰。", 400, 0.0, 0),
        ("A03", "grandpa", "很多人以为，这是楼盖好了、轨道硬塞进去的。", 400, 0.0, 0),
        ("A04", "grandpa", "其实不是：车站和大楼是同期设计的，轨道从楼里预留的位置通过。", 400, -0.02, 0),
        ("A05", "grandpa", "山城的地形逼出了这个办法：地不够平，就往空中要路。", 500, -0.02, 0),
        ("A06", "grandpa", "这一穿，穿成了重庆的名片，全国的人跑来看。", 400, 0.02, 1),
        ("A07", "grandpa", "下次去重庆，别光在楼下拍照，坐一趟车亲身穿一回楼，那才叫过瘾。", 600, 0.0, 0),
    ],
    "D1晚": [
        ("A01", "grandpa", "半夜十一点，亲戚打来电话：孩子住院，押金还差两万——这样的钱，您借不借？", 600, -0.03, 0),
        ("A02", "grandpa", "这叫救急，人命关天的难处，搭把手是情分。", 400, -0.02, 0),
        ("A03", "grandpa", "可还有一种借：借去填窟窿、堵亏空，填进去多少都是无底洞。", 500, 0.0, 0),
        ("A04", "grandpa", "老话讲，救急不救穷。", 600, -0.06, -1),
        ("A05", "grandpa", "先说清：这句是民间老话，不是书里的原话；书里真正写着的，是《中国式人情世故》第二章那句——人情要厚积，关系在往来。", 400, -0.02, 0),
        ("A06", "grandpa", "再说我自己的做法：钱往外借之前，先把归还的约定说清楚，什么时候还、怎么还，当场说明白，金额大小都一样。", 400, 0.0, 0),
        ("A07", "grandpa", "这钱舍不舍得当人情送了，是借之前自己拿的主意，不是借出去以后被迫算了。", 500, -0.02, 0),
        ("A08", "grandpa", "约定在先，钱借得安心，交情也处得长久。", 500, -0.02, 0),
        ("A09", "grandpa", "这本书我放在主页橱窗里了，点开我主页，商品橱窗里就有。", 400, 0.0, 0),
        ("A10", "grandpa", "您借出去的钱，后来要回来了吗？", 800, -0.02, 0),
    ],
}


def trim_silence(src: Path, dst: Path) -> None:
    """Trim leading and trailing silence without clipping speech tails."""
    cmd = [
        FFMPEG, "-y", "-i", str(src),
        "-af",
        "silenceremove=start_periods=1:start_duration=0:start_threshold=-45dB,"
        "areverse,silenceremove=start_periods=1:start_duration=0:start_threshold=-45dB,areverse,"
        "apad=pad_dur=0.05",
        "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", str(dst),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def make_silence(dur_ms: int, dst: Path) -> None:
    cmd = [
        FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-t", f"{dur_ms / 1000.0:.3f}", "-c:a", "pcm_s16le", str(dst),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> None:
    cfg = load_config(ROOT / "config" / "voice_api" / "config.yaml")
    roles = cfg["roles"]
    summary = {}

    for ep, lines in D1_SPECS.items():
        audio_dir = WORK / ep / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        meta_lines = []
        concat_list = []
        cursor_ms = 0

        for idx, (lid, rkey, text, pause_ms, sdelta, pdelta) in enumerate(lines):
            r = roles[rkey]
            raw_mp3 = audio_dir / f"{lid}_raw.mp3"
            trim_wav = audio_dir / f"{lid}.wav"
            line_cfg = {
                "voice_id": r["voice_id"],
                "speed": round(float(r.get("speed", 0.95)) + sdelta, 2),
                "pitch": int(r.get("pitch", 0)) + pdelta,
                "vol": float(r.get("vol", 1.0)),
                "text": text,
                "model": cfg.get("model", "speech-2.8-hd"),
            }
            if not raw_mp3.exists() or raw_mp3.stat().st_size == 0:
                throttle(cfg)
                res = synthesize_minimax(cfg, line_cfg, raw_mp3)
                trace_id = res.get("trace_id", "")
            else:
                trace_id = "cached"

            trim_silence(raw_mp3, trim_wav)
            dur_ms = probe_duration_ms(FFMPEG, trim_wav)
            start_ms = cursor_ms
            end_ms = start_ms + dur_ms
            cursor_ms = end_ms

            concat_list.append(trim_wav)
            sil_wav = audio_dir / f"{lid}_sil.wav"
            make_silence(pause_ms, sil_wav)
            concat_list.append(sil_wav)
            cursor_ms += pause_ms

            meta_lines.append({
                "id": lid,
                "role": r["name"],
                "voice_id": r["voice_id"],
                "text": text,
                "chars": len(text),
                "speech_ms": dur_ms,
                "pause_after_ms": pause_ms,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "trace_id": trace_id,
            })
            print(f"[{ep}] {lid} ({r['name']}): {dur_ms}ms + {pause_ms}ms pause | trace={trace_id}")

        list_txt = audio_dir / "concat.txt"
        list_txt.write_text(
            "\n".join(f"file '{p.as_posix()}'" for p in concat_list),
            encoding="utf-8",
        )
        full_wav = audio_dir / "full_voice.wav"
        subprocess.run(
            [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(list_txt), "-c:a", "pcm_s16le", str(full_wav)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        total_ms = probe_duration_ms(FFMPEG, full_wav)
        summary[ep] = {
            "total_ms": total_ms,
            "total_chars": sum(x["chars"] for x in meta_lines),
            "lines": meta_lines,
        }
        (audio_dir / "tts_meta.json").write_text(
            json.dumps(summary[ep], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"==> [{ep}] full_voice.wav = {total_ms / 1000.0:.3f}s, chars={summary[ep]['total_chars']}")

    (WORK / "d1_tts_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
