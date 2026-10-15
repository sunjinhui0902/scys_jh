"""Read-only checks; use --strict for the core video development environment."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strict', action='store_true')
    a = ap.parse_args()
    checks = {n: bool(shutil.which(n)) for n in ['git', 'gh']}
    for n in ['PIL', 'edge_tts', 'pymediainfo', 'pyJianYingDraft', 'imageio_ffmpeg', 'openpyxl']:
        checks[n] = importlib.util.find_spec(n) is not None
    checks['project_skills'] = all((ROOT / '.agents/skills' / n / 'SKILL.md').is_file()
                                   for n in ['scys-workspace', 'wechat-channels-book-commerce'])
    ff = list((ROOT / '竞品视频分析_2026-10-15/tools').glob('**/ffmpeg.exe'))
    checks['ffmpeg_restored'] = bool(ff)
    if ff:
        checks['ffmpeg_runs'] = subprocess.run([str(ff[0]), '-version'], capture_output=True).returncode == 0
    checks['reference_videos_restored'] = any((ROOT / '00_对标与采集工具/wx_channel/downloads').glob('**/*.mp4'))
    checks['models_restored'] = any((ROOT / '竞品视频分析_2026-10-15/models').glob('**/model.pt'))
    print(json.dumps({'root': str(ROOT), 'python': sys.version.split()[0], 'checks': checks}, ensure_ascii=False, indent=2))
    required = ['git', 'gh', 'project_skills', 'PIL', 'edge_tts', 'pymediainfo', 'pyJianYingDraft', 'imageio_ffmpeg', 'openpyxl']
    return int(a.strict and not all(checks[k] for k in required))


if __name__ == '__main__':
    raise SystemExit(main())
