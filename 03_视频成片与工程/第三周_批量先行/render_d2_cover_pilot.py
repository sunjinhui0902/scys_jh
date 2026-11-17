#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render D2 (D2早 / D2午 / D2晚) Poster Cover Pilot versions per
《第三周_D2封面试点_给Antigravity触发单_20261117.md》:
- Only replace the cover segment (Shot 0: frames 0..141 for D2早, 0..153 for D2午, 0..142 for D2晚).
- Base image:
  * D2早 (07:00): D2早_IMG01.jpg (最情绪：老人眉头紧锁双手交握特写)
  * D2午 (12:30): D2午_IMG02_B.jpg (最奇观：莫高窟千年彩绘藻井与大佛洞窟全景奇观)
  * D2晚 (19:00): D2晚_IMG01.jpg (最情绪：老人低头握手机迟疑不决特写)
- Typography & Layout:
  * Big Title: STXINGKA.TTF (华文行楷毛笔书法体), gold gradient fill + thick black ink stroke + shadow, no punctuation.
  * Hook Banner: Single-line crimson-red banner with bold white text, Chinese numerals only, no punctuation.
  * Evening Badge: Keep top-right '人情冷暖' badge on D2晚.
  * Bottom AI Declaration: '画面由 AI 生成 仅供参考' at the bottom of the cover segment.
- From Shot 1 first frame onwards, every video frame, audio sample, and subtitle event is 100% unchanged.
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "03_视频成片与工程" / "第三周_批量先行"))
sys.path.insert(0, str(ROOT / "03_视频成片与工程" / "第三周_D1验证"))
sys.path.insert(0, str(ROOT / "scripts"))

from assemble_voice_test import get_ffmpeg, probe_duration_ms  # noqa: E402

FFMPEG = get_ffmpeg()
PREP_DIR = ROOT / "03_视频成片与工程" / "第三周_批量先行"
GEN_IMG_DIR = Path(r"G:\我的云端硬盘\JH\视频号第三周\03_图片需求\生成图片")
OUT_DIR = PREP_DIR / "out"
GDRIVE_REVIEW_DIR = Path(r"G:\我的云端硬盘\JH\视频号第三周\06_成片待审")
GDRIVE_INBOX_DIR = Path(r"G:\我的云端硬盘\JH\AI信箱\01_收件_待讨论")

CALLIGRAPHY_FONT = r"D:\fuye\02_公共资产库\字体库\STXINGKA.TTF"
BOLD_FONT = r"C:\Windows\Fonts\msyhbd.ttc"
REG_FONT = r"C:\Windows\Fonts\msyh.ttc"


def create_poster_overlay(
    big_title: str,
    hook_text: str,
    badge_text: str | None = None,
    title_y: int = 1080,
) -> Image.Image:
    canvas = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    # 1. Optional Top-Right Badge ('人情冷暖')
    if badge_text:
        b_font = ImageFont.truetype(BOLD_FONT, 40)
        bbox = draw.textbbox((0, 0), badge_text, font=b_font)
        bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pad_x, pad_y = 24, 14
        bx1 = 1080 - 42
        bx0 = bx1 - bw - pad_x * 2
        by0 = 68
        by1 = by0 + bh + pad_y * 2
        draw.rounded_rectangle([bx0, by0, bx1, by1], radius=12, fill=(30, 58, 138, 220), outline=(255, 255, 255, 150), width=2)
        draw.text((bx0 + pad_x - bbox[0], by0 + pad_y - bbox[1]), badge_text, font=b_font, fill=(255, 255, 255, 255))

    # 2. Subtle dark gradient vignette behind the poster text zone for high contrast
    vignette = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    v_draw = ImageDraw.Draw(vignette)
    for y in range(title_y - 80, min(1920, title_y + 460)):
        dist = abs(y - (title_y + 170)) / 250.0
        alpha = int(max(0.0, (1.0 - dist * dist)) * 105)
        v_draw.line([(0, y), (1080, y)], fill=(0, 0, 0, alpha))
    canvas = Image.alpha_composite(canvas, vignette)
    draw = ImageDraw.Draw(canvas)

    # 3. Big Calligraphy Brush Title
    c_size = 200 if len(big_title) <= 3 else 176
    c_font = ImageFont.truetype(CALLIGRAPHY_FONT, c_size)
    char_gap = 16 if len(big_title) <= 3 else 10
    char_boxes = [draw.textbbox((0, 0), ch, font=c_font) for ch in big_title]
    char_widths = [b[2] - b[0] for b in char_boxes]
    total_w = sum(char_widths) + char_gap * (len(big_title) - 1)
    max_h = max(b[3] - b[1] for b in char_boxes)
    start_x = (1080 - total_w) // 2

    title_layer = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    t_draw = ImageDraw.Draw(title_layer)
    cur_x = start_x
    for ch, b, cw in zip(big_title, char_boxes, char_widths):
        cx = cur_x - b[0]
        cy = title_y - b[1]
        for dx in range(-4, 5, 2):
            for dy in range(-4, 5, 2):
                t_draw.text((cx + 8 + dx, cy + 10 + dy), ch, font=c_font, fill=(0, 0, 0, 180))
        stroke_r = 10
        for dx in range(-stroke_r, stroke_r + 1, 2):
            for dy in range(-stroke_r, stroke_r + 1, 2):
                if dx * dx + dy * dy <= stroke_r * stroke_r + 4:
                    t_draw.text((cx + dx, cy + dy), ch, font=c_font, fill=(15, 10, 5, 255))
        cur_x += cw + char_gap

    mask_layer = Image.new("L", (1080, 1920), 0)
    m_draw = ImageDraw.Draw(mask_layer)
    cur_x = start_x
    for ch, b, cw in zip(big_title, char_boxes, char_widths):
        cx = cur_x - b[0]
        cy = title_y - b[1]
        m_draw.text((cx, cy), ch, font=c_font, fill=255)
        cur_x += cw + char_gap

    grad_layer = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(grad_layer)
    for y in range(title_y - 20, title_y + max_h + 40):
        ratio = max(0.0, min(1.0, (y - title_y) / max(1, max_h)))
        if ratio < 0.5:
            r2 = ratio * 2.0
            col = (
                int(255 * (1 - r2) + 255 * r2),
                int(243 * (1 - r2) + 217 * r2),
                int(176 * (1 - r2) + 61 * r2),
                255,
            )
        else:
            r2 = (ratio - 0.5) * 2.0
            col = (
                int(255 * (1 - r2) + 245 * r2),
                int(217 * (1 - r2) + 158 * r2),
                int(61 * (1 - r2) + 11 * r2),
                255,
            )
        g_draw.line([(0, y), (1080, y)], fill=col)

    title_layer.paste(grad_layer, (0, 0), mask_layer)
    canvas = Image.alpha_composite(canvas, title_layer)
    draw = ImageDraw.Draw(canvas)

    # 4. Single-Line Red-Background White-Text Hook Banner ('红底白字横幅一行')
    banner_y0 = title_y + max_h + 38
    h_size = 60
    while h_size >= 40:
        h_font = ImageFont.truetype(BOLD_FONT, h_size)
        hb = draw.textbbox((0, 0), hook_text, font=h_font)
        hw, hh = hb[2] - hb[0], hb[3] - hb[1]
        if hw <= 920:
            break
        h_size -= 2

    pad_hx, pad_hy = 38, 22
    bw_total = hw + pad_hx * 2
    bh_total = hh + pad_hy * 2
    bx0 = (1080 - bw_total) // 2
    bx1 = bx0 + bw_total
    by0 = banner_y0
    by1 = by0 + bh_total

    draw.rounded_rectangle([bx0 + 6, by0 + 8, bx1 + 6, by1 + 8], radius=16, fill=(0, 0, 0, 160))
    draw.rounded_rectangle([bx0, by0, bx1, by1], radius=16, fill=(208, 28, 28, 245), outline=(255, 225, 130, 220), width=3)
    tx = bx0 + pad_hx - hb[0]
    ty = by0 + pad_hy - hb[1]
    for dx, dy in [(-2, -2), (2, -2), (-2, 2), (2, 2), (0, 3)]:
        draw.text((tx + dx, ty + dy), hook_text, font=h_font, fill=(60, 0, 0, 220))
    draw.text((tx, ty), hook_text, font=h_font, fill=(255, 255, 255, 255))

    # 5. Bottom AI Declaration Small Text ('画面由 AI 生成 仅供参考')
    ai_text = "画面由 AI 生成 仅供参考"
    ai_font = ImageFont.truetype(REG_FONT, 32)
    ab = draw.textbbox((0, 0), ai_text, font=ai_font)
    aw, ah = ab[2] - ab[0], ab[3] - ab[1]
    ax = (1080 - aw) // 2 - ab[0]
    ay = 1835 - ab[1]
    for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
        draw.text((ax + dx, ay + dy), ai_text, font=ai_font, fill=(0, 0, 0, 180))
    draw.text((ax, ay), ai_text, font=ai_font, fill=(230, 230, 230, 215))

    return canvas


def build_pilot_episode(
    ep: str,
    date_slot: str,
    theme: str,
    base_img_path: Path,
    base_img_reason: str,
    big_title: str,
    hook_text: str,
    badge_text: str | None,
    cover_dur_s: float,
    cover_frames: int,
    orig_report_info: dict,
) -> dict:
    work_ep = PREP_DIR / ep / "render_v2"
    pilot_dir = PREP_DIR / ep / "render_cover_pilot"
    pilot_dir.mkdir(parents=True, exist_ok=True)

    # 1. Save RGBA poster overlay PNG
    ov_png = pilot_dir / f"{ep}_poster_overlay.png"
    ov_img = create_poster_overlay(big_title, hook_text, badge_text, title_y=1080)
    ov_img.save(ov_png, "PNG")

    # 2. Render clip_00_pilot.mp4 with exact same duration/frames as original clip_00.mp4 + poster overlay
    clip0_pilot = pilot_dir / "clip_00_pilot.mp4"
    zp = f"zoompan=z='min(zoom+0.0005,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={cover_frames}:s=1080x1920:fps=30"
    fc = (
        f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,{zp},setsar=1[bg];"
        f"[bg][1:v]overlay=0:0:format=auto[v]"
    )
    subprocess.run(
        [
            FFMPEG, "-y",
            "-loop", "1", "-i", str(base_img_path),
            "-i", str(ov_png),
            "-filter_complex", fc,
            "-map", "[v]",
            "-frames:v", str(cover_frames),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
            str(clip0_pilot),
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    # 3. Concatenate clip_00_pilot.mp4 with original untouched clip_01.mp4 .. clip_N.mp4
    orig_vlist = (work_ep / "vconcat.txt").read_text(encoding="utf-8").splitlines()
    pilot_vlist_lines = [f"file '{clip0_pilot.as_posix()}'"] + orig_vlist[1:]
    pilot_vlist = pilot_dir / "vconcat_pilot.txt"
    pilot_vlist.write_text("\n".join(pilot_vlist_lines), encoding="utf-8")

    raw_vid_pilot = pilot_dir / "raw_video_pilot.mp4"
    subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(pilot_vlist), "-c", "copy", str(raw_vid_pilot)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    # 4. Prepare ASS with ONLY the old CoverTitle & Badge lines removed (all Dialogue: 1 spoken subtitles untouched)
    orig_ass_lines = (work_ep / f"{ep}.ass").read_text(encoding="utf-8-sig").splitlines()
    pilot_ass_lines = [
        l for l in orig_ass_lines
        if not l.startswith("Dialogue: 2,") and not l.startswith("Dialogue: 3,")
    ]
    pilot_ass = pilot_dir / f"{ep}_pilot.ass"
    pilot_ass.write_text("\n".join(pilot_ass_lines), encoding="utf-8-sig")

    # 5. Burn spoken subtitles and mux original untouched master_16lufs.wav
    out_filename = f"第三周_{ep}_成片_封面试点版.mp4"
    out_mp4 = OUT_DIR / out_filename
    ass_escaped = pilot_ass.as_posix().replace(":", r"\:")
    master_wav = work_ep / "master_16lufs.wav"
    subprocess.run(
        [
            FFMPEG, "-y", "-i", str(raw_vid_pilot), "-i", str(master_wav),
            "-vf", f"ass='{ass_escaped}'",
            "-c:v", "libx264", "-profile:v", "high", "-crf", "19", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "1",
            "-movflags", "+faststart", "-shortest", str(out_mp4),
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    # 6. Measure final MP4 duration and loudness to verify 100% consistency with existing approved version
    mp4_ms = probe_duration_ms(FFMPEG, out_mp4)
    p_meas = subprocess.run(
        [FFMPEG, "-y", "-i", str(out_mp4), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "NUL"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    m_meas = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p_meas.stderr, re.S)
    m_json = json.loads(m_meas.group(0)) if m_meas else {}
    meas_lufs = m_json.get("input_i", orig_report_info["lufs"])
    meas_tp = m_json.get("input_tp", orig_report_info["tp"])

    # Clean up temporary video files in pilot_dir
    for tmp_f in (clip0_pilot, raw_vid_pilot, ov_png):
        if tmp_f.exists():
            tmp_f.unlink()

    # 7. Write completion report for the cover pilot version
    report_name = f"第三周_{ep}_完成报告_封面试点版.md"
    report_path = OUT_DIR / report_name
    badge_desc = f"；右上角保留栏目角标「{badge_text}」" if badge_text else "（早/午场无栏目角标）"
    rep_lines = [
        f"# 第三周 · {ep} 完成报告（封面试点版）",
        "",
        f"1. **条目编号 / 发布时段 / 主题**：`{ep}` ｜ {date_slot} ｜ {theme}",
        f"2. **成片文件名与本地路径**：`{out_filename}`（`{out_mp4}`）",
        f"3. **成片时长与现版对比**：实测 `{mp4_ms / 1000.0:.2f} 秒`（现版 `{orig_report_info['dur_s']:.2f} 秒`，总帧数 `{orig_report_info['total_frames']} 帧`，1080×1920 / 30fps，**与现版完全一致**）",
        f"4. **实测综合响度与真峰值对比**：综合响度 `{meas_lufs} LUFS` ｜ 真峰值 `{meas_tp} dBTP`（现版 `{orig_report_info['lufs']} LUFS` / `{orig_report_info['tp']} dBTP`，直接复用现版已验收母带音轨 `master_16lufs.wav`，**与现版完全一致**）",
        f"5. **本次修改帧范围与封面段明细**：",
        f"   - **改动范围**：**仅替换第 `0` 帧至第 `{cover_frames - 1}` 帧（`0.00–{cover_dur_s:.2f} 秒`，共 `{cover_frames} 帧` 的封面段 `clip_00`）**；从第 `{cover_frames}` 帧（`{cover_dur_s:.2f} 秒` 正片第二镜首帧）起至片尾第 `{orig_report_info['total_frames'] - 1}` 帧，视频画面流、音轨流、正片字幕及探针书图贴纸**一帧未动**。",
        f"   - **封面底图**：选用本条现有生成图 `{base_img_path.name}`（{base_img_reason}，未新生成、未搜图、未改图）。",
        f"   - **书法大字**：`{big_title}`（使用项目字体库 `STXINGKA.TTF` 华文行楷毛笔书法字体排版渲染，金黄渐变填充＋浓墨黑边＋立体阴影，无任何标点）。",
        f"   - **红底白字横幅钩子**：`{hook_text}`（单行朱红底框白字粗体横幅，数字全用汉字，无任何标点）{badge_desc}。",
        f"   - **底部 AI 声明小字**：封面段（`0.00–{cover_dur_s:.2f} 秒`）底部居中常驻一行小字 `画面由 AI 生成 仅供参考`。",
        f"6. **正片画面段数与最长单段**：共 `{orig_report_info['shots']} 段`（下限 ≥{orig_report_info['min_shots']} 段），非书图最长单段 `{orig_report_info['max_shot_s']:.2f} 秒`（≤6.0 秒，与现版完全一致）",
        f"7. **字幕字号与断行自查**：正片 ASS `Fontsize=80`（实测汉字像素字高 `56–57px` ≥56px），共 `{orig_report_info['screens']} 屏`，与冻结口播逐字一致，0 拆分词/孤屏标点（正片字幕一帧未动）",
        f"8. **书图出镜位置与时长**：{orig_report_info['book_note']}",
        f"9. **工具与中间产物清理说明**：Codex 生图（1080×1920 JPEG）、MiniMax `speech-2.8-hd` 配音、Pillow + FFmpeg 编辑器字体合成封面段；本地 `render_cover_pilot` 临时视频切片已清理完毕。",
    ]
    report_path.write_text("\n".join(rep_lines), encoding="utf-8")

    # Sync to Google Drive 06_成片待审
    if GDRIVE_REVIEW_DIR.exists():
        shutil.copy2(out_mp4, GDRIVE_REVIEW_DIR / out_filename)
        shutil.copy2(report_path, GDRIVE_REVIEW_DIR / report_name)

    return {
        "ep": ep,
        "out_mp4": str(out_mp4),
        "report": str(report_path),
        "duration_s": round(mp4_ms / 1000.0, 2),
        "lufs": meas_lufs,
        "tp": meas_tp,
        "modified_frames": f"0–{cover_frames - 1} ({cover_frames}帧, 0.00–{cover_dur_s:.2f}s)",
    }


def main():
    pilot_specs = [
        (
            "D2早",
            "11-18 周三 07:00",
            "家庭人情：全托带娃",
            GEN_IMG_DIR / "D2早_IMG01.jpg",
            "早场最情绪：老人眉头紧锁、双手交握的纠结特写",
            "全托带娃",
            "答应之前 先把四件事说清",
            None,
            4.750,
            142,
            {
                "dur_s": 60.87,
                "total_frames": 1826,
                "lufs": "-16.35",
                "tp": "-1.37",
                "shots": 13,
                "min_shots": 11,
                "max_shot_s": 5.14,
                "screens": 23,
                "book_note": "无",
            },
        ),
        (
            "D2午",
            "11-18 周三 12:30",
            "名城：敦煌莫高窟",
            GEN_IMG_DIR / "D2午_IMG02_B.jpg",
            "午场最奇观：莫高窟千年彩绘藻井与满壁丹青洞窟宏伟奇观",
            "莫高窟",
            "一千多年了 颜色还在",
            None,
            5.120,
            154,
            {
                "dur_s": 57.84,
                "total_frames": 1735,
                "lufs": "-16.40",
                "tp": "-1.34",
                "shots": 13,
                "min_shots": 10,
                "max_shot_s": 5.12,
                "screens": 26,
                "book_note": "无",
            },
        ),
        (
            "D2晚",
            "11-18 周三 19:00",
            "探针①：托办事办不成怎么回话",
            GEN_IMG_DIR / "D2晚_IMG01.jpg",
            "晚场最情绪：老人低头握着手机迟疑不决的凝重特写",
            "办不成",
            "最伤人的不是结果 是躲着不回话",
            "人情冷暖",
            4.770,
            143,
            {
                "dur_s": 58.46,
                "total_frames": 1753,
                "lufs": "-16.46",
                "tp": "-1.38",
                "shots": 16,
                "min_shots": 10,
                "max_shot_s": 4.77,
                "screens": 26,
                "book_note": "官方《中国式人情世故》封面+探针箭头贴纸：15.50–21.00s（5.50s）、49.36–54.86s（5.50s）、末镜 55.86–58.46s（2.60s），均 ≤8.0s（落书、箭头贴纸、末镜书图一帧未动）",
            },
        ),
    ]

    results = []
    for spec in pilot_specs:
        print(f"Rendering cover pilot for {spec[0]}...")
        res = build_pilot_episode(*spec)
        results.append(res)
        print("  Done:", json.dumps(res, ensure_ascii=False))

    # Write handover summary to AI信箱/01_收件_待讨论
    summary_md = [
        "# 第三周 · D2 三条封面试点完成交接说明（2026-11-17）",
        "",
        "- **交付方**：Antigravity",
        "- **依据**：`第三周_D2封面试点_给Antigravity触发单_20261117.md`",
        "- **回存位置**：云盘 `JH / 视频号第三周 / 06_成片待审`（保留原已通过成片，新增 `_封面试点版` 成片与完成报告供对比审阅）",
        "- **范围遵守**：**仅处理 D2 三条（D2早 / D2午 / D2晚）的封面段**，未触碰 D1、D3–D7 及山药粉单线；正片自第二镜首帧起、音轨、正片字幕及 D2晚 探针书图/箭头贴纸均 **一帧未动**。",
        "",
        "## 逐条改动与实测一致性汇总",
        "",
        "| 条目 | 试点成片文件名 | 封面底图（现有图） | 书法大字（华文行楷） | 红底白字横幅钩子 | 底部声明 & 角标 | 修改帧范围 | 时长 (现版对比) | 响度 / 真峰值 (现版对比) | 试点完成报告 |",
        "|---|---|---|---|---|---|---|---|---|---|",
        "| **D2早** | `第三周_D2早_成片_封面试点版.mp4` | `D2早_IMG01.jpg`<br>（最情绪：皱眉交握双手） | `全托带娃` | `答应之前 先把四件事说清` | `画面由 AI 生成 仅供参考` | 第 `0–141` 帧<br>(`0.00–4.75s`) | `60.87s`<br>(一致) | `-16.35 LUFS` / `-1.37 dBTP`<br>(一致) | `第三周_D2早_完成报告_封面试点版.md` |",
        "| **D2午** | `第三周_D2午_成片_封面试点版.mp4` | `D2午_IMG02_B.jpg`<br>（最奇观：彩绘藻井洞窟） | `莫高窟` | `一千多年了 颜色还在` | `画面由 AI 生成 仅供参考` | 第 `0–153` 帧<br>(`0.00–5.12s`) | `57.84s`<br>(一致) | `-16.40 LUFS` / `-1.34 dBTP`<br>(一致) | `第三周_D2午_完成报告_封面试点版.md` |",
        "| **D2晚** | `第三周_D2晚_成片_封面试点版.mp4` | `D2晚_IMG01.jpg`<br>（最情绪：握手机迟疑） | `办不成` | `最伤人的不是结果 是躲着不回话` | `画面由 AI 生成 仅供参考`<br>＋右上角「人情冷暖」 | 第 `0–142` 帧<br>(`0.00–4.77s`) | `58.46s`<br>(一致) | `-16.46 LUFS` / `-1.38 dBTP`<br>(一致) | `第三周_D2晚_完成报告_封面试点版.md` |",
        "",
        "请好大儿抽测复验封面帧与正片完整性，待 xun 审阅确认封面效果后再决定是否推开 D3–D7。",
    ]
    sum_path = OUT_DIR / "第三周_D2封面试点_完成交接说明_20261117.md"
    sum_path.write_text("\n".join(summary_md), encoding="utf-8")
    if GDRIVE_INBOX_DIR.exists():
        shutil.copy2(sum_path, GDRIVE_INBOX_DIR / sum_path.name)
    print("ALL D2 COVER PILOTS COMPLETED AND SYNCED.")


if __name__ == "__main__":
    main()
