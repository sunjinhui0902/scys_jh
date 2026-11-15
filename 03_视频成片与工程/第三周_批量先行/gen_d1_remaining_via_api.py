#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate remaining D1 images via Gemini API (dual-key failover) and resize to 1080x1920 JPEG."""

import base64
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
PROMPT_MD = Path(r"G:\我的云端硬盘\JH\视频号第三周\04_制作卡与Gemini输出\生图_D1_1117周二.md")
OUT_DIR = ROOT / "03_视频成片与工程" / "第三周_批量先行" / "D1_生图测试"
D1_ZAO_REF = ROOT / "03_视频成片与工程" / "第三周_D1验证" / "D1早" / "images"

TARGETS = {
    "D1早_IMG03_B": [D1_ZAO_REF / "IMG03.png", D1_ZAO_REF / "IMG01.png"],
    "D1早_IMG04_B": [D1_ZAO_REF / "IMG04.png"],
    "D1早_IMG05":   [D1_ZAO_REF / "IMG01.png", D1_ZAO_REF / "IMG02.png", D1_ZAO_REF / "IMG04.png"],
    "D1晚_IMG03":   [OUT_DIR / "D1晚_IMG02.jpg"],
    "D1晚_IMG03_B": [OUT_DIR / "D1晚_IMG02.jpg"],
    "D1晚_IMG04":   [OUT_DIR / "D1晚_IMG02.jpg"],
    "D1晚_IMG04_B": [OUT_DIR / "D1晚_IMG02.jpg"],
    "D1晚_IMG05":   [OUT_DIR / "D1晚_IMG01_C.jpg"],
    "D1晚_IMG05_B": [OUT_DIR / "D1晚_IMG01_C.jpg"],
}

MODELS = ["gemini-3.1-flash-image", "gemini-2.5-flash-image", "gemini-3-pro-image"]


def load_keys_and_proxy() -> tuple[list[str], str | None]:
    env_file = Path.home() / ".gemini" / "config" / "skills" / "gemini-dual-api" / ".env"
    env: dict[str, str] = {}
    if env_file.exists():
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    keys = [
        env.get("GEMINI_API_KEY_1") or os.environ.get("GEMINI_API_KEY_1", ""),
        env.get("GEMINI_API_KEY_2") or os.environ.get("GEMINI_API_KEY_2", ""),
    ]
    keys = [k for k in keys if k]
    proxy = env.get("HTTPS_PROXY") or os.environ.get("HTTPS_PROXY")
    return keys, proxy


def parse_prompts(md_path: Path) -> dict[str, str]:
    prompts: dict[str, str] = {}
    for line in md_path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^- (D1[早午晚]_IMG\d+(?:_[BC])?)｜[^｜]+｜(.+)$", line.strip())
        if m:
            prompts[m.group(1)] = m.group(2).strip()
    return prompts


def call_gemini_image(opener, key: str, model: str, prompt: str, refs: list[Path]) -> bytes:
    parts: list[dict] = []
    if refs:
        parts.append({"text": "请严格保持以下参考图中主要人物（或衣着、道具、环境风格）的视觉一致性，按后面的完整描述生成一张全新的 9:16 竖屏写实摄影静图："})
        for rp in refs:
            if rp.exists():
                mime = "image/png" if rp.suffix.lower() == ".png" else "image/jpeg"
                b64 = base64.b64encode(rp.read_bytes()).decode("ascii")
                parts.append({"inlineData": {"mimeType": mime, "data": b64}})
    parts.append({"text": prompt})

    body = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": "9:16"},
        },
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with opener.open(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    for cand in data.get("candidates", []):
        for p in cand.get("content", {}).get("parts", []):
            inline = p.get("inlineData") or p.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
    raise RuntimeError(f"No image in response: {json.dumps(data, ensure_ascii=False)[:400]}")


def main() -> None:
    keys, proxy = load_keys_and_proxy()
    assert keys, "No Gemini API keys found"
    opener = (
        urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        if proxy
        else urllib.request.build_opener()
    )
    prompts = parse_prompts(PROMPT_MD)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for img_id, refs in TARGETS.items():
        dst = OUT_DIR / f"{img_id}.jpg"
        if dst.exists():
            print(f"[SKIP] {img_id}.jpg already exists")
            continue
        prompt = prompts[img_id]
        raw_bytes = None
        last_err = None
        for model in MODELS:
            for k_idx, key in enumerate(keys, 1):
                try:
                    raw_bytes = call_gemini_image(opener, key, model, prompt, refs)
                    print(f"[OK] {img_id} via {model} (key #{k_idx})")
                    break
                except urllib.error.HTTPError as e:
                    err_body = e.read().decode("utf-8", errors="replace")[:300]
                    last_err = f"{model} key#{k_idx} HTTP {e.code}: {err_body}"
                    print(f"[RETRY] {img_id}: {last_err}")
                except Exception as e:
                    last_err = f"{model} key#{k_idx} ERR: {e}"
                    print(f"[RETRY] {img_id}: {last_err}")
            if raw_bytes is not None:
                break
        if raw_bytes is None:
            raise RuntimeError(f"Failed {img_id}: {last_err}")
        im = Image.open(io.BytesIO(raw_bytes)).convert("RGB").resize((1080, 1920), Image.Resampling.LANCZOS)
        im.save(dst, "JPEG", quality=92)
        print(f"  -> Saved {dst.name} ({dst.stat().st_size} bytes)")
        time.sleep(1.5)


if __name__ == "__main__":
    main()
