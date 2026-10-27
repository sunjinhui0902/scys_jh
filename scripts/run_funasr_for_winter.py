# -*- coding: utf-8 -*-
import os
import sys
import json
import time
from pathlib import Path

# Force UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "竞品视频分析_2026-10-15"
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

print("正在初始化 FunASR 模型 (离线 Seaco-Paraformer + VAD + 标点)...", flush=True)
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

TARGET_DIRS = [
    ROOT / "03_视频成片与工程" / "十大冬日绝景_纯涨粉系列" / "上集_第10至第6名",
    ROOT / "03_视频成片与工程" / "十大冬日绝景_纯涨粉系列" / "下集_第5至第1名"
]

for pdir in TARGET_DIRS:
    mp3_file = pdir / "03_配音音频" / "voice_master.mp3"
    out_json = pdir / "asr_alignment.json"
    if not mp3_file.exists():
        print(f"[跳过] 音频不存在: {mp3_file}", flush=True)
        continue
    
    print(f"\n正在对齐: {pdir.name} ({mp3_file.name})...", flush=True)
    t0 = time.time()
    res = model.generate(
        input=str(mp3_file),
        sentence_timestamp=True,
        batch_size_s=300,
        disable_pbar=True
    )
    dur = time.time() - t0
    char_count = len(res[0].get("timestamp", []))
    print(f"[{pdir.name}] ASR 对齐完成 (耗时 {dur:.2f}s): {char_count} 字符时间戳", flush=True)
    
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(res[0], f, ensure_ascii=False, indent=2)
    print(f"[{pdir.name}] 时间戳已保存至: {out_json}", flush=True)

print("\n=== 全部冬日绝景 FunASR 字符级时间戳对齐完成！ ===", flush=True)
