# -*- coding: utf-8 -*-
import os
import sys
import time
from pathlib import Path

R = Path("竞品视频分析_2026-10-15").resolve()
os.environ["MODELSCOPE_CACHE"] = str(R / "models")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["MODELSCOPE_OFFLINE"] = "1"
os.environ["OMP_NUM_THREADS"] = "4"
os.environ["MKL_NUM_THREADS"] = "4"

from funasr import AutoModel

root = R / "models" / "models"
def mp(pattern):
    matches = list(root.glob(pattern + "/snapshots/master"))
    if not matches:
        matches = list(root.glob(pattern))
    return str(matches[0])

model_dir = mp("*seaco_paraformer*")
vad_dir = mp("*fsmn_vad*")
punc_dir = mp("*punc_ct*")

print("model_dir:", model_dir)
print("vad_dir:", vad_dir)
print("punc_dir:", punc_dir)

model = AutoModel(
    model=model_dir,
    vad_model=vad_dir,
    punc_model=punc_dir,
    vad_kwargs={"max_single_segment_time": 30000},
    device="cpu",
    ncpu=4,
    disable_update=True,
    trust_remote_code=False,
    disable_pbar=True
)

audio_file = Path("03_视频成片与工程/01_平遥古城_单集精讲/03_视频/voice_master.mp3").resolve()
print("Transcribing:", audio_file)
t0 = time.time()
res = model.generate(
    input=str(audio_file),
    sentence_timestamp=True,
    batch_size_s=300
)
print(f"Transcription finished in {time.time()-t0:.2f}s!")
sentences = res[0].get("sentence_info", [])
print(f"Total sentences: {len(sentences)}")
for s in sentences[:8]:
    print(f"{s['start']/1000.0:.2f}s - {s['end']/1000.0:.2f}s: {s['text']}")
