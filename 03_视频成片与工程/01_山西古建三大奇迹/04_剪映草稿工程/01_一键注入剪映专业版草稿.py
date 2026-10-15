import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "04_自动化生产流水线"))
from workspace_paths import EP1, JIANYING
import pyJianYingDraft as draft

# 剪映草稿生成器 - 第1期：山西古建三大奇迹
JIANYING_DRAFTS_DIR = str(JIANYING)
DRAFT_NAME = "【带货二创】山西古建三大奇迹_短句爆款字幕版"

EP1_DIR = str(EP1)
IMG_DIR = os.path.join(EP1_DIR, "02_分镜视觉素材")
AUDIO_DIR = os.path.join(EP1_DIR, "03_配音音频", "clause_audios")

# 引入 39 句分镜定义
from sys import path
path.append(str(ROOT / "04_自动化生产流水线"))
from build_rhythmic_subtitles import CLAUSES

def make_draft():
    print(f"正在向剪映注入草稿工程: {DRAFT_NAME} ...")
    folder = draft.DraftFolder(JIANYING_DRAFTS_DIR)
    script = folder.create_draft(DRAFT_NAME, width=1080, height=1920, fps=30, allow_replace=True)
    
    script.append_track(draft.TrackSpec(draft.TrackType.video, name="画面轨"))
    script.append_track(draft.TrackSpec(draft.TrackType.audio, name="解说配音轨"))

    cur_us = 0
    pause_us = int(0.10 * 1_000_000)
    
    import pymediainfo
    text_style = draft.TextStyle(
        size=13.5,
        bold=True,
        color=(1.0, 1.0, 1.0),
        border=draft.TextBorder(color=(0.0, 0.0, 0.0), width=4.5),
        align=draft.TextAlign.center
    )

    for idx, c in enumerate(CLAUSES):
        aud_path = os.path.join(AUDIO_DIR, f"clause_{idx:02d}.mp3")
        media_info = pymediainfo.MediaInfo.parse(aud_path)
        dur = 2.0
        for track in media_info.tracks:
            if track.track_type == "Audio":
                dur = float(track.duration) / 1000.0
                break
        
        dur_us = int(dur * 1_000_000)
        
        # 视频轨
        v_seg = draft.VideoSegment(c["img"], draft.Timerange(cur_us, dur_us + pause_us))
        script.add_segment(v_seg)
        
        # 音频轨
        a_seg = draft.AudioSegment(aud_path, draft.Timerange(cur_us, dur_us))
        script.add_segment(a_seg)
        
        # 字幕文本
        sub_seg = draft.TextSegment(
            c["text"],
            draft.Timerange(cur_us, dur_us + pause_us),
            style=text_style,
            clip_settings=draft.ClipSettings(transform_y=-0.28)
        )
        script.add_segment(sub_seg)
        
        cur_us += dur_us + pause_us

    script.save()
    print(f"剪映专业版草稿生成成功！直接在剪映打开【{DRAFT_NAME}】即可精剪与微调。")

if __name__ == "__main__":
    make_draft()
