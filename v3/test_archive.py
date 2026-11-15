"""Archive corruption, conflicting originals and path safety controls."""
import json
from pathlib import Path
import tempfile
import unittest

from v3.archive import pack, restore, safe


class ArchiveControls(unittest.TestCase):
    def test_round_trip_refuses_changed_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / 'v3/runs/pilot-controlled/answers.jsonl'
            path.parent.mkdir(parents=True); raw = b'{"example":"test fixture"}\n'
            path.write_bytes(raw); pack(root)
            path.unlink(); self.assertEqual(restore(root)['restored_files'], 1)
            self.assertEqual(path.read_bytes(), raw)
            path.write_bytes(b'changed')
            with self.assertRaises(ValueError): restore(root)

    def test_corrupt_bytes_and_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / 'v3/runs/pilot-controlled/jobs.json'
            path.parent.mkdir(parents=True); path.write_text('[]'); pack(root)
            path.with_name('jobs.json.gz').write_bytes(b'corrupted')
            with self.assertRaises(ValueError): restore(root)
            for name in ('/tmp/escape', 'v3/runs/../../escape', 'v3/other.json'):
                with self.assertRaises(ValueError): safe(root, name)

    def test_manifest_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / 'v3/runs/pilot-controlled/jobs.json'
            path.parent.mkdir(parents=True); path.write_text('[]'); pack(root)
            with self.assertRaises(FileExistsError): pack(root)


if __name__ == '__main__': unittest.main()
