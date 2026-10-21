# -*- coding: utf-8 -*-
import os
import time
from pathlib import Path

def search_dir(base_path, max_depth=3):
    try:
        p = Path(base_path)
        if not p.exists():
            return
        cutoff = time.time() - 3600 * 8  # last 8 hours
        for root, dirs, files in os.walk(p):
            rel_parts = Path(root).relative_to(p).parts
            if len(rel_parts) > max_depth:
                dirs.clear()
                continue
            # skip ignorable dirs
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['site-packages', 'node_modules', 'AppData', 'Windows', 'Program Files']]
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in ['.png', '.jpg', '.jpeg', '.webp', '.zip']:
                    fp = Path(root) / f
                    try:
                        mtime = fp.stat().st_mtime
                        if mtime > cutoff:
                            tstr = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
                            print(f"{tstr} | {fp.stat().st_size} bytes | {fp}")
                    except Exception:
                        pass
    except Exception as e:
        print(f"Error {base_path}: {e}")

if __name__ == "__main__":
    for loc in [
        "C:/Users/Miche/Desktop",
        "C:/Users/Miche/Downloads",
        "C:/Users/Miche/Pictures",
        "03_视频成片与工程",
        "02_公共资产库",
        "D:/"
    ]:
        print(f"=== {loc} ===")
        search_dir(loc, max_depth=3)
