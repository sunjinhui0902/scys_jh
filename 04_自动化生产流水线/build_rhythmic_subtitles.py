import os
from workspace_paths import ROOT, EP1, JIANYING, FONT_DIR as PORTABLE_FONT_DIR, ffmpeg, font
import asyncio
import subprocess
import pymediainfo
import edge_tts
import pyJianYingDraft as draft

PROJECT_DIR = str(EP1)
IMG_DIR = os.path.join(PROJECT_DIR, "02_分镜视觉素材")
GPT_DIR = os.path.join(IMG_DIR, "gpt_masterpieces")
AI_DIR = os.path.join(IMG_DIR, "ai_images")
REAL_DIR = os.path.join(IMG_DIR, "real_images")
AUDIO_DIR = os.path.join(PROJECT_DIR, "03_配音音频")
CLAUSE_AUDIO_DIR = os.path.join(AUDIO_DIR, "clause_audios")
CLIPS_DIR = os.path.join(PROJECT_DIR, "05_高清成片导出", "rhythmic_clips")
os.makedirs(CLAUSE_AUDIO_DIR, exist_ok=True)
os.makedirs(CLIPS_DIR, exist_ok=True)

FFMPEG = ffmpeg()
JIANYING_DRAFTS_DIR = str(JIANYING)
DRAFT_NAME = "【带货二创】山西古建三大奇迹_短句爆款字幕版"

# Visual Materials
COVER_IMG = os.path.join(IMG_DIR, "cover_packaging_epic_gpt.jpg")
TEMPLE_GPT = os.path.join(GPT_DIR, "gpt_epic_cliff_temple.jpg")
DOUGONG_GPT = os.path.join(GPT_DIR, "gpt_dougong_exploded_diagram.jpg")
BOOK_IMG = os.path.join(AI_DIR, "chinese_arch_book_open_1791686187608.jpg")

REAL_FOGUANG = os.path.join(REAL_DIR, "scene1_shanxi_foguang_overview.jpg")
REAL_DOUGONG = os.path.join(REAL_DIR, "scene2_timber_dougong_structure.jpg")
AI_BEAM = os.path.join(AI_DIR, "timber_beam_structure_1791685456832.jpg")
REAL_CHONGFU = os.path.join(REAL_DIR, "scene3_chongfu_temple_shuozhou.jpg")
AI_TEMPLE = os.path.join(AI_DIR, "shanxi_temple_hall_1791685429020.jpg")
REAL_YONGLE = os.path.join(REAL_DIR, "scene4_yonglegong_exterior.jpg")
REAL_MURAL = os.path.join(REAL_DIR, "scene4_yonglegong_mural_chaoyuantu.jpg")

# 39 Short Rhythmic Clauses (短断句，每句 5-11 字，卡点口播)
# 首页用 GPT 封面与大殿；中间全部用真实古建与壁画；尾页用 GPT 3D 斗拱爆炸图与中文典藏大书！
CLAUSES = [
    # === 首页 (Hook: 0-7) -> GPT 封面与史诗大殿 ===
    {"text": "从五代到元代的木构国宝", "img": COVER_IMG,    "motion": "pull"},
    {"text": "全国大半都在山西",       "img": COVER_IMG,    "motion": "pull"},
    {"text": "但90%的人不知道",        "img": TEMPLE_GPT,   "motion": "push"},
    {"text": "这里还藏着三大建筑奇迹", "img": TEMPLE_GPT,   "motion": "push"},
    {"text": "断了梁的殿",             "img": TEMPLE_GPT,   "motion": "push"},
    {"text": "抽掉柱的堂",             "img": REAL_FOGUANG, "motion": "tilt_up"},
    {"text": "拆散又拼回来的宫",       "img": REAL_FOGUANG, "motion": "tilt_up"},

    # === 奇迹一：高平崇明寺·断梁殿 (7-14) -> 真实古建 ===
    {"text": "第一个奇迹",             "img": REAL_DOUGONG, "motion": "push"},
    {"text": "高平崇明寺·断梁殿",      "img": REAL_DOUGONG, "motion": "push"},
    {"text": "中佛殿的主梁",           "img": AI_BEAM,      "motion": "tilt_down"},
    {"text": "竟是用两截短木拼接的",   "img": AI_BEAM,      "motion": "tilt_down"},
    {"text": "古代匠人在接缝下方",     "img": REAL_DOUGONG, "motion": "push"},
    {"text": "加了一道顺栿串承托",     "img": REAL_DOUGONG, "motion": "push"},
    {"text": "用天才的力学平衡",       "img": REAL_DOUGONG, "motion": "pull"},
    {"text": "稳稳扛过了一千多年",     "img": REAL_DOUGONG, "motion": "pull"},

    # === 奇迹二：朔州崇福寺·减柱造 (15-23) -> 真实古建 ===
    {"text": "第二个奇迹",             "img": REAL_CHONGFU, "motion": "push"},
    {"text": "朔州崇福寺·减柱造",      "img": REAL_CHONGFU, "motion": "push"},
    {"text": "走进弥陀殿",             "img": AI_TEMPLE,    "motion": "pan_right"},
    {"text": "殿内空旷得不可思议",     "img": AI_TEMPLE,    "motion": "pan_right"},
    {"text": "为了让视野完全开阔",     "img": REAL_CHONGFU, "motion": "tilt_up"},
    {"text": "直接打破传统网格",       "img": REAL_CHONGFU, "motion": "tilt_up"},
    {"text": "硬生生抽掉了所有承重柱", "img": AI_TEMPLE,    "motion": "push"},
    {"text": "这种减柱移柱的精妙计算", "img": AI_TEMPLE,    "motion": "push"},
    {"text": "至今让人叹为观止",       "img": REAL_CHONGFU, "motion": "pull"},

    # === 奇迹三：芮城永乐宫·大搬迁 (24-32) -> 真实古建与壁画 ===
    {"text": "第三个奇迹",             "img": REAL_YONGLE,  "motion": "push"},
    {"text": "拆散重生的永乐宫",       "img": REAL_YONGLE,  "motion": "push"},
    {"text": "上世纪五十年代修水库",   "img": REAL_YONGLE,  "motion": "pull"},
    {"text": "全国顶级专家把整座宫殿", "img": REAL_YONGLE,  "motion": "pull"},
    {"text": "连同近千平米的绝美壁画", "img": REAL_MURAL,   "motion": "pan_right"},
    {"text": "逐一编号拆解",           "img": REAL_MURAL,   "motion": "pan_right"},
    {"text": "异地搬迁二十公里后",     "img": REAL_YONGLE,  "motion": "push"},
    {"text": "重新拼装复原",           "img": REAL_YONGLE,  "motion": "push"},
    {"text": "成就了世界文物史上的传奇", "img": REAL_MURAL, "motion": "pan_right"},

    # === 尾页 (带货转化: 33-38) -> GPT 3D斗拱爆炸图 + 中文典藏大书 ===
    {"text": "如果不翻开这本书",       "img": DOUGONG_GPT,  "motion": "tilt_down"},
    {"text": "你很难真正读懂",         "img": DOUGONG_GPT,  "motion": "tilt_down"},
    {"text": "古人用榫卯创造的力学奇迹", "img": DOUGONG_GPT,"motion": "push"},
    {"text": "想彻底看懂中国古建密码", "img": BOOK_IMG,     "motion": "push"},
    {"text": "这本带详细手绘图解的大书", "img": BOOK_IMG,   "motion": "pan_right"},
    {"text": "每一页都值得带回家品读", "img": BOOK_IMG,     "motion": "pull"}
]

def format_time_srt(sec: float) -> str:
    millis = int((sec - int(sec)) * 1000)
    total_sec = int(sec)
    s = total_sec % 60
    m = (total_sec // 60) % 60
    h = total_sec // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{millis:03d}"

def build_vf(motion: str, total_frames: int) -> str:
    if motion == "push":
        zp = f"zoompan=z='min(zoom+0.0006,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s=1080x1920:fps=25"
    elif motion == "pull":
        zp = f"zoompan=z='if(lte(on,1),1.15,max(1.0,1.15-0.0006*on))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s=1080x1920:fps=25"
    elif motion == "pan_right":
        zp = f"zoompan=z='1.15':x='(on/{total_frames})*(iw-iw/zoom)':y='ih/2-(ih/zoom/2)':d={total_frames}:s=1080x1920:fps=25"
    elif motion == "tilt_up":
        zp = f"zoompan=z='1.15':x='iw/2-(iw/zoom/2)':y='(1-on/{total_frames})*(ih-ih/zoom)':d={total_frames}:s=1080x1920:fps=25"
    elif motion == "tilt_down":
        zp = f"zoompan=z='1.15':x='iw/2-(iw/zoom/2)':y='(on/{total_frames})*(ih-ih/zoom)':d={total_frames}:s=1080x1920:fps=25"
    else:
        zp = f"zoompan=z='min(zoom+0.0005,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s=1080x1920:fps=25"
    return f"scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,{zp}"

async def main():
    print("=== Step 1: Synthesizing 39 Rhythmic Short Clauses ===")
    timed_clauses = []
    current_time = 0.0
    pause = 0.15 # Natural rapid pause between punchy clauses
    
    for idx, c in enumerate(CLAUSES):
        aud_path = os.path.join(CLAUSE_AUDIO_DIR, f"clause_{idx:02d}.mp3")
        comm = edge_tts.Communicate(c["text"], voice="zh-CN-YunjianNeural", rate="-4%", pitch="-2Hz")
        await comm.save(aud_path)
        
        mi = pymediainfo.MediaInfo.parse(aud_path)
        dur = 2.0
        for t in mi.tracks:
            if t.track_type == "Audio":
                dur = float(t.duration) / 1000.0
                break
        
        start_t = current_time
        end_t = start_t + dur
        current_time = end_t + pause
        
        timed_clauses.append({
            "idx": idx,
            "text": c["text"],
            "img": c["img"],
            "motion": c["motion"],
            "aud_path": aud_path,
            "start": start_t,
            "end": end_t,
            "dur": dur
        })
        print(f"[{start_t:.2f}s - {end_t:.2f}s] ({len(c['text'])}字) {c['text']}")

    total_dur = current_time
    print(f"\nTotal Video Duration: {total_dur:.2f} seconds across {len(timed_clauses)} short clauses.")

    print("\n=== Step 2: Generating Short-Phrase SRT Subtitles ===")
    srt_path = os.path.join(PROJECT_DIR, "01_文案与分镜", "subtitles_rhythmic.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        for idx, tc in enumerate(timed_clauses):
            f.write(f"{idx + 1}\n")
            f.write(f"{format_time_srt(tc['start'])} --> {format_time_srt(tc['end'])}\n")
            f.write(f"{tc['text']}\n\n")
    print(f"SRT saved: {srt_path}")

    print("\n=== Step 3: Rendering Video Clips with Dynamic Motion ===")
    clip_files = []
    for idx, tc in enumerate(timed_clauses):
        out_clip = os.path.join(CLIPS_DIR, f"clip_{idx:02d}.mp4")
        clip_files.append(out_clip)
        
        total_frames = int(tc["dur"] * 25) + 4
        vf = build_vf(tc["motion"], total_frames)
        
        cmd = [
            FFMPEG, "-y",
            "-loop", "1", "-i", tc["img"],
            "-i", tc["aud_path"],
            "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            out_clip
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if (idx + 1) % 5 == 0 or idx == len(timed_clauses) - 1:
            print(f"Rendered {idx + 1}/{len(timed_clauses)} clips...")

    print("\n=== Step 4: Concatenating and Burning Short-Phrase Subtitles ===")
    concat_txt = os.path.join(CLIPS_DIR, "concat.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for c in clip_files:
            p = c.replace("\\", "/")
            f.write(f"file '{p}'\n")

    raw_concat_mp4 = os.path.join(PROJECT_DIR, "05_高清成片导出", "raw_rhythmic_concat.mp4")
    cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", concat_txt, "-c", "copy", raw_concat_mp4]
    subprocess.run(cmd, check=True)

    # Reference screenshot styling:
    # Large bold white text + Heavy solid black outline
    # MarginV=560 positions the subtitle right above the bottom interaction area!
    final_mp4 = os.path.join(PROJECT_DIR, "05_高清成片导出", "山西古建三大奇迹_短句爆款字幕版.mp4")
    srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")
    sub_style = (
        f"subtitles='{srt_escaped}':force_style="
        "'FontName=Microsoft YaHei,FontSize=26,Bold=1,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,"
        "Outline=4.5,Shadow=0,Alignment=2,MarginV=560'"
    )
    
    cmd = [
        FFMPEG, "-y",
        "-i", raw_concat_mp4,
        "-vf", sub_style,
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        final_mp4
    ]
    subprocess.run(cmd, check=True)
    print(f"\nFinal Short-Phrase Subtitle MP4 successfully rendered:\n{final_mp4} ({os.path.getsize(final_mp4)} bytes)")

    print("\n=== Step 5: Creating Jianying Pro Draft Project ===")
    folder = draft.DraftFolder(JIANYING_DRAFTS_DIR)
    script = folder.create_draft(DRAFT_NAME, width=1080, height=1920, fps=30, allow_replace=True)
    script.append_track(draft.TrackSpec(draft.TrackType.video, name="画面轨"))
    script.append_track(draft.TrackSpec(draft.TrackType.audio, name="解说配音轨"))

    cur_us = 0
    pause_us = int(pause * 1_000_000)
    for idx, tc in enumerate(timed_clauses):
        dur_us = int(tc["dur"] * 1_000_000)
        
        v_seg = draft.VideoSegment(tc["img"], draft.Timerange(cur_us, dur_us + pause_us))
        script.add_segment(v_seg)
        a_seg = draft.AudioSegment(tc["aud_path"], draft.Timerange(cur_us, dur_us))
        script.add_segment(a_seg)
        cur_us += dur_us + pause_us

    # Jianying Large White Subtitle Style:
    # Size 13.5 (large bold), White color, Solid Black Border
    # Position: transform_y = -0.28 (around 65% height, matching reference screenshot)
    text_style = draft.TextStyle(
        size=13.5,
        bold=True,
        color=(1.0, 1.0, 1.0),
        align=1,
        auto_wrapping=True,
        max_line_width=0.75
    )
    clip_pos = draft.ClipSettings(transform_y=-0.28)
    
    script.import_srt(
        srt_path,
        track_name="短句口播字幕",
        text_style=text_style,
        clip_settings=clip_pos
    )
    script.save()
    print(f"Jianying Draft updated: {DRAFT_NAME}")

if __name__ == "__main__":
    asyncio.run(main())
