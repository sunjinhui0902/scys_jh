# -*- coding: utf-8 -*-
"""竞品音频 —— UVR-MDX-NET 伴奏分离（提取口播人声与纯 BGM 的前置步骤）。

对每条竞品视频取片段做 Instrumental（去人声）分离，输出到工作目录。
依赖 audio-separator + onnxruntime；首次运行会下载 UVR-MDX-NET-Inst_HQ_3.onnx 模型。

用法：
    python scripts/competitor_audio_audit/separate_instrumental.py --manifest <manifest.json>
    python scripts/competitor_audio_audit/separate_instrumental.py --excerpt-sec 240
"""
import argparse
import json
import os
import subprocess
import wave
from pathlib import Path

import numpy as np

from common import DEFAULT_MANIFEST, SCRATCH, ensure_dirs, find_ffmpeg, load_wav

SR = 22050
START_SEC = 30.0
MODEL_NAME = "UVR-MDX-NET-Inst_HQ_3.onnx"


def rms_db(x):
    if len(x) == 0:
        return -120.0
    return 20 * np.log10(np.sqrt(np.maximum((x ** 2).mean(), 1e-12)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--work", default=str(SCRATCH / "sep_batch"))
    ap.add_argument("--excerpt-sec", type=float, default=240.0,
                    help="每条分离的片段长度（口播提取需 ≥240 秒）")
    ap.add_argument("--model-dir", default=str(SCRATCH / "models"))
    args = ap.parse_args()

    mpath = Path(args.manifest)
    if not mpath.exists():
        raise SystemExit(f"清单不存在：{mpath}")
    manifest = json.load(open(mpath, encoding="utf-8"))

    work = Path(args.work)
    ensure_dirs(work, Path(args.model_dir))

    from audio_separator.separator import Separator
    sep = Separator(output_dir=str(work), output_format="WAV",
                    model_file_dir=str(Path(args.model_dir)),
                    output_single_stem="Instrumental")
    sep.download_model_and_data(MODEL_NAME)
    sep.load_model(MODEL_NAME)

    for rec in manifest:
        tag = rec["tag"]
        src = work / f"{tag}_excerpt.wav"
        if not src.exists():
            wav_src = Path(rec.get("wav") or "")
            if not wav_src.exists():
                wav_src = SCRATCH / "orig_audio" / (tag + ".wav")
            if not wav_src.exists():
                print(f"[SKIP] {tag} 缺音轨，先跑 extract_audio")
                continue
            subprocess.run([find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
                            "-ss", str(START_SEC), "-t", str(args.excerpt_sec),
                            "-i", str(wav_src), "-ac", "1", "-ar", str(SR),
                            "-c:a", "pcm_s16le", str(src)], check=True)
        sep.separate(str(src))
        produced = [f for f in os.listdir(work)
                    if f.startswith(f"{tag}_excerpt") and "Instrumental" in f]
        if not produced:
            print(f"[FAIL] {tag}")
            continue
        x, sr = load_wav(work / produced[0])
        print(f"[OK] {tag:<20} {len(x)/sr:>6.1f}s  RMS {rms_db(x):>6.1f} dBFS", flush=True)

    print("\n分轨目录 ->", work)


if __name__ == "__main__":
    main()
