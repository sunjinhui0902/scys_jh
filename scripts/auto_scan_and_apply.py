#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto Scan & Apply Images Pipeline
==================================
定时扫描 03_视频成片与工程 下的各单集精讲项目。
当 GPT 生成的真实图片（shot_01 ~ shot_08, shot_12 等）放入对应目录后，
自动调用 fast_draft_pipeline 热替换剪映草稿素材。
"""

import os
import sys
import time
import json
import argparse
from pathlib import Path
from datetime import datetime

# UTF-8 编码安全保障
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.fast_draft_pipeline import apply_images_to_draft, build_pipeline_draft

PROJECTS_DIR = ROOT / "03_视频成片与工程"
LOG_FILE = PROJECTS_DIR / "auto_scan.log"
STATE_FILE = PROJECTS_DIR / ".auto_scan_state.json"

TARGET_PROJECTS = [
    "01_平遥古城_单集精讲",
    "02_延安宝塔山_单集精讲",
    "03_开封清明上河园_单集精讲",
    "04_苏州拙政园_单集精讲",
    "05_杭州西湖_单集精讲",
]


def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(state: dict):
    try:
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log(f"保存扫描状态失败: {e}")


def scan_and_apply_all():
    log("🔍 开始全量素材巡检...")
    state = load_state()
    updated_count = 0

    for proj_name in TARGET_PROJECTS:
        proj_dir = PROJECTS_DIR / proj_name
        if not proj_dir.is_dir():
            continue

        visuals_dir = proj_dir / "02_分镜视觉素材"
        assets_dir = proj_dir / "assets"
        visuals_dir.mkdir(parents=True, exist_ok=True)

        # 扫描真实图片（排除占位图、preview及子目录）
        real_images = []
        for sdir in [visuals_dir, assets_dir]:
            if sdir.exists():
                for f in sdir.iterdir():
                    if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"] and "placeholder" not in f.name.lower() and not f.name.startswith("preview"):
                        if f.name not in real_images:
                            real_images.append(f.name)

        real_images.sort()
        prev_images = state.get(proj_name, {}).get("images", [])

        # 如果发现有新图片加入，或者之前从未热替换过且已有图片
        if set(real_images) != set(prev_images) and len(real_images) > 0:
            log(f"📦 【{proj_name}】检测到素材更新！当前真实图片数: {len(real_images)} 张 ({', '.join(real_images)})")
            try:
                apply_images_to_draft(proj_dir)
                log(f"✅ 【{proj_name}】剪映草稿热替换成功！")
                state[proj_name] = {
                    "images": real_images,
                    "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "ready" if len(real_images) >= 8 else "partial"
                }
                save_state(state)
                updated_count += 1
            except Exception as e:
                log(f"❌ 【{proj_name}】热替换失败: {e}")
        else:
            status_desc = f"{len(real_images)} 张已装配" if real_images else "暂无新图，等待 GPT"
            log(f"   - {proj_name}: {status_desc}")

    log(f"🏁 巡检完成，本轮成功热替换 {updated_count} 个工程草稿。")


def run_daemon(interval_sec: int = 1800):
    log(f"🚀 自动扫描守护进程启动，扫描间隔: {interval_sec} 秒 ({interval_sec // 60} 分钟)")
    try:
        while True:
            scan_and_apply_all()
            log(f"💤 进入休眠，下一次扫描将在 {interval_sec // 60} 分钟后触发...\n")
            time.sleep(interval_sec)
    except KeyboardInterrupt:
        log("🛑 守护进程手动终止。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto scan and apply images to drafts")
    parser.add_argument("--once", action="store_true", help="单次扫描并退出")
    parser.add_argument("--interval", type=int, default=1800, help="持续扫描时间间隔（秒，默认1800秒即30分钟）")
    args = parser.parse_args()

    if args.once:
        scan_and_apply_all()
    else:
        run_daemon(args.interval)
