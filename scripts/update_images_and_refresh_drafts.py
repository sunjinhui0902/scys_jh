#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Helper script to update GPT-generated images and instantly refresh JianYing drafts.
Usage:
    python scripts/update_images_and_refresh_drafts.py --mapping '{"ep1_01.png": "D:/path/to/img.png"}'
    or simply place files directly into 03_视频成片与工程/十大历史名城_带孙辈长见识/assets/images/
"""

import sys
import json
import shutil
import argparse
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = ROOT / "03_视频成片与工程" / "十大历史名城_带孙辈长见识"
IMAGES_DIR = BASE_DIR / "assets" / "images"

import build_jianying_city_drafts

def update_and_build(mapping: dict = None):
    if mapping:
        for target_name, src_path_str in mapping.items():
            src_path = Path(src_path_str)
            if src_path.is_file():
                dst_path = IMAGES_DIR / target_name
                shutil.copy2(src_path, dst_path)
                print(f"✓ 已更新图片: {target_name} <- {src_path}")
            else:
                print(f"[警告] 提供的源图片文件不存在: {src_path_str}")

    print("\n🚀 重新构建剪映工程...")
    build_jianying_city_drafts.main()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping", help="JSON string or path to JSON file containing {image_name: src_path}")
    args = parser.parse_args()

    mapping_dict = None
    if args.mapping:
        if Path(args.mapping).is_file():
            mapping_dict = json.loads(Path(args.mapping).read_text(encoding="utf-8"))
        else:
            mapping_dict = json.loads(args.mapping)

    update_and_build(mapping_dict)
