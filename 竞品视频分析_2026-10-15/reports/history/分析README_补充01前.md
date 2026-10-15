# 阅见生活竞品视频分析｜V4.0 本地工作区

源素材：`D:\fuye\tools\wx_channel\downloads`。本目录独立于源素材；任何脚本只读源视频和 `records.db`，所有结果写在本目录。

## 当前范围

用户已确认 G1 样本与允许输入范围，现执行 V4 Phase 2。全量本地处理按332个来源路径、317个不同SHA内容运行，完全重复内容复用结果但保留全部video_id与来源。本目录的 `analysis_a/` 由 Antigravity 独占写入。Codex不自动向任何云模型上传素材。

## 目录

- `manifest/manifest.jsonl`：全部视频一文件一行，含完整来源路径和 SHA-256。
- `manifest/sample_plan.json`：10 条分层样本，选定后固定，重跑不变。
- `state/inventory/`、`state/decode/`、`state/<video_id>.json`：逐文件、逐步骤断点记录。
- `audio/`：本地抽取的16 kHz单声道WAV，仅供转录和验收；同SHA内容可复用。
- `transcripts/`、`segments/`、`frames/`：Codex 独占写入。`segments/<video_id>.json` 是 FunASR 原始输出；`segments/<video_id>.aligned.json` 是经词级时间戳重建并逐字校验的可读分段，交接包指向后者。
- `handoff/<video_id>/READY.json`：交接包最后写入；无 READY 的目录不可处理。
- `analysis_a/`：Antigravity 独占写入；Codex 不代写 AI 结论。
- `reports/`：盘点、样本验收与交接说明。

## 续跑命令

在 PowerShell 中运行（均不会修改源目录）：

```powershell
& 'D:\fuye\竞品视频分析_2026-10-15\.venv\Scripts\python.exe' 'D:\fuye\竞品视频分析_2026-10-15\phase2_run.py' --workers 3
py -3.10 'D:\fuye\竞品视频分析_2026-10-15\repair_alignments.py'
& 'D:\fuye\竞品视频分析_2026-10-15\.venv\Scripts\python.exe' 'D:\fuye\竞品视频分析_2026-10-15\phase2_analyze.py'
& 'C:\Users\Miche\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'D:\fuye\竞品视频分析_2026-10-15\phase2_audit.py'
& 'C:\Users\Miche\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'D:\fuye\竞品视频分析_2026-10-15\phase2_export.py'
& 'C:\Users\Miche\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' 'D:\fuye\竞品视频分析_2026-10-15\verify_workbook.mjs'
```

`phase2_run.py` 会拒绝与已确认活着的同任务主进程同时写入。成功步骤跳过；超长音频按约300秒在附近低能量处切分，已完成分段JSON不重写，单分段最多尝试2次。过程日志在 logs/，worker和主任务状态在 state/。本轮不再打开下载数据库，沿用已存的元数据。

## 交接与权限

`handoff` 包含转录、4帧和原视频本地路径；READY仅表示本地文件写完。原10条样本包中的 `external_upload_authorized=false` 是上一阶段写入的历史标记，后续用户确认记录见 manifest/g1_user_confirmation.json。用户本轮已表示输入范围确认，但未重复范围明细，A应遵循用户已确认的具体范围，不能把此记录解释为任意外传许可。Antigravity只写 analysis_a/，不改Codex的清单、状态、转录、截图、报告或Excel。

## Phase 2 已交付

332个来源路径、317个SHA内容，全部已完成转录或同SHA复用、时间戳、4帧及READY包；一个7-Sheet基础Excel已完成。正式深度分析限定clusters/deep_candidates.json中25条，不能把332个READY包解释为全部深度分析任务。

请把reports/Antigravity_Phase3_25条任务指令.md交给A；候选共约2.90小时，每批建议5条。A只写analysis_a/，先完成临时文件并校验合法JSON后原子重命名。现有3份试标注尚待修正，核心AI字段保持AI_PENDING。

真实断点与失败恢复证据见manifest/resume_test_result.json、logs/failures/。本批相似度已逐对复核21对，固定记录脚本不应作为新素材的自动人工验收。最终阶段性证据见manifest/phase2_delivery_acceptance.json。渲染工具局限见manifest/workbook_visual_qa.json；平台ID应从Excel文本单元格或manifest读取。

## Phase 4 当前最终交付

全项目终验PARTIAL：25条A分析全部整合，20条限定范围AI_OK、5条AI_REVIEW；307条按计划未做深度。5套模板中4套研究可用、1套草案待补证。以reports/最终验收报告.md及manifest/phase4_final_acceptance.json为准。

后续重导出使用phase4_export.py；Phase2导出命令属于历史阶段，不应覆盖当前整合版。phase4_import.py的固定视觉/更正记录适用于本批次，A补证更新后须先人工核对新增证据再刷新，不得把旧验收结论机械套用。
