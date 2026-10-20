#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Setup asset directories, link audio files, and create clean placeholder cards for testing
so the JianYing draft generator can run end-to-end immediately.
"""

import sys
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = ROOT / "03_视频成片与工程" / "十大历史名城_带孙辈长见识"
ASSETS_DIR = BASE_DIR / "assets"
AUDIO_DIR = ASSETS_DIR / "audio"
IMAGES_DIR = ASSETS_DIR / "images"

AUDIO_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# 1. Audio setup
src_ep1 = BASE_DIR / "上集_第10至第6名" / "03_配音音频" / "voice_master.mp3"
src_ep2 = BASE_DIR / "下集_前五名揭晓" / "03_配音音频" / "voice_master.mp3"
dst_ep1 = AUDIO_DIR / "ep1_voice.mp3"
dst_ep2 = AUDIO_DIR / "ep2_voice.mp3"

if src_ep1.exists() and not dst_ep1.exists():
    shutil.copy2(src_ep1, dst_ep1)
    print(f"✓ 已复制上集音频: {dst_ep1.name}")

if src_ep2.exists() and not dst_ep2.exists():
    shutil.copy2(src_ep2, dst_ep2)
    print(f"✓ 已复制下集音频: {dst_ep2.name}")

# BGM setup
bgm_src = ROOT / "05_爆款知识库与复盘" / "试做产物" / "S04_洛阳_中国历史名城Demo" / "audio" / "bgm_guqin_ambient.mp3"
bgm_dst = AUDIO_DIR / "bgm_guofeng.mp3"
if bgm_src.exists() and not bgm_dst.exists():
    shutil.copy2(bgm_src, bgm_dst)
    print(f"✓ 已就绪国风BGM底轨: {bgm_dst.name}")

# SFX setup
sfx_src = ROOT / "05_爆款知识库与复盘" / "试做产物" / "S04_洛阳_中国历史名城Demo" / "audio" / "sfx_transition.wav"
sfx_dst = AUDIO_DIR / "sfx_ding.wav"
if sfx_src.exists() and not sfx_dst.exists():
    shutil.copy2(sfx_src, sfx_dst)
    print(f"✓ 已就绪清脆叮音效: {sfx_dst.name}")

# 2. Image placeholders setup
REQUIRED_IMAGES = [
    # 上集图片
    ("ep1_01.png", "【上集引子】带孙辈长见识的十大历史名城"),
    ("ep1_02.png", "【第10名·平遥】明清古县城街景与城门"),
    ("ep1_03.png", "【第10名·平遥】日升昌票号柜台与汇票"),
    ("ep1_04.png", "【第9名·延安】宝塔山巍峨远景"),
    ("ep1_05.png", "【第9名·延安】杨家岭窑洞与煤油灯"),
    ("ep1_06.png", "【第8名·开封】清明上河园与虹桥舟楫"),
    ("ep1_07.png", "【第8名·开封】宋朝夜市商贩与包公祠"),
    ("ep1_08.png", "【第7名·苏州】拙政园移步换景与小桥"),
    ("ep1_09.png", "【第7名·苏州】园林花窗与亭台楼阁"),
    ("ep1_10.png", "【第6名·杭州】西湖苏堤漫步与三潭印月"),
    ("ep1_11.png", "【痛点转折】长辈带娃出游如何生动讲解"),
    
    # 下集图片
    ("ep2_01.png", "【第5名·北京】故宫太和殿红墙金瓦与长城"),
    ("ep2_02.png", "【第4名·洛阳】龙门石窟卢舍那大佛盛唐气象"),
    ("ep2_03.png", "【第3名·南京】夫子庙贡院与明孝陵钟山"),
    ("ep2_04.png", "【第2名·西安】秦始皇兵马俑大秦军阵"),
    ("ep2_05.png", "【第2名·西安】古城墙骑行与古城池防守"),
    ("ep2_06.png", "【第1名·成都】千年古蜀与热气腾腾烟火气"),
    ("ep2_07.png", "【第1名·成都】都江堰李冰父子治水千年水利"),
    ("ep2_08.png", "【第1名·成都】杜甫草堂与武侯祠三国英雄"),
    ("ep2_09.png", "【第1名·成都】锦里老茶馆与川剧变脸绝活"),
    ("ep2_10.png", "【下集共鸣】爷孙伴读与景点讲解难题"),
    ("ep2_11.png", "【温情收尾】趁腿脚利索多带孙辈走走看看"),
    
    # 图书素材（两集通用）
    ("book_01.png", "【大美中国】101个一生必去之地烫金封面"),
    ("book_02.png", "【大美中国】手绘地图与现成大白话故事讲解内页"),
    ("book_03.png", "【大美中国】大字大图实景跨页排版展卷")
]

def make_card(name: str, desc: str, out_path: Path):
    if out_path.exists():
        return
    img = Image.new("RGB", (1080, 1920), color=(26, 32, 44))
    draw = ImageDraw.Draw(img)
    
    # Draw simple frame & info
    draw.rectangle([40, 40, 1040, 1880], outline=(212, 175, 55), width=8)
    draw.rectangle([60, 60, 1020, 1860], outline=(80, 90, 110), width=2)
    
    # Save placeholder image
    img.save(str(out_path), "PNG")
    print(f"  [占位图就绪] {name}: {desc}")

print("\n--- 检查与创建视觉资产占位图 (1080x1920) ---")
for fname, desc in REQUIRED_IMAGES:
    make_card(fname, desc, IMAGES_DIR / fname)

print(f"\n🎉 资产池准备完毕: {ASSETS_DIR}")
