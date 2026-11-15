#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Week 3 Batch Prep: MiniMax TTS (20 episodes / 183 lines), -16 LUFS voice tracks, and jieba word-safe subtitles."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import jieba

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from assemble_voice_test import get_ffmpeg, probe_duration_ms  # noqa: E402
from voice_api_tts import load_config, synthesize_minimax, throttle  # noqa: E402

FFMPEG = get_ffmpeg()

CLOUD_WEEK = Path(r"G:\我的云端硬盘\JH\视频号第三周")
LOCAL_SRC = ROOT / "config" / "voice_api"


def _resolve_src(filename: str) -> Path:
    """按 环境变量 → 云盘挂载 → 本机 Antigravity scratch 顺序查找依据文件。

    云盘是多机共享的权威副本；scratch 用 Path.home() 推导，不写死本机用户名，
    以免脚本入库后泄露机器身份、也便于换机后直接复用。
    """
    cands = []
    env = os.environ.get("SCYS_WEEK3_SRC")
    if env:
        cands.append(Path(env) / filename)
    for base in (CLOUD_WEEK / "02_音频脚本", CLOUD_WEEK / "01_口播定稿", LOCAL_SRC):
        cands.append(base / filename)
    brain = Path.home() / ".gemini" / "antigravity" / "brain"
    if brain.is_dir():
        for scratch in sorted(brain.glob("*/scratch"),
                              key=lambda p: p.stat().st_mtime, reverse=True):
            cands.append(scratch / filename)
    for c in cands:
        if c.is_file():
            return c
    raise FileNotFoundError(
        f"找不到依据文件：{filename}\n已尝试：\n  " + "\n  ".join(str(c) for c in cands))


TONE_MD = _resolve_src("第三周_配音语气单.md")
FROZEN_MD = _resolve_src("第三周_口播冻结稿.md")
D1_VER_DIR = ROOT / "03_视频成片与工程" / "第三周_D1验证"
OUT_DIR = ROOT / "03_视频成片与工程" / "第三周_批量先行"


def parse_tone_sheet(path: Path) -> list[dict]:
    episodes = []
    cur = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("## "):
            # e.g. ## D1早 11-17 周二 07:00｜管教·对话A
            head = line[3:].strip()
            ep_id = head.split()[0]
            date_part, _, theme = head.partition("｜")
            date_str = date_part[len(ep_id):].strip()
            cur = {"ep_id": ep_id, "date_slot": date_str, "theme": theme.strip(), "lines": []}
            episodes.append(cur)
        elif cur is not None and line.startswith("- A"):
            # - A01｜奶奶（奶奶音色）｜原文：...｜语气：...｜音调：...｜语速：...｜停顿：...｜重音：...｜场景：...
            segs = [s.strip() for s in line[2:].split("｜")]
            lid = segs[0]
            role_raw = segs[1]
            role_key = "grandma" if "奶奶" in role_raw else "grandpa"
            role_name = "奶奶" if role_key == "grandma" else "爷爷"
            text = ""
            speed_desc = ""
            pitch_desc = ""
            pause_desc = ""
            for s in segs[2:]:
                if s.startswith("原文："):
                    text = s[3:].strip()
                elif s.startswith("语速："):
                    speed_desc = s[3:].strip()
                elif s.startswith("音调："):
                    pitch_desc = s[3:].strip()
                elif s.startswith("停顿："):
                    pause_desc = s[3:].strip()
            # Parse pause_after_ms
            pause_ms = 400
            m = re.search(r"(?:句后|句末|末尾)[^0-9]*([0-9]+(?:\.[0-9]+)?)\s*秒", pause_desc)
            if m:
                pause_ms = round(float(m.group(1)) * 1000)
            else:
                m2 = re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*秒", pause_desc)
                if m2:
                    pause_ms = round(float(m2[-1]) * 1000)
            pause_ms = max(250, min(800, pause_ms))

            # Speed & pitch delta
            sdelta = 0.0
            if "偏慢" in speed_desc or "中慢" in speed_desc:
                sdelta = -0.02
            elif speed_desc.startswith("慢"):
                sdelta = -0.05
            elif "偏快" in speed_desc:
                sdelta = 0.02

            pdelta = 0
            if "上扬" in pitch_desc and "下沉" not in pitch_desc:
                pdelta = 1
            elif "下沉" in pitch_desc and "上扬" not in pitch_desc:
                pdelta = -1

            cur["lines"].append({
                "id": lid,
                "role_key": role_key,
                "role_name": role_name,
                "text": text,
                "pause_after_ms": pause_ms,
                "speed_delta": sdelta,
                "pitch_delta": pdelta,
            })
    return episodes


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


def make_silence(dur_ms: int, dst: Path) -> None:
    cmd = [
        FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-t", f"{dur_ms / 1000.0:.3f}", "-c:a", "pcm_s16le", str(dst),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def loudnorm_and_measure(src_wav: Path, dst_wav: Path) -> tuple[str, str]:
    p1 = subprocess.run(
        [FFMPEG, "-y", "-i", str(src_wav), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "NUL"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p1.stderr, re.S)
    stats = json.loads(m.group(0)) if m else {}
    if stats:
        af2 = (
            f"loudnorm=I=-16:TP=-1.5:LRA=11:linear=true:"
            f"measured_I={stats['input_i']}:measured_TP={stats['input_tp']}:"
            f"measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}:"
            f"offset={stats['target_offset']}"
        )
    else:
        af2 = "loudnorm=I=-16:TP=-1.5:LRA=11"
    subprocess.run(
        [FFMPEG, "-y", "-i", str(src_wav), "-af", af2, "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", str(dst_wav)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    p2 = subprocess.run(
        [FFMPEG, "-y", "-i", str(dst_wav), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "NUL"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    m2 = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p2.stderr, re.S)
    final_stats = json.loads(m2.group(0)) if m2 else {}
    return str(final_stats.get("input_i", "N/A")), str(final_stats.get("input_tp", "N/A"))


PUNCT_ONLY_RE = re.compile(r"^[，。；：？！、—…“”‘’（）《》,.!?;:\-]+$")
SUBTITLE_OVERRIDES = {
    "您见过轻轨从居民楼里穿过去的吗？": ["您见过轻轨", "从居民楼里穿过去的吗？"],
}


def _merge_punct_tokens(words: list[str]) -> list[str]:
    """Attach punctuation tokens to the preceding word so punctuation never starts or forms a solo screen."""
    merged: list[str] = []
    for w in words:
        if not w:
            continue
        if merged and PUNCT_ONLY_RE.match(w):
            merged[-1] += w
        else:
            merged.append(w)
    return merged


def split_semantic_lines(text: str, max_chars: int = 14) -> list[str]:
    """Word-boundary-safe split using jieba, keeping punctuation & '——'/'—' attached and <= max_chars."""
    if text in SUBTITLE_OVERRIDES:
        return list(SUBTITLE_OVERRIDES[text])
    parts = re.split(r"(?<=[，。；：？！、])|(?<=——)|(?<!—)(?<=—)(?!—)", text)
    parts = [p for p in parts if p]
    chunks: list[str] = []
    buf = ""
    for p in parts:
        if PUNCT_ONLY_RE.match(p) and buf:
            if len(buf) + len(p) <= max_chars:
                buf += p
                continue
        if len(buf) + len(p) <= max_chars:
            buf += p
        else:
            if buf:
                chunks.append(buf)
                buf = ""
            if len(p) <= max_chars:
                buf = p
            else:
                words = _merge_punct_tokens(jieba.lcut(p))
                cur = ""
                for w in words:
                    if cur and len(cur) + len(w) > max_chars:
                        chunks.append(cur)
                        cur = w
                    else:
                        cur += w
                if cur:
                    chunks.append(cur)
    if buf:
        chunks.append(buf)
    if len(chunks) >= 2 and (len(chunks[-1]) <= 3 or PUNCT_ONLY_RE.match(chunks[-1][0])):
        if len(chunks[-2]) + len(chunks[-1]) <= max_chars:
            chunks[-2] += chunks[-1]
            chunks.pop()
        else:
            # Rebalance last two chunks at word boundary (punctuation attached)
            combined = chunks[-2] + chunks[-1]
            words = _merge_punct_tokens(jieba.lcut(combined))
            half = len(combined) // 2
            best = None
            for i in range(1, len(words)):
                l_cand = "".join(words[:i])
                r_cand = "".join(words[i:])
                if len(l_cand) <= max_chars and len(r_cand) <= max_chars:
                    best = (l_cand, r_cand)
                    if len(l_cand) >= half:
                        break
            if best:
                chunks[-2], chunks[-1] = best
    return chunks


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg = load_config(ROOT / "config" / "voice_api" / "config.yaml")
    cfg["request_interval_seconds"] = 3.2
    roles = cfg["roles"]
    episodes = parse_tone_sheet(TONE_MD)
    total_sentences = sum(len(ep["lines"]) for ep in episodes)
    print(f"Parsed {len(episodes)} episodes, {total_sentences} sentences.")

    all_summary = []
    sub_md_lines = [
        "# 第三周 · 字幕稿先行（批量 20 条）",
        "",
        "- 依据：`视频号第三周 / 01_口播定稿 / 第三周_口播冻结稿.md` 与 `02_音频脚本 / 第三周_配音语气单.md`",
        "- 规范：逐句严格一字不改；使用 `jieba` 词边界保护 + 意群二次断行（单屏 ≤ 14 字，词与专名/数字绝不拆屏）。",
        "",
    ]

    for ep in episodes:
        ep_id = ep["ep_id"]
        ep_audio_dir = OUT_DIR / ep_id / "audio"
        ep_audio_dir.mkdir(parents=True, exist_ok=True)

        # Reuse D1 verified audio if present
        d1_src = D1_VER_DIR / ep_id / "audio"
        if ep_id in ("D1早", "D1午", "D1晚") and (d1_src / "full_voice.wav").exists():
            for f in d1_src.iterdir():
                if f.is_file():
                    shutil.copy2(f, ep_audio_dir / f.name)
            meta = json.loads((ep_audio_dir / "tts_meta.json").read_text(encoding="utf-8"))
            voice_16 = ep_audio_dir / "voice_16lufs.wav"
            lufs, tp = loudnorm_and_measure(ep_audio_dir / "full_voice.wav", voice_16)
            re_dub_count = 1 if ep_id == "D1早" else 0
            print(f"[REUSED {ep_id}] {meta['total_ms']/1000:.2f}s | lines={len(meta['lines'])} | LUFS={lufs} | TP={tp}")
        else:
            meta_lines = []
            concat_list = []
            cursor_ms = 0
            for item in ep["lines"]:
                lid = item["id"]
                r = roles[item["role_key"]]
                raw_mp3 = ep_audio_dir / f"{lid}_raw.mp3"
                trim_wav = ep_audio_dir / f"{lid}.wav"
                sil_wav = ep_audio_dir / f"{lid}_sil.wav"
                line_cfg = {
                    "voice_id": r["voice_id"],
                    "speed": round(float(r.get("speed", 0.95)) + item["speed_delta"], 2),
                    "pitch": int(r.get("pitch", -1)) + item["pitch_delta"],
                    "vol": float(r.get("vol", 1.0)),
                    "text": item["text"],
                    "model": cfg.get("model", "speech-2.8-hd"),
                }
                if not raw_mp3.exists() or raw_mp3.stat().st_size == 0:
                    throttle(cfg)
                    res = synthesize_minimax(cfg, line_cfg, raw_mp3)
                    trace_id = res.get("trace_id", "")
                else:
                    trace_id = "cached"
                if not trim_wav.exists():
                    trim_silence(raw_mp3, trim_wav)
                dur_ms = probe_duration_ms(FFMPEG, trim_wav)
                if not sil_wav.exists():
                    make_silence(item["pause_after_ms"], sil_wav)
                start_ms = cursor_ms
                end_ms = start_ms + dur_ms
                cursor_ms = end_ms + item["pause_after_ms"]
                concat_list.extend([trim_wav, sil_wav])
                meta_lines.append({
                    "id": lid,
                    "role": item["role_name"],
                    "voice_id": r["voice_id"],
                    "text": item["text"],
                    "chars": len(item["text"]),
                    "speech_ms": dur_ms,
                    "pause_after_ms": item["pause_after_ms"],
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "trace_id": trace_id,
                })
                print(f"[{ep_id}] {lid} ({item['role_name']}): {dur_ms}ms + {item['pause_after_ms']}ms | trace={trace_id}")

            list_txt = ep_audio_dir / "concat.txt"
            list_txt.write_text("\n".join(f"file '{p.as_posix()}'" for p in concat_list), encoding="utf-8")
            full_wav = ep_audio_dir / "full_voice.wav"
            subprocess.run(
                [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(list_txt), "-c:a", "pcm_s16le", str(full_wav)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            total_ms = probe_duration_ms(FFMPEG, full_wav)
            voice_16 = ep_audio_dir / "voice_16lufs.wav"
            lufs, tp = loudnorm_and_measure(full_wav, voice_16)
            meta = {"total_ms": total_ms, "total_chars": sum(x["chars"] for x in meta_lines), "lines": meta_lines}
            (ep_audio_dir / "tts_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            re_dub_count = 0
            print(f"==> [{ep_id}] {total_ms/1000:.2f}s | LUFS={lufs} | TP={tp}")

        # Generate word-safe subtitles for this episode
        sub_md_lines.append(f"## {ep_id} {ep['date_slot']}｜{ep['theme']}")
        ep_subs = []
        screen_idx = 1
        for l in meta["lines"]:
            chunks = split_semantic_lines(l["text"], max_chars=14)
            for ch in chunks:
                ep_subs.append({"screen": screen_idx, "line_id": l["id"], "role": l["role"], "text": ch, "chars": len(ch)})
                sub_md_lines.append(f"- P{screen_idx:02d}｜{l['id']}（{l['role']}）：`{ch}`（{len(ch)}字）")
                screen_idx += 1
        sub_md_lines.append("")
        (OUT_DIR / ep_id / "subtitles_prep.json").write_text(json.dumps(ep_subs, ensure_ascii=False, indent=2), encoding="utf-8")

        all_summary.append({
            "ep_id": ep_id,
            "date_slot": ep["date_slot"],
            "theme": ep["theme"],
            "duration_s": round(meta["total_ms"] / 1000.0, 3),
            "line_count": len(meta["lines"]),
            "screen_count": len(ep_subs),
            "re_dub_count": re_dub_count,
            "lufs": lufs,
            "tp": tp,
            "local_dir": str(OUT_DIR / ep_id),
        })

    (OUT_DIR / "第三周_字幕稿先行_批量20条.md").write_text("\n".join(sub_md_lines), encoding="utf-8")
    (OUT_DIR / "week3_prep_summary.json").write_text(json.dumps(all_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"ALL DONE: {len(all_summary)} episodes prepared.")


if __name__ == "__main__":
    main()
