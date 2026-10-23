"""Read-only validation of the handed-off copy corpus; outputs stay in this draft.

Never imports/runs the original extractor (it writes into its input directory).
"""
from pathlib import Path
import re, json, hashlib, statistics, collections, unicodedata

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'codex_analysis_draft'
KB = ROOT / '05_爆款知识库与复盘' / '爆款作者口播文案库'
RAW = ROOT / 'raw_extracted_for_codex'
TRACKS = {
    'DS': ('读史明智', KB / '01_读史明智_文案TXT'),
    'JX': ('锦绣千秋录', KB / '02_锦绣千秋录+食力过日子_文案TXT' / '锦绣千秋录_19篇'),
    'SL': ('食力过日子', KB / '02_锦绣千秋录+食力过日子_文案TXT' / '食力过日子_11篇'),
    'YB': ('元宝十大_资治通鉴', KB / '03_十大对标元宝视频+资治通鉴_文案TXT'),
}
KEYS = ['书','史记','资治通鉴','左下角','小黄车','链接','孙辈','孩子们','收藏','全彩']
STRONG = re.compile('这本书|这套书|一本书|一套书|推荐.{0,16}书|下方.*链接|小黄车|先用后付|七天无理由|书已上架|书以上价|书以上架|下单|购买|买一本|买一套')

def sha(b): return hashlib.sha256(b).hexdigest()
def normalized(t): return re.sub(r'[^\w\u4e00-\u9fff]', '', unicodedata.normalize('NFKC', t)).lower()
def rel(p): return p.relative_to(ROOT).as_posix()
def quant(v, p):
    a = sorted(v); x = (len(a)-1)*p; lo=int(x); hi=min(lo+1,len(a)-1)
    return round(a[lo]+(a[hi]-a[lo])*(x-lo),2)

rows=[]; summary={}; checks=[]
try:
    import jieba
except ImportError:
    jieba=None

for code,(name,folder) in TRACKS.items():
    records=[]
    hook_text=(RAW/f'01_hooks_bridges_ctas_{name}.md').read_text(encoding='utf-8')
    hook_blocks=re.split(r'^## 篇目 \d+：',hook_text,flags=re.M)[1:]
    sample_text=(RAW/f'02_samples_{name}.md').read_text(encoding='utf-8')
    sample_blocks=re.split(r'^## 抽样 #\d+【.*?】：',sample_text,flags=re.M)[1:]
    for i,p in enumerate(sorted(folder.glob('*.txt')),1):
        b=p.read_bytes(); t=b.decode('utf-8-sig',errors='strict')
        lines=[l.strip() for l in t.splitlines() if l.strip()]; flat=''.join(lines)
        sents=[s.strip() for s in re.split(r'[,，.。!！?？;；\n\r]+',t) if s.strip()]
        bridge=[]
        for j,l in enumerate(lines):
            if any(k in l for k in KEYS):
                start=max(0,j-2); end=min(len(lines),j+3)
                if bridge and start<=bridge[-1][1]: bridge[-1][1]=max(end,bridge[-1][1])
                else: bridge.append([start,end])
        blocks=['\n'.join(lines[a:z]) for a,z in bridge]
        raw_lines=t.splitlines(); hooks=hook_blocks[i-1] if i<=len(hook_blocks) else ''
        actual_hook=re.search(r'```text\n(.*?)\n```',hooks,re.S)
        row={'id':f'{code}{i:03d}','track':name,'source':rel(p),'filename':p.name,'sha256':sha(b),
             'normalized_sha256':sha(normalized(t).encode()),'char_count':len(re.sub(r'\s+','',t)),
             'han_count':len(re.findall(r'[\u4e00-\u9fff]',t)),'lines':len(lines),
             'sentence_count':len(sents),'sentence_lengths':[len(s) for s in sents],
             'hook':flat[:120],'tail':flat[-150:],'bridge_windows':len(blocks),
             'strong_candidate_windows':sum(bool(STRONG.search(x)) for x in blocks),
             'source_strong_candidate':bool(STRONG.search(t)),
             'is_full_sample':any(x.splitlines()[0]==p.name for x in sample_blocks),
             'hook_export_exact':bool(actual_hook and actual_hook.group(1)==flat[:120]),
             'source_line_count':len(raw_lines),'four_words':[] if jieba is None else [w for w in jieba.cut(t) if len(w)==4 and re.match(r'^[\u4e00-\u9fa5]{4}$',w)]}
        # Recompute all exported windows, their filename binding and declared length.
        export_blocks=re.findall(r'```text\n(.*?)\n```',hooks,re.S)
        row['bridge_export_exact']=(export_blocks[1:]==blocks if blocks else export_blocks[1:]==[flat[-150:]])
        row['filename_binding_exact']=hooks.splitlines()[0]==p.name
        declared=re.search(r'\*\*总字数\*\*：([\d,]+)',hooks)
        row['declared_char_count_exact']=bool(declared and int(declared.group(1).replace(',',''))==row['char_count'])
        records.append(row); rows.append(row)
    full_checks=[]
    byname={p.name:p for p in folder.glob('*.txt')}
    for block in sample_blocks:
        fn=block.splitlines()[0]; match=re.search(r'```text\n(.*?)\n```',block,re.S)
        equal=fn in byname and match and match.group(1)==byname[fn].read_text(encoding='utf-8').strip()
        full_checks.append({'filename':fn,'exact':bool(equal)})
    counts=[r['char_count'] for r in records]; lens=[x for r in records for x in r['sentence_lengths']]
    unique={r['normalized_sha256']:r for r in records}
    freq=collections.Counter(w for r in records for w in r['four_words'])
    summary[name]={'files':len(records),'byte_unique':len(set(r['sha256'] for r in records)),
        'normalized_unique':len(unique),'mean_chars':round(statistics.mean(counts),1),'min_chars':min(counts),'max_chars':max(counts),
        'sentence_count':len(lens),'mean_sentence_length':round(statistics.mean(lens),2),
        'segment_quantiles':{'p10':quant(lens,.1),'p50':quant(lens,.5),'p90':quant(lens,.9)},
        'fraction_segments_5_9_chars':round(sum(5<=x<=9 for x in lens)/len(lens),4),
        'four_word_total':sum(freq.values()) if jieba else None,'four_word_top30':freq.most_common(30),
        'full_sample_exports':full_checks,'full_sample_unique':len(set(r['normalized_sha256'] for r in records if r['is_full_sample'])),
        'hook_export_exact':sum(r['hook_export_exact'] for r in records),
        'bridge_export_exact':sum(r['bridge_export_exact'] for r in records),
        'filename_binding_exact':sum(r['filename_binding_exact'] for r in records),
        'declared_char_count_exact':sum(r['declared_char_count_exact'] for r in records),
        'keyword_windows':sum(r['bridge_windows'] for r in records),
        'strong_candidate_windows':sum(r['strong_candidate_windows'] for r in records),
        'files_with_strong_candidates':sum(r['source_strong_candidate'] for r in records),
        'tail_omitted_files':sum(r['bridge_windows']>0 for r in records),
        'text_under_300_ids':[r['id'] for r in records if r['char_count']<300]}

groups=collections.defaultdict(list)
for r in rows: groups[r['normalized_sha256']].append(r['id'])
duplicate_groups=[ids for ids in groups.values() if len(ids)>1]
source_manifest={rel(p):{'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns} for p in list(RAW.glob('*.md'))+list(KB.rglob('*.txt'))}
compact_rows=[{k:v for k,v in r.items() if k not in {'sentence_lengths','four_words'}} for r in rows]
result={'scope':'text-only; keyword candidates are NOT semantic sales labels; no video/performance verification',
        'summary':summary,'total_files':len(rows),'total_normalized_unique':len(groups),
        'duplicate_groups':duplicate_groups,'jieba_available':jieba is not None,
        'source_manifest':source_manifest,'rows':compact_rows}
(OUT/'evidence').mkdir(parents=True,exist_ok=True)
(OUT/'evidence'/'corpus_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
index=['# 来源索引与引用口径','',
       'ID按各目录文件名排序固定。原片例句均指现有TXT转写，不代表已回听音视频。行号为原TXT物理行；原提取包的行号则是去空行后的序号。',
       '343是文件数；独立文本去重数见审核报告。未做原视频指纹映射，不能称独立视频数。','',
       '| ID | 组别 | 字符数（含标点） | A全文样本 | 原TXT |','|---|---|---:|---|---|']
for r in rows:
    label=r['filename'].replace('|','／').replace('[','［').replace(']','］')
    index.append(f"| {r['id']} | {r['track']} | {r['char_count']} | {'是' if r['is_full_sample'] else '否'} | [{label}](<../{r['source']}>) |")
(OUT/'来源索引.md').write_text('\n'.join(index)+'\n',encoding='utf-8')
print(json.dumps({'summary':summary,'total_files':len(rows),'unique':len(groups),'duplicates':duplicate_groups},ensure_ascii=False,indent=2))
