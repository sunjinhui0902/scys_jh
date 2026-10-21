# -*- coding: utf-8 -*-
import os
import sys
import shutil
import subprocess
import time
import json
from pathlib import Path
import soundfile as sf

FFMPEG = Path(r"D:\fuye\竞品视频分析_2026-10-15\tools\ffmpeg-9.0.2-essentials_build\bin\ffmpeg.exe")
R = Path("竞品视频分析_2026-10-15").resolve()
os.environ["MODELSCOPE_CACHE"] = str(R / "models")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["MODELSCOPE_OFFLINE"] = "1"
os.environ["OMP_NUM_THREADS"] = "4"
os.environ["MKL_NUM_THREADS"] = "4"

from funasr import AutoModel

root = R / "models" / "models"
def mp(pattern):
    return str(next(root.glob(pattern + "/snapshots/master")))

print("Initializing FunASR model...")
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
    "02_延安宝塔山_单集精讲",
    "03_开封清明上河园_单集精讲",
    "04_苏州拙政园_单集精讲",
    "05_杭州西湖_单集精讲",
]

base_dir = Path("03_视频成片与工程")

for proj_name in TARGET_PROJECTS:
    proj_dir = (base_dir / proj_name).resolve()
    mp3_files = list(proj_dir.glob("**/voice_master.mp3"))
    if not mp3_files:
        print(f"Warning: voice_master.mp3 not found in {proj_name}")
        continue
    src_mp3 = mp3_files[0]
    out_json = proj_dir / "asr_alignment.json"
    
    tmp_mp3 = Path(f"C:/Users/Miche/AppData/Local/Temp/asr_{proj_name[:2]}.mp3")
    tmp_wav = Path(f"C:/Users/Miche/AppData/Local/Temp/asr_{proj_name[:2]}.wav")
    
    shutil.copy2(src_mp3, tmp_mp3)
    cmd = [str(FFMPEG), "-y", "-i", str(tmp_mp3), "-ar", "16000", "-ac", "1", str(tmp_wav)]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    
    data, sr = sf.read(str(tmp_wav), dtype="float32")
    print(f"[{proj_name}] WAV loaded: {len(data)/sr:.2f}s, starting ASR...")
    
    t0 = time.time()
    res = model.generate(
        input=data,
        fs=sr,
        sentence_timestamp=True,
        batch_size_s=60,
        disable_pbar=True
    )
    print(f"[{proj_name}] ASR finished in {time.time()-t0:.2f}s, total sentences: {len(res[0].get('sentence_info', []))}")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(res[0], f, ensure_ascii=False, indent=2)
    print(f"[{proj_name}] Saved {out_json.name}")
    
    # clean up temp
    try:
        tmp_mp3.unlink(missing_ok=True)
        tmp_wav.unlink(missing_ok=True)
    except Exception:
        pass

print("ALL 5 PROJECTS FUNASR COMPLETED!")
