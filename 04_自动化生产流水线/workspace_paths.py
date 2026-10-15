"""Portable paths for the existing production examples."""
from pathlib import Path
import os
import shutil

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / '.env').is_file():
    for line in (ROOT / '.env').read_text(encoding='utf-8-sig').splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            if key.strip().startswith('SCYS_'):
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
EP1 = ROOT / '03_视频成片与工程/01_山西古建三大奇迹'
FONT_DIR = ROOT / '02_公共资产库/字体库'
JIANYING = Path(os.environ.get('SCYS_JIANYING_DRAFTS', str(Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'JianyingPro/User Data/Projects/com.lveditor.draft')))


def ffmpeg():
    custom = os.environ.get('SCYS_FFMPEG') or shutil.which('ffmpeg')
    if custom:
        return custom
    bundled = next((ROOT / '竞品视频分析_2026-10-15/tools').glob('**/ffmpeg.exe'), None)
    if bundled:
        return str(bundled)
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def font(name):
    for p in [FONT_DIR / name, Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / name]:
        if p.exists():
            return str(p)
    raise FileNotFoundError(f'缺少字体 {name}，请先恢复 core 素材包或安装该字体。')
