# -*- coding: utf-8 -*-
"""授权 BGM 选曲试听串烧：每首候选前用 TTS 报曲名，方便用户直接试听定稿。

用法：
    python scripts/competitor_audio_audit/build_bgm_audition.py
产物：
    03_视频成片与工程/BGM试听_20261119/
        国风古建_试听.mp3 / 史诗解说_试听.mp3 / 温情叙事_试听.mp3
        全套_试听.mp3 / 试听顺序.txt
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ROOT = common.ROOT
ASSET = ROOT / "02_公共资产库" / "授权BGM候选_20261119"
OUT_DIR = ROOT / "03_视频成片与工程" / "BGM试听_20261119"
WORK = ROOT / "scratch" / "bgm_audition"

VOICE = "zh-CN-YunjianNeural"   # 与 AGENTS.md 默认基准一致
RATE = "-8%"
PITCH = "-6Hz"
SEG_SEC = 16.0


def tts(text, out_path):
    """Edge-TTS 生成报幕语音（免费免密钥）。"""
    import asyncio
    import edge_tts
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and out_path.stat().st_size > 1024:
        return out_path
    comm = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH)

    async def run():
        await comm.save(str(out_path))

    asyncio.run(run())
    return out_path


def ffmpeg():
    return common.find_ffmpeg()


def excerpt(src, dst, sec=SEG_SEC):
    """截取前 sec 秒并转成 PCM wav（先转 PCM 再做后续拼接，避免 mp3 直接拼接报错）。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(src), "-t", str(sec), "-ac", "1", "-ar", "22050",
                    "-c:a", "pcm_s16le", str(dst)], check=True)
    return dst


def concat(wavs, out_mp3):
    lst = out_mp3.with_suffix(".txt")
    lst.write_text("\n".join("file '%s'" % str(w).replace("\\", "/") for w in wavs), encoding="utf-8")
    subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c:a", "libmp3lame", "-b:a", "192k", str(out_mp3)], check=True)
    lst.unlink(missing_ok=True)
    return out_mp3


def main():
    spec = json.loads((ASSET / "选曲清单.json").read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    order_lines = []
    all_wavs = []

    for track, rows in spec.get("tracks_by_track", {}).items():
        name = track.split(" ", 1)[-1].split("（")[0]
        wavs = []
        for i, r in enumerate(rows, 1):
            src = None
            for p in (ASSET / r["source"] / r["channel"]).glob("*.mp3"):
                if p.stem == r["title"]:
                    src = p
                    break
            if src is None:
                print("  ! 找不到音频:", r["title"])
                continue
            lic = "CC0公版" if "CC0" in (r.get("license") or "") else "Mixkit"
            say = "第%s首，%s。%s。"
            text = say % (i, r["title"], lic)
            v = tts(text, WORK / ("v_%02d_%s.mp3" % (i, r["title"][:24].replace("'", "").replace(" ", "_"))))
            ve = excerpt(v, WORK / ("v_%02d_%s.wav" % (i, r["title"][:24].replace("'", "").replace(" ", "_"))))
            be = excerpt(src, WORK / ("b_%02d_%s.wav" % (i, r["title"][:24].replace("'", "").replace(" ", "_"))))
            wavs += [ve, be]
            order_lines.append("%s 第%d首｜%s｜%s｜%s" % (name, i, r["title"], lic, r.get("listening_style") or ""))
            print("  ✓ %s 第%d首 %s" % (name, i, r["title"]))
        if wavs:
            concat(wavs, OUT_DIR / ("%s_试听.mp3" % name))
            all_wavs += wavs

    if all_wavs:
        concat(all_wavs, OUT_DIR / "全套_试听.mp3")
    (OUT_DIR / "试听顺序.txt").write_text("\n".join(order_lines), encoding="utf-8")
    print("试听串烧 → %s" % OUT_DIR)


if __name__ == "__main__":
    main()
