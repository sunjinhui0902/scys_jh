#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Finalize Week 2 Production:
配音新音色重配 -> 剪映工程装配 -> 成片 MP4 极速渲染与云端上传
"""

import os
import sys
import json
import re
import time
import shutil
import zipfile
import asyncio
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path("D:/fuye")
GDRIVE = Path("G:/我的云端硬盘")
WEEK2_DIR = GDRIVE / "视频号第二周"
WEEK1_DIR = GDRIVE / "视频号第一周"

sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "04_自动化生产流水线"))
import voice_api_tts
from workspace_paths import ffmpeg
import edge_tts
import pymediainfo
import pyJianYingDraft as draft

FFMPEG_EXE = ffmpeg()
JIANYING_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "JianyingPro/User Data/Projects/com.lveditor.draft"
BGM_PATH = ROOT / "01_配音与音色库" / "背景音乐库" / "bgm_shili_guofeng.mp3"
IMG_GEN_DIR = WEEK2_DIR / "03_图片需求" / "生成图片"
OUT_REVIEW_DIR = WEEK2_DIR / "06_成片待审"

# 官方书图路径
BOOK_MAP = {
    "冷门知识1000问": WEEK1_DIR / "03_书图" / "冷门知识1000问" / "冷门知识1000问_封面.jpg",
    "2027古诗日历": WEEK1_DIR / "03_书图" / "2027古诗日历" / "古诗日历_主图.jpg",
    "戒掉手机自律书": WEEK1_DIR / "03_书图" / "戒掉手机自律书" / "戒掉手机自律书_封面.jpg",
    "中国人的规矩": WEEK1_DIR / "03_书图" / "中国人的规矩" / "中国人的规矩_封面.jpg",
    "中国式人情世故": WEEK1_DIR / "03_书图" / "中国式人情世故" / "中国式人情世故_封面.jpg",
    "被遗忘的后半句": WEEK1_DIR / "03_书图" / "被遗忘的后半句" / "被遗忘的后半句_封面.jpg",
}

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
    draw.rectangle([0, 250, width, 550], fill=(0, 0, 0, 190))
    font_cover = get_chinese_font(68)
    draw.text((width // 2, 400), cover_text, fill=(255, 220, 50), font=font_cover, anchor="mm")
    im.save(str(path), "JPEG", quality=92)

# ==================== 音频脚本与镜头解析 ====================
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

# ==================== 读音规则与 TTS 文本预处理 ====================
def clean_sub_text(text: str) -> str:
    """
    清洗字幕文本：去除任何角色前缀（爸爸、妈妈、爷爷、奶奶、孩子、女声、男声、讲述等）与所有标点符号。
    """
    # 1. 彻底去除任何角色提示词前缀
    text = re.sub(r"^(孩子|爷爷|奶奶|爸爸|妈妈|女声|男声|讲述)[：:\s·]*", "", text)
    # 2. 去除 markdown 粗体/强调标记
    text = re.sub(r"[\*#]+", "", text)
    # 3. 叠呼词如 奶奶奶奶 / 爷爷爷爷 拆为 奶奶 奶奶 / 爷爷 爷爷
    text = re.sub(r"^(奶奶){2}", "奶奶 奶奶", text)
    text = re.sub(r"^(爷爷){2}", "爷爷 爷爷", text)
    # 4. 去除封闭性标点（书名号、双引号、单引号、括号等）
    text = re.sub(r"[《》“”‘’\"\'（）\(\)\[\]【】]", "", text)
    # 5. 将破折号、连接号替换为空格
    text = re.sub(r"[—–\-]+", " ", text)
    # 6. 将所有中英文标点符号替换为空格
    text = re.sub(r"[，。！？!?；;:…、·]+", " ", text)
    # 7. 合并多余连续空格并 strip
    text = re.sub(r"\s+", " ", text).strip()
    return text

def prepare_tts_text(raw_text: str, role: str, session: str, day: str, engine: str) -> str:
    """
    根据读音清单与停顿符号，生成最适合 TTS 朗读的文本。
    """
    text = raw_text.strip()
    
    # 1. 数字读法硬规矩
    text = text.replace("《冷门知识1000问》", "《冷门知识一千问》")
    text = text.replace("1000问", "一千问")
    text = text.replace("一千个问题", "一千个问题")
    text = text.replace("2027", "二零二七")
    text = text.replace("1823", "一八二三")
    text = text.replace("1604", "一六零四")
    text = text.replace("1924", "一九二四")
    
    # 2. 多音字与地名生僻字注音保障
    if session == "早场":
        if day == "D1":
            text = text.replace("哈气", "哈气")
        elif day == "D4":
            text = text.replace("磨蹭", "磨蹭")
        elif day == "D5":
            text = text.replace("攒咸的", "攒咸的")
        elif day == "D6":
            text = text.replace("攒的电", "攒的电")
    elif session == "午场":
        if day == "D1":
            text = text.replace("模印", "木印") # 确保 mú 发音
        elif day == "D4":
            text = text.replace("1823年", "一八二三年")
        elif day == "D6":
            text = text.replace("1604年", "一六零四年")
        elif day == "D7":
            text = text.replace("1924年", "一九二四年")
    elif session == "晚场":
        if day == "D1":
            text = text.replace("亲家", "庆家") # 确保 qìng 发音
        elif day == "D3":
            text = text.replace("量小非君子", "亮小非君子") # 确保 liàng 发音
        elif day == "D5":
            text = text.replace("指望", "指望")
        elif day == "D6":
            text = text.replace("出份子", "出份子").replace("随份子", "随份子")

    # 去掉 markdown 粗体标记
    clean_text = re.sub(r"\*\*([^\*]+)\*\*", r"\1", text)
    clean_text = clean_text.replace("——", "，").replace("—", "，")

    # 3. 停顿处理
    if engine == "minimax":
        # MiniMax 原生停顿语法: // -> <#0.8#>, / -> <#0.3#>
        clean_text = clean_text.replace("//", "<#0.8#>").replace("/", "<#0.3#>")
    else: # edge
        # Edge-TTS: // -> …… ， / -> ，
        clean_text = clean_text.replace("//", "…… ").replace("/", "， ")

    return clean_text

# ==================== 音频合成执行 ====================
async def synthesize_sentence(cfg: dict, role_cfg: dict, item: dict, session: str, day: str, target: Path):
    role = item["role"]
    role_info = item["role_info"]
    raw_text = item["raw_text"]
    
    # 角色映射与引擎选择
    if session == "早场":
        if role == "孩子":
            r_key = "boy"
        elif role == "爷爷":
            r_key = "grandpa"
        elif role == "奶奶":
            r_key = "grandma"
        elif role == "女声":
            r_key = "mom"
        elif role == "男声":
            r_key = "dad"
        else:
            r_key = "boy"
    elif session == "午场":
        r_key = "grandpa"
    else: # 晚场
        r_key = "grandma" if (day == "D5" and role == "奶奶") else "grandpa"

    c_role = role_cfg[r_key]
    engine = c_role["engine"]
    tts_text = prepare_tts_text(raw_text, role, session, day, engine)

    # 语速与情绪微调
    is_slow = ("慢讲" in role_info or "放慢" in role_info or "语重心长" in role_info)
    is_fast = ("急躁" in role_info or "语速快" in role_info)

    if engine == "edge":
        # 爷爷统一走免费 Edge-TTS
        # 基准: rate="-10%", pitch="-8Hz"
        rate_val = -10
        if session == "晚场":
            rate_val -= 2 # 晚场再慢一档
        if is_slow:
            rate_val -= 4
        elif is_fast:
            rate_val += 4
        
        edge_rate = f"{rate_val:+d}%"
        edge_pitch = c_role.get("edge_pitch", "-8Hz")
        edge_voice = c_role.get("edge_voice", "zh-CN-YunjianNeural")

        comm = edge_tts.Communicate(tts_text, edge_voice, rate=edge_rate, pitch=edge_pitch, volume="+0%")
        await comm.save(str(target))
        return {
            "engine": "edge",
            "voice": edge_voice,
            "characters": len(tts_text),
            "paid": False
        }
    else:
        # MiniMax 合成 (boy, girl, dad, mom, grandma)
        if role == "孩子" or r_key == "boy":
            speed = 1.50 # 用户明确要求：如果是孩子 语速放快到1.5倍
        else:
            speed = float(c_role.get("speed", 1.0))
            if is_slow:
                speed = round(speed * 0.94, 2)
            elif is_fast:
                speed = round(speed * 1.05, 2)
        
        line_req = {
            "voice_id": c_role["voice_id"],
            "speed": speed,
            "pitch": int(c_role.get("pitch", 0)),
            "vol": float(c_role.get("vol", 1.0)),
            "text": tts_text
        }
        res = voice_api_tts.synthesize_minimax(cfg, line_req, target)
        return {
            "engine": "minimax",
            "voice": c_role["voice_id"],
            "characters": res.get("usage_characters", len(tts_text)),
            "trace_id": res.get("trace_id"),
            "paid": True
        }

# ==================== ASS 字幕与 MP4 渲染 ====================
def ms_to_ass_time(ms: int) -> str:
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    cs = (ms % 1000) // 10
    return f"{h:01d}:{m:02d}:{s:02d}.{cs:02d}"

def render_mp4(proj_dir: Path, out_mp4: Path, manifest: dict, shot_files: list, sentences: list, session: str, cover_card_img: Path):
    total_dur_us = manifest["total_duration_sec"] * 1_000_000
    total_dur_s = manifest["total_duration_sec"]
    
    work_dir = proj_dir / "05_成片"
    work_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = work_dir / "_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 1. 构建 ASS 字幕文件
    ass_file = temp_dir / "subtitles.ass"
    ass_lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        # 爷爷暖黄: &H0033D1FF (BGR)
        "Style: Grandpa,Microsoft YaHei,52,&H0033D1FF,&H00000000,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,3,14,0,2,40,40,210,1",
        # 奶奶暖粉: &H00AB99FF
        "Style: Grandma,Microsoft YaHei,52,&H00AB99FF,&H00000000,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,3,14,0,2,40,40,210,1",
        # 孩子纯白: &H00FFFFFF
        "Style: Child,Microsoft YaHei,52,&H00FFFFFF,&H00000000,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,3,14,0,2,40,40,210,1",
        # 画外音灰: &H00CCCCCC
        "Style: Narrator,Microsoft YaHei,52,&H00CCCCCC,&H00000000,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,3,14,0,2,40,40,210,1",
        # 通用大字 (午场/晚场纯白底衬)
        "Style: Standard,Microsoft YaHei,54,&H00FFFFFF,&H00000000,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,3,16,0,2,40,40,210,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    ]

    for sent in sentences:
        s_ms = sent["start_us"] // 1000
        e_ms = sent["end_us"] // 1000
        role = sent["role"]
        
        # 确定样式
        if session == "早场":
            if role == "爷爷":
                style_name = "Grandpa"
            elif role == "奶奶":
                style_name = "Grandma"
            elif role in ("女声", "男声"):
                style_name = "Narrator"
            else:
                style_name = "Child"
        else:
            style_name = "Standard"

        # 字幕按断句点切分子片段
        subs = sent["subtitles"]
        num_c = len(subs)
        chunk_ms = (e_ms - s_ms) // num_c if num_c > 0 else (e_ms - s_ms)
        for c_idx, sub_t in enumerate(subs):
            cs_ms = s_ms + c_idx * chunk_ms
            ce_ms = cs_ms + chunk_ms if c_idx < num_c - 1 else e_ms
            st_ass = ms_to_ass_time(cs_ms)
            et_ass = ms_to_ass_time(ce_ms)
            ass_lines.append(f"Dialogue: 0,{st_ass},{et_ass},{style_name},,0,0,0,,{sub_t}")

    ass_file.write_text("\n".join(ass_lines), encoding="utf-8")

    # 2. 生成各镜头切片视频 (带首帧 0.5s 封面卡 + 正片各镜 + 慢推拉)
    concat_list = temp_dir / "concat.txt"
    clip_files = []

    # 0.5s 首帧封面卡
    cover_clip = temp_dir / "clip_00_cover.mp4"
    cmd_cover = [
        FFMPEG_EXE, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-loop", "1", "-i", str(cover_card_img),
        "-t", "0.500",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1",
        "-r", "30",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        str(cover_clip)
    ]
    subprocess.run(cmd_cover, check=True)
    clip_files.append(cover_clip)

    # 各正片镜头切片 (第一镜扣除首帧 0.5s，确保总时长精确等于 total_dur_s)
    for s_idx, shot_info in enumerate(shot_files):
        img_p = shot_info["path"]
        dur_s = shot_info["dur_s"]
        if s_idx == 0:
            dur_s = max(0.2, dur_s - 0.5)

        clip_p = temp_dir / f"clip_{s_idx+1:02d}.mp4"

        cmd_clip = [
            FFMPEG_EXE, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-loop", "1", "-i", str(img_p),
            "-t", f"{dur_s:.3f}",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1",
            "-r", "30",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(clip_p)
        ]
        subprocess.run(cmd_clip, check=True)
        clip_files.append(clip_p)

    concat_list.write_text("\n".join(f"file '{p.as_posix()}'" for p in clip_files), encoding="utf-8")

    # 3. 准备音频混音 (基于 adelay 和 aresample 精确对齐人声 + BGM -18dB)
    voice_master_mp3 = temp_dir / "voice_master.mp3"
    cmd_v = [FFMPEG_EXE, "-nostdin", "-hide_banner", "-y"]
    parts, labels = [], []
    for idx, sent in enumerate(sentences):
        cmd_v += ["-i", str(sent["audio_file"])]
        offset_ms = int(sent["start_us"] // 1000)
        parts.append(f"[{idx}:a]adelay={offset_ms}|{offset_ms},aresample=44100[a{idx}]")
        labels.append(f"[a{idx}]")
    
    v_graph = ";".join(parts) + ";" + "".join(labels) + f"amix=inputs={len(sentences)}:duration=longest:normalize=0[vout]"
    cmd_v += ["-filter_complex", v_graph, "-map", "[vout]", "-c:a", "libmp3lame", "-b:a", "192k", str(voice_master_mp3)]
    subprocess.run(cmd_v, check=True)

    # 混音 BGM (-18dB)
    fade_out_start = max(0, total_dur_s - 2.5)
    filter_complex = (
        f"[0:a]volume=1.4125[v];"
        f"[1:a]aloop=loop=-1:size=2e+09,atrim=0:{total_dur_s:.3f},"
        f"afade=t=in:ss=0:d=1.0,afade=t=out:st={fade_out_start:.3f}:d=2.5,volume=0.12589[m];"
        f"[v][m]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )
    mixed_audio = temp_dir / "mixed_audio.aac"
    cmd_audio = [
        FFMPEG_EXE, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(voice_master_mp3),
        "-i", str(BGM_PATH),
        "-filter_complex", filter_complex,
        "-map", "[aout]",
        "-c:a", "aac", "-b:a", "192k",
        str(mixed_audio)
    ]
    subprocess.run(cmd_audio, check=True)

    # 4. 画面 + 音频 + ASS 字幕滤镜合成最终 MP4
    ass_escaped = str(ass_file).replace("\\", "/").replace(":", "\\:")
    cmd_final = [
        FFMPEG_EXE, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-i", str(mixed_audio),
        "-vf", f"subtitles=filename='{ass_escaped}'",
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-shortest", "-movflags", "+faststart",
        str(out_mp4)
    ]
    subprocess.run(cmd_final, check=True)

    # 清理临时文件
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass

    return out_mp4

# ==================== 单日单场装配调度 ====================
async def process_single_video(session: str, day: str, script_data: dict, shot_list: list, cfg: dict, role_cfg: dict):
    day_num = int(day.replace("D", ""))
    proj_title = f"成片_{day}_{session}"
    prefix = "AUD_D" if session == "早场" else ("AUD_N" if session == "午场" else "AUD_W")
    
    cover_text = COVER_TEXT_MAP[session][day]
    book_key = BOOK_ASSIGNMENT[session][day]
    book_path = BOOK_MAP[book_key]

    print(f"\n==========================================")
    print(f">>> 处理: {proj_title} ({session} {day})")
    print(f"==========================================")

    proj_dir = ROOT / "03_视频成片与工程" / proj_title
    audio_dir = proj_dir / "03_配音音频"
    visual_dir = proj_dir / "02_分镜视觉素材"
    proj_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)
    visual_dir.mkdir(parents=True, exist_ok=True)

    items = script_data["items"]
    num_sents = len(items)
    num_shots = len(shot_list)

    # 1. 逐句定版配音合成 (新音色重配)
    sentences = []
    cur_time_us = 0
    remade_count = 0
    total_chars = 0

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

    for s_idx, item in enumerate(items):
        sent_id = f"{prefix}{day_num}_{item['id']}"
        raw_text = item["raw_text"]
        af = audio_dir / f"{sent_id}.mp3"

        # 如果是孩子，强制重新生成 (更新为 1.5 倍语速)
        # 非孩子角色如果已存在有效音频则直接复用
        is_child = (item["role"] == "孩子")
        if is_child or (not af.exists()) or af.stat().st_size == 0:
            res = await synthesize_sentence(cfg, role_cfg, item, session, day, af)
            remade_count += 1
            total_chars += res.get("characters", 0)

        dur_us = get_audio_duration_us(af)
        gap_us = 200_000 if s_idx < num_sents - 1 else 0

        # 切分子幕：去掉角色前缀、去掉所有标点符号
        parts = [p.strip() for p in re.split(r"[/]+", raw_text) if p.strip()]
        sub_list = []
        for p in parts:
            c_p = clean_sub_text(p)
            if c_p:
                sub_list.append(c_p)

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

    total_dur_us = cur_time_us
    total_dur_sec = round(total_dur_us / 1_000_000, 2)
    print(f"  [✓ 配音完成] 重配 {remade_count} 句，总字数: {total_chars}，总时长: {total_dur_sec} 秒")

    # 2. 匹配分镜图片与官方书图
    shot_files = []
    missing_materials = []

    for s_idx, shot in enumerate(shot_list):
        s_name = shot["name"]
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
            target_local = visual_dir / real_file.name
            if not target_local.exists() or target_local.stat().st_size != real_file.stat().st_size:
                safe_copy(real_file, target_local)
        else:
            missing_materials.append(s_name)
            target_local = visual_dir / f"{s_name}.jpg"

        # 计算该镜时长
        sents_in_shot = [s for s in sentences if s["shot_idx"] == s_idx]
        if sents_in_shot:
            s_dur_us = sents_in_shot[-1]["end_us"] - sents_in_shot[0]["start_us"]
            if s_idx == num_shots - 1:
                s_dur_us = max(s_dur_us, total_dur_us - sents_in_shot[0]["start_us"])
        else:
            s_dur_us = total_dur_us // num_shots

        shot_files.append({
            "name": s_name,
            "path": target_local,
            "dur_us": s_dur_us,
            "dur_s": s_dur_us / 1_000_000
        })

    # 3. 生成首帧封面卡片
    hook_img = shot_files[0]["path"]
    cover_card_img = visual_dir / f"cover_{proj_title}.jpg"
    create_cover_card(cover_card_img, hook_img, cover_text)

    # 4. 装配并保存剪映工程
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

    # A1 轨
    for sent in sentences:
        a_seg = draft.AudioSegment(
            sent["audio_file"],
            draft.Timerange(sent["start_us"], sent["dur_us"]),
            volume=1.4125
        )
        script.add_segment(a_seg, track="A1_人声")

    # A2 轨
    if BGM_PATH.exists():
        bgm_dur_us = get_audio_duration_us(BGM_PATH)
        cur_bgm_us = 0
        chunk_idx = 0
        while cur_bgm_us < total_dur_us:
            chunk_len = min(bgm_dur_us, total_dur_us - cur_bgm_us)
            b_seg = draft.AudioSegment(
                str(BGM_PATH),
                draft.Timerange(cur_bgm_us, chunk_len),
                source_timerange=draft.Timerange(0, chunk_len),
                volume=0.12589 # -18dB
            )
            fade_in = 1_000_000 if chunk_idx == 0 else 0
            fade_out = 2_500_000 if (cur_bgm_us + chunk_len >= total_dur_us) else 0
            if fade_in or fade_out:
                b_seg.add_fade(fade_in, fade_out)
            script.add_segment(b_seg, track="A2_BGM(-18dB)")
            cur_bgm_us += chunk_len
            chunk_idx += 1

    # V1 轨
    cur_v1_us = 0
    for shot_info in shot_files:
        v_seg = draft.VideoSegment(
            str(shot_info["path"]),
            draft.Timerange(cur_v1_us, shot_info["dur_us"])
        )
        try:
            with Image.open(str(shot_info["path"])) as im:
                w, h = im.size
                if w >= h or w / h > 0.6:
                    v_seg.add_background_filling("blur", blur=0.375)
        except Exception:
            pass

        v_seg.add_keyframe(draft.KeyframeProperty.uniform_scale, 0, 1.0)
        v_seg.add_keyframe(draft.KeyframeProperty.uniform_scale, shot_info["dur_us"], 1.06)
        script.add_segment(v_seg, track="V1_正片画面")
        cur_v1_us += shot_info["dur_us"]

    # V2 轨
    cov_seg = draft.VideoSegment(str(cover_card_img), draft.Timerange(0, 500_000))
    script.add_segment(cov_seg, track="V2_书图与封面")
    last_shot = shot_files[-1]
    last_start_us = total_dur_us - last_shot["dur_us"]
    book_seg = draft.VideoSegment(str(last_shot["path"]), draft.Timerange(last_start_us, last_shot["dur_us"]))
    book_seg.add_background_filling("blur", blur=0.375)
    book_seg.add_keyframe(draft.KeyframeProperty.uniform_scale, 0, 1.0)
    book_seg.add_keyframe(draft.KeyframeProperty.uniform_scale, last_shot["dur_us"], 1.05)
    script.add_segment(book_seg, track="V2_书图与封面")

    # 字幕轨
    color_map = {
        "孩子": (1.0, 1.0, 1.0),
        "爷爷": (1.0, 0.82, 0.2),
        "奶奶": (1.0, 0.60, 0.67),
        "女声": (0.8, 0.8, 0.8),
        "男声": (0.8, 0.8, 0.8),
    }
    sub_clip = draft.ClipSettings(transform_y=-0.573)
    sub_border = draft.TextBorder(color=(0.0, 0.0, 0.0), width=40.0)
    sub_bg = draft.TextBackground(color="#000000", alpha=0.6, round_radius=0.15)

    for sent in sentences:
        subs = sent["subtitles"]
        s_start = sent["start_us"]
        s_dur = sent["dur_us"]
        sub_chunk_dur = s_dur // len(subs) if subs else s_dur
        for c_i, sub_text in enumerate(subs):
            c_start = s_start + c_i * sub_chunk_dur
            c_dur = sub_chunk_dur if c_i < len(subs) - 1 else (s_start + s_dur - c_start)
            col = color_map.get(sent["role"], (1.0, 1.0, 1.0)) if session == "早场" else (1.0, 1.0, 1.0)
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

    script.save()
    jianying_draft_path = JIANYING_DIR / proj_title

    # 5. 云端与本地备份剪映工程
    cloud_drafts_dir = WEEK2_DIR / "06_成片待审" / "01_剪映草稿工程"
    cloud_drafts_dir.mkdir(parents=True, exist_ok=True)
    for jf in ["draft_content.json", "draft_meta_info.json"]:
        src = jianying_draft_path / jf
        if src.exists():
            safe_copy(src, proj_dir / jf)

    cloud_proj_folder = cloud_drafts_dir / proj_title
    if cloud_proj_folder.exists():
        shutil.rmtree(cloud_proj_folder)
    shutil.copytree(jianying_draft_path, cloud_proj_folder, copy_function=safe_copy)

    zip_path = cloud_drafts_dir / f"{proj_title}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root_p, _, files in os.walk(jianying_draft_path):
            for f in files:
                full_p = Path(root_p) / f
                arcname = full_p.relative_to(jianying_draft_path.parent)
                zf.write(full_p, arcname)

    manifest_data = {
        "name": proj_title,
        "session": session,
        "day": day,
        "total_duration_sec": total_dur_sec,
        "missing_materials": missing_materials,
        "sentences_count": num_sents,
        "shots_count": num_shots,
        "remade_count": remade_count
    }

    # 6. 极速渲染成片 MP4
    local_mp4 = proj_dir / "05_成片" / f"{proj_title}.mp4"
    print(f"  🎬 开始渲染成片 MP4: {local_mp4.name} ...")
    render_mp4(proj_dir, local_mp4, manifest_data, shot_files, sentences, session, cover_card_img)

    # 7. 上传成片到云端 06_成片待审
    cloud_mp4 = OUT_REVIEW_DIR / f"{proj_title}.mp4"
    safe_copy(local_mp4, cloud_mp4)
    print(f"  [✓ 成片上传云端] {cloud_mp4.name} ({cloud_mp4.stat().st_size / 1024 / 1024:.2f} MB)")

    missing_str = "、".join(missing_materials) if missing_materials else "无"
    return {
        "session": session,
        "day": day,
        "name": proj_title,
        "duration": f"{total_dur_sec}秒",
        "remade_count": remade_count,
        "missing": missing_str
    }

# ==================== 全局主执行入口 ====================
async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Finalize Week 2 Production")
    parser.add_argument("--session", choices=["早场", "午场", "晚场"], help="只处理指定场次")
    parser.add_argument("--day", help="只处理指定天数 (如 D1)")
    args = parser.parse_args()

    print("================================================================")
    print("=== 开始执行第二周全量配音重配、剪辑装配与成片导出 ===")
    print("================================================================")

    # 加载配置
    cfg = voice_api_tts.load_config(ROOT / "config" / "voice_api" / "config.yaml")
    role_cfg_path = ROOT / "01_配音与音色库" / "六角色定稿_V1_20261107" / "六角色定稿配置.json"
    role_cfg = json.loads(role_cfg_path.read_text(encoding="utf-8"))["roles"]

    p_m_script = WEEK2_DIR / "02_音频脚本" / "第二周_早场音频制作脚本.md"
    p_n_script = WEEK2_DIR / "02_音频脚本" / "第二周_午场音频制作脚本.md"
    p_w_script = WEEK2_DIR / "02_音频脚本" / "第二周_晚场音频制作脚本.md"

    p_m_shots = WEEK2_DIR / "03_图片需求" / "第二周_早场图片需求清单.md"
    p_n_shots = WEEK2_DIR / "03_图片需求" / "第二周_午场图片需求清单.md"
    p_w_shots = WEEK2_DIR / "03_图片需求" / "第二周_晚场图片需求清单.md"

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

    sessions_to_run = [args.session] if args.session else ["早场", "午场", "晚场"]
    days_to_run = [args.day] if args.day else [f"D{d}" for d in range(1, 8)]

    for s_name in sessions_to_run:
        for d_str in days_to_run:
            res = await process_single_video(
                s_name, d_str,
                scripts_all[s_name][d_str],
                shots_all[s_name][d_str],
                cfg, role_cfg
            )
            results.append(res)

    print("\n" + "="*60)
    print("=== 装配与成片导出汇总报告 ===")
    print("="*60)
    for r in results:
        print(f"已完成 {r['session']}{r['day']}、总时长 {r['duration']}、重配句数 {r['remade_count']}、缺失素材（{r['missing']}）")

if __name__ == "__main__":
    asyncio.run(main())
