#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render final D1早 and D1晚 MP4s using MiniMax -16 LUFS audio, fixed subtitles, and full D1 images."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "03_视频成片与工程" / "第三周_D1验证"))
sys.path.insert(0, str(ROOT / "scripts"))

from assemble_voice_test import get_ffmpeg, probe_duration_ms  # noqa: E402
from render_d1_videos import mix_and_loudnorm, ms_to_ass, make_book_card, BOOK_COVER  # noqa: E402

FFMPEG = get_ffmpeg()
PREP_DIR = ROOT / "03_视频成片与工程" / "第三周_批量先行"
VER_DIR = ROOT / "03_视频成片与工程" / "第三周_D1验证"
NEW_IMG_DIR = PREP_DIR / "D1_生图测试"
OUT_DIR = PREP_DIR / "out"


def build_ass_from_prep(meta: dict, subs_prep: list[dict], cover_title: str, badge_text: str | None, first_shot_end_ms: int, out_ass: Path) -> int:
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
        "Style: Grandpa,Microsoft YaHei,58,&H0033D1FF,&H000000FF,&H00000000,&H99000000,-1,0,0,0,100,100,1,0,3,12,0,2,45,45,210,1",
        "Style: Grandma,Microsoft YaHei,58,&H00AB99FF,&H000000FF,&H00000000,&H99000000,-1,0,0,0,100,100,1,0,3,12,0,2,45,45,210,1",
        "Style: CoverTitle,Microsoft YaHei,74,&H0033D1FF,&H000000FF,&H00000000,&HB0000000,-1,0,0,0,100,100,2,0,3,16,0,8,60,60,180,1",
        "Style: Badge,Microsoft YaHei,42,&H00FFFFFF,&H000000FF,&H00000000,&HB01E3A8A,-1,0,0,0,100,100,2,0,3,12,0,9,40,40,70,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events = [f"Dialogue: 2,0:00:00.00,{ms_to_ass(first_shot_end_ms)},CoverTitle,,0,0,0,,{cover_title}"]
    if badge_text:
        events.append(f"Dialogue: 3,0:00:00.00,{ms_to_ass(first_shot_end_ms)},Badge,,0,0,0,,{badge_text}")

    line_map = {l["id"]: l for l in meta["lines"]}
    by_line: dict[str, list[dict]] = {}
    for s in subs_prep:
        by_line.setdefault(s["line_id"], []).append(s)

    for lid, chunks in by_line.items():
        l = line_map[lid]
        style = "Grandma" if l["role"] == "奶奶" else "Grandpa"
        s_ms, e_ms = l["start_ms"], l["end_ms"]
        dur = max(100, e_ms - s_ms)
        total_c = max(1, sum(c["chars"] for c in chunks))
        cur = s_ms
        for i, ch in enumerate(chunks):
            nxt = e_ms if i == len(chunks) - 1 else cur + round(dur * (ch["chars"] / total_c))
            events.append(f"Dialogue: 1,{ms_to_ass(cur)},{ms_to_ass(nxt)},{style},,0,0,0,,{ch['text']}")
            cur = nxt

    out_ass.write_text("\n".join(header + events), encoding="utf-8-sig")
    return len(events)


def split_window(imgs: list[Path], s_ms: int, e_ms: int, max_ms: int = 5800) -> list[tuple[Path, int, int, bool]]:
    dur = e_ms - s_ms
    n = max(len(imgs), (dur + max_ms - 1) // max_ms)
    step = dur // n
    out = []
    cur = s_ms
    for i in range(n):
        nxt = e_ms if i == n - 1 else cur + step
        out.append((imgs[i % len(imgs)], cur, nxt, False))
        cur = nxt
    return out


def render_ep(ep: str, cover_title: str, badge_text: str | None, meta: dict, shots: list[tuple[Path, int, int, bool]]) -> dict:
    subs_prep = json.loads((PREP_DIR / ep / "subtitles_prep.json").read_text(encoding="utf-8"))
    total_ms = meta["total_ms"]
    work_ep = PREP_DIR / ep / "render_work"
    work_ep.mkdir(parents=True, exist_ok=True)
    ass_path = work_ep / f"{ep}.ass"
    evt_count = build_ass_from_prep(meta, subs_prep, cover_title, badge_text, shots[0][2], ass_path)

    master_wav = work_ep / "master_16lufs.wav"
    lufs_stats = mix_and_loudnorm(VER_DIR / ep / "audio" / "full_voice.wav", total_ms, master_wav)

    clip_paths = []
    for idx, (img_path, s_ms, e_ms, is_book) in enumerate(shots):
        dur_s = max(0.5, (e_ms - s_ms) / 1000.0)
        limit_s = 8.0 if is_book else 6.0
        assert dur_s <= limit_s, f"{ep} shot {idx} exceeds {limit_s}s: {dur_s:.2f}s"
        frames = max(15, round(dur_s * 30))
        clip = work_ep / f"clip_{idx:02d}.mp4"
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

    vlist = work_ep / "vconcat.txt"
    vlist.write_text("\n".join(f"file '{p.as_posix()}'" for p in clip_paths), encoding="utf-8")
    raw_vid = work_ep / "raw_video.mp4"
    subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(vlist), "-c", "copy", str(raw_vid)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_mp4 = OUT_DIR / f"第三周_{ep}_成片.mp4"
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
        "duration_s": round(mp4_ms / 1000.0, 2),
        "lufs": lufs_stats.get("input_i"),
        "tp": lufs_stats.get("input_tp"),
        "subtitle_events": evt_count,
        "shot_count": len(shots),
        "max_shot_s": max(round((e - s) / 1000.0, 2) for _, s, e, _ in shots),
    }


def main() -> None:
    book_card = VER_DIR / "assets" / "book_card_1080x1920.png"
    if not book_card.exists():
        make_book_card(BOOK_COVER, book_card)

    def win(meta: dict, start_i: int, end_i: int) -> tuple[int, int]:
        lines = meta["lines"]
        s = lines[start_i]["start_ms"]
        e = meta["total_ms"] if end_i == len(lines) - 1 else lines[end_i + 1]["start_ms"]
        return s, e

    # D1早
    m_zao = json.loads((VER_DIR / "D1早" / "audio" / "tts_meta.json").read_text(encoding="utf-8"))
    z_old = VER_DIR / "D1早" / "images"
    s_zao = []
    s_zao.extend(split_window([z_old / "IMG01.png", NEW_IMG_DIR / "D1早_IMG01_B.jpg"], *win(m_zao, 0, 2)))
    s_zao.extend(split_window([NEW_IMG_DIR / "D1早_IMG02.jpg", z_old / "IMG02.png"], *win(m_zao, 3, 4)))
    s_zao.extend(split_window([z_old / "IMG03.png", NEW_IMG_DIR / "D1早_IMG03_B.jpg"], *win(m_zao, 5, 6)))
    s_zao.extend(split_window([z_old / "IMG04.png", NEW_IMG_DIR / "D1早_IMG04_B.jpg"], *win(m_zao, 7, 8)))
    s_zao.extend(split_window([NEW_IMG_DIR / "D1早_IMG05.jpg", z_old / "IMG04.png"], *win(m_zao, 9, 10)))
    r_zao = render_ep("D1早", "孙子下棋 输了就哭", None, m_zao, s_zao)
    print("D1早:", json.dumps(r_zao, ensure_ascii=False))

    # D1晚
    m_wan = json.loads((VER_DIR / "D1晚" / "audio" / "tts_meta.json").read_text(encoding="utf-8"))
    s_wan = []
    s_wan.extend(split_window([NEW_IMG_DIR / "D1晚_IMG01.jpg", NEW_IMG_DIR / "D1晚_IMG01_B.jpg", NEW_IMG_DIR / "D1晚_IMG01_C.jpg"], *win(m_wan, 0, 1)))
    s_wan.extend(split_window([NEW_IMG_DIR / "D1晚_IMG02.jpg", NEW_IMG_DIR / "D1晚_IMG02_B.jpg", NEW_IMG_DIR / "D1晚_IMG02_C.jpg"], *win(m_wan, 2, 3)))
    s_wan.extend(split_window([NEW_IMG_DIR / "D1晚_IMG03.jpg", NEW_IMG_DIR / "D1晚_IMG03_B.jpg"], *win(m_wan, 4, 5)))
    s_wan.extend(split_window([NEW_IMG_DIR / "D1晚_IMG04.jpg", NEW_IMG_DIR / "D1晚_IMG04_B.jpg"], *win(m_wan, 6, 7)))
    b_s, b_e = win(m_wan, 8, 8)
    s_wan.append((book_card, b_s, b_e, True))
    s_wan.extend(split_window([NEW_IMG_DIR / "D1晚_IMG05.jpg", NEW_IMG_DIR / "D1晚_IMG05_B.jpg"], *win(m_wan, 9, 9)))
    r_wan = render_ep("D1晚", "救急 不救穷", "人情冷暖", m_wan, s_wan)
    print("D1晚:", json.dumps(r_wan, ensure_ascii=False))


if __name__ == "__main__":
    main()
