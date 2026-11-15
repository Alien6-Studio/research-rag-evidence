"""Exercise real Git materialization and the untrusted layout/cache boundary."""
import base64
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from reproduction import runtime


def object_oid(kind, raw):
    return hashlib.sha1(f"{kind} {len(raw)}\0".encode() + raw).hexdigest()


class LayoutBoundaryTests(unittest.TestCase):
    def git(self, root, *args, raw=None, env=None):
        return subprocess.check_output(["git", *args], cwd=root, input=raw,
                                       env=env, stderr=subprocess.DEVNULL)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        self.root, self.original = base / "public", base / "original"
        for root in (self.root, self.original):
            root.mkdir()
            self.git(root, "init", "--quiet", "--object-format=sha1", "--initial-branch=main")
        specimens = [
            ("run.py", "reproduction/implementations/shared/runner.py", b"# frozen shared code\n", "100644"),
            ("v2/records.json", "data/budget/records.json", b'{"observed":17}\n', "100644"),
            ("v3/verify.py", "reproduction/implementations/selection/verify.py", b"# frozen selection code\n", "100755"),
        ]
        rows = []
        for original, published, raw, mode in specimens:
            path = self.root / published
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            oid = self.git(self.original, "hash-object", "-w", "--stdin", raw=raw).strip().decode()
            self.assertEqual(oid, object_oid("blob", raw))
            rows.append({"original": original, "published": published, "mode": mode,
                         "git_blob_sha1": oid, "sha256": runtime.sha256(raw), "bytes": len(raw)})
        rows.sort(key=lambda row: row["original"])
        entries = b"".join(f"{row['mode']} {row['git_blob_sha1']}\t{row['original']}\0".encode() for row in rows)
        self.git(self.original, "update-index", "-z", "--index-info", raw=entries)
        tree = self.git(self.original, "write-tree").strip().decode()
        commit_raw = f"tree {tree}\nauthor A <a@example.invalid> 1 +0000\ncommitter A <a@example.invalid> 1 +0000\n\nOriginal snapshot\n".encode()
        self.layout = {"schema": "alien6-functional-layout-v1", "role": "synthetic lossless relocation",
                       "source_commit_sha1": object_oid("commit", commit_raw), "source_tree_sha1": tree,
                       "source_commit_base64": base64.b64encode(commit_raw).decode(), "files": rows}
        (self.root / "provenance").mkdir()
        self.write_manifest()
        # A distinct public commit proves that the old source identity cannot
        # leak into the public object database during reconstruction.
        empty = self.git(self.root, "write-tree").strip().decode()
        public_raw = f"tree {empty}\nauthor A <a@example.invalid> 2 +0000\ncommitter A <a@example.invalid> 2 +0000\n\nPublic functional snapshot\n".encode()
        public_oid = self.git(self.root, "hash-object", "-t", "commit", "-w", "--stdin", raw=public_raw).strip()
        self.git(self.root, "update-ref", "refs/heads/main", public_oid.decode())

    def write_manifest(self):
        raw = (json.dumps(self.layout, indent=2) + "\n").encode()
        (self.root / runtime.MANIFEST).write_bytes(raw)
        self.expected = runtime.sha256(raw)

    def public_git(self):
        return {p.relative_to(self.root / ".git").as_posix(): p.read_bytes()
                for p in (self.root / ".git").rglob("*") if p.is_file()}

    @contextmanager
    def captured_temporary_directory(self):
        factory = runtime.tempfile.TemporaryDirectory
        paths = []
        def capture(*args, **kwargs):
            result = factory(*args, **kwargs)
            paths.append(Path(result.name))
            return result
        with patch.object(runtime.tempfile, "TemporaryDirectory", side_effect=capture):
            yield paths

    def test_real_git_reconstruction_preserves_modes_tree_and_commit_without_public_mutations(self):
        before = self.public_git()
        with runtime.workspace(self.root, self.expected) as (target, env, layout):
            self.assertNotEqual(target, self.root)
            self.assertEqual(self.git(target, "rev-parse", "HEAD", env=env).strip().decode(), layout["source_commit_sha1"])
            self.assertEqual(self.git(target, "rev-parse", "HEAD^{tree}", env=env).strip().decode(), layout["source_tree_sha1"])
            self.assertEqual(self.git(target, "fsck", "--strict", "--no-dangling", env=env), b"")
            self.assertEqual(self.git(target, "for-each-ref", env=env), b"")
            for row in layout["files"]:
                path = target / row["original"]
                self.assertEqual(path.read_bytes(), (self.root / row["published"]).read_bytes())
                self.assertEqual(bool(path.stat().st_mode & stat.S_IXUSR), row["mode"] == "100755")
        self.assertFalse(target.exists())
        self.assertEqual(self.public_git(), before)
        self.assertNotEqual(subprocess.run(["git", "cat-file", "-e", self.layout["source_commit_sha1"]],
                                           cwd=self.root, capture_output=True).returncode, 0)

    def test_missing_binding_is_detected_by_the_original_tree_even_with_rehashed_manifest(self):
        self.layout["files"].pop(); self.write_manifest()
        with self.captured_temporary_directory() as paths:
            with self.assertRaisesRegex(ValueError, "Materialized Git tree differs"):
                with runtime.workspace(self.root, self.expected):
                    self.fail("An incomplete snapshot reached the child")
        self.assertTrue(paths)
        self.assertTrue(all(not path.exists() for path in paths))

    def test_manifest_fingerprint_and_duplicate_json_keys_fail_before_materialization(self):
        raw = (self.root / runtime.MANIFEST).read_bytes()
        (self.root / runtime.MANIFEST).write_bytes(raw + b" ")
        with self.assertRaisesRegex(ValueError, "manifest fingerprint"):
            runtime.load_layout(self.root, self.expected)
        duplicated = raw.replace(b'"schema":', b'"schema":"forged","schema":', 1)
        (self.root / runtime.MANIFEST).write_bytes(duplicated)
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            runtime.load_layout(self.root, runtime.sha256(duplicated))

    def test_duplicate_original_or_published_bindings_are_rejected(self):
        original = json.loads(json.dumps(self.layout))
        for field in ("original", "published"):
            with self.subTest(field=field):
                self.layout = json.loads(json.dumps(original))
                self.layout["files"][1][field] = self.layout["files"][0][field]
                self.write_manifest()
                with self.assertRaisesRegex(ValueError, "Duplicate layout binding"):
                    runtime.load_layout(self.root, self.expected)

    def test_path_traversals_git_paths_and_file_directory_overlap_are_rejected(self):
        for path in ("../escape", "/absolute", "a/../b", "a//b", ".git/objects/x",
                     ".GIT/config", "a/.GiT/config", "a\\b", "a\nb", "./a"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                runtime.safe_path(path)
        self.layout["files"][1]["original"] = self.layout["files"][0]["original"] + "/child"
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "Overlapping file and directory"):
            runtime.load_layout(self.root, self.expected)

    def test_published_file_and_directory_symlinks_cannot_escape_evidence_boundary(self):
        row = self.layout["files"][0]
        path = self.root / row["published"]
        outside = Path(self.temporary.name) / "outside"
        outside.write_bytes(path.read_bytes()); path.unlink(); path.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            runtime.evidence_bytes(self.root, row)
        path.unlink(); path.write_bytes(outside.read_bytes())
        directory = path.parent
        moved = directory.with_name(directory.name + "-moved")
        directory.rename(moved); directory.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            runtime.evidence_bytes(self.root, row)

    def test_same_length_byte_tamper_and_missing_file_fail_closed_and_cleanup(self):
        row = self.layout["files"][0]; path = self.root / row["published"]
        original = path.read_bytes(); path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        before = self.public_git()
        with self.captured_temporary_directory() as paths:
            with self.assertRaisesRegex(ValueError, "evidence fingerprint differs"):
                with runtime.workspace(self.root, self.expected):
                    self.fail("Changed scientific bytes reached the child")
        self.assertTrue(all(not path.exists() for path in paths))
        self.assertEqual(self.public_git(), before)
        path.unlink()
        with self.assertRaisesRegex(ValueError, "Missing or escaping"):
            runtime.evidence_bytes(self.root, row)

    def test_symlink_gitlink_modes_parent_commits_and_forged_commit_identities_are_rejected(self):
        original = json.loads(json.dumps(self.layout))
        for mode in ("120000", "160000", "100600"):
            self.layout = json.loads(json.dumps(original)); self.layout["files"][0]["mode"] = mode; self.write_manifest()
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "fingerprint or mode"):
                runtime.load_layout(self.root, self.expected)
        self.layout = json.loads(json.dumps(original))
        raw = base64.b64decode(self.layout["source_commit_base64"])
        raw = raw.replace(b"\nauthor ", b"\nparent " + b"1" * 40 + b"\nauthor ", 1)
        self.layout["source_commit_base64"] = base64.b64encode(raw).decode()
        self.layout["source_commit_sha1"] = object_oid("commit", raw); self.write_manifest()
        with self.assertRaisesRegex(ValueError, "Captured commit identity"):
            runtime.load_layout(self.root, self.expected)
        self.layout = json.loads(json.dumps(original)); self.layout["source_commit_sha1"] = "0" * 40; self.write_manifest()
        with self.assertRaisesRegex(ValueError, "Captured commit identity"):
            runtime.load_layout(self.root, self.expected)

    def test_child_exception_removes_workspace_and_does_not_mutate_public_git(self):
        before = self.public_git()
        with self.assertRaisesRegex(RuntimeError, "synthetic child failed"):
            with runtime.workspace(self.root, self.expected) as (target, env, layout):
                (target / "untracked-child-output").write_text("temporary only")
                raise RuntimeError("synthetic child failed")
        self.assertFalse(target.exists())
        self.assertEqual(self.public_git(), before)

    def test_git_and_python_environment_redirections_are_not_inherited(self):
        hostile = {"GIT_DIR": "/not-this-repo", "GIT_OBJECT_DIRECTORY": "/public-object-store",
                   "GIT_CONFIG_COUNT": "3", "GIT_INDEX_FILE": "/public-index",
                   "PYTHONPATH": "/untrusted-modules", "PYTHONHOME": "/untrusted-python",
                   "PYTHONSTARTUP": "/untrusted-startup", "PYTHONUSERBASE": "/untrusted-site",
                   "PYTHONINSPECT": "1", "PYTHONPYCACHEPREFIX": "/public-cache",
                   "PYTHONWARNINGS": "error", "PYTHONHASHSEED": "random"}
        with patch.dict(os.environ, hostile):
            env = runtime.isolated_environment()
        for key in hostile:
            self.assertNotIn(key, env)
        self.assertEqual(env["PYTHONNOUSERSITE"], "1")
        self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertEqual(env["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(env["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(env["GIT_NO_REPLACE_OBJECTS"], "1")

    def test_report_paths_cannot_overwrite_published_scientific_files(self):
        row = self.layout["files"][0]
        scientific = self.root / row["published"]
        raw = scientific.read_bytes()
        with self.assertRaisesRegex(ValueError, "Reports inside the repository"):
            runtime.run_science("test", root=self.root, output=scientific)
        self.assertEqual(scientific.read_bytes(), raw)
        (self.root / ".cache").mkdir()
        alias = self.root / ".cache/alias"
        alias.symlink_to(scientific.parent, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Reports inside the repository"):
            runtime.run_science("test", root=self.root, output=alias / "new-report")

    def test_failed_child_stage_keeps_a_failed_report_and_cleans_the_workspace(self):
        child = Path(self.temporary.name) / "child"
        child.mkdir()
        before = self.public_git()
        @contextmanager
        def workspace(*args, **kwargs):
            try:
                yield child, {}, self.layout
            finally:
                child.rmdir()
        output = Path(self.temporary.name) / "failed-replay-report"
        with patch.object(runtime, "workspace", workspace), patch.object(
                runtime, "prepare_inputs"), patch.object(runtime.subprocess, "run", return_value=SimpleNamespace(returncode=3)):
            with self.assertRaisesRegex(RuntimeError, "Offline verification stage failed"):
                runtime.run_science("verify", root=self.root, offline=True, output=output)
        summary = json.loads((output / "verification.json").read_text())
        self.assertEqual(summary["status"], "failed")
        self.assertEqual(summary["stages"][0]["exit_code"], 3)
        self.assertEqual(summary["model_calls"], 0)
        self.assertFalse(child.exists())
        self.assertEqual(self.public_git(), before)


class OfflineInputTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        self.target, self.root, self.cache = base / "target", base / "public", base / "cache"
        for path in (self.target, self.root, self.cache):
            path.mkdir()
        self.values = {"hotpot-validation.parquet": b"pinned public dataset bytes\n",
                       "qwen-tokenizer.json": b'{"synthetic":"tokenizer"}\n'}
        self.sources = {key: {"sha256": runtime.sha256(self.values[name]),
                              "url": "file:///nonexistent-network-or-input-resource"}
                        for key, name in (("dataset", "hotpot-validation.parquet"), ("tokenizer", "qwen-tokenizer.json"))}
        (self.target / "sources.json").write_text(json.dumps(self.sources))

    def test_offline_missing_or_corrupt_cache_never_starts_the_input_fetcher(self):
        with patch.object(runtime.subprocess, "run", side_effect=AssertionError("Network-capable child started")):
            with self.assertRaisesRegex(ValueError, "Offline mode requires"):
                runtime.prepare_inputs(self.target, runtime.isolated_environment(), self.root, self.cache, offline=True)
            for name, raw in self.values.items():
                (self.cache / name).write_bytes(raw)
            (self.cache / "hotpot-validation.parquet").write_bytes(b"wrong bytes")
            with self.assertRaisesRegex(ValueError, "hotpot-validation.parquet"):
                runtime.prepare_inputs(self.target, runtime.isolated_environment(), self.root, self.cache, offline=True)

    def test_offline_symlinked_cache_file_is_rejected_without_following_or_network(self):
        for name, raw in self.values.items():
            (self.cache / name).write_bytes(raw)
        name = "hotpot-validation.parquet"
        outside = Path(self.temporary.name) / "outside-cache"
        outside.write_bytes(self.values[name]); (self.cache / name).unlink(); (self.cache / name).symlink_to(outside)
        with patch.object(runtime.subprocess, "run", side_effect=AssertionError("Network-capable child started")):
            with self.assertRaisesRegex(ValueError, "Offline mode requires"):
                runtime.prepare_inputs(self.target, runtime.isolated_environment(), self.root, self.cache, offline=True)
        self.assertEqual(outside.read_bytes(), self.values[name])

    def test_valid_external_cache_runs_the_actual_frozen_input_checker_without_download_or_cache_changes(self):
        # Use the preserved implementation, with unreachable input URLs. Any
        # attempted fetch would fail rather than silently using the network.
        source_root = Path(__file__).resolve().parents[1]
        layout = runtime.load_layout(source_root)
        original = next(row for row in layout["files"] if row["original"] == "prepare_data.py")
        (self.target / "prepare_data.py").write_bytes(runtime.evidence_bytes(source_root, original))
        before = {}
        for name, raw in self.values.items():
            path = self.cache / name; path.write_bytes(raw)
            before[name] = (raw, path.stat().st_mtime_ns)
        runtime.prepare_inputs(self.target, runtime.isolated_environment(), self.root, self.cache, offline=True)
        for name, (raw, modified) in before.items():
            self.assertEqual((self.target / "data" / name).read_bytes(), raw)
            self.assertEqual((self.cache / name).read_bytes(), raw)
            self.assertEqual((self.cache / name).stat().st_mtime_ns, modified)
        self.assertFalse((self.root / ".cache").exists())


if __name__ == "__main__":
    unittest.main()
