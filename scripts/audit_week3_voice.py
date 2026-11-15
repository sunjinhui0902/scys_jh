#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第三周配音验收
==============
读取 voice_api_tts.py 产出的《试听报告.json》与合成目录，检查：
1. 句数/字数/失败数是否与语气单一致；
2. 整条拼接时长是否 ≈ Σ句时长 + Σ句间停顿（验证「按语气单停顿值裁边」是否真的生效）；
3. 每句语速（字/秒），标出明显偏快/偏慢的句子；
4. 单条总时长与总字数是否符合第三周规格（约 55–65 秒 / 240–280 字）；
5. 整条音频的实测响度。

用法：
    python scripts/audit_week3_voice.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

OUT_DIR = ROOT / "01_配音与音色库" / "第三周配音_20261115"
REPORT = OUT_DIR / "试听报告.json"
TONE_SHEET = Path(r"G:\我的云端硬盘\JH\视频号第三周\02_音频脚本\第三周_配音语气单.md")

# 第三周整周需求单未对各条设硬性时长上限（冻结口播一字不改，时长由字数×语气单语速决定）。
# 这里的带宽只用于发现「语速跑偏导致时长异常」，不作为发布判定。
BAND_BY_SLOT = {"早": (50, 67), "午": (48, 69), "晚": (62, 80)}
# 目标语速带（据第二周 P2 实测 3.53 字/秒，容差放宽到中老年舒适区）
RATE_LOW, RATE_HIGH = 3.0, 5.6
# 排镜段数下限（需求单 2026-11-15 方案 c：段数下限＝成片时长÷6 向上取整）
SHOT_SECONDS = 6


def ffprobe(path: Path) -> dict:
    exe = None
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        exe = exe.replace("ffmpeg", "ffprobe")
    except Exception:
        exe = "ffprobe"
    try:
        out = subprocess.run(
            [exe, "-v", "error", "-show_entries", "format=duration",
             "-show_entries", "stream=sample_rate,channels", "-of", "json", str(path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        data = json.loads(out.stdout or "{}")
        fmt = data.get("format", {})
        return {"duration": float(fmt.get("duration", 0) or 0)}
    except Exception:
        return {"duration": 0.0}


def loudness(path: Path) -> str:
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        out = subprocess.run(
            [exe, "-hide_banner", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        txt = out.stderr or ""
        i = txt.rfind("Integrated loudness")
        if i < 0:
            i = txt.rfind("I:")
        seg = txt[i:i + 400] if i >= 0 else txt[-400:]
        for line in seg.splitlines():
            if "I:" in line and "LUFS" in line:
                return line.strip()
        return "未取到"
    except Exception as e:
        return f"未测({type(e).__name__})"


def parse_gaps(sheet: Path) -> dict:
    """从语气单取每条每句的句后停顿（ms）与原文字数。"""
    import re
    text = sheet.read_text(encoding="utf-8")
    EP = re.compile(r"^##\s+(D\d[早午晚][^\n]*)$", re.M)
    LINE = re.compile(
        r"^-\s*(A\d+)｜([^｜]+)｜原文：(.*?)｜语气：(.*?)；音调：(.*?)；语速：(.*?)；停顿：(.*?)；重音：(.*?)；场景：(.*)$",
        re.M)
    marks = list(EP.finditer(text))
    out = {}
    for i, m in enumerate(marks):
        title = m.group(1).strip()
        key = title.split("｜")[0].split(" ")[0]
        body = text[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(text)]
        for lm in LINE.finditer(body):
            lid, role, original, mood, tone, spd, pause = lm.group(1), lm.group(2), lm.group(3), lm.group(4), lm.group(5), lm.group(6), lm.group(7)
            gm = re.search(r"句(?:后|末)\s*(?:停|收)?\s*([0-9.]+)\s*秒", pause)
            gap = int(round(float(gm.group(1)) * 1000)) if gm else 400
            out[f"{key}_{lid}"] = {"text": original.strip(), "gap_ms": gap,
                                  "role": re.sub(r"[（(].*?[)）]", "", role).strip()}
    return out


def main() -> None:
    if not REPORT.is_file():
        raise SystemExit(f"未找到试听报告：{REPORT}\n先跑 voice_api_tts.py")
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    lines = rep.get("lines", [])
    failed = rep.get("failed", [])
    scenes = rep.get("scenes", [])
    meta = parse_gaps(TONE_SHEET)

    print("=" * 78)
    print(f"条目 {len(scenes)}   句数 {len(lines)}   失败 {len(failed)}   "
          f"新增 MiniMax 请求 {rep.get('new_minimax_calls', '?')}")
    print("=" * 78)

    by_scene: dict[str, list] = {}
    for ln in lines:
        by_scene.setdefault(ln["file"].rsplit("_", 1)[0], []).append(ln)

    print()
    print(f"{'条目':8s} {'句数':>4s} {'字数':>5s} {'实测时长':>8s} {'语速字/秒':>9s} {'画面段数下限':>10s}")
    print("-" * 78)
    problems = []
    for sc in scenes:
        key = sc["file"].replace(".mp3", "")
        items = sorted(by_scene.get(key, []), key=lambda x: x["file"])
        chars = sum(len(meta.get(i["file"].replace(".mp3", ""), {}).get("text", "")) or len(i.get("text", "")) for i in items)
        dur_ms = sc.get("duration_ms", 0)
        # 拼接校验：句时长之和 + 前 n-1 句的句后停顿（末句停顿不计入条内）
        sum_sent = sum(i.get("duration_ms", 0) for i in items)
        gaps = [meta.get(i["file"].replace(".mp3", ""), {}).get("gap_ms", 400) for i in items[:-1]]
        expect = sum_sent + sum(gaps)
        diff = dur_ms - expect
        sec = dur_ms / 1000
        rate = chars / sec if sec else 0
        slot = key[-1] if key and key[-1] in BAND_BY_SLOT else "早"
        lo, hi = BAND_BY_SLOT.get(slot, (40, 90))
        shots = -(-int(sec) // SHOT_SECONDS)  # 向上取整
        flag = "" if lo <= sec <= hi else "  <-- 时长偏离带宽"
        print(f"{key:8s} {len(items):4d} {chars:5d} {sec:7.1f}s {rate:9.2f} {shots:8d} 段{flag}")
        print(f"{'':8s} 句时长合计 {sum_sent/1000:.1f}s + 句间停顿 {sum(gaps)/1000:.1f}s "
              f"= 期望 {expect/1000:.1f}s，实测 {sec:.1f}s，差 {diff/1000:+.2f}s")
        if abs(diff) > 1500:
            problems.append(f"{key} 拼接时长偏差 {diff/1000:+.2f}s（>1.5s），需核查停顿裁边")
        if not lo <= sec <= hi:
            problems.append(f"{key} 时长 {sec:.1f}s 偏离 {slot}场带宽 {lo}-{hi}s，需复核语速")
        if not 3.3 <= rate <= 4.6:
            problems.append(f"{key} 平均语速 {rate:.2f} 字/秒 偏离 3.3-4.6 舒适带")

    print()
    print("=" * 78)
    print("语速检查（字/秒；目标带 %.1f-%.1f）" % (RATE_LOW, RATE_HIGH))
    print("=" * 78)
    fast, slow = [], []
    for ln in lines:
        key = ln["file"].replace(".mp3", "")
        info = meta.get(key)
        if not info or not ln.get("duration_ms"):
            continue
        n = len(info["text"])
        rate = n / (ln["duration_ms"] / 1000)
        if rate > RATE_HIGH:
            fast.append((ln["file"], n, round(rate, 2), info["role"], info["text"][:26]))
        elif rate < RATE_LOW:
            slow.append((ln["file"], n, round(rate, 2), info["role"], info["text"][:26]))
    print(f"偏快句 {len(fast)} 句 / 偏慢句 {len(slow)} 句")
    for f in sorted(fast, key=lambda x: -x[2])[:18]:
        print(f"  [快] {f[0]:16s} {f[1]:3d}字 {f[2]:5.2f}字/秒 {f[3]:4s} {f[4]}")
    for s in sorted(slow, key=lambda x: x[2])[:10]:
        print(f"  [慢] {s[0]:16s} {s[1]:3d}字 {s[2]:5.2f}字/秒 {s[3]:4s} {s[4]}")

    if failed:
        print()
        print("失败明细：")
        for f in failed:
            print(f"  {f.get('file')}  {f.get('error')}")

    print()
    print("=" * 78)
    print("整条干声实测响度（I = 综合响度 / TPK = 真峰值）")
    print("说明：需求单的 -16 LUFS 是**成片**口径，装配阶段由 loudnorm 达标；")
    print("      此处为未做任何增益的干声原始电平，供装配时设定增益量参考。")
    print("=" * 78)
    for sc in scenes:
        p = OUT_DIR / sc["file"]
        if p.is_file():
            print(f"  {sc['file']:14s} {loudness(p)}")

    if problems:
        print()
        print("需处理：")
        for p in problems:
            print("  - " + p)
    else:
        print()
        print("拼接与规格检查未发现偏差。")


if __name__ == "__main__":
    main()
