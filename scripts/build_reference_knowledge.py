"""Build a small source-linked reference-book knowledge index, or search it."""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "05_爆款知识库与复盘"
QUICK = BASE / "参考图书拆解_2026-10-15"
CITY = BASE / "15城专题拆解_2026-10-15"
OUT = BASE / "城市与图书知识库"
GROUPS = {
    "城市空间与秩序": ["北京", "西安", "洛阳", "南京", "承德"],
    "石窟艺术与交流": ["大同", "洛阳", "敦煌"],
    "水与山水经营": ["苏州", "杭州", "丽江"],
    "商业与城市网络": ["平遥", "泉州"],
    "知识与文化传承": ["安阳", "曲阜", "登封"],
}
TITLES = {"B01": "中国历史文化名城大辞典·下卷", "B02": "小城大历史·南方篇",
          "B03": "小城大历史·北方篇", "B04": "走遍中国109个历史文化名城·下册"}
LABELS = {"official_supported": "官方支持限定判断", "book_supported": "书页支持，按题补核",
          "qualified_or_conflicting": "限定或差异，保留口径", "verified": "核心判断已交叉核对",
          "needs_review": "待核对", "candidate": "候选，效果未测试"}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def link(label: str, path: Path, start: Path) -> str:
    return f"[{label}]({Path(os.path.relpath(path, start)).as_posix().replace(' ', '%20')})"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def lines(path: Path):
    return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines() if s.strip()]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def themes(city: str) -> list[str]:
    return [g for g, cities in GROUPS.items() if city in cities] or ["其他城市线索"]


def build() -> dict[Path, str]:
    cities = lines(CITY / "城市档案.jsonl")
    facts = lines(CITY / "事实台账.jsonl")
    topics = lines(CITY / "视频选题90条.jsonl")
    old_topics = lines(QUICK / "选题卡.jsonl")
    manifest = read_json(CITY / "来源与范围.json")
    assert [c["city"] for c in cities] == manifest["user_city_order"]
    assert (len(cities), len(facts), len(topics), len(old_topics)) == (15, 75, 90, 20)
    outputs: dict[Path, str] = {}

    def page(name: str, text: str):
        outputs[OUT / name] = text.strip() + "\n"

    def lk(label: str, path: Path, name: str = "README.md"):
        return link(label, path, (OUT / name).parent)

    records = []

    def record(key, kind, title, source, source_id="", city="", status="", **extra):
        records.append(dict(id=key, kind=kind, title=title, city=city,
                            themes=themes(city) if city else [], source_file=rel(source),
                            source_id=source_id, status=status, **extra))

    for b in manifest["books"]:
        record("book:" + b["id"], "book", TITLES[b["id"]], CITY / "来源与范围.json", b["id"],
               status="targeted_reading", local_pdf=b["file"], source_sha256=b["sha256"],
               selected_pdf_pages=b["selected_pdf_pages"])
    for s in manifest["official_sources"]:
        record("source:" + s["id"], "source", s["title"], CITY / "来源与范围.json", s["id"],
               status="checked_at_source_date", url=s["url"], checked_on=s["checked_on"])
    for n, c in enumerate(cities, 1):
        record("city:" + c["city_id"], "city", c["position"], ROOT / c["file"], c["city_id"],
               c["city"], "targeted_reading", summary=c["summary"], original_opening=c["opening"],
               book_scope=c["book_scope"], data_file=rel(CITY / "城市档案.jsonl"), source_line=n)
    for n, f in enumerate(facts, 1):
        record("fact:" + f["fact_id"], "fact", f["claim"], CITY / "事实台账.jsonl", f["fact_id"],
               f["city"], f["status"], source_line=n, evidence=f["evidence"], scope=f["scope"])
    for n, t in enumerate(topics, 1):
        record("city15:" + t["topic_id"], "topic", t["question"], CITY / "视频选题90条.jsonl", t["topic_id"],
               t["city"], t["status"], source_line=n, batch="city15_targeted_v1",
               angle=t["original_angle"], evidence=t["evidence_entry"],
               needs=t["visual_and_verification_needs"], performance=t["performance"], product_sku=t["product_sku"])
    for n, t in enumerate(old_topics, 1):
        record("quick:" + t["id"], "topic", t["viewer_question"], QUICK / "选题卡.jsonl", t["id"],
               t["city"], t["verification_status"], source_line=n, batch="quick_reference_v1",
               angle=t["original_hook"], evidence=t["sources"], needs=t["needs_check"],
               performance=t["performance_status"], product_sku="unconfirmed")
    draft = QUICK / "03_三条原创口播与分镜.md"
    for n, city in enumerate(["平遥", "大同", "苏州"], 1):
        record(f"script:quick:{n:02}", "script", f"{city}原创口播与分镜", draft,
               f"{n:02}", city, "read_aloud_draft", section=f"## {n:02}｜{city}")
    assert len({r["id"] for r in records}) == len(records) == 225
    for r in records:
        assert (ROOT / r["source_file"]).is_file(), r["source_file"]
        if "source_line" in r:
            source = ROOT / r.get("data_file", r["source_file"])
            item = lines(source)[r["source_line"] - 1]
            assert r["source_id"] in [item.get(k) for k in ("id", "city_id", "topic_id", "fact_id")]
    page("检索索引.jsonl", "\n".join(json.dumps(r, ensure_ascii=False) for r in records))
    status_counts = dict(collections.Counter(f["status"] for f in facts))
    source_files = sorted([p for folder in (QUICK, CITY) for p in folder.rglob("*") if p.is_file()])
    inventory = [dict(file=rel(p), sha256=digest(p), bytes=p.stat().st_size) for p in source_files]
    page("归档清单.json", json.dumps(dict(schema_version=1, organized_on="2026-10-15",
         scope="两批参考图书拆解的分类索引；历史原件保留原位", counts=dict(books=4, city_dossiers=15,
         fact_records=75, fact_status=status_counts, current_topic_records=90, historical_topic_records=20,
         topic_records_not_deduplicated=110, original_read_aloud_drafts=3, city_openings=15,
         search_records=225, source_files=len(inventory)),
         sources=inventory, exclusions=["原PDF、OCR全文与页面图像不入公开库", "不计入竞品分析验收数量"],
         local_related=dict(path="03_视频成片与工程/15城文案与配图_75张_2026-10-15/15城文案与配图",
         status="linked_only_not_reviewed_or_uploaded_in_this_archive")), ensure_ascii=False, indent=2))
    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(csv_buffer, fieldnames=["file", "sha256", "bytes"], lineterminator="\n")
    writer.writeheader(); writer.writerows(inventory)
    page("资料总目录.csv", csv_buffer.getvalue())

    page("README.md", f"""# 城市与图书知识库

服务本项目历史文化类视频号图书内容：按城市找问题，按主题串系列，按事实ID回查来源，再写原创口播与安排画面。组织日期：2026-10-15。

## 分类入口

| 分类 | 已归档内容 | 入口 |
| --- | --- | --- |
| 01 书目与来源 | 4本参考书、18个官方资料入口、原书章节定位 | [书目来源](01_书目与来源/README.md) |
| 02 城市档案 | 指定15城详细档案；另列首轮其他城市线索 | [按城市查](02_城市档案/README.md) |
| 03 跨城主题 | 城市空间、石窟、水与山水、商业网络、文化传承 | [按主题查](03_跨城主题/README.md) |
| 04 事实依据 | 75条事实记录：50官方支持、21书页支持、4限定或差异 | [事实状态与入口](04_事实依据/README.md) |
| 05 视频选题 | 90条15城候选题＋20张首轮选题卡 | [选题索引](05_视频选题/README.md) |
| 06 文案与素材 | 3条原创试读稿、15段城市开场；关联本机图文包 | [写稿与素材入口](06_文案与素材/README.md) |
| 07 方法与核验 | 复用步骤、GitHub技能选型、核验问题与复盘入口 | [使用与维护](07_方法与核验/README.md) |

两批原件保持原位；本目录承担分类和检索，来源路径与文件指纹记入[归档清单](归档清单.json)及[资料总目录](资料总目录.csv)。110是两批选题记录数，尚未去重；15段开场不计作完整稿；目录定位与OCR数量不计作精读数量。

## 一次复用怎么走

1. 进入城市档案，选一个观众问题；也可从主题专题选一组城市。
2. 从90题中选择 `Cxx-Txx`，取该城事实 `Cxx-Fxx`，按需回到原书页或官方资料。
3. 用一个发现写完整口播，参考3条试读稿的结构；实际引书对应真实在售版本和内页。
4. 安排实景、中文图示和必要署名，试读后确定时长；发布表现回填项目既有复盘表。

研究资料、候选题、试读稿与素材包分别保留自己的状态。现有题目没有本批播放或成交实测，不能称为已验证爆款。

## 直接检索

[检索索引.jsonl](检索索引.jsonl)含225条来源索引，支持城市、主题、类型、编号及标题检索。每条保留原文件、记录编号与适用状态；书页证据保留页码与原件指纹。

在项目根目录使用已有Python环境：

```text
python scripts/build_reference_knowledge.py --search 泉州
python scripts/build_reference_knowledge.py --search 石窟 --kind topic
python scripts/build_reference_knowledge.py --search C03-F01 --kind fact
```

上述搜索只读。以后增加批次时，先扩展整理脚本的来源配置，再重建目录；当前脚本只覆盖已列明的两批。校验命令：`python scripts/build_reference_knowledge.py --check`。

## 历史批次

- {lk('参考图书首轮拆解', QUICK / 'README.md')}：四书定位、20张卡、3条试读稿与技能选型。
- {lk('15城专题拆解', CITY / 'README.md')}：逐城详细总结、75条事实、90题、跨城试做建议。

原PDF与OCR缓存留在本机，公开仓库保存原创分析、简短事实定位与索引。其他工程中尚未验收的文案和媒体仅关联路径，未纳入本次同步包。
""")
    name = "01_书目与来源/README.md"
    rows = "\n".join(f"| {b['id']} | {TITLES[b['id']]} | {b['pages']} | {len(b['selected_pdf_pages'])} |" for b in manifest["books"])
    officials = "\n".join(f"- `{s['id']}` [{s['title']}]({s['url']})（原记录核对日：{s['checked_on']}）。" for s in manifest["official_sources"])
    page(name, f"""# 书目与来源

| 编号 | 参考书 | PDF总页数 | 15城专题引用页数 |
| --- | --- | ---: | ---: |
{rows}

只读过目录及重点正文。15城专题引用75页；截至原批次记录，OCR缓存累计115页。以上不表示1229页已全文精读。

- {lk('四书性质、优先级与边界', QUICK / '01_四书拆解.md', name)}
- {lk('214条城市章节定位', QUICK / '城市章节索引.csv', name)}：目录定位，不是214个已深拆主题。
- {lk('原件指纹与实际引用页', CITY / '来源与范围.json', name)}
- {lk('本机参考图书目录', ROOT / '02_公共资产库/参考图书/README.md', name)}：原件未移动、未公开。

## 官方资料入口

以下沿用原批次核对记录，本次归类未重新逐页浏览；仅支持各事实条目的限定范围。

{officials}
""")
    name = "02_城市档案/README.md"
    rows = []
    for c in cities:
        rows.append(f"| {c['city_id']} | {lk(c['city'], ROOT / c['file'], name)} | {c['position']} | {'、'.join(themes(c['city']))} |")
    extra = sorted({t["city"] for t in old_topics} - {c["city"] for c in cities})
    page(name, f"""# 按城市检索

每城含定位、历史观察层次、5条事实、6条选题、开场、画面与引书方向及边界。城市固定按用户指定顺序排列。

| 编号 | 城市档案 | 内容切口 | 主题 |
| --- | --- | --- | --- |
{chr(10).join(rows)}

完整连读版：{lk('15城详细总结', CITY / '15城详细总结.md', name)}。

## 首轮其他城市线索

{'、'.join(extra)}。这些城市只有首轮选题线索，未新增同等深度的城市档案。去{lk('选题索引', OUT / '05_视频选题/README.md', name)}查历史卡片；继续研究先回原书定位。
""")
    name = "03_跨城主题/README.md"
    group_links = []
    for i, (group, members) in enumerate(GROUPS.items(), 1):
        filename = f"03_跨城主题/{i:02}_{group}.md"
        group_links.append(f"- [{group}]({i:02}_{group}.md)：{'、'.join(members)}。")
        content = []
        for city in members:
            c = next(c for c in cities if c["city"] == city)
            content.append(f"## {city}\n\n{c['position']}。\n\n{lk('城市档案与来源', ROOT / c['file'], filename)}；事实编号 `{c['city_id']}-F01～F05`，选题编号 `{c['city_id']}-T01～T06`。\n")
        page(filename, f"# {group}\n\n本页按观察角度组织城市系列，城市可跨主题。具体相似与差异须回各城档案，不能把同一成因套用到所有城市。\n\n" + "\n".join(content) + f"\n延伸：{lk('跨城系列与试做建议', CITY / '跨城系列与试做建议.md', filename)}。")
    page(name, "# 按跨城主题检索\n\n五组是内容策划分类，允许交叉；不代表城市历史只有这一面。\n\n" + "\n".join(group_links))
    name = "04_事实依据/README.md"
    fact_rows = []
    for c in cities:
        fs = [f for f in facts if f["city"] == c["city"]]
        count = collections.Counter(f["status"] for f in fs)
        fact_rows.append(f"| {c['city']} | `{c['city_id']}-F01～F05` | {count['official_supported']} | {count['book_supported']} | {count['qualified_or_conflicting']} |")
    differences = "\n".join(f"- `{f['fact_id']}` {f['city']}：{f['claim']}" for f in facts if f["status"] == "qualified_or_conflicting")
    page(name, f"""# 事实依据与状态

75条事实：50条官方支持限定判断，21条书页支持，4条保留限定或差异。全部保留在{lk('原事实台账', CITY / '事实台账.jsonl', name)}；支持范围随记录保存，不能把一条已核事实扩展成整篇稿件已核。

| 城市 | 事实编号 | 官方支持 | 书页支持 | 限定或差异 |
| --- | --- | ---: | ---: | ---: |
{chr(10).join(fact_rows)}

## 优先保留的差异记录

{differences}

完整的8类写稿核对问题见{lk('来源与核对说明', CITY / '来源与核对说明.md', name)}。8类问题与4条结构化差异记录是不同统计口径。

旧书人口、排名、区划与实时开放信息不作为现状；传说、游记与文学想象须标明类型。OCR只辅助定位，专名、年代和数值回看原页。
""")
    name = "05_视频选题/README.md"
    topic_rows = "\n".join(f"| {t['topic_id']} | {t['city']} | {t['question']} |" for t in topics)
    old_rows = "\n".join(f"| quick:{t['id']} | {t['city']} | {t['viewer_question']} | {LABELS.get(t['verification_status'], t['verification_status'])} |" for t in old_topics)
    page(name, f"""# 视频选题索引

90条15城候选题和20张首轮卡，共110条来源记录，未做跨批语义去重。先选15城专题中的细化问题；需要扩展角度时再查历史卡片。历史 `T01` 与当前 `C01-T01` 编号不同，统一索引用批次前缀区分。

详细证据和画面补核：{lk('90条选题原记录', CITY / '视频选题90条.jsonl', name)}、{lk('首轮20卡原记录', QUICK / '选题卡.jsonl', name)}。候选题均无本批效果实测，真实带货SKU待确认。

## 当前15城90题

| 编号 | 城市 | 观众问题 |
| --- | --- | --- |
{topic_rows}

## 首轮20张历史卡

核对状态只适用于原卡写明的核心判断，具体细节仍按原记录处理。

| 检索编号 | 城市 | 观众问题 | 原卡状态 |
| --- | --- | --- | --- |
{old_rows}
""")
    name = "06_文案与素材/README.md"
    local = ROOT / "03_视频成片与工程/15城文案与配图_75张_2026-10-15/15城文案与配图"
    openings = "\n\n".join(f"- **{c['city']}**：{lk('城市开场及画面建议', ROOT / c['file'], name)}。" for c in cities)
    page(name, f"""# 文案与素材入口

## 原创试读稿

{lk('平遥、大同、苏州：3条完整口播与分镜', draft, name)}。按原批次为试读稿，目标时长尚未以配音校准，镜头是素材需求；引书段对应研究参考书，实际带货版本要另外对照。

## 15城开场与画面方向

以下是开场段和写作方向，不单独计为15条完整口播。

{openings}

## 关联本机已有图文包

{lk('15城文案与配图：开始使用', local / '开始使用.md', name)}；{lk('15城完整文案', local / '15城完整文案.md', name)}；{lk('图片来源总表', local / '图片来源总表.csv', name)}。

本轮仅确认入口文件存在并关联目录。该包说明称含15份完整口播、60张实景和15张AI氛围图；这些是包内声明，本次没有逐条审稿、逐图复核许可或验证图文对应，也未将其文案、媒体和恢复包纳入本次提交。此入口依赖本机已有文件，跨电脑应以该生产工程独立交付记录为准。

研究批次的3条稿、15段开场和此生产包分开计数。图像授权、署名、AI标识、真实SKU与试读时长在选定素材和稿件后按实际内容核对。
""")
    name = "07_方法与核验/README.md"
    page(name, f"""# 方法、核验与维护

## 按项目目标复用

服务历史文化、城市观察与图书内容：一个具体疑问进入，两个到三个必要事实支撑，一个可见发现收束，再自然引到实际图书。事实来源留后台，不把核对过程念进口播。

- {lk('参考图书到视频号 Skill', ROOT / '.agents/skills/reference-book-to-video/SKILL.md', name)}：检索、回原页、写稿和证据边界。
- {lk('视频号图书内容 Skill', ROOT / '.agents/skills/wechat-channels-book-commerce/SKILL.md', name)}：口播、分镜、商品衔接及发布检查。
- {lk('GitHub技能选型与复用记录', QUICK / '04_GitHub技能选型与复用.md', name)}：保留首轮选型结果，外部仓库状态与许可不因本次归档重新确认。
- {lk('说书式口播写法', BASE / '07_说书式口播写法.md', name)}：项目现有方法；归档时工作区文件，维护与同步由原任务负责。
- {lk('短片生产SOP', BASE / '03_短片生产SOP.md', name)}、{lk('发布复盘表', BASE / '04_发布复盘表.csv', name)}：沿用现有生产与反馈入口。

## 核验优先级

先处理实际稿件会使用的事实、数字和画面。差异项保留原口径；未确认的细节可避用。参考{lk('来源与核对说明', CITY / '来源与核对说明.md', name)}。研究书目、实际售卖SKU和素材许可分别记录。

## 新资料怎样存

1. 新书或新城市拆解另开带日期批次，保存书目指纹、读取范围、事实与候选题；已验收原件不覆盖。
2. 扩展 `scripts/build_reference_knowledge.py` 的明确来源，更新此分类入口和检索索引；不扫描OCR全文、不自动吸收未经审核的生产稿。
3. 用 `--check` 验证索引与源记录一致，再按项目约定只同步该次任务结果。原PDF、OCR全文、页面图和媒体遵循各自存储约定。
4. 新开场、完整稿、配音、成片、发布与反馈分别计数；只有实际数据支持时才归纳表现。

本次只增加知识库分类、检索和路由，没有改变原批次事实状态、竞品验收数量或既有试做工程。
""")
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare generated files without writing")
    parser.add_argument("--search", help="Read-only search of the stored index")
    parser.add_argument("--kind", choices=["book", "source", "city", "fact", "topic", "script"])
    args = parser.parse_args()
    if args.search is not None:
        if args.check:
            parser.error("--search and --check are mutually exclusive")
        query = args.search.casefold()
        hits = [r for r in lines(OUT / "检索索引.jsonl")
                if (not args.kind or r["kind"] == args.kind)
                and query in json.dumps(r, ensure_ascii=False).casefold()]
        for r in hits:
            print(f"{r['id']} | {r['city']} | {r['title']} | {r['status']}\n  {r['source_file']} [{r['source_id']}]")
        print(f"共 {len(hits)} 条来源记录；非去重题目数。")
        return
    if args.kind:
        parser.error("--kind requires --search")
    outputs = build()
    changed = [p for p, content in outputs.items() if not p.exists() or p.read_text(encoding="utf-8") != content]
    if args.check:
        for p in changed:
            print("STALE", rel(p))
        if changed:
            raise SystemExit(1)
        print(f"OK: {len(outputs)} files; 225 records; source IDs and paths valid")
        return
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    print(f"Organized {len(outputs)} files; changed {len(changed)}; 225 source-linked records")


if __name__ == "__main__":
    main()
