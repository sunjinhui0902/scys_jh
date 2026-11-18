# -*- coding: utf-8 -*-
"""音色 A/B 样片对比构建器。

同一画面、同文案、同 BGM、同混音参数，只改 Edge 配音的 pitch/rate，
产出可直接横评的样片 + 一条对照串烧。

两个已踩过的坑（务必保留这两处写法）：
  1) 对 mp3 直接 -stream_loop 会在文件尾触发解码错误甚至卡死
     → 先转 PCM wav 再循环
  2) -stream_loop 视频流 + 输出侧 -t 截断会写出损坏的 mp4
     → 预先生成干净的 _video_only_Ns.mp4（-c:v copy），再 -c:v copy -shortest 拼音频

用法：
    python scripts/competitor_audio_audit/build_ab_sample.py --project W6_11-08_1900
"""
import argparse
import asyncio
import json
import os
import re
import subprocess
from pathlib import Path

import edge_tts

from common import (BGM_GUOFENG, PROJECT_DIR, SCRATCH, ensure_dirs, ffmpeg_probe,
                    find_ffmpeg)

VOICE_GAIN = 1.4125   # +3.0 dB（管线规范）
BGM_GAIN = 0.2239     # -13.0 dB（管线规范）
FADE_OUT = 2.5        # 秒

VARIANTS = [
    ("V1_当前默认_云健-6Hz-8%", "zh-CN-YunjianNeural", "-6Hz", "-8%", "当前默认黄金音"),
    ("V2_竞品最接近_云健+28Hz-4%", "zh-CN-YunjianNeural", "+28Hz", "-4%", "嵌入距离竞品主流最近"),
    ("V3_保守版_云健+26Hz-8%", "zh-CN-YunjianNeural", "+26Hz", "-8%", "只抬音高，保留慢语速"),
]


def run(cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def dur(path):
    d, _ = ffmpeg_probe(path)
    return d


def extract_text(script_md):
    raw = Path(script_md).read_text(encoding="utf-8")
    m = re.search(r"##\s*纯净口播文案\s*\n+(.+?)(?=\n##\s|\Z)", raw, re.S)
    return m.group(1).strip()


async def synth(text, voice, pitch, rate, out):
    kw = {}
    if pitch != "+0Hz":
        kw["pitch"] = pitch
    if rate != "+0%":
        kw["rate"] = rate
    last = None
    for attempt in range(5):
        try:
            await edge_tts.Communicate(text, voice, **kw).save(str(out))
            if out.exists() and out.stat().st_size > 10000:
                return True
            last = RuntimeError("空文件")
        except Exception as e:
            last = e
        await asyncio.sleep(3 + attempt * 3)
    print("   FAIL", voice, pitch, rate, str(last)[:120])
    return False


def make_bgm_loop(out_dir, need_sec):
    """先转 PCM 再循环，规避 mp3 stream_loop 的解码错误。"""
    dst = Path(out_dir) / "_bgm_loop.wav"
    if not dst.exists() or dur(dst) < need_sec + 2:
        run([find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
             "-stream_loop", "30", "-i", str(BGM_GUOFENG), "-t", str(need_sec + 3),
             "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(dst)])
    return dst


def make_video_only(out_dir, src_video, sec):
    """预生成干净视频流（copy 不重编码），供各版本复用。"""
    dst = Path(out_dir) / f"_video_only_{int(sec)}s.mp4"
    if not dst.exists():
        run([find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
             "-stream_loop", "-1", "-i", str(src_video), "-t", str(sec),
             "-an", "-c:v", "copy", "-movflags", "+faststart", str(dst)])
    return dst


def mix(voice_mp3, out_mp3, bgm_loop):
    d = dur(voice_mp3)
    run([find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
         "-i", str(voice_mp3), "-stream_loop", "-1", "-i", str(bgm_loop),
         "-filter_complex",
         f"[0:a]volume={VOICE_GAIN}[v];"
         f"[1:a]volume={BGM_GAIN},atrim=0:{d},afade=t=out:st={max(d-FADE_OUT,0)}:d={FADE_OUT}[b];"
         f"[v][b]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[out]",
         "-map", "[out]", "-c:a", "libmp3lame", "-b:a", "192k", str(out_mp3)])


def build_video(video_only, mix_mp3, out_mp4):
    d = dur(mix_mp3)
    run([find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
         "-i", str(video_only), "-i", str(mix_mp3),
         "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
         "-movflags", "+faststart", str(out_mp4)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="W6_11-08_1900", help="底板工程目录名")
    ap.add_argument("--out", default=None, help="输出目录名（默认 03_视频成片与工程/音色对比_<日期>）")
    ap.add_argument("--reference", default=None, help="串烧末尾的竞品原声对照文件")
    args = ap.parse_args()

    proj = PROJECT_DIR / args.project
    script_md = proj / "01_文案与分镜" / "口播文案.md"
    if not script_md.exists():
        raise SystemExit(f"找不到口播文案：{script_md}")
    finals = sorted((proj / "05_成片").glob("*.mp4"))
    if not finals:
        raise SystemExit(f"找不到成片（用作画面底板）：{proj / '05_成片'}")
    src_video = finals[0]

    out_dir = Path(args.out) if args.out else PROJECT_DIR / ("音色对比_" + "20261118")
    ensure_dirs(out_dir)
    text = extract_text(script_md)
    print("口播净字数 %d" % len(text))

    mixes = []
    for label, voice, pitch, rate, note in VARIANTS:
        vdir = Path(out_dir) / label
        ensure_dirs(vdir)
        vm = vdir / "voice_master.mp3"
        if not (vm.exists() and vm.stat().st_size > 10000):
            print("[合成]", label)
            asyncio.run(synth(text, voice, pitch, rate, vm))
        mixp = vdir / f"{label}_混音.mp3"
        bgm_loop = make_bgm_loop(out_dir, dur(vm))
        mix(vm, mixp, bgm_loop)
        video_only = make_video_only(out_dir, src_video, 60)
        vid = vdir / f"{label}_样片.mp4"
        build_video(video_only, mixp, vid)
        mixes.append((label, mixp))
        print(f"[完成] {label}  {dur(mixp):.1f}s")

    # 对照串烧
    items = [str(m) for _, m in mixes]
    if args.reference and Path(args.reference).exists():
        items.append(str(Path(args.reference)))
    concat = Path(out_dir) / "concat.txt"
    with open(concat, "w", encoding="utf-8", newline="\n") as f:
        for p in items:
            f.write("file '" + p.replace("\\", "/") + "'\n")
    burn = Path(out_dir) / "音色A_B对照_串烧.mp3"
    run([find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
         "-f", "concat", "-safe", "0", "-i", str(concat),
         "-c:a", "libmp3lame", "-b:a", "192k", str(burn)])

    meta = {"base_project": args.project, "script": str(script_md.relative_to(PROJECT_DIR.parent)),
            "source_video": str(src_video.relative_to(PROJECT_DIR.parent)),
            "mix_spec": f"人声 +3.0dB (gain {VOICE_GAIN})；BGM -13dB (volume {BGM_GAIN})，"
                        f"循环铺满，末尾 {FADE_OUT}s 淡出",
            "variants": [{"variant": l, "voice": v, "pitch": p, "rate": r, "note": n,
                          "mix_mp3": str(Path(out_dir) / l / f"{l}_混音.mp3"),
                          "sample_video": str(Path(out_dir) / l / f"{l}_样片.mp4"),
                          "sec": round(dur(Path(out_dir) / l / f"{l}_混音.mp3"), 2)}
                         for l, v, p, r, n in VARIANTS],
            "burn_in": {"file": str(burn), "sec": round(dur(burn), 2),
                        "order": [l for l, _ in mixes] + (["参考对照"] if args.reference else [])}}
    json.dump(meta, open(Path(out_dir) / "音色对比清单.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n[串烧] " + str(burn))


if __name__ == "__main__":
    main()
