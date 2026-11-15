#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第三周配音语气单解析器
======================
把云盘「视频号第三周 / 02_音频脚本 / 第三周_配音语气单.md」解析成结构化逐句数据，
再生成可交给 scripts/voice_api_tts.py 的 YAML 配置。

冻结纪律（来源：01_口播定稿/第三周_口播冻结稿.md 文件头）：
- 口播原文一字不改，本脚本只读取、不改写；
- 定版音色不换角（全周只用爷爷/奶奶两种）；
- 逐句生成，句间停顿按语气单标注值裁边合成，不留原始长静默。

用法：
    python scripts/parse_week3_tone_sheet.py                 # 解析 + 写配置 + 打印统计
    python scripts/parse_week3_tone_sheet.py --stats-only    # 只看统计，不写文件
    python scripts/parse_week3_tone_sheet.py --episodes D1早,D1午   # 只导出指定条目
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 云盘路径：优先走本机已挂载的 Google Drive 盘符（无需 API）
CLOUD_ROOT = Path(r"G:\我的云端硬盘\JH\视频号第三周")
TONE_SHEET = CLOUD_ROOT / "02_音频脚本" / "第三周_配音语气单.md"
LOCAL_TONE_SHEET = ROOT / "config" / "voice_api" / "第三周_配音语气单.md"
OUT_YAML = ROOT / "config" / "voice_api" / "config_week3_第三周.yaml"

# ---------- 解析规则 ----------
EP_RE = re.compile(r"^##\s+(D\d[早午晚][^\n]*)$", re.M)
LINE_RE = re.compile(
    r"^-\s*(A\d+)｜([^｜]+)｜原文：(.*?)｜语气：(.*?)；音调：(.*?)；语速：(.*?)；停顿：(.*?)；重音：(.*?)；场景：(.*)$",
    re.M,
)
BASE_RE = re.compile(r"^-\s*(A\d+)｜([^｜]+)｜原文：(.*)$", re.M)

# 条目 ASCII 键：命令行传中文会被 PowerShell 编码破坏，故同时提供 D1-morning 这类纯 ASCII 键
SLOT_EN = {"早": "morning", "午": "noon", "晚": "evening"}


def episode_id(title: str) -> str:
    m = re.match(r"(D\d)[早午晚]", title.strip())
    if not m:
        return title.strip().split("｜")[0]
    slot = re.match(r"(D\d)[早午晚]", title.strip()).group(0)[len(m.group(1)):]
    return f"{m.group(1)}-{SLOT_EN.get(slot, slot)}"


# 语速描述 → MiniMax speed 倍率
SPEED_MAP = {
    "偏慢": 0.92,
    "中速偏慢": 0.93,
    "中慢": 0.95,
    "慢": 0.95,
    "中速": 1.00,
    "中速偏快一点点": 1.03,
    "中速偏快": 1.03,
}

# 语气描述 → MiniMax emotion（t2a_v2 支持：happy/sad/angry/fearful/disgusted/surprised/calm/neutral）
# 已实测：chat/excited/grateful/serious/confused 被 API 拒绝（2013 invalid params），不可用。
# 匹配顺序即优先级：先具体后笼统，happy 置于 sad 之前（「又心疼又有点想笑」应判为带笑）。
EMOTION_RULES = [
    ("surprised", ["惊奇", "惊讶", "意外", "错愕", "意外地", "稀奇"]),
    ("angry", ["严厉", "生气", "火气", "怼", "训斥", "发火"]),
    ("happy", ["带笑", "笑意", "轻快", "开心", "自豪", "暖", "馋意", "兴奋", "带劲", "高兴", "笑"]),
    ("sad", ["心疼", "委屈", "惋惜", "惆怅", "失落", "无奈", "叹息", "伤", "难过", "着急", "发紧"]),
    ("calm", ["沉稳", "笃定", "平稳", "认真", "郑重", "正式", "冷静", "通透", "家常口吻", "随口",
              "念叨", "交底", "掏心窝子", "掰着手指头", "顺着话头", "条理", "干脆", "平静", "平实",
              "实在", "诚恳", "坦率", "不凶", "和气", "温和", "收口", "收尾", "讲理", "提醒"]),
]
DEFAULT_EMOTION = "calm"


def detect_emotion(mood: str) -> str:
    for emotion, keys in EMOTION_RULES:
        if any(k in mood for k in keys):
            return emotion
    return DEFAULT_EMOTION


def detect_pitch(tone: str, role: str) -> int:
    """MiniMax pitch 偏移（整数档位）。语气单只描述音调走向，不含绝对音高。"""
    if "上扬" in tone or "微扬" in tone:
        return 1
    if "下沉" in tone or "偏低" in tone:
        return -1
    return 0


def parse_speed(desc: str) -> float:
    for k, v in SPEED_MAP.items():
        if k in desc:
            return v
    return 1.0


def parse_gap(pause_desc: str) -> int:
    """取「句后/句末」的静默毫秒数；句中没有作为句间间隔的依据。"""
    m = re.search(r"句(?:后|末)\s*(?:停|收)?\s*([0-9.]+)\s*秒", pause_desc)
    if m:
        return int(round(float(m.group(1)) * 1000))
    m = re.search(r"([0-9.]+)\s*秒", pause_desc)
    if m:
        return int(round(float(m.group(1)) * 1000))
    return 400


def normalize_role(role_raw: str) -> str:
    role = role_raw.strip()
    role = role.replace("（奶奶音色）", "").replace("（爷爷音色）", "").strip()
    role = re.sub(r"[（(].*?[)）]", "", role).strip()
    return role.split()[0] if role else "爷爷"


def load_sheet() -> str:
    for p in (TONE_SHEET, LOCAL_TONE_SHEET):
        if p.is_file():
            return p.read_text(encoding="utf-8")
    raise SystemExit(f"找不到配音语气单：{TONE_SHEET} 或 {LOCAL_TONE_SHEET}")


def parse(text: str) -> list[dict]:
    marks = list(EP_RE.finditer(text))
    episodes = []
    for i, m in enumerate(marks):
        title = m.group(1).strip()
        body = text[m.end(): marks[i + 1].start() if i + 1 < len(marks) else len(text)]
        lines = []
        for lm in LINE_RE.finditer(body):
            lid, role_raw, original, mood, tone, speed_desc, pause, stress, scene = lm.groups()
            role = normalize_role(role_raw)
            lines.append({
                "id": lid,
                "role": role,
                "text": original.strip(),
                "mood": mood.strip(),
                "tone": tone.strip(),
                "speed_desc": speed_desc.strip(),
                "speed": parse_speed(speed_desc),
                "pause": pause.strip(),
                "gap_ms": parse_gap(pause),
                "stress": stress.strip(),
                "scene": scene.strip(),
                "emotion": detect_emotion(mood),
                "pitch": detect_pitch(tone, role),
            })
        if not lines:  # 兜底：条目里若缺字段分隔，退化为「Axx｜角色｜原文」三段式
            for bm in BASE_RE.finditer(body):
                lid, role_raw, original = bm.groups()
                lines.append({
                    "id": lid, "role": normalize_role(role_raw), "text": original.strip(),
                    "mood": "", "tone": "", "speed_desc": "", "speed": 1.0, "pause": "",
                    "gap_ms": 400, "stress": "", "scene": "", "emotion": DEFAULT_EMOTION, "pitch": 0,
                })
        episodes.append({"title": title, "eid": episode_id(title), "lines": lines})
    return episodes


def build_yaml(episodes: list[dict], roles_cfg: dict, api_cfg: dict) -> dict:
    scenes = []
    for ep in episodes:
        lines = []
        for ln in ep["lines"]:
            role_key = "grandpa" if ln["role"] == "爷爷" else "grandma"
            lines.append({
                "role": role_key,
                "text": ln["text"],
                "speed": ln["speed"],
                "pitch": ln["pitch"],
                "emotion": ln["emotion"],
                "save_name": f"{ep['title'].split('｜')[0].split(' ')[0]}_{ln['id']}.mp3",
            })
        scenes.append({
            "name": f"{ep['title'].split('｜')[0].split(' ')[0]}.mp3",
            "out_dir": "第三周配音_20261115",
            "lines": lines,
        })
    out = {
        "api_key": api_cfg.get("api_key", ""),
        "base_url": api_cfg.get("base_url", "https://api.minimaxi.com"),
        "model": api_cfg.get("model", "speech-2.8-hd"),
        "language_boost": api_cfg.get("language_boost", "auto"),
        "timeout_seconds": api_cfg.get("timeout_seconds", 90),
        "audio_setting": api_cfg.get("audio_setting", {"sample_rate": 32000, "bitrate": 128000, "format": "mp3", "channel": 1}),
        "output_dir": "第三周配音_20261115",
        "request_interval_seconds": api_cfg.get("request_interval_seconds", 1.3),
        "max_retries": api_cfg.get("max_retries", 4),
        "skip_existing": True,
        "roles": roles_cfg,
        "scenes": scenes,
        "_meta": {
            "source": "云盘 JH/视频号第三周/02_音频脚本/第三周_配音语气单.md",
            "frozen": "2026-11-15 00:54 xun 冻结（口播一字不改）",
            "generated_by": "scripts/parse_week3_tone_sheet.py",
        },
    }
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="解析第三周配音语气单")
    ap.add_argument("--stats-only", action="store_true")
    ap.add_argument("--episodes", default=None,
                    help="只导出指定条目。接受 ASCII 键（D1-morning/D1-noon/D1-evening）"
                         "或条目序号（1-20），逗号分隔")
    ap.add_argument("--out", default=str(OUT_YAML))
    args = ap.parse_args()

    text = load_sheet()
    all_eps = parse(text)
    episodes = all_eps
    if args.episodes:
        want = {s.strip() for s in args.episodes.split(",") if s.strip()}
        picked = []
        for i, ep in enumerate(all_eps, 1):
            if ep["eid"] in want or ep["title"].split("｜")[0] in want or str(i) in want:
                picked.append(ep)
        episodes = picked
        if not episodes:
            print("可用条目：")
            for i, ep in enumerate(all_eps, 1):
                print(f"  {i:2d}. {ep['eid']:14s} {ep['title']}")
            raise SystemExit(f"没有匹配的条目：{sorted(want)}")

    total_lines = sum(len(e["lines"]) for e in episodes)
    total_chars = sum(len(l["text"]) for e in episodes for l in e["lines"])
    role_lines = Counter(l["role"] for e in episodes for l in e["lines"])
    role_chars = Counter()
    for e in episodes:
        for l in e["lines"]:
            role_chars[l["role"]] += len(l["text"])

    print(f"条目 {len(episodes)}  句数 {total_lines}  字数 {total_chars}")
    print()
    for e in episodes:
        chars = sum(len(l["text"]) for l in e["lines"])
        rset = "+".join(sorted({l["role"] for l in e["lines"]}))
        print(f"  {e['eid']:14s} {len(e['lines']):3d}句 {chars:4d}字  {rset}   {e['title'].split('｜')[-1]}")
    print()
    print("角色分布：")
    for r, c in role_lines.most_common():
        engine = "Edge(免费)" if r == "爷爷" else "MiniMax(按字计费)"
        print(f"  {r}: {c}句 / {role_chars[r]}字  [{engine}]")
    print()
    print("emotion 分布：", dict(Counter(l["emotion"] for e in episodes for l in e["lines"])))
    print("speed 分布：", sorted({l["speed"] for e in episodes for l in e["lines"]}))
    print("gap 分布(ms)：", sorted({l["gap_ms"] for e in episodes for l in e["lines"]}))
    print()
    print("语气描述去重（emotion 未命中的需人工复核）：")
    unmapped = []
    for e in episodes:
        for l in e["lines"]:
            if not any(k in l["mood"] for _, ks in EMOTION_RULES for k in ks):
                unmapped.append((l["id"], l["mood"]))
    for lid, mood in dict.fromkeys(unmapped):
        print(f"  {lid}: {mood}")

    if args.stats_only:
        return

    import yaml
    api_cfg = yaml.safe_load((ROOT / "config" / "voice_api" / "config.yaml").read_text(encoding="utf-8")) or {}
    final_cfg = yaml.safe_load(
        (ROOT / "01_配音与音色库" / "六角色定稿_V1_20261107" / "六角色定稿配置.json").read_text(encoding="utf-8")
    )
    roles_cfg = final_cfg["roles"]
    out = build_yaml(episodes, roles_cfg, api_cfg)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "# 由 scripts/parse_week3_tone_sheet.py 自动生成，请勿手改\n"
        "# 角色参数来自 01_配音与音色库/六角色定稿_V1_20261107/六角色定稿配置.json\n"
        + yaml.safe_dump(out, allow_unicode=True, sort_keys=False, width=1000),
        encoding="utf-8",
    )
    print()
    print(f"已写出配置：{out_path}")
    print(f"下一步：python scripts/voice_api_tts.py --config {out_path}")


if __name__ == "__main__":
    main()
