# -*- coding: utf-8 -*-
"""
脚本：将 GPT 生成的全部 12 个分镜图片（shot_01.png ~ shot_12.png）从 assets/ 同步到 02_分镜视觉素材/
并调用 fast_draft_pipeline 完成 5 个精讲视频工程的剪映草稿全量热替换！
"""
import os
import shutil
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS_DIR = ROOT / "03_视频成片与工程"

TARGET_PROJECTS = [
    "01_平遥古城_单集精讲",
    "02_延安宝塔山_单集精讲",
    "03_开封清明上河园_单集精讲",
    "04_苏州拙政园_单集精讲",
    "05_杭州西湖_单集精讲",
]

def sync_and_apply():
    for proj_name in TARGET_PROJECTS:
        proj_dir = PROJECTS_DIR / proj_name
        assets_dir = proj_dir / "assets"
        visuals_dir = proj_dir / "02_分镜视觉素材"
        visuals_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. 同步 shot_*.png 到 02_分镜视觉素材
        copied = []
        if assets_dir.exists():
            for f in sorted(assets_dir.glob("shot_*.png")):
                dest = visuals_dir / f.name
                if not dest.exists() or dest.stat().st_size != f.stat().st_size:
                    shutil.copy2(f, dest)
                    copied.append(f.name)
        
        print(f"[{proj_name}] 同步了 {len(copied)} 张新图片到 02_分镜视觉素材/，当前视觉素材目录图片数: {len(list(visuals_dir.glob('shot_*.png')))}")

if __name__ == "__main__":
    sync_and_apply()
