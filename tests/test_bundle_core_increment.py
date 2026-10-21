"""Verify bounded image increments and compatibility with existing restore data."""
import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SPEC = importlib.util.spec_from_file_location('bundle', Path(__file__).resolve().parents[1] / 'scripts/bundle.py')
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)


class CoreIncrementTests(unittest.TestCase):
    def test_multiple_prefixes_deduplicate_and_restore(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root / 'config/bundle-manifest.json'
            manifest.parent.mkdir()
            initial = {'repository': bundle.REPO, 'tag': 'previous', 'files': [], 'blobs': {}, 'archives': []}
            manifest.write_text(json.dumps(initial), encoding='utf-8')
            for name in ['project1', 'project2']:
                folder = root / name
                folder.mkdir()
                (folder / 'shot_01.png').write_bytes(b'known-image-content')
                (folder / 'ignored.mp3').write_bytes(b'not-included')
            args = argparse.Namespace(tag='new-test', upload=False, incremental_prefix=None,
                                      core_prefix=['project1', 'project2', 'project1'])
            with patch.object(bundle, 'ROOT', root), patch.object(bundle, 'MANIFEST', manifest):
                bundle.pack(args)
                result = json.loads(manifest.read_text(encoding='utf-8'))
                self.assertEqual(len(result['files']), 2)
                self.assertEqual(len(result['blobs']), 1)
                archive = root / '.bundle-cache/new-test' / result['archives'][0]['name']
                with zipfile.ZipFile(archive) as z:
                    self.assertIsNone(z.testzip())
                target = root / 'restored'
                bundle.restore(argparse.Namespace(group=['core'], target=str(target), cache=None, offline=True))
                for name in ['project1', 'project2']:
                    self.assertEqual((target / name / 'shot_01.png').read_bytes(), b'known-image-content')
                    self.assertFalse((target / name / 'ignored.mp3').exists())
                (root / 'project1/shot_01.png').write_bytes(b'changed')
                args.tag = 'next-test'
                with self.assertRaisesRegex(ValueError, 'frozen'):
                    bundle.pack(args)


if __name__ == '__main__':
    unittest.main()
