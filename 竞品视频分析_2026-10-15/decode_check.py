"""Two-point video stream decode smoke check for every inventoried file."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import time

from pipeline import OUTPUT_DIR, FFMPEG, atomic_json, atomic_text, now


def check(item: dict) -> dict:
    start = time.monotonic()
    path = item["source_path"]
    checks = []
    if not item["probe_ok"]:
        return {"video_id": item["video_id"], "source_path": path, "status": "PROBE_FAILED", "checks": [], "elapsed_s": 0}
    for sec in [min(1.0, item["duration_s"] / 2), item["duration_s"] / 2]:
        cmd = [str(FFMPEG), "-nostdin", "-v", "error", "-ss", str(sec), "-i", path, "-map", "0:v:0", "-frames:v", "1", "-f", "null", "NUL"]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            checks.append({"time_s": round(sec, 3), "ok": p.returncode == 0, "error": p.stderr[-500:] if p.returncode else None})
        except Exception as exc:
            checks.append({"time_s": round(sec, 3), "ok": False, "error": str(exc)})
    return {"video_id": item["video_id"], "source_path": path, "status": "TWO_POINT_OK" if all(c["ok"] for c in checks) else "TWO_POINT_FAILED", "checks": checks, "elapsed_s": round(time.monotonic() - start, 3)}


def main() -> None:
    if not FFMPEG:
        raise RuntimeError("FFmpeg unavailable")
    items = [json.loads(s) for s in (OUTPUT_DIR / "manifest" / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if s]
    cache = OUTPUT_DIR / "state" / "decode"
    cache.mkdir(parents=True, exist_ok=True)
    todo = [x for x in items if not (cache / f"{x['video_id']}.json").exists()]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(check, item): item for item in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            data = fut.result()
            atomic_json(cache / f"{data['video_id']}.json", data)
            if i % 25 == 0 or i == len(todo):
                print(f"decode {i}/{len(todo)}", flush=True)
    rows = [json.loads((cache / f"{x['video_id']}.json").read_text(encoding="utf-8")) for x in items]
    atomic_text(OUTPUT_DIR / "manifest" / "decode_checks.jsonl", "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows))
    atomic_json(OUTPUT_DIR / "manifest" / "decode_summary.json", {"checked_at": now(), "method": "FFmpeg one video frame at 1 second and 50 percent; this does not verify every frame or audio", "count": len(rows), "two_point_ok": sum(x["status"] == "TWO_POINT_OK" for x in rows), "two_point_failed": sum(x["status"] == "TWO_POINT_FAILED" for x in rows), "probe_failed": sum(x["status"] == "PROBE_FAILED" for x in rows)})


if __name__ == "__main__":
    main()
