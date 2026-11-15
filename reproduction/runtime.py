"""Verify a lossless functional layout and replay frozen science in isolation."""
from __future__ import annotations

import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'provenance/layout-map.json'
LAYOUT_SHA256 = '273c620f64bd7bee4dc07551e40707f1413235ad40b98be6e6742a94860d18a9'
OID = re.compile(r'[a-f0-9]{40}\Z')
SHA256 = re.compile(r'[a-f0-9]{64}\Z')
MAX_MANIFEST_BYTES = 2 * 1024 * 1024


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_path(name):
    if (not isinstance(name, str) or not name or '\\' in name
            or any(ord(c) < 32 for c in name) or PurePosixPath(name).is_absolute()
            or PurePosixPath(name).as_posix() != name
            or any(part.casefold() in ('.', '..', '.git') for part in name.split('/'))):
        raise ValueError('Noncanonical layout path')
    return name


def unique_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def regular_source(root, name):
    root = Path(root).resolve()
    path = root / safe_path(name)
    if any(p.is_symlink() for p in [path, *path.parents] if p != root.parent):
        raise ValueError('Symlink in a published evidence path')
    if not path.resolve().is_relative_to(root) or not path.is_file():
        raise ValueError('Missing or escaping published evidence path')
    return path


def load_layout(root=ROOT, expected_sha256=LAYOUT_SHA256):
    root = Path(root)
    path = regular_source(root, MANIFEST)
    if path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError('Layout manifest exceeds its size limit')
    raw = path.read_bytes()
    if sha256(raw) != expected_sha256:
        raise ValueError('Layout manifest fingerprint differs')
    value = unique_json(raw)
    if set(value) != {'schema', 'role', 'source_commit_sha1', 'source_tree_sha1', 'source_commit_base64', 'files'} or value['schema'] != 'alien6-functional-layout-v1':
        raise ValueError('Unexpected layout schema')
    if not OID.fullmatch(value['source_commit_sha1']) or not OID.fullmatch(value['source_tree_sha1']):
        raise ValueError('Invalid captured Git identity')
    commit = base64.b64decode(value['source_commit_base64'], validate=True)
    if (len(commit) > 8192 or not commit.startswith(('tree ' + value['source_tree_sha1'] + '\n').encode())
            or b'\nparent ' in commit.split(b'\n\n', 1)[0]
            or hashlib.sha1(f'commit {len(commit)}\0'.encode() + commit).hexdigest() != value['source_commit_sha1']):
        raise ValueError('Captured commit identity differs')
    original, published = set(), set()
    if not isinstance(value['files'], list) or not value['files']:
        raise ValueError('Empty layout inventory')
    for row in value['files']:
        if set(row) != {'original', 'published', 'mode', 'git_blob_sha1', 'sha256', 'bytes'}:
            raise ValueError('Unexpected layout row')
        a, b = safe_path(row['original']), safe_path(row['published'])
        if a in original or b in published:
            raise ValueError('Duplicate layout binding')
        if (row['mode'] not in ('100644', '100755') or not OID.fullmatch(row['git_blob_sha1'])
                or not SHA256.fullmatch(row['sha256']) or not isinstance(row['bytes'], int)
                or isinstance(row['bytes'], bool) or row['bytes'] < 0):
            raise ValueError('Invalid layout fingerprint or mode')
        original.add(a); published.add(b)
    for names in (original, published):
        for name in names:
            if any(parent.as_posix() in names for parent in PurePosixPath(name).parents):
                raise ValueError('Overlapping file and directory layout paths')
    return value


def evidence_bytes(root, row):
    path = regular_source(root, row['published'])
    if path.stat().st_size != row['bytes']:
        raise ValueError('Published evidence size differs: ' + row['published'])
    raw = path.read_bytes()
    blob = hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()
    if sha256(raw) != row['sha256'] or blob != row['git_blob_sha1']:
        raise ValueError('Published evidence fingerprint differs: ' + row['published'])
    return raw


def isolated_environment():
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('GIT_', 'PYTHON'))}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
               GIT_NO_REPLACE_OBJECTS='1', GIT_TERMINAL_PROMPT='0',
               PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1')
    return env


def git(root, env, *args, raw=None):
    p = subprocess.run(['git', *args], cwd=root, env=env, input=raw, capture_output=True)
    if p.returncode:
        raise RuntimeError('Isolated Git operation failed: ' + p.stderr.decode(errors='replace'))
    return p.stdout


@contextmanager
def workspace(root=ROOT, expected_sha256=LAYOUT_SHA256):
    """Rebuild the captured tree in a disposable repo; never touch public .git."""
    layout = load_layout(root, expected_sha256)
    with tempfile.TemporaryDirectory(prefix='alien6-rag-replay-') as directory:
        target = Path(directory)
        for row in layout['files']:
            raw = evidence_bytes(root, row)
            path = target / row['original']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            path.chmod(0o755 if row['mode'] == '100755' else 0o644)
        env = isolated_environment()
        git(target, env, 'init', '--quiet', '--object-format=sha1', '--initial-branch=replay')
        names = ''.join(row['original'] + '\n' for row in layout['files']).encode()
        observed = git(target, env, 'hash-object', '-w', '--no-filters', '--stdin-paths', raw=names).decode().splitlines()
        if observed != [row['git_blob_sha1'] for row in layout['files']]:
            raise ValueError('Materialized Git blob identities differ')
        entries = b''.join(f"{row['mode']} {row['git_blob_sha1']}\t{row['original']}\0".encode() for row in layout['files'])
        git(target, env, 'update-index', '-z', '--index-info', raw=entries)
        if git(target, env, 'write-tree').decode().strip() != layout['source_tree_sha1']:
            raise ValueError('Materialized Git tree differs; missing or extra binding')
        commit = base64.b64decode(layout['source_commit_base64'], validate=True)
        actual = git(target, env, 'hash-object', '-t', 'commit', '-w', '--stdin', raw=commit).decode().strip()
        if actual != layout['source_commit_sha1']:
            raise ValueError('Materialized Git commit differs')
        git(target, env, 'update-ref', '--no-deref', 'HEAD', actual)
        git(target, env, 'fsck', '--strict', '--no-dangling')
        yield target, env, layout


def check(root=ROOT):
    with workspace(root) as (target, env, layout):
        subprocess.run([sys.executable, 'validation/replay_registered.py', '--check-capsule'], cwd=target, env=env, check=True)
        return {'status': 'verified', 'relocated_files': len(layout['files']),
                'bytes': sum(row['bytes'] for row in layout['files']),
                'source_tree_sha1': layout['source_tree_sha1'],
                'public_git_objects_written': 0, 'model_calls': 0}


def prepare_inputs(target, env, root, inputs=None, offline=False):
    """Use only two pinned public inputs; the optional supplied cache is read-only."""
    sources = json.loads((target / 'sources.json').read_text())
    cache = Path(inputs) if inputs is not None else Path(root) / '.cache/inputs'
    data = target / 'data'; data.mkdir(exist_ok=True)
    missing = []
    for key, name in [('dataset', 'hotpot-validation.parquet'), ('tokenizer', 'qwen-tokenizer.json')]:
        path = cache / name
        if path.is_file() and not path.is_symlink() and sha256(path.read_bytes()) == sources[key]['sha256']:
            shutil.copyfile(path, data / name)
        else:
            missing.append(name)
    if missing and offline:
        raise ValueError('Offline mode requires the pinned input cache: ' + ', '.join(missing))
    subprocess.run([sys.executable, 'prepare_data.py'], cwd=target, env=env, check=True)
    if inputs is None:
        cache.mkdir(parents=True, exist_ok=True)
        for name in ('hotpot-validation.parquet', 'qwen-tokenizer.json'):
            destination = cache / name
            if destination.is_symlink():
                raise ValueError('Symlink in the input cache')
            with tempfile.NamedTemporaryFile(dir=cache, prefix='.input-', delete=False) as f:
                temporary = Path(f.name)
                try:
                    f.write((data / name).read_bytes()); f.flush()
                    os.replace(temporary, destination)
                finally:
                    temporary.unlink(missing_ok=True)


def run_science(action, root=ROOT, inputs=None, offline=False, output=None):
    started = time.monotonic()
    if output is None:
        output = Path(root) / '.cache/reproduction' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = Path(output).resolve()
    public = Path(root).resolve()
    # Reports may use the ignored cache or an external directory, never overwrite scientific sources.
    if output.is_relative_to(public) and not output.is_relative_to(public / '.cache'):
        raise ValueError('Reports inside the repository must use .cache')
    output.mkdir(parents=True, exist_ok=False)
    stages = []
    def execute(label, command, target, env, report=None):
        print(label, flush=True)
        stage = {'name': label, 'model_calls': 0}
        stages.append(stage)
        if report:
            with (output / report).open('wb') as stream:
                p = subprocess.run([sys.executable, *command], cwd=target, env=env, stdout=stream)
        else:
            p = subprocess.run([sys.executable, *command], cwd=target, env=env)
        stage['exit_code'] = p.returncode
        if p.returncode:
            raise RuntimeError('Offline verification stage failed: ' + label)
    status = 'failed'
    try:
        with workspace(root) as (target, env, layout):
            prepare_inputs(target, env, root, inputs, offline)
            for label, command in [
                ('Restore budget evidence', ['-m', 'v2.archive', 'restore']),
                ('Restore excluded pilot evidence', ['-m', 'v3.archive', 'restore', '--manifest', 'v3/amendments/01/retained-pilot-archive.json']),
                ('Restore selection evidence', ['-m', 'v3.archive', 'restore']),
                ('Test frozen scientific controls', ['-m', 'unittest', 'discover', '-p', 'test_*.py', '-v'])]:
                execute(label, command, target, env)
            if action == 'verify':
                for label, command, report in [
                    ('Replay the budget diagnostic', ['-m', 'v2.verify', '--output', 'v2/verification.json'], None),
                    ('Audit budget records and annotations', ['-m', 'v2.audit', '--check'], None),
                    ('Audit original exploratory records', ['validation/audit_records.py'], 'exploratory-records.json'),
                    ('Replay exploratory sensitivities', ['extensions/deeper_analysis.py', '--check'], None),
                    ('Verify the article claim ledger', ['-m', 'v2.article_evidence', '--check'], None),
                    ('Replay the registered selection comparison', ['validation/replay_registered.py', '--require-collected'], 'selection.json'),
                    ('Verify immutable evidence inventories', ['scripts/verify_evidence.py'], None)]:
                    execute(label, command, target, env, report)
                shutil.copyfile(target / 'v2/verification.json', output / 'budget.json')
            status = 'passed'
    finally:
        summary = {'status': status, 'action': action, 'model_calls': 0,
                   'layout_sha256': LAYOUT_SHA256, 'elapsed_seconds': round(time.monotonic() - started, 3),
                   'public_git_objects_written': 0, 'stages': stages}
        (output / 'verification.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({**summary, 'reports': str(output)}, indent=2))
    return summary
