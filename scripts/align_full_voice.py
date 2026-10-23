import os
import sys
import json
import time
import subprocess
from pathlib import Path
import soundfile as sf

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

print("正在初始化 FunASR 模型...")
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

FFMPEG = Path(r"D:\fuye\.local\gpt-sovits-test\bin\ffmpeg.exe")
src_mp3 = Path(r"D:\fuye\01_配音与音色库\生成结果\本次配音.mp3")
tmp_wav = Path(r"C:\Users\Miche\AppData\Local\Temp\asr_full_下集.wav")

subprocess.run([str(FFMPEG), "-y", "-i", str(src_mp3), "-ar", "16000", "-ac", "1", str(tmp_wav)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
data, sr = sf.read(str(tmp_wav), dtype="float32")
print(f"音频时长: {len(data)/sr:.2f}s, 开始 FunASR 字级别发音对齐...")
t0 = time.time()
res = model.generate(input=data, fs=sr, sentence_timestamp=True, batch_size_s=60, disable_pbar=True)
dur = time.time() - t0
print(f"ASR 对齐完成 (耗时 {dur:.2f}s), 句子数: {len(res[0].get('sentence_info', []))}")

out_file = Path(r"D:\fuye\01_配音与音色库\生成结果\asr_alignment.json")
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(res[0], f, ensure_ascii=False, indent=2)
print("保存成功:", out_file)
tmp_wav.unlink(missing_ok=True)
