import os
import sys
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = r"D:\fuye"

sys.path.append(os.path.join(PROJECT_ROOT, "04_自动化生产流水线"))
from workspace_paths import ffmpeg

FFMPEG = ffmpeg()

DEMO_DIR = os.path.join(PROJECT_ROOT, r"05_爆款知识库与复盘\试做产物\S04_洛阳_中国历史名城Demo")
AUDIO_DIR = os.path.join(DEMO_DIR, "audio")
SHOTS_DIR = os.path.join(DEMO_DIR, "visuals", "shots")
CLIPS_DIR = os.path.join(DEMO_DIR, "visuals", "motion_clips")
os.makedirs(CLIPS_DIR, exist_ok=True)

SHOTS = [
    ("shot_01.jpg", 5.744, "zoompan=z='min(zoom+0.0008,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=25"),
    ("shot_02.jpg", 5.990, "zoompan=z='if(lte(on,1),1.14,max(1.02,1.14-0.0008*on))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=25"),
    ("shot_03.jpg", 7.812, "zoompan=z='min(zoom+0.0007,1.14)':x='(on/{frames})*(iw-iw/zoom)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=25"),
    ("shot_04.jpg", 6.344, "zoompan=z='min(zoom+0.0007,1.12)':x='(on/{frames})*(iw-iw/zoom)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=25"),
    ("shot_05.jpg", 5.726, "zoompan=z='if(lte(on,1),1.14,max(1.0,1.14-0.0008*on))':x='iw/2-(iw/zoom/2)':y='(on/{frames})*(ih-ih/zoom)':d={frames}:s=1080x1920:fps=25"),
    ("shot_06.jpg", 7.980, "zoompan=z='min(zoom+0.0007,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=25"),
    ("shot_07.jpg", 6.080, "zoompan=z='min(zoom+0.0008,1.16)':x='(1-on/{frames})*(iw-iw/zoom)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=25"),
    ("shot_08.jpg", 5.990, "zoompan=z='if(lte(on,1),1.14,max(1.02,1.14-0.0008*on))':x='iw/2-(iw/zoom/2)':y='(1-on/{frames})*(ih-ih/zoom)':d={frames}:s=1080x1920:fps=25"),
    ("shot_09.jpg", 8.076, "zoompan=z='min(zoom+0.0006,1.14)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=25"),
    ("shot_10.jpg", 5.486, "zoompan=z='if(lte(on,1),1.12,max(1.0,1.12-0.0008*on))':x='iw/2-(iw/zoom/2)':y='(on/{frames})*(ih-ih/zoom)':d={frames}:s=1080x1920:fps=25"),
    ("shot_11.jpg", 8.772, "zoompan=z='min(zoom+0.0005,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=25"),
    ("shot_12.jpg", 7.860, "zoompan=z='min(zoom+0.0006,1.15)':x='(on/{frames})*(iw-iw/zoom)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=25"),
    ("shot_13.jpg", 5.770, "zoompan=z='if(lte(on,1),1.14,max(1.0,1.14-0.0008*on))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=25"),
]

def run():
    print("=== Step 1: 渲染 13 个动态运镜切片 ===")
    clip_paths = []
    for idx, (img_name, dur, zp_tmpl) in enumerate(SHOTS):
        img_p = os.path.join(SHOTS_DIR, img_name)
        out_clip = os.path.join(CLIPS_DIR, f"clip_{idx:02d}.mp4")
        clip_paths.append(out_clip)
        total_frames = int(dur * 25) + 1
        vf = zp_tmpl.format(frames=total_frames)
        cmd = [
            FFMPEG, "-y",
            "-loop", "1", "-i", img_p,
            "-t", str(dur),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            out_clip
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[{idx+1}/{len(SHOTS)}] 镜头完成: {img_name} ({dur}s)")

    print("\n=== Step 2: 无损拼接镜头 ===")
    concat_txt = os.path.join(CLIPS_DIR, "concat.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for c in clip_paths:
            p = c.replace("\\", "/")
            f.write(f"file '{p}'\n")

    raw_concat = os.path.join(CLIPS_DIR, "raw_concat.mp4")
    subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", concat_txt, "-c", "copy", raw_concat], check=True)
    print("视频轨拼接完成!")

    print("\n=== Step 3: 音画混合 (央视纪录片人声 + 阳关三叠古琴BGM) ===")
    mixed_audio = os.path.join(CLIPS_DIR, "mixed_audio.wav")
    voice_wav = os.path.join(AUDIO_DIR, "master_narration.wav")
    bgm_mp3 = os.path.join(AUDIO_DIR, "bgm_guqin_ambient.mp3")
    mix_cmd = [
        FFMPEG, "-y",
        "-i", voice_wav,
        "-i", bgm_mp3,
        "-filter_complex", "[0:a]volume=1.0[a0];[1:a]volume=0.9[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-map", "[aout]",
        mixed_audio
    ]
    subprocess.run(mix_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("多轨音频混音完成!")

    print("\n=== Step 4: 压制中老年大字高对比字幕样片 ===")
    srt_escaped = os.path.join(DEMO_DIR, "subtitles.srt").replace("\\", "/").replace(":", "\\:")
    final_mp4 = os.path.join(DEMO_DIR, "S04_洛阳_中国历史名城_样片.mp4")

    # Fontsize=24, Bold=1, White text with 3.8 black outline, safe bottom margin 540 (above bottom UI)
    sub_filter = f"subtitles='{srt_escaped}':force_style='FontName=Microsoft YaHei,FontSize=24,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3.8,Shadow=0,Alignment=2,MarginV=540'"

    final_cmd = [
        FFMPEG, "-y",
        "-i", raw_concat,
        "-i", mixed_audio,
        "-vf", sub_filter,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        final_mp4
    ]
    subprocess.run(final_cmd, check=True)
    print(f"\n🎉 动态样片渲染成功:\n{final_mp4} ({os.path.getsize(final_mp4)} 字节)")

if __name__ == "__main__":
    run()
