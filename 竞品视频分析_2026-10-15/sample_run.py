"""Run ten V4 local samples with per-step state and atomic handoff."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from pipeline import OUTPUT_DIR, FFMPEG, atomic_json, atomic_text, now

TARGETS = [
    ("开卷读书", 45, "短视频口播"),
    ("开卷读书", 100, "中等时长情绪题材"),
    ("文汇书香苑", 450, "历史人物长故事"),
    ("林睿读书&书在橱窗", 60, "短视频历史题材"),
    ("林睿读书&书在橱窗", 420, "长视频历史题材"),
    ("破局书屋", 30, "短视频职场题材"),
    ("破局书屋", 240, "较长职场题材"),
    ("赵健的读书日记", 180, "读书账号中等时长"),
    ("赵健的读书日记", 315, "读书账号长视频"),
    ("锦绣千秋录", 420, "风景文化长视频"),
]


def manifest() -> list[dict]:
    return [json.loads(line) for line in (OUTPUT_DIR / "manifest" / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if line]


def plan() -> list[dict]:
    path = OUTPUT_DIR / "manifest" / "sample_plan.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    items = manifest()
    used = set()
    result = []
    for account, target, reason in TARGETS:
        candidates = [x for x in items if x["account"] == account and x["probe_ok"] and x["has_audio"] and x["video_id"] not in used]
        if not candidates:
            raise RuntimeError(f"No suitable sample for {account}")
        x = min(candidates, key=lambda a: abs(a["duration_s"] - target))
        used.add(x["video_id"])
        result.append({**x, "selection_reason": reason, "target_duration_s": target})
    atomic_json(path, result)
    return result


def run(cmd: list[str], timeout: int = 600) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if p.returncode:
        raise RuntimeError(p.stderr[-1200:] or f"exit {p.returncode}")


def frame_times(duration: float) -> list[float]:
    end = max(0, duration - 0.1)
    values = [min(1, end), min(5, end), min(duration / 2, end), min(max(0, duration - 2), end)]
    # Every selected sample is well over five seconds; preserve four distinct points.
    return [round(x, 3) for x in values]


def mark(state_path: Path, state: dict, step: str, status: str, elapsed: float | None = None, error: str | None = None) -> None:
    state.setdefault("steps", {})[step] = {"status": status, "at": now(), "elapsed_s": elapsed, "error": error}
    state["status"] = "LOCAL_FAILED" if status == "FAILED" else "LOCAL_RUNNING"
    atomic_json(state_path, state)


def process_local(items: list[dict], resume: bool = True) -> None:
    if FFMPEG is None:
        raise RuntimeError("FFmpeg not found")
    for number, item in enumerate(items, 1):
        vid = item["video_id"]
        source = item["source_path"]
        state_path = OUTPUT_DIR / "state" / f"{vid}.json"
        state = json.loads(state_path.read_text(encoding="utf-8")) if resume and state_path.exists() else {"video_id": vid, "source_path": source, "account": item["account"], "started_at": now(), "status": "DISCOVERED", "steps": {}}
        print(f"local {number}/{len(items)} {vid} {item['account']} {item['duration_s']:.1f}s", flush=True)
        wav = OUTPUT_DIR / "audio" / f"{vid}.wav"
        wav.parent.mkdir(parents=True, exist_ok=True)
        if not (resume and state["steps"].get("audio", {}).get("status") == "OK" and wav.exists()):
            t = time.monotonic()
            try:
                tmp = wav.with_suffix(".tmp.wav")
                run([str(FFMPEG), "-nostdin", "-y", "-loglevel", "error", "-i", source, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "wav", str(tmp)], timeout=max(600, int(item["duration_s"] * 3)))
                os.replace(tmp, wav)
                mark(state_path, state, "audio", "OK", time.monotonic() - t)
            except Exception as exc:
                mark(state_path, state, "audio", "FAILED", time.monotonic() - t, str(exc))
                continue
        times = frame_times(item["duration_s"])
        frames = []
        for idx, sec in enumerate(times, 1):
            dest = OUTPUT_DIR / "frames" / vid / f"{idx:02d}_{sec:.3f}s.jpg"
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not (resume and dest.exists() and dest.stat().st_size > 0):
                t = time.monotonic()
                try:
                    tmp = dest.with_suffix(".tmp.jpg")
                    run([str(FFMPEG), "-nostdin", "-y", "-loglevel", "error", "-ss", str(sec), "-i", source, "-frames:v", "1", "-q:v", "3", str(tmp)], timeout=120)
                    if not tmp.exists() or tmp.stat().st_size == 0:
                        raise RuntimeError("Empty frame")
                    os.replace(tmp, dest)
                    mark(state_path, state, f"frame_{idx}", "OK", time.monotonic() - t)
                except Exception as exc:
                    mark(state_path, state, f"frame_{idx}", "FAILED", time.monotonic() - t, str(exc))
                    break
            frames.append({"index": idx, "time_s": sec, "path": str(dest)})
        atomic_json(OUTPUT_DIR / "frames" / vid / "index.json", frames)


def transcribe(items: list[dict], resume: bool = True) -> None:
    if resume:
        complete = 0
        for item in items:
            vid = item["video_id"]
            state_path = OUTPUT_DIR / "state" / f"{vid}.json"
            txt = OUTPUT_DIR / "transcripts" / f"{vid}.txt"
            seg = OUTPUT_DIR / "segments" / f"{vid}.json"
            if state_path.exists() and txt.exists() and seg.exists():
                state = json.loads(state_path.read_text(encoding="utf-8"))
                complete += state.get("steps", {}).get("asr", {}).get("status") == "OK"
        if complete == len(items):
            print(f"asr resume: {complete}/{len(items)} already complete; model load skipped", flush=True)
            return
    os.environ.setdefault("MODELSCOPE_CACHE", str(OUTPUT_DIR / "models"))
    from funasr import AutoModel
    import funasr
    import torch

    t_load = time.monotonic()
    model = AutoModel(model="paraformer-zh", vad_model="fsmn-vad", punc_model="ct-punc", vad_kwargs={"max_single_segment_time": 30000}, device="cpu", ncpu=6, disable_update=True, trust_remote_code=False)
    load_s = time.monotonic() - t_load
    atomic_json(OUTPUT_DIR / "manifest" / "asr_environment.json", {"funasr": funasr.__version__, "torch": torch.__version__, "model_path": str(getattr(model, "model_path", "")), "model_load_s": load_s, "loaded_at": now()})
    for number, item in enumerate(items, 1):
        vid = item["video_id"]
        wav = OUTPUT_DIR / "audio" / f"{vid}.wav"
        state_path = OUTPUT_DIR / "state" / f"{vid}.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        txt = OUTPUT_DIR / "transcripts" / f"{vid}.txt"
        seg = OUTPUT_DIR / "segments" / f"{vid}.json"
        if resume and state["steps"].get("asr", {}).get("status") == "OK" and txt.exists() and seg.exists():
            print(f"asr skip {number}/{len(items)} {vid}", flush=True)
            continue
        if not wav.exists():
            mark(state_path, state, "asr", "FAILED", error="Audio extraction missing")
            continue
        print(f"asr {number}/{len(items)} {vid} {item['duration_s']:.1f}s", flush=True)
        t = time.monotonic()
        try:
            result = model.generate(input=str(wav), batch_size_s=60, batch_size_threshold_s=30, sentence_timestamp=True)
            raw = result[0] if result else {}
            text = raw.get("text", "") or ""
            sentences = raw.get("sentence_info") or []
            checks = {"nonempty": bool(text.strip()), "sentence_count": len(sentences), "timestamps_present": bool(sentences), "timestamps_in_range": all(isinstance(s.get("start"), (int, float)) and isinstance(s.get("end"), (int, float)) and 0 <= s["start"] <= s["end"] <= (item["duration_s"] + 2) * 1000 for s in sentences)}
            atomic_text(txt, text + ("\n" if text else ""))
            atomic_json(seg, {"video_id": vid, "duration_s": item["duration_s"], "sentence_info": sentences, "raw_timestamp": raw.get("timestamp", []), "checks": checks, "model": "paraformer-zh + fsmn-vad + ct-punc", "time_unit": "milliseconds", "generated_at": now()})
            mark(state_path, state, "asr", "OK" if text.strip() and checks["timestamps_in_range"] else "FAILED", time.monotonic() - t, None if text.strip() else "Empty transcript")
            print(f"asr done {vid} chars={len(text)} seconds={time.monotonic()-t:.1f}", flush=True)
        except Exception as exc:
            mark(state_path, state, "asr", "FAILED", time.monotonic() - t, str(exc))
            print(f"asr failed {vid}: {exc}", flush=True)


def handoff(items: list[dict]) -> None:
    for item in items:
        vid = item["video_id"]
        state_path = OUTPUT_DIR / "state" / f"{vid}.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state["steps"].get("asr", {}).get("status") != "OK":
            continue
        frames = json.loads((OUTPUT_DIR / "frames" / vid / "index.json").read_text(encoding="utf-8"))
        if len(frames) != 4 or not all(Path(x["path"]).exists() for x in frames):
            continue
        root = OUTPUT_DIR / "handoff" / vid
        root.mkdir(parents=True, exist_ok=True)
        ready = root / "READY.json"
        aligned = OUTPUT_DIR / "segments" / f"{vid}.aligned.json"
        segment_path = aligned if aligned.exists() else OUTPUT_DIR / "segments" / f"{vid}.json"
        if ready.exists():
            old_input = json.loads((root / "input.json").read_text(encoding="utf-8"))
            if old_input.get("segments_path") == str(segment_path):
                continue
            ready.unlink()
        (root / "frames").mkdir(exist_ok=True)
        shutil.copyfile(OUTPUT_DIR / "transcripts" / f"{vid}.txt", root / "transcript.txt")
        frame_inputs = []
        for f in frames:
            dest = root / "frames" / Path(f["path"]).name
            shutil.copyfile(f["path"], dest)
            frame_inputs.append({"time_s": f["time_s"], "path": str(dest)})
        atomic_text(root / "original_video.path.txt", item["source_path"] + "\n")
        atomic_json(root / "input.json", {"schema_version": "1.0", "video_id": vid, "account": item["account"], "duration_s": item["duration_s"], "source_video_path": item["source_path"], "transcript_path": str(root / "transcript.txt"), "segments_path": str(segment_path), "raw_segments_path": str(OUTPUT_DIR / "segments" / f"{vid}.json"), "frames": frame_inputs, "ready_at": now(), "input_mode_pending_verification": True})
        atomic_json(ready, {"schema_version": "1.0", "video_id": vid, "ready_at": now(), "files_complete": True, "external_upload_authorized": False})
        state["status"] = "HANDOFF_READY"
        state["handoff_ready_at"] = now()
        atomic_json(state_path, state)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["plan", "local", "asr", "handoff"])
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()
    items = plan()
    if args.command == "plan":
        for x in items:
            print(x["video_id"], x["account"], x["duration_s"], x["selection_reason"], x["source_path"], sep=" | ")
    elif args.command == "local":
        process_local(items, args.resume)
    elif args.command == "asr":
        transcribe(items, args.resume)
    else:
        handoff(items)


if __name__ == "__main__":
    main()
