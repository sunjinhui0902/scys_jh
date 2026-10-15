"""Independent artifact checks for V4 G0/G1 local work."""
from __future__ import annotations

import collections
import json
from pathlib import Path

from pipeline import OUTPUT_DIR, VIDEO_DIR, EXTS, atomic_json, now


def main() -> None:
    manifest = [json.loads(s) for s in (OUTPUT_DIR / "manifest" / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if s]
    disk = {str(p) for p in VIDEO_DIR.rglob("*") if p.is_file() and p.suffix.lower() in EXTS}
    listed = [x["source_path"] for x in manifest]
    assert len(listed) == len(set(listed)) == len(disk) == 332
    assert set(listed) == disk
    assert len({x["sha256"] for x in manifest}) == 317
    assert sum(bool(x.get("db")) for x in manifest) == 317
    decode = [json.loads(s) for s in (OUTPUT_DIR / "manifest" / "decode_checks.jsonl").read_text(encoding="utf-8").splitlines() if s]
    assert len(decode) == len(manifest) and all(x["status"] == "TWO_POINT_OK" for x in decode)
    sample = json.loads((OUTPUT_DIR / "manifest" / "sample_plan.json").read_text(encoding="utf-8"))
    assert len(sample) == 10 and len({x["video_id"] for x in sample}) == 10 and len({x["account"] for x in sample}) == 6
    hashes = json.loads((OUTPUT_DIR / "manifest" / "sample_source_hash_check.json").read_text(encoding="utf-8"))["results"]
    assert len(hashes) == 10 and all(x["unchanged"] and x["size_unchanged"] and x["mtime_unchanged"] for x in hashes)
    for x in sample:
        vid = x["video_id"]
        state = json.loads((OUTPUT_DIR / "state" / f"{vid}.json").read_text(encoding="utf-8"))
        assert state["status"] == "HANDOFF_READY"
        assert state["steps"]["audio"]["status"] == state["steps"]["asr"]["status"] == "OK"
        assert all(state["steps"][f"frame_{i}"]["status"] == "OK" for i in range(1, 5))
        text = (OUTPUT_DIR / "transcripts" / f"{vid}.txt").read_text(encoding="utf-8").strip()
        assert text
        aligned = json.loads((OUTPUT_DIR / "segments" / f"{vid}.aligned.json").read_text(encoding="utf-8"))
        assert "".join(s["text"] for s in aligned["segments"]) == text
        assert aligned["checks"]["timestamps_in_range"] and aligned["checks"]["timestamp_starts_monotonic"]
        frames = json.loads((OUTPUT_DIR / "frames" / vid / "index.json").read_text(encoding="utf-8"))
        assert len(frames) == 4 and all(Path(f["path"]).is_file() for f in frames)
        pack = OUTPUT_DIR / "handoff" / vid
        ready = json.loads((pack / "READY.json").read_text(encoding="utf-8"))
        inp = json.loads((pack / "input.json").read_text(encoding="utf-8"))
        assert ready["files_complete"] and ready["external_upload_authorized"] is False
        assert inp["segments_path"] == str(OUTPUT_DIR / "segments" / f"{vid}.aligned.json")
        assert (pack / "transcript.txt").read_text(encoding="utf-8").strip() == text
        assert len(inp["frames"]) == 4 and all(Path(f["path"]).is_file() for f in inp["frames"])
    result = {"checked_at": now(), "g0_manifest_paths_match_disk": True, "video_files": len(manifest), "account_counts": dict(collections.Counter(x["account"] for x in manifest)), "two_point_decode_ok": len(decode), "unique_sha256": 317, "sample_count": 10, "sample_accounts": 6, "sample_transcripts_ok": 10, "sample_aligned_segments_ok": 10, "sample_frames_ok": 40, "sample_handoffs_ready": 10, "sample_source_files_unchanged": 10, "database_physical_file_unchanged": False, "database_note": "DB main file changed at downloader service shutdown; WAL/SHM appeared after read-only query. See inventory report.", "antigravity_test_status": "PENDING", "g1_status": "USER_REVIEW_REQUIRED"}
    atomic_json(OUTPUT_DIR / "manifest" / "phase1_validation.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
