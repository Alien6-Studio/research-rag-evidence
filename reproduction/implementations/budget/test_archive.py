import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from v2 import archive


class EvidenceArchiveTests(unittest.TestCase):
    def test_lossless_roundtrip_and_checksum_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "v2/runs/fixture/answers.jsonl"
            path.parent.mkdir(parents=True)
            content = (json.dumps({"text": "retained evidence " * 100}) + "\n").encode() * 1000
            path.write_bytes(content)
            with mock.patch.object(archive, "ROOT", root), mock.patch.object(archive, "MANIFEST", root / "v2/evidence-manifest.json"):
                archive.store()
                self.assertEqual(gzip.decompress(path.with_suffix(".jsonl.gz").read_bytes()), content)
                path.unlink()
                archive.restore(verify_only=True)
                self.assertFalse(path.exists())
                archive.restore()
                self.assertEqual(path.read_bytes(), content)
                path.write_bytes(b"changed")
                with self.assertRaises(ValueError): archive.restore()

    def test_archive_paths_cannot_escape_the_checkout(self):
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(archive, "ROOT", Path(temp)):
                with self.assertRaises(ValueError): archive.safe_path("../other-file")


if __name__ == "__main__":
    unittest.main()
