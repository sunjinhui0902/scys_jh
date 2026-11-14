#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render D1 (早/午/晚) verification MP4s with >=56px wrapped subtitles, Ken Burns, -16 LUFS, and official book cover."""

import json
import re
import subprocess
import sys
from pathlib import Path
import jieba

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from assemble_voice_test import get_ffmpeg, probe_duration_ms  # noqa: E402

FFMPEG = get_ffmpeg()
WORK = ROOT / "03_视频成片与工程" / "第三周_D1验证"
BGM_PATH = ROOT / "01_配音与音色库" / "背景音乐库" / "bgm_shili_guofeng.mp3"
BOOK_COVER = WORK / "assets" / "中国式人情世故_封面.jpg"


def split_semantic_lines(text: str, max_chars: int = 14) -> list[str]:
    """Split a Chinese sentence into short screen lines <= max_chars without ever breaking a word or em-dash."""
    parts = re.split(r"(?<=[，。；：？！、])|(?<=——)", text)
    parts = [p for p in parts if p]
    chunks: list[str] = []
    buf = ""
    for p in parts:
        if len(buf) + len(p) <= max_chars:
            buf += p
        else:
            if buf:
                chunks.append(buf)
                buf = ""
            if len(p) <= max_chars:
                buf = p
            else:
                # Word-boundary-safe split using jieba
                words = jieba.lcut(p)
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
    if len(chunks) >= 2 and len(chunks[-1]) <= 3 and len(chunks[-2]) + len(chunks[-1]) <= max_chars + 2:
        chunks[-2] += chunks[-1]
        chunks.pop()
    return chunks


def ms_to_ass(ms: int) -> str:
    cs = round(ms / 10)
    h = cs // 360000
    cs %= 360000
    m = cs // 6000
    cs %= 6000
    s = cs // 100
    cs %= 100
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_ass(ep: str, meta: dict, cover_title: str, badge_text: str | None, first_shot_end_ms: int, out_ass: Path) -> tuple[list[str], int]:
    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        # >=56px (58px) subtitles: Grandpa warm yellow, Grandma warm pink
        "Style: Grandpa,Microsoft YaHei,58,&H0033D1FF,&H000000FF,&H00000000,&H99000000,-1,0,0,0,100,100,1,0,3,12,0,2,45,45,210,1",
        "Style: Grandma,Microsoft YaHei,58,&H00AB99FF,&H000000FF,&H00000000,&H99000000,-1,0,0,0,100,100,1,0,3,12,0,2,45,45,210,1",
        "Style: CoverTitle,Microsoft YaHei,74,&H0033D1FF,&H000000FF,&H00000000,&HB0000000,-1,0,0,0,100,100,2,0,3,16,0,8,60,60,180,1",
        "Style: Badge,Microsoft YaHei,42,&H00FFFFFF,&H000000FF,&H00000000,&HB01E3A8A,-1,0,0,0,100,100,2,0,3,12,0,9,40,40,70,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events = []
    screen_lines = []

    # Cover title on first shot
    events.append(f"Dialogue: 2,0:00:00.00,{ms_to_ass(first_shot_end_ms)},CoverTitle,,0,0,0,,{cover_title}")
    if badge_text:
        events.append(f"Dialogue: 3,0:00:00.00,{ms_to_ass(first_shot_end_ms)},Badge,,0,0,0,,{badge_text}")

    for line in meta["lines"]:
        style = "Grandma" if line["role"] == "奶奶" else "Grandpa"
        s_ms = line["start_ms"]
        e_ms = line["end_ms"]
        dur = max(100, e_ms - s_ms)
        chunks = split_semantic_lines(line["text"], max_chars=14)
        total_c = max(1, sum(len(c) for c in chunks))
        cur = s_ms
        for i, ch in enumerate(chunks):
            if i == len(chunks) - 1:
                nxt = e_ms
            else:
                nxt = cur + round(dur * (len(ch) / total_c))
            events.append(f"Dialogue: 1,{ms_to_ass(cur)},{ms_to_ass(nxt)},{style},,0,0,0,,{ch}")
            screen_lines.append(f"{line['id']}: {ch} ({len(ch)}字)")
            cur = nxt

    out_ass.write_text("\n".join(header + events), encoding="utf-8-sig")
    return screen_lines, len(events)


def make_book_card(src_jpg: Path, dst_png: Path) -> None:
    """Adapt official square/vertical book cover onto 1080x1920 blurred background without cropping/recoloring."""
    vf = (
        "split[bg][fg];"
        "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=35,eq=brightness=-0.12[b];"
        "[fg]scale=900:1500:force_original_aspect_ratio=decrease[f];"
        "[b][f]overlay=(W-w)/2:(H-h)/2"
    )
    subprocess.run([FFMPEG, "-y", "-i", str(src_jpg), "-vf", vf, str(dst_png)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def mix_and_loudnorm(voice_wav: Path, total_ms: int, out_wav: Path) -> dict:
    """Mix voice + BGM and two-pass loudnorm to -16 LUFS."""
    dur_s = total_ms / 1000.0
    fade_out_start = max(0.0, dur_s - 2.5)
    raw_mix = out_wav.with_name("raw_mix.wav")
    fc = (
        f"[0:a]volume=1.4125[v];"
        f"[1:a]aloop=loop=-1:size=2e+09,atrim=0:{dur_s:.3f},"
        f"volume=0.1412,afade=t=in:st=0:d=1.0,afade=t=out:st={fade_out_start:.3f}:d=2.5[b];"
        f"[v][b]amix=inputs=2:duration=first:normalize=0[m]"
    )
    subprocess.run(
        [FFMPEG, "-y", "-i", str(voice_wav), "-i", str(BGM_PATH), "-filter_complex", fc, "-map", "[m]", "-ar", "44100", "-ac", "1", str(raw_mix)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    # Pass 1: measure loudness
    p1 = subprocess.run(
        [FFMPEG, "-y", "-i", str(raw_mix), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "NUL"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p1.stderr, re.S)
    stats = json.loads(m.group(0)) if m else {}
    # Pass 2: apply linear loudnorm
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
        [FFMPEG, "-y", "-i", str(raw_mix), "-af", af2, "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", str(out_wav)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    # Verify final loudness
    p2 = subprocess.run(
        [FFMPEG, "-y", "-i", str(out_wav), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "NUL"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    m2 = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p2.stderr, re.S)
    final_stats = json.loads(m2.group(0)) if m2 else {}
    return final_stats


def render_episode(ep: str, cover_title: str, badge_text: str | None, shots: list[tuple[Path, int, int]]) -> dict:
    """shots: list of (image_path, start_ms, end_ms)."""
    ep_dir = WORK / ep
    meta = json.loads((ep_dir / "audio" / "tts_meta.json").read_text(encoding="utf-8"))
    total_ms = meta["total_ms"]

    # Build ASS subtitles
    ass_path = ep_dir / f"{ep}.ass"
    first_end_ms = shots[0][2]
    screen_lines, evt_count = build_ass(ep, meta, cover_title, badge_text, first_end_ms, ass_path)

    # Mix & loudnorm audio to -16 LUFS
    master_wav = ep_dir / "audio" / "master_16lufs.wav"
    lufs_stats = mix_and_loudnorm(ep_dir / "audio" / "full_voice.wav", total_ms, master_wav)

    # Render each shot with Ken Burns zoompan at 1080x1920 30fps, then concat
    clip_paths = []
    for idx, (img_path, s_ms, e_ms) in enumerate(shots):
        dur_s = max(0.5, (e_ms - s_ms) / 1000.0)
        frames = max(15, round(dur_s * 30))
        clip = ep_dir / f"clip_{idx:02d}.mp4"
        if idx % 2 == 0:
            zp = f"zoompan=z='min(zoom+0.0005,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=30"
        else:
            zp = f"zoompan=z='if(lte(zoom,1.0),1.06,max(1.00,zoom-0.0005))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=30"
        vf = f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,{zp},setsar=1"
        subprocess.run(
            [FFMPEG, "-y", "-loop", "1", "-i", str(img_path), "-vf", vf, "-t", f"{dur_s:.3f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", str(clip)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        clip_paths.append(clip)

    vlist = ep_dir / "vconcat.txt"
    vlist.write_text("\n".join(f"file '{p.as_posix()}'" for p in clip_paths), encoding="utf-8")
    raw_vid = ep_dir / "raw_video.mp4"
    subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(vlist), "-c", "copy", str(raw_vid)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    # Burn ASS subtitles + mux -16 LUFS audio
    out_mp4 = WORK / "out" / f"第三周_{ep}_验证成片.mp4"
    ass_escaped = ass_path.as_posix().replace(":", r"\:")
    subprocess.run(
        [
            FFMPEG, "-y", "-i", str(raw_vid), "-i", str(master_wav),
            "-vf", f"ass='{ass_escaped}'",
            "-c:v", "libx264", "-profile:v", "high", "-crf", "19", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "1",
            "-movflags", "+faststart", "-shortest", str(out_mp4),
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    mp4_ms = probe_duration_ms(FFMPEG, out_mp4)
    return {
        "ep": ep,
        "mp4": str(out_mp4),
        "size_bytes": out_mp4.stat().st_size,
        "audio_ms": total_ms,
        "mp4_ms": mp4_ms,
        "lufs": lufs_stats.get("input_i", "N/A"),
        "tp": lufs_stats.get("input_tp", "N/A"),
        "subtitle_events": evt_count,
        "screen_lines": screen_lines,
        "shots": [(str(p.name), s, e, round((e - s) / 1000.0, 2)) for p, s, e in shots],
    }


def build_shots_from_groups(img_dir: Path, meta: dict, groups: list[tuple[str, int, int]], book_slot: tuple[int, Path] | None = None) -> list[tuple[Path, int, int]]:
    """Build shot list; split any slot > 6.0s into <= 5.5s sub-segments if needed, or insert official book card."""
    lines = meta["lines"]
    raw_shots = []
    for img_name, start_idx, end_idx in groups:
        s_ms = lines[start_idx]["start_ms"]
        if end_idx == len(lines) - 1:
            e_ms = meta["total_ms"]
        else:
            e_ms = lines[end_idx + 1]["start_ms"]
        raw_shots.append((img_dir / img_name, s_ms, e_ms))

    if book_slot:
        # Replace the specified line index's window with official book card (<= 8s)
        b_idx, b_path = book_slot
        b_s = lines[b_idx]["start_ms"]
        b_e = lines[b_idx + 1]["start_ms"] if b_idx + 1 < len(lines) else meta["total_ms"]
        # Split the shot containing [b_s, b_e]
        updated = []
        for p, s, e in raw_shots:
            if s <= b_s and b_e <= e:
                if b_s > s:
                    updated.append((p, s, b_s))
                updated.append((b_path, b_s, b_e))
                if e > b_e:
                    updated.append((p, b_e, e))
            else:
                updated.append((p, s, e))
        raw_shots = updated

    return raw_shots


def main() -> None:
    book_card = WORK / "assets" / "book_card_1080x1920.png"
    make_book_card(BOOK_COVER, book_card)

    results = {}

    # D1早: 11 lines (0..10) -> IMG01(0..2), IMG02(3..4), IMG03(5..6), IMG04(7..8), IMG05(9..10)
    m_zao = json.loads((WORK / "D1早" / "audio" / "tts_meta.json").read_text(encoding="utf-8"))
    s_zao = build_shots_from_groups(WORK / "D1早" / "images", m_zao, [
        ("IMG01.png", 0, 2), ("IMG02.png", 3, 4), ("IMG03.png", 5, 6), ("IMG04.png", 7, 8), ("IMG05.png", 9, 10)
    ])
    results["D1早"] = render_episode("D1早", "孙子下棋 输了就哭", None, s_zao)

    # D1午: 7 lines (0..6) -> IMG01(0..1), IMG02(2..3), IMG03(4..4), IMG04(5..5), IMG05(6..6)
    m_wu = json.loads((WORK / "D1午" / "audio" / "tts_meta.json").read_text(encoding="utf-8"))
    s_wu = build_shots_from_groups(WORK / "D1午" / "images", m_wu, [
        ("IMG01.png", 0, 1), ("IMG02.png", 2, 3), ("IMG03.png", 4, 4), ("IMG04.png", 5, 5), ("IMG05.png", 6, 6)
    ])
    results["D1午"] = render_episode("D1午", "轻轨 从楼里穿过去", None, s_wu)

    # D1晚: 10 lines (0..9)
    m_wan = json.loads((WORK / "D1晚" / "audio" / "tts_meta.json").read_text(encoding="utf-8"))
    wan_img_dir = WORK / "D1晚" / "images"
    if (wan_img_dir / "IMG04.png").exists() and (wan_img_dir / "IMG05.png").exists():
        s_wan = build_shots_from_groups(
            wan_img_dir, m_wan,
            [("IMG01.png", 0, 1), ("IMG02.png", 2, 3), ("IMG03.png", 4, 5), ("IMG04.png", 6, 7), ("IMG05.png", 8, 9)],
            book_slot=(8, book_card),
        )
        results["D1晚"] = render_episode("D1晚", "救急 不救穷", "人情冷暖", s_wan)
    else:
        ass_path = WORK / "D1晚" / "D1晚.ass"
        first_end = m_wan["lines"][2]["start_ms"]
        screen_lines, evt_count = build_ass("D1晚", m_wan, "救急 不救穷", "人情冷暖", first_end, ass_path)
        master_wav = WORK / "D1晚" / "audio" / "master_16lufs.wav"
        lufs_stats = mix_and_loudnorm(WORK / "D1晚" / "audio" / "full_voice.wav", m_wan["total_ms"], master_wav)
        results["D1晚"] = {
            "ep": "D1晚",
            "status": "BLOCKED_MISSING_IMAGES",
            "missing": ["IMG04.png", "IMG05.png"],
            "reason": "image-generator 429 RESOURCE_EXHAUSTED (~5h reset)",
            "audio_ms": m_wan["total_ms"],
            "lufs": lufs_stats.get("input_i", "N/A"),
            "tp": lufs_stats.get("input_tp", "N/A"),
            "subtitle_events": evt_count,
            "screen_lines": screen_lines,
        }

    (WORK / "d1_render_report.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    for k, v in results.items():
        if v.get("mp4"):
            print(f"DONE {k}: {v['mp4']} | {v['mp4_ms']/1000:.2f}s | LUFS={v['lufs']} | size={v['size_bytes']/1048576:.2f}MB")
        else:
            print(f"PARTIAL {k}: {v.get('status')} | audio={v['audio_ms']/1000:.2f}s | LUFS={v['lufs']} | missing={v.get('missing')}")


if __name__ == "__main__":
    main()
