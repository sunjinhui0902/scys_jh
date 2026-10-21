import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import json
from pathlib import Path

JIANYING_DIR = Path(r"C:\Users\Miche\AppData\Local\JianyingPro\User Data\Projects\com.lveditor.draft")

drafts_info = [
    {
        "id": "01_平遥",
        "name": "【图书带货】带孙辈长见识：第10名·山西平遥_音字对齐修订_20261022",
        "project_dir": "03_视频成片与工程/01_平遥古城_单集精讲",
        "checkpoints": [
            ("说到这儿", 110.08, 113.11),
            ("肚子里的词儿", 121.23, 124.33)
        ]
    },
    {
        "id": "02_延安",
        "name": "【图书带货】带孙辈长见识：第9名·陕西延安_音字对齐修订_20261022",
        "project_dir": "03_视频成片与工程/02_延安宝塔山_单集精讲",
        "checkpoints": [
            ("说到这儿", 87.46, 89.67)
        ]
    },
    {
        "id": "03_开封",
        "name": "【图书带货】带孙辈长见识：第8名·河南开封_音字对齐修订_20261022",
        "project_dir": "03_视频成片与工程/03_开封清明上河园_单集精讲",
        "checkpoints": [
            ("就全印在孩子脑子里了", 88.79, 90.59)
        ]
    },
    {
        "id": "04_苏州",
        "name": "【图书带货】带孙辈长见识：第7名·江苏苏州_音字对齐修订_20261022",
        "project_dir": "03_视频成片与工程/04_苏州拙政园_单集精讲",
        "checkpoints": [
            ("居然稳稳地出现在了", 65.85, 68.42)
        ]
    },
    {
        "id": "05_杭州",
        "name": "【图书带货】带孙辈长见识：第6名·浙江杭州_音字对齐修订_20261022",
        "project_dir": "03_视频成片与工程/05_杭州西湖_单集精讲",
        "checkpoints": [
            ("不知道怎么把苏东坡", 91.68, 93.43)
        ]
    }
]

print("==========================================================================================")
print("                       五城修订草稿全量实测与质量审计报告                                   ")
print("==========================================================================================")

for dinfo in drafts_info:
    draft_dir = JIANYING_DIR / dinfo["name"]
    content_file = draft_dir / "draft_content.json"
    if not content_file.exists():
        print(f"❌ [缺失] 未找到草稿: {dinfo['name']}")
        continue

    data = json.loads(content_file.read_text(encoding="utf-8"))
    texts_dict = {t["id"]: t for t in data.get("materials", {}).get("texts", [])}
    tracks = data.get("tracks", [])

    # 获取人声与BGM轨道
    voice_track = next((t for t in tracks if "解说人声" in t.get("name", "")), None)
    bgm_track = next((t for t in tracks if "背景音乐" in t.get("name", "")), None)
    sub_track = next((t for t in tracks if "底字幕" in t.get("name", "")), None)
    nav_track = next((t for t in tracks if "导航卡" in t.get("name", "")), None)
    title_track = next((t for t in tracks if "主标题" in t.get("name", "")), None)
    sticker_track = next((t for t in tracks if "贴字" in t.get("name", "")), None)
    v_track = next((t for t in tracks if "主视觉" in t.get("name", "")), None)

    voice_vol = voice_track["segments"][0]["volume"] if voice_track and voice_track.get("segments") else "N/A"
    bgm_vol = bgm_track["segments"][0]["volume"] if bgm_track and bgm_track.get("segments") else "N/A"

    # 提取音频淡入淡出
    fades = data.get("materials", {}).get("audio_fades", [])
    fade_in = next((f["fade_in_duration"]/1e6 for f in fades if f.get("fade_in_duration", 0) > 0), 0)
    fade_out = next((f["fade_out_duration"]/1e6 for f in fades if f.get("fade_out_duration", 0) > 0), 0)

    # 提取贴字文案
    sticker_text = ""
    if sticker_track and sticker_track.get("segments"):
        s_mat_id = sticker_track["segments"][0].get("material_id")
        if s_mat_id in texts_dict:
            sticker_text = json.loads(texts_dict[s_mat_id].get("content", "{}")).get("text", "")

    # 提取主标题
    main_title = ""
    if title_track and title_track.get("segments"):
        t_mat_id = title_track["segments"][0].get("material_id")
        if t_mat_id in texts_dict:
            main_title = json.loads(texts_dict[t_mat_id].get("content", "{}")).get("text", "")

    print(f"\n------------------------------------------------------------------------------------------")
    print(f"🎬 【{dinfo['id']}】草稿名称: {dinfo['name']}")
    print(f"   - 人声音量: {voice_vol} (+3.0dB) | BGM音量: {bgm_vol} (-13.0dB) | BGM淡入: {fade_in}s | 淡出: {fade_out}s")
    print(f"   - 顶部主标题: {main_title}")
    print(f"   - 营销贴字: {sticker_text}")
    print(f"   - 视觉分镜数: {len(v_track['segments']) if v_track else 0} | 导航卡数: {len(nav_track['segments']) if nav_track else 0}")
    print(f"   - 底字幕条数: {len(sub_track['segments']) if sub_track else 0}")

    # 解析所有字幕
    subtitles = []
    if sub_track:
        for s in sub_track.get("segments", []):
            mat_id = s.get("material_id")
            content_json = texts_dict.get(mat_id, {}).get("content", "{}")
            txt = json.loads(content_json).get("text", "")
            tr = s.get("target_timerange", {})
            subtitles.append({
                "text": txt,
                "start": tr.get("start", 0) / 1e6,
                "dur": tr.get("duration", 0) / 1e6,
                "end": (tr.get("start", 0) + tr.get("duration", 0)) / 1e6
            })

    # 检查重点问题对齐误差
    print(f"   📍 关键问题点对齐核验表:")
    print(f"      {'检测文案片段':<22} | {'旧版字幕时间':<10} | {'实际发音波形':<10} | {'修订草稿时间':<10} | {'绝对误差(Δt)':<10} | 判定")
    for cp_text, old_t, asr_t in dinfo["checkpoints"]:
        # 寻找匹配字幕
        matched = next((s for s in subtitles if cp_text in s["text"] or any(w in s["text"] for w in cp_text.split())), None)
        if matched:
            new_t = matched["start"]
            diff = abs(new_t - asr_t)
            verdict = "✅ 达标 (<=0.05s)" if diff <= 0.05 else ("✅ 达标 (<=0.3s)" if diff <= 0.3 else "❌ 超标")
            print(f"      {cp_text:<24} | {old_t:>8.2f}s  | {asr_t:>8.2f}s  | {new_t:>8.2f}s  | {diff:>8.2f}s  | {verdict}")
        else:
            print(f"      {cp_text:<24} | 未能直接匹配对应字幕条目")

    # 抽样前中后字幕
    if subtitles:
        mid_idx = len(subtitles) // 2
        print(f"   🔍 前/中/后时间采样:")
        print(f"      [前段 1] {subtitles[0]['start']:.2f}s - {subtitles[0]['end']:.2f}s: {subtitles[0]['text']}")
        print(f"      [中段 {mid_idx}] {subtitles[mid_idx]['start']:.2f}s - {subtitles[mid_idx]['end']:.2f}s: {subtitles[mid_idx]['text']}")
        print(f"      [末段 {len(subtitles)}] {subtitles[-1]['start']:.2f}s - {subtitles[-1]['end']:.2f}s: {subtitles[-1]['text']}")
