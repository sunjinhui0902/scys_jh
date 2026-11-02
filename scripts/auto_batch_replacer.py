import os
import sys
import time
import json
import re
import shutil
import argparse
import subprocess
from pathlib import Path

# UTF-8 编码安全保障
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path("d:/fuye")
PROJ_ROOT = ROOT / "03_视频成片与工程"
sys.path.insert(0, str(ROOT / "scripts"))

ALL_FOLDERS = [
    # 批次 1 (11-03)
    "M1_11-03_0700", "N1_11-03_1230", "W1_11-03_1900",
    # 批次 2 (11-04)
    "M6_11-04_0700", "N2_11-04_1230", "W2_11-04_1900",
    # 批次 3 (11-05)
    "M4_11-05_0700", "N3_11-05_1230", "W3_11-05_1900",
    # 批次 4 (11-06)
    "M2_11-06_0700", "N4_11-06_1230", "W4_11-06_1900",
    # 批次 5 (11-07)
    "M5_11-07_0700", "N5_11-07_1230", "W5_11-07_1900",
    # 批次 6 (11-08)
    "M3_11-08_0700", "N6_11-08_1230", "W6_11-08_1900",
    # 批次 7 (11-09)
    "M7_11-09_0700", "N7_11-09_1230", "W7_11-09_1900"
]

def scan_and_sync_external_images():
    """扫描可能的新图片存放位置（如出图批次目录、Google云盘等），自动同步落位到工程目录"""
    # 检查 03_视频成片与工程 下的所有出图批次目录
    candidate_roots = [PROJ_ROOT, Path("G:/我的云端硬盘/视频号第一周")]
    new_found = 0
    
    for c_root in candidate_roots:
        if not c_root.exists():
            continue
        # 寻找包含 shot_xx.png 且在包含编号目录下的文件
        for root, dirs, files in os.walk(c_root):
            # 避免将本工程内部自己复制给自己
            if "03_视频成片与工程" in root and any(f"/{f}/" in root.replace("\\", "/") or root.endswith(f) for f in ALL_FOLDERS):
                continue
            
            for file in files:
                if file.lower().startswith("shot_") and file.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    # 尝试从路径或文件名推断归属项目编号
                    m = re.search(r"\b([MNW][1-7])\b", root)
                    if m:
                        code = m.group(1)
                        # 找到对应的主工程目录
                        matching_folders = [f for f in ALL_FOLDERS if f.startswith(f"{code}_")]
                        if matching_folders:
                            target_proj = PROJ_ROOT / matching_folders[0] / "02_分镜视觉素材"
                            target_proj.mkdir(parents=True, exist_ok=True)
                            target_file = target_proj / file
                            src_file = Path(root) / file
                            if not target_file.exists() or target_file.stat().st_size != src_file.stat().st_size:
                                shutil.copy2(src_file, target_file)
                                new_found += 1
                                print(f"  [发现外部新素材] 同步 {file} -> {target_proj.parent.name}")
    return new_found

def check_and_update_all_projects():
    """检查全部 21 条工程，若有未热替换的真实图片则执行 apply-images，若 6 镜全齐且无成片则执行成片渲染"""
    sync_count = scan_and_sync_external_images()
    
    total_completed_renders = 0
    total_ready_drafts = 0
    summary = []
    
    for folder in ALL_FOLDERS:
        proj_dir = PROJ_ROOT / folder
        manifest_file = proj_dir / "draft_manifest.json"
        
        if not manifest_file.exists():
            summary.append({
                "folder": folder,
                "status": "DRAFT_NOT_INITIALIZED",
                "real_images": 0,
                "has_video": False
            })
            continue
        
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        shots = manifest.get("shots", [])
        placeholders_count = sum(1 for s in shots if s.get("is_placeholder", True))
        real_count = len(shots) - placeholders_count
        
        # 扫描 02_分镜视觉素材 看看是否有新放入的真实图片
        visuals_dir = proj_dir / "02_分镜视觉素材"
        available_real_imgs = []
        if visuals_dir.exists():
            for p in visuals_dir.iterdir():
                if p.is_file() and p.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"] and "placeholder" not in p.name.lower() and not p.name.startswith("preview"):
                    available_real_imgs.append(p)
        
        # 如果素材库中的真实图片数量大于草稿中记录的真实图片数量，触发热替换
        if len(available_real_imgs) > real_count:
            print(f"\n🔄 检测到新素材就位: {folder} (素材库已有 {len(available_real_imgs)}/6 张真实图片)，执行热替换...")
            cmd_apply = [sys.executable, str(ROOT / "scripts" / "fast_draft_pipeline.py"), "apply-images", "--dir", str(proj_dir)]
            subprocess.run(cmd_apply, check=True)
            
            # 重新读取 manifest
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            shots = manifest.get("shots", [])
            placeholders_count = sum(1 for s in shots if s.get("is_placeholder", True))
            real_count = len(shots) - placeholders_count
        
        # 检查是否已导出成品 MP4
        render_dir = proj_dir / "05_成片"
        mp4_files = list(render_dir.glob("*.mp4")) if render_dir.exists() else []
        has_video = len(mp4_files) > 0
        
        # 如果 6 镜全部齐备（0 占位图），但尚未导出成品 MP4，自动触发渲染
        if placeholders_count == 0 and not has_video:
            print(f"\n🎬 6 镜真实画面已全部就绪！自动启动成片渲染: {folder} ...")
            try:
                from render_final_video import render_project
                out_name = f"{folder.split('_')[0]}_{manifest.get('draft_title', folder).replace('【图书带货】', '').strip()}_成片.mp4"
                # 清洗文件名特殊字符
                out_name = re.sub(r'[\\/:*?"<>|]+', '_', out_name)
                out_mp4 = render_dir / out_name
                render_project(proj_dir, out_mp4)
                has_video = True
            except Exception as e:
                print(f"⚠️ 渲染成片失败: {e}")
        
        if has_video:
            total_completed_renders += 1
        if placeholders_count == 0:
            total_ready_drafts += 1
        
        status_label = "成片就绪" if has_video else ("素材就绪待渲染" if placeholders_count == 0 else f"等生图中({real_count}/6)")
        summary.append({
            "folder": folder,
            "code_id": folder.split("_")[0],
            "title": manifest.get("draft_title", "").replace("【图书带货】", "").strip(),
            "real_images": real_count,
            "placeholders": placeholders_count,
            "has_video": has_video,
            "status": status_label
        })
    
    # 保存最新状态看板
    state_file = PROJ_ROOT / "auto_replace_state.json"
    state_data = {
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_projects": len(ALL_FOLDERS),
        "total_ready_drafts": total_ready_drafts,
        "total_completed_renders": total_completed_renders,
        "is_all_finished": total_completed_renders == len(ALL_FOLDERS),
        "projects": summary
    }
    state_file.write_text(json.dumps(state_data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    print("\n========================================================")
    print(f"📊 [巡检状态概览] 成品视频就绪: {total_completed_renders}/21 | 草稿真实画面就绪: {total_ready_drafts}/21")
    print(f"========================================================")
    for s in summary:
        print(f"  {s['code_id']:4s} | {s['folder']:15s} | 真实画面: {s['real_images']}/6 | {s['status']}")
    
    return state_data

def run_daemon(interval_sec: int = 3600):
    print(f"🚀 启动自动巡检守护进程 (每隔 {interval_sec} 秒检查一次)...")
    cycle = 1
    while True:
        print(f"\n--- 周期 #{cycle} 开始检查 [{time.strftime('%Y-%m-%d %H:%M:%S')}] ---")
        state = check_and_update_all_projects()
        if state["is_all_finished"]:
            print("🎉 全部 21 条视频已 100% 制作完成并导出成片！任务顺利结束。")
            break
        print(f"--- 周期 #{cycle} 结束，等待 {interval_sec} 秒后下一次巡检 ---")
        time.sleep(interval_sec)
        cycle += 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto Batch Replacer & Video Exporter")
    parser.add_argument("--scan-once", action="store_true", help="立即执行一次巡检与更新")
    parser.add_argument("--daemon", action="store_true", help="启动常驻定时巡检守护进程")
    parser.add_argument("--interval", type=int, default=3600, help="轮询间隔秒数 (默认3600秒)")
    args = parser.parse_args()
    
    if args.daemon:
        run_daemon(args.interval)
    else:
        check_and_update_all_projects()
