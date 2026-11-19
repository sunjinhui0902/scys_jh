# -*- coding: utf-8 -*-
"""授权 BGM 候选抓取 + 上线校验。

解决的问题：竞品拆出来的 13 条伴奏全部有版权（TSFH / 久石让 / 周杰伦 / 大鱼海棠…），
不能进成片；剪映「商用音乐」的授权范围只有「剪映、抖音」两平台，**不含视频号**。
本脚本从**明确可商用且不限平台**的免费通道抓候选，下载后做客观校验，
产出「可以直接替换进成片」的音频与授权凭证存档。

通道（均免注册、免署名、不限平台、允许商业用途）：

| source   | 站点                        | 许可                          | 直链形态                        |
|----------|-----------------------------|-------------------------------|---------------------------------|
| mixkit   | mixkit.co/free-stock-music  | Mixkit Free License           | assets.mixkit.co/music/<id>/<id>.mp3 |
| freepd   | en.freepd.cn/music/<cat>    | CC0 / 公共领域                | en.freepd.cn/api/music/<hex>    |

注意：**freepd.com 主站已关闭**（返回 “FreePD.com - Site Closed”），
必须走 freepd.cn / en.freepd.cn。

子命令：
    list   --source mixkit --channel traditional      # 列候选（不下载）
    fetch  --source mixkit --channel traditional      # 下载 + 校验 + 存档凭证
    check  <文件...>                                   # 只校验本地音频

所有路径从本文件位置推导，禁止写死盘符或用户名。
"""
import argparse
import hashlib
import html as html_mod
import json
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ROOT = common.ROOT
AUDIT_DIR = Path(__file__).resolve().parent
# 授权候选资产区（音频不入 Git，JSON 入库）
ASSET_DIR = ROOT / "02_公共资产库" / "授权BGM候选_20261119"
CRED_DIR = ASSET_DIR / "授权凭证"
MANIFEST = ASSET_DIR / "授权BGM候选清单.json"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

MIXKIT_BASE = "https://mixkit.co"
FREEPD_BASE = "https://en.freepd.cn"

# 许可快照：存档进仓库 JSON，标���过期风险与核验日期
LICENSE_INFO = {
    "mixkit": {
        "license_name": "Mixkit Free License",
        "attribution": False,
        "commercial_use": True,
        "platform_limit": None,
        "registration": False,
        "note": "Envato 旗下。免费免署名免注册，允许商业用途。"
                "逐条资产可能有 Restricted License 变体，且页面有 “Item from Envato Elements” "
                "付费推广位——那些不是免费素材，不要点。不得作为独立音乐文件再分发。",
        "verified_on": "2026-11-19",
    },
    "freepd": {
        "license_name": "CC0 / Public Domain",
        "attribution": False,
        "commercial_use": True,
        "platform_limit": None,
        "registration": False,
        "note": "公有领域 / CC0，免署名、可商用、不限平台、不限注册。"
                "注意 freepd.com 主站已关闭，实际可用站点为 freepd.cn / en.freepd.cn。",
        "verified_on": "2026-11-19",
    },
}


# ------------------------------------------------------------------ 网络
def http_get(url, timeout=60, retries=3):
    """带 UA 的 GET，返回 bytes。失败重试。"""
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError("GET failed: %s :: %s" % (url, last))


def _text(url, timeout=60):
    return http_get(url, timeout=timeout).decode("utf-8", errors="replace")


# ------------------------------------------------------------------ 列表解析
def list_mixkit(channel, page_limit=1):
    """解析 Mixkit 分类页 → [{id,title,author,mp3_url,page_url,license}]"""
    out = []
    for p in range(1, page_limit + 1):
        url = "%s/free-stock-music/%s/" % (MIXKIT_BASE, channel)
        if p > 1:
            url = "%s/free-stock-music/%s/?page=%d" % (MIXKIT_BASE, channel, p)
        html = _text(url)
        blocks = re.split(r'class="item-grid__item"', html)[1:]
        if not blocks:
            break
        for blk in blocks:
            m = re.search(r'data-audio-player-preview-url-value="([^"]+\.mp3)"', blk)
            if not m:
                continue
            mp3 = m.group(1)
            mid = re.search(r"data-audio-player-item-id-value=\"(\d+)\"", blk)
            t = re.search(r'item-grid-card__title">\s*(.*?)\s*</h2>', blk, re.S)
            a = re.search(r'item-grid-music-preview__author">\s*by\s*(.*?)\s*</p>', blk, re.S)
            out.append({
                "id": mid.group(1) if mid else "",
                "title": html_mod.unescape(re.sub(r"\s+", " ", t.group(1)).strip()) if t else "",
                "author": html_mod.unescape(re.sub(r"\s+", " ", a.group(1)).strip()) if a else "",
                "mp3_url": mp3,
                "page_url": "%s/free-stock-music/%s-%s/" % (MIXKIT_BASE, channel, mid.group(1)) if mid else url,
                "channel": channel,
                "source": "mixkit",
            })
    return out


def list_freepd(category):
    """解析 en.freepd.cn 分类页 → [{title,mp3_url,page_url}]"""
    url = "%s/music/%s" % (FREEPD_BASE, category)
    html = _text(url)
    pat = r'href="(/api/music/[0-9a-f]+)"\s+download="([^"]+)"[^>]*>([^<]+)</a>'
    out = []
    seen = set()
    for m in re.finditer(pat, html):
        href, dl, label = m.group(1), m.group(2), re.sub(r"\s+", " ", m.group(3)).strip()
        if href in seen:
            continue
        seen.add(href)
        out.append({
            "id": href.rsplit("/", 1)[-1],
            "title": label or dl,
            "author": "FreePD (public domain)",
            "mp3_url": FREEPD_BASE + href,
            "page_url": url,
            "channel": category,
            "source": "freepd",
        })
    return out


# ------------------------------------------------------------------ 音频校验
def volumedetect(path):
    """ffmpeg volumedetect → {'mean_db': float, 'peak_db': float}"""
    ff = common.find_ffmpeg()
    p = subprocess.run(
        [ff, "-hide_banner", "-nostats", "-i", str(path), "-af", "volumedetect",
         "-f", "null", "-"], capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    err = p.stderr or ""
    mean = peak = None
    m = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB", err)
    if m:
        mean = float(m.group(1))
    m = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?) dB", err)
    if m:
        peak = float(m.group(1))
    return {"mean_db": mean, "peak_db": peak}


_SIVAD = None


def _get_sivad():
    """Silero VAD 模型只加载一次（否则每条曲目都要重新载入，批量抓取会慢到不可用）。"""
    global _SIVAD
    if _SIVAD is None:
        from silero_vad import load_silero_vad
        _SIVAD = load_silero_vad()
    return _SIVAD


def speech_scan(path, max_sec=180.0):
    """Silero VAD 扫描：估计「疑似人声」占比。

    这是**辅助判据**：纯器乐也可能被 VAD 误触发（打击乐、铜管、笛子），
    演唱/吟唱也可能**漏判**——实测本批 21 条候选里 3 条含无词吟唱/合唱被 VAD 判成「未检出明显人声」。
    判定阈值取保守值，最终仍须多模态听感复核。
    """
    try:
        import numpy as np
        import torch
        import librosa
        from silero_vad import get_speech_timestamps
    except Exception as e:  # noqa: BLE001
        return {"available": False, "reason": str(e)}
    try:
        wav, sr = librosa.load(str(path), sr=16000, mono=True)
        if len(wav) > max_sec * sr:
            wav = wav[:int(max_sec * sr)]
        sivad = _get_sivad()
        ts = get_speech_timestamps(torch.from_numpy(wav.astype(np.float32)), sivad,
                                  sampling_rate=16000,
                                  min_speech_duration_ms=400,
                                  speech_pad_ms=120)
        dur = len(wav) / sr
        voiced = sum((t["end"] - t["start"]) for t in ts) / sr if ts else 0.0
        longest = max(((t["end"] - t["start"]) / sr for t in ts), default=0.0)
        ratio = voiced / dur if dur > 0 else 0.0
        if ratio >= 0.02 or longest >= 1.5:
            verdict = "疑似含人声"
        elif longest >= 0.6:
            verdict = "存疑"
        else:
            verdict = "未检出明显人声"
        return {"available": True, "speech_ratio": round(ratio, 4),
                "longest_segment_sec": round(longest, 2),
                "segments": len(ts), "scanned_sec": round(dur, 1),
                "verdict": verdict}
    except Exception as e:  # noqa: BLE001
        return {"available": False, "reason": str(e)}


def to_wav(path, out_wav):
    ff = common.find_ffmpeg()
    subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(path),
                    "-ac", "1", "-ar", "22050", "-c:a", "pcm_s16le", str(out_wav)],
                   check=True)


def normalize_to_mean(src, dst, target_mean_db, peak_cap_db=-3.0):
    """按实测 mean 差值做恒定增益归一到目标电平。

    peak_cap_db：归一后峰值上限（dBFS，默认 -3）。超过上限时串一级软限幅
    （alimiter，level=false 不做自动电平提升），避免与口播叠加后削顶。
    """
    ff = common.find_ffmpeg()
    v = volumedetect(src)
    if v["mean_db"] is None:
        raise RuntimeError("volumedetect failed for %s" % src)
    delta = target_mean_db - v["mean_db"]
    chain = "volume=%.3fdB" % delta
    if peak_cap_db is not None:
        chain += ",alimiter=limit=%.6f:attack=5:release=50:level=false" % (10 ** (peak_cap_db / 20.0))
    subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                    "-af", chain, "-c:a", "libmp3lame", "-b:a", "192k",
                    str(dst)], check=True)
    return {"delta_db": round(delta, 2), "src_mean_db": v["mean_db"],
            "target_mean_db": target_mean_db, "peak_cap_db": peak_cap_db}


# ------------------------------------------------------------------ 主流程
def cmd_list(args):
    items = (list_mixkit(args.channel) if args.source == "mixkit"
             else list_freepd(args.channel))
    items = items[:args.limit] if args.limit else items
    print("[%s/%s] 共 %d 条" % (args.source, args.channel, len(items)))
    for i, it in enumerate(items, 1):
        print("%2d. %-42s | %-22s | %s" % (i, it["title"][:42], it["author"][:22], it["mp3_url"]))
    return items


def cmd_fetch(args):
    items = (list_mixkit(args.channel) if args.source == "mixkit"
             else list_freepd(args.channel))
    if args.limit:
        items = items[:args.limit]
    out_dir = Path(args.out_dir) if args.out_dir else (ASSET_DIR / args.source / args.channel)
    out_dir.mkdir(parents=True, exist_ok=True)
    CRED_DIR.mkdir(parents=True, exist_ok=True)

    records = []
    for it in items:
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", it["title"]).strip()[:60] or ("track_" + it["id"])
        dst = out_dir / (safe + ".mp3")
        try:
            if not dst.exists() or dst.stat().st_size < 1024:
                blob = http_get(it["mp3_url"], timeout=120)
                dst.write_bytes(blob)
        except Exception as e:  # noqa: BLE001
            print("  ! 下载失败 %s :: %s" % (it["title"], e))
            continue

        vol = volumedetect(dst)
        vad = speech_scan(dst, max_sec=60.0)
        dur, _ = common.ffmpeg_probe(dst)
        rec = {
            "title": it["title"], "author": it["author"],
            "channel": it["channel"], "source": it["source"],
            "file": dst.name, "bytes": dst.stat().st_size,
            "sha256": hashlib.sha256(dst.read_bytes()).hexdigest()[:16],
            "duration_sec": round(dur, 2),
            "mean_db": vol["mean_db"], "peak_db": vol["peak_db"],
            "speech_scan": vad,
            "mp3_url": it["mp3_url"], "page_url": it["page_url"],
            "license": LICENSE_INFO[it["source"]],
            "downloaded_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        }
        records.append(rec)
        print("  + %-40s %6.1fs mean=%s peak=%s %s" % (
            it["title"][:40], dur, vol["mean_db"], vol["peak_db"], vad.get("verdict", "-")))

    payload = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "source": args.source, "channel": args.channel,
        "out_dir": str(out_dir.relative_to(ROOT)) if out_dir.is_relative_to(ROOT) else str(out_dir),
        "count": len(records), "tracks": records,
    }
    # 每个分类一份明细（放在该分类目录内），另聚合一份总表
    ch_manifest = out_dir / "候选清单.json"
    ch_manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    # 总表从各分类明细重新汇总（避免并发 fetch 互相覆盖）
    agg = {}
    for p in sorted(ASSET_DIR.glob("*/*/候选清单.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        agg["%s/%s" % (d.get("source"), d.get("channel"))] = d
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(agg, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(MANIFEST)
    print("清单 → %s（%d 条）" % (ch_manifest, len(records)))
    print("总表 → %s（%d 个分类）" % (MANIFEST, len(agg)))
    return records


def cmd_check(args):
    rows = []
    for f in args.files:
        p = Path(f)
        vol = volumedetect(p)
        vad = speech_scan(p)
        dur, _ = common.ffmpeg_probe(p)
        rows.append({"file": p.name, "duration_sec": round(dur, 2),
                     "mean_db": vol["mean_db"], "peak_db": vol["peak_db"],
                     "speech_scan": vad})
        print("%-44s %6.1fs mean=%s peak=%s %s" % (
            p.name, dur, vol["mean_db"], vol["peak_db"], vad.get("verdict", "-")))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
        print("→ %s" % args.json_out)
    return rows


def cmd_normalize(args):
    """把候选按实测 mean 差值归一到目标电平，输出可直接替换的副本。

    目标电平的含义：**混音后**（管线 BGM 增益 0.2239 = -13dB）与人声的相对关系。
    例如 -23dB → 混音内 -36dB，比人声（-20.8dB）低约 15dB，是"托底不抢戏"的位置。
    """
    out_dir = Path(args.out_dir) if args.out_dir else (ASSET_DIR / "已归一")
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for f in args.files:
        src = Path(f)
        dst = out_dir / src.name
        info = normalize_to_mean(src, dst, args.target_mean_db, args.peak_cap)
        vol = volumedetect(dst)
        rows.append({"src": src.name, "out": dst.name, **info,
                     "out_mean_db": vol["mean_db"], "out_peak_db": vol["peak_db"],
                     "bytes": dst.stat().st_size})
        print("%-44s %+.2f dB  →  mean=%s peak=%s" % (
            src.name, info["delta_db"], vol["mean_db"], vol["peak_db"]))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
        print("→ %s" % args.json_out)
    return rows


def main():
    ap = argparse.ArgumentParser(description="授权 BGM 候选抓取与上线校验")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list", help="列出候选（不下载）")
    pl.add_argument("--source", choices=["mixkit", "freepd"], required=True)
    pl.add_argument("--channel", required=True)
    pl.add_argument("--limit", type=int, default=0)

    pf = sub.add_parser("fetch", help="下载候选并校验")
    pf.add_argument("--source", choices=["mixkit", "freepd"], required=True)
    pf.add_argument("--channel", required=True)
    pf.add_argument("--limit", type=int, default=0)
    pf.add_argument("--out-dir", default="")

    pn = sub.add_parser("normalize", help="按目标电平归一，输出可直接替换的副本")
    pn.add_argument("files", nargs="+")
    pn.add_argument("--target-mean-db", type=float, default=-23.0)
    pn.add_argument("--peak-cap", type=float, default=-3.0,
                    help="归一后峰值上限 dBFS；传 0 表示不限幅")
    pn.add_argument("--out-dir", default="")
    pn.add_argument("--json-out", default="")

    pc = sub.add_parser("check", help="校验本地音频")
    pc.add_argument("files", nargs="+")
    pc.add_argument("--json-out", default="")

    args = ap.parse_args()
    if args.cmd == "list":
        cmd_list(args)
    elif args.cmd == "fetch":
        cmd_fetch(args)
    elif args.cmd == "normalize":
        cmd_normalize(args)
    elif args.cmd == "check":
        cmd_check(args)


if __name__ == "__main__":
    main()
