# -*- coding: utf-8 -*-
import os
import sys
import time
import shutil
import json
from pathlib import Path

# Force UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from fast_draft_pipeline import build_pipeline_draft

JIANYING_DIR = Path("C:/Users/Miche/AppData/Local/JianyingPro/User Data/Projects/com.lveditor.draft")
ROOT_META_FILE = JIANYING_DIR / "root_meta_info.json"

# 1. 彻底删除旧废弃草稿文件夹
OLD_DRAFTS = [
    "【图书带货】此生必去：中国十大冬日绝景",
    "【图书带货】终极揭晓：中国冬日绝景前五"
]

print("1. 清理废弃旧草稿目录...")
for old_name in OLD_DRAFTS:
    old_p = JIANYING_DIR / old_name
    if old_p.exists():
        try:
            shutil.rmtree(old_p)
            print(f"  ✓ 已删除废弃草稿: {old_name}")
        except Exception as e:
            print(f"  ⚠️ 删除失败 {old_name}: {e}")

# 2. 重新构建两大冬日绝景草稿（应用优化版自然断句 + 严格首字发音波形对齐 + SRT导出）
print("\n2. 重新高精装配草稿工程...")
ep1_dir = ROOT / "03_视频成片与工程/十大冬日绝景_纯涨粉系列/上集_第10至第6名"
ep2_dir = ROOT / "03_视频成片与工程/十大冬日绝景_纯涨粉系列/下集_第5至第1名"

build_pipeline_draft(ep1_dir, draft_name="【十大冬日绝景_上集_第10至第6名】")
build_pipeline_draft(ep2_dir, draft_name="【十大冬日绝景_下集_第5至第1名】")

# 3. 同步到项目内的 04_剪映草稿工程
print("\n3. 同步草稿工程至本地 04_剪映草稿工程...")
for name, pdir in [
    ("【十大冬日绝景_上集_第10至第6名】", ep1_dir),
    ("【十大冬日绝景_下集_第5至第1名】", ep2_dir)
]:
    src = JIANYING_DIR / name
    dst = pdir / "04_剪映草稿工程"
    dst.mkdir(parents=True, exist_ok=True)
    if src.exists():
        for f in src.iterdir():
            if f.is_file():
                shutil.copy2(f, dst / f.name)
        print(f"  ✓ 已同步: {name} -> {dst.relative_to(ROOT)}")

# 4. 更新剪映 root_meta_info.json，彻底置顶这两个草稿！
print("\n4. 更新剪映索引 root_meta_info.json (将两大草稿强力置顶)...")
if ROOT_META_FILE.exists():
    root_meta = json.loads(ROOT_META_FILE.read_text(encoding="utf-8"))
    store = root_meta.get("all_draft_store", [])
    
    # 过滤掉旧的废弃草稿和当前的草稿
    filtered_store = []
    target_entries = {}
    
    for item in store:
        d_name = item.get("draft_name", "")
        if d_name in OLD_DRAFTS:
            continue
        if d_name in ["【十大冬日绝景_上集_第10至第6名】", "【十大冬日绝景_下集_第5至第1名】"]:
            target_entries[d_name] = item
        else:
            filtered_store.append(item)
            
    now_us = int(time.time() * 1_000_000)
    
    # 为上集准备 entry
    ep1_name = "【十大冬日绝景_上集_第10至第6名】"
    ep1_meta_file = JIANYING_DIR / ep1_name / "draft_meta_info.json"
    ep1_id = "winter_ep1_id"
    if ep1_meta_file.exists():
        try:
            m_data = json.loads(ep1_meta_file.read_text(encoding="utf-8"))
            ep1_id = m_data.get("draft_id", ep1_id)
        except Exception:
            pass
            
    entry_ep1 = target_entries.get(ep1_name, {
        "draft_cloud_capcut_id": "",
        "draft_cloud_last_action_download": False,
        "draft_cloud_purchased": False,
        "draft_cloud_template_id": "",
        "draft_cloud_tutorial_info": "",
        "draft_cloud_videocut_purchase_info": "",
        "draft_cover": str(JIANYING_DIR / ep1_name / "draft_cover.jpg"),
        "draft_fold_path": str(JIANYING_DIR / ep1_name).replace("\\", "/"),
        "draft_id": ep1_id,
        "draft_is_ai_clone_voice": False,
        "draft_is_ai_shorts": False,
        "draft_is_article_videoDraft": False,
        "draft_is_cloud_offline": False,
        "draft_is_pure_text": False,
        "draft_is_source_import": False,
        "draft_is_ai_generating": False,
        "draft_name": ep1_name,
        "draft_new_version": "",
        "draft_removable_storage_device": "",
        "draft_timeline_materials_size": 0,
        "draft_type": "",
        "tm_draft_cloud_completed": "",
        "tm_draft_cloud_modified": 0,
        "tm_draft_create": now_us,
        "tm_draft_modified": now_us + 10_000_000,
        "tm_draft_removed": 0
    })
    entry_ep1["tm_draft_modified"] = now_us + 10_000_000
    entry_ep1["draft_name"] = ep1_name

    # 为下集准备 entry
    ep2_name = "【十大冬日绝景_下集_第5至第1名】"
    ep2_meta_file = JIANYING_DIR / ep2_name / "draft_meta_info.json"
    ep2_id = "winter_ep2_id"
    if ep2_meta_file.exists():
        try:
            m_data = json.loads(ep2_meta_file.read_text(encoding="utf-8"))
            ep2_id = m_data.get("draft_id", ep2_id)
        except Exception:
            pass
            
    entry_ep2 = target_entries.get(ep2_name, {
        "draft_cloud_capcut_id": "",
        "draft_cloud_last_action_download": False,
        "draft_cloud_purchased": False,
        "draft_cloud_template_id": "",
        "draft_cloud_tutorial_info": "",
        "draft_cloud_videocut_purchase_info": "",
        "draft_cover": str(JIANYING_DIR / ep2_name / "draft_cover.jpg"),
        "draft_fold_path": str(JIANYING_DIR / ep2_name).replace("\\", "/"),
        "draft_id": ep2_id,
        "draft_is_ai_clone_voice": False,
        "draft_is_ai_shorts": False,
        "draft_is_article_videoDraft": False,
        "draft_is_cloud_offline": False,
        "draft_is_pure_text": False,
        "draft_is_source_import": False,
        "draft_is_ai_generating": False,
        "draft_name": ep2_name,
        "draft_new_version": "",
        "draft_removable_storage_device": "",
        "draft_timeline_materials_size": 0,
        "draft_type": "",
        "tm_draft_cloud_completed": "",
        "tm_draft_cloud_modified": 0,
        "tm_draft_create": now_us,
        "tm_draft_modified": now_us + 5_000_000,
        "tm_draft_removed": 0
    })
    entry_ep2["tm_draft_modified"] = now_us + 5_000_000
    entry_ep2["draft_name"] = ep2_name

    # 将上集和下集直接插入到列表最前两个
    new_store = [entry_ep1, entry_ep2] + filtered_store
    root_meta["all_draft_store"] = new_store
    ROOT_META_FILE.write_text(json.dumps(root_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ root_meta_info.json 已更新，两大草稿已成功排在第 1、第 2 位！")

print("\n=== 全部重构优化与置顶完成！ ===")
