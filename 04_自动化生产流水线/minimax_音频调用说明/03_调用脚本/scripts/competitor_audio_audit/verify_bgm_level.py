# -*- coding: utf-8 -*-
"""B 档电平落地验证：证明混音里 BGM 从"不可闻"变成"人声间隙可闻"。

产出（03_视频成片与工程/BGM电平验证_20261120/）：
    A档_旧默认_人声+BGM.mp3   用原始 −52.9 dB 的古琴（现状）
    B档_新默认_人声+BGM.mp3   用归一后 −23.3 dB 的古琴（本次决定）
    B档_仅BGM.mp3             只铺 BGM，便于直接听衬底
    A_B对照_串烧.mp3           A → B 连播
    电平验证.json             逐段实测数据
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ROOT = common.ROOT
FF = common.find_ffmpeg()
OUT = ROOT / "03_视频成片与工程" / "BGM电平验证_20261120"
WORK = ROOT / "scratch" / "bgm_level_check"
OUT.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)

VOICE = ROOT / "03_视频成片与工程" / "音色对比_20261118" / "V1_当前默认_云健-6Hz-8%" / "voice_master.mp3"
BGM_NEW = ROOT / "01_配音与音色库" / "背景音乐库" / "bgm_shili_guofeng.mp3"
BGM_OLD = ROOT / "01_配音与音色库" / "背景音乐库" / "_原始备份" / "bgm_shili_guofeng_原始-52.9dB.mp3"

VOICE_GAIN = 1.4125     # +3.0 dB（管线基准）
BGM_GAIN = 0.2239       # -13.0 dB（管线基准，不变）
FADE_OUT = 2.5


def run(args):
    subprocess.run(args, check=True)


def mean_of(path, start=None, dur=None):
    """测某段（或整段）的 mean/peak dB。"""
    cmd = [FF, "-hide_banner", "-nostats"]
    if start is not None:
        cmd += ["-ss", str(start)]
    cmd += ["-i", str(path)]
    if dur is not None:
        cmd += ["-t", str(dur)]
    cmd += ["-af", "volumedetect", "-f", "null", "-"]
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    import re
    err = p.stderr or ""
    mean = re.search(r"mean_volume:\s*(-?[\d.]+) dB", err)
    peak = re.search(r"max_volume:\s*(-?[\d.]+) dB", err)
    return {"mean_db": float(mean.group(1)) if mean else None,
            "peak_db": float(peak.group(1)) if peak else None}


def build_bgm_bed(src_bgm, tag, dur):
    """BGM 源 → PCM → 循环铺满 dur → 施加管线增益与末尾淡出 → wav"""
    pcm = WORK / ("%s_pcm.wav" % tag)
    run([FF, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src_bgm),
         "-ac", "1", "-ar", "22050", "-c:a", "pcm_s16le", str(pcm)])
    bed = WORK / ("%s_bed.wav" % tag)
    run([FF, "-hide_banner", "-loglevel", "error", "-y", "-stream_loop", "-1", "-i", str(pcm),
         "-af", "volume=%.4f,atrim=0:%.3f,afade=t=out:st=%.3f:d=%.1f" % (
             BGM_GAIN, dur, max(dur - FADE_OUT, 0), FADE_OUT),
         "-c:a", "pcm_s16le", str(bed)])
    return bed


def mix(voice, bed, out_mp3):
    run([FF, "-hide_banner", "-loglevel", "error", "-y",
         "-i", str(voice), "-i", str(bed),
         "-filter_complex", "[0:a]volume=%.4f[v];[1:a]volume=1.0[b];"
                            "[v][b]amix=inputs=2:duration=first:normalize=0[o]" % VOICE_GAIN,
         "-map", "[o]", "-c:a", "libmp3lame", "-b:a", "192k", str(out_mp3)])
    return out_mp3


def find_gaps(voice, dur, want=3, min_len=0.30):
    """用 Silero VAD 找出人声轨里真正的停顿（非语音段），取最长的几段。

    这是"BGM 能不能被听见"的关键测点：停顿处混音里剩下的就只有 BGM。
    """
    import numpy as np
    import torch
    import librosa
    from silero_vad import get_speech_timestamps, load_silero_vad

    wav, sr = librosa.load(str(voice), sr=16000, mono=True)
    sivad = load_silero_vad()
    ts = get_speech_timestamps(torch.from_numpy(wav.astype(np.float32)), sivad,
                               sampling_rate=16000,
                               min_speech_duration_ms=200, speech_pad_ms=50)
    spans = [(t["start"] / 16000.0, t["end"] / 16000.0) for t in ts]
    gaps = []
    cur = 0.0
    for s, e in spans:
        if s - cur >= min_len:
            gaps.append((cur, s - cur))
        cur = max(cur, e)
    if dur - cur >= min_len:
        gaps.append((cur, dur - cur))
    gaps.sort(key=lambda g: -g[1])
    return sorted(gaps[:want])


def main():
    dur, _ = common.ffmpeg_probe(VOICE)
    dur = round(dur, 3)
    print("人声时长: %.2fs" % dur)

    # A 档（旧默认，原版 −52.9 dB）
    bedA = build_bgm_bed(BGM_OLD, "A", dur)
    mixA = mix(VOICE, bedA, OUT / "A档_旧默认_人声+BGM.mp3")
    run([FF, "-hide_banner", "-loglevel", "error", "-y", "-i", str(bedA),
         "-c:a", "libmp3lame", "-b:a", "192k", str(OUT / "A档_仅BGM.mp3")])

    # B 档（新默认，归一后 −23.3 dB）
    bedB = build_bgm_bed(BGM_NEW, "B", dur)
    mixB = mix(VOICE, bedB, OUT / "B档_新默认_人声+BGM.mp3")
    run([FF, "-hide_banner", "-loglevel", "error", "-y", "-i", str(bedB),
         "-c:a", "libmp3lame", "-b:a", "192k", str(OUT / "B档_仅BGM.mp3")])

    # 串烧 A → B
    lst = WORK / "burn.txt"
    lst.write_text("file '%s'\nfile '%s'\n" % (
        (OUT / "A档_旧默认_人声+BGM.mp3").as_posix(),
        (OUT / "B档_新默认_人声+BGM.mp3").as_posix()), encoding="utf-8")
    run([FF, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-c:a", "libmp3lame", "-b:a", "192k",
         str(OUT / "A_B对照_串烧.mp3")])

    # 逐段实测：人声段 vs **真实语音间隙**（BGM 单独可闻的关键）
    data = {"voice_only": mean_of(VOICE),
            "bgm_source_new": mean_of(BGM_NEW),
            "bgm_source_old": mean_of(BGM_OLD),
            "bgm_bed_A_only": mean_of(bedA),
            "bgm_bed_B_only": mean_of(bedB),
            "mix_A": mean_of(mixA),
            "mix_B": mean_of(mixB),
            "segments": {}}
    gaps = find_gaps(VOICE, dur)
    data["voice_gaps_found"] = [{"start": round(s, 2), "dur": round(d, 2)} for s, d in gaps]
    for i, (st, d) in enumerate(gaps, 1):
        data["segments"]["A_gap%d" % i] = mean_of(mixA, st, d)
        data["segments"]["B_gap%d" % i] = mean_of(mixB, st, d)
    data["segments"]["A_voice"] = mean_of(mixA, 2.0, 2.0)
    data["segments"]["B_voice"] = mean_of(mixB, 2.0, 2.0)

    (OUT / "电平验证.json").write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print("产物 → %s" % OUT)


if __name__ == "__main__":
    main()
