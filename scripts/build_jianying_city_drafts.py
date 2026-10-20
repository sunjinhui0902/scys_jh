#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JianYing Pro Draft Automation Generator for Top 10 Historical Cities (Ep1 & Ep2).
Complies with video channel elderly-friendly guidelines, Ken Burns keyframes,
dissolve transitions, two-line top title bar, and bottom rhythmic subtitles.
"""

import os
import sys
import json
import math
import shutil
from pathlib import Path
from typing import List, Dict, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import pymediainfo
import pyJianYingDraft as draft

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "04_自动化生产流水线"))
from workspace_paths import JIANYING

BASE_DIR = ROOT / "03_视频成片与工程" / "十大历史名城_带孙辈长见识"
ASSETS_DIR = BASE_DIR / "assets"
AUDIO_DIR = ASSETS_DIR / "audio"
IMAGES_DIR = ASSETS_DIR / "images"

JIANYING_DIR = str(JIANYING)

def get_audio_duration_us(path: Path) -> int:
    mi = pymediainfo.MediaInfo.parse(str(path))
    for t in mi.tracks:
        if t.track_type == "Audio":
            return int(float(t.duration) * 1000)
    return 10_000_000

def build_draft_for_episode(
    ep_name: str,
    draft_title: str,
    voice_file: Path,
    sections_json: Path,
    bgm_file: Path,
    sfx_file: Path = None,
    image_overrides: Dict[str, str] = None
):
    print(f"\n========================================================")
    print(f"🎬 启动剪映专业版草稿生成: 【{draft_title}】")
    print(f"========================================================")

    if not voice_file.exists():
        raise FileNotFoundError(f"未找到人声音频文件: {voice_file}")

    total_voice_dur_us = get_audio_duration_us(voice_file)
    total_voice_dur_sec = round(total_voice_dur_us / 1_000_000, 2)
    print(f"  [人声音频] 时长: {total_voice_dur_sec}秒 ({total_voice_dur_us}微秒)")

    sections_data: List[Dict[str, Any]] = json.loads(sections_json.read_text(encoding="utf-8"))

    # 计算各分段口播字数比例，将主音频时长精准分配到各个镜头
    total_chars = sum(sum(len(c) for c in s["clauses"]) for s in sections_data)
    print(f"  [分镜分段] 共 {len(sections_data)} 个分段, 口播短句总字数: {total_chars}字")

    # 1. 初始化剪映草稿
    folder = draft.DraftFolder(JIANYING_DIR)
    script = folder.create_draft(draft_title, width=1080, height=1920, fps=30, allow_replace=True)

    # 2. 创建轨道
    v_track = draft.TrackSpec(draft.TrackType.video, name="主视觉画面轨")
    voice_track = draft.TrackSpec(draft.TrackType.audio, name="解说人声轨(+3dB)")
    bgm_track = draft.TrackSpec(draft.TrackType.audio, name="国风背景音乐(-18dB)")
    top_title_track = draft.TrackSpec(draft.TrackType.text, name="顶部固定主标题")
    top_sub_track = draft.TrackSpec(draft.TrackType.text, name="顶部城市导航卡")
    sub_track = draft.TrackSpec(draft.TrackType.text, name="中老年大字底字幕")
    sticker_track = draft.TrackSpec(draft.TrackType.text, name="营销与行动贴字轨")

    script.append_track(v_track)
    script.append_track(voice_track)
    script.append_track(bgm_track)
    script.append_track(top_title_track)
    script.append_track(top_sub_track)
    script.append_track(sub_track)
    script.append_track(sticker_track)

    if ep_name == "下集":
        gold_track = draft.TrackSpec(draft.TrackType.text, name="十城排比金字轨")
        script.append_track(gold_track)
        if sfx_file and sfx_file.exists():
            sfx_track = draft.TrackSpec(draft.TrackType.audio, name="转化提示音效轨")
            script.append_track(sfx_track)

    # 3. 添加主讲人声音频 (+3dB -> volume=1.4125)
    a_voice_seg = draft.AudioSegment(
        str(voice_file),
        draft.Timerange(0, total_voice_dur_us),
        volume=1.4125
    )
    script.add_segment(a_voice_seg, track="解说人声轨(+3dB)")

    # 4. 添加国风 BGM 底轨 (-18dB -> volume=0.1259)
    if bgm_file.exists():
        bgm_dur_us = get_audio_duration_us(bgm_file)
        cur_bgm_us = 0
        while cur_bgm_us < total_voice_dur_us:
            chunk_len = min(bgm_dur_us, total_voice_dur_us - cur_bgm_us)
            b_seg = draft.AudioSegment(
                str(bgm_file),
                draft.Timerange(cur_bgm_us, chunk_len),
                source_timerange=draft.Timerange(0, chunk_len),
                volume=0.1259
            )
            # 在全片最后 1.5 秒淡出
            if cur_bgm_us + chunk_len >= total_voice_dur_us:
                b_seg.add_fade(0, 1_500_000)
            script.add_segment(b_seg, track="国风背景音乐(-18dB)")
            cur_bgm_us += chunk_len

    # 5. 添加顶部固定主标题（贯穿全片，Y = +750 -> +0.781）
    title_style = draft.TextStyle(
        size=13.0,
        bold=True,
        color=(1.0, 0.85, 0.1), # 金黄烫金
        align=1
    )
    title_border = draft.TextBorder(color=(0.0, 0.0, 0.0), width=40.0)
    title_seg = draft.TextSegment(
        "带孙辈长见识：十大历史名城",
        draft.Timerange(0, total_voice_dur_us),
        font=draft.FontType.抖音美好体,
        style=title_style,
        border=title_border,
        clip_settings=draft.ClipSettings(transform_y=0.781)
    )
    script.add_segment(title_seg, track="顶部固定主标题")

    # 6. 分镜头、运镜、顶部导航卡、底部字幕铺设
    cur_time_us = 0
    img_global_index = 1 # 用于奇偶判断

    sub_style = draft.TextStyle(
        size=11.0,
        bold=True,
        color=(1.0, 1.0, 1.0),
        align=1
    )
    sub_border = draft.TextBorder(color=(0.0, 0.0, 0.0), width=40.0)
    sub_bg = draft.TextBackground(color="#000000", alpha=0.6, round_radius=0.15)
    sub_clip = draft.ClipSettings(transform_y=-0.573)

    nav_style = draft.TextStyle(
        size=11.5,
        bold=True,
        color=(1.0, 1.0, 0.9),
        align=1
    )
    nav_clip = draft.ClipSettings(transform_y=0.695)

    for s_idx, sec in enumerate(sections_data):
        sec_chars = sum(len(c) for c in sec["clauses"])
        # 按字数比例分配该分段的总时长
        sec_dur_us = int(total_voice_dur_us * (sec_chars / total_chars))
        sec_start_us = cur_time_us
        sec_end_us = sec_start_us + sec_dur_us

        # 顶部城市副标题
        if sec.get("top_bar"):
            sub_title_seg = draft.TextSegment(
                sec["top_bar"],
                draft.Timerange(sec_start_us, sec_dur_us),
                font=draft.FontType.抖音美好体,
                style=nav_style,
                border=sub_border,
                clip_settings=nav_clip
            )
            script.add_segment(sub_title_seg, track="顶部城市导航卡")

        # 贴纸 / 促单文案
        if sec.get("sticker"):
            st_style = draft.TextStyle(size=12.5, bold=True, color=(1.0, 0.9, 0.0), align=1)
            st_bg = draft.TextBackground(color="#8B0000", alpha=0.85, round_radius=0.2) # 醒目红底金字
            st_seg = draft.TextSegment(
                sec["sticker"],
                draft.Timerange(sec_start_us, sec_dur_us),
                font=draft.FontType.抖音美好体,
                style=st_style,
                border=sub_border,
                background=st_bg,
                clip_settings=draft.ClipSettings(transform_y=-0.38) # 位于画面中下部
            )
            script.add_segment(st_seg, track="营销与行动贴字轨")

        # 特殊分支：下集第12段【十城排比快闪】
        if sec.get("is_fast_montage") and sec.get("montage_items"):
            items = sec["montage_items"]
            # 均分快闪
            item_dur_us = sec_dur_us // len(items)
            for m_idx, m_item in enumerate(items):
                m_start_us = sec_start_us + m_idx * item_dur_us
                m_actual_dur = item_dur_us if m_idx < len(items) - 1 else (sec_end_us - m_start_us)
                
                # 寻找图片
                img_key = m_item["img"]
                img_path = IMAGES_DIR / img_key
                if image_overrides and img_key in image_overrides:
                    img_path = Path(image_overrides[img_key])

                v_seg = draft.VideoSegment(str(img_path), draft.Timerange(m_start_us, m_actual_dur))
                # 硬切：微弱放大运镜
                v_seg.add_keyframe(draft.KeyframeProperty.uniform_scale, 0, 1.0)
                v_seg.add_keyframe(draft.KeyframeProperty.uniform_scale, m_actual_dur, 1.05)
                script.add_segment(v_seg, track="主视觉画面轨")

                # 屏幕中央金色书法字标签（如：平遥 · 明清商业）
                gold_style = draft.TextStyle(size=16.0, bold=True, color=(1.0, 0.84, 0.0), align=1)
                gold_bg = draft.TextBackground(color="#000000", alpha=0.75, round_radius=0.2)
                gold_seg = draft.TextSegment(
                    m_item["label"],
                    draft.Timerange(m_start_us, m_actual_dur),
                    font=draft.FontType.抖音美好体,
                    style=gold_style,
                    border=sub_border,
                    background=gold_bg,
                    clip_settings=draft.ClipSettings(transform_y=0.0) # 居中
                )
                script.add_segment(gold_seg, track="十城排比金字轨")

        else:
            # 常规视觉图片分配
            raw_imgs = sec["img"] if isinstance(sec["img"], list) else [sec["img"]]
            sub_chunk_dur_us = sec_dur_us // len(raw_imgs)

            for i_idx, img_name in enumerate(raw_imgs):
                i_start_us = sec_start_us + i_idx * sub_chunk_dur_us
                i_dur_us = sub_chunk_dur_us if i_idx < len(raw_imgs) - 1 else (sec_end_us - i_start_us)

                img_path = IMAGES_DIR / img_name
                if image_overrides and img_name in image_overrides:
                    img_path = Path(image_overrides[img_name])

                v_seg = draft.VideoSegment(str(img_path), draft.Timerange(i_start_us, i_dur_us))

                # 书本素材按原图尺寸展示，补充柔和毛玻璃虚化背景（避免黑边及裁切）
                if "book_" in img_name:
                    v_seg.add_background_filling("blur", blur=0.375)

                # Ken Burns 关键帧动画：奇数 1.0 -> 1.12，偶数 1.12 -> 1.0
                is_odd = (img_global_index % 2 == 1)
                start_scale = 1.0 if is_odd else 1.12
                end_scale = 1.12 if is_odd else 1.0
                v_seg.add_keyframe(draft.KeyframeProperty.uniform_scale, 0, start_scale)
                v_seg.add_keyframe(draft.KeyframeProperty.uniform_scale, i_dur_us, end_scale)
                img_global_index += 1

                # 城市切换处添加“叠化”转场（时长 0.5 秒 = 500,000 微秒）
                # 注意：转场加在前面的片段上；如果是该城市分段的最后一张图片，且下一个分段是城市切换，则添加
                if i_idx == len(raw_imgs) - 1 and s_idx < len(sections_data) - 1:
                    next_sec = sections_data[s_idx + 1]
                    if next_sec.get("is_city_switch"):
                        v_seg.add_transition(draft.TransitionType.叠化, duration=500_000)

                script.add_segment(v_seg, track="主视觉画面轨")

        # 底部语音同步短字幕
        clause_total_chars = sum(len(c) for c in sec["clauses"])
        clause_cur_us = sec_start_us
        for c in sec["clauses"]:
            c_dur_us = int(sec_dur_us * (len(c) / clause_total_chars))
            # 字幕 segment
            sub_seg = draft.TextSegment(
                c,
                draft.Timerange(clause_cur_us, c_dur_us),
                font=draft.FontType.抖音美好体,
                style=sub_style,
                border=sub_border,
                background=sub_bg,
                clip_settings=sub_clip
            )
            script.add_segment(sub_seg, track="中老年大字底字幕")

            # 检查是否有音效提示 (转化提示叮音效)
            if sec.get("sfx_cue") and sec.get("sfx_cue") in c and sfx_file and sfx_file.exists():
                sfx_dur = min(get_audio_duration_us(sfx_file), 2_000_000)
                sfx_seg = draft.AudioSegment(str(sfx_file), draft.Timerange(clause_cur_us, sfx_dur))
                script.add_segment(sfx_seg, track="转化提示音效轨")

            clause_cur_us += c_dur_us

        cur_time_us = sec_end_us

    # 保存剪映工程
    script.save()
    draft_folder_path = Path(JIANYING_DIR) / draft_title
    print(f"  [✓ 剪映工程生成完毕] 路径: {draft_folder_path}")
    print(f"  [✓ 轨道完整性] 已装配: 视频轨, 人声轨(+3dB), BGM轨(-18dB), 顶部双行标, 底部字幕, 营销贴字")
    return draft_folder_path

def main():
    bgm_path = AUDIO_DIR / "bgm_guofeng.mp3"
    sfx_path = AUDIO_DIR / "sfx_ding.wav"

    # 1. 生成上集草稿
    ep1_voice = AUDIO_DIR / "ep1_voice.mp3"
    ep1_json = BASE_DIR / "上集_分镜与短句台账.json"
    p1 = build_draft_for_episode(
        ep_name="上集",
        draft_title="十大历史名城_上集",
        voice_file=ep1_voice,
        sections_json=ep1_json,
        bgm_file=bgm_path
    )

    # 2. 生成下集草稿
    ep2_voice = AUDIO_DIR / "ep2_voice.mp3"
    ep2_json = BASE_DIR / "下集_分镜与短句台账.json"
    p2 = build_draft_for_episode(
        ep_name="下集",
        draft_title="十大历史名城_下集",
        voice_file=ep2_voice,
        sections_json=ep2_json,
        bgm_file=bgm_path,
        sfx_file=sfx_path
    )

    print("\n========================================================")
    print("🎉 上下两集剪映草稿自动化生成完成！可在剪映客户端直接打开验证。")
    print(f"1. 上集工程: {p1}")
    print(f"2. 下集工程: {p2}")
    print("========================================================")

if __name__ == "__main__":
    main()
