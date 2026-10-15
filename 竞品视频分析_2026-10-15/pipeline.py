"""V4 Phase 0/1 local inventory and resumable sample processing.

Only reads VIDEO_DIR and records.db. All writes stay under OUTPUT_DIR.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time

VIDEO_DIR = Path(os.environ.get("SCYS_VIDEO_DIR", str(Path(__file__).resolve().parents[1] / "00_对标与采集工具/wx_channel/downloads")))
OUTPUT_DIR = Path(__file__).resolve().parent
EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm"}
FFPROBE = next(OUTPUT_DIR.glob("tools/**/ffprobe.exe"), None)
FFMPEG = next(OUTPUT_DIR.glob("tools/**/ffmpeg.exe"), None)


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def atomic_replace(tmp: Path, path: Path) -> None:
    # A short-lived Windows reader may hold a non-delete-sharing handle.
    for attempt in range(8):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(.05 * (attempt + 1))


def atomic_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    atomic_replace(tmp, path)


def atomic_text(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    atomic_replace(tmp, path)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def probe(path: Path) -> dict:
    if not FFPROBE:
        raise RuntimeError("ffprobe unavailable")
    p = subprocess.run([str(FFPROBE), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    if p.returncode:
        raise RuntimeError(p.stderr.strip()[:500] or "ffprobe failed")
    data = json.loads(p.stdout)
    vs = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
    aud = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    if not vs:
        raise RuntimeError("no video stream")
    v = vs[0]
    return {"duration_s": float(data.get("format", {}).get("duration") or v.get("duration") or 0), "width": v.get("width"), "height": v.get("height"), "video_codec": v.get("codec_name"), "audio_codec": aud[0].get("codec_name") if aud else None, "has_audio": bool(aud), "bit_rate": data.get("format", {}).get("bit_rate")}


def db_rows() -> dict[str, dict]:
    uri = "file:" + str(VIDEO_DIR / "records.db").replace("\\", "/") + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT video_id,title,author,duration,file_size,file_path,format,resolution,status,like_count,comment_count,forward_count,fav_count FROM download_records").fetchall()
    result = {os.path.normcase(os.path.normpath(r["file_path"])): dict(r) for r in rows if r["file_path"]}
    con.close()
    return result


def inventory(resume: bool = True) -> None:
    if not VIDEO_DIR.is_dir():
        raise RuntimeError(f"Missing video directory: {VIDEO_DIR}")
    db = db_rows()
    files = sorted((p for p in VIDEO_DIR.rglob("*") if p.is_file() and p.suffix.lower() in EXTS), key=lambda p: str(p).casefold())
    items = []
    cache_dir = OUTPUT_DIR / "state" / "inventory"
    cache_dir.mkdir(parents=True, exist_ok=True)
    for i, path in enumerate(files, 1):
        st = path.stat()
        key = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]
        cache = cache_dir / f"{key}.json"
        data = None
        if resume and cache.exists():
            old = json.loads(cache.read_text(encoding="utf-8"))
            if old.get("size_bytes") == st.st_size and old.get("mtime_ns") == st.st_mtime_ns:
                data = old
        if data is None:
            meta = {}
            error = None
            try:
                meta = probe(path)
            except Exception as exc:
                error = str(exc)
            data = {"video_id": "v_" + key, "source_path": str(path), "account": path.relative_to(VIDEO_DIR).parts[0] if len(path.relative_to(VIDEO_DIR).parts) > 1 else "未知", "size_bytes": st.st_size, "mtime_ns": st.st_mtime_ns, "sha256": sha256(path), "probe_ok": not bool(error), "probe_error": error, **meta}
            row = db.get(os.path.normcase(os.path.normpath(str(path))))
            data["db"] = row
            atomic_json(cache, data)
        items.append(data)
        if i % 25 == 0 or i == len(files):
            print(f"inventory {i}/{len(files)}", flush=True)
    manifest = OUTPUT_DIR / "manifest" / "manifest.jsonl"
    atomic_text(manifest, "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in items))
    counts = collections.Counter(x["account"] for x in items)
    hashes = collections.Counter(x["sha256"] for x in items)
    summary = {"scanned_at": now(), "video_dir": str(VIDEO_DIR), "files": len(items), "accounts": dict(counts), "probe_ok": sum(x["probe_ok"] for x in items), "probe_failed": sum(not x["probe_ok"] for x in items), "without_audio": sum(x["probe_ok"] and not x["has_audio"] for x in items), "db_matched": sum(bool(x.get("db")) for x in items), "full_duplicate_files": sum(n - 1 for n in hashes.values()), "unique_sha256": len(hashes), "total_bytes": sum(x["size_bytes"] for x in items), "total_duration_s": sum(x.get("duration_s", 0) for x in items), "video_extensions": dict(collections.Counter(Path(x["source_path"]).suffix.lower() for x in items))}
    atomic_json(OUTPUT_DIR / "manifest" / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["inventory"])
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()
    if args.command == "inventory":
        inventory(args.resume)


if __name__ == "__main__":
    main()
