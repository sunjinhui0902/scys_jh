"""Register the text-only research without rewriting prior video evidence.

Only append five Artifact Tool-authored rows to the existing summary sheet.
Keep all other ZIP entries byte-identical (round-tripping the whole workbook
would rewrite unrelated native parts). Existing source statuses stay intact.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json, re, hashlib, zipfile, xml.etree.ElementTree as ET, argparse

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'codex_analysis_draft'
BATCH='text_corpus_reverse_2026-10-23'
NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
N={'s':NS}
ET.register_namespace('',NS)

def sha(b): return hashlib.sha256(b).hexdigest()
def append_once(p, marker, text):
    s=p.read_text(encoding='utf-8')
    if marker not in s: p.write_text(s.rstrip()+'\n\n'+text.strip()+'\n',encoding='utf-8')

def main(candidate):
    state_path=ROOT/'竞品视频分析_2026-10-15/manifest/collaboration_state.json'
    state=json.loads(state_path.read_text(encoding='utf8'))
    if state.get('text_corpus_research',{}).get('batch_id')==BATCH:
        print('Already registered; no duplicate append.');return
    p=ROOT/'竞品视频分析_2026-10-15/阅见生活_竞品视频分析_终版.xlsx'
    before=p.read_bytes(); before_sha=sha(before)
    assert before_sha==state['workbook_sha256'],'Workbook changed; stop to preserve concurrent work'
    with zipfile.ZipFile(candidate) as z:
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            shared=[''.join(si.itertext()) for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',N)]
        t=ET.fromstring(z.read('xl/worksheets/sheet7.xml'))
        rows=t.findall('s:sheetData/s:row',N)
        added=[r for r in rows if 40<=int(r.get('r'))<=44]
        assert len(added)==5
        for r in added:
            r.attrib.clear();r.set('r',str(40+added.index(r)));r.set('ht','48');r.set('customHeight','1')
            assert len(list(r))==3
            for c in r:
                typ=c.get('t');v=c.find('s:v',N)
                if typ=='s': val=shared[int(v.text)]
                elif typ=='inlineStr': val=''.join(c.find('s:is',N).itertext())
                elif typ=='str' and v is not None: val=v.text or ''
                else: raise ValueError('Expected authored text cell')
                cell_ref=c.get('r'); c.clear();c.set('r',cell_ref);c.set('s','4');c.set('t','inlineStr')
                ET.SubElement(ET.SubElement(c,f'{{{NS}}}is'),f'{{{NS}}}t').text=val
        fragment=''.join(ET.tostring(r,encoding='unicode') for r in added)
    with zipfile.ZipFile(p) as old:
        names=old.namelist(); members={i.filename:old.read(i.filename) for i in old.infolist()}; infos=old.infolist()
    s=members['xl/worksheets/sheet7.xml'].decode('utf8')
    assert 'r="A40"' not in s and 'ref="A2:C39"' in s
    modified=s.replace('</sheetData>',fragment+'</sheetData>').replace('ref="A2:C39"','ref="A2:C44"',1).encode('utf8')
    assert modified!=members['xl/worksheets/sheet7.xml']
    # Original worksheet rows remain identical as raw XML; no reserialization.
    original_prefix=s.split('</sheetData>')[0].replace('ref="A2:C39"','ref="A2:C44"',1)
    assert modified.decode().startswith(original_prefix)
    tmp=p.with_suffix('.corpus-register.tmp.xlsx')
    with zipfile.ZipFile(tmp,'w') as z:
        for i in infos:z.writestr(i, modified if i.filename=='xl/worksheets/sheet7.xml' else members[i.filename])
    with zipfile.ZipFile(tmp) as z:
        assert z.testzip() is None and z.namelist()==names
        assert all(z.read(k)==v for k,v in members.items() if k!='xl/worksheets/sheet7.xml')
        root=ET.fromstring(z.read('xl/worksheets/sheet7.xml'));assert root.find('s:dimension',N).get('ref')=='A2:C44'
        new_rows=root.findall('s:sheetData/s:row',N)
        old_rows=ET.fromstring(members['xl/worksheets/sheet7.xml']).findall('s:sheetData/s:row',N)
        assert all(ET.tostring(a)==ET.tostring(b) for a,b in zip(old_rows,new_rows))
    # A recoverable local copy, never shipped as a second workbook deliverable.
    backup=ROOT/'.local/codex_corpus_20261023/original.xlsx';backup.write_bytes(before)
    tmp.replace(p); after_sha=sha(p.read_bytes())
    record={'batch_id':BATCH,'at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
            'kind':'independent_text_corpus_pattern_research','status':'RESEARCH_DELIVERED',
            'source_txt_files':343,'exact_unique_texts':342,'full_texts_read':20,'pacing_examples':12,
            'track_reports':4,'common_libraries':1,'hook_templates':24,'bridge_templates':40,
            'video_semantic_verified_added':0,'source_video_added':0,
            'input_scope':'raw_extracted_for_codex plus original TXT; no video/SKU/effect certification',
            'entry':'codex_analysis_draft/README.md','audit':'codex_analysis_draft/00_Antigravity预处理审核与使用说明.md',
            'workbook_sha256_before':before_sha,'workbook_sha256_after':after_sha,
            'workbook_scope':'07_口径与运行摘要 A40:C44 appended; other entries/rows identical',
            'render_note':'Artifact render emitted PNG and export before process exited 1; saved-file ZIP/XML checks used independently; no native Excel UI check'}
    state['text_corpus_research']=record
    state['workbook_sha256']=after_sha
    state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    journal=ROOT/'竞品视频分析_2026-10-15/manifest/analysis_batches.jsonl'
    with journal.open('a',encoding='utf8') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
    note='''## 2026-10-23｜343份独立文本池：第二棒模式识别

批次 `text_corpus_reverse_2026-10-23`。已交付[四组报告与通用库](../codex_analysis_draft/README.md)，并完成[Antigravity预处理审核](../codex_analysis_draft/00_Antigravity预处理审核与使用说明.md)。343份机器核对、342种精确去重文本、20份全文细读、12篇段落计数；4组共24种钩子／40条转折模板。原9份提取MD及343原TXT保持原指纹。

本轮是独立文本池研究，不把343文件加到旧416来源／401SHA内容，不提升旧原视频全文验收1条、36深拆或旧A83／25状态。关键词命中不能当销售语义；343条原视频没有全量回听，营销效果未验证。同一7-Sheet总表仅在摘要A40:C44追加本轮口径；原行和其他6张表的包内内容保持。

下一次A预处理建议：始终保留结尾、去重后按体裁抽样、检索候选与真实桥分栏、根目录相对路径；本轮未修改A脚本或派新任务。文案可有情感修辞，具体事实、商品功能与图片实物结构另核。'''
    append_once(ROOT/'docs/竞品分析协作总控.md',BATCH,note)
    report_note=note.replace('(../codex_analysis_draft/','(../../codex_analysis_draft/')
    append_once(ROOT/'竞品视频分析_2026-10-15/reports/最终验收报告.md',BATCH,report_note)
    log_note=note
    append_once(ROOT/'05_爆款知识库与复盘/06_竞品分析更新日志.md',BATCH,log_note)
    entry=ROOT/'05_爆款知识库与复盘/07_四赛道文案逆向入口.md'
    if not entry.exists():entry.write_text('# 四组文案逆向与情感写作入口\n\n'+note+'\n',encoding='utf8')
    library_note='''## 2026-10-23补充：4组独立TXT池研究

新增[四组文案逆向与情感写作报告](../../codex_analysis_draft/README.md)（批次 `text_corpus_reverse_2026-10-23`）：4份专项＋1份通用库，343文件机器核对、20份全文细读，原视频验收口径不增加。具体来源与去重见新索引；不要混入本页历史317／401视频数。'''
    append_once(ROOT/'竞品视频分析_2026-10-15/content_library/开始使用.md',BATCH,library_note)
    (OUT/'evidence/registration.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(record,ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);a=p.parse_args();main(Path(a.candidate))
