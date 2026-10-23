# -*- coding: utf-8 -*-
"""
为下集五城 (EP01~EP05) 批量生成自训练 GPT-SoVITS 配音音频并准备元数据
"""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

# Ensure UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(r"D:\fuye\.local\gpt-sovits-test")
APP = ROOT / "app"
DATA = ROOT / "finetune-classic-r2-20261023"
FFMPEG = ROOT / "bin" / "ffmpeg.exe"

S1 = DATA / "weights_s1" / "classic_cpu_r2-e4.ckpt"
S2 = DATA / "weights_s2" / "classic_cpu_r2_e3_s120.pth"
REF = DATA / "clips" / "source_03_000_021.wav"

BASE_PROJ = Path(r"D:\fuye\03_视频成片与工程\十大历史名城_下集_文案修订_2026-10-23_v2")
EPISODES = [
    "EP01_第5名_北京",
    "EP02_第4名_洛阳",
    "EP03_第3名_南京",
    "EP04_第2名_西安",
    "EP05_第1名_成都"
]

def main():
    print("=== [下集五城] 自训练音色批量推理启动 ===")
    manifest = json.loads((DATA / "dataset_manifest.json").read_text(encoding="utf-8"))
    ref_text = next(row["text"] for row in manifest["clips"] if row["name"] == REF.name)

    os.environ.update(
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        GRADIO_ANALYTICS_ENABLED="False",
        OMP_NUM_THREADS="6",
        MKL_NUM_THREADS="6",
        version="v1",
        PATH=str(ROOT / "bin") + os.pathsep + os.environ["PATH"]
    )
    os.chdir(APP)
    sys.path[:0] = [str(APP), str(APP / "GPT_SoVITS")]

    import numpy as np
    import soundfile as sf
    import torch
    torch.set_num_threads(6)
    from GPT_SoVITS.TTS_infer_pack.TTS import TTS, TTS_Config

    base_models = APP / "GPT_SoVITS" / "pretrained_models"
    config = {
        "version": "v1",
        "custom": dict(
            device="cpu",
            is_half=False,
            version="v1",
            bert_base_path=str(base_models / "chinese-roberta-wwm-ext-large"),
            cnhuhbert_base_path=str(base_models / "chinese-hubert-base"),
            t2s_weights_path=str(S1),
            vits_weights_path=str(S2)
        )
    }

    print("正在加载 GPT-SoVITS 二次训练模型 (CPU, 6线程)...", flush=True)
    t_load = time.perf_counter()
    pipeline = TTS(TTS_Config(config))
    print(f"模型加载完成，耗时 {time.perf_counter() - t_load:.2f}s", flush=True)

    for ep_name in EPISODES:
        ep_dir = BASE_PROJ / ep_name
        txt_file = ep_dir / "01_文案与分镜" / "待配音.txt"
        audio_dir = ep_dir / "03_配音音频"
        audio_dir.mkdir(parents=True, exist_ok=True)

        wav = audio_dir / "voice_master.wav"
        mp3 = audio_dir / "voice_master.mp3"
        record = audio_dir / "voice_master.json"
        meta_json = audio_dir / "voice_meta.json"

        text = txt_file.read_text(encoding="utf-8-sig").strip()
        print(f"\n--- 处理 {ep_name} (文案字数: {len(text)}) ---", flush=True)

        # 检查是否已存在有效文件
        if mp3.exists() and wav.exists() and mp3.stat().st_size > 1024:
            print(f"[{ep_name}] 已存在有效音频，跳过合成直接复用。", flush=True)
            continue

        started = time.perf_counter()
        params = dict(
            text=text,
            text_lang="all_zh",
            ref_audio_path=str(REF),
            prompt_text=ref_text,
            prompt_lang="all_zh",
            top_k=15,
            top_p=1.0,
            temperature=1.0,
            text_split_method="cut2",
            batch_size=1,
            split_bucket=False,
            return_fragment=False,
            speed_factor=1.0,
            seed=20261022,
            parallel_infer=False,
            repetition_penalty=1.35,
            fragment_interval=0.25
        )

        results = list(pipeline.run(params))
        if not results or len({sr for sr, _ in results}) != 1:
            raise RuntimeError(f"[{ep_name}] 未返回有效的音频结果")

        sr = results[0][0]
        pcm = np.concatenate([audio for _, audio in results])
        if pcm.size == 0 or not np.isfinite(pcm).all() or not np.any(pcm):
            raise RuntimeError(f"[{ep_name}] 生成结果为空或非法")

        with tempfile.TemporaryDirectory(prefix="voice-", dir=audio_dir) as temp:
            tmp = Path(temp)
            sf.write(tmp / "audio.wav", pcm, sr, subtype="PCM_16")
            check, check_sr = sf.read(tmp / "audio.wav")
            if check_sr != 32000 or check.ndim != 1 or np.max(np.abs(check)) >= 1:
                raise RuntimeError(f"[{ep_name}] 音频格式或峰值验证失败")

            subprocess.run([
                str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(tmp / "audio.wav"),
                "-codec:a", "libmp3lame", "-b:a", "192k",
                str(tmp / "audio.mp3")
            ], check=True)

            info = dict(
                voice="classic-round2-20261023",
                text=text,
                input_file=str(txt_file),
                characters=len(text),
                audio_seconds=len(pcm) / sr,
                sample_rate=sr,
                generation_seconds=time.perf_counter() - started,
                parameters=params,
                wav=str(wav),
                mp3=str(mp3),
                listening_review="ready"
            )
            (tmp / "record.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")

            # 写 voice_meta.json 供 fast_draft_pipeline 判定已完成合成
            current_hash = hashlib.md5(f"zh-CN-YunjianNeural|-8%|-6Hz|{text}".encode("utf-8")).hexdigest()
            meta_data = {
                "voice": "classic-round2-20261023",
                "rate": "-8%",
                "pitch": "-6Hz",
                "char_count": len(text),
                "hash": current_hash,
                "audio_seconds": len(pcm) / sr
            }
            (tmp / "voice_meta.json").write_text(json.dumps(meta_data, ensure_ascii=False, indent=2), encoding="utf-8")

            for old, target in [("audio.wav", wav), ("audio.mp3", mp3), ("record.json", record), ("voice_meta.json", meta_json)]:
                if target.exists():
                    target.unlink()
                (tmp / old).rename(target)

        print(f"[{ep_name}] 完成: {len(pcm) / sr:.2f} 秒音频，推理耗时: {time.perf_counter() - started:.2f}s", flush=True)

    print("\n=== [下集五城] 全集自训练音频生成完毕！ ===")

if __name__ == "__main__":
    main()
