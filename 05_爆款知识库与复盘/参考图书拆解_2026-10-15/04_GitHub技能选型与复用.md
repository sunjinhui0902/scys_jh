# GitHub技能选型与复用

检索与查看日期：2026-10-15。以下依据仓库README和SKILL.md的当前内容，区分“看过”“安装”“执行验证”，不按星数判断拆解质量。

| GitHub来源 | 适配判断 | 本次动作 |
| --- | --- | --- |
| [noahnan-max/book-to-skill](https://github.com/noahnan-max/book-to-skill/tree/main/book-to-skill) | 有来源地图、定向阅读、证据锚点、冲突保留；最适合作为拆书骨架 | 已安装到用户技能目录，读取主技能与相关参考文件；本轮按快速资料包轻量适配 |
| [anthropics/skills/pdf](https://github.com/anthropics/skills/tree/main/skills/pdf) | 提供PDF提取与扫描件OCR路线，解决“读不出文字”的前置问题 | 已查看；本机已有PDF技能，不重复安装；本轮使用本地PDFium与RapidOCR完成抽页识别 |
| [nutllwhy/whiteboard-book-video-skill](https://github.com/nutllwhy/whiteboard-book-video-skill) | 可参考短视频脚本与分镜字段，但默认白板火柴人、另有音视频工具依赖 | 已查看，未安装和运行；当前古建实景方向不直接套其视觉风格，也未验证渲染链路 |
| [Heybinshao/book-distiller](https://github.com/Heybinshao/book-distiller) | 倾向全文逐概念提取、保留原话；耗时和产物规模较大，且与本轮快速选题需求不同 | 已查看，未安装；不把大篇幅摘抄作为本项目的默认复用方式 |

## 实际采用的组合

1. `book-to-skill`：来源地图与定向阅读思路。安装时main提交为 `96e8bb5d31b383b3473af57d7915acfa3a887f21`；上游未提供可识别的LICENSE文件，本项目不复制或公开转存它的整包内容。
2. 项目已有 `wechat-channels-book-commerce`：从受众问题出发独立写口播、保留事实对应关系、按商品版本引书。
3. 本项目新增 `reference-book-to-video`：组织已建立的章节索引、定向OCR和选题卡格式。它是本项目独立撰写的操作适配，不声称史地书本身给出了短视频方法论。

上游的完整知识包还有候选方法验证、压力测试、概念合并等质量门。本轮主要交付史地内容资料和稿件，没有宣称完整通过上游七模块或把历史个案验证成普适方法。

外部技能已安装，下轮对话可以调用 `book-to-skill`。随仓库迁移的专用入口是 `.agents/skills/reference-book-to-video/SKILL.md`，按本项目约定保留在项目内。

## 本地复用操作

从项目根目录执行。仅首次需要安装独立依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-book-analysis.txt
```

重新盘点参考图书：

```powershell
.\.venv\Scripts\python.exe scripts/reference_books.py inventory
```

按CSV目录查到页码后，只识别要读的页：

```powershell
.\.venv\Scripts\python.exe scripts/reference_books.py ocr --book B02 --pages 53-54
.\.venv\Scripts\python.exe scripts/reference_books.py show --book B02 --pages 53-54
```

示例为泉州条目。这里的页码始终是PDF阅读器页序，从1开始；不是纸书页码。B01正文目前“PDF页=纸书页+59”，B02/B03加9，B04加7；只有当前扫描文件的已定位正文适用，换文件须重新核对。

书号B01等是当前清单中的定位符；增加、改名书籍后应重新盘点并核对映射。真正的原件身份由SHA-256校验；源文件变化时OCR脚本停止，避免接着读旧缓存。缓存按原件指纹、引擎和渲染参数区分，原件不受修改。

目前脚本只实现本地盘点、抽页OCR、读缓存，不会调用外部付费解析接口，也不会自动发布视频或上传PDF。脚本已实跑4本64页，另验证命中缓存及越界拒绝；不是对未来所有扫描版式的识别效果保证。

## 给其他助手的简短交接词

> 在当前项目使用 reference-book-to-video。先读“参考图书拆解_2026-10-15/README.md”和城市章节索引，按指定城市挑两到四页原文核读，输出一个疑问、二到三个有页码的事实、完整原创口播和对应镜头。区分史实、传说、游记与OCR不确定处；商品未指定时只做内容稿。原件、OCR全文和页面图像保留本机，已有结果不覆盖，新修订另存批次。
