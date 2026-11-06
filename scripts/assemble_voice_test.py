#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多角色配音拼装工具（多声线测试 / 短视频钩子对白）
=============================================================
用途：
1. 按清单下载多角色 TTS 音频（同一句话的多个声线版本），保存为可试听文件。
2. 按“场景内停顿 + 场景间硬切”拼接为场景音频与整条对白音频。
3. 输出试听报告 JSON（每个角色的音色参数、时长、时间轴），供后续剪辑对齐。

特点：
1. 路径全部由脚本自身位置推导，不写死盘符与用户名。
2. 下载地址不写入仓库：清单由 --meta 传入，文件放在仓库外或被 .gitignore 忽略的位置。
3. ffmpeg 走 imageio-ffmpeg 自带二进制，无需系统安装。

用法：
    python scripts/assemble_voice_test.py --meta <清单.json> --out <输出目录名>

清单 JSON 结构：
{
  "items": [
    {
      "id": "s1_01_boy",              # 内部标识
      "role": "男童",                # 角色名
      "line": "爷爷！我嘴冒烟了！",   # 台词
      "voice_id": "clever_boy",      # 音色 ID（决定说话人）
      "emotion": "surprised",        # 情绪
      "speed": 1.08,                # 语速
      "pitch": 2,                   # 音调
      "url": "https://...",          # 音频下载地址（临时签名链接，不入库）
      "save_name": "01_男童.mp3",     # 落地文件名
      "version": "v1",              # 版本号：变了才会重新下载，旧版自动留档
      "backup_name": "备选_01_男童.mp3"
    }
  ],
  "scenes": [                       # 可选：按场景成对分组
    {"name": "场景1_男童与爷爷_0-5s.mp3", "items": ["s1_01_boy", "s1_02_grandpa"]}
  ],
  "total_seconds": 15               # 可选：整条音频对齐的秒数
}
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_ROOT = ROOT / "01_配音与音色库"

GAP_WITHIN_SCENE_MS = 350   # 同一场景内两人接话的间隔
GAP_SCENE_MS = 100          # 场景之间的硬切短停顿
GAP_QUICK_REPLY_MS = 220    # 抢话感：接话更快


def get_ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd: list[str], check: bool = True) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and proc.returncode != 0:
        raise RuntimeError(f"命令失败: {' '.join(cmd)}\n{proc.stderr[-2000:]}")
    return proc.stdout + proc.stderr


def probe_duration_ms(ffmpeg: str, path: Path) -> int:
    # 单独探测输入时 ffmpeg 以非零码退出，属正常行为
    out = run([ffmpeg, "-hide_banner", "-i", str(path)], check=False)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", out)
    if not match:
        raise RuntimeError(f"无法解析时长: {path}")
    hours, minutes, seconds = match.groups()
    return round((int(hours) * 3600 + int(minutes) * 60 + float(seconds)) * 1000)


def build_mix(
    ffmpeg: str,
    inputs: list[Path],
    offsets_ms: list[int],
    out_path: Path,
    as_mp3: bool = True,
    pad_to: float | None = None,
) -> None:
    cmd = [ffmpeg, "-hide_banner", "-y"]
    for src in inputs:
        cmd += ["-i", str(src)]
    parts, labels = [], []
    for idx, offset in enumerate(offsets_ms):
        parts.append(f"[{idx}:a]adelay={offset}|{offset},aresample=44100[a{idx}]")
        labels.append(f"[a{idx}]")
    graph = ";".join(parts) + ";" + "".join(labels) + f"amix=inputs={len(inputs)}:duration=longest:normalize=0[mix0]"
    if pad_to:
        graph += f";[mix0]apad,atrim=0:{pad_to}[mix]"
    else:
        graph += ";[mix0]anull[mix]"
    cmd += ["-filter_complex", graph, "-map", "[mix]", "-c:a", "libmp3lame" if as_mp3 else "pcm_s16le"]
    if as_mp3:
        cmd += ["-b:a", "192k"]
    cmd += [str(out_path)]
    run(cmd)


def download(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        target.write_bytes(response.read())


def resolve_source(item: dict, root: Path) -> Path | None:
    """取音频来源：local_path 指向本地文件，url 指向可下载地址。"""
    if item.get("local_path"):
        source = Path(item["local_path"])
        if not source.is_absolute():
            source = root / source
        return source if source.exists() else None
    return None


def fetch_item(item: dict, target: Path, root: Path) -> None:
    source = resolve_source(item, root)
    if source is not None:
        shutil.copyfile(source, target)
        return
    download(item["url"], target)


def main() -> None:
    parser = argparse.ArgumentParser(description="多角色配音拼装工具")
    parser.add_argument("--meta", required=True, help="清单 JSON 路径（含下载链接，不入库）")
    parser.add_argument("--out", required=True, help="输出目录名，相对 01_配音与音色库")
    parser.add_argument("--total-seconds", type=float, default=None, help="整条音频对齐秒数")
    args = parser.parse_args()

    ffmpeg = get_ffmpeg()
    meta_path = Path(args.meta).expanduser().resolve()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    items = meta["items"]

    out_dir = DEFAULT_OUT_ROOT / args.out
    work_dir = out_dir / "_work"
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    state_path = work_dir / "installed_versions.json"
    installed = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}

    wavs: list[Path] = []
    durations: list[int] = []
    by_id: dict[str, int] = {}
    report = []

    for index, item in enumerate(items):
        by_id[item["id"]] = index
        mp3_path = out_dir / item["save_name"]
        version = item.get("version", "v1")
        current = installed.get(item["save_name"]) == version and mp3_path.exists()
        if not current and mp3_path.exists() and item.get("backup_name"):
            # 旧版本留档，避免覆盖后无法回退
            backup_dir = out_dir / "_备选_历史版本"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path = backup_dir / item["backup_name"]
            if backup_path.exists():
                backup_path.unlink()
            mp3_path.replace(backup_path)
        if not mp3_path.exists() or mp3_path.stat().st_size < 1024:
            fetch_item(item, mp3_path, ROOT)
        installed[item["save_name"]] = version

        wav_path = work_dir / f"{item['id']}.wav"
        run([ffmpeg, "-hide_banner", "-y", "-i", str(mp3_path), "-ac", "1", "-ar", "44100", str(wav_path)])
        wavs.append(wav_path)
        durations.append(probe_duration_ms(ffmpeg, wav_path))
        report.append(
            {
                "role": item["role"],
                "line": item["line"],
                "voice_id": item["voice_id"],
                "emotion": item.get("emotion"),
                "speed": item.get("speed"),
                "pitch": item.get("pitch"),
                "file": item["save_name"],
                "version": version,
                "duration_ms": durations[-1],
            }
        )

    # 备选音色包：只下载归档，不参与拼接，供人工比选
    candidates_dir = out_dir / "_备选_候选音色"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    for candidate in meta.get("candidates", []):
        target = candidates_dir / candidate["file"]
        if target.exists() and target.stat().st_size >= 1024:
            continue
        fetch_item(candidate, target, ROOT)

    scene_reports = []
    for scene in meta.get("scenes", []):
        idxs = [by_id[i] for i in scene["items"]]
        offsets = [0]
        for pos in range(1, len(idxs)):
            gap = GAP_QUICK_REPLY_MS if pos == len(idxs) - 1 else GAP_WITHIN_SCENE_MS
            offsets.append(offsets[-1] + durations[idxs[pos - 1]] + gap)
        out_path = out_dir / scene["name"]
        build_mix(ffmpeg, [wavs[i] for i in idxs], offsets, out_path, as_mp3=True)
        scene_reports.append({"file": scene["name"], "duration_ms": probe_duration_ms(ffmpeg, out_path)})

    offsets = [0]
    for pos in range(1, len(items)):
        if pos in (1, 3, 5):
            gap = GAP_QUICK_REPLY_MS if pos == 5 else GAP_WITHIN_SCENE_MS
        else:
            gap = GAP_SCENE_MS
        offsets.append(offsets[-1] + durations[pos - 1] + gap)

    total_seconds = args.total_seconds if args.total_seconds is not None else meta.get("total_seconds")
    full_stem = out_dir / (meta.get("full_name") or "完整对白_拼接版")
    build_mix(ffmpeg, wavs, offsets, full_stem.with_suffix(".wav"), as_mp3=False, pad_to=total_seconds)
    build_mix(ffmpeg, wavs, offsets, full_stem.with_suffix(".mp3"), as_mp3=True, pad_to=total_seconds)

    timeline = []
    for idx, offset in enumerate(offsets):
        timeline.append(
            {
                "role": items[idx]["role"],
                "line": items[idx]["line"],
                "start_ms": offset,
                "end_ms": offset + durations[idx],
            }
        )

    summary = {
        "output_dir": str(out_dir.relative_to(ROOT)),
        "lines": report,
        "scenes": scene_reports,
        "full_wav": {"file": full_stem.with_suffix(".wav").name, "duration_ms": probe_duration_ms(ffmpeg, full_stem.with_suffix(".wav"))},
        "full_mp3": {"file": full_stem.with_suffix(".mp3").name, "duration_ms": probe_duration_ms(ffmpeg, full_stem.with_suffix(".mp3"))},
        "timeline": timeline,
    }
    (out_dir / "试听报告.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    state_path.write_text(json.dumps(installed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
