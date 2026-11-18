# -*- coding: utf-8 -*-
"""竞品口播 —— 说话人嵌入判定：谁在共用同一个音色？

用法：
    python scripts/competitor_audio_audit/speaker_cluster.py
    python scripts/competitor_audio_audit/speaker_cluster.py --threshold 0.90

流程：
  1) 对每条竞品口播（02_公共资产库/竞品口播人声_*）算说话人嵌入（Resemblyzer）
  2) 对候选音色池（Edge 公共音色 / MiniMax 系统音色）算嵌入
  3) 用候选池自校准阈值：同一底层说话人的不同参数变体 vs 不同说话人
     （不套用经验阈值，阈值来自本机实测）
  4) 余弦 >= threshold 的连通分量 = 共用同一音色的账号群
  5) 簇质心 vs 全部候选排序 → 判断竞品主流音色是否属于某个可调用的公共音色库

输出：scratch/competitor_audio_audit/speaker_cluster.json
"""
import argparse
import json
import os
import subprocess

import numpy as np

from common import (ASSET_VOICE, SCRATCH, cos, embed_audio, ensure_dirs,
                    find_ffmpeg, get_encoder)

CAND_DIRS = {
    "Edge公共音色": SCRATCH / "voice_candidates",
    "MiniMax系统音色": SCRATCH / "minimax_candidates",
}
CACHE_WAV = SCRATCH / "cand16k"


def to16k(src, tag):
    """转成 16k 单声道 wav 作为分析中间件（避免每次重转）。"""
    ensure_dirs(CACHE_WAV)
    dst = CACHE_WAV / (tag + ".wav")
    if not dst.exists():
        subprocess.run([find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
                        "-t", "45", "-i", str(src), "-ac", "1", "-ar", "16000",
                        "-c:a", "pcm_s16le", str(dst)], check=True)
    return dst


def speaker_tag(name):
    """候选文件名约定：<说话人标签>_<说明>_<voice_id>.mp3，第一段即说话人标签。"""
    return name.split("_")[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice-dir", default=None, help="竞品口播人声目录（默认取仓库内最新批次）")
    ap.add_argument("--threshold", type=float, default=0.90, help="判为同一音色的余弦阈值")
    args = ap.parse_args()

    vdir = args.voice_dir
    if not vdir:
        hits = sorted((ASSET_VOICE.parent).glob("竞品口播人声_*"))
        if not hits:
            raise SystemExit("未找到竞品口播人声目录")
        vdir = str(hits[-1])
    print("竞品口播目录:", vdir)

    ensure_dirs(SCRATCH)
    enc, sivad = get_encoder()

    # ---- 竞品嵌入（带缓存）----
    names, embs = [], []
    for fn in sorted(os.listdir(vdir)):
        if fn.endswith("_16k.wav") and "口播人声" in fn:
            names.append(fn.replace("_口播人声_", "_").replace("_16k.wav", ""))
            embs.append(embed_audio(enc, sivad, os.path.join(vdir, fn)))
    if not names:
        raise SystemExit("目录里没有 *_16k.wav 口播人声文件")
    E = np.stack(embs)
    n = len(names)
    M = np.array([[cos(E[i], E[j]) for j in range(n)] for i in range(n)])
    print(f"竞品嵌入 {n} 条")

    # ---- 候选池嵌入 ----
    cands = {}
    for group, cdir in CAND_DIRS.items():
        if not cdir.exists():
            continue
        for fn in sorted(os.listdir(cdir)):
            if not fn.endswith(".mp3"):
                continue
            src = cdir / fn
            if src.stat().st_size < 10000:
                continue
            cands[fn[:-4]] = {"group": group, "e": embed_audio(enc, sivad, to16k(src, fn[:-4]))}
    print(f"候选嵌入 {len(cands)} 个")

    # ---- 自校准（只用 Edge 池：有同说话人的不同参数变体）----
    same, diff = [], []
    keys = list(cands)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            if cands[keys[i]]["group"] != cands[keys[j]]["group"]:
                continue
            s = cos(cands[keys[i]]["e"], cands[keys[j]]["e"])
            rec = {"a": keys[i], "b": keys[j], "cos": round(s, 4)}
            (same if speaker_tag(keys[i]) == speaker_tag(keys[j]) else diff).append(rec)
    same_cos = [r["cos"] for r in same]
    diff_cos = [r["cos"] for r in diff]
    if same_cos:
        print(f"自校准 同说话人变体 n={len(same_cos)} 范围 {min(same_cos)}~{max(same_cos)}")
    if diff_cos:
        print(f"自校准 不同说话人   n={len(diff_cos)} 范围 {min(diff_cos)}~{max(diff_cos)}")

    # ---- 分簇：余弦 >= threshold 的连通分量 ----
    adj = {i: set() for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            if M[i, j] >= args.threshold:
                adj[i].add(j)
                adj[j].add(i)
    seen, comps = set(), []
    for i in range(n):
        if i in seen:
            continue
        stack, comp = [i], []
        seen.add(i)
        while stack:
            c = stack.pop()
            comp.append(c)
            for x in adj[c]:
                if x not in seen:
                    seen.add(x)
                    stack.append(x)
        comps.append(sorted(comp))
    comps.sort(key=len, reverse=True)
    main_comp = comps[0]
    cent = E[main_comp].mean(axis=0)
    cent = cent / np.linalg.norm(cent)

    rows = []
    for tag, info in cands.items():
        rows.append({"cand": tag, "group": info["group"],
                     "cos_to_cluster_centroid": round(cos(info["e"], cent), 4)})
    rows.sort(key=lambda r: -r["cos_to_cluster_centroid"])

    out = {
        "voice_dir": vdir,
        "threshold": args.threshold,
        "names": names,
        "calibration": {"same_speaker_pairs": same, "diff_speaker_pairs": diff,
                        "same_range": [min(same_cos), max(same_cos)] if same_cos else None,
                        "diff_range": [min(diff_cos), max(diff_cos)] if diff_cos else None},
        "clusters": [[names[i] for i in c] for c in comps],
        "main_cluster": [names[i] for i in main_comp],
        "cos_to_cluster_centroid": {names[i]: round(cos(E[i], cent), 4) for i in range(n)},
        "pair_matrix": [[round(float(v), 4) for v in row] for row in M],
        "candidate_pool": rows,
        "candidate_best": rows[0] if rows else None,
    }
    outfile = SCRATCH / "speaker_cluster.json"
    json.dump(out, open(outfile, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("\n=== 共享音色群（余弦>=%.2f 连通分量）===" % args.threshold)
    for c in comps:
        print("  n=%d: %s" % (len(c), ", ".join(names[i].split("_")[0] for i in c)))
    print("\n=== 各条 vs 主簇质心 ===")
    for k, v in sorted(out["cos_to_cluster_centroid"].items(), key=lambda x: -x[1]):
        print("  %-26s %.4f" % (k[:26], v))
    print("\n=== 候选池 vs 主簇质心 Top8 ===")
    for r in rows[:8]:
        print("  %-34s %-16s %.4f" % (r["cand"][:34], r["group"], r["cos_to_cluster_centroid"]))
    print("\nreport ->", outfile)


if __name__ == "__main__":
    main()
