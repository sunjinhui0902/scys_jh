#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成配音包试听索引（Markdown）
=============================================================
把「配置文件 + 已生成音频」整理成一张可勾选的对照表，方便逐条决定
哪些保留、哪些要换音色或改语气。

用法：
    python scripts/voice_pack_index.py --config config/voice_api/config.yaml
    python scripts/voice_pack_index.py --config ... --out-dir 六角色固定配音库_V1_20261107
"""

import argparse
import json
import html
import shutil
import hashlib
from urllib.parse import quote
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_ROOT = ROOT / "01_配音与音色库"


def render_delivery_index(folder: Path) -> None:
    """为一次已完成交付生成可直接播放的本地试听页，不上传音频。"""
    report = json.loads((folder / "试听报告.json").read_text(encoding="utf-8"))
    items = report["lines"]
    esc = html.escape
    dry = folder / "干声MP3"
    dry.mkdir(exist_ok=True)
    for item in items:
        original = ROOT / item["source_file"]
        target = dry / item["file"]
        if not target.exists():
            shutil.copyfile(original, target)
        if hashlib.sha256(target.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"干声副本与报告不一致：{item['file']}")

    def player(file: Path) -> str:
        url = quote(file.relative_to(folder).as_posix(), safe="/")
        return f'<audio controls preload="none" src="{esc(url, quote=True)}"></audio>'

    def source(item: dict) -> Path:
        return dry / item["file"]

    cards = []
    labels = {"boy": "男宝", "girl": "女宝", "dad": "爸爸", "mom": "妈妈", "grandpa": "爷爷", "grandma": "奶奶"}
    for role in ["boy", "girl", "dad", "mom", "grandpa", "grandma"]:
        item = next(x for x in items if x["role"] == role and x["file"].startswith("00_"))
        cards.append(f'<article><h3>{labels[role]}</h3>{player(source(item))}'
                     f'<p class="voice">{esc(str(item.get("voice_id")))}</p>'
                     f'<label>试听选择 <select data-review="{role}"><option value="">待确认</option>'
                     '<option>保留</option><option>换音色</option><option>保留音色，调整语气</option></select></label></article>')
    edge = next(x for x in items if x["role"] == "grandpa_edge" and x["file"].startswith("00B_"))
    comparison = f'<article><h3>爷爷另一候选：Edge版</h3>{player(source(edge))}<p>与上方爷爷读同一句话，先选更自然的一位。</p></article>'
    scenes = []
    for group in report["scenes"]:
        file = folder / group["file"]
        scenes.append(f'<article><h3>{esc(file.stem)}</h3>{player(file)}<p>{group["duration_ms"]/1000:.2f} 秒</p></article>')
    bundles = []
    for group in report["collections"]:
        bundles.append(f'<article><h3>{esc(Path(group["file"]).stem)}</h3>{player(folder/group["file"])}'
                       f'<p>{group["duration_ms"]/60000:.1f} 分钟 · 保留完整台词</p></article>')
    rows = []
    for item in items:
        rows.append(f'<tr><td>{esc(labels.get(item["role"], "爷爷Edge备选"))}</td>'
                    f'<td>{esc(item["text"])}</td><td>{player(source(item))}</td>'
                    f'<td>{item["duration_ms"]/1000:.2f}秒</td></tr>')
    document = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>家庭六角色配音试听</title>
<style>body{margin:0;background:#f4f2ed;color:#282923;font:16px/1.7 system-ui,"Microsoft YaHei",sans-serif}main{max-width:1120px;margin:auto;padding:40px 24px}h1{font-size:34px;line-height:1.3}h2{margin-top:38px}h3{margin:0 0 12px;font-size:18px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}article{background:white;padding:20px;border:1px solid #deded5;border-radius:14px}audio{width:100%;max-width:360px}.voice{font-size:12px;color:#666;overflow-wrap:anywhere}select,button{font:inherit;padding:7px 12px;border:1px solid #aaa;border-radius:7px;background:white}button{cursor:pointer}.note{padding:16px 20px;border-radius:12px;background:#e7ecdf}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:12px;border-bottom:1px solid #ddd;vertical-align:top}td:nth-child(2){min-width:220px}td:nth-child(3){min-width:230px}.scroll{overflow:auto}p{margin:8px 0}small{color:#666}</style>
<main><p>声音库 V1 · 2026年11月7日续做</p><h1>先选六个声音，再听他们怎么说话</h1>
<div class="note">主版66条与爷爷备选15条已整理。已检查文件可解码、时长与拼接完整性；人物年龄感、自然度和情绪是否合适，仍等你试听确认。本页只在本地播放，不上传音频。</div>
<h2>1. 六个角色，同一句话</h2><p>你看，外面下雪了。我们一起去看看吧。</p><small>这一轮沿用昨天已有参数，尚未统一所有角色的语速和情绪，不是严格的盲听对照。</small>
<div class="grid">CARDS</div><div class="grid" style="margin-top:16px">COMPARISON</div>
<p><button id="download">保存我的角色选择</button> <small>选择会保存在当前浏览器；也可导出为JSON文件。</small></p>
<h2>2. 情景对话与情绪组</h2><p>先听01—07组钩子，再听其他对话及情绪组；带E/B的是爷爷备选。</p><div class="grid">SCENES</div>
<h2>3. 完整试听</h2><div class="grid">BUNDLES</div>
<h2>4. 每句干声</h2><div class="scroll"><table><thead><tr><th>角色</th><th>台词</th><th>试听</th><th>时长</th></tr></thead><tbody>ROWS</tbody></table></div>
<p><small>现有音频的原始请求参数没有逐句留档。索引中的角色归属及参数沿用当前配置，不把它们当作已验证的原始生成记录。</small></p></main>
<script>const key='family-voices-review-20261107';let saved={};try{saved=JSON.parse(localStorage.getItem(key)||'{}')}catch{}document.querySelectorAll('[data-review]').forEach(s=>{s.value=saved[s.dataset.review]||'';s.onchange=()=>{saved[s.dataset.review]=s.value;try{localStorage.setItem(key,JSON.stringify(saved))}catch{}}});document.getElementById('download').onclick=()=>{const u=URL.createObjectURL(new Blob([JSON.stringify({status:'user_choices',roles:saved},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='六角色试听选择.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};document.addEventListener('play',e=>{if(e.target.tagName==='AUDIO')document.querySelectorAll('audio').forEach(a=>{if(a!==e.target)a.pause()})},true);</script></html>'''
    for key, value in {"CARDS": "".join(cards), "COMPARISON": comparison, "SCENES": "".join(scenes),
                       "BUNDLES": "".join(bundles), "ROWS": "".join(rows)}.items():
        document = document.replace(key, value)
    (folder / "开始试听.html").write_text(document, encoding="utf-8")
    md = ["# 六角色配音续做试听", "", "优先打开同目录的 开始试听.html，可逐条播放并记录角色选择。", "",
          "主版66条、Edge爷爷备选15条；音频文件已整理，人工听感待确认。", "",
          "| 角色 | 台词 | 干声 |", "| --- | --- | --- |"]
    for item in items:
        md.append(f'| {labels.get(item["role"], "爷爷Edge备选")} | {item["text"]} | [{item["file"]}]({source(item).as_posix()}) |')
    (folder / "试听索引.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"html": str(folder / "开始试听.html"), "entries": len(items)}, ensure_ascii=False))


def render_candidate_index(folder: Path, cfg: dict) -> None:
    """为「候选音色横向对比包」生成可逐条试听、可勾选的本地试听页。

    候选包每个角色有两条场景：候选对照（同句同参数，只换音色）与候选情景
    （同角色情景台词）。页面按角色分组，先放两条混音供连续试听，再逐条列候选。
    """
    scenes = cfg.get("scenes") or []
    roles = cfg.get("roles") or {}
    esc = html.escape

    groups: dict[str, dict] = {}
    for scene in scenes:
        name = scene.get("name", "")
        stem = Path(name).stem
        kind = "对照" if "对照" in stem else "情景"
        role_key = ""
        for key, base in roles.items():
            if base.get("name") and base.get("name") in stem:
                role_key = key
                break
        if not role_key:
            role_key = (scene.get("lines") or [{}])[0].get("role", "")
        g = groups.setdefault(role_key, {"name": roles.get(role_key, {}).get("name", role_key),
                                         "mix": {}, "items": []})
        g["mix"][kind] = name
        for line in scene.get("lines", []):
            base = dict(roles.get(line.get("role")) or {})
            base.update({k: v for k, v in line.items() if v is not None})
            audio = folder / line["save_name"]
            engine = base.get("engine", "minimax")
            voice = (base.get("edge_voice") if engine == "edge"
                     else base.get("voice_id") or base.get("edge_voice"))
            g["items"].append({
                "label": Path(line["save_name"]).stem.split("_", 2)[-1],
                "voice": voice,
                "engine": engine,
                "emotion": line.get("emotion") or "-",
                "speed": base.get("speed", "-"),
                "pitch": base.get("pitch", "-"),
                "edge_rate": line.get("edge_rate", "-"),
                "edge_pitch": line.get("edge_pitch", "-"),
                "text": line.get("text", ""),
                "file": line["save_name"],
                "ok": audio.exists(),
            })

    def player(rel: str) -> str:
        url = quote(rel, safe="/")
        return f'<audio controls preload="none" src="{esc(url, quote=True)}"></audio>'

    sections = []
    for role_key, g in groups.items():
        mix_html = []
        for kind in ("对照", "情景"):
            name = g["mix"].get(kind)
            if not name or not (folder / name).exists():
                continue
            tip = "同一句台词、同一情绪参数，只换音色——用来盲听比对音色本身" if kind == "对照" \
                else "同一角色的情景台词——用来判断音色放进剧情里语气是否成立"
            mix_html.append(f'<article class="mix"><h3>{kind}混音 · {esc(g["name"])}</h3>'
                            f'{player(esc(name))}<p class="tip">{esc(tip)}</p></article>')
        rows = []
        for i, it in enumerate(g["items"], 1):
            opts = ('<option value="">待定</option><option>保留</option><option>淘汰</option>'
                    '<option>备选</option>')
            rows.append(
                f'<tr><td>{i}</td><td>{player(esc(it["file"]))}</td>'
                f'<td>{esc(it["label"])}</td><td class="id">{esc(str(it["voice"]))}</td>'
                f'<td>{esc(it["engine"])}</td><td>{esc(str(it["emotion"]))}</td>'
                f'<td>{esc(str(it["speed"]))}</td><td>{esc(str(it["pitch"]))}</td>'
                f'<td>{esc(str(it["edge_rate"]))}</td><td>{esc(str(it["edge_pitch"]))}</td>'
                f'<td><select data-role="{esc(role_key)}" data-idx="{i}">{opts}</select></td></tr>')
        sections.append(
            f'<section><h2>{esc(g["name"])}</h2><div class="grid">{"".join(mix_html)}</div>'
            f'<div class="scroll"><table><thead><tr><th>#</th><th>试听</th><th>音色</th><th>Voice ID</th>'
            f'<th>引擎</th><th>情绪</th><th>语速</th><th>音调</th><th>Edge语速</th><th>Edge音调</th><th>选择</th>'
            f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>')

    total = sum(len(g["items"]) for g in groups.values())
    missing = sum(1 for g in groups.values() for it in g["items"] if not it["ok"])
    stamp = folder.name.split("_")[-1]
    document = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>候选音色横向对比</title>
<style>body{margin:0;background:#f4f2ed;color:#282923;font:15px/1.7 system-ui,"Microsoft YaHei",sans-serif}
main{max-width:1280px;margin:auto;padding:40px 24px}h1{font-size:32px;line-height:1.3}h2{margin-top:44px;border-bottom:2px solid #d9d7cc;padding-bottom:10px}
h3{margin:0 0 10px;font-size:17px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;margin:16px 0 24px}
article{background:white;padding:18px;border:1px solid #deded5;border-radius:14px}
audio{width:100%}.tip{font-size:13px;color:#666;margin:8px 0 0}
.note{padding:16px 20px;border-radius:12px;background:#e7ecdf;margin:18px 0}
table{width:100%;border-collapse:collapse;background:#fff}th,td{padding:9px 10px;border-bottom:1px solid #e3e3da;vertical-align:top;font-size:13px}
th{background:#eceade;text-align:left;position:sticky;top:0}.id{font-family:ui-monospace,Consolas,monospace;font-size:11px;color:#555;max-width:230px;overflow-wrap:anywhere}
.scroll{overflow:auto;max-height:520px;border:1px solid #deded5;border-radius:12px}
select{padding:5px 8px;font:inherit;border:1px solid #aaa;border-radius:6px;background:#fff}button{font:inherit;padding:8px 14px;border-radius:8px;border:1px solid #888;background:#fff;cursor:pointer}
small{color:#666}</style>
<main><p>家庭六角色固定配音库 · 候选音色横向对比</p><h1>同一句话，换个人说给你听</h1>
<div class="note">每个角色两段：<b>对照混音</b>是同一句台词、同一情绪参数，只换音色；<b>情景混音</b>是同角色的剧情台词，听音色放进戏里语氣成不成立。
下表每条可单独播放并勾选「保留 / 淘汰 / 备选」。本页只在本地播放，不上传音频。</div>
<p><button id="download">保存我的选择</button> <small>选择保存在当前浏览器，可导出为 JSON 回传。</small></p>
SECTIONS
<p><small>音色的年龄感、自然度、情绪是否贴人物，最终要靠人耳判断；此页只负责把素材摆到同一条件下对比。</small></p></main>
<script>const key='family-candidates-review-STAMP';let saved={};try{saved=JSON.parse(localStorage.getItem(key)||'{}')}catch{}
document.querySelectorAll('select[data-role]').forEach(s=>{const k=s.dataset.role+'#'+s.dataset.idx;s.value=saved[k]||'';s.onchange=()=>{saved[k]=s.value;try{localStorage.setItem(key,JSON.stringify(saved))}catch{}}});
document.getElementById('download').onclick=()=>{const u=URL.createObjectURL(new Blob([JSON.stringify({status:'candidate_choices',choices:saved},null,2)],{type:'application/json'}));
const a=document.createElement('a');a.href=u;a.download='候选音色选择.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};
document.addEventListener('play',e=>{if(e.target.tagName==='AUDIO')document.querySelectorAll('audio').forEach(a=>{if(a!==e.target)a.pause()})},true);</script></html>'''
    document = document.replace("SECTIONS", "".join(sections)).replace("STAMP", stamp)
    (folder / "候选音色试听.html").write_text(document, encoding="utf-8")

    md = ["# 候选音色横向对比 · 试听索引", "",
          f"目录：`{folder.relative_to(ROOT)}` ｜ 候选 {total} 条 ｜ 缺失 {missing} 条", "",
          "先听每角色两段混音（对照 = 只换音色；情景 = 剧情台词），再逐条单听打勾。", ""]
    for role_key, g in groups.items():
        md.append(f"## {g['name']}")
        mix_list = " ｜ ".join(f"[{k}]({esc(v)})" for k, v in g["mix"].items())
        md.append(f"混音：{mix_list}")
        md.append("")
        md.append("| # | 音色 | Voice ID | 引擎 | 情绪 | 语速 | 音调 | Edge语速 | Edge音调 | 文件 | 状态 |")
        md.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for i, it in enumerate(g["items"], 1):
            md.append(f"| {i} | {it['label']} | `{it['voice']}` | {it['engine']} | {it['emotion']} | "
                      f"{it['speed']} | {it['pitch']} | {it['edge_rate']} | {it['edge_pitch']} | "
                      f"`{it['file']}` | {'✅' if it['ok'] else '缺'} |")
        md.append("")
    (folder / "试听索引.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"html": str(folder / "候选音色试听.html"), "index": str(folder / "试听索引.md"),
                      "candidates": total, "missing": missing}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="生成配音包试听索引")
    parser.add_argument("--config", default=str(ROOT / "config" / "voice_api" / "config.yaml"))
    parser.add_argument("--out-dir", default=None, help="索引输出目录名（相对 01_配音与音色库）")
    parser.add_argument("--delivery", default=None, help="已完成交付目录名，生成本地可播放试听页")
    parser.add_argument("--candidate", action="store_true", help="按候选音色对比包模式生成试听页")
    args = parser.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
    roles = cfg.get("roles") or {}
    scenes = cfg.get("scenes") or []

    out_dir = DEFAULT_OUT_ROOT / (args.out_dir or cfg.get("output_dir") or "")
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.candidate:
        render_candidate_index(out_dir, cfg)
        return
    if args.delivery:
        render_delivery_index(out_dir / args.delivery)
        return

    rows = []
    for scene in scenes:
        folder = DEFAULT_OUT_ROOT / scene["out_dir"] if scene.get("out_dir") else out_dir
        for line in scene.get("lines", []):
            role_key = line.get("role")
            base = dict(roles.get(role_key) or {})
            base.update({k: v for k, v in line.items() if v is not None})
            save_name = line.get("save_name") or f"{line.get('id')}.mp3"
            audio = folder / save_name
            rows.append(
                {
                    "scene": scene.get("name"),
                    "id": line.get("id"),
                    "role": base.get("name") or role_key,
                    "voice": base.get("voice_id") or base.get("edge_voice"),
                    "engine": base.get("engine", "minimax"),
                    "emotion": line.get("emotion") or "-",
                    "speed": line.get("speed") if line.get("speed") is not None else base.get("speed", "-"),
                    "pitch": line.get("pitch") if line.get("pitch") is not None else base.get("pitch", "-"),
                    "text": line.get("text", ""),
                    "file": save_name,
                    "ok": audio.exists(),
                }
            )

    lines_md = [
        "# 配音包试听索引",
        "",
        "勾选要保留的条目，反馈要换的角色即可（换音色改配置里的 roles，换语气改该条 emotion/speed/pitch）。",
        "",
        f"配置：`{Path(args.config).name}` ｜ 目录：`{out_dir.relative_to(ROOT)}` ｜ 条目：{len(rows)}",
        "",
        "| # | 角色 | 音色 | 引擎 | 情绪 | 语速 | 音调 | 台词 | 文件 | 状态 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for idx, row in enumerate(rows, 1):
        lines_md.append(
            f"| {idx} | {row['role']} | `{row['voice']}` | {row['engine']} | {row['emotion']} | "
            f"{row['speed']} | {row['pitch']} | {row['text']} | `{row['file']}` | {'✅' if row['ok'] else '缺'} |"
        )

    lines_md += ["", "## 场景混音文件", "", "| 场景 | 文件 |", "| --- | --- |"]
    for scene in scenes:
        folder = DEFAULT_OUT_ROOT / scene["out_dir"] if scene.get("out_dir") else out_dir
        mark = "✅" if (folder / scene.get("name", "")).exists() else "缺"
        lines_md.append(f"| {scene.get('name')} | `{scene.get('name')}` {mark} |")

    index_path = out_dir / "试听索引.md"
    index_path.write_text("\n".join(lines_md) + "\n", encoding="utf-8")
    print(json.dumps({"index": str(index_path), "entries": len(rows), "missing": sum(1 for r in rows if not r['ok'])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
