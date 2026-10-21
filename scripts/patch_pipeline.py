# -*- coding: utf-8 -*-
import re

with open("scripts/fast_draft_pipeline.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update split_rhythmic_clauses
old_clause = """    # 细分过长的句子（超过 11 字者在逗号/语气处切分）
    final_clauses = []
    for c in clauses:
        if len(c) <= 11:
            final_clauses.append(c)
        else:
            mid = len(c) // 2
            final_clauses.append(c[:mid].strip())
            final_clauses.append(c[mid:].strip())
    return [c for c in final_clauses if c]"""

new_clause = """    # 细分过长的句子（超过 11 字者在逗号/语气处切分），清理顿号为优雅空格
    final_clauses = []
    for c in clauses:
        c = c.strip("，。！？；…、 \\t\\r\\n").replace("、", " ")
        if not c:
            continue
        if len(c) <= 11:
            final_clauses.append(c)
        else:
            mid = len(c) // 2
            final_clauses.append(c[:mid].strip())
            final_clauses.append(c[mid:].strip())
    return [c for c in final_clauses if c]"""

# 2. Update sticker_match
old_sticker = """    sticker_match = re.search(r"转化贴纸文案[：:]\\s*【(.*?)】", md_content)
    if sticker_match:
        meta["sticker"] = sticker_match.group(1).strip()"""

new_sticker = """    sticker_match = re.search(r"转化贴纸文案[：:]\\s*【(.*?)】", md_content)
    if sticker_match:
        raw_st = sticker_match.group(1).strip()
        # 彻底清除样式提示词如 “红底金字：”、“黄底黑字：”
        meta["sticker"] = re.sub(r"^[^\s：:]*?[底字色框][\w]*?[：:]\s*", "", raw_st)"""

assert old_clause in content, "old_clause not found"
assert old_sticker in content, "old_sticker not found"

content = content.replace(old_clause, new_clause)
content = content.replace(old_sticker, new_sticker)

with open("scripts/fast_draft_pipeline.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Patch applied successfully to scripts/fast_draft_pipeline.py")
