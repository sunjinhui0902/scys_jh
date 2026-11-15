#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第三周两版配音 A/B 对照生成
===========================
把「好大儿版」与「Antigravity 版」统一归一化到 -16 LUFS（消除音量差干扰听感），
再拼成 A/B 对照文件，并输出逐条差异清单。

用法：
    python scripts/make_week3_ab_compare.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

MINE = ROOT / "01_配音与音色库" / "第三周配音_20261115"
THEIRS = ROOT / "03_视频成片与工程" / "第三周_批量先行"
OUT = MINE / "AB对比"

# 对照条目：对话条 / 单人奇观条 / 晚场带引文条
EPISODES = ["D1早", "D1午", "D1晚"]
TARGET_LUFS = -16.0
TARGET_TP = -1.5
SILENCE_S = 2.0


def run(args: list[str]) -> None:
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"命令失败：{' '.join(args[:4])}...\n{(r.stderr or '')[-500:]}")


def duration(path: Path) -> float:
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=60)
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", r.stderr or "")
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def lufs(path: Path) -> float:
    r = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path), "-af", "ebur128=peak=true",
                        "-f", "null", "-"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=180)
    import re
    txt = r.stderr or ""
    i = txt.rfind("Integrated loudness")
    m = re.search(r"I:\s*(-?[\d.]+)\s*LUFS", txt[i:i + 400] if i >= 0 else txt[-400:])
    return float(m.group(1)) if m else float("nan")


def normalize(src: Path, dst: Path) -> None:
    run([FFMPEG, "-hide_banner", "-y", "-i", str(src),
         "-af", f"loudnorm=I={TARGET_LUFS}:TP={TARGET_TP}:LRA=11",
         "-ar", "44100", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "192k", str(dst)])


def concat(parts: list[Path], dst: Path) -> None:
    lst = OUT / f"_concat_{dst.stem}.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    run([FFMPEG, "-hide_banner", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c:a", "libmp3lame", "-b:a", "192k", str(dst)])
    lst.unlink(missing_ok=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    ag_summary = {x["ep_id"]: x for x in json.loads(
        (THEIRS / "week3_prep_summary.json").read_text(encoding="utf-8"))}

    rows = []
    for ep in EPISODES:
        mine_src = MINE / f"{ep}.mp3"
        theirs_src = THEIRS / ep / "audio" / "voice_16lufs.wav"
        if not mine_src.is_file() or not theirs_src.is_file():
            print(f"[跳过] {ep} 缺源文件 mine={mine_src.is_file()} theirs={theirs_src.is_file()}")
            continue

        n_mine = OUT / f"单版_好大儿版_{ep}.mp3"
        n_theirs = OUT / f"单版_Antigravity版_{ep}.mp3"
        normalize(mine_src, n_mine)
        normalize(theirs_src, n_theirs)

        sil = OUT / f"_sil_{ep}.mp3"
        run([FFMPEG, "-hide_banner", "-y", "-f", "lavfi",
             "-i", f"anullsrc=r=44100:cl=mono", "-t", str(SILENCE_S),
             "-c:a", "libmp3lame", "-b:a", "192k", str(sil)])

        ab = OUT / f"AB_{ep}_前Antigravity_后好大儿版.mp3"
        concat([n_theirs, sil, n_mine], ab)

        dm, dt = duration(n_mine), duration(n_theirs)
        rows.append({
            "ep": ep, "mine_s": dm, "theirs_s": dt,
            "mine_lufs": lufs(n_mine), "theirs_lufs": lufs(n_theirs),
            "ab": ab, "n_mine": n_mine, "n_theirs": n_theirs,
        })
        sil.unlink(missing_ok=True)
        print(f"[完成] {ep}  Antigravity {dt:.1f}s / 好大儿 {dm:.1f}s  差 {dm - dt:+.1f}s")

    # 逐条全量时长差（来自两边实测数据）
    print()
    print("=== 全 20 条时长对比 ===")
    print(f"{'条目':8s} {'好大儿版':>9s} {'Antigravity版':>13s} {'差值':>8s}")
    diffs = []
    for ep, a in ag_summary.items():
        mine_sec = duration(MINE / f"{ep}.mp3") if (MINE / f"{ep}.mp3").is_file() else 0.0
        d = mine_sec - float(a["duration_s"])
        diffs.append((ep, mine_sec, float(a["duration_s"]), d))
        print(f"{ep:8s} {mine_sec:8.1f}s {float(a['duration_s']):12.2f}s {d:+7.1f}s")
    print(f"  平均差值 {sum(x[3] for x in diffs)/len(diffs):+.1f}s")

    # 写对比清单
    lines = []
    A = lines.append
    A("# 第三周 · 两版配音对比清单（2026-11-15 14:00）")
    A("")
    A("- 用途：xun 试听定版前，逐条比较「好大儿版」与「Antigravity 版」，据此指定装配基线。")
    A("- 对照音频均在 **-16 LUFS 归一化后**生成（消除音量差干扰听感），"
      "拼接顺序为 **先 Antigravity 版 → 2 秒静音 → 好大儿版**。")
    A("- 纯单版文件同目录（`单版_好大儿版_*.mp3` / `单版_Antigravity版_*.mp3`），"
      "已归一化，可单独细听。")
    A("")
    A("## 一、两版参数对照")
    A("")
    A("| 项 | 好大儿版 | Antigravity 版 |")
    A("|---|---|---|")
    A("| 爷爷音色 | Edge-TTS `zh-CN-YunjianNeural` -10%/-8Hz | MiniMax `Chinese (Mandarin)_Male_Announcer` |")
    A("| 奶奶音色 | MiniMax `Chinese (Mandarin)_Kind-hearted_Antie` | MiniMax `Chinese (Mandarin)_Wise_Women` |")
    A("| 逐句裁边 | 有 | 有 |")
    A("| 句间停顿 | 按语气单标注值 | 按语气单标注值 |")
    A("| loudnorm | 未做（干声） | 两遍，全部命中 -16±0.5 |")
    A("| 字幕稿 | 无 | 已出（jieba 断行预处理） |")
    A("| 逐句干声可单独重配 | 有（183 句） | 有 |")
    A("")
    A("## 二、逐条时长对比（全 20 条）")
    A("")
    A("| 条目 | 好大儿版 | Antigravity 版 | 差值 | 好大儿版段数下限 | Antigravity版段数下限 |")
    A("|---|---|---|---|---|---|")
    for ep, ms, ts, d in diffs:
        sm = max(1, -(-int(ms) // 6))
        st = max(1, -(-int(ts) // 6))
        A(f"| {ep} | {ms:.1f}s | {ts:.2f}s | {d:+.1f}s | ≥{sm} 段 | ≥{st} 段 |")
    A("")
    A("> 段数下限＝成片时长÷6 向上取整（整周需求单 2026-11-15 方案 c）。"
      "**选哪版，排镜段数就按哪版算**，两者在多条上段数不同。")
    A("")
    A("## 三、试听对照文件")
    A("")
    for r in rows:
        A(f"- **{r['ep']}**：`{r['ab'].name}`"
          f"（Antigravity {r['theirs_s']:.1f}s → 好大儿 {r['mine_s']:.1f}s）")
    A("")
    A("---")
    A("*由 scripts/make_week3_ab_compare.py 生成。*")

    (OUT / "第三周_两版配音对比清单_20261115.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print()
    print(f"输出目录：{OUT}")
    for p in sorted(OUT.iterdir()):
        print(f"  - {p.name}  ({p.stat().st_size}B)")


if __name__ == "__main__":
    main()
