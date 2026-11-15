"""Adversarial offline tests for the temporary registration proof store."""
import base64
from contextlib import redirect_stdout
import gzip
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from validation import replay_registered as replay


class RegistrationReplayTests(unittest.TestCase):
    def git(self, root, *args, raw=None, env=None):
        return subprocess.check_output(["git", *args], cwd=root, input=raw,
                                       env=env, stderr=subprocess.DEVNULL)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        self.root, self.builder = base / "study", base / "builder"
        for root in (self.root, self.builder):
            root.mkdir()
            self.git(root, "init", "--initial-branch=main", "--quiet")
        self.objects = {}
        def add(kind, raw):
            oid = replay.object_oid(kind, raw)
            self.objects[oid] = (kind, raw)
            actual = self.git(self.builder, "hash-object", "-w", "-t", kind, "--stdin", raw=raw).strip().decode()
            self.assertEqual(actual, oid)
            return oid
        self.add_object = add
        self.payload = b"frozen scientific payload\n"
        payload_oid = add("blob", self.payload)
        registration = {"registered_utc": "2026-11-15T10:00:00+00:00",
                        "files": {"frozen/payload.txt": replay.sha256(self.payload)}}
        registration_raw = (json.dumps(registration) + "\n").encode()
        registration_oid = add("blob", registration_raw)
        subtree = add("tree", b"100644 payload.txt\0" + bytes.fromhex(payload_oid))
        tree = add("tree", b"40000 frozen\0" + bytes.fromhex(subtree)
                   + b"100644 registered.json\0" + bytes.fromhex(registration_oid))
        # An intentionally unavailable parent demonstrates that this is a path
        # proof rather than a reconstruction of an earlier Git history.
        commit = add("commit", f"tree {tree}\nparent {'1' * 40}\nauthor A <a@example.invalid> 1 +0000\ncommitter A <a@example.invalid> 1 +0000\n\nFrozen input\n".encode())
        receipt = {"commit": commit, "registration_sha256": replay.sha256(registration_raw),
                   "github_pull_request_created_at": "2026-11-15T10:01:00Z",
                   "commit_url": "https://example.invalid/commit/" + commit}
        receipt_raw = (json.dumps(receipt) + "\n").encode()
        (self.root / "registered.json").write_bytes(registration_raw)
        (self.root / "receipt.json").write_bytes(receipt_raw)
        self.anchors = ({"registration_path": "registered.json", "registration_sha256": replay.sha256(registration_raw),
                         "receipt_path": "receipt.json", "receipt_sha256": replay.sha256(receipt_raw),
                         "commit": commit},)
        self.manifest = {"schema": replay.SCHEMA, "scope": "partial Git Merkle proofs; no historical refs",
                         "registrations": [{"commit": commit, "registration_path": "registered.json",
                                            "registration_sha256": replay.sha256(registration_raw),
                                            "registered_utc": registration["registered_utc"],
                                            "publication_record": replay.publication_record(self.anchors[0], receipt),
                                            "bindings": [
                                                {"path": "frozen/payload.txt", "blob_oid": payload_oid, "sha256": replay.sha256(self.payload)},
                                                {"path": "registered.json", "blob_oid": registration_oid, "sha256": replay.sha256(registration_raw)}]}]}
        (self.root / "provenance").mkdir()
        self.repack()

    def save_manifest(self):
        (self.root / replay.MANIFEST).write_text(json.dumps(self.manifest))

    def repack(self):
        pack = self.git(self.builder, "pack-objects", "--stdout", "--no-reuse-delta", "--no-reuse-object",
                        raw=("\n".join(self.objects) + "\n").encode())
        decoded = json.dumps({"schema": replay.SCHEMA, "pack_base64": base64.b64encode(pack).decode()}).encode()
        encoded = gzip.compress(decoded, mtime=0)
        (self.root / replay.CAPSULE).write_bytes(encoded)
        self.manifest.update(object_count=len(self.objects), objects=[
            {"oid": oid, "type": kind, "bytes": len(raw), "sha256": replay.sha256(raw)}
            for oid, (kind, raw) in self.objects.items()])
        self.manifest["capsule"] = {"path": replay.CAPSULE, "bytes": len(encoded), "sha256": replay.sha256(encoded),
                                    "decoded_bytes": len(decoded), "decoded_sha256": replay.sha256(decoded),
                                    "pack_bytes": len(pack), "pack_sha256": replay.sha256(pack)}
        self.save_manifest()

    def store_files(self):
        return {p.relative_to(self.root / ".git/objects").as_posix(): p.read_bytes()
                for p in (self.root / ".git/objects").rglob("*") if p.is_file()}

    def test_real_git_path_proof_without_head_refs_or_persistent_objects(self):
        before = self.store_files()
        with replay.verified_environment(self.root, self.anchors) as (env, summary):
            temporary = Path(env["GIT_OBJECT_DIRECTORY"])
            self.assertEqual(self.git(self.root, "show", self.anchors[0]["commit"] + ":frozen/payload.txt", env=env), self.payload)
            self.assertEqual(summary["registered_paths"], 2)
            self.assertEqual(summary["model_calls"], 0)
            self.assertEqual(self.git(self.root, "for-each-ref", env=env), b"")
            self.assertNotEqual(temporary, self.root / ".git/objects")
        self.assertFalse(temporary.exists())
        self.assertEqual(self.store_files(), before)
        self.assertEqual(self.git(self.root, "symbolic-ref", "HEAD"), b"refs/heads/main\n")
        self.assertNotEqual(subprocess.run(["git", "cat-file", "-e", self.anchors[0]["commit"]], cwd=self.root,
                                           capture_output=True).returncode, 0)

    def test_container_tampering_is_rejected_before_git(self):
        path = self.root / replay.CAPSULE
        path.write_bytes(path.read_bytes() + b"tamper")
        with patch.object(replay, "git", side_effect=AssertionError("Git must not be reached")):
            with self.assertRaisesRegex(ValueError, "Compressed capsule"):
                replay.load_capsule(self.root, self.anchors)

    def test_receipt_or_registration_cannot_be_rebound_by_editing_manifest(self):
        (self.root / "receipt.json").write_text("{}\n")
        self.manifest["registrations"][0]["publication_record"]["sha256"] = replay.sha256(b"{}\n")
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "anchored registration or public receipt"):
            replay.load_capsule(self.root, self.anchors)

    def test_duplicate_inventory_and_traversal_are_rejected(self):
        original = json.loads(json.dumps(self.manifest))
        self.manifest["objects"].append(dict(self.manifest["objects"][0])); self.save_manifest()
        with self.assertRaisesRegex(ValueError, "duplicate Git object"):
            replay.load_capsule(self.root, self.anchors)
        self.manifest = original
        self.manifest["registrations"][0]["bindings"][0]["path"] = "../outside"
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, "Noncanonical proof path"):
            replay.load_capsule(self.root, self.anchors)

    def test_valid_pack_does_not_excuse_wrong_object_sha256(self):
        self.manifest["objects"][0]["sha256"] = "0" * 64; self.save_manifest()
        with self.assertRaisesRegex(ValueError, "object SHA-1 or SHA-256"):
            with replay.verified_environment(self.root, self.anchors):
                self.fail("A forged object fingerprint reached the replay")
        self.assertEqual(self.store_files(), {})

    def test_valid_object_inventory_does_not_excuse_forged_merkle_binding(self):
        bindings = self.manifest["registrations"][0]["bindings"]
        bindings[0]["blob_oid"] = bindings[1]["blob_oid"]; self.save_manifest()
        with self.assertRaisesRegex(ValueError, "Merkle binding differs"):
            with replay.verified_environment(self.root, self.anchors):
                self.fail("A false path binding reached the replay")

    def test_unrelated_git_objects_are_not_smuggled_into_the_proof(self):
        self.add_object("blob", b"unrelated object\n"); self.repack()
        with self.assertRaisesRegex(ValueError, "outside its required proof paths"):
            with replay.verified_environment(self.root, self.anchors):
                self.fail("An unnecessary object reached the replay")

    def test_ambient_git_redirects_are_ignored_and_exception_cleans_store(self):
        before = self.store_files()
        with patch.dict(os.environ, {"GIT_OBJECT_DIRECTORY": "/invalid", "GIT_DIR": "/invalid",
                                     "GIT_ALTERNATE_OBJECT_DIRECTORIES": "/invalid", "GIT_CONFIG_COUNT": "1"}):
            with self.assertRaisesRegex(RuntimeError, "child failed"):
                with replay.verified_environment(self.root, self.anchors) as (env, _):
                    temporary = Path(env["GIT_OBJECT_DIRECTORY"])
                    self.assertNotIn("GIT_DIR", env)
                    self.assertNotIn("GIT_CONFIG_COUNT", env)
                    self.assertTrue(temporary.exists())
                    raise RuntimeError("child failed")
        self.assertFalse(temporary.exists())
        self.assertEqual(self.store_files(), before)

    def test_wrapper_runs_only_fixed_offline_child_and_preserves_stdout_and_status(self):
        from contextlib import contextmanager
        @contextmanager
        def environment():
            yield {"PYTHONHASHSEED": "10"}, {}
        def child(command, **kwargs):
            self.assertEqual(command, [replay.sys.executable, "-m", "v3.verify", "--require-collected"])
            self.assertNotIn("capture_output", kwargs)
            print('{"original_report": true}')
            return SimpleNamespace(returncode=7)
        output = io.StringIO()
        with patch.object(replay, "verified_environment", environment), patch.object(
                replay.subprocess, "run", side_effect=child), patch.object(
                replay.sys, "argv", ["replay_registered.py", "--require-collected"]), redirect_stdout(output):
            self.assertEqual(replay.main(), 7)
        self.assertEqual(output.getvalue(), '{"original_report": true}\n')


if __name__ == "__main__":
    unittest.main()
