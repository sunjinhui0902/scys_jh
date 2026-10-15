"""Synchronize accumulated knowledge base assets from scys_jh to Google Drive.

Usage:
    python scripts/sync_to_gdrive.py [--target <path>] [--dry-run] [--include-books] [--verbose]
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time

SRC_ROOT = Path(__file__).resolve().parents[1]

# File extensions to exclude (large binaries, media, model weights, caches)
EXCLUDE_EXTS = {
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv",
    ".wav", ".mp3", ".ogg", ".flac",
    ".zip", ".tar", ".gz", ".7z", ".rar",
    ".pt", ".pth", ".bin", ".onnx",
    ".exe", ".dll", ".so", ".dylib",
    ".pyc", ".db-wal", ".db-shm",
}

# Directories to exclude from traversal
EXCLUDE_DIR_NAMES = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    ".local", ".bundle-cache", "tools", "rendered_motion_clips",
    "DouK-Downloader", "视频号下载成果", "wx_channel", "models",
    "audio", "frames", "chunks", "segments",
}

# Sensitive file patterns
SECRET_PATTERNS = [
    re.compile(r"^\.env(?:\..*)?$", re.IGNORECASE),
    re.compile(r".*\.(?:pem|key|crt|cer|p12|pfx)$", re.IGNORECASE),
    re.compile(r".*(?:token|cookie|auth_qr).*", re.IGNORECASE),
    re.compile(r"hardware_fingerprint\.json", re.IGNORECASE),
]

# Knowledge base items to synchronize
DEFAULT_KNOWLEDGE_PATHS = [
    "05_爆款知识库与复盘",
    "docs",
    "03_视频成片与工程/15城纠偏稿_2026-10-16_v2",
    "竞品视频分析_2026-10-15/content_library",
    "竞品视频分析_2026-10-15/reports",
    ".agents/skills",
]

ROOT_DOC_FILES = [
    "短视频全流程实战经验与生产SOP.md",
    "对标工具保姆级实操指南.md",
    "AI爆款带货视频拆解九宫格工具(1).xlsx",
    "README.md",
    "AGENTS.md",
]


def resolve_target_dir(arg_target: str | None = None) -> Path:
    """Resolve destination directory from args, env vars, .env file, or auto-detect."""
    if arg_target:
        return Path(arg_target).resolve()

    env_target = os.environ.get("SCYS_GDRIVE_TARGET")
    if env_target:
        return Path(env_target).resolve()

    dotenv_path = SRC_ROOT / ".env"
    if dotenv_path.is_file():
        try:
            for line in dotenv_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("#") or not line or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == "SCYS_GDRIVE_TARGET":
                    return Path(v.strip().strip("'\"")).resolve()
        except Exception:
            pass

    # Auto-detect mounted Google Drive paths
    for letter in "GHIJKLMNOPQRSTUVWXYZCDEF":
        candidate_zh = Path(f"{letter}:/我的云端硬盘/fuye")
        if candidate_zh.parent.exists():
            return candidate_zh.resolve()
        candidate_en = Path(f"{letter}:/My Drive/fuye")
        if candidate_en.parent.exists():
            return candidate_en.resolve()

    raise FileNotFoundError(
        "无法定位目标云端硬盘路径。请在 .env 中设置 SCYS_GDRIVE_TARGET=... 或使用 --target 参数。"
    )


def is_excluded_file(rel_path: Path) -> bool:
    """Determine if a file should be excluded based on extension, parts, or secrets."""
    name = rel_path.name
    ext = rel_path.suffix.lower()

    if ext in EXCLUDE_EXTS:
        return True

    for pattern in SECRET_PATTERNS:
        if pattern.search(name):
            return True

    for part in rel_path.parts:
        if part in EXCLUDE_DIR_NAMES:
            return True

    return False


def collect_knowledge_files(include_books: bool = False) -> list[Path]:
    """Scan and collect all knowledge base files eligible for sync."""
    collected: list[Path] = []
    seen: set[str] = set()

    # 1. Root doc files
    for doc_name in ROOT_DOC_FILES:
        doc_file = SRC_ROOT / doc_name
        if doc_file.is_file():
            rel = doc_file.relative_to(SRC_ROOT)
            if not is_excluded_file(rel):
                collected.append(doc_file)
                seen.add(str(rel))

    # 2. Knowledge directories
    paths_to_scan = list(DEFAULT_KNOWLEDGE_PATHS)
    if include_books:
        paths_to_scan.append("02_公共资产库/参考图书")

    for sub in paths_to_scan:
        dir_path = SRC_ROOT / sub
        if not dir_path.exists():
            continue
        if dir_path.is_file():
            rel = dir_path.relative_to(SRC_ROOT)
            if str(rel) not in seen and not is_excluded_file(rel):
                collected.append(dir_path)
                seen.add(str(rel))
            continue

        for root, dirs, files in os.walk(dir_path):
            # Prune excluded directories in-place
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIR_NAMES]

            for f in files:
                full_file = Path(root) / f
                rel = full_file.relative_to(SRC_ROOT)
                if str(rel) in seen:
                    continue
                if not is_excluded_file(rel):
                    collected.append(full_file)
                    seen.add(str(rel))

    return sorted(collected, key=lambda p: str(p.relative_to(SRC_ROOT)))


def generate_index_markdown(target_dir: Path, total_files: int, total_size_mb: float, copied: int, skipped: int) -> str:
    """Generate a clean navigation catalog in the target directory."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""# 知识库云端同步概览与导航

> 本文档由 `scripts/sync_to_gdrive.py` 自动生成与更新。  
> **最新同步时间**：`{now_str}`  
> **文件状态**：共 {total_files} 个知识库文件，约 {total_size_mb:.2f} MB（本次新增/更新: {copied}，跳过未修改: {skipped}）。

---

## 快速导航与模块指引

### 1. 核心实战规范与SOP
- [短视频全流程实战经验与生产SOP.md](短视频全流程实战经验与生产SOP.md)：视频号图书带货全流程统一生产规范与经验
- [对标工具保姆级实操指南.md](对标工具保姆级实操指南.md)：对标账号与素材采集工具使用指南
- [AI爆款带货视频拆解九宫格工具(1).xlsx](AI爆款带货视频拆解九宫格工具(1).xlsx)：拆解分析工具表格
- [docs/内容纠偏与文档导航.md](docs/内容纠偏与文档导航.md)：防偏题导航与文档总入口
- [docs/竞品分析协作总控.md](docs/竞品分析协作总控.md)：竞品分析总控与各批次规范

### 2. 15城最新纠偏口播与制作卡
- [03_视频成片与工程/15城纠偏稿_2026-10-16_v2/15城完整口播.md](03_视频成片与工程/15城纠偏稿_2026-10-16_v2/15城完整口播.md)：15城说书式高转化口播全稿
- [03_视频成片与工程/15城纠偏稿_2026-10-16_v2/五镜配图方案.md](03_视频成片与工程/15城纠偏稿_2026-10-16_v2/五镜配图方案.md)：五镜叙事递进选图方案
- [03_视频成片与工程/15城纠偏稿_2026-10-16_v2/后台事实台账.md](03_视频成片与工程/15城纠偏稿_2026-10-16_v2/后台事实台账.md)：硬核物理/建筑机关台账与页码依据
- 各城独立卡片：进入 `03_视频成片与工程/15城纠偏稿_2026-10-16_v2/` 查看各城市独立 `制作卡.md`、`口播.txt`、`字幕短句.txt`

### 3. 爆款知识库与双层书目
- [05_爆款知识库与复盘/01_钩子与引书结构库.md](05_爆款知识库与复盘/01_钩子与引书结构库.md)：开场反常识钩子与主推书承接句式
- [05_爆款知识库与复盘/02_单点选题排期.md](05_爆款知识库与复盘/02_单点选题排期.md)：排期规划与选题矩阵
- [05_爆款知识库与复盘/07_说书式口播写法.md](05_爆款知识库与复盘/07_说书式口播写法.md)：5步说书式硬核机制写法
- [05_爆款知识库与复盘/09_带货内容执行标准.md](05_爆款知识库与复盘/09_带货内容执行标准.md)：五大执行铁律
- [05_爆款知识库与复盘/10_双层书目与15城映射.md](05_爆款知识库与复盘/10_双层书目与15城映射.md)：后台史料弹药库 vs 前台在售主推书
- [05_爆款知识库与复盘/城市与图书知识库/](05_爆款知识库与复盘/城市与图书知识库/)：各城市与古建事实卡库

### 4. 竞品文库与原创选题库
- [竞品视频分析_2026-10-15/content_library/全量文案参考.jsonl](竞品视频分析_2026-10-15/content_library/全量文案参考.jsonl)：竞品文案结构库
- [竞品视频分析_2026-10-15/content_library/原创选题30条.jsonl](竞品视频分析_2026-10-15/content_library/原创选题30条.jsonl)：可直接投产的原创选题
- [竞品视频分析_2026-10-15/content_library/选题结构拆解.jsonl](竞品视频分析_2026-10-15/content_library/选题结构拆解.jsonl)：拆解逻辑与转化点
- [竞品视频分析_2026-10-15/reports/](竞品视频分析_2026-10-15/reports/)：分阶段聚类与分析报告

### 5. 提示词与纠偏参考样例
- [Gpt纠偏参考样例与视频号带货知识库.md](Gpt纠偏参考样例与视频号带货知识库.md)：直接喂给 AI 的 Prompt 与黄金标准样稿

---
*注：原始采集视频、大体积模型与剪辑渲染缓存不纳入云端同步。*
"""


def sync_knowledge(
    target_dir: Path,
    dry_run: bool = False,
    include_books: bool = False,
    verbose: bool = False,
) -> dict:
    """Execute the synchronization process."""
    start_time = time.time()
    files = collect_knowledge_files(include_books=include_books)

    copied = 0
    skipped = 0
    errors = 0
    total_bytes = 0

    log_lines: list[str] = []
    log_lines.append(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始同步知识库到: {target_dir}")
    log_lines.append(f"待处理知识库文件总数: {len(files)}")

    target_dir.mkdir(parents=True, exist_ok=True)

    for src_file in files:
        rel_path = src_file.relative_to(SRC_ROOT)
        dest_file = target_dir / rel_path
        file_size = src_file.stat().st_size
        total_bytes += file_size

        need_copy = False
        if not dest_file.exists():
            need_copy = True
        else:
            dest_stat = dest_file.stat()
            if dest_stat.st_size != file_size:
                need_copy = True
            elif src_file.stat().st_mtime - dest_stat.st_mtime > 1.0:
                need_copy = True

        if need_copy:
            if not dry_run:
                try:
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dest_file)
                    copied += 1
                    if verbose:
                        print(f" [复制] {rel_path}")
                except Exception as ex:
                    errors += 1
                    print(f" [错误] 复制 {rel_path} 失败: {ex}", file=sys.stderr)
            else:
                copied += 1
                if verbose:
                    print(f" [试运行-复制] {rel_path}")
        else:
            skipped += 1
            if verbose:
                print(f" [跳过] {rel_path} (已是最新)")

    total_mb = total_bytes / (1024 * 1024)

    # Write target index & manifest
    if not dry_run:
        index_content = generate_index_markdown(target_dir, len(files), total_mb, copied, skipped)
        index_path = target_dir / "00_知识库同步索引与最新概览.md"
        index_path.write_text(index_content, encoding="utf-8")

        manifest = {
            "last_sync": datetime.now().isoformat(),
            "target_dir": str(target_dir),
            "total_files": len(files),
            "copied_files": copied,
            "skipped_files": skipped,
            "error_files": errors,
            "total_bytes": total_bytes,
            "total_mb": round(total_mb, 2),
            "duration_seconds": round(time.time() - start_time, 2),
        }
        manifest_path = target_dir / "sync_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    duration = time.time() - start_time
    summary = (
        f"同步完成！总文件: {len(files)}, 更新/新增: {copied}, 未修改跳过: {skipped}, "
        f"总大小: {total_mb:.2f} MB, 耗时: {duration:.2f} 秒, 错误: {errors}"
    )
    log_lines.append(summary)

    # Write log to .local/logs
    log_dir = SRC_ROOT / ".local" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "gdrive_sync.log"
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write("\n".join(log_lines) + "\n\n")

    print(summary)
    return {
        "total": len(files),
        "copied": copied,
        "skipped": skipped,
        "errors": errors,
        "total_mb": total_mb,
        "duration": duration,
    }


def main():
    parser = argparse.ArgumentParser(description="同步项目知识库到云端硬盘")
    parser.add_argument("--target", "-t", type=str, default=None, help="目标云端硬盘路径")
    parser.add_argument("--dry-run", action="store_true", help="试运行，不实际写入文件")
    parser.add_argument("--include-books", action="store_true", help="是否连同参考图书PDF一起同步")
    parser.add_argument("--verbose", "-v", action="store_true", help="输出每个文件的同步详情")
    args = parser.parse_args()

    try:
        target_dir = resolve_target_dir(args.target)
    except FileNotFoundError as err:
        print(f"[错误] {err}", file=sys.stderr)
        sys.exit(1)

    print(f"源项目路径: {SRC_ROOT}")
    print(f"目标云盘:   {target_dir}")
    sync_knowledge(
        target_dir=target_dir,
        dry_run=args.dry_run,
        include_books=args.include_books,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
