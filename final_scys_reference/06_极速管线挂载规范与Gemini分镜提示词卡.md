# 极速管线挂载规范与 Gemini 分镜提示词卡

> **定位**：直接挂载至本项目自动化工程生产流水线（`scripts/fast_draft_pipeline.py`）的工程化实操卡。  
> **核心目标**：从文案参考库选定题材 ➔ 调用 Gemini 极速生成口播与分镜 Prompt ➔ 15 秒一键生成剪映草稿 ➔ GPT 生图后 3 秒秒级热替换成片。

---

## 一、 流水线工程标准声学与剪辑装配参数

在调用 `scripts/fast_draft_pipeline.py init --dir "03_视频成片与工程/<项目名>"` 时，严格遵循以下基准配置：

```json
{
  "voice_config": {
    "engine": "edge-tts",
    "voice_name": "zh-CN-YunjianNeural",
    "rate": "-8%",
    "pitch": "-6Hz",
    "description": "01_央视纪录片·沧桑历史男声（低频极厚、从容沉静、字正腔圆，权威通识感）"
  },
  "bgm_config": {
    "bgm_file": "01_配音与音色库/背景音乐库/bgm_shili_guofeng.mp3",
    "volume_db": -13.0,
    "voice_boost_db": 3.0,
    "fade_out_sec": 3.0,
    "description": "食力过日子原版国风悠扬温情BGM，轻柔托底，中老年认同感极强"
  },
  "subtitle_config": {
    "font": "SimHei",
    "font_size": 42,
    "bottom_offset": 180,
    "highlight_color": "#FFCC00",
    "primary_color": "#FFFFFF",
    "stroke_color": "#000000",
    "stroke_width": 3,
    "description": "中老年大字底字幕，高对比度防眩目"
  },
  "motion_config": {
    "animation": "Ken_Burns_Native_Keyframes",
    "scale_range": [1.0, 1.08],
    "transition": "CrossDissolve",
    "transition_duration": 0.5
  }
}
```

---

## 二、 网页 Gemini 极速改稿与分镜提示词宏模板（一键复制使用）

当你在 `./final_scys_reference/` 中挑选好某一题材的钩子与转折后，将以下 Prompt 发送给 **网页 Gemini**：

````markdown
你现在是拥有千万粉丝的“中老年人文历史/地理慢游”头部短视频总编导。请根据我提供的【对标爆款主题/原稿】，进行去 AI 化的深度原创改编，严格输出两大部分：

### 【输入条件】
- **选题题材**：[例如：中国十大适合带孙辈长见识的历史名城 / 资治通鉴成事七律之稳 / 乡村大集]
- **目标商品**：[例如：《大美中国·一生要去的101个地方》 / 大字全本《资治通鉴》]
- **核心钩子模版编号**：[例如：H01 / H05 / H09]
- **转折桥模版编号**：[例如：B01 / B06 / B07]

### 【必须遵守的硬性规则】
1. **短句高气口**：平均分句长度严格控制在 7~9 字之间，多用逗号断句，适合纪录片男声朗读；
2. **全文篇幅**：总字数严格控制在 1,400 ~ 1,600 字（朗读时长约 3.5 ~ 4 分钟）；
3. **去 AI 空洞词汇**：严禁出现“震撼人心、气势恢宏、深厚底蕴、颠覆认知、格局破局”等书面词，全部替换为可见的动作、声音、烟火气生活细节；
4. **结构分配**：前 150 字立住悬念关系 ➔ 1,000 字正文（5~6 个递进点，带具体画面细节） ➔ 200 字从生活痛点顺理成章引出图书 ➔ 80 字比价促单（玩具快餐比价法或做人防身法）。

---

### 【请按以下结构格式输出】：

#### 第一部分：完整口播纯文本（逐行断句版，可直接喂给 Edge-TTS）
```text
（请在此输出逐行口播文案，每行一句，保持短句）
```

#### 第二部分：GPT 生图分镜清单（输出 6~8 张 9:16 竖屏精美生图 Prompt）
格式要求：
- **镜头 1（开篇悬念）**：
  - 画面描述（中文）：
  - GPT 英文 Prompt（包含 9:16, 8k, cinematic, documentary style, nostalgic warm lighting, photorealistic）：
- **镜头 2（首个景观/核心细节）**：
  ...
- **镜头 7（带货场景/图书翻阅陪伴画面）**：
  - 画面描述：老两口或祖孙二人在温暖灯光下坐在茶几前翻看精美大画册的温馨特写。
  - GPT 英文 Prompt：
````

---

## 三、 极速成片流水线两步实操命令

### 步骤一：拿到 Gemini 口播后，15 秒初始化剪映工程（与 GPT 生图并行）
```powershell
python scripts/fast_draft_pipeline.py init --dir "03_视频成片与工程/<新建工程名>"
```
* **立即粘贴** Gemini 生成的第一部分口播文案；
* 程序自动完成：Edge-TTS 央视纪录片配音、逐句毫秒级大字字幕、BGM 混音淡出、占位图就绪。剪映草稿 15 秒内瞬间生成完毕！

### 步骤二：GPT 生图完毕放入 `02_分镜视觉素材/`，3 秒热替换成片
```powershell
python scripts/fast_draft_pipeline.py apply-images --dir "03_视频成片与工程/<新建工程名>"
```
* 毫秒级扫描新图片，热替换剪映素材，关键帧与转场纹丝不动，草稿瞬间变最终高清成片，可直接导出发布！
