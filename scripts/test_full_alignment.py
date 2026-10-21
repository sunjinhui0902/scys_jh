import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
import json
import re
import difflib
import jieba
from pathlib import Path
from scripts.fast_draft_pipeline import parse_gemini_markdown

def smart_split_clauses(text: str) -> list:
    """按标点与语义切分为 5~9 字呼吸节奏短句，结巴分词保护词组，合并微短句"""
    # 按照逗号、句号、感叹号、问号、分号等标点切分
    raw_parts = re.split(r"[，。！？；…\n]+", text)
    clauses = [p.strip() for p in raw_parts if p.strip()]
    
    final_clauses = []
    for c in clauses:
        c = c.strip("、 \t\r\n").replace("、", " ")
        if not c:
            continue
        if len(c) <= 10:
            final_clauses.append(c)
        else:
            # 超过 10 个字，使用 jieba 寻找最优词边界进行切分
            words = list(jieba.cut(c))
            best_idx = 1
            best_diff = 999
            cur_len = 0
            half = len(c) / 2.0
            for idx, w in enumerate(words[:-1]):
                cur_len += len(w)
                diff = abs(cur_len - half)
                if diff < best_diff:
                    best_diff = diff
                    best_idx = idx + 1
            p1 = "".join(words[:best_idx]).strip()
            p2 = "".join(words[best_idx:]).strip()
            if p1:
                final_clauses.append(p1)
            if p2:
                final_clauses.append(p2)
                
    # 合并过短微片段（<= 2个字，如“接着”、“随后”、“下了船”）到下一句
    merged = []
    i = 0
    while i < len(final_clauses):
        cur = final_clauses[i]
        if len(cur) <= 2 and i + 1 < len(final_clauses):
            merged.append(cur + " " + final_clauses[i+1])
            i += 2
        else:
            merged.append(cur)
            i += 1
    return merged

# Test on raw clean_c from markdown
test_text = "咱们隔辈人疼孩子，真不是给他买多少贵重玩具，而是趁咱们腿脚还利索，带他去看看祖国的大好河山。今天，咱们单独精讲，最适合带孙辈去长见识的第十座历史名城，山西平遥。"
splits = smart_split_clauses(test_text)
print("Splits for test intro:")
for s in splits:
    print(f"  [{len(s)}字] {s}")

# Test Pingyao alignment with raw clean_c
pdir = Path("03_视频成片与工程/01_平遥古城_单集精讲")
asr_d = json.load(open(pdir / "asr_alignment.json", encoding="utf-8"))
asr_clean = "".join(c for c in asr_d["text"] if c not in " ，。！？；…、\n\r\t")
asr_ts = asr_d["timestamp"]

md = open(pdir / "01_文案与分镜/口播文案.md", encoding="utf-8").read()

# Parse sections with raw text
shot_blocks = re.split(r"(?=- 【镜头\d+)", md)
sections = []
for block in shot_blocks:
    block = block.strip()
    if not block.startswith("- 【镜头"):
        continue
    clean_block = re.split(r"\n(?=## |\Z)", block)[0]
    header_line = clean_block.splitlines()[0]
    shot_id_match = re.search(r"【镜头(\d+)(.*?)】", header_line)
    if not shot_id_match:
        continue
    shot_idx = int(shot_id_match.group(1))
    
    clause_match = re.search(r"[-*]\s*对应口播[：:]\s*(.*?)(?=\n\s*[-*]\s*画面描述|\n\s*[-*]\s*【|\Z)", clean_block, re.DOTALL)
    if clause_match:
        raw_text = clause_match.group(1).strip().strip("[]【】\"'")
        clean_c = re.sub(r"[（\(].*?[）\)]", "", raw_text)
        clauses = smart_split_clauses(clean_c)
        sections.append({
            "shot_index": shot_idx,
            "raw_text": clean_c,
            "clauses": clauses
        })

all_clauses = []
for s in sections:
    all_clauses.extend(s["clauses"])

script_clean = "".join("".join(c for c in cl if c not in " ，。！？；…、\n\r\t") for cl in all_clauses)
print(f"Total sections: {len(sections)}, Total clauses: {len(all_clauses)}")
print(f"script_clean len: {len(script_clean)}, asr_clean len: {len(asr_clean)}")

sm = difflib.SequenceMatcher(None, script_clean, asr_clean)
char_ts = [None] * len(script_clean)
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == 'equal':
        for i, j in zip(range(i1, i2), range(j1, j2)):
            char_ts[i] = asr_ts[j]
    elif tag == 'replace':
        asr_slice = asr_ts[j1:j2]
        if asr_slice:
            start_t = asr_slice[0][0]
            end_t = asr_slice[-1][1]
            n = i2 - i1
            dur = (end_t - start_t) / n if n > 0 else 0
            for k in range(n):
                char_ts[i1 + k] = [int(start_t + k * dur), int(start_t + (k + 1) * dur)]

last_t = 0
for idx in range(len(char_ts)):
    if char_ts[idx] is None:
        nxt = None
        for f in range(idx + 1, len(char_ts)):
            if char_ts[f] is not None:
                nxt = char_ts[f][0]
                break
        if nxt is None:
            nxt = last_t + 200
        char_ts[idx] = [last_t, nxt]
    last_t = char_ts[idx][1]

# Now calculate exact timing for each clause
cur_char_idx = 0
clause_timeline = []
for cl in all_clauses:
    cl_clean = "".join(c for c in cl if c not in " ，。！？；…、\n\r\t")
    if not cl_clean:
        continue
    c_start_idx = cur_char_idx
    c_end_idx = cur_char_idx + len(cl_clean)
    start_ms = char_ts[c_start_idx][0]
    end_ms = char_ts[c_end_idx - 1][1]
    clause_timeline.append({
        "text": cl,
        "start_s": start_ms / 1000.0,
        "end_s": end_ms / 1000.0,
        "dur_s": (end_ms - start_ms) / 1000.0
    })
    cur_char_idx = c_end_idx

print(f"Total aligned clauses: {len(clause_timeline)}")
print("--- First 10 clauses ---")
for item in clause_timeline[:10]:
    print(f"[{item['start_s']:.2f}s - {item['end_s']:.2f}s] ({item['dur_s']:.2f}s) {item['text']}")

print("--- Key problem points ---")
for item in clause_timeline:
    if any(k in item['text'] for k in ["说到这儿", "词儿", "肚子"]):
        print(f"[{item['start_s']:.2f}s - {item['end_s']:.2f}s] ({item['dur_s']:.2f}s) {item['text']}")

