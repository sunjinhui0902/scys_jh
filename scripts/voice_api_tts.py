#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自有 API 语音合成（只做声音测试与生成，不做图片、不做视频）
=============================================================
用你自己的 MiniMax 开放平台 API Key 直接调 t2a_v2，不经过桌面端连接器。

流程：
1. 读配置（默认 config/voice_api/config.yaml）里的角色与台词。
2. engine=minimax 的角色走你的 API Key 调 T2A；engine=edge 的角色走 Edge-TTS（免 key）。
3. 逐句合成落盘 → 按场景拼接 → 输出整条 15 秒母版 → 写试听报告。

用法：
    # 全量：合成 6 条 + 生成 3 个场景 + 15 秒母版
    python scripts/voice_api_tts.py

    # 只重做某一句（改完台词/音色只跑一条，不重复消耗额度）
    python scripts/voice_api_tts.py --role 男童

    # 临时试一句新台词（用指定音色）
    python scripts/voice_api_tts.py --role 妈妈 --text "都是你惯的！"

    # 换配置文件
    python scripts/voice_api_tts.py --config config/voice_api/config.yaml

密钥读取顺序：环境变量 MINIMAX_API_KEY > 配置文件 api_key。
配置文件在 .gitignore 内（含密钥，不会进仓库）。
"""

import argparse
import asyncio
import json
import os
import re
import shutil
import hashlib
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml  # noqa: E402
from assemble_voice_test import build_mix, build_sequence, probe_duration_ms, run  # noqa: E402

DEFAULT_CONFIG = ROOT / "config" / "voice_api" / "config.yaml"
DEFAULT_OUT_ROOT = ROOT / "01_配音与音色库"

GAP_WITHIN_SCENE_MS = 350   # 同一场景内两人接话的间隔
GAP_SCENE_MS = 100          # 场景之间硬切短停顿
GAP_QUICK_REPLY_MS = 220    # 抢话感：接话更快

_last_call_at = 0.0


def throttle(cfg: dict) -> None:
    """按配置限速，避免触发 RPM 限制（1002 rate limit exceeded）。"""
    global _last_call_at
    interval = float(cfg.get("request_interval_seconds", 1.3))
    wait = interval - (time.time() - _last_call_at)
    if wait > 0:
        time.sleep(wait)
    _last_call_at = time.time()


def load_config(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"配置文件不存在：{path}\n先从 config/voice_api/config.example.yaml 复制一份并填入 api_key")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def resolve_api_key(cfg: dict) -> str:
    key = os.environ.get("MINIMAX_API_KEY") or str(cfg.get("api_key") or "").strip()
    if not key:
        raise SystemExit(
            "没有可用密钥：请在配置文件里填 api_key，或先设置环境变量 MINIMAX_API_KEY"
        )
    return key


def synthesize_minimax(cfg: dict, line: dict, target: Path) -> dict:
    """调用 T2A v2 合成，返回用量信息。"""
    base = str(cfg.get("base_url") or "https://api.minimaxi.com").rstrip("/")
    url = f"{base}/v1/t2a_v2"
    audio_setting = dict(cfg.get("audio_setting") or {})
    voice_setting = {
        "voice_id": line["voice_id"],
        "speed": line.get("speed", 1.0),
        "vol": line.get("vol", 1.0),
        "pitch": line.get("pitch", 0),
    }
    if line.get("emotion"):
        voice_setting["emotion"] = line["emotion"]
    payload = {
        "model": line.get("model") or cfg.get("model") or "speech-2.8-hd",
        "text": line["text"],
        "stream": False,
        "language_boost": cfg.get("language_boost", "auto"),
        "output_format": "hex",
        "voice_setting": voice_setting,
        "audio_setting": audio_setting,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + resolve_api_key(cfg),
            "Content-Type": "application/json",
        },
    )
    payload_out = None
    for attempt in range(1, int(cfg.get("max_retries", 4)) + 1):
        throttle(cfg)
        try:
            with urllib.request.urlopen(request, timeout=cfg.get("timeout_seconds", 90)) as response:
                payload_out = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"T2A 请求失败 HTTP {exc.code}: {detail}") from exc
        base_resp = payload_out.get("base_resp") or {}
        status = base_resp.get("status_code")
        if status in (0, None):
            break
        if status == 1002 and attempt < int(cfg.get("max_retries", 4)):
            backoff = 8 * attempt
            print(f"[限流] 1002 rate limit，{backoff}s 后重试（第 {attempt} 次）", flush=True)
            time.sleep(backoff)
            continue
        raise RuntimeError(f"T2A 返回错误：{status} {base_resp.get('status_msg')}")

    base_resp = payload_out.get("base_resp") or {}
    if base_resp.get("status_code") not in (0, None):
        raise RuntimeError(f"T2A 返回错误：{base_resp.get('status_code')} {base_resp.get('status_msg')}")
    audio_hex = (payload_out.get("data") or {}).get("audio") or ""
    if not audio_hex:
        raise RuntimeError("T2A 未返回音频数据")
    target.write_bytes(bytes.fromhex(audio_hex))
    info = payload_out.get("extra_info") or {}
    return {
        "engine": "minimax",
        "model": payload["model"],
        "usage_characters": info.get("usage_characters"),
        "audio_length_ms": info.get("audio_length"),
        "trace_id": payload_out.get("trace_id"),
    }


def synthesize_edge(cfg: dict, line: dict, target: Path) -> dict:
    """Edge-TTS 合成，免密钥。"""
    import edge_tts

    rate = signed_edge_value(line.get("edge_rate", "+0%"), "%")
    pitch = signed_edge_value(line.get("edge_pitch", "+0Hz"), "Hz")
    volume = signed_edge_value(line.get("edge_volume", "+0%"), "%")
    voice = line["edge_voice"]

    async def _run() -> None:
        communicate = edge_tts.Communicate(line["text"], voice, rate=rate, pitch=pitch, volume=volume)
        result = communicate.save(str(target))
        if asyncio.iscoroutine(result):
            await result

    asyncio.run(_run())
    return {"engine": "edge", "edge_voice": voice, "edge_rate": rate, "edge_pitch": pitch}


def signed_edge_value(value: str, unit: str) -> str:
    text = str(value).strip()
    if not re.fullmatch(r"[+-]?\d+" + re.escape(unit), text):
        raise ValueError(f"Edge 参数格式不正确：{unit}")
    return text if text.startswith(("+", "-")) else "+" + text


def synthesis_signature(cfg: dict, line: dict) -> str:
    """只比较影响合成的字段，不包含文件名、角色别名或密钥。"""
    if line.get("engine", "minimax") == "edge":
        data = {"engine": "edge", "text": line["text"], "voice": line["edge_voice"],
                "rate": signed_edge_value(line.get("edge_rate", "+0%"), "%"),
                "pitch": signed_edge_value(line.get("edge_pitch", "+0Hz"), "Hz"),
                "volume": signed_edge_value(line.get("edge_volume", "+0%"), "%")}
    else:
        data = {"engine": "minimax", "text": line["text"], "voice": line["voice_id"],
                "model": line.get("model") or cfg.get("model"), "speed": line.get("speed", 1.0),
                "pitch": line.get("pitch", 0), "vol": line.get("vol", 1.0),
                "emotion": line.get("emotion"), "audio": cfg.get("audio_setting"),
                "language": cfg.get("language_boost", "auto")}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def resolve_line(cfg: dict, line: dict) -> dict:
    """合并「角色基础配置表」默认值与本条台词的覆盖参数。"""
    roles = cfg.get("roles") or {}
    role_key = line.get("role")
    merged: dict = dict(roles.get(role_key) or {})
    for key, value in line.items():
        if value is not None:
            merged[key] = value
    merged["role"] = role_key
    if "pitch_offset" in merged:
        # 角色级音调偏移：保住该角色的年龄音色基调
        merged["pitch"] = int(merged.get("pitch", 0)) + int(merged.pop("pitch_offset"))
    if not merged.get("save_name"):
        ident = merged.get("id") or f"{role_key}_{abs(hash(merged.get('text', ''))) % 10000}"
        merged["save_name"] = f"{ident}.mp3"
    return merged


def role_matches(cfg: dict, line: dict, wanted: str) -> bool:
    """--role 可用角色别名（boy）或角色中文名（男宝）匹配。"""
    if line.get("role") == wanted:
        return True
    roles = cfg.get("roles") or {}
    base = roles.get(line.get("role")) or {}
    return str(base.get("name") or "") == wanted


def synthesize_line(cfg: dict, line: dict, out_dir: Path, reuse: dict | None = None,
                    no_new_minimax: bool = False) -> dict:
    target = out_dir / line["save_name"]
    engine = line.get("engine", "minimax")
    if target.exists() and target.stat().st_size >= 1024 and cfg.get("skip_existing", True):
        # 断点续跑：已合成过的句子不重复消耗额度
        return {
            "engine": engine,
            "skipped": True,
            "role": line.get("role"),
            "file": line["save_name"],
            "text": line.get("text"),
            "provenance": "existing_audio_original_request_not_recorded",
        }
    signature = synthesis_signature(cfg, line)
    reusable = (reuse or {}).get(signature)
    if reusable and reusable.exists():
        shutil.copyfile(reusable, target)
        return {"engine": engine, "role": line["role"], "file": line["save_name"],
                "text": line["text"], "reused_from": reusable.name,
                "provenance": "copied_equivalent_current_config_original_request_not_recorded"}
    if engine != "edge" and no_new_minimax:
        raise RuntimeError(f"缺少 {line['save_name']}，已禁止新增收费 MiniMax 请求")
    if engine == "edge":
        info = synthesize_edge(cfg, line, target)
    else:
        info = synthesize_minimax(cfg, line, target)
    info.update({"role": line["role"], "file": line["save_name"], "text": line["text"]})
    if reuse is not None:
        reuse[signature] = target
    return info


def main() -> None:
    parser = argparse.ArgumentParser(description="自有 API 语音合成与拼接")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="配置文件路径")
    parser.add_argument("--out", default=None, help="输出目录名（相对 01_配音与音色库）")
    parser.add_argument("--role", default=None, help="只合成指定角色，例如 男童")
    parser.add_argument("--text", default=None, help="覆盖该角色台词（临时试音用）")
    parser.add_argument("--voice-id", default=None, help="覆盖音色 ID（试其他音色用）")
    parser.add_argument("--edge-voice", default=None, help="覆盖 Edge 音色")
    parser.add_argument("--emotion", default=None, help="覆盖情绪")
    parser.add_argument("--speed", type=float, default=None, help="覆盖语速")
    parser.add_argument("--pitch", type=int, default=None, help="覆盖音调")
    parser.add_argument("--no-mix", action="store_true", help="只合成单句，不做场景与母版拼接")
    parser.add_argument("--pack", action="store_true", help="仅完成顶层配音库，不处理旧钩子目录")
    parser.add_argument("--delivery", default=None, help="在新子目录中输出混音和报告，保留原有合集")
    parser.add_argument("--reuse-equivalent", action="store_true", help="复用按当前配置比对完全等价的已存音频")
    parser.add_argument("--no-new-minimax", action="store_true", help="禁止新增收费 MiniMax 请求")
    args = parser.parse_args()

    cfg = load_config(Path(args.config).expanduser().resolve())
    out_name = args.out or cfg.get("output_dir") or "六声线测试_家庭钩子_20261106"
    out_dir = DEFAULT_OUT_ROOT / out_name
    out_dir.mkdir(parents=True, exist_ok=True)
    delivery_dir = out_dir / args.delivery if args.delivery else out_dir
    if args.delivery:
        if delivery_dir.exists():
            raise SystemExit("交付目录已存在，请使用新的目录名，避免覆盖上次试听")
        delivery_dir.mkdir(parents=True)
    if args.pack and not args.delivery:
        raise SystemExit("--pack 必须配合新的 --delivery 目录使用")
    work_dir = delivery_dir / ("干声WAV" if args.delivery else "_work")
    work_dir.mkdir(parents=True, exist_ok=True)

    scenes = cfg.get("scenes") or []
    if not scenes:
        raise SystemExit("配置里没有 scenes")

    # 解析每条台词：角色基础配置表 + 本条覆盖参数
    resolved_scenes = []
    for scene in scenes:
        if args.pack and scene.get("out_dir"):
            continue
        lines = []
        for raw in scene.get("lines", []):
            line = resolve_line(cfg, raw)
            if args.role and not role_matches(cfg, line, args.role):
                continue
            if args.text:
                line = dict(line, text=args.text)
            if args.voice_id:
                line = dict(line, engine="minimax", voice_id=args.voice_id)
            if args.edge_voice:
                line = dict(line, engine="edge", edge_voice=args.edge_voice)
            if args.emotion:
                line = dict(line, emotion=args.emotion)
            if args.speed is not None:
                line = dict(line, speed=args.speed)
            if args.pitch is not None:
                line = dict(line, pitch=args.pitch)
            lines.append(line)
        if lines:
            resolved_scenes.append({**scene, "lines": lines})

    if not resolved_scenes:
        raise SystemExit(f"没有匹配到角色：{args.role}")

    ffmpeg = __import__("imageio_ffmpeg").get_ffmpeg_exe()
    report_lines = []
    wav_paths: dict[str, Path] = {}
    duration_by_name: dict[str, int] = {}
    reuse = {} if args.reuse_equivalent else None
    if reuse is not None:
        for scene in resolved_scenes:
            folder = DEFAULT_OUT_ROOT / scene["out_dir"] if scene.get("out_dir") else out_dir
            for line in scene["lines"]:
                existing = folder / line["save_name"]
                if existing.exists() and existing.stat().st_size >= 1024:
                    reuse.setdefault(synthesis_signature(cfg, line), existing)

    for scene in resolved_scenes:
        scene_dir = DEFAULT_OUT_ROOT / scene["out_dir"] if scene.get("out_dir") else out_dir
        scene_dir.mkdir(parents=True, exist_ok=True)
        for line in scene["lines"]:
            info = synthesize_line(cfg, line, scene_dir, reuse, args.no_new_minimax)
            wav_path = work_dir / (Path(line["save_name"]).stem + ".wav")
            run([ffmpeg, "-hide_banner", "-y", "-i", str(scene_dir / line["save_name"]), "-ac", "1", "-ar", "44100", str(wav_path)])
            wav_paths[line["save_name"]] = wav_path
            duration_by_name[line["save_name"]] = probe_duration_ms(ffmpeg, wav_path)
            info["duration_ms"] = duration_by_name[line["save_name"]]
            info["voice_id"] = line.get("voice_id") or line.get("edge_voice")
            info["emotion"] = line.get("emotion")
            info["speed"] = line.get("speed")
            info["pitch"] = line.get("pitch")
            info["sha256"] = hashlib.sha256((scene_dir / line["save_name"]).read_bytes()).hexdigest()
            info["source_file"] = str((scene_dir / line["save_name"]).relative_to(ROOT))
            report_lines.append(info)
            (delivery_dir / "合成进度.json").write_text(json.dumps(report_lines, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[合成] {line['role']}: {line['save_name']} "
                  f"({duration_by_name[line['save_name']]}ms, {info.get('usage_characters', '-')} 字符)")

    if args.no_mix:
        return

    # 场景拼接：gap_ms 可按场景指定接话间隔
    scene_reports = []
    for scene in resolved_scenes:
        names = [ln["save_name"] for ln in scene["lines"]]
        if any(n not in wav_paths for n in names):
            continue
        offsets = [0]
        for pos in range(1, len(names)):
            if scene.get("gap_ms") is not None:
                gap = int(scene["gap_ms"])
            else:
                gap = GAP_QUICK_REPLY_MS if pos == len(names) - 1 else GAP_WITHIN_SCENE_MS
            offsets.append(offsets[-1] + duration_by_name[names[pos - 1]] + gap)
        scene_path = (delivery_dir if args.delivery else
                      DEFAULT_OUT_ROOT / scene["out_dir"] if scene.get("out_dir") else out_dir) / scene["name"]
        build_mix(ffmpeg, [wav_paths[n] for n in names], offsets, scene_path, as_mp3=True)
        scene_reports.append({"file": scene["name"], "duration_ms": probe_duration_ms(ffmpeg, scene_path)})
        print(f"[场景] {scene['name']} ({scene_reports[-1]['duration_ms']}ms)")

    if args.pack:
        # 主版与备选分别保留完整时长；绝不能沿用旧15秒母版的截断参数。
        primary = [line for scene in resolved_scenes if not any(
            x.get("engine") == "edge" for x in scene["lines"]) for line in scene["lines"]]
        alternates = [line for scene in resolved_scenes if any(
            x.get("engine") == "edge" for x in scene["lines"]) for line in scene["lines"]]
        collections = []
        for label, group in [("完整试听_主版", primary), ("完整试听_Edge爷爷备选", alternates)]:
            if not group:
                continue
            stem = delivery_dir / f"{label}_{len(group)}条"
            positions = build_sequence([wav_paths[x["save_name"]] for x in group], stem.with_suffix(".wav"), 700)
            run([ffmpeg, "-hide_banner", "-y", "-i", str(stem.with_suffix(".wav")),
                 "-c:a", "libmp3lame", "-b:a", "192k", str(stem.with_suffix(".mp3"))])
            collections.append({"file": stem.with_suffix(".mp3").name,
                                "duration_ms": probe_duration_ms(ffmpeg, stem.with_suffix(".mp3")),
                                "timeline": [{"file": x["save_name"], "role": x["role"], "text": x["text"],
                                              "start_ms": pos, "end_ms": pos + duration_by_name[x["save_name"]]}
                                             for x, pos in zip(group, positions)]})
        summary = {"output_dir": str(delivery_dir.relative_to(ROOT)), "lines": report_lines,
                   "scenes": scene_reports, "collections": collections,
                   "new_minimax_calls": sum(x.get("engine") == "minimax" and not x.get("skipped") and
                                            not x.get("reused_from") for x in report_lines),
                   "human_review": "pending", "existing_audio_parameters": "inherited_from_current_config_not_independently_verified"}
        (delivery_dir / "试听报告.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[交付完成] {len(report_lines)}条；新增 MiniMax 请求 {summary['new_minimax_calls']}；人工试听待确认")
        return

    # 整条母版
    all_names = [ln["save_name"] for sc in resolved_scenes for ln in sc["lines"]]
    if cfg.get("full_name") and all(n in wav_paths for n in all_names):
        offsets = [0]
        for pos in range(1, len(all_names)):
            if pos % 2 == 1:
                gap = GAP_QUICK_REPLY_MS if pos == len(all_names) - 1 else GAP_WITHIN_SCENE_MS
            else:
                gap = GAP_SCENE_MS
            offsets.append(offsets[-1] + duration_by_name[all_names[pos - 1]] + gap)
        total = cfg.get("total_seconds", 15)
        stem_dir = delivery_dir if args.delivery else DEFAULT_OUT_ROOT / cfg["master_out_dir"] if cfg.get("master_out_dir") else out_dir
        stem_dir.mkdir(parents=True, exist_ok=True)
        stem = stem_dir / cfg.get("full_name", "完整_15秒_六声线对白_纯对白版")
        build_mix(ffmpeg, [wav_paths[n] for n in all_names], offsets, stem.with_suffix(".wav"), as_mp3=False, pad_to=total)
        build_mix(ffmpeg, [wav_paths[n] for n in all_names], offsets, stem.with_suffix(".mp3"), as_mp3=True, pad_to=total)
        print(f"[母版] {stem.name}.wav / .mp3 ({probe_duration_ms(ffmpeg, stem.with_suffix('.wav'))}ms)")

        timeline = []
        for idx, name in enumerate(all_names):
            role = next(ln["role"] for sc in resolved_scenes for ln in sc["lines"] if ln["save_name"] == name)
            text = next(ln["text"] for sc in resolved_scenes for ln in sc["lines"] if ln["save_name"] == name)
            timeline.append({"role": role, "line": text, "start_ms": offsets[idx], "end_ms": offsets[idx] + duration_by_name[name]})

    summary = {
        "output_dir": str(out_dir.relative_to(ROOT)),
        "lines": report_lines,
        "scenes": scene_reports,
        "timeline": timeline if cfg.get("full_name") else [],
    }
    (out_dir / "试听报告.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
