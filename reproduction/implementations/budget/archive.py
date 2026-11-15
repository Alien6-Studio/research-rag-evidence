"""Lossless, checksummed storage of large JSON evidence in the repository."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "v2/evidence-manifest.json"


def sha(content):
    return hashlib.sha256(content).hexdigest()


def safe_path(name):
    path = (ROOT / name).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError("Evidence path escapes the repository")
    return path


def store():
    entries = []
    candidates = [p for p in (ROOT / "v2/runs").rglob("*") if p.is_file() and p.suffix in (".json", ".jsonl")]
    candidates += [p for p in (ROOT / "v2/runs").rglob("*.json.gz") if "embedding-traces" in p.parts]
    for path in sorted(candidates):
        raw = path.read_bytes()
        compressed = len(raw) > 1_000_000 and path.suffix != ".gz"
        archived = path.with_name(path.name + ".gz") if compressed else path
        if compressed:
            encoded = gzip.compress(raw, mtime=0)
            if archived.exists() and archived.read_bytes() != encoded:
                raise ValueError(f"Refusing to overwrite different archived evidence: {archived}")
            archived.write_bytes(encoded)
        entries.append({"path": str(path.relative_to(ROOT)), "sha256": sha(raw), "bytes": len(raw),
                        "archive": str(archived.relative_to(ROOT)), "archive_sha256": sha(archived.read_bytes()),
                        "compression": "gzip" if compressed else None})
    manifest = {"format": "Lossless raw evidence; no metric or response is changed by compression.", "files": entries}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Archived {len(entries)} evidence files with exact byte hashes.")


def restore(verify_only=False):
    manifest = json.loads(MANIFEST.read_text())
    for item in manifest["files"]:
        archived = safe_path(item["archive"])
        content = archived.read_bytes()
        if sha(content) != item["archive_sha256"]:
            raise ValueError(f"Archive checksum mismatch: {item['archive']}")
        raw = gzip.decompress(content) if item["compression"] == "gzip" else content
        if sha(raw) != item["sha256"] or len(raw) != item["bytes"]:
            raise ValueError(f"Raw evidence checksum mismatch: {item['path']}")
        target = safe_path(item["path"])
        if target.exists() and sha(target.read_bytes()) != item["sha256"]:
            raise ValueError(f"Existing raw evidence differs: {item['path']}")
        if not verify_only and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
    print(f"Verified {len(manifest['files'])} archived evidence files.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["store", "restore", "verify"])
    command = parser.parse_args().command
    if command == "store": store()
    else: restore(verify_only=command == "verify")
