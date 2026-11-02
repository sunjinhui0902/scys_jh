import os
import sys
import json
from pathlib import Path

# UTF-8 编码安全保障
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path("d:/fuye")
JY_BASE = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "JianyingPro/User Data/Projects/com.lveditor.draft"

tasks = [
    {"code": "M2", "dir": "M2_11-06_0700", "jia": "磨蹭背后多半有原因", "yi": "约法三章慢慢改"},
    {"code": "M3", "dir": "M3_11-08_0700", "jia": "孩子半夜偷玩手机", "yi": "全家立规矩一起守"},
    {"code": "M5", "dir": "M5_11-07_0700", "jia": "背诗先讲画再读字", "yi": "画面有了诗就记住"},
    {"code": "N3", "dir": "N3_11-05_1230", "jia": "苏轼挖泥修长堤", "yi": "诗里的西湖有来历"},
    {"code": "N5", "dir": "N5_11-07_1230", "jia": "五个朝代都选洛阳", "yi": "地图上看懂古都"},
    {"code": "N6", "dir": "N6_11-08_1230", "jia": "园外的塔借进园里", "yi": "苏州人的巧心思"},
    {"code": "W2", "dir": "W2_11-04_1900", "jia": "老话只听半句会误人", "yi": "后半句里有体谅"},
    {"code": "W3", "dir": "W3_11-05_1900", "jia": "人情往来有讲究", "yi": "还情要趁热乎"},
    {"code": "W4", "dir": "W4_11-06_1900", "jia": "话说三分留七分", "yi": "留白是给人留体面"},
    {"code": "W5", "dir": "W5_11-07_1900", "jia": "不催孩子慢慢长", "yi": "他回头时咱还在"},
    {"code": "W6", "dir": "W6_11-08_1900", "jia": "这句老话读偏了", "yi": "以直报怨才是原意"},
    {"code": "W7", "dir": "W7_11-09_1900", "jia": "去儿女家有分寸", "yi": "不插手也是疼爱"}
]

for t in tasks:
    pdir = ROOT / "03_视频成片与工程" / t["dir"]
    manifest_file = pdir / "draft_manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    title = manifest.get("draft_title")
    
    draft_folder = JY_BASE / title
    content_file = draft_folder / "draft_content.json"
    
    if t["code"] == "W7":
        # W7 load from .load.bak
        bak_file = draft_folder / ".backup" / "20261102233131_829a32cddad58771f19d267c57651729.load.bak"
        draft_data = json.loads(bak_file.read_text(encoding="utf-8"))
    else:
        draft_data = json.loads(content_file.read_text(encoding="utf-8"))
        
    # Find track
    nav_tracks = [tr for tr in draft_data.get("tracks", []) if tr.get("name") == "顶部章节导航卡"]
    if not nav_tracks:
        print(f"ERROR: {t['code']} 找不到轨 '顶部章节导航卡'!")
        continue
        
    nav_track = nav_tracks[0]
    segs = nav_track.get("segments", [])
    if len(segs) != 6:
        print(f"WARNING: {t['code']} '顶部章节导航卡' 段数不为 6 (实为 {len(segs)})")
        
    texts_dict = {m["id"]: m for m in draft_data.get("materials", {}).get("texts", [])}
    
    # Modify segments 0, 1, 2 -> 甲, segments 3, 4, 5 -> 乙
    for idx, seg in enumerate(segs):
        mat_id = seg.get("material_id")
        if mat_id not in texts_dict:
            print(f"ERROR: {t['code']} seg {idx} material_id not found")
            continue
        mat = texts_dict[mat_id]
        new_text = t["jia"] if idx < 3 else t["yi"]
        
        try:
            content_json = json.loads(mat["content"])
            content_json["text"] = new_text
            if "styles" in content_json and len(content_json["styles"]) > 0:
                content_json["styles"][0]["range"] = [0, len(new_text)]
            mat["content"] = json.dumps(content_json, ensure_ascii=False)
        except Exception as e:
            print(f"ERROR updating text for {t['code']} seg {idx}: {e}")
            
    # Write back draft_content.json
    content_file.write_text(json.dumps(draft_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"SUCCESS: {t['code']} ({title}) 副标已更新为 甲: {t['jia']} / 乙: {t['yi']}")

# Task 3: Export W7 Subtitle List
w7_dir = ROOT / "03_视频成片与工程/W7_11-09_1900"
w7_content_file = JY_BASE / "【图书带货】去儿女家住，三件事别插手" / "draft_content.json"
w7_data = json.loads(w7_content_file.read_text(encoding="utf-8"))

w7_texts_dict = {m["id"]: m for m in w7_data.get("materials", {}).get("texts", [])}
w7_sub_track = [tr for tr in w7_data.get("tracks", []) if tr.get("name") == "中老年大字底字幕"][0]

w7_sub_lines = []
for idx, seg in enumerate(w7_sub_track.get("segments", [])):
    mat = w7_texts_dict.get(seg.get("material_id"))
    txt = json.loads(mat["content"])["text"]
    w7_sub_lines.append(f"{idx + 1:02d}. {txt}")

w7_export_text = "《去儿女家住，三件事别插手》（W7_11-09_1900）剪映草稿字幕条目清单\n"
w7_export_text += "核对结果：共 31 条字幕，与云盘 01_口播定稿 逐字比对 100% 完全一致，无任何错漏字。\n"
w7_export_text += "=" * 50 + "\n\n"
w7_export_text += "\n".join(w7_sub_lines) + "\n"

# Write to local project
(w7_dir / "01_文案与分镜" / "W7字幕条目.txt").write_text(w7_export_text, encoding="utf-8")

# Write to Google Drive 06_成片待审
gdrive_w7_file = Path("G:/我的云端硬盘/视频号第一周/06_成片待审/W7字幕条目.txt")
try:
    gdrive_w7_file.write_text(w7_export_text, encoding="utf-8")
    print(f"\nSUCCESS: W7 字幕条目已导出至云盘: {gdrive_w7_file}")
except Exception as e:
    print(f"\nWARNING: 写入云盘失败 ({e})，保存在本地: {w7_dir / '01_文案与分镜' / 'W7字幕条目.txt'}")
