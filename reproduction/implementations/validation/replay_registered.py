"""Replay frozen registrations using a temporary, deliberately partial Git ODB.

The capsule proves registered file bytes under the two original commit IDs. It
does not restore their history, create refs, or independently attest publication
times. The unchanged public receipts retain their original evidentiary scope.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
from contextlib import contextmanager
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "provenance/registration-objects-manifest.json"
CAPSULE = "provenance/registration-objects.json.gz"
SCHEMA = "alien6-registration-git-proof-v1"
MAX_BYTES = 16 * 1024 * 1024
OID = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
ANCHORS = (
    {"registration_path": "v3/registration.json",
     "registration_sha256": "d044efd69556cd9c40c10d04e62e358660f36d4f1172c554404fd25bc1562d62",
     "receipt_path": "v3/public-registration.json",
     "receipt_sha256": "d610f697f57441b1e9bde45fc599f1431120d5c8ab23412a90b2471be1d8a15d",
     "commit": "90fecf74f2cbfeaf52618688681c366430604042"},
    {"registration_path": "v3/registration-amendment-01.json",
     "registration_sha256": "0b868b6460492e8f0784b94ea9a69dc389cf0f96a7aedd2414267b92bac896db",
     "receipt_path": "v3/public-registration-amendment-01.json",
     "receipt_sha256": "adcd805ab3c49a0dd4eb8d221dc5daccc4c59a0c80e9ff63b2ce9e98e75ad958",
     "commit": "62657fd9774943b09552f8a9895e7877243a8664"},
)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def object_oid(kind, raw):
    return hashlib.sha1(f"{kind} {len(raw)}\0".encode() + raw).hexdigest()


def json_bytes(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate JSON key: " + key)
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=unique)


def safe_path(name):
    if (not isinstance(name, str) or not name or "\\" in name
            or "\0" in name or PurePosixPath(name).is_absolute()
            or PurePosixPath(name).as_posix() != name
            or any(part in (".", "..") for part in name.split("/"))):
        raise ValueError("Noncanonical proof path")
    return name


def bounded_read(path):
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Proof file exceeds its size limit")
    return path.read_bytes()


def publication_record(anchor, receipt):
    return {"path": anchor["receipt_path"], "sha256": anchor["receipt_sha256"],
            "publication_boundary_utc": receipt.get("published_at") or receipt["github_pull_request_created_at"],
            "references": {key: receipt[key] for key in
                           ("commit_url", "release_url", "github_pull_request_url", "protocol_tag")
                           if key in receipt}}


def load_capsule(root=ROOT, anchors=ANCHORS):
    """Check container identity and bind it to immutable local receipt anchors."""
    root = Path(root)
    manifest = json_bytes(bounded_read(root / MANIFEST))
    if manifest.get("schema") != SCHEMA or manifest.get("scope") != "partial Git Merkle proofs; no historical refs":
        raise ValueError("Unexpected proof schema or scope")
    container = manifest["capsule"]
    if container["path"] != CAPSULE:
        raise ValueError("Unexpected capsule path")
    encoded = bounded_read(root / CAPSULE)
    if len(encoded) != container["bytes"] or sha256(encoded) != container["sha256"]:
        raise ValueError("Compressed capsule fingerprint differs")
    with gzip.GzipFile(fileobj=io.BytesIO(encoded)) as stream:
        decoded = stream.read(MAX_BYTES + 1)
    if len(decoded) > MAX_BYTES:
        raise ValueError("Decoded capsule exceeds its size limit")
    if len(decoded) != container["decoded_bytes"] or sha256(decoded) != container["decoded_sha256"]:
        raise ValueError("Decoded capsule fingerprint differs")
    capsule = json_bytes(decoded)
    if set(capsule) != {"schema", "pack_base64"} or capsule["schema"] != SCHEMA:
        raise ValueError("Unexpected capsule payload")
    pack = base64.b64decode(capsule["pack_base64"], validate=True)
    if len(pack) != container["pack_bytes"] or sha256(pack) != container["pack_sha256"]:
        raise ValueError("Git pack fingerprint differs")
    if (len(pack) < 32 or pack[:4] != b"PACK"
            or struct.unpack(">I", pack[4:8])[0] not in (2, 3)
            or hashlib.sha1(pack[:-20]).digest() != pack[-20:]):
        raise ValueError("Invalid Git pack header or checksum")
    inventory = {}
    for row in manifest["objects"]:
        if (set(row) != {"oid", "type", "bytes", "sha256"}
                or not OID.fullmatch(row["oid"]) or row["oid"] in inventory
                or row["type"] not in ("commit", "tree", "blob")
                or not isinstance(row["bytes"], int) or isinstance(row["bytes"], bool)
                or not 0 <= row["bytes"] <= MAX_BYTES or not SHA256.fullmatch(row["sha256"])):
            raise ValueError("Invalid or duplicate Git object inventory entry")
        inventory[row["oid"]] = row
    if (not inventory or len(inventory) != manifest["object_count"]
            or len(inventory) != struct.unpack(">I", pack[8:12])[0]):
        raise ValueError("Git object count differs")
    registrations = manifest["registrations"]
    if len(registrations) != len(anchors):
        raise ValueError("Registration proof count differs")
    for proof, anchor in zip(registrations, anchors, strict=True):
        raw = bounded_read(root / anchor["registration_path"])
        receipt_raw = bounded_read(root / anchor["receipt_path"])
        if sha256(raw) != anchor["registration_sha256"] or sha256(receipt_raw) != anchor["receipt_sha256"]:
            raise ValueError("An anchored registration or public receipt changed")
        registration, receipt = json_bytes(raw), json_bytes(receipt_raw)
        if receipt["commit"] != anchor["commit"] or receipt["registration_sha256"] != anchor["registration_sha256"]:
            raise ValueError("Public receipt identity differs")
        expected = {**registration["files"], anchor["registration_path"]: anchor["registration_sha256"]}
        bindings = proof["bindings"]
        paths = [safe_path(row["path"]) for row in bindings]
        if len(paths) != len(set(paths)) or set(paths) != set(expected):
            raise ValueError("Registered path set differs")
        if (proof["commit"] != anchor["commit"]
                or proof["registration_path"] != anchor["registration_path"]
                or proof["registration_sha256"] != anchor["registration_sha256"]
                or proof["registered_utc"] != registration["registered_utc"]
                or proof["publication_record"] != publication_record(anchor, receipt)):
            raise ValueError("Registration proof identity differs")
        for row in bindings:
            if (set(row) != {"path", "blob_oid", "sha256"}
                    or not OID.fullmatch(row["blob_oid"])
                    or row["sha256"] != expected[row["path"]]):
                raise ValueError("Registered content fingerprint differs")
    return manifest, pack


def git_environment():
    """Ignore ambient Git redirections/replacements, especially object writes."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_NO_REPLACE_OBJECTS="1")
    return env


def git(root, env, *args, raw=None):
    result = subprocess.run(["git", *args], cwd=root, env=env, input=raw,
                            capture_output=True, check=True)
    return result.stdout


def tree_entries(raw):
    result, offset = {}, 0
    while offset < len(raw):
        space, end = raw.index(b" ", offset), raw.index(b"\0", offset)
        mode, name = raw[offset:space], raw[space + 1:end]
        if (mode not in (b"40000", b"100644", b"100755", b"120000", b"160000")
                or not name or name in (b".", b"..") or b"/" in name
                or name in result or end + 21 > len(raw)):
            raise ValueError("Invalid Git tree entry")
        result[name] = (mode, raw[end + 1:end + 21].hex())
        offset = end + 21
    return result


def verify_merkle(manifest, objects):
    needed = set()
    for proof in manifest["registrations"]:
        commit = proof["commit"]
        if commit not in objects or objects[commit][0] != "commit":
            raise ValueError("Missing anchored commit object")
        needed.add(commit)
        first = objects[commit][1].split(b"\n", 1)[0]
        if not first.startswith(b"tree ") or not OID.fullmatch(first[5:].decode("ascii")):
            raise ValueError("Invalid commit tree")
        for binding in proof["bindings"]:
            oid = first[5:].decode("ascii")
            parts = safe_path(binding["path"]).split("/")
            for index, part in enumerate(parts):
                if oid not in objects or objects[oid][0] != "tree":
                    raise ValueError("Missing required Merkle tree")
                needed.add(oid)
                entry = tree_entries(objects[oid][1]).get(part.encode())
                if entry is None:
                    raise ValueError("Registered path missing from commit tree")
                mode, oid = entry
                if mode != (b"40000" if index < len(parts) - 1 else b"100644"):
                    if index < len(parts) - 1 or mode != b"100755":
                        raise ValueError("Registered path is not a regular file")
            if oid not in objects or objects[oid][0] != "blob":
                raise ValueError("Missing registered blob")
            needed.add(oid)
            if oid != binding["blob_oid"] or sha256(objects[oid][1]) != binding["sha256"]:
                raise ValueError("Merkle binding differs from registered bytes")
    if needed != objects.keys():
        raise ValueError("Capsule contains objects outside its required proof paths")


def read_objects(root, env, manifest, index_path):
    output = git(root, env, "verify-pack", "-v", str(index_path)).decode()
    packed = {line.split()[0] for line in output.splitlines() if OID.fullmatch(line.split()[0])}
    inventory = {row["oid"]: row for row in manifest["objects"]}
    if packed != inventory.keys():
        raise ValueError("Packed object inventory differs")
    raw = git(root, env, "cat-file", "--batch", raw=("\n".join(inventory) + "\n").encode())
    stream, objects = io.BytesIO(raw), {}
    for oid, row in inventory.items():
        expected = f"{oid} {row['type']} {row['bytes']}\n".encode()
        if stream.readline() != expected:
            raise ValueError("Git object header differs")
        body = stream.read(row["bytes"])
        if (stream.read(1) != b"\n" or object_oid(row["type"], body) != oid
                or sha256(body) != row["sha256"]):
            raise ValueError("Git object SHA-1 or SHA-256 differs")
        objects[oid] = (row["type"], body)
    if stream.read():
        raise ValueError("Unexpected Git object stream suffix")
    verify_merkle(manifest, objects)


@contextmanager
def verified_environment(root=ROOT, anchors=ANCHORS):
    """Yield an isolated Git environment, then remove every restored old object."""
    root = Path(root).resolve()
    manifest, pack = load_capsule(root, anchors)
    base = git_environment()
    if git(root, base, "rev-parse", "--show-object-format").strip() != b"sha1":
        raise ValueError("Registration proofs require the original SHA-1 Git object format")
    actual = Path(os.fsdecode(git(root, base, "rev-parse", "--git-path", "objects").strip()))
    actual = (root / actual).resolve() if not actual.is_absolute() else actual.resolve()
    if os.pathsep in str(actual) or "\n" in str(actual) or not actual.is_dir():
        raise ValueError("Unsupported main Git object directory")
    with tempfile.TemporaryDirectory(prefix="alien6-registration-odb-") as temporary:
        objects = Path(temporary) / "objects"
        (objects / "pack").mkdir(parents=True, mode=0o700)
        env = {**base, "GIT_OBJECT_DIRECTORY": str(objects),
               "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(actual), "PYTHONHASHSEED": "10"}
        git(root, env, "index-pack", "--stdin", raw=pack)
        indices = list((objects / "pack").glob("*.idx"))
        if len(indices) != 1:
            raise ValueError("Unexpected restored pack inventory")
        read_objects(root, env, manifest, indices[0])
        yield env, {"status": "registered Merkle proofs verified", "objects": manifest["object_count"],
                    "registered_paths": sum(len(p["bindings"]) for p in manifest["registrations"]),
                    "object_types": dict(Counter(row["type"] for row in manifest["objects"])),
                    "historical_refs_created": 0, "model_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-capsule", "--check", action="store_true", help="Check the capsule only; no HEAD or model needed")
    mode.add_argument("--require-collected", action="store_true", help="Run the complete frozen offline verification (the default)")
    args = parser.parse_args()
    with verified_environment() as (env, summary):
        if not args.check_capsule:
            # Inherit stdout unchanged: the frozen verifier emits the sole report.
            return subprocess.run([sys.executable, "-m", "v3.verify", "--require-collected"],
                                  cwd=ROOT, env=env).returncode
    print(json.dumps({**summary, "temporary_objects_cleaned": True}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print("Registration replay failed: " + str(error), file=sys.stderr)
        raise SystemExit(1)
