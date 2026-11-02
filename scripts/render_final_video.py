import os
import sys
import json
import re
import shutil
import subprocess
from pathlib import Path

# UTF-8 编码安全保障
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path("d:/fuye")
sys.path.insert(0, str(ROOT / "04_自动化生产流水线"))
from workspace_paths import ffmpeg

FFMPEG_EXE = ffmpeg()
SHILI_BGM = ROOT / "01_配音与音色库" / "背景音乐库" / "bgm_shili_guofeng.mp3"

def ms_to_ass_time(ms: int) -> str:
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    cs = (ms % 1000) // 10
    return f"{h:01d}:{m:02d}:{s:02d}.{cs:02d}"

def render_project(project_dir: Path, output_mp4: Path) -> Path:
    project_dir = Path(project_dir).resolve()
    manifest_file = project_dir / "draft_manifest.json"
    if not manifest_file.is_file():
        raise FileNotFoundError(f"Missing {manifest_file}")
    
    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    total_dur_us = data["total_dur_us"]
    total_dur_s = total_dur_us / 1_000_000
    sections = data["sections"]
    shots = data["shots"]
    title_text = data.get("draft_title", "").replace("【图书带货】", "").strip()
    
    work_dir = project_dir / "05_成片"
    work_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = work_dir / "_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n========================================================")
    print(f"🎬 正在渲染成品视频: {project_dir.name}")
    print(f"⏱️ 视频时长: {total_dur_s:.2f} 秒 | 镜头数: {len(shots)}")
    print(f"========================================================")
    
    # 1. 生成 ASS 字幕文件
    ass_file = temp_dir / "render.ass"
    ass_lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        # 顶部固定主标题: 暖黄底金字、居中顶栏
        "Style: Title,Microsoft YaHei,46,&H0010E0FF,&H00000000,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,1,3,1,8,40,40,90,1",
        # 章节导航卡: 白字黑边
        "Style: Nav,Microsoft YaHei,38,&H00E8FFFF,&H00000000,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,8,40,40,165,1",
        # 中老年大字底字幕: 白字粗体、黑半透明底衬、高安全边距
        "Style: Subtitle,Microsoft YaHei,54,&H00FFFFFF,&H00000000,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,3,16,0,2,40,40,190,1",
        # 结尾转化行动贴纸: 深红底金黄字
        "Style: Sticker,Microsoft YaHei,46,&H0000E8FF,&H00000000,&H00000000,&H00000099,-1,0,0,0,100,100,0,0,3,12,0,2,40,40,300,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    ]
    
    # 全局主标题
    total_end_ass = ms_to_ass_time(int(total_dur_s * 1000))
    ass_lines.append(f"Dialogue: 0,0:00:00.00,{total_end_ass},Title,,0,0,0,,{title_text}")
    
    # 章节导航卡
    for sec in sections:
        s_ms = sec["computed_start_us"] // 1000
        e_ms = sec["computed_end_us"] // 1000
        st_ass = ms_to_ass_time(s_ms)
        et_ass = ms_to_ass_time(e_ms)
        top_bar = sec.get("top_bar", "")
        if top_bar:
            ass_lines.append(f"Dialogue: 1,{st_ass},{et_ass},Nav,,0,0,0,,{top_bar}")
    
    # SRT 字幕
    srt_file = project_dir / "01_文案与分镜" / "subtitles.srt"
    if srt_file.is_file():
        srt_content = srt_file.read_text(encoding="utf-8")
        blocks = re.split(r"\n\s*\n", srt_content.strip())
        for b in blocks:
            lines = [l.strip() for l in b.splitlines() if l.strip()]
            if len(lines) >= 3:
                time_line = lines[1]
                sub_text = " ".join(lines[2:])
                m = re.match(r"(\d+:\d+:\d+,\d+)\s*-->\s*(\d+:\d+:\d+,\d+)", time_line)
                if m:
                    def srt_t_to_ass(st_str):
                        st_str = st_str.replace(",", ".")
                        parts = st_str.split(":")
                        h = int(parts[0])
                        m = int(parts[1])
                        s_cs = parts[2][:5]
                        return f"{h:01d}:{m:02d}:{s_cs}"
                    t_start = srt_t_to_ass(m.group(1))
                    t_end = srt_t_to_ass(m.group(2))
                    ass_lines.append(f"Dialogue: 2,{t_start},{t_end},Subtitle,,0,0,0,,{sub_text}")
    
    # 结尾贴纸
    if len(sections) > 0:
        last_sec = sections[-1]
        last_s_ms = last_sec["computed_start_us"] // 1000
        last_st_ass = ms_to_ass_time(last_s_ms)
        sticker_text = "支持先用后付 橱窗直接拍"
        script_md = project_dir / "01_文案与分镜" / "口播文案.md"
        if script_md.exists():
            m = re.search(r"转化贴纸文案[：:]\s*【(.*?)】", script_md.read_text(encoding="utf-8"))
            if m:
                sticker_text = m.group(1).strip()
        ass_lines.append(f"Dialogue: 3,{last_st_ass},{total_end_ass},Sticker,,0,0,0,,{sticker_text}")
    
    ass_file.write_text("\n".join(ass_lines), encoding="utf-8")
    
    # 2. 逐镜头切片视频生成
    concat_list = temp_dir / "concat.txt"
    clip_files = []
    
    for s_idx, shot in enumerate(shots):
        img_path = Path(shot["current_image"])
        dur_s = shot["duration_us"] / 1_000_000
        clip_path = temp_dir / f"clip_{s_idx:02d}.mp4"
        
        vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
        
        cmd = [
            FFMPEG_EXE, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-loop", "1", "-i", str(img_path),
            "-t", f"{dur_s:.3f}",
            "-vf", vf,
            "-r", "30",
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            str(clip_path)
        ]
        subprocess.run(cmd, check=True)
        clip_files.append(clip_path)
    
    concat_list.write_text("\n".join(f"file '{p.as_posix()}'" for p in clip_files), encoding="utf-8")
    
    # 3. 准备音频混音 (人声 + BGM)
    voice_file = project_dir / "03_配音音频" / "voice_master.mp3"
    
    fade_out_start = max(0, total_dur_s - 2.5)
    filter_complex = (
        f"[0:a]volume=1.4125[v];"
        f"[1:a]aloop=loop=-1:size=2e+09,atrim=0:{total_dur_s:.3f},afade=t=in:ss=0:d=1.0,afade=t=out:st={fade_out_start:.3f}:d=2.5,volume=0.2239[m];"
        f"[v][m]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )
    mixed_audio = temp_dir / "mixed_audio.aac"
    cmd_audio = [
        FFMPEG_EXE, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(voice_file),
        "-i", str(SHILI_BGM),
        "-filter_complex", filter_complex,
        "-map", "[aout]",
        "-c:a", "aac", "-b:a", "192k",
        str(mixed_audio)
    ]
    subprocess.run(cmd_audio, check=True)
    
    # 4. 拼接画面、添加字幕滤镜并合成最终 MP4
    ass_escaped = str(ass_file).replace("\\", "/").replace(":", "\\:")
    cmd_final = [
        FFMPEG_EXE, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-i", str(mixed_audio),
        "-vf", f"subtitles=filename='{ass_escaped}'",
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        "-shortest", "-movflags", "+faststart",
        str(output_mp4)
    ]
    subprocess.run(cmd_final, check=True)
    
    # 清理临时切片
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass
    
    file_size_mb = output_mp4.stat().st_size / (1024 * 1024)
    print(f"[✓ 成品导出完成] {output_mp4.name} ({file_size_mb:.2f} MB, {total_dur_s:.2f}s)")
    return output_mp4

if __name__ == "__main__":
    tasks = [
        ("M1_11-03_0700", "M1_孩子玩手机换个办法_成片.mp4"),
        ("N1_11-03_1230", "N1_都江堰怎么分水_成片.mp4"),
        ("W1_11-03_1900", "W1_做客送礼老讲究_成片.mp4")
    ]
    for folder, out_name in tasks:
        p = ROOT / "03_视频成片与工程" / folder
        out_f = p / "05_成片" / out_name
        render_project(p, out_f)
    print("\nAll 3 final videos successfully rendered!")
