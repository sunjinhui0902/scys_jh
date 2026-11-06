# 语音 API 配置说明（仅用于声音测试与生成）

本项目**只用自有 API 做声音**，不做图片、不做视频。图像走 GPT 生图流水线，视频不涉及。

## 一、文件位置

| 文件 | 是否入库 | 作用 |
| --- | --- | --- |
| `config/voice_api/config.yaml` | ❌ 不入库（被 `.gitignore` 的 `**/config.yaml` 忽略） | 你填密钥的地方 + 音色与台词表 |
| `config/voice_api/config.example.yaml` | ✅ 入库 | 结构模板，给别人看用 |
| `scripts/voice_api_tts.py` | ✅ 入库 | 合成 + 拼接脚本 |
| `scripts/assemble_voice_test.py` | ✅ 入库 | 拼接底层（ffmpeg 混音与时间轴），被上面那个脚本调用 |

## 二、填密钥（两种方式，二选一）

**方式 A：填配置文件**（推荐，配置里还有音色表）

1. 打开 `config/voice_api/config.yaml`
2. 把 `api_key: ""` 换成你的 Key（开放平台控制台 > 账户管理 > API Keys）

**方式 B：用环境变量**（不改文件）

```powershell
$env:MINIMAX_API_KEY = "你的Key"
```

读取顺序：**环境变量优先于配置文件**。密钥全程不打印、不进仓库、不进日志。

## 三、已实测的参数（2026-11-06）

| 项 | 值 | 说明 |
| --- | --- | --- |
| 端点 | `https://api.minimaxi.com/v1/t2a_v2` | 中国区 key；国际区 key 要换成 `https://api.minimax.io`（实测混用会报 `invalid api key`） |
| 鉴权 | `Authorization: Bearer <key>` | |
| 模型 | `speech-2.8-hd` | 也支持 `2.8-turbo` / `2.6-hd` / `speech-02-hd`；`<#0.35#>` 停顿标记与 `(laughs)(sighs)(breath)` 语气词只有 2.8 系列支持 |
| 情绪 | `voice_setting.emotion` | neutral / happy / sad / angry / fearful / surprised / disgusted |
| 语速音调 | `voice_setting.speed` 0.5–2.0、`pitch` −12–12 | |
| 返回 | `data.audio` 为 hex | 脚本自动解码成 mp3 |
| 计费口径 | `extra_info.usage_characters` | 按字符计；六声线全量约 **81 字符** |

## 四、命令

```bash
# 全量：合成 6 条 + 3 个场景 + 15 秒母版
python scripts/voice_api_tts.py

# 只重做一句（改台词/音色只跑一条，不重复消耗额度）
python scripts/voice_api_tts.py --role 男童

# 临时试一句新音色，不进母版
python scripts/voice_api_tts.py --role 爸爸 --voice-id "Chinese (Mandarin)_Southern_Young_Man" --emotion angry --speed 1.12 --no-mix --out "_临时试音"

# 换配置文件 / 换输出目录
python scripts/voice_api_tts.py --config config/voice_api/config.yaml --out "六声线测试_XXX"
```

覆盖参数：`--text`（改台词）、`--voice-id`（换 MiniMax 音色）、`--edge-voice`（换 Edge 音色）、`--emotion`、`--speed`、`--pitch`、`--no-mix`（只合成不拼接）。

## 五、当前定稿音色表

| 角色 | 引擎 | 音色 | 情绪 | 语速 | 音调 |
| --- | --- | --- | --- | --- | --- |
| 男童（约6岁） | minimax | `Chinese (Mandarin)_Straightforward_Boy` | surprised | 1.08 | −5 |
| 爷爷（约65岁） | edge | `zh-CN-YunyangNeural` | — | −18% | −6Hz |
| 女童（约6岁） | minimax | `Chinese (Mandarin)_Warm_Girl` | happy | 1.00 | +1 |
| 奶奶（约60岁） | minimax | `Chinese (Mandarin)_Wise_Women` | happy | 0.95 | 0 |
| 妈妈（约35岁） | minimax | `female-chengshu` | angry | 1.12 | 0 |
| 爸爸（约40岁） | minimax | `male-qn-badao` | angry | 1.08 | −1 |

备选音色（已试听验证，详见 `config/voice_api/config.yaml` 末尾注释）：
爷爷换 `Chinese (Mandarin)_Male_Announcer`（neutral 0.90 / −3）可让**全部角色都走自有 API**；奶奶音调别低于 −2（会干哑发傻）；`lovely_girl` 太夹、`Humorous_Elder` 太像猪八戒，均已弃用。

## 六、常见问题

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `invalid api key` | 中国区 key 打到了 `api.minimax.io` | 把 `base_url` 改成 `https://api.minimaxi.com` |
| `token is required` / 401 | 密钥为空或读到了别的配置 | 确认 `api_key` 已填，或设置 `MINIMAX_API_KEY` 环境变量 |
| 角色听起来是女声反串 | 童声音色在音调 0 时偏软 | 男童把 `pitch` 压到 −5 |
| 老人像卡通/搞笑角色 | 老年男声音色库偏戏剧化 | 改用 `zh-CN-YunyangNeural`（Edge）或 `Male_Announcer` |
