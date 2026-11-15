"""Lossless publication and exact offline restoration of V3 observations."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath

from v3.design import ROOT, read, utc, write_new


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def safe(root, name):
    rel = PurePosixPath(name)
    if rel.is_absolute() or '..' in rel.parts or rel.as_posix() != name or not name.startswith('v3/runs/'):
        raise ValueError('Noncanonical V3 observation path')
    target = Path(root) / name
    if not target.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError('Archive escapes the repository')
    if any(p.is_symlink() for p in (target, *target.parents) if p.is_relative_to(root)):
        raise ValueError('Archive symlinks are not permitted')
    return target


def pack(root=ROOT):
    root = Path(root); base = root / 'v3'
    target = base / 'archive-manifest.json'
    if target.exists():
        raise FileExistsError('The published V3 archive manifest is immutable')
    entries = []
    for path in sorted((base / 'runs').rglob('*')):
        if not path.is_file() or path.suffix not in ('.json', '.jsonl'):
            continue
        raw = path.read_bytes(); encoded = gzip.compress(raw, mtime=0)
        stored = path.with_name(path.name + '.gz')
        with stored.open('xb') as handle: handle.write(encoded)
        entries.append({'source_path': path.relative_to(root).as_posix(),
                        'path': stored.relative_to(root).as_posix(), 'encoding': 'gzip',
                        'bytes': len(encoded), 'sha256': sha(encoded),
                        'decoded_bytes': len(raw), 'decoded_sha256': sha(raw)})
    for path in sorted((base / 'runs/embedding-traces').glob('batch-*.json.gz')):
        encoded = path.read_bytes(); raw = gzip.decompress(encoded)
        entries.append({'source_path': path.relative_to(root).as_posix(),
                        'path': path.relative_to(root).as_posix(), 'encoding': 'preserved-gzip-packet',
                        'bytes': len(encoded), 'sha256': sha(encoded),
                        'decoded_bytes': len(raw), 'decoded_sha256': sha(raw)})
    if not entries:
        raise ValueError('No V3 observations to archive')
    write_new(target, {'schema': 'alien6-rag-v3-lossless-archive-v1', 'published_utc': utc(),
                      'files': sorted(entries, key=lambda x: x['source_path']),
                      'scope': 'Original observation bytes and timestamps retained; gzip header time is zero. No model calls are made on replay.'})
    return {'files': len(entries), 'compressed_bytes': sum(x['bytes'] for x in entries),
            'decoded_bytes': sum(x['decoded_bytes'] for x in entries)}


def restore(root=ROOT):
    root = Path(root); manifest = read(root / 'v3/archive-manifest.json')
    if manifest['schema'] != 'alien6-rag-v3-lossless-archive-v1':
        raise ValueError('Unknown V3 archive schema')
    paths = set(); restored = 0
    for row in manifest['files']:
        if row['source_path'] in paths:
            raise ValueError('Duplicate V3 archive source')
        paths.add(row['source_path'])
        stored = safe(root, row['path']); target = safe(root, row['source_path'])
        encoded = stored.read_bytes()
        if len(encoded) != row['bytes'] or sha(encoded) != row['sha256'] or encoded[4:8] != b'\0' * 4:
            raise ValueError('Compressed V3 evidence changed')
        raw = gzip.decompress(encoded)
        if len(raw) != row['decoded_bytes'] or sha(raw) != row['decoded_sha256']:
            raise ValueError('Decoded V3 evidence changed')
        if row['encoding'] == 'preserved-gzip-packet':
            if stored != target:
                raise ValueError('Preserved packet identity differs')
        elif row['encoding'] == 'gzip':
            if target.exists():
                if target.read_bytes() != raw:
                    raise ValueError('Existing observation differs; never overwrite it')
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as output: output.write(raw)
                restored += 1
        else:
            raise ValueError('Unknown V3 archive encoding')
    return {'verified_files': len(paths), 'restored_files': restored, 'model_calls': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['pack', 'restore'])
    args = parser.parse_args()
    print(json.dumps(pack() if args.stage == 'pack' else restore(), indent=2))
