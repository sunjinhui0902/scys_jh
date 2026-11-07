#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build Week 2 Morning Dialogue Drafts (D1, D2, D3)
符合《第二周_生产规范.md》及用户要求：
1. 逐天独立建工程，竖屏 1080×1920，命名：成片_D1_早场、成片_D2_早场、成片_D3_早场
2. V1 正片画面按镜号顺序排，时长对齐对应音频句；
   V2 放首帧封面（钩子镜图+封面大字）与末镜书图；
   A1 人声用平常 TTS 按 AUD_D{天}_S{句号} 逐句上轨占位，一句一个文件；
   A2 剪映曲库轻音乐，人声段压低到 -18dB；
   字幕轨一句一屏，带角色小标签与角色配色（爷爷暖黄、奶奶暖粉、孩子白色、画外音灰色）；
3. 静图缓慢推拉；
4. 真实素材（IMG_D1_02.png, IMG_D1_04.png，官方书图）直接上轨，缺失素材用纯色占位图搭框架；
5. 不导出成片 MP4，输出草稿至剪映目录并备份至云端 06_成片待审/01_剪映草稿工程。
"""

import os
import sys
import json
import asyncio
import shutil
import zipfile
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

BOOK_D1_D3 = WEEK1_DIR / "03_书图" / "冷门知识1000问" / "冷门知识1000问_封面.jpg"
BOOK_D2 = WEEK1_DIR / "03_书图" / "2027古诗日历" / "古诗日历_主图.jpg"

IMG_GEN_DIR = WEEK2_DIR / "03_图片需求" / "生成图片"

def get_audio_duration_us(path: Path) -> int:
    mi = pymediainfo.MediaInfo.parse(str(path))
    for t in mi.tracks:
        if t.track_type == "Audio":
            return int(float(t.duration) * 1000)
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
    draw.text((width // 2, height // 2 + 100), desc, fill=(200, 200, 200), font=font_desc, anchor="mm")
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
    # 顶部暗色遮罩
    draw.rectangle([0, 250, width, 550], fill=(0, 0, 0, 180))
    font_cover = get_chinese_font(68)
    draw.text((width // 2, 400), cover_text, fill=(255, 220, 50), font=font_cover, anchor="mm")
    im.save(str(path), "JPEG", quality=90)

# 角色音色配置
VOICE_MAP = {
    "孩子": {"voice": "zh-CN-XiaoyiNeural", "rate": "+4%", "pitch": "+12Hz"},
    "爷爷": {"voice": "zh-CN-YunjianNeural", "rate": "-8%", "pitch": "-6Hz"},
    "奶奶": {"voice": "zh-CN-XiaoxiaoNeural", "rate": "-8%", "pitch": "-4Hz"},
    "女声": {"voice": "zh-CN-XiaoxiaoNeural", "rate": "+5%", "pitch": "+0Hz"},
    "男声": {"voice": "zh-CN-YunxiNeural", "rate": "+0%", "pitch": "+0Hz"},
}

# 角色字幕颜色配置
COLOR_MAP = {
    "孩子": (1.0, 1.0, 1.0),       # 白色
    "爷爷": (1.0, 0.82, 0.2),      # 暖黄
    "奶奶": (1.0, 0.60, 0.67),     # 暖粉
    "女声": (0.8, 0.8, 0.8),       # 画外音灰色
    "男声": (0.8, 0.8, 0.8),       # 画外音灰色
}

# D1, D2, D3 详细脚本与分镜定义
PROJECTS_DATA = [
    {
        "day": 1,
        "name": "成片_D1_早场",
        "cover_text": "哈气为什么冒白烟",
        "book_path": BOOK_D1_D3,
        "book_name": "《冷门知识1000问》",
        "sentences": [
            {"id": "AUD_D1_S01", "role": "孩子", "text": "爷爷爷爷，你看，我嘴冒烟了！", "subtitles": ["孩子：爷爷爷爷", "孩子：你看", "孩子：我嘴冒烟了"], "shot_idx": 1},
            {"id": "AUD_D1_S02", "role": "爷爷", "text": "哈哈，那可不是烟。", "subtitles": ["爷爷：哈哈", "爷爷：那可不是烟"], "shot_idx": 2},
            {"id": "AUD_D1_S03", "role": "孩子", "text": "那是啥？我是不是着火啦？", "subtitles": ["孩子：那是啥", "孩子：我是不是着火啦"], "shot_idx": 2},
            {"id": "AUD_D1_S04", "role": "爷爷", "text": "你呼出来的气，又暖又湿，里头全是看不见的水汽。一碰上外头的冷空气，它立马变成一颗颗小水珠，飘在你嘴边 —— 就成了你看见的白烟。", "subtitles": ["爷爷：你呼出来的气", "爷爷：又暖又湿", "爷爷：里头全是看不见的水汽", "爷爷：一碰上外头的冷空气", "爷爷：它立马变成一颗颗小水珠", "爷爷：飘在你嘴边", "爷爷：就成了你看见的白烟"], "shot_idx": 3},
            {"id": "AUD_D1_S05", "role": "孩子", "text": "那天越冷，烟越大？", "subtitles": ["孩子：那天越冷", "孩子：烟越大"], "shot_idx": 3},
            {"id": "AUD_D1_S06", "role": "爷爷", "text": "对喽！跟冬天窗户上起雾，一个理儿。", "subtitles": ["爷爷：对喽", "爷爷：跟冬天窗户上起雾", "爷爷：一个理儿"], "shot_idx": 4},
            {"id": "AUD_D1_S07", "role": "孩子", "text": "那我再哈一个大的！", "subtitles": ["孩子：那我再哈一个大的"], "shot_idx": 4},
            {"id": "AUD_D1_S08", "role": "爷爷", "text": "这类问题，孩子能追着问一串：天为什么是蓝的、影子为什么跟着人。我备的那本《冷门知识一千问》，一千个问题，一个问题一页讲法。下次孩子问，别说去问老师，跟他一起翻 —— 答案他记不住不要紧，他记得住，是谁陪他找的。", "subtitles": ["爷爷：这类问题", "爷爷：孩子能追着问一串", "爷爷：天为什么是蓝的", "爷爷：影子为什么跟着人", "爷爷：我备的那本《冷门知识1000问》", "爷爷：一千个问题", "爷爷：一个问题一页讲法", "爷爷：下次孩子问", "爷爷：别说去问老师", "爷爷：跟他一起翻", "爷爷：答案他记不住不要紧", "爷爷：他记得住", "爷爷：是谁陪他找的"], "shot_idx": 5},
        ],
        "shots": [
            {"idx": 1, "filename": "IMG_D1_01", "is_anim": True, "desc": "冬日户外小男孩仰头哈气冒白烟"},
            {"idx": 2, "filename": "IMG_D1_02.png", "is_anim": False, "desc": "爷爷侧面含笑看着孩子，半身"},
            {"idx": 3, "filename": "IMG_D1_03", "is_anim": True, "desc": "微观科普气流遇冷凝成小水珠"},
            {"idx": 4, "filename": "IMG_D1_04.png", "is_anim": False, "desc": "清晨窗户玻璃满是雾气画笑脸"},
            {"idx": 5, "filename": "IMG_D1_05", "is_anim": False, "desc": "《冷门知识1000问》官方封面图", "is_book": True},
        ]
    },
    {
        "day": 2,
        "name": "成片_D2_早场",
        "cover_text": "背诗，先看一幅画",
        "book_path": BOOK_D2,
        "book_name": "2027 古诗日历",
        "sentences": [
            {"id": "AUD_D2_S01", "role": "女声", "text": "还不会背！还不会背！读了多少遍了！", "subtitles": ["女声：还不会背", "女声：还不会背", "女声：读了多少遍了"], "shot_idx": 1},
            {"id": "AUD_D2_S02", "role": "奶奶", "text": "别吼孩子。背不下来，不是笨，是他脑子里没那幅画。来，跟奶奶看画。", "subtitles": ["奶奶：别吼孩子", "奶奶：背不下来", "奶奶：不是笨", "奶奶：是他脑子里没那幅画", "奶奶：来", "奶奶：跟奶奶看画"], "shot_idx": 2},
            {"id": "AUD_D2_S03", "role": "奶奶", "text": "第一幅：大半夜，一个人睡不着，坐在床边。月光从窗户洒进来，白花花铺了一地。", "subtitles": ["奶奶：第一幅", "奶奶：大半夜", "奶奶：一个人睡不着", "奶奶：坐在床边", "奶奶：月光从窗户洒进来", "奶奶：白花花铺了一地"], "shot_idx": 3},
            {"id": "AUD_D2_S04", "role": "孩子", "text": "好像…… 霜一样？", "subtitles": ["孩子：好像", "孩子：霜一样"], "shot_idx": 3},
            {"id": "AUD_D2_S05", "role": "奶奶", "text": "对！他自己也这么想，这就叫疑是地上霜。他抬起头，望望月亮，又低下头 ——", "subtitles": ["奶奶：对", "奶奶：他自己也这么想", "奶奶：这就叫疑是地上霜", "奶奶：他抬起头", "奶奶：望望月亮", "奶奶：又低下头"], "shot_idx": 3},
            {"id": "AUD_D2_S06", "role": "孩子", "text": "想家了。", "subtitles": ["孩子：想家了"], "shot_idx": 3},
            {"id": "AUD_D2_S07", "role": "奶奶", "text": "你看，画看懂了，诗自己就顺下来了：床前明月光，疑是地上霜。举头望明月，低头思故乡。", "subtitles": ["奶奶：你看", "奶奶：画看懂了", "奶奶：诗自己就顺下来了", "奶奶：床前", "奶奶：明月光", "奶奶：疑是", "奶奶：地上霜", "奶奶：举头", "奶奶：望明月", "奶奶：低头", "奶奶：思故乡"], "shot_idx": 4},
            {"id": "AUD_D2_S08", "role": "奶奶", "text": "我陪孙子读那本二零二七古诗日历，一天一首，先讲画、再读字，拼音译文都配好了。背诗不是背字，是先让他看见，诗人看见的东西。", "subtitles": ["奶奶：我陪孙子读那本二零二七古诗日历", "奶奶：一天一首", "奶奶：先讲画", "奶奶：再读字", "奶奶：拼音译文都配好了", "奶奶：背诗不是背字", "奶奶：是先让他看见", "奶奶：诗人看见的东西"], "shot_idx": 5},
        ],
        "shots": [
            {"idx": 1, "filename": "IMG_D2_01", "is_anim": False, "desc": "夜晚客厅妈妈叉腰孩子低头"},
            {"idx": 2, "filename": "IMG_D2_02", "is_anim": False, "desc": "奶奶伸手拦在中间轻拍孩子肩"},
            {"idx": 3, "filename": "IMG_D2_03", "is_anim": False, "desc": "古代旅人床边望明月月光如霜"},
            {"idx": 4, "filename": "IMG_D2_04", "is_anim": False, "desc": "孩子若有所思抬头奶奶微笑"},
            {"idx": 5, "filename": "IMG_D2_05", "is_anim": False, "desc": "2027 古诗日历官方主图", "is_book": True},
        ]
    },
    {
        "day": 3,
        "name": "成片_D3_早场",
        "cover_text": "月亮为什么跟着我",
        "book_path": BOOK_D1_D3,
        "book_name": "《冷门知识1000问》",
        "sentences": [
            {"id": "AUD_D3_S01", "role": "孩子", "text": "奶奶奶奶，这月亮是不是喜欢我呀？老是跟着我！", "subtitles": ["孩子：奶奶奶奶", "孩子：这月亮是不是喜欢我呀", "孩子：老是跟着我"], "shot_idx": 1},
            {"id": "AUD_D3_S02", "role": "奶奶", "text": "它呀，跟谁都走，就看谁的问题问得好。奶奶告诉你个秘密：月亮离咱们，三十八万公里。", "subtitles": ["奶奶：它呀", "奶奶：跟谁都走", "奶奶：就看谁的问题问得好", "奶奶：奶奶告诉你个秘密", "奶奶：月亮离咱们", "奶奶：三十八万公里"], "shot_idx": 2},
            {"id": "AUD_D3_S03", "role": "孩子", "text": "那么远 ——！", "subtitles": ["孩子：那么远"], "shot_idx": 2},
            {"id": "AUD_D3_S04", "role": "奶奶", "text": "咱们在地上走出去几百米，跟三十八万公里一比，等于原地没动。所以你往哪儿走，一抬头，它都在那个角度挂着，就像一直跟着你。", "subtitles": ["奶奶：咱们在地上走出去几百米", "奶奶：跟三十八万公里一比", "奶奶：等于原地没动", "奶奶：所以你往哪儿走", "奶奶：一抬头", "奶奶：它都在那个角度挂着", "奶奶：就像一直跟着你"], "shot_idx": 3},
            {"id": "AUD_D3_S05", "role": "孩子", "text": "那树怎么往后跑？", "subtitles": ["孩子：那树怎么往后跑"], "shot_idx": 4},
            {"id": "AUD_D3_S06", "role": "奶奶", "text": "树离得近呀！你走一步，它退一步。近的往后跑，远的一动不动 —— 一比，可不就显得月亮在追你了。", "subtitles": ["奶奶：树离得近呀", "奶奶：你走一步", "奶奶：它退一步", "奶奶：近的往后跑", "奶奶：远的一动不动", "奶奶：一比", "奶奶：可不就显得月亮在追你了"], "shot_idx": 4},
            {"id": "AUD_D3_S07", "role": "孩子", "text": "我要告诉小明，他还说月亮偏心呢！", "subtitles": ["孩子：我要告诉小明", "孩子：他还说月亮偏心呢"], "shot_idx": 4},
            {"id": "AUD_D3_S08", "role": "奶奶", "text": "这种问题，那本《冷门知识一千问》里收了不少，天文地理占了整整一部分。孩子的问题千万别敷衍 —— 敷衍一次，他就少问一次，慢慢就全去问手机了。陪他把答案找出来，这个晚上，他能记一辈子。", "subtitles": ["奶奶：这种问题", "奶奶：那本《冷门知识1000问》里收了不少", "奶奶：天文地理占了整整一部分", "奶奶：孩子的问题千万别敷衍", "奶奶：敷衍一次", "奶奶：他就少问一次", "奶奶：慢慢就全去问手机了", "奶奶：陪他把答案找出来", "奶奶：这个晚上", "奶奶：他能记一辈子"], "shot_idx": 5},
        ],
        "shots": [
            {"idx": 1, "filename": "IMG_D3_01", "is_anim": True, "desc": "夜晚小路孩子仰头指月亮薄云飘过"},
            {"idx": 2, "filename": "IMG_D3_02", "is_anim": False, "desc": "月光下奶奶蹲下与孩子平视讲话"},
            {"idx": 3, "filename": "IMG_D3_03", "is_anim": True, "desc": "地球与远处月亮距离示意图"},
            {"idx": 4, "filename": "IMG_D3_04", "is_anim": True, "desc": "树木向后掠过月亮位置不变对比"},
            {"idx": 5, "filename": "IMG_D3_05", "is_anim": False, "desc": "《冷门知识1000问》官方封面图", "is_book": True},
        ]
    }
]

async def synth_line(text: str, role: str, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cfg = VOICE_MAP.get(role, {"voice": "zh-CN-YunjianNeural", "rate": "+0%", "pitch": "+0Hz"})
    comm = edge_tts.Communicate(text, cfg["voice"], rate=cfg["rate"], pitch=cfg["pitch"])
    await comm.save(str(out_path))

async def main():
    print("=== 开始装配第二周早场 D1、D2、D3 工程框架 ===")
    summary_report = []

    for proj in PROJECTS_DATA:
        day_num = proj["day"]
        proj_title = proj["name"]
        print(f"\n>>> 正在处理 D{day_num}: {proj_title} ...")

        # 本地工程文件夹与草稿目录
        local_proj_dir = ROOT / "03_视频成片与工程" / proj_title
        local_audio_dir = local_proj_dir / "03_配音音频"
        local_visual_dir = local_proj_dir / "02_分镜视觉素材"
        local_proj_dir.mkdir(parents=True, exist_ok=True)
        local_audio_dir.mkdir(parents=True, exist_ok=True)
        local_visual_dir.mkdir(parents=True, exist_ok=True)

        # 1. 逐句生成 TTS 音频占位文件
        cur_time_us = 0
        audio_segments = []
        for s_idx, sent in enumerate(proj["sentences"]):
            af = local_audio_dir / f"{sent['id']}.mp3"
            if not af.exists() or af.stat().st_size == 0:
                print(f"  正在生成占位音频 {sent['id']} ({sent['role']}) ...")
                await synth_line(sent["text"], sent["role"], af)
            
            dur_us = get_audio_duration_us(af)
            # 停顿设置：场景内短停 0.3s，场景间切换 0.5s
            gap_us = 300_000 if s_idx < len(proj["sentences"]) - 1 else 0
            
            sent["audio_file"] = str(af)
            sent["start_us"] = cur_time_us
            sent["dur_us"] = dur_us
            sent["end_us"] = cur_time_us + dur_us
            cur_time_us += dur_us + gap_us

        total_audio_dur_us = cur_time_us
        total_sec = round(total_audio_dur_us / 1_000_000, 2)
        print(f"  人声 A1 轨铺设完毕，总时长: {total_sec} 秒")

        # 2. 镜头画面与时间区间计算 (Shot 1 to 5)
        # 每个镜头包含的句子区间
        shot_files = {}
        missing_materials = []

        # 检查素材存在情况
        for shot in proj["shots"]:
            s_idx = shot["idx"]
            fn = shot["filename"]
            is_book = shot.get("is_book", False)
            
            real_file = None
            if is_book:
                if proj["book_path"].exists():
                    real_file = proj["book_path"]
            else:
                # 检查云端 03_图片需求/生成图片
                cands = [
                    IMG_GEN_DIR / fn,
                    IMG_GEN_DIR / f"{fn}.png",
                    IMG_GEN_DIR / f"{fn}.jpg",
                    IMG_GEN_DIR / f"{fn}.gif",
                ]
                for c in cands:
                    if c.exists() and c.is_file():
                        real_file = c
                        break

            if real_file:
                # 真实素材到位
                target_local = local_visual_dir / real_file.name
                if not target_local.exists():
                    shutil.copy2(real_file, target_local)
                shot_files[s_idx] = target_local
            else:
                # 缺失，记录缺失并建立占位图
                missing_materials.append(fn)
                placeholder_path = local_visual_dir / f"placeholder_{fn}.jpg"
                create_placeholder(placeholder_path, fn, shot["desc"])
                shot_files[s_idx] = placeholder_path

        # 计算每个镜头的起止时间（对齐对应的音频句）
        shot_timings = {}
        for s_idx in range(1, 6):
            sents_in_shot = [s for s in proj["sentences"] if s["shot_idx"] == s_idx]
            if sents_in_shot:
                s_start = sents_in_shot[0]["start_us"]
                s_end = sents_in_shot[-1]["end_us"]
                # 最后一个镜头延展到总音频结束
                if s_idx == 5:
                    s_end = max(s_end, total_audio_dur_us)
                shot_timings[s_idx] = {"start_us": s_start, "dur_us": s_end - s_start, "end_us": s_end}
            else:
                shot_timings[s_idx] = {"start_us": 0, "dur_us": total_audio_dur_us // 5, "end_us": total_audio_dur_us}

        # 3. 装配剪映工程 (pyJianYingDraft)
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

        # A1 轨：逐句上轨占位（一句一个文件）
        for sent in proj["sentences"]:
            af_path = sent["audio_file"]
            a_seg = draft.AudioSegment(
                str(af_path),
                draft.Timerange(sent["start_us"], sent["dur_us"]),
                volume=1.4125 # +3dB
            )
            script.add_segment(a_seg, track="A1_人声")

        # A2 轨：BGM 循环铺满，人声段压低到 -18dB (volume=0.12589)，首端淡入 1.0s，末端淡出 2.5s
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

        # V1 轨：正片画面按镜号顺序排，时长对齐对应音频句，静图做缓慢推拉
        for s_idx in range(1, 6):
            img_file = shot_files[s_idx]
            st = shot_timings[s_idx]
            v_seg = draft.VideoSegment(str(img_file), draft.Timerange(st["start_us"], st["dur_us"]))
            
            # 毛玻璃背景虚化适配
            try:
                with Image.open(str(img_file)) as im:
                    w, h = im.size
                    if w >= h or w / h > 0.6:
                        v_seg.add_background_filling("blur", blur=0.375)
            except Exception:
                pass

            # 静图缓慢推拉 Ken Burns
            v_seg.add_keyframe(draft.KeyframeProperty.uniform_scale, 0, 1.0)
            v_seg.add_keyframe(draft.KeyframeProperty.uniform_scale, st["dur_us"], 1.06)

            script.add_segment(v_seg, track="V1_正片画面")

        # V2 轨：首帧封面（钩子镜图+封面大字）与末镜书图
        # 首帧封面 (前 500ms)
        cover_img_path = local_visual_dir / f"cover_{proj_title}.jpg"
        hook_img = shot_files[1]
        create_cover_card(cover_img_path, hook_img, proj["cover_text"])
        cover_dur_us = 500_000 # 0.5s 首帧封面
        v2_cover_seg = draft.VideoSegment(str(cover_img_path), draft.Timerange(0, cover_dur_us))
        script.add_segment(v2_cover_seg, track="V2_书图与封面")

        # 末镜官方书图（放在 V2 轨 Shot 5 区间）
        if proj["book_path"].exists():
            st5 = shot_timings[5]
            v2_book_seg = draft.VideoSegment(str(proj["book_path"]), draft.Timerange(st5["start_us"], st5["dur_us"]))
            v2_book_seg.add_background_filling("blur", blur=0.375)
            v2_book_seg.add_keyframe(draft.KeyframeProperty.uniform_scale, 0, 1.0)
            v2_book_seg.add_keyframe(draft.KeyframeProperty.uniform_scale, st5["dur_us"], 1.05)
            script.add_segment(v2_book_seg, track="V2_书图与封面")

        # 字幕轨：按断句点切分，一句一屏，带角色标签与规范配色
        sub_border = draft.TextBorder(color=(0.0, 0.0, 0.0), width=40.0)
        sub_bg = draft.TextBackground(color="#000000", alpha=0.6, round_radius=0.15)
        sub_clip = draft.ClipSettings(transform_y=-0.573)

        for sent in proj["sentences"]:
            subs = sent["subtitles"]
            s_start = sent["start_us"]
            s_dur = sent["dur_us"]
            # 均摊该句各分段字幕时长
            sub_chunk_dur = s_dur // len(subs)
            for c_i, sub_text in enumerate(subs):
                c_start = s_start + c_i * sub_chunk_dur
                c_dur = sub_chunk_dur if c_i < len(subs) - 1 else (s_start + s_dur - c_start)
                
                col = COLOR_MAP.get(sent["role"], (1.0, 1.0, 1.0))
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

        # 保存剪映草稿工程
        script.save()
        jianying_draft_path = JIANYING_DIR / proj_title
        print(f"  剪映草稿已保存: {jianying_draft_path}")

        # 4. 同步草稿工程至本地项目目录及云端硬盘备份 (06_成片待审/01_剪映草稿工程)
        cloud_drafts_dir = WEEK2_DIR / "06_成片待审" / "01_剪映草稿工程"
        cloud_drafts_dir.mkdir(parents=True, exist_ok=True)

        # 复制草稿 JSON 至 local_proj_dir
        for jf in ["draft_content.json", "draft_meta_info.json"]:
            src = jianying_draft_path / jf
            if src.exists():
                shutil.copy2(src, local_proj_dir / jf)

        # 打包草稿工程 zip 存入云端 06_成片待审/01_剪映草稿工程
        zip_path = cloud_drafts_dir / f"{proj_title}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root_p, _, files in os.walk(jianying_draft_path):
                for f in files:
                    full_p = Path(root_p) / f
                    arcname = full_p.relative_to(jianying_draft_path.parent)
                    zf.write(full_p, arcname)
        print(f"  草稿包已上传至云盘: {zip_path}")

        # 保存元数据清单
        manifest_path = local_proj_dir / "draft_manifest.json"
        manifest_data = {
            "name": proj_title,
            "day": day_num,
            "total_duration_sec": total_sec,
            "total_dur_us": total_audio_dur_us,
            "missing_materials": missing_materials,
            "sentences_count": len(proj["sentences"]),
            "shots_count": 5
        }
        manifest_path.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2), encoding="utf-8")

        # 整理当天汇报行
        missing_str = "、".join(missing_materials) if missing_materials else "无"
        summary_report.append({
            "day": f"D{day_num}",
            "name": proj_title,
            "duration": f"{total_sec}秒",
            "missing": missing_str,
            "missing_audios": [f"AUD_D{day_num}_S{s:02d}" for s in range(1, 9)]
        })

    print("\n=== 装配完成，汇报结果 ===")
    for item in summary_report:
        print(f"已装配 {item['day']}、总时长 {item['duration']}、缺失素材：{item['missing']}")

if __name__ == "__main__":
    asyncio.run(main())
