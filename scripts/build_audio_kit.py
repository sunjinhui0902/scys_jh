#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""构建「minimax 音频调用说明」资产包。

把仓库里的配音音色、背景音乐资产、调用脚本整理成一份可独立分发的包：
    04_自动化生产流水线/minimax_音频调用说明/          （包目录）
    04_自动化生产流水线/minimax_音频调用说明.zip       （压缩包）

用法：
    python scripts/build_audio_kit.py            # 构建目录 + 清单 + zip
    python scripts/build_audio_kit.py --no-zip   # 只构建目录与清单
    python scripts/build_audio_kit.py --check    # 只跑安全校验，不写文件

安全红线（构建时强制校验，违反直接中止）：
    1. 不含 config/voice_api/config.yaml（含密钥），只放 config.example.yaml
    2. 不含 02_公共资产库/竞品口播人声_20261116-17/ 与 竞品BGM素材_20261116-17/ 的任何文件
    3. 不含密钥原文（对 config.yaml 里的 api_key 做逐字节比对）

音频与 zip 不入 Git（.gitignore 已排除 *.mp3/*.wav/*.zip），md/JSON/脚本入库。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG_NAME = "minimax_音频调用说明"
PKG_DIR = ROOT / "04_自动化生产流水线" / PKG_NAME
ZIP_PATH = ROOT / "04_自动化生产流水线" / f"{PKG_NAME}.zip"

CST = timezone(timedelta(hours=8))

# ---------------------------------------------------------------- 素材定义

VOICE_DIR = ROOT / "01_配音与音色库"
BGM_LIB = VOICE_DIR / "背景音乐库"
CANDIDATE_ROOT = ROOT / "02_公共资产库" / "授权BGM候选_20261119"
ROLES_DIR = VOICE_DIR / "六角色定稿_V1_20261107"
CLONE_SRC = VOICE_DIR / "对标原声参考" / "食力过日子_带孙辈长见识_下集"

# 克隆参考片段：从自有账号成片音轨切出的整句片段（VAD 对齐 + 三路提示词 ASR 交叉验证）
CLONE_REF_START = 27.042
CLONE_REF_DURATION = 9.052
CLONE_REF_TEXT = "那一排一排的陶俑，每一个脸都不一样。您跟孩子讲，这是两千多年前秦始皇的陪葬品。"

# (包内相对路径, 仓库内来源相对路径, 分类, 用途说明)
COPY_ASSETS: list[tuple[str, str, str, str]] = [
    # ---- 01_音色 ----
    ("01_音色/主线三音色/01_央视纪录片_沧桑历史男声.mp3",
     "01_配音与音色库/01_央视纪录片_沧桑历史男声.mp3",
     "音色-主线", "默认音色（央视纪录片·沧桑历史男声）样本"),
    ("01_音色/主线三音色/03_文化讲书_自然叙事男声.mp3",
     "01_配音与音色库/03_文化讲书_自然叙事男声.mp3",
     "音色-主线", "备选音色（文化讲书·自然叙事男声）样本"),
    ("01_音色/主线三音色/05_三晋风味_关中厚重女声.mp3",
     "01_配音与音色库/05_三晋风味_关中厚重女声.mp3",
     "音色-主线", "备选音色（三晋风味·关中厚重女声）样本"),
    ("01_音色/selected_voices.json",
     "01_配音与音色库/selected_voices.json",
     "音色-配置", "音色选择记录（机器可读，含默认基准与 A/B 音色 ID）"),
    ("01_音色/六角色定稿_家庭钩子/六角色定稿配置.json",
     "01_配音与音色库/六角色定稿_V1_20261107/六角色定稿配置.json",
     "音色-配置", "六角色定稿音色表"),
    ("01_音色/六角色定稿_家庭钩子/role_selections.json",
     "config/voice_api/role_selections.json",
     "音色-配置", "六角色选择记录（含样本 SHA-256 与计费说明）"),
    ("01_音色/听感基准/平遥古城_学者大家男声_食力BGM混音_清晰版.mp3",
     "01_配音与音色库/试听样本/平遥古城_学者大家男声_食力BGM混音_清晰版.mp3",
     "音色-试听", "黄金组合听感基准：央视纪录片男声 + 食力 BGM 混音成品"),
    ("01_音色/听感基准/平遥古城_文化讲书男声_食力BGM混音_清晰版.mp3",
     "01_配音与音色库/试听样本/平遥古城_文化讲书男声_食力BGM混音_清晰版.mp3",
     "音色-试听", "备选音色 + 食力 BGM 混音成品"),
    # ---- 02_背景音乐 ----
    ("02_背景音乐/默认_食力过日子_国风古琴_B档.mp3",
     "01_配音与音色库/背景音乐库/bgm_shili_guofeng.mp3",
     "BGM-默认", "默认 BGM（B 档，源 mean −23.3 dBFS，管线默认取这一份）"),
    ("02_背景音乐/默认_食力过日子_国风古琴_原始-52.9dB_回退源.mp3",
     "01_配音与音色库/背景音乐库/_原始备份/bgm_shili_guofeng_原始-52.9dB.mp3",
     "BGM-默认", "原始 −52.9 dBFS 版本（回退源；混音内实际听不见）"),
    ("02_背景音乐/选曲清单.json",
     "02_公共资产库/授权BGM候选_20261119/选曲清单.json",
     "BGM-清单", "18 首选曲的授权 / 电平 / 听感 / 下载直链"),
    ("02_背景音乐/授权候选总表.json",
     "02_公共资产库/授权BGM候选_20261119/授权BGM候选清单.json",
     "BGM-清单", "全部 176 首候选指纹（Mixkit 168 + FreePD 8）"),
    # ---- 03_调用脚本 ----
    ("03_调用脚本/scripts/voice_api_tts.py",
     "scripts/voice_api_tts.py", "脚本", "MiniMax TTS / Edge TTS 配音入口"),
    ("03_调用脚本/scripts/assemble_voice_test.py",
     "scripts/assemble_voice_test.py", "脚本", "配音混音与拼接（voice_api_tts 依赖）"),
    ("03_调用脚本/scripts/clone_voice_ztts.py",
     "scripts/clone_voice_ztts.py", "脚本", "E2-F5-TTS 零样本克隆入口"),
    ("03_调用脚本/scripts/fast_draft_pipeline.py",
     "scripts/fast_draft_pipeline.py", "脚本", "极速草稿装配管线（init / apply-images）"),
    ("03_调用脚本/scripts/competitor_audio_audit/bgm_candidates.py",
     "scripts/competitor_audio_audit/bgm_candidates.py", "脚本", "BGM 抓取 / 校验 / 归一"),
    ("03_调用脚本/scripts/competitor_audio_audit/build_bgm_audition.py",
     "scripts/competitor_audio_audit/build_bgm_audition.py", "脚本", "生成选曲试听串烧"),
    ("03_调用脚本/scripts/competitor_audio_audit/verify_bgm_level.py",
     "scripts/competitor_audio_audit/verify_bgm_level.py", "脚本", "VAD 停顿段电平实测"),
    ("03_调用脚本/scripts/competitor_audio_audit/common.py",
     "scripts/competitor_audio_audit/common.py", "脚本", "公共库：路径与 ffmpeg 定位"),
    ("03_调用脚本/scripts/competitor_audio_audit/pystub/webrtcvad.py",
     "scripts/competitor_audio_audit/pystub/webrtcvad.py", "脚本", "webrtcvad 占位实现"),
    ("03_调用脚本/04_自动化生产流水线/workspace_paths.py",
     "04_自动化生产流水线/workspace_paths.py", "脚本", "可移植路径（fast_draft_pipeline 依赖）"),
    ("03_调用脚本/config/voice_api/config.example.yaml",
     "config/voice_api/config.example.yaml", "配置-模板", "MiniMax 密钥配置模板（不含密钥）"),
    ("03_调用脚本/01_配音与音色库/背景音乐库/bgm_shili_guofeng.mp3",
     "01_配音与音色库/背景音乐库/bgm_shili_guofeng.mp3",
     "脚本-运行时资产", "管线默认 BGM 路径占位：fast_draft_pipeline 按此相对路径取 BGM"),
    ("03_调用脚本/01_配音与音色库/背景音乐库/_原始备份/bgm_shili_guofeng_原始-52.9dB.mp3",
     "01_配音与音色库/背景音乐库/_原始备份/bgm_shili_guofeng_原始-52.9dB.mp3",
     "脚本-运行时资产", "A 档回退 BGM：verify_bgm_level.py 做 A/B 对照时按此路径取旧版"),
    ("03_调用脚本/03_视频成片与工程/音色对比_20261118/V1_当前默认_云健-6Hz-8%/voice_master.mp3",
     "03_视频成片与工程/音色对比_20261118/V1_当前默认_云健-6Hz-8%/voice_master.mp3",
     "脚本-运行时资产", "电平验证用的人声轨（V1 当前默认云健 −6Hz/−8%），verify_bgm_level.py 依赖"),
    # ---- 试听串烧（挑曲依据） ----
    ("02_背景音乐/试听串烧/国风古建_试听.mp3",
     "03_视频成片与工程/BGM试听_20261119/国风古建_试听.mp3",
     "BGM-试听", "国风古建赛道 6 首试听串烧（每首前有口播报曲名）"),
    ("02_背景音乐/试听串烧/史诗解说_试听.mp3",
     "03_视频成片与工程/BGM试听_20261119/史诗解说_试听.mp3",
     "BGM-试听", "史诗解说赛道 6 首试听串烧（每首前有口播报曲名）"),
    ("02_背景音乐/试听串烧/温情叙事_试听.mp3",
     "03_视频成片与工程/BGM试听_20261119/温情叙事_试听.mp3",
     "BGM-试听", "温情叙事赛道 6 首试听串烧（每首前有口播报曲名）"),
    ("02_背景音乐/试听串烧/全套_试听.mp3",
     "03_视频成片与工程/BGM试听_20261119/全套_试听.mp3",
     "BGM-试听", "18 首全套串烧（366.6 秒）"),
    ("02_背景音乐/试听串烧/试听顺序.txt",
     "03_视频成片与工程/BGM试听_20261119/试听顺序.txt",
     "BGM-试听", "串烧播放顺序与曲名对照表"),
]

# 授权凭证（网页许可快照）
CREDENTIAL_FILES = [
    "剪映_商用音乐说明_2026-11-19.txt",
    "Mixkit_许可页_2026-11-19.txt",
    "Mixkit_音乐库首页_2026-11-19.txt",
    "Mixkit_traditional分类页_2026-11-19.txt",
    "FreePD_服务条款_2026-11-19.txt",
    "FreePD_epic分类页_2026-11-19.txt",
]

# 归一两档目录名 → 包内目录名
LEVEL_DIRS = [
    ("B_可听见_mean-23dB", "授权候选_B档_可听见_mean-23dB"),
    ("A_与现状一致_mean-52.9dB", "授权候选_A档_与现状一致_mean-53dB"),
]

# ---------------------------------------------------------------- 工具函数


SCRIPT_USAGE_MD = """# 调用脚本使用说明

> 本目录是 `minimax 音频调用说明` 资产包的**可运行副本**。
> 目录结构按仓库布局镜像，所以脚本里 `Path(__file__).resolve().parents[1]` 仍然指向
> **本目录**——把整个 `03_调用脚本/` 当成一个迷你仓库根即可直接运行，无需回到主仓库。

## 一、目录结构

```
03_调用脚本/                       ← 迷你仓库根（脚本的 ROOT 就是这里）
├── scripts/
│   ├── voice_api_tts.py            MiniMax / Edge 配音入口
│   ├── assemble_voice_test.py      混音拼接（voice_api_tts 依赖）
│   ├── clone_voice_ztts.py         E2-F5-TTS 零样本克隆入口
│   ├── fast_draft_pipeline.py      极速剪映草稿装配管线
│   └── competitor_audio_audit/
│       ├── bgm_candidates.py       BGM 抓取 / 校验 / 归一
│       ├── build_bgm_audition.py   选曲试听串烧
│       ├── verify_bgm_level.py     VAD 停顿段电平实测
│       ├── common.py               路径与 ffmpeg 定位
│       └── pystub/webrtcvad.py     webrtcvad 占位实现
├── 04_自动化生产流水线/
│   └── workspace_paths.py          可移植路径（fast_draft_pipeline 依赖）
├── config/voice_api/
│   └── config.example.yaml         MiniMax 密钥模板（**不含密钥**）
├── 01_配音与音色库/背景音乐库/
│   ├── bgm_shili_guofeng.mp3       管线默认 BGM 位置（B 档 −23 dBFS）
│   └── _原始备份/
│       └── bgm_shili_guofeng_原始-52.9dB.mp3   A 档回退源（电平对照用）
└── 03_视频成片与工程/音色对比_20261118/
    └── V1_当前默认_云健-6Hz-8%/voice_master.mp3  电平验证用的人声轨
```

> `01_配音与音色库/背景音乐库/bgm_shili_guofeng.mp3` 不是多余文件：
> `fast_draft_pipeline.py` 找不到 BGM 时按**这个相对路径**回退查找，删掉它草稿里就没 BGM 了。
> `_原始备份/` 与 `音色对比_20261118/` 是 `verify_bgm_level.py` 做 A/B 电平对照的输入。

## 二、首次配置（只做一次）

```bash
# 复制密钥模板并填入自己的 MiniMax API Key
cp config/voice_api/config.example.yaml config/voice_api/config.yaml
```

也可以不建文件，直接设环境变量 `MINIMAX_API_KEY`（**环境变量优先**）。
中国区 key 用 `https://api.minimaxi.com`；国际区改 `https://api.minimax.io`。

Edge-TTS 路线和 E2-F5-TTS 克隆路线**都不需要任何 key**。

## 三、四条命令

### 1）Edge-TTS 试音（免费免密钥，主力路线）

```bash
python -c "import asyncio,edge_tts; asyncio.run(edge_tts.Communicate('今天我们讲的是平遥古城','zh-CN-YunjianNeural',pitch='-6Hz',rate='-8%').save(r'out.mp3'))"
```

### 2）MiniMax 六声线合成（需要自有 key）

```bash
python scripts/voice_api_tts.py --config config/voice_api/config.yaml --pack
python scripts/voice_api_tts.py --role 奶奶 --text "你也在看着它呀。"
python scripts/voice_api_tts.py --pack --no-new-minimax      # 禁止新增付费请求
```

### 3）E2-F5-TTS 克隆（免费免 key）

包内已备好**切好的参考片段 + 逐字参考文本**（见 `../01_音色/克隆参考_方案A/`）：

```bash
# 先干跑，检查切句，不发请求
python scripts/clone_voice_ztts.py \\
  --ref-audio "../01_音色/克隆参考_方案A/参考片段_食力日子_27.042s_9.052s.wav" \\
  --ref-start 0 --ref-duration 9.052 \\
  --ref-text "../01_音色/克隆参考_方案A/参考文本.txt" \\
  --script "<你的口播文案.md>" \\
  --out-dir "./克隆输出" \\
  --chunk-min 18 --chunk-max 40 --dry-run

# 去掉 --dry-run 即正式合成
```

> **参考文本必须逐字对应参考音频**。包内这份已用 Silero VAD + 三路 ASR 交叉验证过，
> 可以直接用；换成别的参考片段时必须重新逐字核对，否则克隆出的音色会明显漂。

### 4）BGM 归一与校验（不需要 key）

```bash
python scripts/competitor_audio_audit/bgm_candidates.py check "<文件>.mp3"
python scripts/competitor_audio_audit/bgm_candidates.py normalize "<文件>.mp3" --target-mean-db -23 --peak-cap -3
```

> `normalize` 默认把成品写到 `<脚本根>/02_公共资产库/授权BGM候选_20261119/已归一/`，
> 用 `--out-dir` 可以改到别处。`list` / `fetch` 会联网抓 Mixkit / FreePD，
> `fetch` 也建议显式给 `--out-dir`。

### 5）一键装配剪映草稿

```bash
python scripts/fast_draft_pipeline.py init --dir "<项目目录>"
python scripts/fast_draft_pipeline.py apply-images --dir "<项目目录>"
```

管线会按 `01_配音与音色库/背景音乐库/bgm_shili_guofeng.mp3` 取 BGM（增益固定 −13 dB），
并给解说人声轨加 +3 dB。

### 6）电平实测复核（不需要 key）

```bash
python scripts/competitor_audio_audit/verify_bgm_level.py
```

包内已备好它需要的三个输入（人声轨、B 档 BGM、A 档回退 BGM），可直接跑出停顿段电平对照。

## 四、哪些脚本在包内跑不了（按需回仓库跑）

| 脚本 | 原因 | 怎么办 |
|---|---|---|
| `build_bgm_audition.py` | 它读的是**原始下载池** `02_公共资产库/授权BGM候选_20261119/<来源>/<分类>/*.mp3`，包内只收了 18 首**已归一成品** | 想重做试听串烧，回仓库跑；包内 `../02_背景音乐/试听串烧/` 已有成品可直接听 |
| `bgm_candidates.py list/fetch` | 需要联网重抓全站候选池（包内只有 18 首） | 同上 |

## 五、依赖

```bash
pip install edge-tts pyyaml gradio_client
pip install jieba pymediainfo pyJianYingDraft pillow
pip install numpy librosa silero-vad
```

`ffmpeg` 需要在 PATH，或用环境变量 `SCYS_FFMPEG` / `FFMPEG_BIN` 指定，
或装 `imageio-ffmpeg`（脚本会自动取其内置二进制）。

## 六、已知边界

- 草稿装配需要 **剪映草稿目录**：`SCYS_JIANYING_DRAFTS` 环境变量，默认
  `%LOCALAPPDATA%\\JianyingPro\\User Data\\Projects\\com.lveditor.draft`。
- `fast_draft_pipeline.py` 里 `02_公共资产库/00_固定书本实拍资产/` 只对特定项目生效，
  本包未收录该素材，缺了不影响其他项目。
- E2-F5-TTS 是**公共免费空间**，稳定性不由我们掌控；逐段独立合成，段间音色会漂。
  **必须保留 Edge / MiniMax 作兜底。**
"""


def find_ffmpeg() -> str:
    """定位 ffmpeg：环境变量 > 仓库内 > PATH。"""
    env = os.environ.get("FFMPEG_BIN") or os.environ.get("SCYS_FFMPEG")
    if env and Path(env).exists():
        return env
    hit = next((ROOT.glob("**/ffmpeg.exe")), None)
    if hit:
        return str(hit)
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def human(n: int) -> str:
    return f"{n / 1024 / 1024:.2f} MB" if n >= 1024 * 1024 else f"{n / 1024:.1f} KB"


# ---------------------------------------------------------------- 构建


def build_clone_reference(dst_dir: Path) -> list[dict]:
    """切出克隆参考片段，并写入已交叉验证的参考文本。"""
    src = CLONE_SRC / "voice_master.wav"
    dst_dir.mkdir(parents=True, exist_ok=True)
    clip = dst_dir / f"参考片段_食力日子_{CLONE_REF_START}s_{CLONE_REF_DURATION}s.wav"
    subprocess.run(
        [find_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
         "-ss", str(CLONE_REF_START), "-t", str(CLONE_REF_DURATION), "-i", str(src),
         "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", str(clip)],
        check=True,
    )
    (dst_dir / "参考文本.txt").write_text(CLONE_REF_TEXT + "\n", encoding="utf-8")
    meta = {
        "用途": "E2-F5-TTS 零样本克隆的参考音频 + 逐字参考文本",
        "来源": "自有账号《食力过日子·带孙辈长见识（下）》成片音轨",
        "来源文件": "01_配音与音色库/对标原声参考/食力过日子_带孙辈长见识_下集/voice_master.wav",
        "来源说明": "我们自己账号的成片音轨，可用作克隆参考；竞品 13 条口播音频绝对不可用于克隆",
        "切段起点_s": CLONE_REF_START,
        "切段长度_s": CLONE_REF_DURATION,
        "整句边界": "起点与终点均落在语音停顿处，片段含 2 个完整句子",
        "参考文本": CLONE_REF_TEXT,
        "参考文本验证方式": "Silero VAD 切分语音段定位句子边界 + 三种提示词 ASR 交叉复核，结果一致",
        "音频规格": "WAV 16-bit PCM / 单声道 / 44100 Hz（与 clone_voice_ztts.py 内部切片规格一致）",
        "已知背景": "片段含成片混音的 BGM 底噪，停顿间隙约 −36 dBFS、低于人声约 24 dB；"
                    "这是成片音轨原样，不是纯干声。克隆音色若不够纯可换参考段。",
        "用法": "python scripts/clone_voice_ztts.py --ref-audio <本文件> --ref-start 0 "
                f"--ref-duration {CLONE_REF_DURATION} --ref-text 参考文本.txt ...",
    }
    (dst_dir / "参考片段来源.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return [clip, dst_dir / "参考文本.txt", dst_dir / "参考片段来源.json"]


def collect_candidates() -> list[tuple[str, str, str, str]]:
    """展开 18×2 首归一候选 + 归一记录。"""
    out: list[tuple[str, str, str, str]] = []
    for src_dir, dst_dir in LEVEL_DIRS:
        base = CANDIDATE_ROOT / "已归一" / src_dir
        for f in sorted(base.iterdir()):
            if f.suffix.lower() == ".mp3":
                out.append((f"02_背景音乐/{dst_dir}/{f.name}", str(f.relative_to(ROOT)),
                            "BGM-授权候选", f"{dst_dir}：授权候选曲成品"))
            elif f.suffix.lower() == ".json":
                out.append((f"02_背景音乐/{dst_dir}/{f.name}", str(f.relative_to(ROOT)),
                            "BGM-授权候选", f"{dst_dir}：归一记录（源文件与 SHA-256）"))
    for name in CREDENTIAL_FILES:
        src = CANDIDATE_ROOT / "授权凭证" / name
        out.append((f"02_背景音乐/授权凭证/{name}", str(src.relative_to(ROOT)),
                    "BGM-授权凭证", "许可条款网页快照（授权依据）"))
    return out


def clean_runtime_output(pkg_dir: Path) -> list[str]:
    """清掉脚本运行后残留在包里的产物（scratch、克隆输出、电平验证输出等）。"""
    removed: list[str] = []
    for rel in ("03_调用脚本/scratch", "03_调用脚本/克隆输出",
                "03_调用脚本/03_视频成片与工程/BGM电平验证_20261120",
                "03_调用脚本/03_视频成片与工程/BGM试听_20261119"):
        target = pkg_dir / rel
        if target.exists():
            shutil.rmtree(target)
            removed.append(rel)
    return removed


def build_package(do_zip: bool = True) -> dict:
    # 只重建生成的子树；包根下手写的说明文档（README.md / 两份速查）保持原样
    for sub in ("01_音色", "02_背景音乐", "03_调用脚本"):
        target = PKG_DIR / sub
        if target.exists():
            shutil.rmtree(target)
    PKG_DIR.mkdir(parents=True, exist_ok=True)

    entries: list[dict] = []

    def add(rel: str, src: Path, category: str, purpose: str) -> None:
        dst = PKG_DIR / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        entries.append({
            "path": rel,
            "category": category,
            "purpose": purpose,
            "bytes": dst.stat().st_size,
            "sha256": sha256(dst),
            "source_in_repo": str(src.relative_to(ROOT)).replace("\\", "/"),
        })

    # 1) 固定素材
    for rel, src_rel, category, purpose in COPY_ASSETS:
        src = ROOT / src_rel
        if not src.is_file():
            raise SystemExit(f"源文件缺失：{src_rel}")
        add(rel, src, category, purpose)

    # 2) 授权候选与凭证
    for rel, src_rel, category, purpose in collect_candidates():
        src = ROOT / src_rel
        if not src.is_file():
            raise SystemExit(f"源文件缺失：{src_rel}")
        add(rel, src, category, purpose)

    # 3) 克隆参考片段（现场生成）
    clone_dir = PKG_DIR / "01_音色" / "克隆参考_方案A"
    for p in build_clone_reference(clone_dir):
        entries.append({
            "path": str(p.relative_to(PKG_DIR)).replace("\\", "/"),
            "category": "音色-克隆参考",
            "purpose": "E2-F5-TTS 零样本克隆参考片段与逐字参考文本（由源音轨现场切出）",
            "bytes": p.stat().st_size,
            "sha256": sha256(p),
            "source_in_repo": "01_配音与音色库/对标原声参考/食力过日子_带孙辈长见识_下集/voice_master.wav",
        })

    # 4) 包内脚本使用说明（由本脚本生成，保证与实际脚本一致）
    usage_md = PKG_DIR / "03_调用脚本" / "使用说明.md"
    usage_md.parent.mkdir(parents=True, exist_ok=True)
    usage_md.write_text(SCRIPT_USAGE_MD, encoding="utf-8")
    entries.append({
        "path": "03_调用脚本/使用说明.md",
        "category": "说明",
        "purpose": "包内脚本的使用说明（目录结构已按仓库布局镜像，可直接运行）",
        "bytes": usage_md.stat().st_size,
        "sha256": sha256(usage_md),
        "source_in_repo": "scripts/build_audio_kit.py（生成）",
    })

    # 5) 清单
    manifest = {
        "package": PKG_NAME,
        "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
        "repo": "scys_jh",
        "description": "配音音色 + 背景音乐资产包：什么时候用什么、怎么用",
        "safety": {
            "contains_secret": False,
            "contains_competitor_audio": False,
            "rules": [
                "不含 config/voice_api/config.yaml（MiniMax 密钥），只含 config.example.yaml",
                "不含 02_公共资产库/竞品口播人声_20261116-17/ 与 竞品BGM素材_20261116-17/ 任何文件",
                "不含任何密钥原文（构建时逐字节比对）",
            ],
        },
        "counts": {
            "files": len(entries),
            "bytes": sum(e["bytes"] for e in entries),
        },
        "files": sorted(entries, key=lambda e: e["path"]),
    }
    (PKG_DIR / "清单.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    validate(PKG_DIR)
    removed = clean_runtime_output(PKG_DIR)

    if do_zip:
        make_zip(PKG_DIR, ZIP_PATH)
        manifest["zip"] = {
            "path": str(ZIP_PATH.relative_to(ROOT)).replace("\\", "/"),
            "bytes": ZIP_PATH.stat().st_size,
            "sha256": sha256(ZIP_PATH),
        }
        if removed:
            manifest["cleaned_runtime_output"] = removed
        (PKG_DIR / "清单.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def make_zip(pkg_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for p in sorted(pkg_dir.rglob("*")):
            if p.is_file():
                zf.write(p, arcname=str(Path(pkg_dir.name) / p.relative_to(pkg_dir)))


def validate(pkg_dir: Path) -> None:
    """安全校验：密钥、竞品音频、密钥原文。任一命中直接中止。"""
    problems: list[str] = []

    banned_fragments = ["竞品口播人声", "竞品BGM素材", "竞品口播", "competitor_audio_2026"]
    for p in pkg_dir.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(pkg_dir)).replace("\\", "/")
        if any(frag in rel for frag in banned_fragments):
            problems.append(f"命中竞品音频红线：{rel}")
        if p.name == "config.yaml":
            problems.append(f"包含密钥配置文件：{rel}")

    # 密钥原文逐字节比对
    secret_cfg = ROOT / "config" / "voice_api" / "config.yaml"
    secrets: list[str] = []
    if secret_cfg.is_file():
        for line in secret_cfg.read_text(encoding="utf-8-sig").splitlines():
            if line.strip().startswith("api_key:"):
                val = line.split(":", 1)[1].strip().strip('"').strip("'")
                if len(val) >= 16:
                    secrets.append(val)
    for p in pkg_dir.rglob("*"):
        if not p.is_file() or p.suffix.lower() in {".mp3", ".wav", ".m4a", ".zip"}:
            continue
        try:
            body = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for s in secrets:
            if s in body:
                problems.append(f"密钥原文出现在：{p.relative_to(pkg_dir)}")

    if problems:
        for pb in problems:
            print(f"[红线] {pb}", file=sys.stderr)
        raise SystemExit("安全校验未通过，已中止构建")


def main() -> int:
    ap = argparse.ArgumentParser(description="构建 minimax 音频调用说明资产包")
    ap.add_argument("--no-zip", action="store_true", help="只构建目录与清单，不打 zip")
    ap.add_argument("--check", action="store_true", help="只跑安全校验")
    args = ap.parse_args()

    if args.check:
        validate(PKG_DIR if PKG_DIR.exists() else ROOT)
        print("安全校验通过")
        return 0

    manifest = build_package(do_zip=not args.no_zip)
    c = manifest["counts"]
    print(f"✅ 包目录：{PKG_DIR.relative_to(ROOT)}")
    print(f"   文件 {c['files']} 个，合计 {human(c['bytes'])}")
    if "zip" in manifest:
        print(f"✅ 压缩包：{manifest['zip']['path']}  {human(manifest['zip']['bytes'])}")
    print(f"   SHA-256：{manifest['zip']['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
