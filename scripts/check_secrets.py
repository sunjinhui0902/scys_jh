"""Scan staged text without printing secret values."""
import argparse
import io
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
RULES={
    'GitHub credential': rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})',
    'OpenAI credential': rb'\bsk-(?:(?:proj|svcacct)-[A-Za-z0-9_-]{24,}|[A-Za-z0-9]{32,})\b',
    'private key': rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'populated secret field': rb'(?im)^[ \t]*["\x27]?(?:api_key|access_token|refresh_token|client_secret|cloud_secret|cookie|cookie_tiktok)["\x27]?[ \t]*[:=][ \t]*["\x27]?[^\s"\x27#}\],][^\r\n]{10,}',
}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--staged',action='store_true');a=ap.parse_args()
    cmd=['git','diff','--cached','--name-only','--diff-filter=ACMR','-z'] if a.staged else ['git','ls-files','-z']
    paths=[p.decode('utf-8') for p in subprocess.check_output(cmd,cwd=ROOT).split(b'\0') if p];bad=[];count=0
    staged={}
    if a.staged and paths:
        rows=subprocess.check_output(['git','ls-files','--stage','-z'],cwd=ROOT).split(b'\0')
        objects={row.split(b'\t',1)[1].decode('utf-8'):row.split(b'\t',1)[0].split()[1] for row in rows if row}
        refs=b'\n'.join(objects[p] for p in paths)+b'\n'
        stream=io.BytesIO(subprocess.check_output(['git','cat-file','--batch'],input=refs,cwd=ROOT))
        for name in paths:
            header=stream.readline().split();size=int(header[2]);staged[name]=stream.read(size);stream.read(1)
    for item in paths:
        name=item
        parts=Path(name).parts
        if parts and parts[0]=='00_对标与采集工具' and ('downloads' in parts or '视频号下载成果' in parts):
            bad.append((name,'raw collection directory must remain local'))
        data=staged[name] if a.staged else (ROOT/name).read_bytes()
        if b'\0' in data[:8192]:continue
        count+=1
        for title,pattern in RULES.items():
            if re.search(pattern,data):bad.append((name,title))
    print(f'Scanned {count} text files; findings: {len(bad)}')
    for name,title in bad:print(f'{name}: {title}')
    return int(bool(bad))


if __name__=='__main__':sys.exit(main())
