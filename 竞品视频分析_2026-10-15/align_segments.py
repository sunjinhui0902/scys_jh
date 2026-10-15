"""Rebuild readable timed clauses from FunASR text and token timestamps.

FunASR sentence_info can contain punctuation-only/fragmented text on long input.
This file preserves the raw model output and creates a separately verified alignment.
"""
from __future__ import annotations

import json
from pathlib import Path
import unicodedata

from pipeline import OUTPUT_DIR, atomic_json, now

BREAKS = set("，,。！？?!；;")


def token_spans(text: str, keep_apostrophe: bool = False) -> list[tuple[int, int, str]]:
    spans = []
    i = 0
    while i < len(text):
        c = text[i]
        if c.isspace() or unicodedata.category(c).startswith("P"):
            i += 1
            continue
        if c.isascii() and c.isalnum():
            j = i + 1
            while j < len(text):
                if text[j].isascii() and text[j].isalnum():j += 1
                elif keep_apostrophe and text[j] in "'’" and j+1<len(text) and text[j+1].isascii() and text[j+1].isalnum():j += 1
                else:break
            spans.append((i, j, text[i:j]))
            i = j
        else:
            spans.append((i, i + 1, c))
            i += 1
    return spans


def align(video_id: str) -> dict:
    raw_path = OUTPUT_DIR / "segments" / f"{video_id}.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    text = (OUTPUT_DIR / "transcripts" / f"{video_id}.txt").read_text(encoding="utf-8").strip()
    stamps = raw["raw_timestamp"]
    spans = token_spans(text)
    tokenization = 'Chinese characters / ASCII alphanumeric runs'
    if len(spans) != len(stamps):
        alternate=token_spans(text,keep_apostrophe=True)
        if len(alternate)==len(stamps):spans=alternate;tokenization='Chinese characters / ASCII words with internal apostrophes'
    if len(spans) != len(stamps):
        raise ValueError(f"{video_id}: {len(spans)} text tokens != {len(stamps)} time spans")
    if not all(0 <= a <= b <= (raw["duration_s"] + 2) * 1000 for a, b in stamps):
        raise ValueError(f"{video_id}: invalid time range")
    if not all(stamps[i][0] <= stamps[i + 1][0] for i in range(len(stamps) - 1)):
        raise ValueError(f"{video_id}: non-monotonic token starts")
    result = []
    left = 0
    tok_left = 0
    tok_idx = 0
    for i, c in enumerate(text):
        if tok_idx < len(spans) and i == spans[tok_idx][1] - 1:
            tok_idx += 1
        if c in BREAKS and tok_idx > tok_left:
            chunk = text[left : i + 1]
            if chunk.strip():
                result.append({"start_ms": stamps[tok_left][0], "end_ms": stamps[tok_idx - 1][1], "text": chunk, "token_start": tok_left, "token_end_exclusive": tok_idx})
            left = i + 1
            tok_left = tok_idx
    if tok_idx > tok_left or text[left:].strip():
        result.append({"start_ms": stamps[tok_left][0] if tok_idx > tok_left else stamps[-1][1], "end_ms": stamps[tok_idx - 1][1] if tok_idx > tok_left else stamps[-1][1], "text": text[left:], "token_start": tok_left, "token_end_exclusive": tok_idx})
    # Includes all punctuation and spaces from transcript, including trailing text.
    reconstructed = "".join(s["text"] for s in result)
    if reconstructed != text:
        raise ValueError(f"{video_id}: text reconstruction mismatch at {len(reconstructed)} vs {len(text)}")
    if any(x["start_ms"] > x["end_ms"] for x in result):
        raise ValueError(f"{video_id}: negative segment")
    return {"video_id": video_id, "duration_s": raw["duration_s"], "source_transcript": str(OUTPUT_DIR / "transcripts" / f"{video_id}.txt"), "source_raw_segments": str(raw_path), "alignment_method": "Transcription tokens sequentially paired with FunASR raw_timestamp; split on punctuation. Millisecond times are model estimates.", "tokenization":tokenization, "segments": result, "checks": {"text_reconstructed_exactly": True, "token_count_equal": True, "timestamps_in_range": True, "timestamp_starts_monotonic": True, "segment_count": len(result)}, "generated_at": now()}


def main() -> None:
    plan = json.loads((OUTPUT_DIR / "manifest" / "sample_plan.json").read_text(encoding="utf-8"))
    for item in plan:
        data = align(item["video_id"])
        atomic_json(OUTPUT_DIR / "segments" / f"{item['video_id']}.aligned.json", data)
        print(item["video_id"], len(data["segments"]), flush=True)


if __name__ == "__main__":
    main()
