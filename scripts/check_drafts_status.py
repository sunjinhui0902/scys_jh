# -*- coding: utf-8 -*-
import os
import json
import time
from pathlib import Path

def check():
    base_dir = Path("03_视频成片与工程")
    draft_root = Path(os.environ.get("LOCALAPPDATA", "")) / "JianyingPro" / "User Data" / "Projects" / "com.lveditor.draft"
    
    proj_dirs = sorted([d for d in base_dir.iterdir() if d.is_dir() and d.name[:2] in ["01", "02", "03", "04", "05"] and "精讲" in d.name])
    
    results = []
    for proj_dir in proj_dirs:
        voice_files = list(proj_dir.glob("**/voice_master.mp3"))
        voice_path = voice_files[0] if voice_files else None
        
        manifest_path = proj_dir / "draft_manifest.json"
        
        man_data = {}
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                man_data = json.load(f)
                
        draft_title = man_data.get("draft_title", "UNKNOWN")
        draft_dir = draft_root / draft_title if draft_title != "UNKNOWN" else None
        draft_json = draft_dir / "draft_content.json" if draft_dir else None
        
        info = {
            "project_folder": proj_dir.name,
            "draft_title": draft_title,
            "voice_file": str(voice_path) if voice_path else None,
            "voice_size": voice_path.stat().st_size if voice_path else 0,
            "voice_mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(voice_path.stat().st_mtime)) if voice_path else None,
            "draft_exists": draft_dir.exists() if draft_dir else False,
            "audios_in_draft": [],
            "video_segments": 0,
            "subtitles_count": 0,
            "fixed_assets_bound": [],
            "bgm_volume": []
        }
        
        if draft_json and draft_json.exists():
            with open(draft_json, "r", encoding="utf-8") as f:
                d = json.load(f)
            materials = d.get("materials", {})
            info["audios_in_draft"] = [a.get("name") for a in materials.get("audios", [])]
            videos = materials.get("videos", [])
            info["video_segments"] = len(videos)
            for v in videos:
                p = v.get("path", "")
                if "book_01" in p or "book_02" in p or "book_03" in p:
                    info["fixed_assets_bound"].append(os.path.basename(p))
            info["subtitles_count"] = len(materials.get("texts", []))
            
            # check bgm volume
            for t in d.get("tracks", []):
                if t.get("type") == "audio":
                    for seg in t.get("segments", []):
                        vol = seg.get("volume")
                        mat_id = seg.get("material_id")
                        mat_name = next((a.get("name") for a in materials.get("audios", []) if a.get("id") == mat_id), "unknown")
                        if "bgm" in mat_name:
                            info["bgm_volume"].append(f"{mat_name}: vol={vol}")
                            break
            
        results.append(info)
        
    for r in results:
        print("==================================================")
        print(f"项目文件夹: {r['project_folder']}")
        print(f"剪映草稿标题: {r['draft_title']}")
        print(f"配音文件: {r['voice_size']} 字节 (生成时间: {r['voice_mtime']})")
        print(f"草稿状态: 存在={r['draft_exists']}, 视频片段={r['video_segments']}, 字幕条数={r['subtitles_count']}")
        print(f"草稿音频轨: {r['audios_in_draft']}")
        print(f"BGM 音量设置: {r['bgm_volume']}")
        print(f"已自动绑定的固定书本实拍图: {r['fixed_assets_bound']}")

if __name__ == "__main__":
    check()
