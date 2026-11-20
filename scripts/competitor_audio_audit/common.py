# -*- coding: utf-8 -*-
"""竞品音频审计 —— 共享工具层。

包含三类能力：
  1) 声学特征：MFCC 摘要/序列、基频 F0、DTW 余弦相似度
  2) 说话人嵌入：Resemblyzer(VGGish) + Silero VAD 静音裁剪 + 音量归一
     （用自带的 webrtcvad 桩替代需要 MSVC 编译的原生模块）
  3) 路径与外部工具：仓库根目录、ffmpeg 定位、目录约定

所有路径一律从本文件位置推导，禁止写死盘符或用户名。
"""
import os
import shutil
import struct
import sys
import wave
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------- 路径
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
AUDIT_DIR = ROOT / "scripts" / "competitor_audio_audit"

SCRATCH = ROOT / "scratch" / "competitor_audio_audit"
DATA_DIR = AUDIT_DIR / "data"          # 批次元数据（入库，便于复跑）
DEFAULT_MANIFEST = DATA_DIR / "1116_1117" / "manifest.json"
ASSET_BGM = ROOT / "02_公共资产库" / "竞品BGM素材_20261116-17"
ASSET_VOICE = ROOT / "02_公共资产库" / "竞品口播人声_20261116-17"
DOWNLOADS = ROOT / "00_对标与采集工具" / "视频号下载成果"
VOICE_LIB = ROOT / "01_配音与音色库"
VOICE_API_CFG = ROOT / "config" / "voice_api" / "config.yaml"
GOLDEN_VOICE = VOICE_LIB / "01_央视纪录片_沧桑历史男声.mp3"
BGM_GUOFENG = VOICE_LIB / "背景音乐库" / "bgm_shili_guofeng.mp3"
PROJECT_DIR = ROOT / "03_视频成片与工程"

SR = 22050
NFFT = 1024
HOP = 256
NB = 26
FMIN, FMAX = 80.0, 8000.0


def ensure_dirs(*paths):
    for p in paths:
        Path(p).mkdir(parents=True, exist_ok=True)


def find_ffmpeg():
    """定位 ffmpeg：环境变量 FFMPEG_BIN > 仓库内自带 > PATH > imageio-ffmpeg 内置。

    独立分发包（如 04_自动化生产流水线/minimax_音频调用说明/03_调用脚本/）里没有
    仓库自带的 ffmpeg 二进制，最后一级 imageio-ffmpeg 兜底才能让 check/normalize 直接可用。
    """
    env = os.environ.get("FFMPEG_BIN")
    if env and Path(env).exists():
        return env
    hits = sorted(ROOT.glob("**/ffmpeg.exe"))
    if hits:
        return str(hits[0])
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return "ffmpeg"


def ffmpeg_probe(path):
    """返回 (duration_sec, codec_hint)。不依赖 ffprobe，直接解析 ffmpeg 输出。"""
    import re
    import subprocess
    out = subprocess.run([find_ffmpeg(), "-hide_banner", "-i", str(path)],
                         capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", out)
    dur = 0.0
    if m:
        dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return dur, out


# ---------------------------------------------------------------- 声学特征
def mel_fb(sr=SR):
    freqs = np.fft.rfftfreq(NFFT, 1.0 / sr)
    f = lambda m: 2595.0 * np.log10(1.0 + m / 700.0)
    inv = lambda mel: 700.0 * (10 ** (mel / 2595.0) - 1.0)
    mels = np.linspace(f(FMIN), f(FMAX), NB + 2)
    hz = inv(mels)
    fb = np.zeros((NB, len(freqs)))
    for i in range(NB):
        lo, ctr, hi = hz[i], hz[i + 1], hz[i + 2]
        fb[i] = np.maximum(0, np.minimum((freqs - lo) / max(ctr - lo, 1e-6),
                                         (hi - freqs) / max(hi - ctr, 1e-6)))
        s = fb[i].sum()
        if s > 0:
            fb[i] /= s
    return fb


FB = mel_fb()


def dct2(x):
    N = x.shape[-1]
    k = np.arange(N)
    M = np.cos(np.pi / N * (k[:, None] + 0.5) * k[None, :]) * np.sqrt(2.0 / N)
    return x @ M.T


def f0_track(frame, sr=SR, fmin=60, fmax=400):
    if len(frame) < 1024 or np.sqrt((frame ** 2).mean()) < 1e-3:
        return 0.0
    f = frame - frame.mean()
    ac = np.correlate(f, f, mode="full")[len(f) - 1:]
    lo, hi = int(sr / fmax), int(sr / fmin)
    seg = ac[lo:hi]
    if len(seg) == 0 or seg.max() <= 0:
        return 0.0
    i = int(np.argmax(seg))
    if seg[i] / (ac[0] + 1e-9) < 0.3:
        return 0.0
    return sr / (lo + i)


def load_wav(path):
    with wave.open(str(path), "rb") as w:
        d = w.readframes(w.getnframes())
        sr = w.getframerate()
    return np.frombuffer(d, dtype=np.int16).astype(np.float32) / 32768.0, sr


def features(path, max_sec=180.0):
    """MFCC 摘要 + F0 中位数 + MFCC 序列（供 DTW 比对）。"""
    x, sr = load_wav(path)
    if len(x) > max_sec * sr:
        x = x[:int(max_sec * sr)]
    n = 1 + (len(x) - NFFT) // HOP
    sw = np.lib.stride_tricks.sliding_window_view(x, NFFT)[::HOP][:n]
    sw = sw * np.hanning(NFFT).astype(np.float32)
    mag = np.abs(np.fft.rfft(sw, axis=1)).astype(np.float32)
    e = 20 * np.log10(np.sqrt((mag ** 2).mean(axis=1)) + 1e-9)
    sel = e > np.percentile(e, 55)
    if sel.sum() < 20:
        sel = np.ones_like(sel, dtype=bool)
    mel = np.log10((mag[sel] @ FB.T) + 1e-6)
    mfcc = dct2(mel)[:, :13]
    f0s = [f0_track(fr) for fr in sw[sel][::3]]
    f0s = np.array([v for v in f0s if v > 0])
    return {"mfcc_mean": mfcc.mean(axis=0), "mfcc_std": mfcc.std(axis=0),
            "f0": float(np.median(f0s)) if len(f0s) else 0.0,
            "f0_iqr": float(np.percentile(f0s, 75) - np.percentile(f0s, 25)) if len(f0s) else 0.0,
            "dur": len(x) / sr, "mfcc_seq": mfcc}


def dtw_cos(a, b, max_frames=250):
    """MFCC 序列 DTW 路径上的平均余弦相似度（容忍两条音频文本不同）。"""
    import librosa
    A, B = a[:max_frames], b[:max_frames]
    if len(A) < 8 or len(B) < 8:
        return 0.0
    _, wp = librosa.sequence.dtw(X=A, Y=B, metric="cosine", subseq=False)
    path = wp[::-1]
    sims = []
    for i, j in path:
        if i < len(A) and j < len(B):
            sims.append(float(np.dot(A[i], B[j]) /
                              (np.linalg.norm(A[i]) * np.linalg.norm(B[j]) + 1e-9)))
    return float(np.mean(sims)) if sims else 0.0


def cos(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


# ---------------------------------------------------------------- 说话人嵌入
def _install_webrtcvad_stub():
    """resemblyzer 顶层 import webrtcvad，但原生模块需要 MSVC 编译。
    本项目用 Silero VAD 做静音裁剪，因此塞一个只可导入的桩。"""
    stub_dir = AUDIT_DIR / "pystub"
    stub_dir.mkdir(parents=True, exist_ok=True)
    stub = stub_dir / "webrtcvad.py"
    if not stub.exists():
        stub.write_text(
            "# -*- coding: utf-8 -*-\n"
            "# 纯 Python 桩：resemblyzer 顶层 import webrtcvad，"
            "但本项目改用 Silero VAD 裁静音，故只需可导入。\n\n\n"
            "class Vad(object):\n"
            "    def __init__(self, *args, **kwargs):\n"
            "        raise NotImplementedError(\n"
            "            \"webrtcvad 桩：本机无 MSVC 编译器，请改用 trim_silence=False / Silero VAD\")\n\n"
            "    def is_speech(self, frame, sample_rate):\n"
            "        raise NotImplementedError(\"webrtcvad 桩\")\n",
            encoding="utf-8")
    sys.path.insert(0, str(stub_dir))


def get_encoder():
    """返回 (VoiceEncoder, silero_vad_model)。首次调用会下载/加载模型。"""
    _install_webrtcvad_stub()
    import torch
    from resemblyzer import VoiceEncoder
    from silero_vad import load_silero_vad
    return VoiceEncoder(verbose=False), load_silero_vad()


def _normalize_volume(wav, target_dBFS):
    int16_max = (2 ** 15) - 1
    rms = np.sqrt(np.mean((wav * int16_max) ** 2))
    d = target_dBFS - 20 * np.log10(rms / int16_max)
    return wav if d < 0 else wav * (10 ** (d / 20))


def embed_audio(enc, sivad, path, max_sec=45.0):
    """复刻 resemblyzer 官方 preprocess_wav，但用 Silero VAD 代替 webrtcvad 裁静音。
    两者目的相同：压掉长静音，避免静音段污染说话人嵌入。"""
    import librosa
    import resemblyzer.hparams as hp
    import torch
    from silero_vad import get_speech_timestamps
    wav, sr = librosa.load(str(path), sr=None)
    wav = librosa.resample(wav, orig_sr=sr, target_sr=hp.sampling_rate)
    wav = _normalize_volume(wav, hp.audio_norm_target_dBFS)
    ts = get_speech_timestamps(torch.from_numpy(wav.astype(np.float32)), sivad,
                               sampling_rate=hp.sampling_rate,
                               min_speech_duration_ms=200, speech_pad_ms=100)
    if ts:
        wav = np.concatenate([wav[t["start"]:t["end"]] for t in ts])
    return enc.embed_utterance(wav.astype(np.float32))
