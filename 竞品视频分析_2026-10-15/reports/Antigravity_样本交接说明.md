# Antigravity 样本交接说明（待用户授权后使用）

共享目录：`D:\fuye\竞品视频分析_2026-10-15`

本轮先等 Codex 完成并标记 `handoff/<video_id>/READY.json`，再由用户把本说明交给 Antigravity。Codex 不假设能够启动或控制 Antigravity。首次向 Gemini 等云端模型提交材料前，用户须确认允许的输入范围：仅转录文本、文本加截图，还是原 MP4；同时确认额度。`READY` 仅代表本地文件写完，不是云端上传许可。

## 两个能力测试样本

1. `v_7e9d12d17d945cb4`：林睿读书&书在橱窗，约 421 秒，《资治通鉴》相关，画面含插画/历史叙事。交接包：`handoff/v_7e9d12d17d945cb4/`。
2. `v_30cc827b5d5dd936`：赵健的读书日记，约 180 秒，旧书店真人实拍。交接包：`handoff/v_30cc827b5d5dd936/`。

两条画面形式不同，适合分别测试原 MP4 的声音和画面理解。只有 `READY.json` 存在才读取该包。两个 `original_video.path.txt` 仅提供本地路径，不代表模型已经读到视频。

## 测试与记录

对每条分别核对：指定秒数真实画面、对应口播、首次引书时间、末尾是否有购买引导。答案须与原视频或 Codex 的时间戳及截图对照，并记下冲突与不确定项。只读到路径、标题、缩略图或元信息，不得标 `native_video` 成功。

若当前产品不支持完整 MP4 音画输入，改用 `transcript.txt + frames/*.jpg`，把 `input_mode` 记为 `text_plus_frames`；只读文本则记 `text_only`。这两种模式不能推断完整镜头节奏或音乐。输出 `analysis_a/MP4能力验证.md`，说明输入方式、可能的云端传输范围、四项测试证据、限制与结论。

用户确认 G1 后，Antigravity 可从已就绪样本中先试分析 3～5 条。只写 `analysis_a/<video_id>.json`，先临时写入并校验合法 JSON，再原子重命名。每条最少包括 `video_id`、`input_mode`、`analyzed_at`、`fields`、`evidence`、`limitations`、`status`、`schema_version`。不要修改 Codex 的清单、状态、转录、截图、报告或 Excel，不要自动扩大到全部视频。
