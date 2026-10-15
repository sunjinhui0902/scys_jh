import os
import sys
import shutil
import re

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import pyJianYingDraft as draft


# Setup paths
PROJECT_ROOT = r"D:\fuye"
sys.path.append(os.path.join(PROJECT_ROOT, "04_自动化生产流水线"))
from workspace_paths import JIANYING

DEMO_DIR = os.path.join(PROJECT_ROOT, r"05_爆款知识库与复盘\试做产物\S04_洛阳_中国历史名城Demo")
AUDIO_DIR = os.path.join(DEMO_DIR, "audio")
SHOTS_DIR = os.path.join(DEMO_DIR, "visuals", "shots")
SRT_PATH = os.path.join(DEMO_DIR, "subtitles.srt")
ARCHIVE_DRAFT_DIR = os.path.join(DEMO_DIR, "JianYingDraft_S04_洛阳")

JIANYING_DRAFTS_DIR = str(JIANYING)
DRAFT_NAME = "【带货二创】S04_洛阳五大都城_中国历史名城"

# Total duration: 87.63s (87,630,000 us)
TOTAL_DURATION_US = 87_630_000

# 13 Shot definitions (start_us, end_us, image_filename, motion_type)
SHOT_CONFIGS = [
    {
        "id": 1,
        "name": "应天门夜景打卡实拍",
        "file": "shot_01.jpg",
        "start": 0,
        "end": 5_744_000,
        "keyframes": [
            (draft.KeyframeProperty.uniform_scale, 0, 1.00),
            (draft.KeyframeProperty.uniform_scale, 5_744_000, 1.12),
        ]
    },
    {
        "id": 2,
        "name": "应天门日景全景实拍",
        "file": "shot_02.jpg",
        "start": 5_744_000,
        "end": 11_734_000,
        "keyframes": [
            (draft.KeyframeProperty.uniform_scale, 0, 1.14),
            (draft.KeyframeProperty.uniform_scale, 11_734_000 - 5_744_000, 1.02),
        ]
    },
    {
        "id": 3,
        "name": "镜头拉远·河洛五都概念鸟瞰",
        "file": "shot_03.jpg",
        "start": 11_734_000,
        "end": 19_546_000,
        "keyframes": [
            (draft.KeyframeProperty.uniform_scale, 0, 1.00),
            (draft.KeyframeProperty.uniform_scale, 19_546_000 - 11_734_000, 1.14),
            (draft.KeyframeProperty.position_x, 0, -0.03),
            (draft.KeyframeProperty.position_x, 19_546_000 - 11_734_000, 0.03),
        ]
    },
    {
        "id": 4,
        "name": "二里头都城遗址现场实拍",
        "file": "shot_04.jpg",
        "start": 19_546_000,
        "end": 25_890_000,
        "keyframes": [
            (draft.KeyframeProperty.uniform_scale, 0, 1.00),
            (draft.KeyframeProperty.uniform_scale, 25_890_000 - 19_546_000, 1.12),
            (draft.KeyframeProperty.position_x, 0, -0.04),
            (draft.KeyframeProperty.position_x, 25_890_000 - 19_546_000, 0.04),
        ]
    },
    {
        "id": 5,
        "name": "隋唐洛阳城沙盘模型实拍",
        "file": "shot_05.jpg",
        "start": 25_890_000,
        "end": 31_616_000,
        "keyframes": [
            (draft.KeyframeProperty.uniform_scale, 0, 1.14),
            (draft.KeyframeProperty.uniform_scale, 31_616_000 - 25_890_000, 1.00),
            (draft.KeyframeProperty.position_y, 0, -0.03),
            (draft.KeyframeProperty.position_y, 31_616_000 - 25_890_000, 0.03),
        ]
    },
    {
        "id": 6,
        "name": "定鼎门遗址博物馆与古今地层",
        "file": "shot_06.jpg",
        "start": 31_616_000,
        "end": 39_596_000,
        "keyframes": [
            (draft.KeyframeProperty.uniform_scale, 0, 1.00),
            (draft.KeyframeProperty.uniform_scale, 39_596_000 - 31_616_000, 1.15),
        ]
    },
    {
        "id": 7,
        "name": "打开地图·隋唐洛阳城古代地形与水系",
        "file": "shot_07.jpg",
        "start": 39_596_000,
        "end": 45_676_000,
        "keyframes": [
            (draft.KeyframeProperty.uniform_scale, 0, 1.05),
            (draft.KeyframeProperty.uniform_scale, 45_676_000 - 39_596_000, 1.16),
            (draft.KeyframeProperty.position_x, 0, 0.04),
            (draft.KeyframeProperty.position_x, 45_676_000 - 39_596_000, -0.03),
        ]
    },
    {
        "id": 8,
        "name": "河洛大地苍茫意境·下次再去洛阳",
        "file": "shot_08.jpg",
        "start": 45_676_000,
        "end": 51_666_000,
        "keyframes": [
            (draft.KeyframeProperty.uniform_scale, 0, 1.14),
            (draft.KeyframeProperty.uniform_scale, 51_666_000 - 45_676_000, 1.02),
            (draft.KeyframeProperty.position_y, 0, 0.03),
            (draft.KeyframeProperty.position_y, 51_666_000 - 45_676_000, -0.02),
        ]
    },
    {
        "id": 9,
        "name": "应天门城门斗拱特写·哪一代人的城",
        "file": "shot_09.jpg",
        "start": 51_666_000,
        "end": 59_742_000,
        "keyframes": [
            (draft.KeyframeProperty.uniform_scale, 0, 1.00),
            (draft.KeyframeProperty.uniform_scale, 59_742_000 - 51_666_000, 1.14),
        ]
    },
    {
        "id": 10,
        "name": "应天门高耸城阙仰角·城门不只是背景",
        "file": "shot_10.jpg",
        "start": 59_742_000,
        "end": 65_228_000,
        "keyframes": [
            (draft.KeyframeProperty.uniform_scale, 0, 1.12),
            (draft.KeyframeProperty.uniform_scale, 65_228_000 - 59_742_000, 1.00),
            (draft.KeyframeProperty.position_y, 0, -0.03),
            (draft.KeyframeProperty.position_y, 65_228_000 - 59_742_000, 0.02),
        ]
    },
    {
        "id": 11,
        "name": "自然引书·中国历史名城典藏封面",
        "file": "shot_11.jpg",
        "start": 65_228_000,
        "end": 74_000_000,
        "keyframes": [
            (draft.KeyframeProperty.uniform_scale, 0, 1.00),
            (draft.KeyframeProperty.uniform_scale, 74_000_000 - 65_228_000, 1.12),
        ]
    },
    {
        "id": 12,
        "name": "茶案翻开大书·古都名城目录篇章",
        "file": "shot_12.jpg",
        "start": 74_000_000,
        "end": 81_860_000,
        "keyframes": [
            (draft.KeyframeProperty.uniform_scale, 0, 1.02),
            (draft.KeyframeProperty.uniform_scale, 81_860_000 - 74_000_000, 1.15),
            (draft.KeyframeProperty.position_x, 0, -0.03),
            (draft.KeyframeProperty.position_x, 81_860_000 - 74_000_000, 0.03),
        ]
    },
    {
        "id": 13,
        "name": "茶台静物全景收束·留白余韵",
        "file": "shot_13.jpg",
        "start": 81_860_000,
        "end": 87_630_000,
        "keyframes": [
            (draft.KeyframeProperty.uniform_scale, 0, 1.14),
            (draft.KeyframeProperty.uniform_scale, 87_630_000 - 81_860_000, 1.00),
        ]
    },
]

def parse_srt_timestamps(srt_file):
    blocks = open(srt_file, encoding="utf-8").read().strip().split("\n\n")
    def parse_time(ts):
        m = re.match(r"(\d+):(\d+):(\d+),(\d+)", ts)
        h, mi, s, ms = map(int, m.groups())
        return (h * 3600 + mi * 60 + s) * 1_000_000 + ms * 1000

    items = []
    for b in blocks:
        lines = b.strip().split("\n")
        idx = int(lines[0])
        t_start, t_end = lines[1].split(" --> ")
        text = lines[2].strip()
        s_us = parse_time(t_start)
        e_us = parse_time(t_end)
        items.append({"idx": idx, "start": s_us, "end": e_us, "dur": e_us - s_us, "text": text})
    return items

def main():
    print("=" * 60)
    print("🚀 开始构建 S04 洛阳 剪映 Pro 原生工程项目...")
    print(f"剪映草稿目录: {JIANYING_DRAFTS_DIR}")
    print(f"工程名称: {DRAFT_NAME}")
    print("=" * 60)

    # 1. 创建草稿
    folder = draft.DraftFolder(JIANYING_DRAFTS_DIR)
    script = folder.create_draft(DRAFT_NAME, width=1080, height=1920, fps=30, allow_replace=True)

    # 2. 注册多轨道
    script.append_track(draft.TrackSpec(draft.TrackType.video, name="画面轨"))
    script.append_track(draft.TrackSpec(draft.TrackType.audio, name="解说配音轨"))
    script.append_track(draft.TrackSpec(draft.TrackType.audio, name="中式国风BGM轨"))
    script.append_track(draft.TrackSpec(draft.TrackType.audio, name="转场音效轨"))

    # 3. 填充画面轨 (13 个镜头切片 + 原生运动关键帧)
    print("\n[Track 1] 正在构建【画面轨】(13个镜头切片 + 原生缩放平移关键帧)...")
    for s in SHOT_CONFIGS:
        img_path = os.path.join(SHOTS_DIR, s["file"])
        if not os.path.exists(img_path):
            raise FileNotFoundError(f"未找到镜头图像素材: {img_path}")
        
        dur = s["end"] - s["start"]
        v_seg = draft.VideoSegment(img_path, draft.Timerange(s["start"], dur))
        
        # 添加运镜关键帧
        for prop, offset, val in s["keyframes"]:
            v_seg.add_keyframe(prop, offset, val)
        
        script.add_segment(v_seg, track="画面轨")
        print(f"  + Shot {s['id']:02d}: {s['name']} [{s['start']/1e6:05.2f}s - {s['end']/1e6:05.2f}s] ({dur/1e6:.2f}s)")

    # 4. 填充解说配音轨 (31 句 clause_*.mp3，对齐 SRT)
    print("\n[Track 2] 正在构建【解说配音轨】(31句央视沧桑历史音色 精准对齐)...")
    srt_items = parse_srt_timestamps(SRT_PATH)
    for item in srt_items:
        clause_file = os.path.join(AUDIO_DIR, f"clause_{item['idx'] - 1:02d}.mp3")
        if not os.path.exists(clause_file):
            raise FileNotFoundError(f"未找到语音分片: {clause_file}")
        
        a_seg = draft.AudioSegment(clause_file, draft.Timerange(item["start"], item["dur"]))
        script.add_segment(a_seg, track="解说配音轨")
        print(f"  + Clause {item['idx']:02d}: {item['text']} [{item['start']/1e6:05.2f}s - {item['end']/1e6:05.2f}s]")

    # 5. 填充中式国风 BGM 轨 (87.63s，-24dB 历史古琴氛围)
    print("\n[Track 3] 正在构建【中式国风BGM轨】(阳关三叠古琴 -24dB)...")
    bgm_path = os.path.join(AUDIO_DIR, "bgm_guqin_ambient.mp3")
    if not os.path.exists(bgm_path):
        raise FileNotFoundError(f"未找到 BGM 文件: {bgm_path}")
    bgm_seg = draft.AudioSegment(bgm_path, draft.Timerange(0, TOTAL_DURATION_US), volume=0.85)
    script.add_segment(bgm_seg, track="中式国风BGM轨")
    print(f"  + BGM 挂载完成: 0.00s - {TOTAL_DURATION_US/1e6:.2f}s (-24dB)")

    # 6. 填充转场音效轨 (3处关键节点转场音效)
    print("\n[Track 4] 正在构建【转场音效轨】(3处结构转折点微澜划屏音效)...")
    sfx_path = os.path.join(AUDIO_DIR, "sfx_transition.wav")
    sfx_timestamps = [
        (11_734_000, "镜头拉远转折"),
        (39_596_000, "打开地图转折"),
        (65_228_000, "自然引书转折")
    ]
    sfx_dur = 800_000
    for ts, tag in sfx_timestamps:
        sfx_seg = draft.AudioSegment(sfx_path, draft.Timerange(ts, sfx_dur), volume=0.7)
        script.add_segment(sfx_seg, track="转场音效轨")
        print(f"  + SFX 转场: {tag} [{ts/1e6:05.2f}s]")

    # 7. 导入原生大字律动字幕轨 (安全下沉 transform_y = -0.68，白色加黑粗描边)
    print("\n[Track 5] 正在构建【原生大字律动字幕轨】(31句 5~9字，避开橱窗与点赞)...")
    large_text_style = draft.TextStyle(
        size=12.5,
        bold=True,
        color=(1.0, 1.0, 1.0), # 纯白高对比
        align=1,               # 居中对齐
        auto_wrapping=True,
        max_line_width=0.76
    )
    border = draft.TextBorder(color=(0.0, 0.0, 0.0), width=40.0) # 40.0 黑色实心描边
    clip_pos = draft.ClipSettings(transform_y=-0.68)              # 底部安全避让
    
    style_ref = draft.TextSegment(
        "", draft.Timerange(0, 0),
        style=large_text_style,
        border=border,
        clip_settings=clip_pos
    )
    
    script.import_srt(
        str(SRT_PATH),
        track_name="大字口播字幕",
        style_reference=style_ref,
        clip_settings=clip_pos
    )
    print(f"  + 31 句字幕已成功载入原生文本轨，样式已统一应用！")

    # 8. 保存草稿
    script.save()
    target_draft_path = os.path.join(JIANYING_DRAFTS_DIR, DRAFT_NAME)
    print(f"\n✅ 剪映 Pro 原生工程已成功写入剪映草稿目录:\n{target_draft_path}")

    # 9. 备份至本 Demo 目录供归档与离线分发
    if os.path.exists(ARCHIVE_DRAFT_DIR):
        shutil.rmtree(ARCHIVE_DRAFT_DIR)
    shutil.copytree(target_draft_path, ARCHIVE_DRAFT_DIR)
    print(f"✅ 剪映 Pro 原生工程已成功归档至工作区备份目录:\n{ARCHIVE_DRAFT_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    main()
