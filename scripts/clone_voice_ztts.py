#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用零样本克隆配音器（E2-F5-TTS，零成本 / 免 API key）

背景
----
`scripts/clone_wangliqun_tts.py` 是历史样例：参考音频、参考台词、脚本、输出全部写死，
而且 `list(glob("王立群*.mp3"))[0]` 会匹配到 3 个文件、靠排序碰运气命中。
本脚本把同样的能力参数化，并修掉那个隐患。

零样本克隆的硬要求
------------------
E2-F5-TTS 是 (参考音频, 参考文本, 生成文本) 三元组：
  * 参考音频建议 **5~15 秒**清晰单人人声，太长（分钟级）会漂；
  * 参考文本必须与参考音频**逐字对应**，对不上音色会明显漂移；
  * 生成文本按语义短段逐段合成，段与段之间音色一致性会下降，需人工试听验收。

用法
----
    # 1) 先切参考片段（5~10 秒）并写好逐字对应的参考文本
    python scripts/clone_voice_ztts.py \
        --ref-audio "01_配音与音色库/对标原声参考/食力过日子_带孙辈长见识_下集/voice_master.wav" \
        --ref-start 30 --ref-duration 8 \
        --ref-text "参考文本.txt" \
        --script "03_视频成片与工程/XX/01_文案与分镜/口播文案.md" \
        --out-dir "01_配音与音色库/方案A克隆音色_20261119_竞品节奏_v01" \
        --chunk-min 18 --chunk-max 40

所有路径从项目根目录推导；禁止写死盘符。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def extract_script_text(script_path: Path) -> str:
    """从 Gemini 标准工程 Markdown 里取「纯净口播文案」段。"""
    raw = script_path.read_text(encoding="utf-8")
    m = re.search(r"##\s*纯净口播文案\s*\n+(.+?)(?=\n##\s|\Z)", raw, re.S)
    if m:
        return m.group(1).strip()
    return raw.strip()


def split_sentences(text: str, chunk_min: int, chunk_max: int):
    """按标点切语义短段，长段再按逗号/分号二次切分。

    chunk_min/chunk_max 直接控制"平均句长"，是复刻竞品短句快切节奏的主要旋钮：
    竞品主流平均句长 1.7~2.5 秒（约 8~14 字/秒），对应 chunk 建议 18~40 字。
    """
    parts = re.split(r"([。！？\n]+)", text)
    chunks, cur = [], ""
    for p in parts:
        if not p:
            continue
        if p in "。！？\n":
            cur += p.strip()
            if len(cur) >= chunk_min:
                chunks.append(cur)
                cur = ""
        else:
            cur += p
    if cur.strip():
        chunks.append(cur.strip())

    final = []
    for c in chunks:
        c = c.strip()
        if not c:
            continue
        if len(c) <= chunk_max:
            final.append(c)
            continue
        sub = re.split(r"([，；、])", c)
        sub_cur = ""
        for sp in sub:
            sub_cur += sp
            if len(sub_cur) >= chunk_min:
                final.append(sub_cur)
                sub_cur = ""
        if sub_cur.strip():
            final.append(sub_cur.strip())
    return [c for c in final if c.strip()]


def probe_duration(path: Path) -> float:
    out = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(path)],
                         capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", out)
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def main():
    ap = argparse.ArgumentParser(description="E2-F5-TTS 零样本克隆配音（免费，免 key）")
    ap.add_argument("--ref-audio", required=True, help="参考音频路径")
    ap.add_argument("--ref-text", required=True, help="参考文本：文件路径或直接给字符串")
    ap.add_argument("--ref-start", type=float, default=0.0, help="参考音频起点（秒）")
    ap.add_argument("--ref-duration", type=float, default=10.0, help="参考音频截取长度（秒，建议 5~15）")
    ap.add_argument("--script", required=True, help="口播文案 Markdown（Gemini 标准工程格式）")
    ap.add_argument("--out-dir", required=True, help="输出目录（建议 01_配音与音色库/<名称>_<日期>_v01）")
    ap.add_argument("--chunk-min", type=int, default=18, help="每段最少字数")
    ap.add_argument("--chunk-max", type=int, default=40, help="每段最多字数")
    ap.add_argument("--space", default="mrfakename/E2-F5-TTS", help="Gradio 空间名")
    ap.add_argument("--name", default="克隆音色", help="本次音色名称（写进生成记录）")
    ap.add_argument("--dry-run", action="store_true", help="只切分与检查，不发起合成")
    args = ap.parse_args()

    ref_src = Path(args.ref_audio)
    if not ref_src.is_absolute():
        ref_src = ROOT / ref_src
    script_p = Path(args.script)
    if not script_p.is_absolute():
        script_p = ROOT / script_p
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir

    if not ref_src.exists():
        raise SystemExit(f"参考音频不存在：{ref_src}")
    if not script_p.exists():
        raise SystemExit(f"口播文案不存在：{script_p}")

    # ---- 参考文本：既支持"给文件路径"，也支持"直接把文本写在命令行" ----
    ref_text = ""
    rp = None
    try:
        rp = Path(args.ref_text)
        is_file = rp.exists()
    except OSError:
        is_file = False
    if is_file:
        ref_text = rp.read_text(encoding="utf-8").strip()
    else:
        ref_text = args.ref_text.strip()
    if not ref_text:
        raise SystemExit("参考文本为空（可给文件路径，也可直接给文本）")

    # ---- 切参考片段 ----
    ref_dir = out_dir / "参考片段"
    ref_dir.mkdir(parents=True, exist_ok=True)
    ref_clip = ref_dir / (ref_src.stem + f"__{int(args.ref_start)}s_{int(args.ref_duration)}s.wav")
    if not ref_clip.exists():
        subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
                        "-ss", str(args.ref_start), "-t", str(args.ref_duration),
                        "-i", str(ref_src), "-ac", "1", "-ar", "44100",
                        "-c:a", "pcm_s16le", str(ref_clip)], check=True)
    ref_dur = probe_duration(ref_clip)
    if ref_dur < 3:
        raise SystemExit(f"参考片段过短（{ref_dur:.1f}s），零样本克隆建议 5~15 秒")

    # ---- 切生成段 ----
    text = extract_script_text(script_p)
    chunks = split_sentences(text, args.chunk_min, args.chunk_max)
    print(f"参考片段 {ref_clip.name}  {ref_dur:.1f}s  参考文本 {len(ref_text)} 字")
    print(f"口播净字数 {len(text)}  切为 {len(chunks)} 段"
          f"（平均 {len(text)/max(len(chunks),1):.1f} 字/段）")
    if args.dry_run:
        for i, c in enumerate(chunks, 1):
            print(f"  [{i:02d}] {c}")
        return

    wav_dir = out_dir / "干声WAV"
    mp3_dir = out_dir / "干声MP3"
    wav_dir.mkdir(parents=True, exist_ok=True)
    mp3_dir.mkdir(parents=True, exist_ok=True)

    from gradio_client import Client, handle_file
    client = Client(args.space)

    ref_sha = sha256(ref_clip)
    records = []
    ok_wavs = []
    for i, sent in enumerate(chunks, 1):
        chunk_wav = wav_dir / f"chunk_{i:03d}.wav"
        key = hashlib.sha256(f"{ref_sha}|{ref_text}|{sent}".encode()).hexdigest()[:16]
        rec = {"index": i, "text": sent, "cache_key": key,
               "ref_audio": str(ref_clip.relative_to(ROOT)),
               "ref_audio_sha256": ref_sha, "ref_text": ref_text,
               "engine": "E2-F5-TTS(ZeroGPU)", "space": args.space}
        if chunk_wav.exists() and chunk_wav.stat().st_size > 1024:
            rec.update({"status": "cached", "file": str(chunk_wav.relative_to(ROOT)),
                        "sha256": sha256(chunk_wav), "sec": round(probe_duration(chunk_wav), 2)})
            records.append(rec)
            ok_wavs.append(chunk_wav)
            print(f"  [{i:02d}/{len(chunks)}] 命中缓存")
            continue

        rec["status"] = "failed"
        for attempt in range(3):
            try:
                res = client.predict(
                    ref_audio=handle_file(str(ref_clip)),
                    ref_text=ref_text,
                    gen_text=sent,
                    remove_silence=False,
                    api_name="/predict",
                )
                shutil.copy(str(res), str(chunk_wav))
                if chunk_wav.stat().st_size > 1024:
                    rec.update({"status": "ok", "file": str(chunk_wav.relative_to(ROOT)),
                                "sha256": sha256(chunk_wav),
                                "sec": round(probe_duration(chunk_wav), 2)})
                    ok_wavs.append(chunk_wav)
                    print(f"  [{i:02d}/{len(chunks)}] ✓ {rec['sec']}s  {sent[:18]}…")
                    break
            except Exception as e:
                rec["error"] = str(e)[:200]
                print(f"  [{i:02d}/{len(chunks)}] ⚠ 重试 {attempt+1}/3：{str(e)[:90]}")
                time.sleep(2 + attempt * 2)
        records.append(rec)

    failed = [r for r in records if r["status"] == "failed"]
    if failed:
        print(f"\n❌ {len(failed)}/{len(records)} 段失败，未生成母带。"
              f"修复参考文本/音频后重跑会命中缓存续跑。")
        json.dump({"voice": args.name, "records": records, "failed": len(failed)},
                  open(out_dir / "生成记录.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        raise SystemExit(1)

    # ---- 拼接母带 ----
    concat = out_dir / "concat_list.txt"
    with open(concat, "w", encoding="utf-8", newline="\n") as f:
        for w in ok_wavs:
            f.write("file '" + w.as_posix() + "'\n")
    master_wav = out_dir / "voice_master.wav"
    master_mp3 = out_dir / "voice_master.mp3"
    subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "concat", "-safe", "0", "-i", str(concat),
                    "-c:a", "pcm_s16le", "-ar", "44100", str(master_wav)], check=True)
    subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(master_wav), "-c:a", "libmp3lame", "-b:a", "320k",
                    str(master_mp3)], check=True)
    for w in ok_wavs:
        subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
                        "-i", str(w), "-c:a", "libmp3lame", "-b:a", "192k",
                        str(mp3_dir / (w.stem + ".mp3"))], check=True)

    summary = {
        "voice": args.name,
        "engine": "E2-F5-TTS(ZeroGPU)",
        "space": args.space,
        "cost": "免费公共空间，免 API key",
        "ref_audio": str(ref_clip.relative_to(ROOT)),
        "ref_audio_sha256": ref_sha,
        "ref_duration_sec": round(ref_dur, 2),
        "ref_text": ref_text,
        "script": str(script_p.relative_to(ROOT)),
        "chunk_min": args.chunk_min, "chunk_max": args.chunk_max,
        "segments": len(records), "failed": len(failed),
        "master_wav": str(master_wav.relative_to(ROOT)),
        "master_mp3": str(master_mp3.relative_to(ROOT)),
        "master_sec": round(probe_duration(master_wav), 2),
        "master_sha256": sha256(master_wav),
        "records": records,
        "human_review": "pending",
    }
    json.dump(summary, open(out_dir / "生成记录.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n✅ 母带：{master_wav.relative_to(ROOT)}  {summary['master_sec']}s")
    print(f"   记录：{(out_dir / '生成记录.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
