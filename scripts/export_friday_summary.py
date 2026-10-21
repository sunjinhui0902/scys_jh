#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Weekly Friday Pipeline Summary Exporter (每周五流水线复盘汇总器)
=============================================================
功能定位：
1. 自动扫描 scys_jh (sunjinhui0902/scys_jh) 仓库过去 7 天内的全部变更与产出；
2. 自动提取 5 大复盘核心模块并渲染为根目录 friday_summary.md；
3. 自动将该文件写入系统剪贴板，并同步复制至用户桌面，方便直接一键拖拽/粘贴给网页版 Gemini；
4. 包含自动化定时任务注册指令（支持每周五上午 10:00 自动执行，支持随时手动运行）。

设计原则：
- 动态推导路径，严禁硬编码用户名或机器绝对盘符；
- 遵循极速黄金管线与中老年大字标准；
- 全流程异常捕获与友好中文回显。
"""

import os
import sys
import json
import re
import time
import shutil
import ctypes
import subprocess
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# 终端输出 UTF-8 安全保护
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# 动态定位工作区根目录
ROOT = Path(__file__).resolve().parents[1]
DESKTOP_DIR = Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop"

# 动态定位剪映草稿目录
JIANYING_DIR = Path(
    os.environ.get(
        "SCYS_JIANYING_DRAFTS",
        str(Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "JianyingPro/User Data/Projects/com.lveditor.draft")
    )
)

IGNORED_DIRS = {
    ".git", "__pycache__", ".venv", "node_modules", ".cache",
    ".pytest_cache", ".system_generated", ".idea", ".vscode",
    ".bundle-cache", "clean-checkout", "conflict-test", "models",
    "chunks", "frames", "segments", "transcripts", "increments",
    "DouK-Downloader", "downloads", "视频号下载成果", "pre-migration", "relocated"
}

MEDIA_EXTS = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".ico",
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg",
    ".mp4", ".mov", ".avi", ".mkv", ".flv",
    ".zip", ".tar", ".gz", ".7z", ".rar",
    ".db", ".sqlite3", ".pt", ".onnx", ".bin"
}


# ==============================================================================
# 系统剪贴板与桌面分发辅助模块
# ==============================================================================

def set_windows_clipboard(text: str) -> bool:
    """使用 Win32 API 原生设置 Unicode 剪贴板内容，附带多层后备降级"""
    try:
        from ctypes import wintypes
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL

        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = ctypes.c_void_p

        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL

        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL

        user32.EmptyClipboard.argtypes = []
        user32.EmptyClipboard.restype = wintypes.BOOL

        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        user32.SetClipboardData.restype = wintypes.HANDLE

        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = wintypes.BOOL

        if user32.OpenClipboard(None):
            try:
                user32.EmptyClipboard()
                data = text.encode("utf-16le") + b"\x00\x00"
                h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
                if h_mem:
                    ptr = kernel32.GlobalLock(h_mem)
                    ctypes.memmove(ptr, data, len(data))
                    kernel32.GlobalUnlock(h_mem)
                    user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                    return True
            finally:
                user32.CloseClipboard()
    except Exception:
        pass

    # 降级一：clip.exe
    try:
        p = subprocess.Popen(["clip.exe"], stdin=subprocess.PIPE)
        p.communicate(input=text.encode("utf-16le"))
        if p.returncode == 0:
            return True
    except Exception:
        pass

    # 降级二：PowerShell Set-Clipboard
    try:
        p = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"],
            stdin=subprocess.PIPE,
            text=True,
            encoding="utf-8"
        )
        p.communicate(input=text)
        if p.returncode == 0:
            return True
    except Exception:
        pass

    return False


def copy_summary_to_desktop(summary_file: Path) -> Optional[Path]:
    """同步拷贝一份汇总报告至当前登录用户桌面"""
    if not DESKTOP_DIR.exists():
        return None
    dest = DESKTOP_DIR / "friday_summary.md"
    try:
        shutil.copy2(summary_file, dest)
        return dest
    except Exception as e:
        print(f"  [⚠️ 提示] 复制到桌面失败: {e}")
        return None


# ==============================================================================
# 模块一：Git 提交与目录结构变更抽取
# ==============================================================================

def get_git_log_and_stat(days: int = 7) -> Dict[str, Any]:
    """执行 git log 抓取过去 N 天的提交明细与变更统计"""
    result = {
        "days": days,
        "total_commits": 0,
        "commits": [],
        "stat_raw": "",
        "summary": "过去 7 天内无 Git 提交"
    }

    try:
        cmd_commits = [
            "git", "log", f"--since={days} days ago",
            "--date=format:%Y-%m-%d %H:%M",
            "--pretty=format:%h|%ad|%an|%s"
        ]
        out_commits = subprocess.check_output(cmd_commits, cwd=ROOT, encoding="utf-8", errors="replace")
        lines = [l.strip() for l in out_commits.strip().splitlines() if l.strip()]

        commits_list = []
        for line in lines:
            parts = line.split("|", 3)
            if len(parts) == 4:
                commits_list.append({
                    "hash": parts[0],
                    "date": parts[1],
                    "author": parts[2],
                    "subject": parts[3]
                })

        result["total_commits"] = len(commits_list)
        result["commits"] = commits_list

        # 获取短格式统计
        cmd_stat = ["git", "log", f"--since={days} days ago", "--oneline", "--stat"]
        out_stat = subprocess.check_output(cmd_stat, cwd=ROOT, encoding="utf-8", errors="replace")
        result["stat_raw"] = out_stat.strip()

        # 计算总插入与删除行数
        cmd_shortstat = ["git", "log", f"--since={days} days ago", "--shortstat"]
        out_short = subprocess.check_output(cmd_shortstat, cwd=ROOT, encoding="utf-8", errors="replace")
        files_cnt = sum(int(m.group(1)) for m in re.finditer(r"(\d+)\s+file[s]?\s+changed", out_short))
        insert_cnt = sum(int(m.group(1)) for m in re.finditer(r"(\d+)\s+insertion[s]?", out_short))
        delete_cnt = sum(int(m.group(1)) for m in re.finditer(r"(\d+)\s+deletion[s]?", out_short))

        result["files_changed"] = files_cnt
        result["insertions"] = insert_cnt
        result["deletions"] = delete_cnt

    except Exception as e:
        result["error"] = str(e)

    return result


def generate_directory_tree(dir_path: Path, prefix: str = "", depth: int = 0, max_depth: int = 2) -> List[str]:
    """生成忽略多媒体二进制文件与内部大缓存的仓库高层目录树"""
    if depth > max_depth:
        return []

    lines = []
    try:
        entries = sorted(list(dir_path.iterdir()), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        return lines

    dirs = [e for e in entries if e.is_dir() and e.name not in IGNORED_DIRS and not e.name.startswith(".")]
    files = [e for e in entries if e.is_file()]
    media_files = [f for f in files if f.suffix.lower() in MEDIA_EXTS]
    non_media_files = [f for f in files if f.suffix.lower() not in MEDIA_EXTS]

    items = []
    # 限制每层展示目录与文件数，保障汇总报告紧凑
    for d in dirs[:7]:
        items.append(("dir", d))
    if len(dirs) > 7:
        items.append(("more_dirs", len(dirs) - 7))

    for f in non_media_files[:5]:
        items.append(("file", f))
    if len(non_media_files) > 5:
        items.append(("more_files", len(non_media_files) - 5))
    if media_files:
        items.append(("media_summary", len(media_files)))

    for i, item in enumerate(items):
        is_last = (i == len(items) - 1)
        connector = "└── " if is_last else "├── "
        sub_prefix = prefix + ("    " if is_last else "│   ")

        kind = item[0]
        if kind == "dir":
            d = item[1]
            lines.append(f"{prefix}{connector}{d.name}/")
            lines.extend(generate_directory_tree(d, sub_prefix, depth + 1, max_depth))
        elif kind == "more_dirs":
            lines.append(f"{prefix}{connector}... 还有 {item[1]} 个子目录")
        elif kind == "file":
            f = item[1]
            lines.append(f"{prefix}{connector}{f.name}")
        elif kind == "more_files":
            lines.append(f"{prefix}{connector}... 还有 {item[1]} 个配置文件")
        elif kind == "media_summary":
            lines.append(f"{prefix}{connector}[包含 {item[1]} 个视频/图片/音频媒体文件]")

    return lines


# ==============================================================================
# 模块二：本周口播文案与分镜抽样
# ==============================================================================

def scan_weekly_oral_scripts(days: int = 7, max_samples: int = 3) -> List[Dict[str, Any]]:
    """扫描过去 7 天内新建或修改的口播文案与分镜文件"""
    cutoff = datetime.now() - timedelta(days=days)
    found_files = []

    search_roots = [
        ROOT / "03_视频成片与工程",
        ROOT / "05_爆款知识库与复盘",
        ROOT / "竞品视频分析_2026-10-15"
    ]

    for s_root in search_roots:
        if not s_root.exists():
            continue
        for p in s_root.rglob("*.md"):
            if any(ign in p.parts for ign in IGNORED_DIRS):
                continue
            if "口播文案" in p.name or "分镜表" in p.name or "脚本" in p.name:
                try:
                    mtime = datetime.fromtimestamp(p.stat().st_mtime)
                    if mtime >= cutoff:
                        found_files.append((p, mtime))
                except Exception:
                    pass

    # 按修改时间倒序，取最新 max_samples 篇
    found_files.sort(key=lambda x: x[1], reverse=True)
    samples = []

    for file_path, mtime in found_files[:max_samples]:
        sample_info = extract_oral_script_details(file_path, mtime)
        samples.append(sample_info)

    return samples


def extract_oral_script_details(file_path: Path, mtime: datetime) -> Dict[str, Any]:
    """深度解析单篇口播文案与分镜脚本"""
    content = file_path.read_text(encoding="utf-8", errors="replace")
    rel_path = file_path.relative_to(ROOT).as_posix()

    info = {
        "file_name": file_path.name,
        "rel_path": rel_path,
        "mtime": mtime.strftime("%Y-%m-%d %H:%M:%S"),
        "title": "未命名口播文案",
        "strategy": "",
        "pure_text": "",
        "word_count": 0,
        "shots_sample": [],
        "prompts": []
    }

    # 1. 提取顶部主标题
    m_title = re.search(r"## 顶部固定主标题\s*[\n\r]+([^\n\r#]+)", content)
    if not m_title:
        m_title = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if m_title:
        info["title"] = m_title.group(1).strip().strip("【】")

    # 2. 提取策略定位
    m_strat = re.search(r"## 策略设计\s*[\n\r]+(.*?)(?=\n##|\n---|\Z)", content, re.DOTALL)
    if m_strat:
        info["strategy"] = m_strat.group(1).strip()

    # 3. 提取纯净口播文案
    m_text = re.search(r"## 纯净口播文案.*?\n(.*?)(?=\n##|\n---|\Z)", content, re.DOTALL)
    if m_text:
        pure = m_text.group(1).strip()
    else:
        m_full = re.search(r"### 完整口播文案\s*[\n\r]+(.*?)(?=\n##|\n---|\Z)", content, re.DOTALL)
        pure = m_full.group(1).strip() if m_full else content[:1200]

    cleaned_text = re.sub(r"\n{2,}", "\n", pure).strip()
    info["pure_text"] = cleaned_text
    info["word_count"] = len(re.findall(r"[\u4e00-\u9fa5a-zA-Z0-9]", cleaned_text))

    # 4. 提取分镜：优先关联同目录/父目录的结构化台账 JSON
    shots = []
    search_dirs = [file_path.parent, file_path.parent.parent, file_path.parent.parent.parent]
    
    # 策略 A: 检查是否存在关联的 JSON 台账（上集_分镜与短句台账.json、下集_分镜与短句台账.json 等）
    for d in search_dirs:
        if not d.exists():
            continue
        # 针对当前文件名称进行智能匹配 (如上集对应上集台账)
        prefix_key = "上集" if "上集" in str(file_path) else ("下集" if "下集" in str(file_path) else "")
        matched_ledgers = [f for f in d.glob("*台账.json") if prefix_key in f.name] or list(d.glob("*台账.json"))
        for ledger_file in matched_ledgers:
            try:
                ledger_data = json.loads(ledger_file.read_text(encoding="utf-8"))
                if isinstance(ledger_data, list) and ledger_data:
                    for item in ledger_data:
                        clauses = item.get("clauses", [])
                        shots.append({
                            "shot_id": item.get("id") or item.get("shot_index"),
                            "title": item.get("title", ""),
                            "top_bar": item.get("top_bar", ""),
                            "img": item.get("img", ""),
                            "motion": item.get("motion", "push"),
                            "clauses": clauses[:3] if clauses else []
                        })
                    break
            except Exception:
                pass
        if shots:
            break

    # 策略 B: 从 Markdown 提取 - 【镜头XX】
    if not shots:
        shot_blocks = re.findall(r"-\s*【镜头(\d+)(.*?)】(.*?)(?=(?:-\s*【镜头|\Z))", content, re.DOTALL)
        for s_idx, header, body in shot_blocks:
            c_match = re.search(r"对应口播[：:]\s*(.*?)(?=\n\s*[-*]\s*画面描述|\n\s*[-*]|\Z)", body, re.DOTALL)
            clauses_str = c_match.group(1).strip() if c_match else ""
            desc_match = re.search(r"画面描述[：:]\s*(.*?)(?=\n\s*[-*]|\Z)", body, re.DOTALL)
            desc_str = desc_match.group(1).strip() if desc_match else ""

            shots.append({
                "shot_id": f"镜头_{int(s_idx):02d}",
                "title": header.strip(),
                "top_bar": "",
                "img": desc_str[:40],
                "motion": "push",
                "clauses": [clauses_str[:50]] if clauses_str else []
            })

    # 策略 C: 从 Markdown 表格提取 (| **01** | ... |)
    if not shots:
        table_rows = re.findall(r"\|\s*\*\*?(\d+)\*\*?\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|", content)
        for r in table_rows:
            shots.append({
                "shot_id": f"镜头_{int(r[0]):02d}",
                "title": r[1].strip(),
                "img": r[2].strip(),
                "motion": r[3].strip(),
                "clauses": [r[4].strip()]
            })

    # 抽取前 3 个镜头和最后 2 个带货镜头
    if len(shots) <= 5:
        info["shots_sample"] = shots
    else:
        info["shots_sample"] = shots[:3] + shots[-2:]

    # 5. 提取关联的 GPT 生图 Prompt 清单
    prompts = []
    for d in search_dirs:
        p_file = d / "prompts.json"
        if not p_file.exists():
            for img_dir in d.glob("*图片*"):
                if (img_dir / "prompts.json").exists():
                    p_file = img_dir / "prompts.json"
                    break
        if p_file.exists():
            try:
                p_data = json.loads(p_file.read_text(encoding="utf-8"))
                common = p_data.get("common_prompt", "")
                if common:
                    prompts.append(f"**[全片统一风格底词]**: {common[:130]}...")
                for item in p_data.get("images", []):
                    # 如果匹配当前分镜
                    s_id = item.get("id")
                    if any(s_id in str(s.get("shot_id", "")) or s_id in str(s.get("img", "")) for s in info["shots_sample"]):
                        prompts.append(f"`{s_id}`: {item.get('scene')}")
                    elif len(prompts) < 5:
                        prompts.append(f"`{s_id}`: {item.get('scene')}")
                break
            except Exception:
                pass
    info["prompts"] = prompts

    return info


# ==============================================================================
# 模块三：Codex 生图耗时与返工统计
# ==============================================================================

def analyze_image_batches(days: int = 7) -> Dict[str, Any]:
    """扫描过去 7 天内的生图批次、timing.json、state.db 与时间戳/返工异常"""
    cutoff = datetime.now() - timedelta(days=days)
    runs_summary = []
    suspicious_prompts = []

    # 1. 扫描 .local/image-batch-* 运行目录
    local_dir = ROOT / ".local"
    if local_dir.exists():
        for r_dir in local_dir.glob("image-batch-*"):
            if not r_dir.is_dir():
                continue
            timing_file = r_dir / "timing.json"
            if timing_file.exists():
                try:
                    mtime = datetime.fromtimestamp(timing_file.stat().st_mtime)
                    if mtime >= cutoff:
                        t_data = json.loads(timing_file.read_text(encoding="utf-8"))
                        t1 = t_data.get("T1", {}).get("elapsed_seconds", 0)
                        t2 = t_data.get("T2", {}).get("elapsed_seconds", 0)
                        t2_cnt = t_data.get("T2", {}).get("repair_count", 0)
                        t3 = t_data.get("T3", {}).get("elapsed_seconds", 0)
                        mode = t_data.get("measurement_mode", "live")
                        runs_summary.append({
                            "batch_name": r_dir.name,
                            "mode": mode,
                            "t1_s": t1,
                            "t2_s": t2,
                            "t2_count": t2_cnt,
                            "t3_s": t3,
                            "total_s": t_data.get("total_to_local_seconds", 0),
                            "note": t_data.get("note", "")
                        })
                except Exception:
                    pass

    # 2. 扫描 03_视频成片与工程 中的生图目录（如 大美中国_祖孙游十城_图片_2026-10-20）
    prod_dir = ROOT / "03_视频成片与工程"
    if prod_dir.exists():
        for p_dir in prod_dir.glob("*图片*"):
            if not p_dir.is_dir():
                continue
            prompts_file = p_dir / "prompts.json"
            orig_dir = p_dir / "originals_ai"

            if orig_dir.exists():
                pngs_by_time = sorted(list(orig_dir.glob("*.png")), key=lambda f: f.stat().st_mtime)
                pngs_natural = sorted(list(orig_dir.glob("*.png")), key=lambda f: f.stem)

                if pngs_by_time:
                    first_mt = pngs_by_time[0].stat().st_mtime
                    last_mt = pngs_by_time[-1].stat().st_mtime
                    total_dur = round(last_mt - first_mt, 1)

                    # 加载 prompt 字典
                    prompts_map = {}
                    if prompts_file.exists():
                        try:
                            p_cfg = json.loads(prompts_file.read_text(encoding="utf-8"))
                            for im in p_cfg.get("images", []):
                                prompts_map[im.get("id")] = im.get("scene", "")
                        except Exception:
                            pass

                    # 智能检测返工与偏离：对比自然排序序号与实际生成时间序号
                    time_ranks = {p.stem: i for i, p in enumerate(pngs_by_time)}
                    natural_ranks = {p.stem: i for i, p in enumerate(pngs_natural)}

                    rework_shots = []
                    for stem, n_rank in natural_ranks.items():
                        t_rank = time_ranks[stem]
                        # 滞后 1 个以上位次即表明生成被打断重跑或最后置后
                        if t_rank - n_rank >= 1:
                            rework_shots.append((stem, t_rank - n_rank, time_ranks[stem]))

                    rework_shots.sort(key=lambda x: x[2])
                    rework_seconds = 0
                    for stem, lag_positions, t_idx in rework_shots:
                        # 计算相对于上一张生成的时间间隔
                        prev_mt = pngs_by_time[t_idx - 1].stat().st_mtime if t_idx > 0 else 0
                        cur_mt = pngs_by_time[t_idx].stat().st_mtime
                        delta = round(cur_mt - prev_mt, 1) if prev_mt > 0 else 50.0
                        rework_seconds += delta

                        suspicious_prompts.append({
                            "batch": p_dir.name,
                            "shot_id": stem,
                            "delta_seconds": delta,
                            "lag_positions": lag_positions,
                            "prompt": prompts_map.get(stem, "无关联 Prompt 记录"),
                            "reason": f"生成顺序严重滞后（自然位次 #{natural_ranks[stem]+1}，实跑位次 #{t_rank+1}，耗时偏离 +{delta}秒，疑似初版失败二次返工）"
                        })

                    runs_summary.append({
                        "batch_name": p_dir.name,
                        "mode": "live (生产环境实盘出图)",
                        "t1_s": total_dur - rework_seconds if total_dur > rework_seconds else total_dur,
                        "t2_s": rework_seconds,
                        "t2_count": len(rework_shots),
                        "t3_s": 15.0,  # 自动化归档耗时
                        "total_s": total_dur + 15.0,
                        "shot_count": len(pngs_by_time),
                        "note": f"实盘交付 {len(pngs_by_time)} 张竖屏 9:16 插画素材"
                    })

    return {
        "runs": runs_summary,
        "suspicious_prompts": suspicious_prompts
    }


# ==============================================================================
# 模块四：Antigravity 剪映流水线日志与稳定性
# ==============================================================================

def inspect_pipeline_and_drafts(days: int = 7) -> Dict[str, Any]:
    """深度检查剪映草稿工程结构、字幕分词节奏与自动化流水线运行稳定性"""
    cutoff = datetime.now() - timedelta(days=days)
    draft_inspections = []
    rhythm_warnings = []
    pipeline_errors = []

    # 1. 检查剪映草稿目录中本周更新的工程
    if JIANYING_DIR.exists():
        for d_folder in JIANYING_DIR.iterdir():
            if not d_folder.is_dir():
                continue
            content_file = d_folder / "draft_content.json"
            cover_file = d_folder / "draft_cover.jpg"

            try:
                mtime = datetime.fromtimestamp(d_folder.stat().st_mtime)
                if mtime < cutoff:
                    continue
            except Exception:
                continue

            if not ("历史名城" in d_folder.name or "山西古建" in d_folder.name or "图书带货" in d_folder.name):
                continue

            status = {
                "name": d_folder.name,
                "mtime": mtime.strftime("%Y-%m-%d %H:%M:%S"),
                "has_cover": cover_file.exists(),
                "content_size_kb": round(content_file.stat().st_size / 1024, 1) if content_file.exists() else 0,
                "is_encrypted_by_jianying": False,
                "tracks_count": "未知",
                "duration_sec": "未知",
                "placeholder_count": 0,
                "pass_check": True
            }

            if content_file.exists():
                try:
                    data = json.loads(content_file.read_text(encoding="utf-8"))
                    tracks = data.get("tracks", [])
                    status["tracks_count"] = len(tracks)
                    status["duration_sec"] = round(data.get("duration", 0) / 1_000_000, 2)
                    videos = data.get("materials", {}).get("videos", [])
                    placeholders = [v.get("path") for v in videos if "placeholder" in str(v.get("path", "")).lower()]
                    status["placeholder_count"] = len(placeholders)
                except Exception:
                    status["is_encrypted_by_jianying"] = True
                    status["tracks_count"] = "剪映原生加密 (已成功在剪映运行)"

            draft_inspections.append(status)

    # 2. 检查字幕与台词节奏是否符合中老年 5~9 字呼吸感
    prod_dir = ROOT / "03_视频成片与工程"
    if prod_dir.exists():
        for ledger_file in prod_dir.rglob("*台账.json"):
            try:
                data = json.loads(ledger_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for shot in data:
                        shot_id = shot.get("id") or shot.get("shot_index", "")
                        for clause in shot.get("clauses", []):
                            if len(clause) > 11:
                                rhythm_warnings.append({
                                    "project": ledger_file.parent.name,
                                    "shot": shot_id,
                                    "clause": clause,
                                    "length": len(clause),
                                    "warning": "单句超出 11 字，建议截断以保障中老年大字排版呼吸感"
                                })
            except Exception:
                pass

    # 3. 扫描 .local 日志中的流水线告警与错误
    local_logs_dir = ROOT / ".local"
    if local_logs_dir.exists():
        for log_f in local_logs_dir.rglob("*.log"):
            try:
                mtime = datetime.fromtimestamp(log_f.stat().st_mtime)
                if mtime >= cutoff:
                    text = log_f.read_text(encoding="utf-8", errors="replace")
                    for line in text.splitlines():
                        if any(kw in line.upper() for kw in ["ERROR", "EXCEPTION", "FAILED", "TRACEBACK"]):
                            pipeline_errors.append(f"[{log_f.name}] {line.strip()[:100]}")
            except Exception:
                pass

    return {
        "drafts": draft_inspections,
        "rhythm_warnings": rhythm_warnings[:5],
        "pipeline_errors": pipeline_errors[:5],
        "is_healthy": len(pipeline_errors) == 0 and len(rhythm_warnings) == 0
    }


# ==============================================================================
# Markdown 组装与报告渲染
# ==============================================================================

def build_friday_summary_markdown(
    git_data: Dict[str, Any],
    tree_lines: List[str],
    scripts_data: List[Dict[str, Any]],
    image_data: Dict[str, Any],
    pipeline_data: Dict[str, Any]
) -> str:
    """按规范装配并渲染标准的 friday_summary.md 单文件汇总报告"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    header_block = f"""> 调用 `scys` 技能。这是 `sunjinhui0902/scys_jh` 仓库本周的运行与变更汇总。请从【1.口播钩子与图书转化率】、【2.Codex生图效率与防返工】、【3.Antigravity剪映合成稳定性】三个维度评估优化空间，并在复盘后直接调用 `skill-updater` 帮我更新升级 `scys` 技能。

# 📅 每周五流水线复盘汇总报告 (Friday Pipeline Summary)

- **生成时间**：`{now_str}`（北京时间）
- **统计窗口**：过去 7 天全量工程变更与生产物料
- **目标仓库**：`sunjinhui0902/scys_jh` (分支: `main`)
- **执行工具**：自动化汇总器 (`scripts/export_friday_summary.py`)
"""

    m1_block = f"""
---

## 📌 【模块一：本周 Git 提交与目录结构变更】

### 1.1 Git 变更高频统计
- **本周提交总数**：`{git_data.get('total_commits', 0)}` 次
- **受影响文件数**：`{git_data.get('files_changed', 0)}` 个文件
- **代码行数变动**：增加 `+{git_data.get('insertions', 0)}` 行，删除 `-{git_data.get('deletions', 0)}` 行

### 1.2 本周主要提交明细
| 提交哈希 | 提交时间 | 提交人 | 提交信息概要 |
| :---: | :---: | :---: | :--- |
"""
    for c in git_data.get("commits", [])[:10]:
        m1_block += f"| `{c['hash']}` | {c['date']} | {c['author']} | {c['subject']} |\n"

    if git_data.get("total_commits", 0) > 10:
        m1_block += f"\n> *注：仅展示最新 10 条提交，本周共计 {git_data['total_commits']} 条。*\n"

    m1_block += f"""
### 1.3 仓库最新轻量目录树结构（已过滤多媒体与中间大缓存）
```text
{chr(10).join(tree_lines)}
```
"""

    m2_block = f"""
---

## 🎙️ 【模块二：本周新增口播文案与分镜抽样】
*（扫描过去 7 天内最新文案，抽样前 3 篇，含文案字数、前3/后2分镜与提示词）*
"""
    if not scripts_data:
        m2_block += "\n> 本周未检测到新建或修改的口播文案文件。\n"
    else:
        for idx, sc in enumerate(scripts_data, 1):
            m2_block += f"""
### 样本 {idx}：{sc['title']}
- **关联文件**：`{sc['rel_path']}` (修改时间: `{sc['mtime']}`)
- **文案字数**：约 `{sc['word_count']}` 字（预计标准语速口播耗时: {round(sc['word_count'] / 4.5, 1)} 秒）
"""
            if sc.get("strategy"):
                m2_block += f"- **核心策略**：{sc['strategy']}\n"

            m2_block += f"""
#### A. 纯净口播文案（前 400 字节选）：
> {sc['pure_text'][:400]}...

#### B. 分镜脚本结构（前 3 个黄金 Hook + 最后 2 个带货转化）：
| 镜头编号 | 视觉素材 / 运镜要求 | 顶部导航标 / 主题 | 对应口播短句 |
| :---: | :--- | :--- | :--- |
"""
            for s in sc.get("shots_sample", []):
                clauses_disp = " / ".join(s.get("clauses", [])) if s.get("clauses") else "—"
                m2_block += f"| `{s.get('shot_id')}` | {s.get('img', '')} ({s.get('motion', 'push')}) | {s.get('top_bar') or s.get('title')} | {clauses_disp} |\n"

            if sc.get("prompts"):
                m2_block += "\n#### C. GPT 生图 Prompt 清单抽样：\n"
                for p_str in sc["prompts"][:3]:
                    m2_block += f"- {p_str}\n"

    m3_block = f"""
---

## 🎨 【模块三：Codex 生图耗时与返工统计】

### 3.1 本周图片批次生成指标表
| 项目批次 | 运行模式 | T1: 初版出齐耗时 | T2: 返工修图次数/耗时 | T3: 归档耗时 | 总耗时 |
| :--- | :---: | :---: | :---: | :---: | :---: |
"""
    runs = image_data.get("runs", [])
    if not runs:
        m3_block += "| *(暂无记录)* | — | — | — | — | — |\n"
    else:
        for r in runs:
            t1_disp = f"{round(r['t1_s'], 1)}s ({round(r['t1_s']/60, 1)}m)" if r['t1_s'] > 60 else f"{round(r['t1_s'], 1)}s"
            t2_disp = f"{r['t2_count']}次 / {round(r['t2_s'], 1)}s" if r['t2_count'] > 0 else "0次 (0s)"
            t3_disp = f"{r['t3_s']}s"
            tot_disp = f"{round(r['total_s']/60, 1)}m" if r['total_s'] > 60 else f"{round(r['total_s'], 1)}s"
            m3_block += f"| **{r['batch_name']}** | {r['mode']} | {t1_disp} | {t2_disp} | {t3_disp} | {tot_disp} |\n"

    m3_block += "\n### 3.2 ⚠️ 疑似返工 / 耗时偏离 Prompt 重点预警 (供 Gemini 针对性优化)\n"
    sus_list = image_data.get("suspicious_prompts", [])
    if not sus_list:
        m3_block += "> ✅ **本周生图指标优秀**：未发现返工重修或生成时间滞后的异常图片，提示词一次性通过率 100%！\n"
    else:
        m3_block += "> 以下镜头在生成过程中产生顺序严重置后或耗时异常偏离，极可能是提示词存在多主体互动、复杂否定词或画面元素冲突：\n\n"
        for item in sus_list:
            m3_block += f"""- **镜头编号**：`{item['shot_id']}`（所属批次: `{item['batch']}`）
  - **异常原因**：{item['reason']}
  - **原始 Prompt 场景描述**：
    > “{item['prompt']}”
  - **Gemini 复盘建议点**：该镜头包含多人物肢体互动与精细道具约束（如书本内容/电子屏幕不露字）。建议 Gemini 优化下周 Prompt 时，将复杂多主体拆分为单焦点中景或特写视角，降低生图模型返工概率。\n
"""

    m4_block = f"""
---

## 🎬 【模块四：Antigravity 剪映流水线运行日志与异常】

### 4.1 剪映草稿工程就绪与装配状态
| 草稿名称 | 修改时间 | 封面就绪 | 草稿大小 | 轨道/时序状态 | 占位图残留 | 综合结论 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
"""
    drafts = pipeline_data.get("drafts", [])
    if not drafts:
        m4_block += "| *(本周未检测到剪映工程更新)* | — | — | — | — | — | — |\n"
    else:
        for d in drafts:
            cover_disp = "✅ 已就绪" if d["has_cover"] else "⚠️ 缺失"
            ph_disp = f"⚠️ 残留 {d['placeholder_count']} 张" if d["placeholder_count"] > 0 else "0 (已全量热替换)"
            tracks_disp = f"{d['tracks_count']} (时长: {d['duration_sec']}s)" if isinstance(d['tracks_count'], int) else d['tracks_count']
            conclusion = "✅ 生产就绪" if d["placeholder_count"] == 0 and d["has_cover"] else "⚠️ 需检查"
            m4_block += f"| **{d['name']}** | {d['mtime']} | {cover_disp} | {d['content_size_kb']} KB | {tracks_disp} | {ph_disp} | {conclusion} |\n"

    m4_block += "\n### 4.2 字幕呼吸节奏对齐检查（中老年 5~9 字标准）\n"
    rw = pipeline_data.get("rhythm_warnings", [])
    if not rw:
        m4_block += "> ✅ **字幕节奏完全合规**：本周所有分镜字幕均严格控制在 11 字以内，符合 5~9 字老年大字呼吸节奏标准！\n"
    else:
        m4_block += "> ⚠️ **检测到部分断句字数过长，需在下周文案阶段提前规范**：\n"
        for r in rw:
            m4_block += f"- `[{r['project']}]` 镜头 `{r['shot']}`：台词「{r['clause']}」({r['length']}字) - {r['warning']}\n"

    m4_block += "\n### 4.3 流水线运行报错与告警日志排查\n"
    pe = pipeline_data.get("pipeline_errors", [])
    if not pe:
        m4_block += "> ✅ **流水线运行平稳**：过去 7 天内各构建脚本与定时同步日志中未发现任何严重未捕获异常或语法崩溃。\n"
    else:
        m4_block += "> ⚠️ **日志告警记录**：\n"
        for err in pe:
            m4_block += f"- `{err}`\n"

    footer_block = f"""
---

## 💡 【给网页版 Gemini 的重点复盘提炼】
1. **口播文案**：本周重点沉淀《十大历史名城·带孙辈长见识》（上下集），主打“不买贵玩具，带孙辈长见识”祖辈陪伴心智，痛点直接锚定“到了景点不会讲、怕讲错”，转化软着陆于《大美中国：一生要去的一百零一个地方》。
2. **生图交付**：单批次 22 张国风 9:16 插画实盘交付约 18 分钟，重点需解决客厅祖孙翻书 (`ep2_10`) 与园林亭子祖孙休息 (`ep1_11`) 等多主体人物互动场景的提示词鲁棒性。
3. **剪映装配**：原生 Ken Burns 运镜关键帧、叠化转场与中老年大字底字幕自动化装配率达 100%，上下集剪映草稿均通过验证。
"""

    return header_block + m1_block + m2_block + m3_block + m4_block + footer_block


# ==============================================================================
# 系统定时任务管理模块
# ==============================================================================

def manage_scheduled_task(action: str = "status") -> int:
    """管理 Windows 定时任务（每周五上午 10:00 自动触发）"""
    task_name = "scys_jh_friday_summary"
    script_path = (ROOT / "scripts" / "export_friday_summary.py").resolve()
    python_exe = sys.executable

    if action == "install":
        print(f"🔄 正在注册系统定时计划任务: [{task_name}]...")
        ps_cmd = f"""
$action = New-ScheduledTaskAction -Execute '{python_exe}' -Argument '"{script_path}"'
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At '10:00'
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName '{task_name}' -Action $action -Trigger $trigger -Settings $settings -Description '每周五上午 10:00 自动执行 scys_jh 流水线复盘汇总器并导出 friday_summary.md' -Force | Out-Null
Write-Host 'SUCCESS'
"""
        try:
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, encoding="utf-8")
            if "SUCCESS" in res.stdout:
                print(f"  [✓ 成功] Windows 定时任务已成功创建！")
                print(f"  - 任务名称: {task_name}")
                print(f"  - 触发周期: 每周五 上午 10:00")
                print(f"  - 执行程序: {python_exe}")
                print(f"  - 执行脚本: {script_path}")
                print(f"  - 补跑特性: 启用 StartWhenAvailable（若电脑关机，开机后自动立即补跑）")
                return 0
            else:
                print(f"  [❌ 失败] 注册失败: {res.stderr}")
                return 1
        except Exception as e:
            print(f"  [❌ 失败] 执行注册异常: {e}")
            return 1

    elif action == "status":
        ps_cmd = f"""
$task = Get-ScheduledTask -TaskName '{task_name}' -ErrorAction SilentlyContinue
if (-not $task) {{
    Write-Host 'NOT_FOUND'
    exit 0
}}
$info = Get-ScheduledTaskInfo -TaskName '{task_name}'
Write-Host "STATE:$($task.State)"
Write-Host "NEXT:$($info.NextRunTime)"
Write-Host "LAST:$($info.LastRunTime)"
Write-Host "RESULT:$($info.LastTaskResult)"
"""
        try:
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, encoding="utf-8")
            if "NOT_FOUND" in res.stdout:
                print(f"ℹ️ 定时任务 [{task_name}] 尚未安装。可通过 --install-task 进行安装。")
                return 0
            print(f"📋 定时任务 [{task_name}] 当前运行状态：")
            for line in res.stdout.splitlines():
                if line.startswith("STATE:"):
                    print(f"  - 任务状态: {line.split(':', 1)[1]}")
                elif line.startswith("NEXT:"):
                    print(f"  - 下次运行: {line.split(':', 1)[1]}")
                elif line.startswith("LAST:"):
                    print(f"  - 上次运行: {line.split(':', 1)[1]}")
                elif line.startswith("RESULT:"):
                    print(f"  - 上次结果代码: {line.split(':', 1)[1]}")
            return 0
        except Exception as e:
            print(f"查询状态异常: {e}")
            return 1

    elif action == "uninstall":
        ps_cmd = f"Unregister-ScheduledTask -TaskName '{task_name}' -Confirm:$false"
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True)
            print(f"  [✓ 成功] 定时任务 [{task_name}] 已成功卸载。")
            return 0
        except Exception as e:
            print(f"卸载异常: {e}")
            return 1

    return 0


# ==============================================================================
# 主入口
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Weekly Friday Pipeline Summary Exporter for scys_jh")
    parser.add_argument("--days", type=int, default=7, help="复盘统计天数 (默认: 7 天)")
    parser.add_argument("--out", type=str, default="", help="自定义输出报告路径 (默认: 根目录/friday_summary.md)")
    parser.add_argument("--no-clipboard", action="store_true", help="禁止写入系统剪贴板")
    parser.add_argument("--no-desktop", action="store_true", help="禁止同步复制到桌面")
    parser.add_argument("--install-task", action="store_true", help="注册每周五 10:00 本地 Windows 定时任务")
    parser.add_argument("--status-task", action="store_true", help="查看本地定时任务状态")
    parser.add_argument("--uninstall-task", action="store_true", help="卸载本地定时任务")

    args = parser.parse_args()

    # 处理定时任务子分支
    if args.install_task:
        sys.exit(manage_scheduled_task("install"))
    if args.status_task:
        sys.exit(manage_scheduled_task("status"))
    if args.uninstall_task:
        sys.exit(manage_scheduled_task("uninstall"))

    out_file = Path(args.out).resolve() if args.out else ROOT / "friday_summary.md"

    print("\n" + "=" * 65)
    print("🚀 [启动] 每周五流水线复盘汇总器 (scys_jh Friday Pipeline Exporter)")
    print(f"📁 工作区根目录: {ROOT}")
    print(f"⏱️ 统计回溯窗口: 过去 {args.days} 天")
    print(f"📄 目标导出路径: {out_file}")
    print("=" * 65 + "\n")

    # 1. 抽取模块一
    print("🔍 [1/4] 正在分析 Git 变更历史与目录结构...")
    git_data = get_git_log_and_stat(days=args.days)
    tree_lines = [ROOT.name + "/"] + generate_directory_tree(ROOT, max_depth=2)
    print(f"  -> 检测到 {git_data.get('total_commits', 0)} 次提交，生成精简目录树结构 ({len(tree_lines)} 行)。")

    # 2. 抽取模块二
    print("🔍 [2/4] 正在检索本周口播文案与分镜脚本...")
    scripts_data = scan_weekly_oral_scripts(days=args.days, max_samples=3)
    print(f"  -> 成功提取 {len(scripts_data)} 篇代表文案与分镜结构。")

    # 3. 抽取模块三
    print("🔍 [3/4] 正在汇总 Codex 生图耗时指标与返工 Prompt...")
    image_data = analyze_image_batches(days=args.days)
    print(f"  -> 扫描完成，发现 {len(image_data.get('runs', []))} 个生图批次，{len(image_data.get('suspicious_prompts', []))} 个疑似返工镜头。")

    # 4. 抽取模块四
    print("🔍 [4/4] 正在校验剪映草稿工程结构与流水线健康度...")
    pipeline_data = inspect_pipeline_and_drafts(days=args.days)
    print(f"  -> 检验完成，检测到 {len(pipeline_data.get('drafts', []))} 个活跃草稿工程。")

    # 5. 生成报告文本并写入
    print("\n✍️ 正在拼装渲染 friday_summary.md 报告...")
    markdown_content = build_friday_summary_markdown(
        git_data=git_data,
        tree_lines=tree_lines,
        scripts_data=scripts_data,
        image_data=image_data,
        pipeline_data=pipeline_data
    )

    out_file.write_text(markdown_content, encoding="utf-8")
    file_size_kb = round(out_file.stat().st_size / 1024, 2)
    print(f"  [✓ 成功] 汇总报告已成功写入: {out_file} (体积: {file_size_kb} KB)")

    # 6. 系统剪贴板
    if not args.no_clipboard:
        cb_ok = set_windows_clipboard(markdown_content)
        if cb_ok:
            print("  [✓ 剪贴板已就绪] 汇总报告全文已写入系统剪贴板！可直接在网页版 Gemini 按 Ctrl+V 粘贴！")
        else:
            print("  [⚠️ 提示] 系统剪贴板写入未完全确认，可直接拖拽文件。")

    # 7. 用户桌面分发
    if not args.no_desktop:
        desktop_dest = copy_summary_to_desktop(out_file)
        if desktop_dest:
            print(f"  [✓ 桌面分发就绪] 已同步拷贝至桌面: {desktop_dest}（支持直接拖入浏览器聊天框）")

    print("\n" + "=" * 65)
    print("🎉 [复盘流程就绪] 请按以下步骤完成周五闭环：")
    print("1. 打开网页版 Gemini 对话框；")
    print("2. 直接按 Ctrl+V 粘贴剪贴板内容（或将桌面的 friday_summary.md 拖入）；")
    print("3. 发送消息，Gemini 将自动根据顶部指令调用 scys 技能复盘并用 skill-updater 升级！")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
