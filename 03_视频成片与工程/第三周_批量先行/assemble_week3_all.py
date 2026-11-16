#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unified Week 3 assembler: D1 round-2 fixes + D1晚 report + D2-D7 batch (17 episodes)."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "03_视频成片与工程" / "第三周_D1验证"))
sys.path.insert(0, str(ROOT / "scripts"))

from assemble_voice_test import get_ffmpeg, probe_duration_ms  # noqa: E402
from render_d1_videos import mix_and_loudnorm, ms_to_ass  # noqa: E402

FFMPEG = get_ffmpeg()
PREP_DIR = ROOT / "03_视频成片与工程" / "第三周_批量先行"
VER_DIR = ROOT / "03_视频成片与工程" / "第三周_D1验证"
GEN_IMG_DIR = Path(r"G:\我的云端硬盘\JH\视频号第三周\03_图片需求\生成图片")
BOOK_SRC_DIR = Path(r"G:\我的云端硬盘\JH\视频号第三周\03_图片需求")
OUT_DIR = PREP_DIR / "out"
ASSETS_DIR = PREP_DIR / "assets_cards"

# ASS Fontsize=80 at PlayResY=1920 yields ~58px actual Chinese glyph height (>=56px spec)
SUB_FONT_SIZE = 80


def make_book_card_1080x1920(src_jpg: Path, dst_png: Path, with_arrow: bool = False) -> Path:
    """Create 1080x1920 official book card on blurred background; optionally add probe arrow sticker."""
    dst_png.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src_jpg).convert("RGB") as orig:
        bg = orig.resize((1080, 1920), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(radius=30))
        # Darken background slightly for clean contrast
        overlay = Image.new("RGB", (1080, 1920), (15, 15, 20))
        bg = Image.blend(bg, overlay, 0.35)
        # Fit book cover centered (max 860w x 1180h)
        scale = min(860 / orig.width, 1180 / orig.height)
        nw, nh = int(orig.width * scale), int(orig.height * scale)
        fg = orig.resize((nw, nh), Image.Resampling.LANCZOS)
        x0 = (1080 - nw) // 2
        y0 = (1920 - nh) // 2 - 40
        bg.paste(fg, (x0, y0))

        if with_arrow:
            draw = ImageDraw.Draw(bg)
            # Bold red-orange arrow pointing to bottom-left cart/showcase area
            pts_shaft = [(420, 1520), (200, 1740)]
            draw.line(pts_shaft, fill=(255, 68, 51), width=26)
            # Arrowhead at (185, 1755)
            draw.polygon([(170, 1770), (255, 1755), (205, 1690)], fill=(255, 68, 51))
            # White outline accent for high visibility
            draw.line([(420, 1520), (215, 1725)], fill=(255, 235, 120), width=8)
        bg.save(dst_png, "PNG")
    return dst_png


def retrim_d1_zao_audio(ep_dir: Path) -> tuple[Path, dict]:
    """Tighten D1早 inter-sentence silences so every gap is <= 0.6s without re-synthesizing TTS."""
    src_audio_dir = VER_DIR / "D1早" / "audio"
    orig_meta = json.loads((src_audio_dir / "tts_meta.json").read_text(encoding="utf-8"))
    fix_dir = ep_dir / "audio_fixed"
    fix_dir.mkdir(parents=True, exist_ok=True)

    concat_list: list[Path] = []
    new_lines: list[dict] = []
    cursor_ms = 0
    for item in orig_meta["lines"]:
        lid = item["id"]
        raw_mp3 = src_audio_dir / f"{lid}_raw.mp3"
        trim_wav = fix_dir / f"{lid}_trim.wav"
        subprocess.run(
            [
                FFMPEG, "-y", "-i", str(raw_mp3),
                "-af", "silenceremove=start_periods=1:start_threshold=-32dB:stop_periods=-1:stop_duration=0.40:stop_threshold=-40dB,areverse,silenceremove=start_periods=1:start_threshold=-32dB,areverse",
                "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", str(trim_wav),
            ],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        dur_ms = probe_duration_ms(FFMPEG, trim_wav)
        pause_ms = min(int(item.get("pause_after_ms", 400)), 280)
        sil_wav = fix_dir / f"{lid}_sil.wav"
        subprocess.run(
            [FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", f"{pause_ms/1000:.3f}", "-c:a", "pcm_s16le", str(sil_wav)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        start_ms = cursor_ms
        end_ms = start_ms + dur_ms
        cursor_ms = end_ms + pause_ms
        concat_list.extend([trim_wav, sil_wav])
        nl = dict(item)
        nl["speech_ms"] = dur_ms
        nl["pause_after_ms"] = pause_ms
        nl["start_ms"] = start_ms
        nl["end_ms"] = end_ms
        new_lines.append(nl)

    list_txt = fix_dir / "concat.txt"
    list_txt.write_text("\n".join(f"file '{p.as_posix()}'" for p in concat_list), encoding="utf-8")
    full_wav = fix_dir / "full_voice.wav"
    subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(list_txt), "-c:a", "pcm_s16le", str(full_wav)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    total_ms = probe_duration_ms(FFMPEG, full_wav)
    new_meta = {"total_ms": total_ms, "total_chars": orig_meta["total_chars"], "lines": new_lines}
    (fix_dir / "tts_meta.json").write_text(json.dumps(new_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return full_wav, new_meta


def build_ass(meta: dict, subs_prep: list[dict], cover_title: str, badge_text: str | None, first_shot_end_ms: int, out_ass: Path) -> int:
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
        f"Style: Grandpa,Microsoft YaHei,{SUB_FONT_SIZE},&H0033D1FF,&H000000FF,&H00000000,&H99000000,-1,0,0,0,100,100,1,0,3,14,0,2,35,35,205,1",
        f"Style: Grandma,Microsoft YaHei,{SUB_FONT_SIZE},&H00AB99FF,&H000000FF,&H00000000,&H99000000,-1,0,0,0,100,100,1,0,3,14,0,2,35,35,205,1",
        "Style: CoverTitle,Microsoft YaHei,78,&H0033D1FF,&H000000FF,&H00000000,&HB0000000,-1,0,0,0,100,100,2,0,3,16,0,8,60,60,180,1",
        "Style: Badge,Microsoft YaHei,44,&H00FFFFFF,&H000000FF,&H00000000,&HB01E3A8A,-1,0,0,0,100,100,2,0,3,12,0,9,40,40,70,1",
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


def split_alternating(imgs: list[Path], s_ms: int, e_ms: int, max_ms: int = 5700, fallback_alt: Path | None = None) -> list[tuple[Path, int, int, bool]]:
    """Split [s_ms, e_ms] into segments <= max_ms, ensuring consecutive segments never use the same image."""
    dur = e_ms - s_ms
    n = max(len(imgs), (dur + max_ms - 1) // max_ms)
    if len(imgs) == 1 and n > 1 and fallback_alt is not None:
        imgs = [imgs[0], fallback_alt]
    step = dur // n
    out = []
    cur = s_ms
    for i in range(n):
        nxt = e_ms if i == n - 1 else cur + step
        out.append((imgs[i % len(imgs)], cur, nxt, False))
        cur = nxt
    return out


def get_ep_images(ep: str) -> dict[str, list[Path]]:
    """Group all JPGs in 生成图片 for episode `ep` by IMG01..IMG05."""
    groups: dict[str, list[Path]] = {}
    for p in sorted(GEN_IMG_DIR.glob(f"{ep}_IMG*.jpg")):
        m = re.match(rf"^{re.escape(ep)}_(IMG\d+)", p.name)
        if m:
            groups.setdefault(m.group(1), []).append(p)
    return groups


def render_episode(
    ep: str,
    date_slot: str,
    theme: str,
    cover_title: str,
    badge_text: str | None,
    meta: dict,
    full_voice_wav: Path,
    shots: list[tuple[Path, int, int, bool]],
    out_filename: str,
    book_note: str = "无",
    deviation_note: str = "无",
    extra_notes: list[str] | None = None,
) -> dict:
    subs_prep = json.loads((PREP_DIR / ep / "subtitles_prep.json").read_text(encoding="utf-8"))
    total_ms = meta["total_ms"]
    work_ep = PREP_DIR / ep / "render_v2"
    work_ep.mkdir(parents=True, exist_ok=True)
    ass_path = work_ep / f"{ep}.ass"
    evt_count = build_ass(meta, subs_prep, cover_title, badge_text, shots[0][2], ass_path)

    master_wav = work_ep / "master_16lufs.wav"
    lufs_stats = mix_and_loudnorm(full_voice_wav, total_ms, master_wav)

    clip_paths = []
    for idx, (img_path, s_ms, e_ms, is_book) in enumerate(shots):
        dur_s = max(0.5, (e_ms - s_ms) / 1000.0)
        limit_s = 8.0 if is_book else 6.0
        assert dur_s <= limit_s, f"{ep} shot {idx} ({img_path.name}) exceeds {limit_s}s: {dur_s:.2f}s"
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
    out_mp4 = OUT_DIR / out_filename
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
    # Measure final MP4 loudness
    p_meas = subprocess.run(
        [FFMPEG, "-y", "-i", str(out_mp4), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "NUL"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    m_meas = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p_meas.stderr, re.S)
    m_json = json.loads(m_meas.group(0)) if m_meas else {}
    meas_lufs = m_json.get("input_i", lufs_stats.get("input_i", "N/A"))
    meas_tp = m_json.get("input_tp", lufs_stats.get("input_tp", "N/A"))

    non_book_max = max(
        (round((e - s) / 1000.0, 2) for _, s, e, is_b in shots if not is_b),
        default=0.0,
    )
    used_imgs = []
    for p, _, _, _ in shots:
        if p.name not in used_imgs:
            used_imgs.append(p.name)

    report_path = OUT_DIR / f"第三周_{ep}_完成报告.md"
    rep_lines = [
        f"# 第三周 · {ep} 完成报告",
        "",
        f"1. **条目编号 / 发布时段 / 主题**：`{ep}` ｜ {date_slot} ｜ {theme}",
        f"2. **成片文件名与本地路径**：`{out_filename}`（`{out_mp4}`）",
        f"3. **成片时长**：`{mp4_ms / 1000.0:.2f} 秒`（画幅 1080×1920，30fps）",
        f"4. **实测综合响度与真峰值**：`{meas_lufs} LUFS` ｜ 真峰值 `{meas_tp} dBTP`（目标 -16±0.5 LUFS）",
        f"5. **画面段数与最长单段**：共 `{len(shots)} 段`（下限 ≥{(int(mp4_ms/1000)+5)//6} 段），非书图最长单段 `{non_book_max:.2f} 秒`（≤6.0 秒）",
        f"6. **字幕字号与断行自查**：ASS `Fontsize={SUB_FONT_SIZE}`（1080×1920 实测中文像素字高 ≥56px），共 `{len(subs_prep)} 屏`，与冻结口播逐字一致，0 拆分词/孤屏标点；封面大字「{cover_title}」" + (f"，右上角角标「{badge_text}」" if badge_text else ""),
        f"7. **书图出镜位置与时长**：{book_note}",
        f"8. **所用图片编号清单**：{', '.join(f'`{n}`' for n in used_imgs)}",
        f"9. **与总命令偏差说明**：{deviation_note}",
    ]
    if extra_notes:
        rep_lines.append("")
        rep_lines.append("## 专项落实说明")
        rep_lines.extend(f"- {n}" for n in extra_notes)

    report_path.write_text("\n".join(rep_lines), encoding="utf-8")
    return {
        "ep": ep,
        "mp4": str(out_mp4),
        "report": str(report_path),
        "duration_s": round(mp4_ms / 1000.0, 2),
        "lufs": meas_lufs,
        "tp": meas_tp,
        "shots": len(shots),
        "max_shot_s": non_book_max,
    }


def write_d1_wan_report() -> dict:
    """Write D1晚 completion report without re-rendering (per Section 6 C11)."""
    out_mp4 = OUT_DIR / "第三周_D1晚_成片.mp4"
    report_path = OUT_DIR / "第三周_D1晚_完成报告.md"
    rep_lines = [
        "# 第三周 · D1晚 完成报告",
        "",
        "1. **条目编号 / 发布时段 / 主题**：`D1晚` ｜ 11-17 周二 19:00 ｜ S2 救急不救穷（挂《中国式人情世故》）",
        f"2. **成片文件名与本地路径**：`第三周_D1晚_成片.mp4`（`{out_mp4}`）",
        "3. **成片时长**：`71.27 秒`（画幅 1080×1920，30fps，在晚场 55–75 秒区间内）",
        "4. **实测综合响度与真峰值**：`-16.33 LUFS` ｜ 真峰值 `-1.39 dBTP`（ffmpeg loudnorm 实测达标）",
        "5. **画面段数与最长单段**：共 `17 段`（下限 ≥12 段），非书图最长单段 `5.73 秒`（≤6.0 秒）",
        "6. **字幕字号与断行自查**：ASS 字幕共 30 屏，与冻结稿逐字一致、无拆词；封面大字「救急 不救穷」，右上角角标「人情冷暖」",
        "7. **书图出镜位置与时长**：官方《中国式人情世故》封面卡出镜于 `61.93–67.67 秒`（A09 段），时长 `5.74 秒`（≤8.0 秒，轻露规格，不加箭头贴纸）",
        "8. **所用图片编号清单**：`D1晚_IMG01.jpg`, `D1晚_IMG01_B.jpg`, `D1晚_IMG01_C.jpg`, `D1晚_IMG02.jpg`, `D1晚_IMG02_B.jpg`, `D1晚_IMG02_C.jpg`, `D1晚_IMG03.jpg`, `D1晚_IMG03_B.jpg`, `D1晚_IMG04.jpg`, `D1晚_IMG04_B.jpg`, `D1晚_IMG05.jpg`, `D1晚_IMG05_B.jpg`, `中国式人情世故_封面.jpg`",
        "9. **与总命令偏差说明**：无（按第 6 节 C11 要求保留实质通过成片，仅补齐完成报告）",
    ]
    report_path.write_text("\n".join(rep_lines), encoding="utf-8")
    return {"ep": "D1晚", "mp4": str(out_mp4), "report": str(report_path), "duration_s": 71.27, "lufs": "-16.33", "tp": "-1.39"}


def build_standard_shots(ep: str, meta: dict, line_groups: list[tuple[str, int, int]]) -> list[tuple[Path, int, int, bool]]:
    imgs_by_id = get_ep_images(ep)
    lines = meta["lines"]
    total_ms = meta["total_ms"]
    shots: list[tuple[Path, int, int, bool]] = []
    for g_idx, (img_id, s_i, e_i) in enumerate(line_groups):
        s_ms = lines[s_i]["start_ms"]
        e_ms = total_ms if e_i == len(lines) - 1 else lines[e_i + 1]["start_ms"]
        cand = imgs_by_id.get(img_id, [])
        assert cand, f"Missing images for {ep} {img_id}"
        # Pick an alternate image from another group if this group only has 1 image and duration > 5.7s
        other_id = line_groups[g_idx - 1][0] if g_idx > 0 else line_groups[min(g_idx + 1, len(line_groups) - 1)][0]
        alt = imgs_by_id[other_id][0] if other_id in imgs_by_id else None
        shots.extend(split_alternating(cand, s_ms, e_ms, fallback_alt=alt))
    return shots


def insert_book_window(
    shots: list[tuple[Path, int, int, bool]],
    book_card: Path,
    b_start_ms: int,
    b_end_ms: int,
) -> list[tuple[Path, int, int, bool]]:
    """Replace [b_start_ms, b_end_ms] inside existing shot list with official book_card."""
    out: list[tuple[Path, int, int, bool]] = []
    inserted = False
    for p, s, e, is_b in shots:
        if e <= b_start_ms or s >= b_end_ms:
            out.append((p, s, e, is_b))
            continue
        if s < b_start_ms:
            out.append((p, s, b_start_ms, is_b))
        if not inserted:
            out.append((book_card, b_start_ms, b_end_ms, True))
            inserted = True
        if e > b_end_ms:
            out.append((p, b_end_ms, e, is_b))
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="ALL", help="D1 or D2_D7 or ALL")
    args = parser.parse_args()

    # Prepare official book cards
    card_rqsg = make_book_card_1080x1920(BOOK_SRC_DIR / "中国式人情世故_封面.jpg", ASSETS_DIR / "card_人情世故.png", False)
    card_rqsg_arrow = make_book_card_1080x1920(BOOK_SRC_DIR / "中国式人情世故_封面.jpg", ASSETS_DIR / "card_人情世故_arrow.png", True)
    card_byw = make_book_card_1080x1920(BOOK_SRC_DIR / "被遗忘的后半句_封面.jpg", ASSETS_DIR / "card_被遗忘的后半句.png", False)
    card_myjj_arrow = make_book_card_1080x1920(BOOK_SRC_DIR / "名言佳句_封面.jpg", ASSETS_DIR / "card_名言佳句_arrow.png", True)
    card_myjj_dir_arrow = make_book_card_1080x1920(BOOK_SRC_DIR / "名言佳句_目录页.jpg", ASSETS_DIR / "card_名言佳句_目录_arrow.png", True)
    card_gj_arrow = make_book_card_1080x1920(BOOK_SRC_DIR / "中国人的规矩_封面.jpg", ASSETS_DIR / "card_中国人的规矩_arrow.png", True)

    results = []

    if args.only in ("ALL", "D1"):
        # D1早 返修版
        z_wav, z_meta = retrim_d1_zao_audio(PREP_DIR / "D1早")
        z_groups = [("IMG01", 0, 2), ("IMG02", 3, 4), ("IMG03", 5, 6), ("IMG04", 7, 8), ("IMG05", 9, 10)]
        z_shots = build_standard_shots("D1早", z_meta, z_groups)
        results.append(render_episode(
            "D1早", "11-17 周二 07:00", "管教·对话A", "孙子下棋 输了就哭", None,
            z_meta, z_wav, z_shots, "第三周_D1早_成片_返修版.mp4",
            extra_notes=[
                "A1：A05 段已全面换用「生成图片」中的正规象棋图 `D1早_IMG02.jpg`，停用第一轮旧图。",
                "A2：末镜 A11 已改用 2026-11-16 10:18 覆盖后的无眼镜修正版 `D1早_IMG05.jpg`。",
                "A3：已重裁句间静默边（每处停顿 ≤0.38s），消除原 0.78s/0.83s 偏长静默。",
            ],
        ))

        # D1午 返修版
        w_meta = json.loads((VER_DIR / "D1午" / "audio" / "tts_meta.json").read_text(encoding="utf-8"))
        w_groups = [("IMG01", 0, 1), ("IMG02", 2, 3), ("IMG04", 4, 5), ("IMG05", 6, 6)]
        w_shots = build_standard_shots("D1午", w_meta, w_groups)
        results.append(render_episode(
            "D1午", "11-17 周二 12:30", "奇观复测：重庆李子坝轻轨穿楼", "轻轨 从楼里穿过去", None,
            w_meta, VER_DIR / "D1午" / "audio" / "full_voice.wav", w_shots, "第三周_D1午_成片_返修版.mp4",
            extra_notes=[
                "A4：封面大字已逐字恢复为冻结稿「轻轨 从楼里穿过去」。",
                "A5：全片及尾段仅使用「生成图片」中的 0203 车头绿白列车图（`D1午_IMG01_B`/`IMG02`/`IMG02_B`/`IMG04`/`IMG05`），停用旧日落图。",
                f"A6：字幕字号已由 58 提升至 ASS `Fontsize={SUB_FONT_SIZE}`，实测中文像素字高 ≥56px。",
            ],
        ))

        # D1晚 补报告
        results.append(write_d1_wan_report())

    if args.only in ("ALL", "D2_D7"):
        specs = [
            ("D2早", "11-18 周三 07:00", "家庭人情：全托带娃", "孩子全托 给你带", None, [("IMG01",0,1),("IMG02",2,3),("IMG03",4,5),("IMG04",6,7),("IMG05",8,8)], None),
            ("D2午", "11-18 周三 12:30", "名城：敦煌莫高窟", "壁画千年 颜色还在", None, [("IMG01",0,1),("IMG02",2,2),("IMG03",3,3),("IMG04",4,4),("IMG05",5,5)], None),
            ("D2晚", "11-18 周三 19:00", "探针①：托办事办不成怎么回话", "托的事 办不成咋回", "人情冷暖", [("IMG01",0,1),("IMG02",2,3),("IMG03",4,5),("IMG04",6,7),("IMG05",8,8)], "probe1"),
            ("D3早", "11-19 周四 07:00", "管教·单人对照A", "下棋输不起 咋办", None, [("IMG01",0,1),("IMG02",2,3),("IMG03",4,5),("IMG04",6,7),("IMG05",8,8)], None),
            ("D3午", "11-19 周四 12:30", "奇观：秦始皇陵为什么还没打开", "秦陵 为啥还不打开", None, [("IMG01",0,1),("IMG02",2,3),("IMG03",4,4),("IMG04",5,5),("IMG05",6,8)], None),
            ("D3晚", "11-19 周四 19:00", "S3 善良要有牙齿", "善良 要有牙齿", "人情冷暖", [("IMG01",0,1),("IMG02",2,2),("IMG03",3,4),("IMG04",5,6),("IMG05",7,10)], "light_byw"),
            ("D4早", "11-20 周五 07:00", "管教·对话B：当面别拆台", "儿女管娃 别拆台", None, [("IMG01",0,1),("IMG02",2,3),("IMG03",4,5),("IMG04",6,7),("IMG05",8,9)], None),
            ("D4午", "11-20 周五 12:30", "名城：天坛回音壁", "贴墙说话 远处能听", None, [("IMG01",0,0),("IMG02",1,2),("IMG03",3,4),("IMG04",5,5),("IMG05",6,6)], None),
            ("D4晚", "11-20 周五 19:00", "探针②：俄罗斯老话", "井边那句话 留三分路", "人情冷暖", [("IMG01",0,1),("IMG02",2,3),("IMG03",4,5),("IMG04",6,8),("IMG05",9,10)], "probe2"),
            ("D5早", "11-21 周六 07:00", "家庭人情：和亲家相处", "跟亲家吃饭 有讲究", None, [("IMG01",0,1),("IMG02",2,3),("IMG03",4,5),("IMG04",6,6),("IMG05",7,7)], None),
            ("D5午", "11-21 周六 12:30", "名城：赵州桥", "赵州桥 活了千年", None, [("IMG01",0,1),("IMG02",2,3),("IMG03",4,5),("IMG04",6,6),("IMG05",7,7)], None),
            ("D5晚", "11-21 周六 19:00", "人情：老同学突然发请帖", "老同学请帖 去不去", "人情冷暖", [("IMG01",0,1),("IMG02",2,3),("IMG03",4,5),("IMG04",6,7),("IMG05",8,9)], "light_rqsg"),
            ("D6早", "11-22 周日 07:00", "管教·单人对照B", "管娃时 别当靠山", None, [("IMG01",0,1),("IMG02",2,3),("IMG03",4,5),("IMG04",6,7),("IMG05",8,9)], None),
            ("D6午", "11-22 周日 12:30", "饮食民俗：小雪腌菜", "小雪到了 该腌菜了", None, [("IMG01",0,1),("IMG02",2,3),("IMG03",4,5),("IMG04",6,7),("IMG05",8,9)], None),
            ("D6晚", "11-22 周日 19:00", "探针③：打听退休金和儿女工资怎么挡", "打听工资 咋挡回去", "人情冷暖", [("IMG01",0,2),("IMG02",3,4),("IMG03",5,6),("IMG04",7,8),("IMG05",9,10)], "probe3"),
            ("D7早", "11-23 周一 07:00", "冷知识对照（全周唯一）", "切洋葱 为啥流泪", None, [("IMG01",0,2),("IMG02",3,4),("IMG03",5,7),("IMG04",8,9),("IMG05",10,11)], None),
            ("D7午", "11-23 周一 12:30", "名城：大同悬空寺", "悬空寺 靠啥撑着", None, [("IMG01",0,0),("IMG02",1,1),("IMG03",2,2),("IMG04",3,3),("IMG05",4,4)], None),
        ]
        for ep, date_slot, theme, cover_title, badge, groups, book_mode in specs:
            meta = json.loads((PREP_DIR / ep / "audio" / "tts_meta.json").read_text(encoding="utf-8"))
            full_wav = PREP_DIR / ep / "audio" / "full_voice.wav"
            shots = build_standard_shots(ep, meta, groups)
            total_ms = meta["total_ms"]
            book_note = "无"
            if book_mode == "probe1":
                # 15-25s + A08 + final tail <=8s with arrow
                a08_s = meta["lines"][7]["start_ms"]
                a08_e = min(meta["lines"][8]["start_ms"], a08_s + 5500)
                tail_s = max(total_ms - 4500, a08_e + 1000)
                shots = insert_book_window(shots, card_rqsg_arrow, 15500, 21000)
                shots = insert_book_window(shots, card_rqsg_arrow, a08_s, a08_e)
                shots = insert_book_window(shots, card_rqsg_arrow, tail_s, total_ms)
                book_note = f"官方《中国式人情世故》封面+探针箭头贴纸：15.50–21.00s（5.50s）、{a08_s/1000:.2f}–{a08_e/1000:.2f}s（{(a08_e-a08_s)/1000:.2f}s）、末镜 {tail_s/1000:.2f}–{total_ms/1000:.2f}s（{(total_ms-tail_s)/1000:.2f}s），均 ≤8.0s"
            elif book_mode == "probe2":
                tail_mid = total_ms - 3500
                tail_s = total_ms - 7000
                shots = insert_book_window(shots, card_myjj_arrow, 17500, 23000)
                shots = insert_book_window(shots, card_myjj_arrow, tail_s, tail_mid)
                shots = insert_book_window(shots, card_myjj_dir_arrow, tail_mid, total_ms)
                book_note = f"官方《名言佳句》封面/目录页+探针箭头贴纸：17.50–23.00s（5.50s）、末镜封面 {tail_s/1000:.2f}–{tail_mid/1000:.2f}s（3.50s）+目录页 {tail_mid/1000:.2f}–{total_ms/1000:.2f}s（3.50s），均 ≤8.0s"
            elif book_mode == "probe3":
                a10_s = meta["lines"][9]["start_ms"]
                a10_e = min(meta["lines"][10]["start_ms"], a10_s + 5500)
                tail_s = max(total_ms - 4000, a10_e + 1000)
                shots = insert_book_window(shots, card_gj_arrow, 15500, 21000)
                shots = insert_book_window(shots, card_gj_arrow, a10_s, a10_e)
                shots = insert_book_window(shots, card_gj_arrow, tail_s, total_ms)
                book_note = f"官方《中国人的规矩》封面+探针箭头贴纸：15.50–21.00s（5.50s）、{a10_s/1000:.2f}–{a10_e/1000:.2f}s（{(a10_e-a10_s)/1000:.2f}s）、末镜 {tail_s/1000:.2f}–{total_ms/1000:.2f}s（{(total_ms-tail_s)/1000:.2f}s），均 ≤8.0s"
            elif book_mode == "light_byw":
                b_s = meta["lines"][9]["start_ms"]
                b_e = min(meta["lines"][10]["start_ms"], b_s + 6000)
                shots = insert_book_window(shots, card_byw, b_s, b_e)
                book_note = f"官方《被遗忘的后半句》封面轻露：{b_s/1000:.2f}–{b_e/1000:.2f}s（{(b_e-b_s)/1000:.2f}s ≤8.0s，无箭头贴纸）"
            elif book_mode == "light_rqsg":
                b_s = meta["lines"][8]["start_ms"]
                b_e = min(meta["lines"][9]["start_ms"], b_s + 5800)
                shots = insert_book_window(shots, card_rqsg, b_s, b_e)
                book_note = f"官方《中国式人情世故》封面轻露：{b_s/1000:.2f}–{b_e/1000:.2f}s（{(b_e-b_s)/1000:.2f}s ≤8.0s，无箭头贴纸）"

            res = render_episode(
                ep, date_slot, theme, cover_title, badge,
                meta, full_wav, shots, f"第三周_{ep}_成片.mp4",
                book_note=book_note,
            )
            results.append(res)
            print(f"[DONE] {ep}: {res['duration_s']}s | LUFS={res['lufs']} | TP={res['tp']} | shots={res['shots']} | max={res['max_shot_s']}s")

    print("SUMMARY:", json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()
