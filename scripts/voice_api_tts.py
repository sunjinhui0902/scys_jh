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
import sys
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
from assemble_voice_test import build_mix, probe_duration_ms, run  # noqa: E402

DEFAULT_CONFIG = ROOT / "config" / "voice_api" / "config.yaml"
DEFAULT_OUT_ROOT = ROOT / "01_配音与音色库"

GAP_WITHIN_SCENE_MS = 350   # 同一场景内两人接话的间隔
GAP_SCENE_MS = 100          # 场景之间硬切短停顿
GAP_QUICK_REPLY_MS = 220    # 抢话感：接话更快


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
    try:
        with urllib.request.urlopen(request, timeout=cfg.get("timeout_seconds", 90)) as response:
            payload_out = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"T2A 请求失败 HTTP {exc.code}: {detail}") from exc

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

    rate = line.get("edge_rate", "+0%")
    pitch = line.get("edge_pitch", "+0Hz")
    volume = line.get("edge_volume", "+0%")
    voice = line["edge_voice"]

    async def _run() -> None:
        communicate = edge_tts.Communicate(line["text"], voice, rate=rate, pitch=pitch, volume=volume)
        result = communicate.save(str(target))
        if asyncio.iscoroutine(result):
            await result

    asyncio.run(_run())
    return {"engine": "edge", "edge_voice": voice, "edge_rate": rate, "edge_pitch": pitch}


def synthesize_line(cfg: dict, line: dict, out_dir: Path) -> dict:
    target = out_dir / line["save_name"]
    engine = line.get("engine", "minimax")
    if engine == "edge":
        info = synthesize_edge(cfg, line, target)
    else:
        info = synthesize_minimax(cfg, line, target)
    info.update({"role": line["role"], "file": line["save_name"], "text": line["text"]})
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
    args = parser.parse_args()

    cfg = load_config(Path(args.config).expanduser().resolve())
    out_name = args.out or cfg.get("output_dir") or "六声线测试_家庭钩子_20261106"
    out_dir = DEFAULT_OUT_ROOT / out_name
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = out_dir / "_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    scenes = cfg.get("scenes") or []
    if not scenes:
        raise SystemExit("配置里没有 scenes")

    # 选定要合成的台词
    selected: list[tuple[dict, dict]] = []
    for scene in scenes:
        for line in scene.get("lines", []):
            if args.role and line["role"] != args.role:
                continue
            selected.append((scene, line))

    if not selected:
        raise SystemExit(f"没有匹配到角色：{args.role}")

    ffmpeg = __import__("imageio_ffmpeg").get_ffmpeg_exe()
    report_lines = []
    wav_paths: dict[str, Path] = {}
    duration_by_name: dict[str, int] = {}

    for scene, line in selected:
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
        info = synthesize_line(cfg, line, out_dir)
        wav_path = work_dir / (Path(line["save_name"]).stem + ".wav")
        run([ffmpeg, "-hide_banner", "-y", "-i", str(out_dir / line["save_name"]), "-ac", "1", "-ar", "44100", str(wav_path)])
        wav_paths[line["save_name"]] = wav_path
        duration_by_name[line["save_name"]] = probe_duration_ms(ffmpeg, wav_path)
        info["duration_ms"] = duration_by_name[line["save_name"]]
        info["voice_id"] = line.get("voice_id") or line.get("edge_voice")
        info["emotion"] = line.get("emotion")
        info["speed"] = line.get("speed")
        info["pitch"] = line.get("pitch")
        report_lines.append(info)
        print(f"[合成] {line['role']}: {line['save_name']} "
              f"({duration_by_name[line['save_name']]}ms, {info.get('usage_characters', '-')} 字符)")

    if args.no_mix:
        return

    # 场景拼接
    scene_reports = []
    for scene in scenes:
        names = [ln["save_name"] for ln in scene.get("lines", [])]
        if any(n not in wav_paths for n in names):
            continue
        offsets = [0]
        for pos in range(1, len(names)):
            gap = GAP_QUICK_REPLY_MS if pos == len(names) - 1 else GAP_WITHIN_SCENE_MS
            offsets.append(offsets[-1] + duration_by_name[names[pos - 1]] + gap)
        scene_path = out_dir / scene["name"]
        build_mix(ffmpeg, [wav_paths[n] for n in names], offsets, scene_path, as_mp3=True)
        scene_reports.append({"file": scene["name"], "duration_ms": probe_duration_ms(ffmpeg, scene_path)})
        print(f"[场景] {scene['name']} ({scene_reports[-1]['duration_ms']}ms)")

    # 整条母版
    all_names = [ln["save_name"] for sc in scenes for ln in sc.get("lines", [])]
    if all(n in wav_paths for n in all_names):
        offsets = [0]
        for pos in range(1, len(all_names)):
            if pos % 2 == 1:
                gap = GAP_QUICK_REPLY_MS if pos == len(all_names) - 1 else GAP_WITHIN_SCENE_MS
            else:
                gap = GAP_SCENE_MS
            offsets.append(offsets[-1] + duration_by_name[all_names[pos - 1]] + gap)
        total = cfg.get("total_seconds", 15)
        stem = out_dir / cfg.get("full_name", "完整_15秒_六声线对白_纯对白版")
        build_mix(ffmpeg, [wav_paths[n] for n in all_names], offsets, stem.with_suffix(".wav"), as_mp3=False, pad_to=total)
        build_mix(ffmpeg, [wav_paths[n] for n in all_names], offsets, stem.with_suffix(".mp3"), as_mp3=True, pad_to=total)
        print(f"[母版] {stem.name}.wav / .mp3 ({probe_duration_ms(ffmpeg, stem.with_suffix('.wav'))}ms)")

        timeline = []
        for idx, name in enumerate(all_names):
            role = next(ln["role"] for sc in scenes for ln in sc.get("lines", []) if ln["save_name"] == name)
            text = next(ln["text"] for sc in scenes for ln in sc.get("lines", []) if ln["save_name"] == name)
            timeline.append({"role": role, "line": text, "start_ms": offsets[idx], "end_ms": offsets[idx] + duration_by_name[name]})

        summary = {
            "output_dir": str(out_dir.relative_to(ROOT)),
            "lines": report_lines,
            "scenes": scene_reports,
            "timeline": timeline,
        }
        (out_dir / "试听报告.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
