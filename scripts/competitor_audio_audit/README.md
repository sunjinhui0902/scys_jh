# 竞品音频审计工具链

分析 `00_对标与采集工具/视频号下载成果/` 下竞品视频的**音频**：判断 BGM 是否同源、把口播人声从混音里干净抽出来、判定竞品共用的是哪款 TTS 音色，并把结论转成我们自己可量产的可执行参数。

配套报告：
- `05_爆款知识库与复盘/14_竞品音频复用分析_1116-1117批次_2026-11-18.md`（BGM 部分）
- `05_爆款知识库与复盘/15_竞品口播人声复用分析_1116-1117批次_2026-11-18.md`（口播人声部分）

---

## 为什么用「说话人嵌入」而不是听感 / MFCC

听感识别分不出「同一音色」和「同音域的不同音色」；MFCC + DTW 在**不同文本**之间比较时，相似度主要被文内容带偏（实测组内 0.669 vs 跨组 0.703，几乎无差，**判别力不足**）。

本工具链改用 Resemblyzer（VGGish 说话人嵌入，256 维），并且**阈值不套用经验值**——先用候选池自校准：

| 校准对 | 余弦范围 | 含义 |
|---|---|---|
| 同一底层说话人的不同参数变体（云健 3 档 / 云扬 3 档 / 云希 2 档） | 0.873 – 0.970 | 「同一说话人」基准 |
| 不同说话人（云健 / 云扬 / 云希 / 云夏 / 晓晓 / 晓伊 / 晓北 / 晓妮） | 0.589 – 0.910 | 「异说话人」基线 |

---

## 脚本一览

| 脚本 | 作用 | 前置 | 验证状态 |
|---|---|---|---|
| `common.py` | 共享工具层：MFCC/F0 特征、DTW、说话人嵌入、路径与 ffmpeg 定位 | `numpy librosa resemblyzer silero-vad torch` | ✅ 本批次实跑通过 |
| `extract_voice.py` | **相减法提取口播人声**：原混音 − Instrumental 分轨，并做 VAD 空隙残余自检 | 需先跑 `separate_instrumental.py` | ✅ 本批次实跑通过（13/13） |
| `separate_instrumental.py` | UVR-MDX-NET-Inst_HQ_3 伴奏分离（去人声） | `audio-separator onnxruntime`；首次会下模型 | ✅ 本批次实跑通过（13/13） |
| `speaker_cluster.py` | **说话人嵌入判定**：谁在共用同一音色；竞品音色是否属于可调用的公共音色库 | 需先跑 `extract_voice.py` + `synth_candidates.py` | ✅ 本批次实跑通过 |
| `synth_candidates.py` | 合成候选音色池：Edge 公共音色（免密钥）/ MiniMax 系统音色（自有 key） | MiniMax 需 `config/voice_api/config.yaml` 或 `MINIMAX_API_KEY` | ✅ 本批次实跑通过 |
| `build_ab_sample.py` | 音色 A/B 样片：同画面同文案，只换配音参数，产出样片 + 对照串烧 | 需要一个已有成片的工程目录 | ✅ 本批次实跑通过 |
| `bgm_candidates.py` | **授权 BGM 候选抓取 + 上线校验**：从 Mixkit / FreePD 拉候选，测时长/电平/无人声，按目标电平归一 | `numpy librosa silero-vad`（VAD 可选） | ✅ 本批次实跑通过 |
| `build_bgm_audition.py` | **选曲试听串烧**：每首候选前用 Edge-TTS 报曲名，产出三类赛道的试听 mp3 + 顺序表 | `edge-tts` | ✅ 本批次实跑通过 |
| `verify_bgm_level.py` | **BGM 电平落地验证**：同一条人声 + 同套管线增益，只换 BGM 源版本，用人声停顿段实测两档差异 | `librosa silero-vad` | ✅ 本批次实跑通过 |

批次元数据在 `data/1116_1117/`：`manifest.json`（13 条视频清单，含当时的本机绝对路径，作历史证据保留）、`vad_speech.json`、`style_labels.json`。

---

## 用法

```bash
# 0) 准备批次元数据（manifest 描述要分析哪些视频）
#    字段：path / account / day / tag / wav / audio_sec
#    wav 指向 22.05k 单声道音轨；不存在时会用 path 自动抽取

# 1) 伴奏分离（慢：每条 240 秒片段约 20–25 分钟墙钟）
python scripts/competitor_audio_audit/separate_instrumental.py --manifest <manifest.json>

# 2) 相减法提取口播人声（秒级）
python scripts/competitor_audio_audit/extract_voice.py --manifest <manifest.json>

# 3) 候选音色池（Edge 免密钥；MiniMax 用自有 key）
python scripts/competitor_audio_audit/synth_candidates.py --engine all

# 4) 判定谁在共用同一音色、是否属于公共音色库
python scripts/competitor_audio_audit/speaker_cluster.py --threshold 0.90

# 5) 生成音色 A/B 样片（不改任何默认参数，只产出对比件）
python scripts/competitor_audio_audit/build_ab_sample.py --project W6_11-08_1900

# 6) 授权 BGM 候选：列表 / 下载+校验 / 归一 / 校验本地文件
python scripts/competitor_audio_audit/bgm_candidates.py list   --source freepd --channel epic
python scripts/competitor_audio_audit/bgm_candidates.py fetch  --source freepd --channel epic
python scripts/competitor_audio_audit/bgm_candidates.py fetch  --source mixkit --channel traditional
python scripts/competitor_audio_audit/bgm_candidates.py check  "01_配音与音色库/背景音乐库/bgm_shili_guofeng.mp3"
python scripts/competitor_audio_audit/bgm_candidates.py normalize <候选.mp3> --target-mean-db -23

# 7) 生成选曲试听串烧（带口播报曲名）
python scripts/competitor_audio_audit/build_bgm_audition.py

# 8) BGM 电平落地验证（A档旧默认 vs B档新默认）
python scripts/competitor_audio_audit/verify_bgm_level.py
```

产物落在 `scratch/competitor_audio_audit/`（运行时工作区，不入库）与 `02_公共资产库/竞品口播人声_*/`（资产与清单，JSON 入库、音频不入库）。

---

## 关键工程决策

### 1. 相减法代替全长神经人声分离
竞品人声占比 87–98%，且 v02/v04/v06 **全程无无人声空隙**，靠「找干净片段」行不通。
`原混音 − Instrumental 分轨` 快两个数量级（后者 180s 片段约 25 分钟墙钟、4 进程抢 18 核会吃满 31.5 GB 内存），代价是相减前必须做**样本级对齐**，否则人声被抵消。

质量自检是客观的：Silero VAD 标出「纯音乐空隙」，量空隙残余与声段的能量差。本批次 13 条中 8 条有可用空隙样本，差值 5.5–24.2 dB；**v13 只有 5.5 dB，分离较差，不建议直接当素材用**。

### 2. 两条踩过的坑（务必保留对应写法）

- **对 mp3 直接 `-stream_loop -1` 会在文件尾触发解码错误**（`Invalid data fo` / `Header missing`），ffmpeg 可能直接卡死。
  → 先 `-stream_loop N -i x.mp3 -c:a pcm_s16le` 转成 PCM wav，再对 wav 做循环。
- **`-stream_loop` 视频流 + 输出侧 `-t` 截断会写出损坏的 mp4**（`Invalid NAL unit size`、`moov atom not found`）。
  → 预先生成一份干净的 `_video_only_Ns.mp4`（`-c:v copy` 不重编码），再用 `-c:v copy -shortest` 拼音频。

### 3. webrtcvad 编译门槛
`resemblyzer` 顶层 `import webrtcvad`，而原生模块需要 MSVC 编译器（Python 3.14 无预编译轮）。
本工具链改用 Silero VAD 做静音裁剪（目的相同：压掉长静音），并自带 `pystub/webrtcvad.py` 桩保证可导入。

---

## 本批次结论摘要（2026-11-16 / 11-17，13 条）

- **BGM 两两不同源**（波形归一化互相关最高仅 0.51），但 13/13 全是公共曲库通用曲，无专属性质曲风。
- **口播 13 条全部可提取**，交付在 `02_公共资产库/竞品口播人声_20261116-17/`。
- **主簇 7 条（6 个账号）共用同一音色**：组内说话人余弦均值 0.9436，簇间仅 0.7202。
- **该音色不在 Edge / MiniMax 公共音色库**：33 个候选中最高 0.689（还是我们自己的黄金音），远低于同说话人基准 0.873。
  → 继续在 Edge/MiniMax 里找没有意义；真正「同款」只能接视频号生态同源的火山/豆包系 TTS，或用已有的克隆流程。
- **零版权风险的可复用项**：F0 150–175Hz、语速 30–41 段/分、平均句长 1.7–2.5 秒。

---

## 边界

- 「公共 TTS 而非克隆音」是**强推断**（7 条来自 6 个不相关账号却音色一致），不是直接证明。
- **具体引擎未锁定**：火山/豆包/讯飞/Azure 均未实测；本机网络下多数 Azure 中文音色返回 `NoAudio was received`。
- **原文案未获取**：ASR 通道不可用（`connector__matrix__listen_audio` 执行失败，本机也无 funasr/whisper），未做「同文本同音色」的终极验证。
- 曲名、引擎归属等听感类结论来自多模态模型，**未经人工试听复核**。
- 竞品音轨只作**内部对标参考**，不作成片素材，也不进任何恢复包。
