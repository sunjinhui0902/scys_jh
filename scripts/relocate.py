"""Generate ignored local copies of historical manifests with this computer's paths."""
from pathlib import Path
import argparse
import json
import shutil

ROOT=Path(__file__).resolve().parents[1]
ANALYSIS=ROOT/'竞品视频分析_2026-10-15'


def rewrite(value):
    if isinstance(value,dict):return {k:rewrite(v) for k,v in value.items()}
    if isinstance(value,list):return [rewrite(v) for v in value]
    if isinstance(value,str):
        # Handle both legacy junction paths and canonical original paths.
        for old in ['D:\\fuye\\tools\\wx_channel\\downloads','D:/fuye/tools/wx_channel/downloads']:
            value=value.replace(old,str(ROOT/'00_对标与采集工具/wx_channel/downloads'))
        value=value.replace('D:\\fuye',str(ROOT)).replace('D:/fuye',ROOT.as_posix())
    return value


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--activate',action='store_true',help='Use local manifests; original Git files are backed up under .local before replacement.');a=ap.parse_args()
    target=ROOT/'.local/relocated'
    count=0
    for folder in ['manifest','state','frames','handoff']:
        for p in (ANALYSIS/folder).rglob('*'):
            if not p.is_file() or p.suffix not in ['.json','.jsonl']:continue
            text=p.read_text(encoding='utf-8-sig')
            try:
                if p.suffix=='.json':out=json.dumps(rewrite(json.loads(text)),ensure_ascii=False,indent=2)+'\n'
                else:out='\n'.join(json.dumps(rewrite(json.loads(s)),ensure_ascii=False) for s in text.splitlines() if s.strip())+'\n'
            except ValueError:continue
            dest=target/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(out,encoding='utf-8');count+=1
            if a.activate and out!=text:
                backup=ROOT/'.local/before-relocation'/p.relative_to(ROOT)
                if not backup.exists():backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,backup)
                p.write_text(out,encoding='utf-8')
    print(f'Local path copies: {count}; {target}')


if __name__=='__main__':main()
