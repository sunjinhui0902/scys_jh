---
name: scys-workspace
description: 维护 scys_jh 个人视频工作台，处理 GitHub 同步、跨电脑恢复、环境检查和大文件备份；仅用于本项目。
---

# scys_jh 工作台维护

先读仓库根目录 README.md；换电脑、恢复媒体或安装软件时再读 docs/换电脑与日常使用.md。

使用 `scripts/doctor.py` 检查当前环境。路径均从项目根目录推导。GitHub 目标由 git remote 核实，当前约定 sunjinhui0902/scys_jh，用户已于 2026-10-15 明确要求改为 PUBLIC；按此核对，未经用户再次要求不得改变可见性。不可复制旧机令牌或 cookies；新机在浏览器重新登录。

日常同步先检查 git status，再用 `git pull --ff-only`。需要提交时检查实际差异，运行 `python scripts/check_secrets.py --staged`，只提交本任务改动。远端分叉停止自动合并并说明冲突。用户已授权的同步不重复索要确认；本技能本身不授予推送权限。

大文件由 `scripts/bundle.py` 维护。`restore --group core --group software` 恢复创作素材及工具；按需加入 analysis。支持 SHA-256 检查和重复文件去重。默认不覆盖已有不同内容。新增或修改媒体时用新的 tag 运行 `pack --tag <新版本> --upload`，确认所有附件上传成功后提交 config/bundle-manifest.json。禁止覆写已发布恢复包。

使用 `scripts/relocate.py` 生成本机路径副本，保留 Git 内的历史证据。完成后报告已同步提交、恢复文件数量和未通过的检查。

用户已明确原始视频不上传，只存结果。打包必须排除采集目录、提取音频与模型缓存；保留开发素材、成片和分析结果。
