"""Verify delivery scope, source integrity, citations and workbook preservation."""
from pathlib import Path
import json, re, hashlib, zipfile, subprocess, xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'codex_analysis_draft'
def sha(b):return hashlib.sha256(b).hexdigest()
audit=json.loads((OUT/'evidence/corpus_audit.json').read_text(encoding='utf8'))
result={'source_integrity':{},'reports':{},'statistics':{},'workbook':{}}
for name,v in audit['source_manifest'].items():
    p=ROOT/name
    assert sha(p.read_bytes())==v['sha256'] and p.stat().st_mtime_ns==v['mtime_ns'],name
result['source_integrity']={'unchanged_files':len(audit['source_manifest']),'status':'PASS'}
stats=(ROOT/'raw_extracted_for_codex/00_stats.md').read_text(encoding='utf8')
for i,(name,s) in enumerate(audit['summary'].items(),1):
    block=re.split(r'^### 2\.'+str(i)+r' .*?\n',stats,flags=re.M)[1].split('\n### ')[0]
    actual={int(rank):(w.strip(),int(n)) for rank,w,n in re.findall(r'\*\*#(\d+)\*\* \| ([^|]+) \| (\d+)',block)}
    expected={j+1:tuple(v) for j,v in enumerate(s['four_word_top30'])}
    assert actual==expected,name
    assert all(s[x]==s['files'] for x in ['hook_export_exact','bridge_export_exact','filename_binding_exact','declared_char_count_exact'])
    assert all(f['exact'] for f in s['full_sample_exports'])
    result['statistics'][name]={'files':s['files'],'mechanical_exports':'PASS','top30':'PASS'}
for p in OUT.glob('*.md'):
    t=p.read_text(encoding='utf8');assert t.startswith('# ')
    hook=len(re.findall(r'\| [DJSY]-H\d+',t));bridge=len(re.findall(r'\| [DJSY]-B\d+',t))
    if re.match('0[1-4]_',p.name):assert hook>=5 and bridge>=10 and all(k in t for k in ['Pacing','中老年','SOP'])
    # Angle-wrapped file targets also support #, parentheses and whitespace in filenames.
    for dest in re.findall(r'\]\(<([^>]+)>\)',t):
        d=re.sub(r':\d+$','',dest)
        target=Path(d) if re.match(r'^[A-Z]:/',d) else p.parent/d
        assert target.exists(),(p.name,d)
    for dest in re.findall(r'\]\(([^<>()\s]+)\)',t):
        if not re.match(r'\w+://',dest):assert (p.parent/dest).exists(),(p.name,dest)
    assert '{{' not in t and 'cite: 1' not in t
    result['reports'][p.name]={'status':'PASS','hooks':hook,'bridges':bridge}
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
p=ROOT/'竞品视频分析_2026-10-15/阅见生活_竞品视频分析_终版.xlsx'
baseline=ROOT/'.local/codex_corpus_20261023/original.xlsx'
with zipfile.ZipFile(baseline) as a,zipfile.ZipFile(p) as b:
    assert b.testzip() is None and a.namelist()==b.namelist()
    modified=[n for n in a.namelist() if a.read(n)!=b.read(n)]
    assert modified==['xl/worksheets/sheet7.xml']
    ta,tb=[ET.fromstring(z.read(modified[0])) for z in [a,b]]
    ra=ta.findall('s:sheetData/s:row',ns);rb=tb.findall('s:sheetData/s:row',ns)
    assert len(rb)==len(ra)+5 and all(ET.tostring(x)==ET.tostring(y) for x,y in zip(ra,rb))
    for r in rb[-5:]:assert len(list(r))==3 and all(c.find('s:is/s:t',ns).text for c in r)
    # All other sheets are byte-identical and original summary cells above are exact.
    result['workbook']={'status':'PASS','sheets':7,'changed_part':modified,'old_summary_rows_unchanged':len(ra),'added_cells':15,'sha256':sha(p.read_bytes()),'visual_preview':'normal-zoom final.png inspected; no clipping','renderer_exit':1,'native_excel_ui_tested':False}
state_rel='竞品视频分析_2026-10-15/manifest/collaboration_state.json'
old=json.loads(subprocess.check_output(['git','show','HEAD:'+state_rel],cwd=ROOT))
now=json.loads((ROOT/state_rel).read_text(encoding='utf8'))
for key in old:
    if key!='workbook_sha256':assert now[key]==old[key],key
assert now['workbook_sha256']==sha(p.read_bytes())
result['historical_state_values_unchanged']=True
result['marketing_effects_verified']=False
(OUT/'evidence/verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
print(json.dumps({'sources':result['source_integrity'],'reports':len(result['reports']),'workbook':result['workbook'],'historical_state_values_unchanged':True},ensure_ascii=False,indent=2))
