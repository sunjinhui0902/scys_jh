import os
import sys
import re
import json
import shutil
import asyncio
from pathlib import Path
from PIL import Image, ImageFilter, ImageEnhance

# UTF-8 编码安全保障
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path("d:/fuye")
PKG_DIR = ROOT / "07_每日选题与目标" / "第一周21条交接包"
PROJ_ROOT = ROOT / "03_视频成片与工程"
BOOKS_ROOT = ROOT / "02_公共资产库" / "03_书图"

# 7 本书与各编号映射
BOOK_MAP = {
    "M1": BOOKS_ROOT / "戒掉手机自律书" / "戒掉手机自律书_封面.jpg",
    "M2": BOOKS_ROOT / "戒掉手机自律书" / "戒掉手机自律书_封面.jpg",
    "M3": BOOKS_ROOT / "戒掉手机自律书" / "戒掉手机自律书_封面.jpg",
    "M6": BOOKS_ROOT / "冷门知识1000问" / "冷门知识1000问_封面.jpg",
    "M7": BOOKS_ROOT / "冷门知识1000问" / "冷门知识1000问_封面.jpg",
    "N1": BOOKS_ROOT / "冷门知识1000问" / "冷门知识1000问_封面.jpg",
    "N2": BOOKS_ROOT / "冷门知识1000问" / "冷门知识1000问_封面.jpg",
    "N4": BOOKS_ROOT / "冷门知识1000问" / "冷门知识1000问_封面.jpg",
    "N7": BOOKS_ROOT / "冷门知识1000问" / "冷门知识1000问_封面.jpg",
    "M4": BOOKS_ROOT / "2027古诗日历" / "古诗日历_主图.jpg",
    "M5": BOOKS_ROOT / "2027古诗日历" / "古诗日历_主图.jpg",
    "N3": BOOKS_ROOT / "2027古诗日历" / "古诗日历_主图.jpg",
    "N5": BOOKS_ROOT / "2027古诗日历" / "古诗日历_主图.jpg",
    "N6": BOOKS_ROOT / "2027古诗日历" / "古诗日历_主图.jpg",
    "W1": BOOKS_ROOT / "中国人的规矩" / "中国人的规矩_封面.jpg",
    "W4": BOOKS_ROOT / "中国人的规矩" / "中国人的规矩_封面.jpg",
    "W7": BOOKS_ROOT / "中国人的规矩" / "中国人的规矩_封面.jpg",
    "W2": BOOKS_ROOT / "被遗忘的后半句" / "被遗忘的后半句_封面.jpg",
    "W6": BOOKS_ROOT / "被遗忘的后半句" / "被遗忘的后半句_封面.jpg",
    "W3": BOOKS_ROOT / "中国式人情世故" / "中国式人情世故_封面.jpg",
    "W5": BOOKS_ROOT / "愿你慢慢长大" / "愿你慢慢长大_封面.jpg",
}

# 超时备删句规则（超过 78 秒才删）
TIMEOUT_TRIM_RULES = {
    "W2": "一家人把难处摊开说，比憋着强。",
    "N7": "下次去，先在广场中央找三大殿，再把御花园标在北边，一张图就看懂了。",
    "N4": "它不用电，不用人，"
}

def make_book_cover_9_16(src_path: Path, out_path: Path):
    """将封面图处理为 9:16 毛玻璃底衬 + 立体书封"""
    im = Image.open(src_path).convert("RGBA")
    target_w, target_h = 1080, 1920
    
    aspect = im.width / im.height
    target_aspect = target_w / target_h
    if aspect > target_aspect:
        bg_h = target_h
        bg_w = int(bg_h * aspect)
    else:
        bg_w = target_w
        bg_h = int(bg_w / aspect)
    
    bg = im.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
    left = (bg_w - target_w) // 2
    top = (bg_h - target_h) // 2
    bg = bg.crop((left, top, left + target_w, top + target_h))
    
    bg = bg.filter(ImageFilter.GaussianBlur(radius=40))
    enhancer = ImageEnhance.Brightness(bg)
    bg = enhancer.enhance(0.7)
    
    book_w = 780
    book_h = int(book_w / aspect)
    fg = im.resize((book_w, book_h), Image.Resampling.LANCZOS)
    
    shadow = Image.new("RGBA", (book_w + 40, book_h + 40), (0, 0, 0, 0))
    shadow_box = Image.new("RGBA", (book_w, book_h), (0, 0, 0, 140))
    shadow.paste(shadow_box, (20, 20))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=20))
    
    fg_x = (target_w - book_w) // 2
    fg_y = 480
    
    bg.paste(shadow, (fg_x - 20, fg_y - 20), shadow)
    bg.paste(fg, (fg_x, fg_y), fg)
    
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bg.convert("RGB").save(out_path, "PNG", quality=95)

def parse_card(card_text: str, voice_text: str, code_id: str):
    """从制作卡提取元数据并智能切分 6 个分镜与对应口播"""
    # 1. 封面大字
    m_cover = re.search(r"\*\*封面大字\*\*[：:]\s*(.*?)(?=\n|\Z)", card_text)
    cover_title = m_cover.group(1).strip() if m_cover else code_id
    
    # 2. 转化贴纸
    m_sticker = re.search(r"置顶评论.*?自备[：:]\s*(.*?)(?=\n|\Z)", card_text)
    sticker_text = "支持先用后付 橱窗直接拍"
    if "戒手机" in card_text or "自律" in card_text:
        sticker_text = "买回去和儿女一起看 评论区说个实数"
    elif "冷知识" in card_text or "冷门知识" in card_text:
        sticker_text = "地理生活冷知识 橱窗直接拍"
    elif "规矩" in card_text or "人情" in card_text:
        sticker_text = "懂规矩有分寸 橱窗放心拍"
    elif "日历" in card_text or "古诗" in card_text:
        sticker_text = "每天一首古诗 陪孩子慢慢读"
    elif "长大" in card_text:
        sticker_text = "不催他长大 陪他慢慢来"
    elif "后半句" in card_text:
        sticker_text = "老话里的真智慧 橱窗翻一翻"

    # 3. 提取分镜列表
    shot_lines = []
    in_shots = False
    for line in card_text.splitlines():
        line = line.strip()
        if re.match(r"\*\*分镜.*?镜[）\)]", line) or "**分镜" in line:
            in_shots = True
            continue
        if in_shots:
            if line.startswith("**") or line.startswith("---") or line.startswith("##"):
                break
            if re.match(r"^\d+[\.、]", line):
                shot_lines.append(line)
    
    parsed_shots = []
    for s_str in shot_lines:
        idx_match = re.match(r"^(\d+)[\.、]\s*(.*)", s_str)
        if not idx_match:
            continue
        idx = int(idx_match.group(1))
        content = idx_match.group(2)
        
        # 运镜
        motion = "push"
        m_motion = re.search(r"[（\(](push|pull|pan_right|pan_left|tilt_up|tilt_down|static|静止|静止微推)[）\)]", content, re.I)
        if m_motion:
            raw_m = m_motion.group(1).lower()
            if "pull" in raw_m:
                motion = "pull"
            elif "pan_right" in raw_m:
                motion = "pan_right"
            elif "pan_left" in raw_m:
                motion = "pan_left"
            elif "tilt" in raw_m:
                motion = "tilt_up"
            elif "静止" in raw_m or "static" in raw_m:
                motion = "push"
            else:
                motion = "push"
        
        desc = re.sub(r"[（\(].*?[）\)]", "", content).strip()
        parsed_shots.append({
            "index": idx,
            "motion": motion,
            "desc": desc
        })
    
    # 确保有 6 个镜头
    while len(parsed_shots) < 6:
        idx = len(parsed_shots) + 1
        parsed_shots.append({
            "index": idx,
            "motion": "push",
            "desc": "相关内容特写展示" if idx < 6 else "书本实拍 + 橱窗指引贴纸位"
        })
    parsed_shots = parsed_shots[:6]
    parsed_shots[-1]["desc"] = "书本实拍 + 橱窗指引贴纸位"
    
    # 4. 将纯净口播按句子切分并分配给前 5 镜 + 第 6 镜
    # 中文主标点断句
    raw_sentences = [s.strip() for s in re.split(r"([。！？；])", voice_text) if s.strip()]
    full_sentences = []
    for i in range(0, len(raw_sentences), 2):
        s = raw_sentences[i]
        punct = raw_sentences[i+1] if i+1 < len(raw_sentences) else ""
        if s:
            full_sentences.append(s + punct)
    
    # 将句子平分到 6 个镜头（前 5 镜各约 15~20%，第 6 镜为带货行动）
    total_s = len(full_sentences)
    shot_sentences = [[] for _ in range(6)]
    
    if total_s >= 6:
        # 分配比例
        ratios = [1, 1, 1, 1, 1, 2] # 第 6 镜承接带货与问答
        weights_sum = sum(ratios)
        cur_idx = 0
        for i in range(6):
            take = max(1, round(total_s * (ratios[i] / weights_sum)))
            if i == 5:
                shot_sentences[i] = full_sentences[cur_idx:]
            else:
                shot_sentences[i] = full_sentences[cur_idx:cur_idx + take]
                cur_idx += take
            if not shot_sentences[i] and cur_idx < total_s:
                shot_sentences[i] = [full_sentences[cur_idx]]
                cur_idx += 1
    else:
        for idx, sent in enumerate(full_sentences):
            shot_sentences[min(idx, 5)].append(sent)
        for i in range(6):
            if not shot_sentences[i]:
                shot_sentences[i] = shot_sentences[max(0, i-1)][-1:] if shot_sentences[max(0, i-1)] else ["精彩继续"]
    
    # 为每个镜头设置导航标
    nav_labels = [
        f"开篇精讲：{cover_title[:10]}",
        "核心要点分析",
        "细节与深入理解",
        "长辈支招经验",
        "举一反三总结",
        "橱窗精选推荐"
    ]
    
    return cover_title, parsed_shots, shot_sentences, nav_labels, sticker_text

def build_project_files(folder_name: str):
    dir_p = PKG_DIR / folder_name
    proj_dir = PROJ_ROOT / folder_name
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "01_文案与分镜").mkdir(parents=True, exist_ok=True)
    (proj_dir / "02_分镜视觉素材").mkdir(parents=True, exist_ok=True)
    
    # 拷贝原文
    shutil.copy2(dir_p / "口播.txt", proj_dir / "口播.txt")
    shutil.copy2(dir_p / "制作卡.md", proj_dir / "制作卡.md")
    shutil.copy2(dir_p / "口播.txt", proj_dir / "01_文案与分镜" / "口播.txt")
    shutil.copy2(dir_p / "制作卡.md", proj_dir / "01_文案与分镜" / "制作卡.md")
    
    voice_raw = (proj_dir / "口播.txt").read_text(encoding="utf-8").strip()
    card_raw = (proj_dir / "制作卡.md").read_text(encoding="utf-8").strip()
    
    code_id = folder_name.split("_")[0]
    cover_title, shots, shot_sentences, nav_labels, sticker_text = parse_card(card_raw, voice_raw, code_id)
    
    # 组装 01_文案与分镜/口播文案.md
    shots_md_blocks = []
    for s in shots:
        idx = s["index"]
        motion = s["motion"]
        desc = s["desc"]
        nav = nav_labels[idx - 1]
        clauses_text = "".join(shot_sentences[idx - 1])
        
        block = f"""- 【镜头{idx:02d}】（运镜: {motion} / 导航标: {nav}）
  - 对应口播：{clauses_text}
  - 画面描述：{desc}"""
        shots_md_blocks.append(block)
    
    script_content = f"""# 视频项目名：【{folder_name}】

## 顶部固定主标题
{cover_title}

## 纯净口播文案
{voice_raw}

## 分镜脚本与运镜编排
{chr(10).join(shots_md_blocks)}

## 结尾带货行动呼吁
- 转化贴纸文案：【{sticker_text}】
"""
    (proj_dir / "01_文案与分镜" / "口播文案.md").write_text(script_content, encoding="utf-8")
    
    # 生成第 06 镜书本封面实拍
    book_src = BOOK_MAP.get(code_id)
    if book_src and book_src.is_file():
        dst_cover = proj_dir / "02_分镜视觉素材" / "shot_06.png"
        make_book_cover_9_16(book_src, dst_cover)
    
    return proj_dir, voice_raw, code_id

print("Helper functions ready!")

REMAINING_FOLDERS = [
    # 批次 2 (11-04)
    "M6_11-04_0700", "N2_11-04_1230", "W2_11-04_1900",
    # 批次 3 (11-05)
    "M4_11-05_0700", "N3_11-05_1230", "W3_11-05_1900",
    # 批次 4 (11-06)
    "M2_11-06_0700", "N4_11-06_1230", "W4_11-06_1900",
    # 批次 5 (11-07)
    "M5_11-07_0700", "N5_11-07_1230", "W5_11-07_1900",
    # 批次 6 (11-08)
    "M3_11-08_0700", "N6_11-08_1230", "W6_11-08_1900",
    # 批次 7 (11-09)
    "M7_11-09_0700", "N7_11-09_1230", "W7_11-09_1900"
]

def main():
    import subprocess
    results = []
    
    for idx, folder in enumerate(REMAINING_FOLDERS, 1):
        print(f"\n========================================================")
        print(f"[{idx}/18] 开始装配草稿: {folder}")
        print(f"========================================================")
        
        proj_dir, voice_raw, code_id = build_project_files(folder)
        
        # 执行 init 命令
        cmd = [sys.executable, str(ROOT / "scripts" / "fast_draft_pipeline.py"), "init", "--dir", str(proj_dir)]
        subprocess.run(cmd, check=True)
        
        # 检查 manifest
        manifest_p = proj_dir / "draft_manifest.json"
        manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
        dur_s = round(manifest["total_dur_us"] / 1_000_000, 2)
        
        # 超时检查（> 78秒）
        trimmed = False
        trim_sentence = TIMEOUT_TRIM_RULES.get(code_id)
        if dur_s > 78.0 and trim_sentence and trim_sentence in voice_raw:
            print(f"⚠️ [时长超时告警] 实际时长 {dur_s}s > 78s，执行超时备删句: 删【{trim_sentence}】并重跑配音...")
            trimmed_voice = voice_raw.replace(trim_sentence, "")
            
            # 重新写入纯净口播
            (proj_dir / "口播.txt").write_text(trimmed_voice, encoding="utf-8")
            (proj_dir / "01_文案与分镜" / "口播.txt").write_text(trimmed_voice, encoding="utf-8")
            
            # 重建工程文件
            cover_title, shots, shot_sentences, nav_labels, sticker_text = parse_card(
                (proj_dir / "制作卡.md").read_text(encoding="utf-8"), trimmed_voice, code_id
            )
            shots_md_blocks = []
            for s in shots:
                s_idx = s["index"]
                block = f"- 【镜头{s_idx:02d}】（运镜: {s['motion']} / 导航标: {nav_labels[s_idx-1]}）\n  - 对应口播：{''.join(shot_sentences[s_idx-1])}\n  - 画面描述：{s['desc']}"
                shots_md_blocks.append(block)
            
            script_content = f"# 视频项目名：【{folder}】\n\n## 顶部固定主标题\n{cover_title}\n\n## 纯净口播文案\n{trimmed_voice}\n\n## 分镜脚本与运镜编排\n{chr(10).join(shots_md_blocks)}\n\n## 结尾带货行动呼吁\n- 转化贴纸文案：【{sticker_text}】\n"
            (proj_dir / "01_文案与分镜" / "口播文案.md").write_text(script_content, encoding="utf-8")
            
            # 重新跑 init (force synth)
            subprocess.run([sys.executable, str(ROOT / "scripts" / "fast_draft_pipeline.py"), "init", "--dir", str(proj_dir), "--force-synth"], check=True)
            manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
            dur_s = round(manifest["total_dur_us"] / 1_000_000, 2)
            trimmed = True
        
        # 统计数据
        srt_p = proj_dir / "01_文案与分镜" / "subtitles.srt"
        sub_count = len([b for b in re.split(r"\n\s*\n", srt_p.read_text(encoding="utf-8").strip()) if b.strip()]) if srt_p.exists() else 0
        real_count = sum(1 for s in manifest["shots"] if not s["is_placeholder"])
        placeholder_count = sum(1 for s in manifest["shots"] if s["is_placeholder"])
        
        res_info = {
            "folder": folder,
            "code_id": code_id,
            "title": manifest["draft_title"],
            "duration": dur_s,
            "sub_count": sub_count,
            "real_count": real_count,
            "placeholder_count": placeholder_count,
            "trimmed": trimmed,
            "trim_note": f"删去【{trim_sentence}】" if trimmed else "否"
        }
        results.append(res_info)
        print(f"✓ [{folder}] 装配完成: 时长 {dur_s}s, 字幕 {sub_count}条, 真实画面 {real_count}/6, 占位 {placeholder_count}/6")

    print("\n========================================================")
    print("🎉 全部 18 条草稿装配完毕！")
    print("========================================================")
    for r in results:
        print(f"{r['code_id']:4s} | {r['folder']} | {r['duration']}s | 字幕: {r['sub_count']}条 | 占位: {r['placeholder_count']}个 | 超时删句: {r['trim_note']}")

if __name__ == "__main__":
    main()

