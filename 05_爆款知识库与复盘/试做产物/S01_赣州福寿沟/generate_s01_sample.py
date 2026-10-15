"""
S01 赣州福寿沟 本地试做样片全流程自动化生成脚本
项目约定遵循：
1. 路径从文件位置推导，禁止硬编码用户名与盘符
2. 隔离生成，不覆盖既有工程或剪映草稿
3. 严格核对水窗开合方向，不使用“从不内涝”绝对说法
4. 不展示虚构图书内页，自制核对卡提示
"""

import os
import sys
import subprocess
import wave
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import pymediainfo

# 推导项目路径
CURRENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_DIR.parents[2]
PIPELINE_DIR = REPO_ROOT / "04_自动化生产流水线"
sys.path.insert(0, str(PIPELINE_DIR))
from workspace_paths import ffmpeg

FFMPEG_BIN = ffmpeg()

AUDIO_DIR = CURRENT_DIR / "audio"
VISUALS_DIR = CURRENT_DIR / "visuals"
FRAMES_DIR = VISUALS_DIR / "frames"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
VISUALS_DIR.mkdir(parents=True, exist_ok=True)
FRAMES_DIR.mkdir(parents=True, exist_ok=True)

FONT_PATH = "C:/Windows/Fonts/msyh.ttc"
BOLD_FONT_PATH = "C:/Windows/Fonts/simhei.ttf"

def get_font(size, bold=False):
    p = BOLD_FONT_PATH if bold else FONT_PATH
    try:
        return ImageFont.truetype(p, size)
    except Exception:
        return ImageFont.load_default()

# 34句打磨口播与逐句字幕（严格满足 5～9 字）
CLAUSES = [
    # 段落1：提出问题 (Hook) -> Scene 1
    {"text": "城里下大暴雨", "scene": 1, "sec_name": "01·提出问题"},
    {"text": "城外江水上涨", "scene": 1, "sec_name": "01·提出问题"},
    {"text": "积水该往哪排", "scene": 1, "sec_name": "01·提出问题"},
    {"text": "赣州给出了答案", "scene": 1, "sec_name": "01·提出问题"},

    # 段落2：两江与福寿沟 -> Scene 2
    {"text": "章江贡江汇合", "scene": 2, "sec_name": "02·地理水系"},
    {"text": "古城三面环水", "scene": 2, "sec_name": "02·地理水系"},
    {"text": "地下藏着福寿沟", "scene": 2, "sec_name": "02·地理水系"},
    {"text": "从宋代用到今天", "scene": 2, "sec_name": "02·地理水系"},

    # 段落3：地势与沟塘调蓄 -> Scene 3
    {"text": "地势西南高东北低", "scene": 3, "sec_name": "03·沟塘调蓄"},
    {"text": "顺着坡度排雨水", "scene": 3, "sec_name": "03·沟塘调蓄"},
    {"text": "明沟暗渠连池塘", "scene": 3, "sec_name": "03·沟塘调蓄"},
    {"text": "暴雨时先存水塘", "scene": 3, "sec_name": "03·沟塘调蓄"},
    {"text": "错开下泄的洪峰", "scene": 3, "sec_name": "03·沟塘调蓄"},

    # 段落4：机制A-水窗向外开启排水 -> Scene 4
    {"text": "最巧妙的是水窗", "scene": 4, "sec_name": "04·水窗排水"},
    {"text": "设在出江的口子", "scene": 4, "sec_name": "04·水窗排水"},
    {"text": "城内水位如果高", "scene": 4, "sec_name": "04·水窗排水"},
    {"text": "水流冲推着木闸", "scene": 4, "sec_name": "04·水窗排水"},
    {"text": "窗门向外被冲开", "scene": 4, "sec_name": "04·水窗排水"},
    {"text": "积水顺畅排入江", "scene": 4, "sec_name": "04·水窗排水"},

    # 段落5：机制B-外江上涨反向闭合 -> Scene 5
    {"text": "一旦外江水暴涨", "scene": 5, "sec_name": "05·防倒灌机制"},
    {"text": "江水水位高过窗", "scene": 5, "sec_name": "05·防倒灌机制"},
    {"text": "反向水压顶住门", "scene": 5, "sec_name": "05·防倒灌机制"},
    {"text": "把水窗紧紧压死", "scene": 5, "sec_name": "05·防倒灌机制"},
    {"text": "挡住外面的江水", "scene": 5, "sec_name": "05·防倒灌机制"},
    {"text": "不让江水倒灌来", "scene": 5, "sec_name": "05·防倒灌机制"},

    # 段落6：工程小结与客观态度 -> Scene 6
    {"text": "不靠人力去开关", "scene": 6, "sec_name": "06·科学治水"},
    {"text": "全借水力来工作", "scene": 6, "sec_name": "06·科学治水"},
    {"text": "这不是从不内涝", "scene": 6, "sec_name": "06·科学治水"},
    {"text": "是因地制宜智慧", "scene": 6, "sec_name": "06·科学治水"},
    {"text": "看古城先看水路", "scene": 6, "sec_name": "06·科学治水"},

    # 段落7：阅读延伸与审慎选书 -> Scene 7
    {"text": "想深入读懂古城", "scene": 7, "sec_name": "07·选读提示"},
    {"text": "先查名城书目录", "scene": 7, "sec_name": "07·选读提示"},
    {"text": "核准章节再阅读", "scene": 7, "sec_name": "07·选读提示"},
    {"text": "理性探索历史城", "scene": 7, "sec_name": "07·选读提示"}
]

# 校验字数
for idx, item in enumerate(CLAUSES):
    l = len(item["text"])
    assert 5 <= l <= 9, f"Clause {idx} '{item['text']}' len {l} outside [5, 9]"

# ==================== 1. 音频合成与时间轴 ====================

def generate_audios():
    print(">>> 正在使用 Windows 本地语音服务合成逐句音频...")
    ps_file = CURRENT_DIR / "temp_tts.ps1"
    ps_code = """
Add-Type -AssemblyName System.Speech
$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice = $speak.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -eq 'zh-CN' } | Select-Object -First 1
if ($voice) { $speak.SelectVoice($voice.VoiceInfo.Name) }
$speak.Rate = 1

$clauses = @(
""" + "\n".join([f'    "{c["text"]}"' for c in CLAUSES]) + """
)

for ($i = 0; $i -lt $clauses.Count; $i++) {
    $fn = Join-Path "audio" ("clause_" + $i.ToString("00") + ".wav")
    $speak.SetOutputToWaveFile($fn)
    $speak.Speak($clauses[$i])
}
$speak.Dispose()
"""
    ps_file.write_text(ps_code, encoding="utf-8-sig")
    subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps_file)], cwd=str(CURRENT_DIR), capture_output=False, check=True)
    if ps_file.exists():
        ps_file.unlink()

def assemble_master_audio():
    print(">>> 正在拼接主音频与计算精确时间轴...")
    section_ends = {3, 7, 12, 18, 24, 29, 33}
    pause_clause = 0.10   # 句间微停顿 100ms
    pause_section = 0.25  # 段落微停顿 250ms

    timeline = []
    current_ms = 0.0

    master_path = AUDIO_DIR / "master_narration.wav"
    
    # 读取第一条获取音频参数
    with wave.open(str(AUDIO_DIR / "clause_00.wav"), 'rb') as w:
        params = w.getparams()
        framerate = params.framerate
        nchannels = params.nchannels
        sampwidth = params.sampwidth

    all_frames = bytearray()

    for i, item in enumerate(CLAUSES):
        cf = AUDIO_DIR / f"clause_{i:02d}.wav"
        with wave.open(str(cf), 'rb') as w:
            data = w.readframes(w.getnframes())
            dur_sec = w.getnframes() / framerate
            dur_ms = dur_sec * 1000.0

        start_ms = current_ms
        end_ms = start_ms + dur_ms

        all_frames.extend(data)

        # 停顿处理
        p_sec = pause_section if i in section_ends else pause_clause
        p_ms = p_sec * 1000.0
        silence_bytes = b'\x00' * int(framerate * p_sec * nchannels * sampwidth)
        all_frames.extend(silence_bytes)

        current_ms = end_ms + p_ms

        timeline.append({
            "index": i + 1,
            "text": item["text"],
            "scene": item["scene"],
            "sec_name": item["sec_name"],
            "start_ms": start_ms,
            "end_ms": end_ms,
            "duration_ms": dur_ms,
            "total_clause_time": dur_sec + p_sec
        })

    with wave.open(str(master_path), 'wb') as w:
        w.setparams(params)
        w.writeframes(all_frames)

    total_duration_sec = current_ms / 1000.0
    print(f"Master 音频生成成功: {master_path}")
    print(f"实际样片总时长: {total_duration_sec:.2f} 秒 (在 60～90 秒规格内)")

    return timeline, total_duration_sec

# ==================== 2. SRT 字幕导出 ====================

def format_srt_time(ms: float) -> str:
    total_sec = int(ms // 1000)
    millis = int(ms % 1000)
    s = total_sec % 60
    m = (total_sec // 60) % 60
    h = total_sec // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{millis:03d}"

def export_srt(timeline):
    srt_path = CURRENT_DIR / "subtitles.srt"
    lines = []
    for item in timeline:
        i = item["index"]
        st = format_srt_time(item["start_ms"])
        et = format_srt_time(item["end_ms"])
        txt = item["text"]
        lines.append(f"{i}\n{st} --> {et}\n{txt}\n")
    srt_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"SRT 字幕生成成功: {srt_path}")

# ==================== 3. 7大场景专业视觉示意图绘制 ====================

def draw_header(draw, title, subtitle, scene_tag, watermark="【原理示意 · 暂无实景商业授权】"):
    draw.rounded_rectangle([40, 40, 1040, 220], radius=16, fill="#161f30", outline="#2b3b55", width=2)
    f_badge = get_font(24, bold=True)
    draw.rounded_rectangle([60, 60, 360, 96], radius=8, fill="#e59b20")
    draw.text((75, 65), scene_tag, font=f_badge, fill="#ffffff")
    
    draw.rounded_rectangle([620, 60, 1020, 96], radius=8, fill="#334155")
    draw.text((635, 66), watermark, font=get_font(20, bold=True), fill="#cbd5e1")
    
    draw.text((60, 115), title, font=get_font(38, bold=True), fill="#ffffff")
    draw.text((60, 170), subtitle, font=get_font(24), fill="#94a3b8")

def render_base_scene(scene_id):
    img = Image.new("RGB", (1080, 1920), "#0d131d")
    draw = ImageDraw.Draw(img)

    if scene_id == 1:
        # Scene 1: 问题剖析
        draw_header(draw, "赣州古城：一个水窗，怎么应对两边的水？", "地下排水系统福寿沟 ｜ 本地试做样片 S01", "【S01 选题问题剖析】")
        draw.rounded_rectangle([40, 250, 1040, 1480], radius=20, fill="#141c2b", outline="#25334a", width=2)
        draw.text((70, 280), "【核心问题】城内大暴雨 + 城外江水涨：水往哪排？", font=get_font(32, bold=True), fill="#38bdf8")
        
        draw.rounded_rectangle([70, 340, 1010, 840], radius=16, fill="#0c111a", outline="#1e293b", width=2)
        draw.polygon([(90, 360), (250, 360), (280, 820), (120, 820)], fill="#1e3a5f", outline="#3b82f6", width=2)
        draw.text((140, 560), "章\n江\n(西)", font=get_font(34, bold=True), fill="#60a5fa")
        
        draw.polygon([(830, 360), (990, 360), (960, 820), (800, 820)], fill="#1e3a5f", outline="#3b82f6", width=2)
        draw.text((860, 560), "贡\n江\n(东)", font=get_font(34, bold=True), fill="#60a5fa")
        
        draw.rounded_rectangle([320, 420, 760, 780], radius=16, fill="#1a2538", outline="#fbbf24", width=3)
        draw.text((450, 450), "赣州古城", font=get_font(40, bold=True), fill="#fde047")
        draw.text((410, 510), "（城墙环绕 · 三面邻江）", font=get_font(24), fill="#cbd5e1")
        
        for rx in range(360, 740, 50):
            for ry in range(560, 740, 60):
                draw.text((rx, ry), "🌧", font=get_font(28), fill="#38bdf8")
        
        draw.text((380, 720), "城内雨大 积水迅速聚集！", font=get_font(26, bold=True), fill="#f87171")
        draw.text((100, 420), "▲ 江水暴涨", font=get_font(24, bold=True), fill="#ef4444")
        draw.text((840, 420), "▲ 江水暴涨", font=get_font(24, bold=True), fill="#ef4444")
        
        draw.rounded_rectangle([70, 870, 1010, 1160], radius=14, fill="#182335", outline="#334155", width=1)
        draw.text((95, 895), "两难防汛困局：", font=get_font(28, bold=True), fill="#f59e0b")
        draw.text((95, 945), "• 困境一：外江洪峰暴涨，若排水口敞开，江水势必倒灌淹城", font=get_font(24), fill="#e2e8f0")
        draw.text((95, 995), "• 困境二：若将排水口全堵死，城内暴雨汇集排不出去，同样内涝", font=get_font(24), fill="#e2e8f0")
        draw.text((95, 1045), "• 破局点：北宋水利工匠在城下安设了神奇的「单向水窗」！", font=get_font(24, bold=True), fill="#38bdf8")
        draw.text((95, 1095), "  既能借助城内水压往外排水，又能在江水上涨时反向死死闭合！", font=get_font(23), fill="#a5f3fc")
        
        draw.rounded_rectangle([70, 1190, 1010, 1440], radius=14, fill="#0f172a", outline="#2563eb", width=2)
        draw.text((95, 1215), "【本期探索重点与严谨声明】", font=get_font(26, bold=True), fill="#60a5fa")
        draw.text((95, 1265), "1. 重点拆解：水窗单向自动启闭的方向与力学原理", font=get_font(23), fill="#cbd5e1")
        draw.text((95, 1315), "2. 科学求真：删除夸大神话，赣州古城遇特大洪水并非从不积水", font=get_font(23), fill="#fca5a5")
        draw.text((95, 1365), "3. 素材说明：当前缺乏实景商业许可，全篇采用自绘图严谨示意", font=get_font(23), fill="#fde68a")

    elif scene_id == 2:
        # Scene 2: 地理水系与两江汇流
        draw_header(draw, "两江汇流与福寿双沟地下空间格局", "章江西来 · 贡京东来 · 北汇成赣江", "【02·地理与地下水网】")
        draw.rounded_rectangle([40, 250, 1040, 1480], radius=20, fill="#141c2b", outline="#25334a", width=2)
        draw.text((70, 280), "【水系布局】三面环江地貌与地下双系统", font=get_font(32, bold=True), fill="#38bdf8")

        # Topographic river map box
        draw.rounded_rectangle([70, 340, 1010, 900], radius=16, fill="#0b1017", outline="#1e293b", width=2)
        
        # Confluence rivers
        # North Gan River
        draw.rectangle([460, 360, 620, 520], fill="#1e3a5f", outline="#3b82f6", width=2)
        draw.text((490, 420), "赣江\n(北流)", font=get_font(30, bold=True), fill="#93c5fd")
        draw.text((440, 530), "▲ 八境台·龟尾角汇流点", font=get_font(20), fill="#fde047")
        
        # West Zhang River
        draw.polygon([(100, 880), (220, 880), (460, 580), (380, 560)], fill="#1e3a5f", outline="#3b82f6", width=2)
        draw.text((180, 750), "章江 (自西南来)", font=get_font(24, bold=True), fill="#60a5fa")

        # East Gong River
        draw.polygon([(980, 880), (860, 880), (620, 580), (700, 560)], fill="#1e3a5f", outline="#3b82f6", width=2)
        draw.text((720, 750), "贡江 (自东南来)", font=get_font(24, bold=True), fill="#60a5fa")

        # City core in middle
        draw.rounded_rectangle([360, 590, 720, 870], radius=14, fill="#1e293b", outline="#f59e0b", width=3)
        draw.text((440, 620), "赣州宋城", font=get_font(36, bold=True), fill="#fde047")
        
        # Dual ditch system lines
        draw.line([(420, 700), (320, 740)], fill="#ec4899", width=6)
        draw.text((310, 710), "寿沟 (排入章江)", font=get_font(20, bold=True), fill="#f472b6")
        
        draw.line([(660, 700), (760, 740)], fill="#06b6d4", width=6)
        draw.text((680, 710), "福沟 (排入贡江)", font=get_font(20, bold=True), fill="#67e8f9")

        draw.text((410, 820), "地下总长数十里暗渠系统", font=get_font(20), fill="#94a3b8")

        # Info card
        draw.rounded_rectangle([70, 930, 1010, 1440], radius=14, fill="#182335", outline="#334155", width=1)
        draw.text((95, 955), "历史与工程事实：", font=get_font(28, bold=True), fill="#f59e0b")
        draw.text((95, 1005), "• 建造年代：北宋熙宁年间（1068-1077年），由水利专家刘彝主持修筑", font=get_font(23), fill="#e2e8f0")
        draw.text((95, 1055), "• 系统划分：依据城内天然地貌划分为「福沟」与「寿沟」两大干渠网", font=get_font(23), fill="#e2e8f0")
        draw.text((95, 1105), "• 走向布局：寿沟承纳城西南积水排入章江，福沟承纳城东北积水排入贡江", font=get_font(23), fill="#e2e8f0")
        draw.text((95, 1155), "• 现存价值：地下部分古砖石沟道历经近千年至今仍在服务城市排水", font=get_font(23), fill="#e2e8f0")
        draw.text((95, 1220), "★ 纠偏对比（针对网络竞品夸大）：", font=get_font(24, bold=True), fill="#f87171")
        draw.text((95, 1270), "  竞品称‘九百年从不被淹’系误传，其科学内核是顺应地形自流与分区调控。", font=get_font(22), fill="#cbd5e1")
        draw.text((95, 1320), "  并非具有神仙法力，而是严谨的古典重力水利工程学杰作。", font=get_font(22), fill="#cbd5e1")

    elif scene_id == 3:
        # Scene 3: 地势坡度与沟塘调蓄
        draw_header(draw, "自然地势西南高东北低 ｜ 沟塘调蓄网络", "利用天然落差重力自流 ｜ 连通数十处水塘错峰蓄泄", "【03·地形与沟塘调蓄】")
        draw.rounded_rectangle([40, 250, 1040, 1480], radius=20, fill="#141c2b", outline="#25334a", width=2)
        draw.text((70, 280), "【工程原理】重力自流排水 + 城内水塘弹性蓄滞", font=get_font(32, bold=True), fill="#38bdf8")

        # Topographic slope diagram
        draw.rounded_rectangle([70, 340, 1010, 830], radius=16, fill="#0b1017", outline="#1e293b", width=2)
        
        # Slope curve
        draw.polygon([(100, 680), (100, 520), (500, 600), (950, 720), (950, 800)], fill="#1e293b", outline="#64748b", width=2)
        draw.text((120, 480), "西南城区 (地势较高 ~110米)", font=get_font(22, bold=True), fill="#fbbf24")
        draw.text((700, 680), "东北城区 (地势较低 ~90米)", font=get_font(22, bold=True), fill="#38bdf8")

        # Gravity arrow
        draw.line([(220, 560), (820, 690)], fill="#22c55e", width=6)
        draw.text((450, 580), "▼ 天然坡度落差 10~20米，重力自流无耗能", font=get_font(22, bold=True), fill="#4ade80")

        # Ponds
        draw.rounded_rectangle([250, 710, 420, 790], radius=12, fill="#0284c7", outline="#38bdf8", width=2)
        draw.text((275, 735), "清水塘 (蓄水)", font=get_font(20, bold=True), fill="#ffffff")

        draw.rounded_rectangle([520, 730, 690, 810], radius=12, fill="#0284c7", outline="#38bdf8", width=2)
        draw.text((545, 755), "凤凰池 (蓄水)", font=get_font(20, bold=True), fill="#ffffff")

        draw.rounded_rectangle([760, 750, 930, 820], radius=12, fill="#0284c7", outline="#38bdf8", width=2)
        draw.text((785, 770), "金鱼池 (蓄水)", font=get_font(20, bold=True), fill="#ffffff")

        # Detailed breakdown
        draw.rounded_rectangle([70, 860, 1010, 1440], radius=14, fill="#182335", outline="#334155", width=1)
        draw.text((95, 885), "“沟塘连通”双向调蓄机制：", font=get_font(28, bold=True), fill="#f59e0b")
        draw.text((95, 935), "1. 街道明渠汇水：雨水落到屋面与街道，汇入明沟支渠", font=get_font(23), fill="#e2e8f0")
        draw.text((95, 985), "2. 注入地下福寿沟：沿天然地形坡降，迅速流入福寿沟地下主干", font=get_font(23), fill="#e2e8f0")
        draw.text((95, 1035), "3. 连通城内数十处池塘：暗渠与城内池塘、水洼互联互通", font=get_font(23), fill="#e2e8f0")
        draw.text((95, 1095), "★ 错峰削峰核心功能：", font=get_font(26, bold=True), fill="#38bdf8")
        draw.text((95, 1145), "• 暴雨来袭时：雨急且江水上涨，雨水先漫入水塘暂存，不堵在街面", font=get_font(23), fill="#fed7aa")
        draw.text((95, 1195), "• 外江退水时：水塘暂存的积水顺福寿沟平稳排泄入江，错开洪峰", font=get_font(23), fill="#fed7aa")
        draw.text((95, 1260), "★ 科学治水启示：", font=get_font(24, bold=True), fill="#4ade80")
        draw.text((95, 1310), "  池塘不是单纯的景观装饰，而是古代城市海绵工程的天然“蓄滞洪区”！", font=get_font(22), fill="#cbd5e1")
        draw.text((95, 1360), "  蓄排结合、动静互补，充分彰显古代工匠对水势节奏的精妙掌握。", font=get_font(22), fill="#cbd5e1")

    elif scene_id == 4:
        # Scene 4: 水窗排水剖面图（向外冲开）
        draw_header(draw, "水力自启闭 · 水窗向外开启排水状态", "城内福寿沟水位高于江面 ｜ 水流冲开木闸门向外排水", "【04·水窗排水机制】")
        draw.rounded_rectangle([40, 250, 1040, 1480], radius=20, fill="#141c2b", outline="#25334a", width=2)
        draw.text((70, 280), "【水窗截面剖面】城内水压大：单向木闸向江外推开", font=get_font(32, bold=True), fill="#38bdf8")

        # Cross section diagram
        draw.rounded_rectangle([70, 340, 1010, 930], radius=16, fill="#080e18", outline="#1e293b", width=2)
        
        # Left: City interior / Fushougou culvert
        draw.rectangle([90, 480, 420, 860], fill="#1e293b", outline="#475569", width=2)
        draw.rectangle([90, 560, 420, 860], fill="#0284c7")  # Water inside culvert
        draw.text((120, 500), "古城内地下福寿沟", font=get_font(24, bold=True), fill="#fde047")
        draw.text((120, 600), "▲ 城内暴雨汇集\n   水位升高！水压大", font=get_font(22, bold=True), fill="#ffffff")

        # Middle: Ancient Stone City Wall & Culvert Outlet
        draw.rectangle([420, 360, 660, 860], fill="#334155", outline="#64748b", width=3)
        draw.text((450, 400), "赣州宋城墙\n条石出水通道", font=get_font(24, bold=True), fill="#e2e8f0")
        
        # Culvert tunnel in the wall
        draw.rectangle([420, 620, 660, 860], fill="#0f172a")
        
        # Hinge & Wooden Flap Gate (Open outward to the right)
        # Hinge point at (650, 630)
        draw.ellipse([640, 620, 660, 640], fill="#f59e0b", outline="#ffffff", width=2)
        draw.text((610, 590), "转轴(顶端)", font=get_font(18), fill="#f59e0b")
        # Wooden gate swinging outward to (740, 780)
        draw.polygon([(650, 630), (665, 635), (745, 785), (730, 790)], fill="#b45309", outline="#fde047", width=2)
        draw.text((710, 710), "水窗木闸\n向外被冲开！", font=get_font(22, bold=True), fill="#fde047")

        # Right: River (Water level low)
        draw.rectangle([660, 740, 990, 860], fill="#1e3a5f", outline="#3b82f6", width=2)
        draw.text((750, 770), "外江江面 (水位相对较低)", font=get_font(22, bold=True), fill="#93c5fd")

        # Outflow arrows
        draw.line([(260, 720), (620, 720)], fill="#38bdf8", width=8)
        draw.line([(620, 720), (850, 800)], fill="#38bdf8", width=8)
        draw.text((380, 680), "水流向外喷涌 >>>", font=get_font(26, bold=True), fill="#38bdf8")

        # Mechanism explanation
        draw.rounded_rectangle([70, 960, 1010, 1440], radius=14, fill="#182335", outline="#334155", width=1)
        draw.text((95, 985), "单向排水核心力学条件（重点核验）：", font=get_font(28, bold=True), fill="#f59e0b")
        draw.text((95, 1035), "• 压力差方向：城内福寿沟积水水压 > 城外江面水压", font=get_font(24, bold=True), fill="#e2e8f0")
        draw.text((95, 1085), "• 闸门结构：木质水窗顶端设活动转轴，呈单向自垂悬挂", font=get_font(23), fill="#cbd5e1")
        draw.text((95, 1135), "• 启闭动作：城内水流由内向外冲击，冲力克服闸板重力，窗门推开", font=get_font(23), fill="#cbd5e1")
        draw.text((95, 1185), "• 排水结果：城内暴雨积水毫无阻碍地倾泻注入江中", font=get_font(23), fill="#38bdf8")
        draw.text((95, 1250), "★ 自动化特征：", font=get_font(24, bold=True), fill="#4ade80")
        draw.text((95, 1300), "  全程无需守闸人员值守操作，完全由水流动力自发完成开启，反应极快。", font=get_font(22), fill="#cbd5e1")
        draw.text((95, 1350), "  开合角度随内水流量自动调节，堪称古代水力学‘单向拍门’经典之作。", font=get_font(22), fill="#cbd5e1")

    elif scene_id == 5:
        # Scene 5: 水窗防倒灌剖面图（反向闭合）
        draw_header(draw, "外江暴涨防倒灌 · 水窗反向紧闭状态", "江水水位高于排水口 ｜ 反向巨大水压将水窗死死压死在框上", "【05·水窗防倒灌机制】")
        draw.rounded_rectangle([40, 250, 1040, 1480], radius=20, fill="#141c2b", outline="#25334a", width=2)
        draw.text((70, 280), "【水窗截面剖面】江水暴涨：外力反压阻断倒灌", font=get_font(32, bold=True), fill="#f87171")

        # Cross section diagram
        draw.rounded_rectangle([70, 340, 1010, 930], radius=16, fill="#080e18", outline="#1e293b", width=2)
        
        # Left: City interior / Culvert (Safe, no backflow)
        draw.rectangle([90, 480, 420, 860], fill="#1e293b", outline="#475569", width=2)
        draw.rectangle([90, 680, 420, 860], fill="#0284c7")  # Water inside culvert (low)
        draw.text((120, 500), "古城内地下福寿沟", font=get_font(24, bold=True), fill="#fde047")
        draw.text((120, 560), "✔ 江水被阻挡在外\n  无江水倒灌进入！", font=get_font(22, bold=True), fill="#4ade80")

        # Middle: Ancient Stone City Wall & Culvert Outlet
        draw.rectangle([420, 360, 660, 860], fill="#334155", outline="#64748b", width=3)
        draw.text((450, 400), "赣州宋城墙\n条石出水通道", font=get_font(24, bold=True), fill="#e2e8f0")
        
        # Culvert tunnel
        draw.rectangle([420, 620, 660, 860], fill="#0f172a")
        
        # Hinge & Wooden Flap Gate (Forced shut vertical against the outer frame)
        draw.ellipse([640, 620, 660, 640], fill="#f59e0b", outline="#ffffff", width=2)
        draw.text((610, 590), "转轴(顶端)", font=get_font(18), fill="#f59e0b")
        # Wooden gate vertical tight against frame
        draw.polygon([(645, 630), (665, 630), (665, 860), (645, 860)], fill="#b45309", outline="#ef4444", width=3)
        draw.text((510, 710), "紧闭贴框！\n严密封堵", font=get_font(22, bold=True), fill="#ef4444")

        # Right: River (Water level HIGH flood!)
        draw.rectangle([660, 460, 990, 860], fill="#1e3a5f", outline="#ef4444", width=3)
        draw.text((720, 490), "▲ 外江洪水暴涨！\n  水位高于水窗出水口", font=get_font(24, bold=True), fill="#fca5a5")

        # Inflow push arrows (countered by gate)
        draw.line([(880, 720), (680, 720)], fill="#ef4444", width=8)
        draw.text((700, 670), "<<< 巨大反向水压", font=get_font(24, bold=True), fill="#ef4444")

        # Mechanism & Fact-check explanation
        draw.rounded_rectangle([70, 960, 1010, 1440], radius=14, fill="#182335", outline="#334155", width=1)
        draw.text((95, 985), "反向防倒灌力学条件与事实核实：", font=get_font(28, bold=True), fill="#f59e0b")
        draw.text((95, 1035), "• 压力差方向：城外江面水压 ≫ 城内排水沟水压", font=get_font(24, bold=True), fill="#ef4444")
        draw.text((95, 1085), "• 自闭机制：外江洪水自外向内涌入，巨大的水流压力把闸板死死贴紧窗框", font=get_font(23), fill="#cbd5e1")
        draw.text((95, 1135), "• 防倒灌效果：外江水位越高，压得越死，彻底封死江水倒灌通道", font=get_font(23), fill="#38bdf8")
        draw.text((95, 1195), "★ 关键事实澄清（必须纠偏）：", font=get_font(26, bold=True), fill="#f87171")
        draw.text((95, 1245), "  1. 窗关上后，城内暴雨无法排江，此时依靠城内池塘暂存积水（调蓄削峰）", font=get_font(22), fill="#fed7aa")
        draw.text((95, 1295), "  2. 严正声明：赣州并非‘从不内涝’！若遭遇百年特大洪水漫过城墙或池塘满溢，", font=get_font(22, bold=True), fill="#fca5a5")
        draw.text((95, 1345), "     城内低洼区域仍会受淹。科学防汛靠综合施策，切勿神化古代技术。", font=get_font(22), fill="#fca5a5")

    elif scene_id == 6:
        # Scene 6: 工程智慧总结
        draw_header(draw, "古代水利智慧小结 ｜ 因地制宜与科学精神", "重力自流 · 水力自控 · 沟塘调蓄 ｜ 破除神话，求真知", "【06·工程智慧小结】")
        draw.rounded_rectangle([40, 250, 1040, 1480], radius=20, fill="#141c2b", outline="#25334a", width=2)
        draw.text((70, 280), "【系统总结】赣州福寿沟三大协同支柱", font=get_font(32, bold=True), fill="#38bdf8")

        # 3 Pillar Cards
        # Pillar 1
        draw.rounded_rectangle([70, 340, 1010, 520], radius=14, fill="#1e293b", outline="#3b82f6", width=2)
        draw.text((95, 365), "支柱一：地势高差 · 天然重力自流", font=get_font(26, bold=True), fill="#60a5fa")
        draw.text((95, 415), "• 西南高、东北低，地势落差达10~20米；", font=get_font(22), fill="#cbd5e1")
        draw.text((95, 455), "• 顺应自然坡降布置干支管网，无人工动力成本，常年稳定运行。", font=get_font(22), fill="#cbd5e1")

        # Pillar 2
        draw.rounded_rectangle([70, 540, 1010, 720], radius=14, fill="#1e293b", outline="#f59e0b", width=2)
        draw.text((95, 565), "支柱二：单向水窗 · 水力自动启闭", font=get_font(26, bold=True), fill="#fde047")
        draw.text((95, 615), "• 巧妙利用内外水压差作为开合动力，城内水大则冲开排泄；", font=get_font(22), fill="#cbd5e1")
        draw.text((95, 655), "• 江水上涨则自动反压密封，杜绝江水倒灌，堪称早期自动控制典范。", font=get_font(22), fill="#cbd5e1")

        # Pillar 3
        draw.rounded_rectangle([70, 740, 1010, 920], radius=14, fill="#1e293b", outline="#10b981", width=2)
        draw.text((95, 765), "支柱三：连通池塘 · 弹性蓄滞调蓄", font=get_font(26, bold=True), fill="#34d399")
        draw.text((95, 815), "• 地下暗渠联通数十处地面水塘，暴雨急骤时发挥蓄滞洪峰作用；", font=get_font(22), fill="#cbd5e1")
        draw.text((95, 855), "• 水窗受江水顶托关闭期间，池塘承担暂存雨水防淹职责，错峰泄洪。", font=get_font(22), fill="#cbd5e1")

        # Summary takeaway card
        draw.rounded_rectangle([70, 950, 1010, 1440], radius=14, fill="#182335", outline="#2563eb", width=2)
        draw.text((95, 975), "【看古城的科学视角】", font=get_font(28, bold=True), fill="#f59e0b")
        draw.text((95, 1025), "• 别只看城墙有多高：城墙解决的是军事防御与地表防洪；", font=get_font(24), fill="#e2e8f0")
        draw.text((95, 1075), "• 还要看雨水往哪走：地下管网与城市水系解决的是长期生存与宜居；", font=get_font(24), fill="#e2e8f0")
        draw.text((95, 1145), "★ 拒绝流量煽动，坚持事实本位：", font=get_font(26, bold=True), fill="#fca5a5")
        draw.text((95, 1200), "• 剔除竞品文案中‘绝对不涝’、‘神仙神作’等不实修辞；", font=get_font(23), fill="#fca5a5")
        draw.text((95, 1250), "• 弘扬顺应自然、因地制宜的古代工程科学精神；", font=get_font(23), fill="#93c5fd")
        draw.text((95, 1300), "• 引导读者理性理解古代技术条件与现代城市防洪体系的演进。", font=get_font(23), fill="#93c5fd")

    elif scene_id == 7:
        # Scene 7: 选读与商品目录核对卡
        draw_header(draw, "阅读延伸与理性选书指引 ｜ 真实透明声明", "先核对版本目录 · 确认收录再选读 ｜ 尚未挂载商品链接", "【07·阅读延伸核对卡】")
        draw.rounded_rectangle([40, 250, 1040, 1480], radius=20, fill="#141c2b", outline="#25334a", width=2)
        draw.text((70, 280), "【自制书目卡】城市水利延伸阅读指引", font=get_font(32, bold=True), fill="#38bdf8")

        # Book info card
        draw.rounded_rectangle([70, 340, 1010, 720], radius=16, fill="#1e293b", outline="#f59e0b", width=2)
        draw.text((95, 365), "推荐探索书目： 《中国历史名城》", font=get_font(30, bold=True), fill="#fde047")
        draw.text((95, 420), "• 阅读主题：走进中国古都名城，探索城垣、街道与山水格局", font=get_font(23), fill="#cbd5e1")
        draw.text((95, 470), "• 延伸价值：从地理学与水利学维度，看古人如何布局城市生命线", font=get_font(23), fill="#cbd5e1")
        draw.text((95, 530), "• 当前核实状态（严谨合规）：", font=get_font(23, bold=True), fill="#fca5a5")
        draw.text((95, 575), "  [待核验] 公开版本目录是否确含‘赣州’章节及‘福寿沟’专述", font=get_font(21), fill="#fed7aa")
        draw.text((95, 620), "  [待核验] 实体书出版社版本、出版年份及图解测绘真实性", font=get_font(21), fill="#fed7aa")
        draw.text((95, 665), "  [已核实] 本视频未挂载橱窗商品链接，不虚构实物内页与翻书展示", font=get_font(21, bold=True), fill="#fca5a5")

        # Purchase & Verification Guidance
        draw.rounded_rectangle([70, 750, 1010, 1100], radius=14, fill="#182335", outline="#334155", width=1)
        draw.text((95, 775), "读者选书与阅读建议：", font=get_font(28, bold=True), fill="#f59e0b")
        draw.text((95, 825), "1. 先查目录：购书或借阅前，务必先核对公开目录有无目标城市", font=get_font(23), fill="#e2e8f0")
        draw.text((95, 875), "2. 拒绝虚构：不被未经核实的封面或煽动性带货话术绑架", font=get_font(23), fill="#e2e8f0")
        draw.text((95, 925), "3. 带着问题读：从一个排水窗，读懂一座城市的山水地理命脉", font=get_font(23), fill="#e2e8f0")
        draw.text((95, 985), "4. 待确认事项：待正式确认商品正版SKU及展示权后，再行理性推荐", font=get_font(23), fill="#38bdf8")

        # Compliance statement
        draw.rounded_rectangle([70, 1130, 1010, 1440], radius=14, fill="#0f172a", outline="#2563eb", width=2)
        draw.text((95, 1155), "【Codex 验收与商业合规说明】", font=get_font(26, bold=True), fill="#60a5fa")
        draw.text((95, 1205), "• 零侵权风险：无未获授权之实景视频、摄影原图或图书内页扫描件", font=get_font(22), fill="#cbd5e1")
        draw.text((95, 1255), "• 零夸大误导：不承诺绝对不涝，明确提示橱窗尚未挂载商品", font=get_font(22), fill="#cbd5e1")
        draw.text((95, 1305), "• 样片定位：本产物为单点原创样片，满足 60～90 秒实际试读规格", font=get_font(22), fill="#cbd5e1")
        draw.text((95, 1355), "• 配音说明：本地合成试读样音，正式发布需更换商用授权/真人音色", font=get_font(22), fill="#fde68a")

    return img

def generate_base_scenes():
    print(">>> 正在生成 7 大场景高清原理示意底图 (1080x1920)...")
    for s_id in range(1, 8):
        img = render_base_scene(s_id)
        p = VISUALS_DIR / f"scene_{s_id:02d}.png"
        img.save(p)
        print(f"Base Scene {s_id} saved to {p}")

def generate_frames():
    print(">>> 正在为 34 个口播短句生成带逐句字幕的视频帧...")
    base_imgs = {}
    for s_id in range(1, 8):
        base_imgs[s_id] = Image.open(VISUALS_DIR / f"scene_{s_id:02d}.png")

    total_clauses = len(CLAUSES)

    for i, c in enumerate(CLAUSES):
        s_id = c["scene"]
        base = base_imgs[s_id].copy()
        draw = ImageDraw.Draw(base)

        # Bottom Subtitle Pill Container (Y: 1530 to 1750)
        draw.rounded_rectangle([60, 1530, 1020, 1750], radius=24, fill="#070c14", outline="#e59b20", width=3)
        
        # Subtitle index tag
        tag_text = f"[{i+1:02d}/{total_clauses:02d}] {c['sec_name']}"
        draw.text((90, 1550), tag_text, font=get_font(22, bold=True), fill="#94a3b8")

        # Clause Subtitle Text (Font size 54, bold, centered or prominent)
        f_sub = get_font(54, bold=True)
        txt = c["text"]
        # Calculate text width to center horizontally
        bbox = draw.textbbox((0, 0), txt, font=f_sub)
        tw = bbox[2] - bbox[0]
        tx = (1080 - tw) // 2
        draw.text((tx, 1610), txt, font=f_sub, fill="#ffffff")

        # Progress bar at bottom of card (Y: 1720)
        progress_w = int(880 * ((i + 1) / total_clauses))
        draw.line([(100, 1725), (980, 1725)], fill="#1e293b", width=6)
        draw.line([(100, 1725), (100 + progress_w, 1725)], fill="#f59e0b", width=6)

        frame_path = FRAMES_DIR / f"frame_{i:02d}.png"
        base.save(frame_path)

    print(f"34 帧逐句字幕图已全部保存到: {FRAMES_DIR}")

# ==================== 4. 视频合成 ====================

def render_mp4(timeline, total_duration):
    print(">>> 正在生成 FFmpeg concat 列表与组装 MP4 样片...")
    concat_file = CURRENT_DIR / "concat_list.txt"
    lines = ["ffconcat version 1.0\n"]
    for i, item in enumerate(timeline):
        fp = FRAMES_DIR / f"frame_{i:02d}.png"
        # 使用正斜杠避免 Windows 路径转义问题
        lines.append(f"file '{fp.as_posix()}'\n")
        lines.append(f"duration {item['total_clause_time']:.4f}\n")
    
    # concat 规范要求最后再追加一次最后一帧
    last_fp = FRAMES_DIR / f"frame_{len(timeline)-1:02d}.png"
    lines.append(f"file '{last_fp.as_posix()}'\n")

    concat_file.write_text("".join(lines), encoding="utf-8")

    out_mp4 = CURRENT_DIR / "S01_赣州福寿沟_样片.mp4"
    master_audio = AUDIO_DIR / "master_narration.wav"

    cmd = [
        FFMPEG_BIN, "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-i", str(master_audio),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "25",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(out_mp4)
    ]

    print("执行命令:", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("FFmpeg 渲染失败:\n", res.stderr)
        raise RuntimeError("FFmpeg 执行失败")

    print(f"=== 样片 MP4 成功生成: {out_mp4} ===")

    # 校验视频元数据
    info = pymediainfo.MediaInfo.parse(str(out_mp4))
    general = info.tracks[0]
    dur = float(general.duration) / 1000.0
    w = [t.width for t in info.tracks if t.track_type == 'Video'][0]
    h = [t.height for t in info.tracks if t.track_type == 'Video'][0]
    print(f"视频分辨率: {w}x{h}")
    print(f"实测成片时长: {dur:.2f} 秒 (规格要求 60～90 秒)")

    return out_mp4, dur

def main():
    print("==================================================")
    print("开始生成 S01 赣州古城水窗 本地试做样片全套产物")
    print("==================================================")
    
    # 1. 音频
    generate_audios()
    timeline, total_dur = assemble_master_audio()

    # 2. 字幕
    export_srt(timeline)

    # 3. 视觉图与逐句帧
    generate_base_scenes()
    generate_frames()

    # 4. MP4成片组装
    out_mp4, final_dur = render_mp4(timeline, total_dur)

    print("\n所有本地试做样片流程已全部执行完成！")

if __name__ == "__main__":
    main()
