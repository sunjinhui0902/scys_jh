# -*- coding: utf-8 -*-
"""竞品口播 —— 相减法提取干净人声。

原理：
    口播人声 ≈ 原始混音 − 已分离的 Instrumental（伴奏）分轨
比"再跑一遍全长神经人声分离"快两个数量级（后者 180s 片段约 25 分钟墙钟）。
前置条件：需要 UVR-MDX-NET-Inst_HQ_3 分离出的 Instrumental 分轨，
          由 separate_instrumental.py 产出。

质量自检（客观，不用听感）：
    用 Silero VAD 标注"纯音乐空隙"与"人声段"，分别测能量；
    空隙残余应显著低于人声段（差 12 dB 以上为干净）。

用法：
    python scripts/competitor_audio_audit/extract_voice.py --manifest <manifest.json>
    python scripts/competitor_audio_audit/extract_voice.py --manifest ... --sep-dir <分轨目录>
"""
import argparse
import json
import os
import subprocess
import wave
from pathlib import Path

import numpy as np

from common import (ASSET_VOICE, DEFAULT_MANIFEST, SCRATCH, ensure_dirs, find_ffmpeg,
                    ffmpeg_probe, load_wav)

SR = 22050
START = 30.0          # 提取起点（秒），与本批次一致


def rms_db(x):
    if len(x) == 0:
        return -120.0
    return float(20 * np.log10(np.sqrt(float((x ** 2).mean())) + 1e-12))


def write_wav(path, x, sr=SR):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(np.clip(x * 32767, -32768, 32767).astype(np.int16).tobytes())


def best_offset(a, b, max_lag=4410):
    """FFT 互相关求 b 相对 a 的最佳样本级偏移（相减前必须对齐，否则人声被抵消）。"""
    n = min(len(a), len(b), 1 << 20)
    A = a[:n] - a[:n].mean()
    B = b[:n] - b[:n].mean()
    if np.sqrt((A ** 2).sum()) < 1e-9:
        return 0, 0.0
    m = len(A)
    L = 1 << int(np.ceil(np.log2(m + max_lag * 2)))
    fa = np.fft.rfft(A, L)
    fb = np.fft.rfft(B[:max_lag * 2], L)
    cc = np.fft.irfft(fa * np.conj(fb), L)
    cc = np.concatenate([cc[-(max_lag - 1):], cc[:max_lag]])
    i = int(np.argmax(np.abs(cc)))
    return i - (max_lag - 1), 0.0   # 归一化值不可靠，只用偏移量


def vad_segments(x, sr=SR):
    """Silero VAD → (人声段, 纯音乐空隙)。"""
    import torch
    from silero_vad import get_speech_timestamps, load_silero_vad
    model = load_silero_vad()
    y16 = x
    if sr != 16000:
        import librosa
        y16 = librosa.resample(x, orig_sr=sr, target_sr=16000)
    ts = get_speech_timestamps(torch.from_numpy(y16.astype(np.float32)), model,
                               sampling_rate=16000, min_speech_duration_ms=200,
                               speech_pad_ms=100)
    speech = [(t["start"] / 16000.0, t["end"] / 16000.0) for t in ts]
    gaps = []
    prev = 0.0
    for s, e in speech:
        if s - prev > 0.45:
            gaps.append((prev, s))
        prev = e
    total = len(x) / sr
    if total - prev > 0.45:
        gaps.append((prev, total))
    return speech, gaps


def extract_audio(video_path, out_wav, sr=SR):
    subprocess.run([find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(video_path), "-vn", "-ac", "1", "-ar", str(sr),
                    "-c:a", "pcm_s16le", str(out_wav)], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="视频清单 JSON")
    ap.add_argument("--sep-dir", default=None, help="Instrumental 分轨目录")
    ap.add_argument("--out", default=None, help="输出目录（默认 02_公共资产库/竞品口播人声_*）")
    args = ap.parse_args()

    mpath = Path(args.manifest)
    if not mpath.exists():
        raise SystemExit(f"清单不存在：{mpath}")
    manifest = json.load(open(mpath, encoding="utf-8"))

    out_dir = Path(args.out) if args.out else ASSET_VOICE
    ensure_dirs(out_dir, SCRATCH / "orig_audio")

    sep_dir = Path(args.sep_dir) if args.sep_dir else SCRATCH / "sep_batch"
    report = []
    for rec in manifest:
        tag = rec["tag"]
        account = rec["account"]
        wav_src = Path(rec.get("wav") or "")
        if not wav_src.exists():
            wav_src = SCRATCH / "orig_audio" / (tag + ".wav")
            if not wav_src.exists():
                print(f"[抽音轨] {tag}")
                extract_audio(rec["path"], wav_src)

        inst_files = [f for f in os.listdir(sep_dir)
                      if f.startswith(f"{tag}_excerpt") and "Instrumental" in f] if sep_dir.exists() else []
        if not inst_files:
            print(f"[SKIP] 无伴奏分轨：{tag}（先跑 separate_instrumental.py）")
            continue
        inst, sr = load_wav(sep_dir / inst_files[0])
        n = len(inst)

        orig_slice = SCRATCH / "orig_audio" / f"{tag}_slice.wav"
        if not orig_slice.exists():
            subprocess.run([find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
                            "-ss", str(START), "-t", str(n / SR + 0.5), "-i", str(wav_src),
                            "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", str(orig_slice)],
                           check=True)
        orig, _ = load_wav(orig_slice)
        m = min(len(orig), len(inst))
        orig, inst = orig[:m], inst[:m]

        off, _ = best_offset(orig, inst)
        if abs(off) > 1:
            inst = np.roll(inst, -off)
        voice = orig - inst
        voice = voice - voice.mean()
        pk = float(np.abs(voice).max())
        if pk > 0:
            voice = voice / pk * 0.707

        speech, gaps = vad_segments(voice)
        sp_e = [rms_db(voice[int(a * SR):int(a * SR) + 6600]) for a, b in speech if a < n / SR]
        gp_e = [rms_db(voice[int(a * SR):int(a * SR) + 6600]) for a, b in gaps if a < n / SR]
        s = float(np.median(sp_e)) if sp_e else None
        g = float(np.median(gp_e)) if gp_e else None

        base = out_dir / f"{tag}_口播人声_{account}"
        write_wav(base.with_suffix(".wav"), voice)
        subprocess.run([find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
                        "-i", str(base.with_suffix(".wav")), "-vn",
                        "-c:a", "libmp3lame", "-b:a", "192k", str(base.with_suffix(".mp3"))],
                       check=True)
        report.append({"tag": tag, "account": account, "day": rec.get("day"),
                       "sec": round(m / SR, 1), "offset_samples": int(off),
                       "voice_seg_db": None if s is None else round(s, 1),
                       "gap_residual_db": None if g is None else round(g, 1),
                       "residual_ratio_db": None if (g is None or s is None) else round(g - s, 1)})
        print(f"[OK] {tag:<20} {m/SR:>6.1f}s 偏移{off:>4}  "
              f"人声段{'' if s is None else f'{s:>6.1f}'}dB "
              f"空隙残余{'' if g is None else f'{g:>6.1f}'}dB", flush=True)

    json.dump(report, open(out_dir / "口播人声清单.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n清单 ->", out_dir / "口播人声清单.json")


if __name__ == "__main__":
    main()
