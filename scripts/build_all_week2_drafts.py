#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build All Week 2 Drafts (早场 D1-D7, 午场 D1-D7, 晚场 D1-D7)
"""

import os
import sys
import json
import asyncio
import shutil
import zipfile
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import edge_tts
import pymediainfo
import pyJianYingDraft as draft

ROOT = Path("D:/fuye")
GDRIVE = Path("G:/我的云端硬盘")
WEEK2_DIR = GDRIVE / "视频号第二周"
WEEK1_DIR = GDRIVE / "视频号第一周"

JIANYING_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "JianyingPro/User Data/Projects/com.lveditor.draft"
BGM_PATH = ROOT / "01_配音与音色库" / "背景音乐库" / "bgm_shili_guofeng.mp3"
IMG_GEN_DIR = WEEK2_DIR / "03_图片需求" / "生成图片"

# 官方书图路径
BOOK_MAP = {
    "冷门知识1000问": WEEK1_DIR / "03_书图" / "冷门知识1000问" / "冷门知识1000问_封面.jpg",
    "2027古诗日历": WEEK1_DIR / "03_书图" / "2027古诗日历" / "古诗日历_主图.jpg",
    "戒掉手机自律书": WEEK1_DIR / "03_书图" / "戒掉手机自律书" / "戒掉手机自律书_封面.jpg",
    "中国人的规矩": WEEK1_DIR / "03_书图" / "中国人的规矩" / "中国人的规矩_封面.jpg",
    "中国式人情世故": WEEK1_DIR / "03_书图" / "中国式人情世故" / "中国式人情世故_封面.jpg",
    "被遗忘的后半句": WEEK1_DIR / "03_书图" / "被遗忘的后半句" / "被遗忘的后半句_封面.jpg",
}

# 封面大字
COVER_TEXT_MAP = {
    "早场": {
        "D1": "哈气为什么冒白烟",
        "D2": "背诗，先看一幅画",
        "D3": "月亮为什么跟着我",
        "D4": "磨蹭，是顺序错了",
        "D5": "海水为什么是咸的",
        "D6": "门把手为什么电人",
        "D7": "约定立了，为什么废",
    },
    "午场": {
        "D1": "长城砖缝里，藏着明朝工单",
        "D2": "西安城墙，真掺了糯米",
        "D3": "丽江古城没城墙，靠水守城",
        "D4": "平遥汇票，防伪靠顺口溜",
        "D5": "开封脚下，睡着六个朝代",
        "D6": "泉州双塔，千年为什么不倒",
        "D7": "哈尔滨面包石，百年不滑",
    },
    "晚场": {
        "D1": "饭桌上，这三样别做",
        "D2": "借钱时，别说这三句",
        "D3": "这句老话，被改软了",
        "D4": "探望病人，三带三不带",
        "D5": "对儿女，这三句别说",
        "D6": "出份子，不等于随份子",
        "D7": "老朋友，贵在一种",
    }
}

# 书图分配
BOOK_ASSIGNMENT = {
    "早场": {
        "D1": "冷门知识1000问", "D2": "2027古诗日历", "D3": "冷门知识1000问",
        "D4": "戒掉手机自律书", "D5": "冷门知识1000问", "D6": "冷门知识1000问", "D7": "戒掉手机自律书"
    },
    "午场": {
        "D1": "冷门知识1000问", "D2": "冷门知识1000问", "D3": "冷门知识1000问",
        "D4": "冷门知识1000问", "D5": "冷门知识1000问", "D6": "冷门知识1000问", "D7": "冷门知识1000问"
    },
    "晚场": {
        "D1": "中国人的规矩", "D2": "中国式人情世故", "D3": "被遗忘的后半句",
        "D4": "中国人的规矩", "D5": "被遗忘的后半句", "D6": "中国人的规矩", "D7": "中国式人情世故"
    }
}

def safe_copy(src, dst):
    src = Path(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(src, "rb") as fsrc:
        with open(dst, "wb") as fdst:
            shutil.copyfileobj(fsrc, fdst)

def get_audio_duration_us(path: Path) -> int:
    try:
        mi = pymediainfo.MediaInfo.parse(str(path))
        for t in mi.tracks:
            if t.track_type == "Audio":
                return int(float(t.duration) * 1000)
    except Exception:
        pass
    return 3_000_000

def get_chinese_font(size: int = 40):
    for fp in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/simhei.ttf"]:
        if Path(fp).exists():
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return ImageFont.load_default()

def create_placeholder(path: Path, shot_name: str, desc: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = 1080, 1920
    im = Image.new("RGB", (width, height), color=(24, 26, 30))
    draw = ImageDraw.Draw(im)
    draw.rectangle([30, 30, width - 30, height - 30], outline=(180, 150, 70), width=4)
    draw.rectangle([40, 40, width - 40, height - 40], outline=(100, 85, 40), width=2)
    font_title = get_chinese_font(52)
    font_desc = get_chinese_font(36)
    
    draw.text((width // 2, height // 2 - 120), "[ 待 Codex 生成素材 ]", fill=(180, 150, 70), font=font_title, anchor="mm")
    draw.text((width // 2, height // 2), shot_name, fill=(255, 255, 255), font=font_title, anchor="mm")
    draw.text((width // 2, height // 2 + 100), desc[:40], fill=(200, 200, 200), font=font_desc, anchor="mm")
    im.save(str(path), "JPEG", quality=85)

def create_cover_card(path: Path, hook_img_path: Path, cover_text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = 1080, 1920
    if hook_img_path.exists() and hook_img_path.is_file():
        try:
            im = Image.open(str(hook_img_path)).convert("RGB").resize((width, height))
        except Exception:
            im = Image.new("RGB", (width, height), color=(30, 30, 35))
    else:
        im = Image.new("RGB", (width, height), color=(30, 30, 35))
    draw = ImageDraw.Draw(im)
    draw.rectangle([0, 250, width, 550], fill=(0, 0, 0, 180))
    font_cover = get_chinese_font(68)
    draw.text((width // 2, 400), cover_text, fill=(255, 220, 50), font=font_cover, anchor="mm")
    im.save(str(path), "JPEG", quality=90)

VOICE_CFG = {
    "孩子": {"voice": "zh-CN-XiaoyiNeural", "rate": "+4%", "pitch": "+12Hz"},
    "爷爷": {"voice": "zh-CN-YunjianNeural", "rate": "-8%", "pitch": "-6Hz"},
    "奶奶": {"voice": "zh-CN-XiaoxiaoNeural", "rate": "-8%", "pitch": "-4Hz"},
    "女声": {"voice": "zh-CN-XiaoxiaoNeural", "rate": "+5%", "pitch": "+0Hz"},
    "男声": {"voice": "zh-CN-YunxiNeural", "rate": "+0%", "pitch": "+0Hz"},
    "讲述": {"voice": "zh-CN-YunjianNeural", "rate": "-8%", "pitch": "-6Hz"},
    "午场爷爷": {"voice": "zh-CN-YunjianNeural", "rate": "-8%", "pitch": "-6Hz"},
    "晚场爷爷": {"voice": "zh-CN-YunjianNeural", "rate": "-10%", "pitch": "-6Hz"},
    "晚场奶奶": {"voice": "zh-CN-XiaoxiaoNeural", "rate": "-10%", "pitch": "-4Hz"},
}

COLOR_MAP = {
    "孩子": (1.0, 1.0, 1.0),       # 白色
    "爷爷": (1.0, 0.82, 0.2),      # 暖黄
    "奶奶": (1.0, 0.60, 0.67),     # 暖粉
    "女声": (0.8, 0.8, 0.8),       # 画外音灰色
    "男声": (0.8, 0.8, 0.8),       # 画外音灰色
}

def parse_audio_script(p: Path):
    content = p.read_text(encoding="utf-8")
    days = {}
    current_day = None
    for line in content.splitlines():
        line = line.strip()
        m_day = re.match(r"^##\s+(D\d+)\s*[·\s]*(.*?)$", line)
        if m_day:
            current_day = m_day.group(1)
            days[current_day] = {"title": m_day.group(2), "items": []}
            continue
        if current_day and line.startswith("- S"):
            m_item = re.match(r"^-\s+(S\d+)\s*｜\s*([^｜]+)\s*｜\s*(.*)$", line)
            if m_item:
                sid, role_info, text = m_item.groups()
                role = role_info.split("·")[0].strip()
                days[current_day]["items"].append({
                    "id": sid,
                    "role_info": role_info,
                    "role": role,
                    "raw_text": text
                })
    return days

def parse_shots(p: Path):
    content = p.read_text(encoding="utf-8")
    days = {}
    current_day = None
    for line in content.splitlines():
        line = line.strip()
        m_day = re.match(r"^##\s+(D\d+)\s*[·\s]*(.*?)$", line)
        if m_day:
            current_day = m_day.group(1)
            days[current_day] = []
            continue
        if current_day and (line.startswith("- IMG_") or line.startswith("IMG_")):
            m_shot = re.match(r"^[-*]?\s*(IMG_[DdWwNn]\d+_\d+)\s*(.*)$", line)
            if m_shot:
                sname, desc = m_shot.groups()
                days[current_day].append({
                    "name": sname,
                    "desc": desc.strip("：: ")
                })
    return days

async def synth_line(text: str, voice_key: str, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cfg = VOICE_CFG.get(voice_key, VOICE_CFG["讲述"])
    clean_text = re.sub(r"[\*#]+", "", text)
    clean_text = clean_text.replace("/", " ").replace("——", " ")
    comm = edge_tts.Communicate(clean_text, cfg["voice"], rate=cfg["rate"], pitch=cfg["pitch"])
    await comm.save(str(out_path))

async def assemble_single_video(session_name: str, day_str: str, script_data: dict, shot_list: list):
    day_num = int(day_str.replace("D", ""))
    proj_title = f"成片_{day_str}_{session_name}"
    prefix = "AUD_D" if session_name == "早场" else ("AUD_N" if session_name == "午场" else "AUD_W")
    
    cover_text = COVER_TEXT_MAP[session_name][day_str]
    book_key = BOOK_ASSIGNMENT[session_name][day_str]
    book_path = BOOK_MAP[book_key]

    print(f"\n==========================================")
    print(f">>> 开始装配: {proj_title} ({session_name} {day_str})")
    print(f"==========================================")

    local_proj_dir = ROOT / "03_视频成片与工程" / proj_title
    local_audio_dir = local_proj_dir / "03_配音音频"
    local_visual_dir = local_proj_dir / "02_分镜视觉素材"
    local_proj_dir.mkdir(parents=True, exist_ok=True)
    local_audio_dir.mkdir(parents=True, exist_ok=True)
    local_visual_dir.mkdir(parents=True, exist_ok=True)

    # 1. 解析句子与切分子幕
    sentences = []
    items = script_data["items"]
    num_sents = len(items)
    num_shots = len(shot_list)

    middle_sents = list(range(1, num_sents - 1))
    middle_shots_count = num_shots - 2
    
    shot_sentence_map = {0: [0], num_shots - 1: [num_sents - 1]}
    if middle_shots_count > 0:
        k, m = divmod(len(middle_sents), middle_shots_count)
        start_idx = 0
        for i in range(middle_shots_count):
            end_idx = start_idx + k + (1 if i < m else 0)
            shot_sentence_map[i + 1] = middle_sents[start_idx:end_idx]
            start_idx = end_idx

    sent_to_shot_idx = {}
    for shot_i, s_indices in shot_sentence_map.items():
        for si in s_indices:
            sent_to_shot_idx[si] = shot_i

    # 逐句生成 TTS 音频占位文件
    cur_time_us = 0
    for s_idx, item in enumerate(items):
        sent_id = f"{prefix}{day_num}_{item['id']}"
        raw_text = item["raw_text"]
        
        if session_name == "早场":
            v_key = item["role"]
        elif session_name == "午场":
            v_key = "午场爷爷"
        else: # 晚场
            v_key = "晚场奶奶" if (day_str == "D5" and item["role"] == "奶奶") else "晚场爷爷"

        af = local_audio_dir / f"{sent_id}.mp3"
        if not af.exists() or af.stat().st_size == 0:
            await synth_line(raw_text, v_key, af)

        dur_us = get_audio_duration_us(af)
        gap_us = 300_000 if s_idx < num_sents - 1 else 0

        parts = [p.strip() for p in re.split(r"[/]+", raw_text) if p.strip()]
        sub_list = []
        for p in parts:
            clean_p = re.sub(r"[\*#]+", "", p).strip()
            if not clean_p:
                continue
            if session_name == "早场":
                sub_list.append(f"{item['role']}：{clean_p}")
            else:
                sub_list.append(clean_p)

        sentences.append({
            "id": sent_id,
            "role": item["role"],
            "raw_text": raw_text,
            "audio_file": str(af),
            "start_us": cur_time_us,
            "dur_us": dur_us,
            "end_us": cur_time_us + dur_us,
            "shot_idx": sent_to_shot_idx.get(s_idx, 0),
            "subtitles": sub_list
        })
        cur_time_us += dur_us + gap_us

    total_audio_dur_us = cur_time_us
    total_sec = round(total_audio_dur_us / 1_000_000, 2)
    print(f"  A1 人声音轨就绪，总计 {num_sents} 句，总时长: {total_sec} 秒")

    # 2. 镜头画面匹配
    shot_files = {}
    missing_materials = []

    for s_idx, shot in enumerate(shot_list):
        s_name = shot["name"]
        desc = shot["desc"]
        is_book = (s_idx == num_shots - 1)

        real_file = None
        if is_book:
            if book_path.exists():
                real_file = book_path
        else:
            cands = [
                IMG_GEN_DIR / s_name,
                IMG_GEN_DIR / f"{s_name}.png",
                IMG_GEN_DIR / f"{s_name}.jpg",
            ]
            for c in cands:
                if c.exists() and c.is_file():
                    real_file = c
                    break

        if real_file:
            target_local = local_visual_dir / real_file.name
            if not target_local.exists():
                safe_copy(real_file, target_local)
            shot_files[s_idx] = target_local
        else:
            missing_materials.append(s_name)
            placeholder_path = local_visual_dir / f"placeholder_{s_name}.jpg"
            create_placeholder(placeholder_path, s_name, desc)
            shot_files[s_idx] = placeholder_path

    # 计算镜头时间
    shot_timings = {}
    for s_idx in range(num_shots):
        sents_in_shot = [s for s in sentences if s["shot_idx"] == s_idx]
        if sents_in_shot:
            s_start = sents_in_shot[0]["start_us"]
            s_end = sents_in_shot[-1]["end_us"]
            if s_idx == num_shots - 1:
                s_end = max(s_end, total_audio_dur_us)
            shot_timings[s_idx] = {"start_us": s_start, "dur_us": s_end - s_start, "end_us": s_end}
        else:
            shot_timings[s_idx] = {"start_us": 0, "dur_us": total_audio_dur_us // num_shots, "end_us": total_audio_dur_us}

    # 3. 装配剪映草稿工程
    folder = draft.DraftFolder(str(JIANYING_DIR))
    script = folder.create_draft(proj_title, width=1080, height=1920, fps=30, allow_replace=True)

    v1_track = draft.TrackSpec(draft.TrackType.video, name="V1_正片画面")
    v2_track = draft.TrackSpec(draft.TrackType.video, name="V2_书图与封面")
    a1_track = draft.TrackSpec(draft.TrackType.audio, name="A1_人声")
    a2_track = draft.TrackSpec(draft.TrackType.audio, name="A2_BGM(-18dB)")
    sub_track = draft.TrackSpec(draft.TrackType.text, name="字幕轨")

    script.append_track(v1_track)
    script.append_track(v2_track)
    script.append_track(a1_track)
    script.append_track(a2_track)
    script.append_track(sub_track)

    # A1 轨：逐句上轨
    for sent in sentences:
        a_seg = draft.AudioSegment(
            sent["audio_file"],
            draft.Timerange(sent["start_us"], sent["dur_us"]),
            volume=1.4125
        )
        script.add_segment(a_seg, track="A1_人声")

    # A2 轨：BGM (-18dB)
    if BGM_PATH.exists():
        bgm_dur_us = get_audio_duration_us(BGM_PATH)
        cur_bgm_us = 0
        chunk_idx = 0
        while cur_bgm_us < total_audio_dur_us:
            chunk_len = min(bgm_dur_us, total_audio_dur_us - cur_bgm_us)
            b_seg = draft.AudioSegment(
                str(BGM_PATH),
                draft.Timerange(cur_bgm_us, chunk_len),
                source_timerange=draft.Timerange(0, chunk_len),
                volume=0.12589 # -18dB
            )
            fade_in = 1_000_000 if chunk_idx == 0 else 0
            fade_out = 2_500_000 if (cur_bgm_us + chunk_len >= total_audio_dur_us) else 0
            if fade_in > 0 or fade_out > 0:
                b_seg.add_fade(fade_in, fade_out)
            script.add_segment(b_seg, track="A2_BGM(-18dB)")
            cur_bgm_us += chunk_len
            chunk_idx += 1

    # V1 轨：正片画面按镜号顺序排，全静态图缓慢推拉
    for s_idx in range(num_shots):
        img_file = shot_files[s_idx]
        st = shot_timings[s_idx]
        v_seg = draft.VideoSegment(str(img_file), draft.Timerange(st["start_us"], st["dur_us"]))
        
        try:
            with Image.open(str(img_file)) as im:
                w, h = im.size
                if w >= h or w / h > 0.6:
                    v_seg.add_background_filling("blur", blur=0.375)
        except Exception:
            pass

        v_seg.add_keyframe(draft.KeyframeProperty.uniform_scale, 0, 1.0)
        v_seg.add_keyframe(draft.KeyframeProperty.uniform_scale, st["dur_us"], 1.06)
        script.add_segment(v_seg, track="V1_正片画面")

    # V2 轨：首帧封面与末镜书图
    cover_img_path = local_visual_dir / f"cover_{proj_title}.jpg"
    create_cover_card(cover_img_path, shot_files[0], cover_text)
    v2_cover_seg = draft.VideoSegment(str(cover_img_path), draft.Timerange(0, 500_000))
    script.add_segment(v2_cover_seg, track="V2_书图与封面")

    if book_path.exists():
        st_last = shot_timings[num_shots - 1]
        v2_book_seg = draft.VideoSegment(str(book_path), draft.Timerange(st_last["start_us"], st_last["dur_us"]))
        v2_book_seg.add_background_filling("blur", blur=0.375)
        v2_book_seg.add_keyframe(draft.KeyframeProperty.uniform_scale, 0, 1.0)
        v2_book_seg.add_keyframe(draft.KeyframeProperty.uniform_scale, st_last["dur_us"], 1.05)
        script.add_segment(v2_book_seg, track="V2_书图与封面")

    # 字幕轨
    sub_border = draft.TextBorder(color=(0.0, 0.0, 0.0), width=40.0)
    sub_bg = draft.TextBackground(color="#000000", alpha=0.6, round_radius=0.15)
    sub_clip = draft.ClipSettings(transform_y=-0.573)

    for sent in sentences:
        subs = sent["subtitles"]
        s_start = sent["start_us"]
        s_dur = sent["dur_us"]
        sub_chunk_dur = s_dur // len(subs) if subs else s_dur
        for c_i, sub_text in enumerate(subs):
            c_start = s_start + c_i * sub_chunk_dur
            c_dur = sub_chunk_dur if c_i < len(subs) - 1 else (s_start + s_dur - c_start)
            
            if session_name == "早场":
                col = COLOR_MAP.get(sent["role"], (1.0, 1.0, 1.0))
            else:
                col = (1.0, 1.0, 1.0) # 午场、晚场纯白
            st_style = draft.TextStyle(size=11.0, bold=True, color=col, align=1)
            
            t_seg = draft.TextSegment(
                sub_text,
                draft.Timerange(c_start, c_dur),
                style=st_style,
                border=sub_border,
                background=sub_bg,
                clip_settings=sub_clip
            )
            script.add_segment(t_seg, track="字幕轨")

    # 保存剪映工程
    script.save()
    jianying_draft_path = JIANYING_DIR / proj_title
    print(f"  剪映草稿已保存: {jianying_draft_path}")

    # 云端与本地备份
    cloud_drafts_dir = WEEK2_DIR / "06_成片待审" / "01_剪映草稿工程"
    cloud_drafts_dir.mkdir(parents=True, exist_ok=True)

    for jf in ["draft_content.json", "draft_meta_info.json"]:
        src = jianying_draft_path / jf
        if src.exists():
            safe_copy(src, local_proj_dir / jf)

    # 复制工程文件夹到云端
    cloud_proj_folder = cloud_drafts_dir / proj_title
    if cloud_proj_folder.exists():
        shutil.rmtree(cloud_proj_folder)
    shutil.copytree(jianying_draft_path, cloud_proj_folder, copy_function=safe_copy)

    # 打包 zip
    zip_path = cloud_drafts_dir / f"{proj_title}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root_p, _, files in os.walk(jianying_draft_path):
            for f in files:
                full_p = Path(root_p) / f
                arcname = full_p.relative_to(jianying_draft_path.parent)
                zf.write(full_p, arcname)

    manifest_path = local_proj_dir / "draft_manifest.json"
    manifest_data = {
        "name": proj_title,
        "session": session_name,
        "day": day_str,
        "total_duration_sec": total_sec,
        "missing_materials": missing_materials,
        "sentences_count": num_sents,
        "shots_count": num_shots
    }
    manifest_path.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2), encoding="utf-8")

    missing_str = "、".join(missing_materials) if missing_materials else "无"
    return {
        "session": session_name,
        "day": day_str,
        "name": proj_title,
        "duration": f"{total_sec}秒",
        "missing": missing_str,
        "missing_count": len(missing_materials)
    }

async def main():
    print("=== 开始批量装配第二周 早场(对话版)、午场(无书版)、晚场 D1 到 D7 ===")
    
    p_m_script = Path("G:/我的云端硬盘/视频号第二周/02_音频脚本/第二周_早场音频制作脚本.md")
    p_n_script = Path("G:/我的云端硬盘/视频号第二周/02_音频脚本/第二周_午场音频制作脚本.md")
    p_w_script = Path("G:/我的云端硬盘/视频号第二周/02_音频脚本/第二周_晚场音频制作脚本.md")

    p_m_shots = Path("G:/我的云端硬盘/视频号第二周/03_图片需求/第二周_早场图片需求清单.md")
    p_n_shots = Path("G:/我的云端硬盘/视频号第二周/03_图片需求/第二周_午场图片需求清单.md")
    p_w_shots = Path("G:/我的云端硬盘/视频号第二周/03_图片需求/第二周_晚场图片需求清单.md")

    scripts_all = {
        "早场": parse_audio_script(p_m_script),
        "午场": parse_audio_script(p_n_script),
        "晚场": parse_audio_script(p_w_script)
    }

    shots_all = {
        "早场": parse_shots(p_m_shots),
        "午场": parse_shots(p_n_shots),
        "晚场": parse_shots(p_w_shots)
    }

    results = []

    # 1. 处理早场 (D1 - D7)
    for day in range(1, 8):
        d_str = f"D{day}"
        res = await assemble_single_video("早场", d_str, scripts_all["早场"][d_str], shots_all["早场"][d_str])
        results.append(res)

    # 2. 处理午场 (D1 - D7)
    for day in range(1, 8):
        d_str = f"D{day}"
        res = await assemble_single_video("午场", d_str, scripts_all["午场"][d_str], shots_all["午场"][d_str])
        results.append(res)

    # 3. 处理晚场 (D1 - D7)
    for day in range(1, 8):
        d_str = f"D{day}"
        res = await assemble_single_video("晚场", d_str, scripts_all["晚场"][d_str], shots_all["晚场"][d_str])
        results.append(res)

    print("\n" + "="*50)
    print("=== 全周 21 条视频装配汇总报告 ===")
    print("="*50)
    for r in results:
        print(f"已装配 {r['session']}{r['day']}、总时长 {r['duration']}、缺失素材：{r['missing']}")

if __name__ == "__main__":
    asyncio.run(main())
