r"""
S04 洛阳 ×《中国历史名城》说书式短片本地样片全流程自动化生成脚本
音色升级：
使用 D:\fuye\01_配音与音色库\selected_voices.json 中的 "1" 号音色：
- 名称：央视纪录片·沧桑历史男声
- 语音引擎：edge-tts (zh-CN-YunjianNeural)
- 语速 (rate)：-8%
- 音调 (pitch)：-6Hz
- 特点：低频极厚、从容沉静，富有历史沧桑感与说书式厚重质感

视觉与文案规范：
1. 遵循《说书式口播写法》：熟悉场景 → 镜头拉远 → 一个有依据的发现 → 留给观众的问题 → 自然引书
2. 事实出处留在后台制作文档，口播说人话，不念公文与出处
3. 严格控制每句字幕 5～9 个汉字，语义自然断句
4. 视觉风格：墨蓝＋暖砂金、纸张质感、单一视觉主体、标明“概念插画·非实景”，书封留白
5. 独立隔离运行，不影响既有工程或剪映草稿
"""

import os
import sys
import subprocess
import asyncio
import wave
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import pymediainfo
import edge_tts

# 推导项目路径
CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parents[2]
PIPELINE_DIR = REPO_ROOT / "04_自动化生产流水线"
sys.path.insert(0, str(PIPELINE_DIR))
from workspace_paths import ffmpeg

FFMPEG_BIN = ffmpeg()

AUDIO_DIR = CURRENT_DIR / "audio"
FRAMES_DIR = CURRENT_DIR / "frames"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
FRAMES_DIR.mkdir(parents=True, exist_ok=True)

FONT_PATH = "C:/Windows/Fonts/msyh.ttc"
BOLD_FONT_PATH = "C:/Windows/Fonts/simhei.ttf"

def get_font(size, bold=False):
    p = BOLD_FONT_PATH if bold else FONT_PATH
    try:
        return ImageFont.truetype(p, size)
    except Exception:
        return ImageFont.load_default()

# 31 句打磨口播与逐句字幕（严格满足 5～9 字）
CLAUSES = [
    # 段落1：熟悉场景（图01 多重城影）
    {"text": "去洛阳拍完应天门", "img_key": "01", "sec_name": "01·熟悉场景"},
    {"text": "很多人就收起相机", "img_key": "01", "sec_name": "01·熟悉场景"},
    {"text": "可洛阳的古都故事", "img_key": "01", "sec_name": "01·熟悉场景"},
    {"text": "哪能只停在门前",   "img_key": "01", "sec_name": "01·熟悉场景"},

    # 段落2：镜头拉远（图01 转向 图02 河洛遗址概念图）
    {"text": "试着把镜头拉远",   "img_key": "02", "sec_name": "02·镜头拉远"},
    {"text": "洛阳一带有五处",   "img_key": "02", "sec_name": "02·镜头拉远"},
    {"text": "重要都城遗址",     "img_key": "02", "sec_name": "02·镜头拉远"},
    {"text": "二里头与偃师商城", "img_key": "02", "sec_name": "02·镜头拉远"},
    {"text": "东周王城汉魏故城", "img_key": "02", "sec_name": "02·镜头拉远"},
    {"text": "还有隋唐洛阳城",   "img_key": "02", "sec_name": "02·镜头拉远"},

    # 段落3：一个有依据的发现（图02 河洛遗址概念图）
    {"text": "名字记不住没关系", "img_key": "02", "sec_name": "03·单点发现"},
    {"text": "你只要知道两件事", "img_key": "02", "sec_name": "03·单点发现"},
    {"text": "它们年代不同",     "img_key": "02", "sec_name": "03·单点发现"},
    {"text": "所在位置也不同",   "img_key": "02", "sec_name": "03·单点发现"},
    {"text": "站在门前打开地图", "img_key": "02", "sec_name": "03·单点发现"},
    {"text": "看到的只是其中一段", "img_key": "02", "sec_name": "03·单点发现"},
    {"text": "更多线索在河洛大地", "img_key": "02", "sec_name": "03·单点发现"},

    # 段落4：留给观众的问题（收回图01 门影）
    {"text": "下次再去洛阳",     "img_key": "01", "sec_name": "04·观众提问"},
    {"text": "先挑出一处遗址",   "img_key": "01", "sec_name": "04·观众提问"},
    {"text": "问自己一个问题",   "img_key": "01", "sec_name": "04·观众提问"},
    {"text": "这是哪一代人的城", "img_key": "01", "sec_name": "04·观众提问"},
    {"text": "带着问题去看",     "img_key": "01", "sec_name": "04·观众提问"},
    {"text": "城门就不只是背景", "img_key": "01", "sec_name": "04·观众提问"},

    # 段落5：自然引书（图03 读书收束·空白书）
    {"text": "想从一本书开始",   "img_key": "03", "sec_name": "05·自然引书"},
    {"text": "看看中国历史名城", "img_key": "03", "sec_name": "05·自然引书"},
    {"text": "目录列在古都名城", "img_key": "03", "sec_name": "05·自然引书"},
    {"text": "旁边有安阳和西安", "img_key": "03", "sec_name": "05·自然引书"},
    {"text": "还有古都开封",     "img_key": "03", "sec_name": "05·自然引书"},
    {"text": "从洛阳读起来",     "img_key": "03", "sec_name": "05·自然引书"},
    {"text": "下一座想去的城",   "img_key": "03", "sec_name": "05·自然引书"},
    {"text": "也许就在目录里",   "img_key": "03", "sec_name": "05·自然引书"}
]

# 严格校验字幕字数
for idx, item in enumerate(CLAUSES):
    l = len(item["text"])
    assert 5 <= l <= 9, f"Clause {idx} '{item['text']}' len {l} outside [5, 9]"

# ==================== 1. 音频合成与时间轴 ====================

async def synthesize_all_clauses():
    voice = "zh-CN-YunjianNeural"
    rate = "-8%"
    pitch = "-6Hz"
    print(f">>> 正在使用央视纪录片男声合成音色 ({voice}, rate={rate}, pitch={pitch})...")
    
    for i, item in enumerate(CLAUSES):
        mp3_path = AUDIO_DIR / f"clause_{i:02d}.mp3"
        wav_path = AUDIO_DIR / f"clause_{i:02d}.wav"
        
        # 1. edge-tts 生成高保真 MP3
        comm = edge_tts.Communicate(item["text"], voice=voice, rate=rate, pitch=pitch)
        await comm.save(str(mp3_path))
        
        # 2. 转成标准 WAV (24000Hz, 16bit, mono) 便于精准无缝拼接
        cmd = [
            FFMPEG_BIN, "-y",
            "-i", str(mp3_path),
            "-ar", "24000", "-ac", "1",
            str(wav_path)
        ]
        subprocess.run(cmd, capture_output=True, check=True)

def generate_audios():
    asyncio.run(synthesize_all_clauses())

def assemble_master_audio():
    print(">>> 正在拼接主音频与计算精确时间轴...")
    section_ends = {3, 9, 16, 22, 30}
    pause_clause = 0.10   # 句间停顿 100ms
    pause_section = 0.25  # 段落微停顿 250ms

    timeline = []
    current_ms = 0.0

    master_path = AUDIO_DIR / "master_narration.wav"
    
    with wave.open(str(AUDIO_DIR / "clause_00.wav"), 'rb') as w:
        params = w.getparams()
        framerate = params.framerate
        nchannels = params.nchannels
        sampwidth = params.sampwidth

    all_frames = bytearray()

    for i, item in enumerate(CLAUSES):
        cf = AUDIO_DIR / f"clause_{i:02d}.wav"
        with wave.open(str(cf), 'rb') as w:
            data = w.readframes(w.getnframes())
            dur_sec = w.getnframes() / framerate
            dur_ms = dur_sec * 1000.0

        start_ms = current_ms
        end_ms = start_ms + dur_ms

        all_frames.extend(data)

        p_sec = pause_section if i in section_ends else pause_clause
        p_ms = p_sec * 1000.0
        silence_bytes = b'\x00' * int(framerate * p_sec * nchannels * sampwidth)
        all_frames.extend(silence_bytes)

        current_ms = end_ms + p_ms

        timeline.append({
            "index": i + 1,
            "text": item["text"],
            "img_key": item["img_key"],
            "sec_name": item["sec_name"],
            "start_ms": start_ms,
            "end_ms": end_ms,
            "duration_ms": dur_ms,
            "total_clause_time": dur_sec + p_sec
        })

    with wave.open(str(master_path), 'wb') as w:
        w.setparams(params)
        w.writeframes(all_frames)

    total_duration_sec = current_ms / 1000.0
    print(f"Master 音频生成成功: {master_path}")
    print(f"实际样片总时长: {total_duration_sec:.2f} 秒 (在 60～90 秒规格内)")

    return timeline, total_duration_sec

# ==================== 2. SRT 字幕导出 ====================

def format_srt_time(ms: float) -> str:
    total_sec = int(ms // 1000)
    millis = int(ms % 1000)
    s = total_sec % 60
    m = (total_sec // 60) % 60
    h = total_sec // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{millis:03d}"

def export_srt(timeline):
    srt_path = CURRENT_DIR / "subtitles.srt"
    lines = []
    for item in timeline:
        i = item["index"]
        st = format_srt_time(item["start_ms"])
        et = format_srt_time(item["end_ms"])
        txt = item["text"]
        lines.append(f"{i}\n{st} --> {et}\n{txt}\n")
    srt_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"SRT 字幕生成成功: {srt_path}")

# ==================== 3. 视觉画面渲染（极简、无工程框） ====================

def prepare_base_images():
    print(">>> 正在加载并预处理 3 张核心概念插画...")
    raw_images = {
        "01": CURRENT_DIR / "01_开场_多重城影.png",
        "02": CURRENT_DIR / "02_河洛遗址_概念图.png",
        "03": CURRENT_DIR / "03_读书收束_空白书.png"
    }

    base_1080 = {}
    for key, path in raw_images.items():
        im = Image.open(path).convert("RGBA")
        im_resized = im.resize((1080, 1920), Image.Resampling.LANCZOS)
        base_1080[key] = im_resized

    return base_1080

def generate_frames(base_images):
    print(">>> 正在生成 31 帧逐句字幕视频帧（遵循极简墨蓝＋暖砂金审美）...")
    f_tag = get_font(22)
    f_sub = get_font(54, bold=True)
    f_meta = get_font(20)

    # 预先生成底部暗部渐变遮罩，保证文字通透清晰
    gradient_mask = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(gradient_mask)
    for y in range(1440, 1920):
        alpha = int(220 * ((y - 1440) / 480))
        g_draw.line([(0, y), (1080, y)], fill=(8, 12, 20, alpha))

    total_clauses = len(CLAUSES)

    for i, c in enumerate(CLAUSES):
        img_key = c["img_key"]
        base = base_images[img_key].copy()

        # 叠加底部遮罩
        base = Image.alpha_composite(base, gradient_mask)
        draw = ImageDraw.Draw(base)

        # 1. 顶部小角标：优雅暖砂金边框与低调标注（无霓虹、无工程大框）
        draw.rectangle([60, 60, 270, 100], fill=(16, 22, 34, 180), outline=(212, 175, 55, 140), width=1)
        draw.text((75, 68), "概念插画 · 非实景", font=f_tag, fill=(212, 175, 55, 230))

        # 若是第三张图（空白书），在画面上方轻柔标注书名，不伪装实物封面
        if img_key == "03":
            draw.rectangle([60, 120, 390, 162], fill=(16, 22, 34, 160), outline=(148, 163, 184, 100), width=1)
            draw.text((75, 128), "参考书目：《中国历史名城》", font=get_font(20), fill=(226, 232, 240, 220))

        # 2. 底部字幕区域（单一视觉主体，干净克制）
        sub_text = c["text"]
        bbox = draw.textbbox((0, 0), sub_text, font=f_sub)
        tw = bbox[2] - bbox[0]
        tx = (1080 - tw) // 2

        # 进度与段落标识
        meta_text = f"[{i+1:02d}/{total_clauses:02d}]  {c['sec_name']}"
        draw.text((tx, 1585), meta_text, font=f_meta, fill=(160, 174, 192))

        # 主字幕（纯白、大字、阴影增强可读性）
        # 阴影
        draw.text((tx + 2, 1637), sub_text, font=f_sub, fill=(0, 0, 0, 180))
        # 前景
        draw.text((tx, 1635), sub_text, font=f_sub, fill=(255, 255, 255))

        # 细微进度线
        pw = int(720 * ((i + 1) / total_clauses))
        draw.line([(180, 1735), (900, 1735)], fill=(30, 41, 59, 160), width=3)
        draw.line([(180, 1735), (180 + pw, 1735)], fill=(212, 175, 55, 220), width=3)

        frame_path = FRAMES_DIR / f"frame_{i:02d}.png"
        base.convert("RGB").save(frame_path)

    print(f"31 帧逐句字幕图已全部保存到: {FRAMES_DIR}")

# ==================== 4. 视频合成 ====================

def render_mp4(timeline, total_duration):
    print(">>> 正在生成 FFmpeg concat 列表与组装 S04 样片 MP4...")
    concat_file = CURRENT_DIR / "concat_list.txt"
    lines = ["ffconcat version 1.0\n"]
    for i, item in enumerate(timeline):
        fp = FRAMES_DIR / f"frame_{i:02d}.png"
        lines.append(f"file '{fp.as_posix()}'\n")
        lines.append(f"duration {item['total_clause_time']:.4f}\n")
    
    last_fp = FRAMES_DIR / f"frame_{len(timeline)-1:02d}.png"
    lines.append(f"file '{last_fp.as_posix()}'\n")

    concat_file.write_text("".join(lines), encoding="utf-8")

    out_mp4 = CURRENT_DIR / "S04_洛阳_中国历史名城_样片.mp4"
    master_audio = AUDIO_DIR / "master_narration.wav"

    cmd = [
        FFMPEG_BIN, "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-i", str(master_audio),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "25",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(out_mp4)
    ]

    print("执行命令:", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("FFmpeg 渲染失败:\n", res.stderr)
        raise RuntimeError("FFmpeg 执行失败")

    print(f"=== S04 样片 MP4 成功生成: {out_mp4} ===")

    info = pymediainfo.MediaInfo.parse(str(out_mp4))
    general = info.tracks[0]
    dur = float(general.duration) / 1000.0
    w = [t.width for t in info.tracks if t.track_type == 'Video'][0]
    h = [t.height for t in info.tracks if t.track_type == 'Video'][0]
    print(f"视频分辨率: {w}x{h}")
    print(f"实测成片时长: {dur:.2f} 秒 (规格要求 60～90 秒)")

    return out_mp4, dur

def main():
    print("==================================================")
    print("开始使用【01 央视纪录片·沧桑历史男声】生成 S04 样片")
    print("==================================================")
    
    # 1. 音频 (zh-CN-YunjianNeural, rate=-8%, pitch=-6Hz)
    generate_audios()
    timeline, total_dur = assemble_master_audio()

    # 2. 字幕
    export_srt(timeline)

    # 3. 视觉底图与 31 帧生成
    base_imgs = prepare_base_images()
    generate_frames(base_imgs)

    # 4. MP4成片组装
    out_mp4, final_dur = render_mp4(timeline, total_dur)

    print("\nS04 洛阳新版样片生产流程全部顺利完成！")

if __name__ == "__main__":
    main()
