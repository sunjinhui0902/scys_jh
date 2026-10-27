# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

# Force UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

def audit_project(proj_dir_rel, draft_name):
    proj_dir = Path(proj_dir_rel).resolve()
    manifest_path = proj_dir / 'draft_manifest.json'
    draft_path = Path('C:/Users/Miche/AppData/Local/JianyingPro/User Data/Projects/com.lveditor.draft') / draft_name / 'draft_content.json'
    
    print('='*70)
    print(f'🎬 审计项目: {draft_name}')
    print('='*70)
    
    if not manifest_path.exists():
        print('❌ draft_manifest.json 不存在')
        return
    if not draft_path.exists():
        print('❌ draft_content.json 不存在')
        return
        
    m = json.loads(manifest_path.read_text(encoding='utf-8'))
    d = json.loads(draft_path.read_text(encoding='utf-8'))
    
    print(f'草稿标题: {m.get("draft_title")}')
    print(f'发音对齐: {m.get("alignment_mode")}')
    print(f'音频总长: {m.get("total_dur_us") / 1_000_000:.2f} 秒')
    print(f'分镜数量: {len(m.get("sections", []))}')
    
    tracks = d.get('tracks', [])
    print(f'轨道总数: {len(tracks)}')
    for idx, t in enumerate(tracks):
        t_type = t.get('type')
        seg_count = len(t.get('segments', []))
        print(f'  轨道 {idx+1}: [{t_type}] 片段数={seg_count}')
        
    shots = m.get('shots', [])
    real_count = sum(1 for s in shots if not s.get('is_placeholder'))
    print(f'素材就绪: {real_count}/{len(shots)}')
    for s in shots:
        img_p = Path(s.get('current_image'))
        exists = img_p.exists()
        dur_s = s.get('duration_us') / 1_000_000
        print(f'  - 镜头 {s["shot_index"]:02d}: {img_p.name} | 时长={dur_s:.2f}s | 运镜={s.get("motion")} | 状态={"✓ 正常" if exists else "❌ 缺失"}')

if __name__ == "__main__":
    audit_project('03_视频成片与工程/十大冬日绝景_纯涨粉系列/上集_第10至第6名', '【十大冬日绝景_上集_第10至第6名】')
    print()
    audit_project('03_视频成片与工程/十大冬日绝景_纯涨粉系列/下集_第5至第1名', '【十大冬日绝景_下集_第5至第1名】')
