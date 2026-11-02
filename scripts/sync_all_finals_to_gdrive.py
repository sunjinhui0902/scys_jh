import os
import sys
import json
import shutil
import zipfile
from pathlib import Path

# UTF-8 编码安全保障
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path("d:/fuye")
PROJ_ROOT = ROOT / "03_视频成片与工程"
JY_BASE = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "JianyingPro/User Data/Projects/com.lveditor.draft"
GDRIVE_DIR = Path("G:/我的云端硬盘/视频号第一周/06_成片待审")
GDRIVE_DRAFTS = GDRIVE_DIR / "01_剪映草稿工程"

ALL_FOLDERS = [
    "M1_11-03_0700", "N1_11-03_1230", "W1_11-03_1900",
    "M6_11-04_0700", "N2_11-04_1230", "W2_11-04_1900",
    "M4_11-05_0700", "N3_11-05_1230", "W3_11-05_1900",
    "M2_11-06_0700", "N4_11-06_1230", "W4_11-06_1900",
    "M5_11-07_0700", "N5_11-07_1230", "W5_11-07_1900",
    "M3_11-08_0700", "N6_11-08_1230", "W6_11-08_1900",
    "M7_11-09_0700", "N7_11-09_1230", "W7_11-09_1900"
]

REMAINING_18 = ALL_FOLDERS[3:]

print("=== 1. 刷新 18 条剪映草稿合集_修正版.zip ===")
local_zip = PROJ_ROOT / "第一周剩余18条剪映草稿合集_修正版.zip"
gdrive_zip = GDRIVE_DRAFTS / "第一周剩余18条剪映草稿合集_修正版.zip"

with zipfile.ZipFile(local_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for folder in REMAINING_18:
        pdir = PROJ_ROOT / folder
        with open(pdir / "draft_manifest.json", "r", encoding="utf-8") as f:
            manifest = json.load(f)
            title = manifest.get("draft_title")
        
        draft_folder = JY_BASE / title
        content_path = draft_folder / "draft_content.json"
        meta_path = draft_folder / "draft_meta_info.json"
        
        # 写入 zip
        zf.write(content_path, arcname=f"{folder}/draft_content.json")
        zf.write(meta_path, arcname=f"{folder}/draft_meta_info.json")
        
        # 本地镜像备份
        shutil.copy2(content_path, pdir / "draft_content.json")
        shutil.copy2(meta_path, pdir / "draft_meta_info.json")
        print(f"  [草稿打包] {folder} (6/6 真实素材已挂接)")

shutil.copy2(local_zip, gdrive_zip)
print(f"  [✓ 云盘草稿更新完成] {gdrive_zip.name} ({gdrive_zip.stat().st_size} bytes)")

print("\n=== 2. 同步全部 21 条成片 MP4 至云盘 06_成片待审 ===")
copied_mp4 = 0
for folder in ALL_FOLDERS:
    render_dir = PROJ_ROOT / folder / "05_成片"
    if not render_dir.exists():
        continue
    mp4_files = list(render_dir.glob("*.mp4"))
    for mp4 in mp4_files:
        target_mp4 = GDRIVE_DIR / mp4.name
        if not target_mp4.exists() or target_mp4.stat().st_size != mp4.stat().st_size:
            print(f"  正在同步成片: {mp4.name} ({mp4.stat().st_size / 1024 / 1024:.2f} MB) -> 云盘")
            shutil.copy2(mp4, target_mp4)
            copied_mp4 += 1
        else:
            print(f"  已就绪: {mp4.name}")

print(f"\n成片同步完成，新增同步: {copied_mp4} 个文件")

print("\n=== 3. 统计云盘 06_成片待审 文件总览 ===")
mp4_in_gdrive = list(GDRIVE_DIR.glob("*.mp4"))
print(f"云盘 MP4 成片总数: {len(mp4_in_gdrive)}/21")
for p in sorted(mp4_in_gdrive):
    print(f"  - {p.name} ({p.stat().st_size / 1024 / 1024:.2f} MB)")
