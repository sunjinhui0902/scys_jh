#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
候选音色包客观体检
==================
给每个候选干声出一组可复算的客观指标，用来回答两件事：

1. 素材本身是否合格 —— 能不能解码、有没有削波、有没有静音段、响度是否一致；
2. 候选之间是否真的不一样 —— 基频、语速、音色指纹是否重合。

指标说明：
- f0_hz      自相关估计的中位基频（浊音帧），是「年龄感 / 性别特征」最直接的物理线索；
- cps        每秒字数。同一条对照句台词完全相同，所以 cps 直接等于语速差异；
- rms_dbfs   整体响度，用来发现"某条特别小/特别大"的不平衡；
- clip_ratio 削波样本占比，正常应接近 0；
- sil_ratio 静音占比，过高说明断句或尾音有问题。

基频只能说明物理特征，不等于听感好坏；"像不像 65-75 岁的爷爷"仍要人耳判断。

用法：
    python scripts/voice_candidate_audit.py --config config/voice_api/config_候选对比.yaml
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_ROOT = ROOT / "01_配音与音色库"
SR = 16000


def ffmpeg_exe() -> str:
    return __import__("imageio_ffmpeg").get_ffmpeg_exe()


def decode_mono(path: Path) -> np.ndarray:
    """解码为 16kHz 单声道 float32。"""
    exe = ffmpeg_exe()
    cmd = [exe, "-hide_banner", "-loglevel", "error", "-i", str(path),
           "-f", "s16le", "-acodec", "pcm_s16le", "-ac", "1", "-ar", str(SR), "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0


def estimate_f0(sig: np.ndarray) -> float | None:
    """自相关基频估计：只在能量靠前的浊音帧上求中位数。"""
    if sig.size < SR // 20:
        return None
    win, hop = 1024, 512
    frames = []
    for start in range(0, sig.size - win, hop):
        frames.append(sig[start:start + win])
    if not frames:
        return None
    stack = np.stack(frames)
    energy = np.sqrt((stack ** 2).mean(axis=1))
    if not np.any(energy > 0):
        return None
    thresh = max(np.percentile(energy, 30), energy.max() * 0.05)
    voiced = stack[energy >= thresh]
    if voiced.shape[0] < 3:
        return None
    win_rms = np.sqrt((voiced ** 2).mean(axis=1))
    keep = voiced[win_rms >= win_rms.max() * 0.25]
    if keep.shape[0] < 3:
        return None
    voiced = keep
    f0s = []
    for frame in voiced:
        frame = frame - frame.mean()
        corr = np.correlate(frame, frame, mode="full")[frame.size - 1:]
        lo, hi = SR // 400, SR // 60          # 400Hz ~ 60Hz
        if hi >= corr.size:
            continue
        seg = corr[lo:hi]
        if seg.max() <= 0:
            continue
        lag = int(np.argmax(seg)) + lo
        if corr[lag] / max(corr[0], 1e-9) < 0.25:
            continue
        f0s.append(SR / lag)
    if len(f0s) < 3:
        return None
    return float(np.median(f0s))


def analyse(path: Path) -> dict:
    sig = decode_mono(path)
    if sig.size == 0:
        return {"ok": False, "reason": "解码为空"}
    peak = float(np.max(np.abs(sig)))
    rms = float(np.sqrt((sig ** 2).mean()))
    win = 400
    frames = [sig[i:i + win] for i in range(0, sig.size - win, win)] or [sig]
    fr_rms = np.array([float(np.sqrt((f ** 2).mean())) for f in frames])
    loud_thresh = max(fr_rms.max() * 0.05, 1e-4)
    sil_ratio = float((fr_rms < loud_thresh).mean())
    clip_ratio = float((np.abs(sig) >= 0.995).mean())
    f0 = estimate_f0(sig)
    return {
        "ok": True,
        "duration_ms": int(sig.size / SR * 1000),
        "peak_dbfs": round(20 * np.log10(max(peak, 1e-6)), 2),
        "rms_dbfs": round(20 * np.log10(max(rms, 1e-6)), 2),
        "clip_ratio": round(clip_ratio, 5),
        "sil_ratio": round(sil_ratio, 3),
        "f0_hz": round(f0, 1) if f0 else None,
    }


def fingerprint(sig: np.ndarray, bins: int = 24) -> tuple:
    """简易音色指纹：对数频带能量分布，用来识别重复渲染。"""
    if sig.size < 2048:
        return tuple([0.0] * bins)
    spec = np.abs(np.fft.rfft(sig[: min(sig.size, SR * 20)])) ** 2
    freqs = np.fft.rfftfreq(min(sig.size, SR * 20), 1 / SR)
    edges = np.geomspace(80, 8000, bins + 1)
    out = []
    for i in range(bins):
        band = spec[(freqs >= edges[i]) & (freqs < edges[i + 1])]
        out.append(float(np.log10(band.sum() + 1e-9)))
    v = np.array(out)
    v = v - v.mean()
    norm = np.linalg.norm(v) or 1.0
    return tuple((v / norm).round(4))


def main() -> None:
    ap = argparse.ArgumentParser(description="候选音色包客观体检")
    ap.add_argument("--config", required=True)
    ap.add_argument("--out-dir", default=None, help="输出目录名（相对 01_配音与音色库）")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
    roles = cfg.get("roles") or {}
    scenes = cfg.get("scenes") or []
    folder = DEFAULT_OUT_ROOT / (args.out_dir or cfg.get("output_dir") or "")
    folder.mkdir(parents=True, exist_ok=True)

    rows = []
    md5_map: dict[str, list[str]] = {}
    for scene in scenes:
        scene_name = scene.get("name", "")
        for line in scene.get("lines", []):
            path = folder / line["save_name"]
            base = dict(roles.get(line.get("role")) or {})
            base.update({k: v for k, v in line.items() if v is not None})
            engine = base.get("engine", "minimax")
            voice = (base.get("edge_voice") if engine == "edge"
                     else base.get("voice_id") or base.get("edge_voice"))
            item = {
                "scene": scene_name,
                "kind": "对照" if "对照" in scene_name else "情景",
                "role": base.get("name") or line.get("role"),
                "voice": voice,
                "engine": engine,
                "emotion": line.get("emotion") or "-",
                "speed": base.get("speed", "-"),
                "pitch": base.get("pitch", "-"),
                "edge_rate": line.get("edge_rate", "-"),
                "edge_pitch": line.get("edge_pitch", "-"),
                "text": line.get("text", ""),
                "file": line["save_name"],
            }
            if not path.exists():
                item["status"] = "缺失"
                rows.append(item)
                continue
            data = path.read_bytes()
            md5_map.setdefault(hashlib.md5(data).hexdigest(), []).append(line["save_name"])
            try:
                sig = decode_mono(path)
                item.update(analyse(path))
                item["status"] = "正常" if item.get("clip_ratio", 0) < 0.001 else "削波"
            except Exception as exc:
                item["status"] = f"解码失败:{exc}"
            text_len = len(re.sub(r"[，。！？…、\s]", "", item["text"]))
            dur = (item.get("duration_ms") or 0) / 1000
            item["chars"] = text_len
            item["cps"] = round(text_len / dur, 2) if dur else None
            rows.append(item)

    # 重复指纹（只比较同一场景内，避免跨角色误判）
    dup_groups = [v for v in md5_map.values() if len(v) > 1]

    # 音色指纹两两比对：找出高度相似的候选（同场景内）
    sims = []
    by_scene: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("status") == "正常":
            by_scene.setdefault(r["scene"], []).append(r)
    for scene, items in by_scene.items():
        sigs = {}
        for it in items:
            sigs[it["file"]] = fingerprint(decode_mono(folder / it["file"]))
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = sigs[items[i]["file"]], sigs[items[j]["file"]]
                sim = float(np.dot(np.array(a), np.array(b)))
                if sim > 0.97:
                    sims.append({"scene": scene, "a": items[i]["file"], "b": items[j]["file"],
                                 "fingerprint_cosine": round(sim, 4)})

    summary = {
        "folder": str(folder.relative_to(ROOT)),
        "config": Path(args.config).name,
        "candidates": len(rows),
        "normal": sum(1 for r in rows if r.get("status") == "正常"),
        "clipping": sum(1 for r in rows if r.get("status") == "削波"),
        "missing": sum(1 for r in rows if r.get("status") == "缺失"),
        "decode_failed": sum(1 for r in rows if str(r.get("status", "")).startswith("解码失败")),
        "identical_files": dup_groups,
        "similar_pairs": sims,
        "rows": rows,
    }
    (folder / "候选音色体检.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    md = ["# 候选音色客观体检", "",
          f"目录：`{folder.relative_to(ROOT)}` ｜ 候选 {len(rows)} 条 ｜ 正常 {summary['normal']} ｜ "
          f"削波 {summary['clipping']} ｜ 缺失 {summary['missing']} ｜ 解码失败 {summary['decode_failed']}", "",
          "> f0_hz 是自相关估计的中位基频，cps 是每秒字数（同一对照句台词相同，cps 即语速差）。",
          "> 这些是物理特征，不等于听感好坏；像不像 65-75 岁的老人，仍要人耳判断。", ""]
    for role in ["boy", "girl", "dad", "mom", "grandpa", "grandma"]:
        label = (roles.get(role) or {}).get("name", role)
        md.append(f"## {label}")
        md.append("| # | 场景 | 音色 | 引擎 | f0_hz | cps | 响度dBFS | 削波 | 静音 | 状态 |")
        md.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        idx = 0
        for r in rows:
            if r["role"] != label:
                continue
            idx += 1
            md.append(f"| {idx} | {r['kind']} | `{r['voice']}` | {r['engine']} | "
                      f"{r.get('f0_hz', '-')} | {r.get('cps', '-')} | {r.get('rms_dbfs', '-')} | "
                      f"{r.get('clip_ratio', '-')} | {r.get('sil_ratio', '-')} | {r['status']} |")
        md.append("")
    if dup_groups:
        md.append("## 字节级重复文件")
        for g in dup_groups:
            md.append("- " + "、".join(f"`{x}`" for x in g))
        md.append("")
    if sims:
        md.append("## 音色指纹高度相似的候选（>0.97）")
        for s in sims:
            md.append(f"- `{s['a']}` ↔ `{s['b']}`（{s['fingerprint_cosine']}）")
        md.append("")
    else:
        md.append("## 音色指纹重复检查")
        md.append("同一场景内没有音色指纹高度相似（>0.97）的候选对，说明每个候选确实是不同音色。")
        md.append("")
    (folder / "候选音色体检.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in
                      ["candidates", "normal", "clipping", "missing", "decode_failed"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
