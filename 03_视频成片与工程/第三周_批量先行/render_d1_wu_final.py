#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render final D1午 MP4 using MiniMax -16 LUFS audio, fixed 20-screen subtitles, and new D1午 images (<=6s/img)."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "03_视频成片与工程" / "第三周_D1验证"))
sys.path.insert(0, str(ROOT / "scripts"))

from assemble_voice_test import get_ffmpeg, probe_duration_ms  # noqa: E402
from render_d1_videos import mix_and_loudnorm, ms_to_ass  # noqa: E402
import subprocess

FFMPEG = get_ffmpeg()
PREP_DIR = ROOT / "03_视频成片与工程" / "第三周_批量先行"
D1_VER_DIR = ROOT / "03_视频成片与工程" / "第三周_D1验证" / "D1午"
NEW_IMG_DIR = PREP_DIR / "D1_生图测试"
OLD_IMG_DIR = D1_VER_DIR / "images"


def build_ass_from_prep(meta: dict, subs_prep: list[dict], cover_title: str, first_shot_end_ms: int, out_ass: Path) -> int:
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
        "Style: CoverTitle,Microsoft YaHei,74,&H0033D1FF,&H000000FF,&H00000000,&HB0000000,-1,0,0,0,100,100,2,0,3,16,0,8,60,60,180,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events = [f"Dialogue: 2,0:00:00.00,{ms_to_ass(first_shot_end_ms)},CoverTitle,,0,0,0,,{cover_title}"]
    line_map = {l["id"]: l for l in meta["lines"]}
    by_line: dict[str, list[dict]] = {}
    for s in subs_prep:
        by_line.setdefault(s["line_id"], []).append(s)

    for lid, chunks in by_line.items():
        l = line_map[lid]
        s_ms, e_ms = l["start_ms"], l["end_ms"]
        dur = max(100, e_ms - s_ms)
        total_c = max(1, sum(c["chars"] for c in chunks))
        cur = s_ms
        for i, ch in enumerate(chunks):
            nxt = e_ms if i == len(chunks) - 1 else cur + round(dur * (ch["chars"] / total_c))
            events.append(f"Dialogue: 1,{ms_to_ass(cur)},{ms_to_ass(nxt)},Grandpa,,0,0,0,,{ch['text']}")
            cur = nxt

    out_ass.write_text("\n".join(header + events), encoding="utf-8-sig")
    return len(events)


def split_window(imgs: list[Path], s_ms: int, e_ms: int, max_ms: int = 5800) -> list[tuple[Path, int, int]]:
    dur = e_ms - s_ms
    n = max(len(imgs), (dur + max_ms - 1) // max_ms)
    step = dur // n
    out = []
    cur = s_ms
    for i in range(n):
        nxt = e_ms if i == n - 1 else cur + step
        out.append((imgs[i % len(imgs)], cur, nxt))
        cur = nxt
    return out


def main() -> None:
    meta = json.loads((D1_VER_DIR / "audio" / "tts_meta.json").read_text(encoding="utf-8"))
    subs_prep = json.loads((PREP_DIR / "D1午" / "subtitles_prep.json").read_text(encoding="utf-8"))
    lines = meta["lines"]
    total_ms = meta["total_ms"]

    def win(start_i: int, end_i: int) -> tuple[int, int]:
        s = lines[start_i]["start_ms"]
        e = total_ms if end_i == len(lines) - 1 else lines[end_i + 1]["start_ms"]
        return s, e

    shots: list[tuple[Path, int, int]] = []
    shots.extend(split_window([OLD_IMG_DIR / "IMG01.png", NEW_IMG_DIR / "D1午_IMG01_B.jpg"], *win(0, 1)))
    shots.extend(split_window([NEW_IMG_DIR / "D1午_IMG02.jpg", NEW_IMG_DIR / "D1午_IMG02_B.jpg"], *win(2, 3)))
    shots.extend(split_window([OLD_IMG_DIR / "IMG03.png", NEW_IMG_DIR / "D1午_IMG01_B.jpg"], *win(4, 4)))
    shots.extend(split_window([NEW_IMG_DIR / "D1午_IMG04.jpg", NEW_IMG_DIR / "D1午_IMG02_B.jpg"], *win(5, 5)))
    shots.extend(split_window([NEW_IMG_DIR / "D1午_IMG05.jpg", OLD_IMG_DIR / "IMG05.png"], *win(6, 6)))

    work_ep = PREP_DIR / "D1午" / "render_work"
    work_ep.mkdir(parents=True, exist_ok=True)
    ass_path = work_ep / "D1午.ass"
    evt_count = build_ass_from_prep(meta, subs_prep, "轻轨 穿楼过", shots[0][2], ass_path)

    master_wav = work_ep / "master_16lufs.wav"
    lufs_stats = mix_and_loudnorm(D1_VER_DIR / "audio" / "full_voice.wav", total_ms, master_wav)

    clip_paths = []
    for idx, (img_path, s_ms, e_ms) in enumerate(shots):
        dur_s = max(0.5, (e_ms - s_ms) / 1000.0)
        assert dur_s <= 6.0, f"Shot {idx} exceeds 6.0s: {dur_s:.2f}s"
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

    out_dir = PREP_DIR / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_mp4 = out_dir / "第三周_D1午_成片.mp4"
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
    summary = {
        "mp4": str(out_mp4),
        "size_bytes": out_mp4.stat().st_size,
        "duration_s": round(mp4_ms / 1000.0, 2),
        "lufs": lufs_stats.get("input_i"),
        "tp": lufs_stats.get("input_tp"),
        "subtitle_events": evt_count,
        "shot_count": len(shots),
        "max_shot_s": max(round((e - s) / 1000.0, 2) for _, s, e in shots),
        "shots": [(p.name, round((e - s) / 1000.0, 2)) for p, s, e in shots],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
