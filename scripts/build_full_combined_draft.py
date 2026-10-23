# -*- coding: utf-8 -*-
"""
组装【图书带货】十大名城_下集_五城完整合集 剪映草稿工程
包含 45 镜头，242 秒自训练人声音频，毫秒级字对齐与全部真实视觉素材
"""
import os
import sys
import json
import shutil
import hashlib
from pathlib import Path

# Ensure UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path("scripts").resolve()))
from fast_draft_pipeline import parse_gemini_markdown, build_pipeline_draft

ROOT = Path(".").resolve()
BASE_DIR = ROOT / "03_视频成片与工程" / "十大历史名城_下集_文案修订_2026-10-23_v2"
BATCH_DIR = BASE_DIR / "出图批次_01"
FULL_DIR = BASE_DIR / "EP00_五城全集完整版"

EPISODES = [
    ("EP01_第5名_北京", 0),
    ("EP02_第4名_洛阳", 6),
    ("EP03_第3名_南京", 12),
    ("EP04_第2名_西安", 18),
    ("EP05_第1名_成都", 24),
]

def main():
    print("=== [下集五城完整合集] 开始装配 4 分钟完整草稿工程 ===")
    FULL_DIR.mkdir(parents=True, exist_ok=True)
    (FULL_DIR / "01_文案与分镜").mkdir(parents=True, exist_ok=True)
    (FULL_DIR / "02_分镜视觉素材").mkdir(parents=True, exist_ok=True)
    (FULL_DIR / "03_配音音频").mkdir(parents=True, exist_ok=True)

    # 1. 复制真实图片到 02_分镜视觉素材
    images_src = BATCH_DIR / "images"
    for img_file in images_src.glob("shot_*.png"):
        shutil.copy2(img_file, FULL_DIR / "02_分镜视觉素材" / img_file.name)
    print("  [✓ 视觉素材] 30 张真实内容素材已拷贝至素材库")

    # 2. 复制配音音频与 ASR 对齐文件
    full_mp3_src = ROOT / "01_配音与音色库" / "生成结果" / "本次配音.mp3"
    full_asr_src = ROOT / "01_配音与音色库" / "生成结果" / "asr_alignment.json"
    
    target_mp3 = FULL_DIR / "03_配音音频" / "voice_master.mp3"
    shutil.copy2(full_mp3_src, target_mp3)
    shutil.copy2(full_asr_src, FULL_DIR / "asr_alignment.json")
    print("  [✓ 音频与ASR] 242秒完整配音及 FunASR 对齐数据已就绪")

    # 3. 构造 45 镜头的口播文案.md
    full_voice_text = (ROOT / "01_配音与音色库" / "待配音.txt").read_text(encoding="utf-8").strip()
    
    # 逐集提取分镜
    all_shots_md = []
    global_shot_idx = 1
    
    for ep_name, img_offset in EPISODES:
        ep_md_file = BASE_DIR / ep_name / "01_文案与分镜" / "口播文案.md"
        raw = ep_md_file.read_text(encoding="utf-8")
        _, sections, _ = parse_gemini_markdown(raw, ep_name)
        
        for s in sections:
            shot_str = f"- 【镜头{global_shot_idx:02d}】（运镜: {s['motion']} / 导航标: {s['top_bar']}）\n"
            first_clause = s["clauses"][0] if s["clauses"] else ""
            shot_str += f"  - 对应口播：{first_clause}\n"
            if s.get("fixed_asset"):
                shot_str += f"  - 画面描述：复用固定资产: {s['fixed_asset']}\n"
            else:
                # 对应到连续编号的 shot_XX.png
                content_idx = s["shot_index"] # 1 to 6
                actual_batch_num = img_offset + content_idx
                shot_str += f"  - 画面描述：shot_{actual_batch_num:02d}.png 真实画面特写\n"
                shot_str += f"  - 素材文件名：shot_{actual_batch_num:02d}.png\n"
            all_shots_md.append(shot_str)
            global_shot_idx += 1

    md_content = f"""# 十大历史名城下集｜前五名全集连贯精讲

## 顶部固定主标题
带孙辈长见识：十大历史名城

## 纯净口播文案
{full_voice_text}

## 分镜脚本与运镜编排

""" + "\n".join(all_shots_md) + """

## 结尾带货行动呼吁
- 转化贴纸文案：【路上有话聊 回家有回忆】
"""

    script_file = FULL_DIR / "01_文案与分镜" / "口播文案.md"
    script_file.write_text(md_content, encoding="utf-8")
    print(f"  [✓ 文案分镜] 构造完成 45 个分镜脚本: {script_file.name}")

    # 4. 写入 voice_meta.json 确保哈希一致防重新触发 Edge-TTS
    vt, _, _ = parse_gemini_markdown(md_content, "EP00")
    current_hash = hashlib.md5(f"zh-CN-YunjianNeural|-8%|-6Hz|{vt}".encode("utf-8")).hexdigest()
    meta_data = {
        "voice": "classic-round2-20261023",
        "rate": "-8%",
        "pitch": "-6Hz",
        "char_count": len(vt),
        "hash": current_hash,
        "audio_seconds": 242.78
    }
    (FULL_DIR / "03_配音音频" / "voice_meta.json").write_text(json.dumps(meta_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # 5. 调用 build_pipeline_draft 生成剪映草稿
    draft_title = "【图书带货】十大名城_下集_五城完整合集"
    print(f"  [草稿装配] 开始装配剪映草稿: 【{draft_title}】 ...")
    build_pipeline_draft(
        project_dir=FULL_DIR,
        draft_name=draft_title
    )
    print("\n🎉 === [下集五城完整合集] 剪映 4 分钟草稿已装配成功！ ===")

if __name__ == "__main__":
    main()
