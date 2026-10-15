"""Read-only source/database-metadata and immutable A delivery verification."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from integrate_competitor_supplement import R, atomic, fingerprint, read, stamp


def stream_sha(p):
    import hashlib
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


started = time.monotonic()
rows = [json.loads(s) for s in (R / 'manifest/manifest.jsonl').read_text(encoding='utf-8').splitlines()]
ok = 0
for i, row in enumerate(rows, 1):
    p = Path(row['source_path'])
    s = p.stat()
    assert stream_sha(p) == row['sha256'] and s.st_size == row['size_bytes'] and s.st_mtime_ns == row['mtime_ns'], row['video_id']
    ok += 1
    if i % 75 == 0:
        print(f'Checked sources {i}/{len(rows)}', flush=True)
source_root = Path(rows[0]['source_path']).parent.parent
disk = {str(p) for p in source_root.rglob('*') if p.is_file() and p.suffix.lower() in {'.mp4', '.mov', '.mkv', '.m4v', '.avi', '.webm'}}
assert disk == {r['source_path'] for r in rows}
old_a = read(R / 'manifest/phase4_input_snapshot.json')['files']
for ref in old_a:
    p = Path(ref['source'])
    assert stream_sha(p) == ref['sha256'] and p.stat().st_mtime_ns == ref['mtime_ns']
new_a = read(R / 'manifest/supplement_01_import_summary.json')['A_source_files']
assert all(fingerprint(ref['path']) == ref for ref in new_a)
db_old = read(R / 'manifest/phase2_source_snapshot.json')['database_files_metadata_only']
db_now = {p.name: {'size_bytes': p.stat().st_size, 'mtime_ns': p.stat().st_mtime_ns}
          for p in source_root.glob('records.db*') if p.is_file()}
db_matches = db_old == db_now
chunks = read(R / 'manifest/resume_test_before.json')['completed_chunks']
assert all(stream_sha(ref['path']) == ref['sha256'] and Path(ref['path']).stat().st_mtime_ns == ref['mtime_ns'] for ref in chunks)
result = {'at': stamp(), 'status': 'PASS' if db_matches else 'PARTIAL', 'sources_sha_size_mtime_unchanged': ok, 'directory_membership_matches': True,
          'original_A_unchanged': len(old_a), 'supplement_A_unchanged': len(new_a),
          'database_opened': False, 'database_metadata_unchanged': db_matches,
          'database_metadata_baseline': db_old, 'database_metadata_current': db_now,
          'database_note': '本轮未打开或改写数据库；与Phase2历史元数据相比有变化时原因未知，不能据此宣称历史数据库不变',
          'old_ASR_chunks_unchanged': len(chunks),
          'elapsed_seconds': round(time.monotonic() - started, 3)}
atomic(R / 'manifest/supplement_01_integrity.json', result)
print(json.dumps(result, ensure_ascii=True))
