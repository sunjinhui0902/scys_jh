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

proj_dir = Path("03_视频成片与工程/01_平遥古城_单集精讲").resolve()
mp3_files = list(proj_dir.glob("**/voice_master.mp3"))
assert mp3_files, f"voice_master.mp3 not found in {proj_dir}"
src_mp3 = mp3_files[0]

tmp_mp3 = Path(r"C:\Users\Miche\AppData\Local\Temp\test_py_01.mp3")
tmp_wav = Path(r"C:\Users\Miche\AppData\Local\Temp\test_py_01.wav")

shutil.copy2(src_mp3, tmp_mp3)
print(f"Copied {src_mp3.name} to {tmp_mp3} ({tmp_mp3.stat().st_size} bytes)")

cmd = [str(FFMPEG), "-y", "-i", str(tmp_mp3), "-ar", "16000", "-ac", "1", str(tmp_wav)]
res = subprocess.run(cmd, capture_output=True)
assert tmp_wav.exists() and tmp_wav.stat().st_size > 0, f"ffmpeg failed: {res.stderr}"

data, sr = sf.read(str(tmp_wav), dtype="float32")
print(f"Loaded WAV: {len(data)/sr:.2f} seconds, sr={sr}")

t0 = time.time()
res = model.generate(
    input=data,
    fs=sr,
    sentence_timestamp=True,
    batch_size_s=60,
    disable_pbar=True
)
print(f"ASR complete in {time.time()-t0:.2f}s!")

if res:
    sentences = res[0].get("sentence_info", [])
    print(f"Total sentences: {len(sentences)}")
    out_json = Path("03_视频成片与工程/01_平遥古城_单集精讲/asr_alignment.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(res[0], f, ensure_ascii=False, indent=2)
    print(f"Saved {out_json}!")
    for s in sentences[:8]:
        print(f"  {s['start']/1000.0:.2f}s - {s['end']/1000.0:.2f}s: {s['text']}")
