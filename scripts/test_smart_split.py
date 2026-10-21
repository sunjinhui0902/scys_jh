# -*- coding: utf-8 -*-
import re
import jieba

def smart_split_clauses(text: str, max_len: int = 12, min_len: int = 3) -> list:
    """
    智能中文断句：
    1. 优先在句读标点（，。！？；…）处切分
    2. 超过 max_len 的长句，利用 jieba 词性/词边界切分，绝不切断词汇（如'祖国','明清','孩子'等）
    3. 极短连接词（如'接着'、'随后'、'下了船'）若短于 min_len，自动与后句合并，避免闪烁极短字幕
    """
    # 标点切分
    raw_parts = re.split(r"([，。！？；…\n]+)", text)
    initial_clauses = []
    cur = ""
    for p in raw_parts:
        if not p:
            continue
        if re.match(r"^[，。！？；…\n]+$", p):
            if cur.strip():
                initial_clauses.append(cur.strip())
            cur = ""
        else:
            cur += p
    if cur.strip():
        initial_clauses.append(cur.strip())
        
    refined_clauses = []
    for c in initial_clauses:
        # 去除首尾标点并将内部顿号转为空格
        c = c.strip("，。！？；…、 \t\r\n").replace("、", " ")
        if not c:
            continue
            
        if len(c) <= max_len:
            refined_clauses.append(c)
        else:
            # 使用 jieba 切词找最近中点的词边界
            words = list(jieba.cut(c))
            best_split_idx = -1
            best_diff = 999
            cur_len = 0
            for i, w in enumerate(words[:-1]):
                cur_len += len(w)
                diff = abs(cur_len - len(c) / 2.0)
                if diff < best_diff:
                    best_diff = diff
                    best_split_idx = cur_len
            
            if best_split_idx > 0 and best_split_idx < len(c):
                part1 = c[:best_split_idx].strip()
                part2 = c[best_split_idx:].strip()
                refined_clauses.append(part1)
                refined_clauses.append(part2)
            else:
                refined_clauses.append(c)
                
    # 合并过短的连接词（如 '接着'、'随后' 等 <= 2字 或 极短引导词）
    merged_clauses = []
    skip_next = False
    for i, c in enumerate(refined_clauses):
        if skip_next:
            skip_next = False
            continue
        # 如果当前短句仅 2 个字（如“接着”、“随后”）且后面还有句子，则与后一句合并
        if len(c) <= 2 and i < len(refined_clauses) - 1:
            next_c = refined_clauses[i+1]
            if len(c) + len(next_c) <= 15:
                merged_clauses.append(f"{c} {next_c}")
                skip_next = True
                continue
        merged_clauses.append(c)
        
    return merged_clauses

if __name__ == "__main__":
    tests = [
        "咱们隔辈人疼孩子，真不是给他买多少贵重玩具，而是趁咱们腿脚还利索，带他去看看祖国的大好河山。",
        "接着，您牵着孩子的手，走进杨家岭和枣园的土窑洞。",
        "推开那扇吱呀作响的木格花窗，窑洞里夏天凉快、冬天保暖，可陈设却简陋得让人心疼。",
        "接着，您再带孩子坐上摇橹船，去湖中心看看三潭印月。",
        "下了船，再去湖边的岳王庙走一走，"
    ]
    for t in tests:
        print("INPUT:", t)
        res = smart_split_clauses(t)
        for r in res:
            print(f"  [{len(r)}字] {r}")
        print()
