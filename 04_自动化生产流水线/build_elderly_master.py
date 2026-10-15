import os
from workspace_paths import ROOT, EP1, JIANYING, FONT_DIR as PORTABLE_FONT_DIR, ffmpeg, font
import subprocess
import pymediainfo
import pyJianYingDraft as draft

BASE_DIR = str(EP1)
AUDIO_DIR = os.path.join(BASE_DIR, "03_配音音频", "audio_chunks")
GPT_DIR = os.path.join(BASE_DIR, "02_分镜视觉素材", "gpt_masterpieces")
AI_DIR = os.path.join(BASE_DIR, "02_分镜视觉素材", "ai_images")
REAL_DIR = os.path.join(BASE_DIR, "02_分镜视觉素材", "real_images")
CLIPS_DIR = os.path.join(BASE_DIR, "elderly_motion_clips")
os.makedirs(CLIPS_DIR, exist_ok=True)

FFMPEG = ffmpeg()
JIANYING_DRAFTS_DIR = str(JIANYING)
DRAFT_NAME = "【带货二创】山西古建三大奇迹_中老年大字典藏版"

# Asset paths
COVER_IMG = os.path.join(BASE_DIR, "02_分镜视觉素材", "cover_packaging_epic_gpt.jpg")
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

# 16-Shot Choreography:
# 首页用 GPT 封面与大殿；中间全部用原来的真实古建/殿宇；尾页用 GPT 3D 斗拱爆炸图与中文大书！
SHOTS = [
    # === 首页 (Hook: 0-15s) -> GPT 史诗画风 ===
    {"img": COVER_IMG,    "motion": "pull",      "desc": "【首页标题卡】中国山西三大木构神迹烫金大字封面缓缓推进"},
    {"img": TEMPLE_GPT,   "motion": "push",      "desc": "【首页大景】GPT云海悬崖大殿，夕阳逆光史诗开场"},
    {"img": REAL_FOGUANG, "motion": "tilt_up",   "desc": "【佛光寺实拍】三晋群山古刹远景，抛出三大奇迹悬念"},
    
    # === 奇迹一：高平崇明寺·断梁殿 (15-35s) -> 真实古建 ===
    {"img": REAL_DOUGONG, "motion": "push",      "desc": "【实拍斗拱特写】崇明寺中佛殿斗拱咬合"},
    {"img": AI_BEAM,      "motion": "tilt_down", "desc": "【大殿梁架内景】横梁受力，两截短木拼接"},
    {"img": REAL_DOUGONG, "motion": "pull",      "desc": "【实拍顺栿串】千年不倒平衡结构"},
    
    # === 奇迹二：朔州崇福寺·减柱造 (35-55s) -> 真实古建 ===
    {"img": REAL_CHONGFU, "motion": "push",      "desc": "【崇福寺实拍外景】朔州崇福寺弥陀殿"},
    {"img": AI_TEMPLE,    "motion": "pan_right", "desc": "【空旷内堂】打破传统网格，抽掉所有承重柱"},
    {"img": REAL_CHONGFU, "motion": "tilt_up",   "desc": "【崇福寺立面】精妙力学计算"},
    {"img": AI_TEMPLE,    "motion": "pull",      "desc": "【空旷大堂视野】至今让人叹为观止"},
    
    # === 奇迹三：芮城永乐宫·大搬迁 (55-75s) -> 真实古建与国宝壁画 ===
    {"img": REAL_YONGLE,  "motion": "push",      "desc": "【永乐宫实拍外景】元代三清殿全景"},
    {"img": REAL_YONGLE,  "motion": "pull",      "desc": "【大搬迁传奇】逐一编号拆解异地搬迁20公里"},
    {"img": REAL_MURAL,   "motion": "pan_right", "desc": "【朝元图壁画】神仙画卷横向慢速运镜"},
    
    # === 尾页 (带货转化: 75-95s) -> GPT 3D斗拱爆炸图 + 中文大书 ===
    {"img": DOUGONG_GPT,  "motion": "tilt_down", "desc": "【尾页GPT爆炸图】如果不翻开这本书，很难读懂古人榫卯力学智慧"},
    {"img": BOOK_IMG,     "motion": "push",      "desc": "【中文典藏大书展开】手绘剖面图与传统题签大字"},
    {"img": BOOK_IMG,     "motion": "pull",      "desc": "【深色茶台全景】留在手边慢慢翻，引导下单"}
]

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

def run():
    print("=== Step 1: Rendering 16 Clips ===")
    clip_files = []
    for idx, s in enumerate(SHOTS):
        aud = os.path.join(AUDIO_DIR, f"chunk_{idx:02d}.mp3")
        out_clip = os.path.join(CLIPS_DIR, f"clip_{idx:02d}.mp4")
        clip_files.append(out_clip)
        
        mi = pymediainfo.MediaInfo.parse(aud)
        dur = 5.0
        for t in mi.tracks:
            if t.track_type == "Audio":
                dur = float(t.duration) / 1000.0
                break
        total_frames = int(dur * 25) + 5
        vf = build_vf(s["motion"], total_frames)
        
        print(f"[{idx+1}/16] {s['desc']} ({dur:.2f}s)...")
        cmd = [
            FFMPEG, "-y",
            "-loop", "1", "-i", s["img"],
            "-i", aud,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            out_clip
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print("\n=== Step 2: Concatenating Clips ===")
    concat_txt = os.path.join(CLIPS_DIR, "concat.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for c in clip_files:
            p = c.replace("\\", "/")
            f.write(f"file '{p}'\n")

    raw_mp4 = os.path.join(BASE_DIR, "raw_elderly_concat.mp4")
    cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", concat_txt, "-c", "copy", raw_mp4]
    subprocess.run(cmd, check=True)

    print("\n=== Step 3: Hardcoding Large High-Contrast Subtitles for Elderly ===")
    # Format subtitles: Large font, bold, warm golden yellow with solid black outline
    srt_file = os.path.join(BASE_DIR, "01_文案与分镜", "subtitles.srt").replace("\\", "/").replace(":", "\\:")
    final_mp4 = os.path.join(BASE_DIR, "山西古建三大奇迹_中老年大字典藏版.mp4")
    
    # Subtitle style:
    # Fontsize=24 in 1080p, Bold=1, PrimaryColour=&H002DF5FE (Warm Gold), OutlineColour=&H00000000, Outline=3, MarginV=140
    sub_filter = f"subtitles='{srt_file}':force_style='FontName=Microsoft YaHei,FontSize=22,Bold=1,PrimaryColour=&H0033FFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=140'"
    
    cmd = [
        FFMPEG, "-y",
        "-i", raw_mp4,
        "-vf", sub_filter,
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        final_mp4
    ]
    subprocess.run(cmd, check=True)
    print(f"Large Subtitle MP4 successfully rendered:\n{final_mp4} ({os.path.getsize(final_mp4)} bytes)")

    print("\n=== Step 4: Creating Jianying Pro Draft Project ===")
    folder = draft.DraftFolder(JIANYING_DRAFTS_DIR)
    script = folder.create_draft(DRAFT_NAME, width=1080, height=1920, fps=30, allow_replace=True)
    script.append_track(draft.TrackSpec(draft.TrackType.video, name="画面轨"))
    script.append_track(draft.TrackSpec(draft.TrackType.audio, name="解说配音轨"))

    cur_us = 0
    pause_us = 250_000
    for idx, s in enumerate(SHOTS):
        aud = os.path.join(AUDIO_DIR, f"chunk_{idx:02d}.mp3")
        mi = pymediainfo.MediaInfo.parse(aud)
        dur_us = 5_000_000
        for t in mi.tracks:
            if t.track_type == "Audio":
                dur_us = int(float(t.duration) * 1000)
                break
        
        v_seg = draft.VideoSegment(s["img"], draft.Timerange(cur_us, dur_us + pause_us))
        script.add_segment(v_seg)
        a_seg = draft.AudioSegment(aud, draft.Timerange(cur_us, dur_us))
        script.add_segment(a_seg)
        cur_us += dur_us + pause_us

    # Jianying Large Text Style for Middle-aged & Elderly:
    # Size increased to 12.0 (standard is 8.0, 50% larger!), Bold=True, Warm Golden Yellow Color
    large_text_style = draft.TextStyle(
        size=12.0,
        bold=True,
        color=(1.0, 0.95, 0.2), # Bright readable warm gold
        align=1, # Center align
        auto_wrapping=True,
        max_line_width=0.76
    )
    # ClipSettings: position transform_y = -0.68 (bottom third, safe from platform buttons)
    clip_pos = draft.ClipSettings(transform_y=-0.68)
    
    script.import_srt(
        os.path.join(BASE_DIR, "01_文案与分镜", "subtitles.srt"),
        track_name="大字口播字幕",
        text_style=large_text_style,
        clip_settings=clip_pos
    )
    script.save()
    print(f"Jianying Draft saved:\n{DRAFT_NAME}")

if __name__ == "__main__":
    run()
