import os
import sys
import json
import zipfile
import shutil
from pathlib import Path

# UTF-8 编码安全保障
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path("d:/fuye")
JY_BASE = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "JianyingPro/User Data/Projects/com.lveditor.draft"
GDRIVE_DIR = Path("G:/我的云端硬盘/视频号第一周/06_成片待审/01_剪映草稿工程")

proj_map = {
    "M2": "M2_11-06_0700",
    "M3": "M3_11-08_0700",
    "M4": "M4_11-05_0700",
    "M5": "M5_11-07_0700",
    "M6": "M6_11-04_0700",
    "M7": "M7_11-09_0700",
    "N2": "N2_11-04_1230",
    "N3": "N3_11-05_1230",
    "N4": "N4_11-06_1230",
    "N5": "N5_11-07_1230",
    "N6": "N6_11-08_1230",
    "N7": "N7_11-09_1230",
    "W2": "W2_11-04_1900",
    "W3": "W3_11-05_1900",
    "W4": "W4_11-06_1900",
    "W5": "W5_11-07_1900",
    "W6": "W6_11-08_1900",
    "W7": "W7_11-09_1900"
}

# 本地临时打包输出路径
local_zip_path = ROOT / "03_视频成片与工程" / "第一周剩余18条剪映草稿合集_修正版.zip"
gdrive_zip_path = GDRIVE_DIR / "第一周剩余18条剪映草稿合集_修正版.zip"
old_zip_path = GDRIVE_DIR / "第一周剩余18条剪映草稿合集.zip"

print(f"正在创建修正版 ZIP: {local_zip_path} ...")
with zipfile.ZipFile(local_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for code, pdir in proj_map.items():
        with open(ROOT / "03_视频成片与工程" / pdir / "draft_manifest.json", "r", encoding="utf-8") as f:
            manifest = json.load(f)
            title = manifest.get("draft_title")
            
        draft_folder = JY_BASE / title
        content_path = draft_folder / "draft_content.json"
        meta_path = draft_folder / "draft_meta_info.json"
        
        if not content_path.exists() or not meta_path.exists():
            print(f"ERROR: {code} draft files missing in {draft_folder}")
            continue
            
        # 验证 JSON 有效性
        with open(content_path, "r", encoding="utf-8") as f:
            c_json = json.load(f)
        with open(meta_path, "r", encoding="utf-8") as f:
            m_json = json.load(f)
            
        # 写入压缩包
        arc_content = f"{pdir}/draft_content.json"
        arc_meta = f"{pdir}/draft_meta_info.json"
        
        zf.write(content_path, arcname=arc_content)
        zf.write(meta_path, arcname=arc_meta)
        
        # 同时镜像备份到 03_视频成片与工程/<dir>/
        local_target_dir = ROOT / "03_视频成片与工程" / pdir
        shutil.copy2(content_path, local_target_dir / "draft_content.json")
        shutil.copy2(meta_path, local_target_dir / "draft_meta_info.json")
        
        print(f"  [✓ 打包] {code} -> {pdir}/ (content: {os.path.getsize(content_path)} bytes, meta: {os.path.getsize(meta_path)} bytes)")

print(f"\nZIP 制作完成: {local_zip_path.stat().st_size} bytes")

# 复制到云盘
if GDRIVE_DIR.exists():
    print(f"正在同步至 Google Drive: {gdrive_zip_path} ...")
    shutil.copy2(local_zip_path, gdrive_zip_path)
    print("  [✓ 云盘上传完成]")
    
    # 删除旧合集 ZIP
    if old_zip_path.exists():
        print(f"正在删除旧合集 ZIP: {old_zip_path} ...")
        old_zip_path.unlink()
        print("  [✓ 旧合集 ZIP 已成功删除，只保留修正版]")
    else:
        print("  [提示] 旧合集 ZIP 不存在，无需删除")
else:
    print(f"WARNING: 云盘目录未找到: {GDRIVE_DIR}")

# 校验新合集
print("\n=== 新合集 ZIP 完整性验证 ===")
with zipfile.ZipFile(local_zip_path, "r") as zf:
    namelist = zf.namelist()
    print(f"总文件数: {len(namelist)} (预期 36 个文件: 18 * 2)")
    for code, pdir in proj_map.items():
        c_entry = f"{pdir}/draft_content.json"
        m_entry = f"{pdir}/draft_meta_info.json"
        c_bytes = zf.read(c_entry)
        m_bytes = zf.read(m_entry)
        c_obj = json.loads(c_bytes.decode("utf-8"))
        m_obj = json.loads(m_bytes.decode("utf-8"))
        print(f"  [PASS] {code:2s} ({pdir}): content={len(c_bytes)}b, tracks={len(c_obj['tracks'])}, meta={m_obj.get('draft_name')}")

print("\n合集打包与验证全部成功！")
