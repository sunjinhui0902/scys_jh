# -*- coding: utf-8 -*-
import os
import sys
import shutil
import subprocess
import time
import json
from pathlib import Path
import soundfile as sf

# Force UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(".").resolve()
FFMPEG = ROOT / r"竞品视频分析_2026-10-15\tools\ffmpeg-9.0.2-essentials_build\bin\ffmpeg.exe"
if not FFMPEG.exists():
    FFMPEG = Path(r"D:\fuye\.local\gpt-sovits-test\bin\ffmpeg.exe")

R = ROOT / "竞品视频分析_2026-10-15"
os.environ["MODELSCOPE_CACHE"] = str(R / "models")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["MODELSCOPE_OFFLINE"] = "1"
os.environ["OMP_NUM_THREADS"] = "4"
os.environ["MKL_NUM_THREADS"] = "4"

from funasr import AutoModel

root = R / "models" / "models"
def mp(pattern):
    return str(next(root.glob(pattern + "/snapshots/master")))

print("正在初始化 FunASR 模型 (离线 Paraformer + VAD + 标点)...", flush=True)
model = AutoModel(
    model=mp("*seaco_paraformer*"),
    vad_model=mp("*fsmn_vad*"),
    punc_model=mp("*punc_ct*"),
    vad_kwargs={"max_single_segment_time": 30000},
    device="cpu",
    ncpu=4,
    disable_update=True,
    trust_remote_code=False,
    disable_pbar=True
)

TARGET_PROJECTS = [
    "EP01_第5名_北京",
    "EP02_第4名_洛阳",
    "EP03_第3名_南京",
    "EP04_第2名_西安",
    "EP05_第1名_成都"
]

base_dir = ROOT / "03_视频成片与工程" / "十大历史名城_下集_文案修订_2026-10-23_v2"

for proj_name in TARGET_PROJECTS:
    proj_dir = (base_dir / proj_name).resolve()
    mp3_file = proj_dir / "03_配音音频" / "voice_master.mp3"
    if not mp3_file.exists():
        print(f"Warning: voice_master.mp3 not found in {proj_name}", flush=True)
        continue
    
    out_json = proj_dir / "asr_alignment.json"
    tmp_wav = Path(f"C:/Users/Miche/AppData/Local/Temp/asr_{proj_name[:4]}.wav")
    
    cmd = [str(FFMPEG), "-y", "-i", str(mp3_file), "-ar", "16000", "-ac", "1", str(tmp_wav)]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    data, sr = sf.read(str(tmp_wav), dtype="float32")
    print(f"\n[{proj_name}] 音频已载入: {len(data)/sr:.2f}s, 开始 FunASR 字级别发音时间戳对齐...", flush=True)
    
    t0 = time.time()
    res = model.generate(
        input=data,
        fs=sr,
        sentence_timestamp=True,
        batch_size_s=60,
        disable_pbar=True
    )
    dur = time.time() - t0
    sentence_count = len(res[0].get("sentence_info", []))
    char_count = len(res[0].get("timestamp", []))
    print(f"[{proj_name}] ASR 对齐完成 (耗时 {dur:.2f}s): {sentence_count} 句，{char_count} 字符时间戳", flush=True)
    
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(res[0], f, ensure_ascii=False, indent=2)
    print(f"[{proj_name}] 已保存: {out_json}", flush=True)
    
    try:
        tmp_wav.unlink(missing_ok=True)
    except Exception:
        pass

print("\n=== [下集五城] FunASR 全部发音时间戳对齐完成！ ===", flush=True)
