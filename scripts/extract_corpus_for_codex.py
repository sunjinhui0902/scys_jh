#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工程化预处理脚本：爆款作者口播文案本地数据清洗与全量提取
面向 Codex 逆向工程流水线生成标准化输入：
1. 00_stats.md (4大子赛道硬指标统计、句长分布、Top 30 四字高频词)
2. 01_hooks_bridges_ctas_[赛道名].md (全量前120字钩子、带货转折逼单样本 / 末尾150字升华)
3. 02_samples_[赛道名].md (按字数长中短均匀抽样 10 篇完整正文)
"""

import os
import sys
import re
from collections import Counter
import jieba

# 基础目录与配置
BASE_KB = r'D:\fuye\05_爆款知识库与复盘\爆款作者口播文案库'
OUT_DIR = r'D:\fuye\raw_extracted_for_codex'
os.makedirs(OUT_DIR, exist_ok=True)

TRACKS = [
    {
        'key': '读史明智',
        'dir': os.path.join(BASE_KB, '01_读史明智_文案TXT')
    },
    {
        'key': '锦绣千秋录',
        'dir': os.path.join(BASE_KB, '02_锦绣千秋录+食力过日子_文案TXT', '锦绣千秋录_19篇')
    },
    {
        'key': '食力过日子',
        'dir': os.path.join(BASE_KB, '02_锦绣千秋录+食力过日子_文案TXT', '食力过日子_11篇')
    },
    {
        'key': '元宝十大_资治通鉴',
        'dir': os.path.join(BASE_KB, '03_十大对标元宝视频+资治通鉴_文案TXT')
    }
]

KEYWORDS = ["书", "史记", "资治通鉴", "左下角", "小黄车", "链接", "孙辈", "孩子们", "收藏", "全彩"]

def parse_file(fpath):
    with open(fpath, 'r', encoding='utf-8', errors='ignore') as fp:
        raw_text = fp.read()
    
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    flat_text = ''.join(lines)
    clean_chars = re.sub(r'\s+', '', raw_text)
    char_count = len(clean_chars)
    
    # 句长切分（按常见中英文逗号、句号、感叹号、问号、分号及换行）
    sentences = [s.strip() for s in re.split(r'[,，.。!！?？;；\n\r]+', raw_text) if s.strip()]
    sent_lens = [len(s) for s in sentences]
    
    # 四字词统计
    words4 = [w for w in jieba.cut(raw_text) if len(w) == 4 and re.match(r'^[\u4e00-\u9fa5]{4}$', w)]
    
    # 1. 钩子（前120字）
    hook_120 = flat_text[:120]
    
    # 2. 带货转折与逼单检索
    hit_indices = []
    for i, line in enumerate(lines):
        if any(k in line for k in KEYWORDS):
            hit_indices.append(i)
            
    bridges = []
    if hit_indices:
        intervals = []
        for h in hit_indices:
            start_i = max(0, h - 2)
            end_i = min(len(lines), h + 3)
            intervals.append((start_i, end_i))
            
        # 合并相邻或重叠区间
        merged = []
        for s, e in intervals:
            if not merged:
                merged.append([s, e])
            else:
                if s <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], e)
                else:
                    merged.append([s, e])
                    
        for s, e in merged:
            block_lines = lines[s:e]
            kws = set()
            for bl in block_lines:
                for k in KEYWORDS:
                    if k in bl:
                        kws.add(k)
            bridges.append({
                'start_line': s + 1,
                'end_line': e,
                'keywords': list(kws),
                'text': '\n'.join(block_lines)
            })
            
    tail_150 = flat_text[-150:]
    
    return {
        'filename': os.path.basename(fpath),
        'char_count': char_count,
        'line_count': len(lines),
        'raw_text': raw_text,
        'lines': lines,
        'flat_text': flat_text,
        'sent_lens': sent_lens,
        'words4': words4,
        'hook_120': hook_120,
        'bridges': bridges,
        'tail_150': tail_150
    }

def main():
    track_results = {}
    
    print("开始清洗与解析全量文案...")
    for t in TRACKS:
        tname = t['key']
        tdir = t['dir']
        files = sorted([f for f in os.listdir(tdir) if f.endswith('.txt')])
        print(f"正在处理赛道 [{tname}] - 目录: {tdir} (文件数: {len(files)})")
        
        parsed_files = []
        for f in files:
            fp = os.path.join(tdir, f)
            parsed_files.append(parse_file(fp))
            
        track_results[tname] = parsed_files

    # -------------------------------------------------------------
    # 任务 1: 输出 00_stats.md
    # -------------------------------------------------------------
    print("\n生成 00_stats.md...")
    stats_md_path = os.path.join(OUT_DIR, '00_stats.md')
    
    with open(stats_md_path, 'w', encoding='utf-8') as fp:
        fp.write("# 爆款视频口播文案硬指标统计报告 (4 大子赛道)\n\n")
        fp.write("> **生成时间**：2026-10-23  \n")
        fp.write("> **分析对象**：343 篇对标爆款视频口播原文（UTF-8 纯文本）  \n")
        fp.write("> **定位说明**：本报告为工程化预处理产物，提供客观统计指标，供后续逆向分析与模板提取使用。\n\n")
        fp.write("---\n\n")
        
        fp.write("## 1. 全赛道核心指标横向对比总表\n\n")
        fp.write("| 子赛道名称 | 样本篇数 | 平均总字数 (字) | 字数极值区间 (Min - Max) | 平均分句长 (字/句) | 分句总数 | 四字词总频次 |\n")
        fp.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        
        for tname, files in track_results.items():
            total_n = len(files)
            counts = [f['char_count'] for f in files]
            avg_cnt = sum(counts) / total_n if total_n else 0
            min_cnt = min(counts) if total_n else 0
            max_cnt = max(counts) if total_n else 0
            
            all_sents = [l for f in files for l in f['sent_lens']]
            avg_sent = sum(all_sents) / len(all_sents) if all_sents else 0
            
            all_w4 = [w for f in files for w in f['words4']]
            
            fp.write(f"| **{tname}** | {total_n} 篇 | {avg_cnt:.1f} | {min_cnt} - {max_cnt} | {avg_sent:.2f} | {len(all_sents):,} | {len(all_w4):,} |\n")
            
        fp.write("\n---\n\n")
        fp.write("## 2. 各赛道高频四字词 Top 30 详表\n\n")
        
        for tname, files in track_results.items():
            w4_counter = Counter([w for f in files for w in f['words4']])
            top30 = w4_counter.most_common(30)
            
            fp.write(f"### 2.{list(track_results.keys()).index(tname)+1} 赛道：{tname} (共 {len(files)} 篇)\n\n")
            fp.write("| 排名 | 高频四字词 / 成语 | 出现频次 | 排名 | 高频四字词 / 成语 | 出现频次 | 排名 | 高频四字词 / 成语 | 出现频次 |\n")
            fp.write("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
            
            for row in range(10):
                c1 = top30[row] if row < len(top30) else ('-', '-')
                c2 = top30[row + 10] if (row + 10) < len(top30) else ('-', '-')
                c3 = top30[row + 20] if (row + 20) < len(top30) else ('-', '-')
                fp.write(f"| **#{row+1:02d}** | {c1[0]} | {c1[1]} | **#{row+11:02d}** | {c2[0]} | {c2[1]} | **#{row+21:02d}** | {c3[0]} | {c3[1]} |\n")
            fp.write("\n")

    # -------------------------------------------------------------
    # 任务 2: 输出 01_hooks_bridges_ctas_[赛道名].md (4份)
    # -------------------------------------------------------------
    print("\n生成 01_hooks_bridges_ctas_[赛道名].md...")
    for tname, files in track_results.items():
        fname = f"01_hooks_bridges_ctas_{tname}.md"
        out_path = os.path.join(OUT_DIR, fname)
        
        with open(out_path, 'w', encoding='utf-8') as fp:
            fp.write(f"# 全量首尾与带货转折样本提取库：{tname}\n\n")
            fp.write(f"> **赛道**：{tname}  \n")
            fp.write(f"> **样本总量**：{len(files)} 篇  \n")
            fp.write(f"> **提取规则**：  \n")
            fp.write(f"> 1. 【开头钩子样本】：全文前 120 字  \n")
            fp.write(f"> 2. 【带货转折与逼单样本】：检索包含关键词 `{KEYWORDS}` 之段落及其前 2 句上下文；  \n")
            fp.write(f"> 3. 【收尾升华样本】：若文中无带货关键词（如纯风景/生活叙事），则提取最后 150 字。  \n\n")
            fp.write("---\n\n")
            
            for idx, item in enumerate(files):
                fp.write(f"## 篇目 {idx+1:03d}：{item['filename']}\n\n")
                fp.write(f"- **总字数**：{item['char_count']} 字\n")
                fp.write(f"- **总行数**：{item['line_count']} 行\n\n")
                
                fp.write("### 📌 【开头钩子样本（前120字）】\n")
                fp.write(f"```text\n{item['hook_120']}\n```\n\n")
                
                if item['bridges']:
                    fp.write(f"### 🛒 【带货转折与逼单样本】（共检索到 {len(item['bridges'])} 处命中区间）\n\n")
                    for b_idx, b in enumerate(item['bridges']):
                        kw_str = "、".join(b['keywords'])
                        fp.write(f"**区间 #{b_idx+1}（第 {b['start_line']} - {b['end_line']} 行，命中词：`{kw_str}`）**：\n")
                        fp.write(f"```text\n{b['text']}\n```\n\n")
                else:
                    fp.write("### 🌅 【收尾升华样本（末尾150字）】（无明显带货词）\n\n")
                    fp.write(f"```text\n{item['tail_150']}\n```\n\n")
                    
                fp.write("---\n\n")

    # -------------------------------------------------------------
    # 任务 3: 输出 02_samples_[赛道名].md (4份)
    # -------------------------------------------------------------
    print("\n生成 02_samples_[赛道名].md (均匀抽样10篇完整正文)...")
    for tname, files in track_results.items():
        fname = f"02_samples_{tname}.md"
        out_path = os.path.join(OUT_DIR, fname)
        
        # 按字数升序排列
        sorted_files = sorted(files, key=lambda x: x['char_count'])
        total_n = len(sorted_files)
        
        sample_indices = []
        if total_n <= 10:
            sample_indices = list(range(total_n))
        else:
            # 均匀抽取 10 个索引
            sample_indices = [round(i * (total_n - 1) / 9) for i in range(10)]
            # 去重并保序
            seen = set()
            clean_indices = []
            for si in sample_indices:
                if si not in seen:
                    clean_indices.append(si)
                    seen.add(si)
            sample_indices = clean_indices
            
        with open(out_path, 'w', encoding='utf-8') as fp:
            fp.write(f"# 典型全文骨架抽样库：{tname} (均匀梯队10篇)\n\n")
            fp.write(f"> **赛道**：{tname}  \n")
            fp.write(f"> **总样本池**：{total_n} 篇  \n")
            fp.write(f"> **抽样规则**：按文案总字数由短到长均匀阶梯抽样（覆盖短篇、中篇、长篇各层次），提供未删节完整正文供逆向行文骨架。  \n\n")
            fp.write("---\n\n")
            
            # 梯队标签函数
            def get_tier(idx_in_10):
                if idx_in_10 < 3:
                    return "短篇样本 (Short Tier)"
                elif idx_in_10 < 7:
                    return "中篇样本 (Medium Tier)"
                else:
                    return "长篇样本 (Long Tier)"
                    
            for rank_idx, file_idx in enumerate(sample_indices):
                item = sorted_files[file_idx]
                tier_label = get_tier(rank_idx)
                
                fp.write(f"## 抽样 #{rank_idx+1:02d}【{tier_label}】：{item['filename']}\n\n")
                fp.write(f"- **字数排名**：第 {file_idx+1} / {total_n} 位\n")
                fp.write(f"- **总字数**：{item['char_count']} 字\n")
                fp.write(f"- **总分句数**：{len(item['sent_lens'])} 句（平均句长 {sum(item['sent_lens'])/len(item['sent_lens']):.2f} 字）\n\n")
                fp.write("### 📖 【未删节完整正文】\n\n")
                fp.write(f"```text\n{item['raw_text'].strip()}\n```\n\n")
                fp.write("---\n\n")

    print(f"\n全部工程化预处理完成！输出位于: {OUT_DIR}")

if __name__ == '__main__':
    main()
