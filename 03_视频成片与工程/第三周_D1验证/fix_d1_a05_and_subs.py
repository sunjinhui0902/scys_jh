#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Re-synthesize D1早 A05 without breaking '故意让' and rebuild D1早 full_voice.wav + tts_meta.json."""

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


def trim_silence(src: Path, dst: Path) -> None:
    cmd = [
        FFMPEG, "-y", "-i", str(src),
        "-af",
        "silenceremove=start_periods=1:start_duration=0:start_threshold=-45dB,"
        "areverse,silenceremove=start_periods=1:start_duration=0:start_threshold=-45dB,areverse,"
        "apad=pad_dur=0.05",
        "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", str(dst),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> None:
    cfg = load_config(ROOT / "config" / "voice_api" / "config.yaml")
    audio_dir = WORK / "D1早" / "audio"
    meta = json.loads((audio_dir / "tts_meta.json").read_text(encoding="utf-8"))

    # Re-synth A05 with speed=0.98 so '我要是故意让，' flows naturally without splitting '故意让'
    a05_raw = audio_dir / "A05_raw.mp3"
    a05_wav = audio_dir / "A05.wav"
    r = cfg["roles"]["grandpa"]
    line_cfg = {
        "voice_id": r["voice_id"],
        "speed": 0.98,
        "pitch": int(r.get("pitch", -1)),
        "vol": float(r.get("vol", 1.0)),
        "text": "我要是故意让，他赢十盘也学不会。",
        "model": cfg.get("model", "speech-2.8-hd"),
    }
    throttle(cfg)
    res = synthesize_minimax(cfg, line_cfg, a05_raw)
    trim_silence(a05_raw, a05_wav)
    new_dur = probe_duration_ms(FFMPEG, a05_wav)
    print(f"Re-synthesized D1早 A05: {new_dur}ms | trace={res.get('trace_id', '')}")

    # Rebuild full_voice.wav and update timestamps
    cursor_ms = 0
    concat_list = []
    for item in meta["lines"]:
        lid = item["id"]
        wav_p = audio_dir / f"{lid}.wav"
        sil_p = audio_dir / f"{lid}_sil.wav"
        dur_ms = probe_duration_ms(FFMPEG, wav_p)
        if lid == "A05":
            item["trace_id"] = res.get("trace_id", "") + " (重配版)"
        item["speech_ms"] = dur_ms
        item["start_ms"] = cursor_ms
        item["end_ms"] = cursor_ms + dur_ms
        cursor_ms = item["end_ms"] + item["pause_after_ms"]
        concat_list.extend([wav_p, sil_p])

    list_txt = audio_dir / "concat.txt"
    list_txt.write_text("\n".join(f"file '{p.as_posix()}'" for p in concat_list), encoding="utf-8")
    full_wav = audio_dir / "full_voice.wav"
    subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(list_txt), "-c:a", "pcm_s16le", str(full_wav)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    total_ms = probe_duration_ms(FFMPEG, full_wav)
    meta["total_ms"] = total_ms
    (audio_dir / "tts_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Rebuilt D1早 full_voice.wav: {total_ms / 1000.0:.3f}s")


if __name__ == "__main__":
    main()
