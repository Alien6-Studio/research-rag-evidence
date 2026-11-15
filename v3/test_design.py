"""Controls for prospective sample separation and immutable registration."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from v3 import design


def case(index, kind="bridge"):
    name = f"{kind}-{index:04}"
    titles = [f"{name}-document-{i}" for i in range(10)]
    return {"id": name, "question": f"Question {name}?", "type": kind,
            "answer": "reference",
            "context": {"title": titles, "sentences": [["Original sentence."]
                                                         for _ in titles]},
            "supporting_facts": {"title": [titles[0]], "sent_id": [0]}}


class CohortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = [case(i, kind) for kind in ("bridge", "comparison")
                    for i in range(300)]

    def test_fixed_sizes_balanced_generation_and_seed_offsets(self):
        value = design.select_cohorts(self.rows, [])
        self.assertEqual((len(value["pilot"]), len(value["confirmatory"]),
                          len(value["generation_ids"])), (8, 256, 128))
        by_id = {item["id"]: item for item in value["confirmatory"]}
        self.assertEqual(set(value["generation_ids"]) - by_id.keys(), set())
        for split, count in (("pilot", 4), ("confirmatory", 128)):
            for kind in ("bridge", "comparison"):
                self.assertEqual(sum(c["type"] == kind for c in value[split]), count)
        for kind in ("bridge", "comparison"):
            self.assertEqual(sum(by_id[i]["type"] == kind
                                 for i in value["generation_ids"]), 64)
        self.assertEqual(value["seeds"], {"pilot": 20261116,
                                         "confirmatory": 20261117,
                                         "generation": 20261118,
                                         "job_order": 20261120})

    def test_deterministic_under_input_permutation_and_reference_changes(self):
        baseline = design.select_cohorts(self.rows, [])
        changed = copy.deepcopy(list(reversed(self.rows)))
        for item in changed:
            item["answer"] = "A different reference, never used for eligibility"
        replay = design.select_cohorts(changed, [])
        for split in ("pilot", "confirmatory"):
            self.assertEqual([c["id"] for c in baseline[split]],
                             [c["id"] for c in replay[split]])
        self.assertEqual(baseline["generation_ids"], replay["generation_ids"])

    def test_historical_ids_normalized_questions_and_support_titles_excluded(self):
        historical = case(999, "bridge")
        repeated_id = case(0)
        repeated_id["id"] = historical["id"]
        repeated_question = case(1)
        repeated_question["question"] = "  QUESTION   BRIDGE-0999?  "
        repeated_title = case(2)
        old_title = historical["supporting_facts"]["title"][0]
        repeated_title["context"]["title"][0] = old_title
        repeated_title["supporting_facts"]["title"][0] = old_title
        rows = [repeated_id, repeated_question, repeated_title, *self.rows]
        value = design.select_cohorts(rows, [historical])
        selected = value["pilot"] + value["confirmatory"]
        self.assertNotIn(historical["id"], {c["id"] for c in selected})
        self.assertNotIn(design.normalized_question(historical),
                         {design.normalized_question(c) for c in selected})
        self.assertNotIn(old_title, {t for c in selected
                                     for t in c["supporting_facts"]["title"]})

    def test_internal_id_question_and_support_title_separation(self):
        value = design.select_cohorts(self.rows + copy.deepcopy(self.rows), [])
        selected = value["pilot"] + value["confirmatory"]
        self.assertEqual(len({c["id"] for c in selected}), 264)
        self.assertEqual(len({design.normalized_question(c) for c in selected}), 264)
        titles = [t for c in selected for t in set(c["supporting_facts"]["title"])]
        self.assertEqual(len(titles), len(set(titles)))

    def test_invalid_annotations_and_non_ten_paragraph_cases_are_not_selected(self):
        bad = case(901)
        bad["supporting_facts"]["sent_id"] = [999]
        short = case(902)
        short["context"]["title"].pop()
        short["context"]["sentences"].pop()
        value = design.select_cohorts([bad, short, *self.rows], [])
        ids = {c["id"] for c in value["pilot"] + value["confirmatory"]}
        self.assertFalse({bad["id"], short["id"]} & ids)

    def test_insufficient_eligible_population_fails_without_reducing_size(self):
        with self.assertRaisesRegex(ValueError, "Insufficient eligible"):
            design.select_cohorts([case(0)], [])


class RecordTests(unittest.TestCase):
    def test_creation_is_exclusive_and_jsonl_append_retains_prior_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested/record.json"
            design.write_new(path, {"value": "original"})
            original = path.read_bytes()
            with self.assertRaises(FileExistsError):
                design.write_new(path, {"value": "replacement"})
            self.assertEqual(path.read_bytes(), original)
            stream = Path(directory) / "records.jsonl"
            self.assertEqual(design.lines(stream), [])
            design.append(stream, {"intent": 1})
            design.append(stream, {"response": 1})
            self.assertEqual(design.lines(stream), [{"intent": 1}, {"response": 1}])


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.base = self.root / "v3"
        for name in design.FROZEN_FILES:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n")
        for name in ("design.py", "test_design.py", "core.py"):
            (self.base / name).write_text("# Fixed source\n")
        for name, raw in (("hotpot-validation.parquet", b"pinned dataset"),
                          ("qwen-tokenizer.json", b"pinned tokenizer")):
            path = self.root / "data" / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(raw)
        (self.root / "sources.json").write_text(json.dumps({
            "dataset": {"sha256": design.file_sha(self.root / "data/hotpot-validation.parquet")},
            "tokenizer": {"sha256": design.file_sha(self.root / "data/qwen-tokenizer.json")}}))
        history = self.root / "v2/observations.json"
        history.parent.mkdir()
        history.write_text("Retained observation bytes\n")
        (self.root / design.PRESERVATION).write_text(json.dumps({
            "baseline_commit": "historical", "files": {
                "v2/observations.json": design.file_sha(history)}}))
        self.context = patch.multiple(design, ROOT=self.root, BASE=self.base,
                                      COHORTS=self.base / "data/cohorts.json",
                                      REGISTRATION=self.base / "registration.json")
        self.context.start()

    def tearDown(self):
        self.context.stop()
        self.directory.cleanup()

    def register(self):
        with patch.object(design.subprocess, "check_output", return_value="base-commit\n"):
            return design.register()

    def committed(self, raw=None, returncode=0):
        return patch.object(design.subprocess, "run", return_value=subprocess.CompletedProcess(
            ["git", "show"], returncode,
            stdout=design.REGISTRATION.read_bytes() if raw is None else raw))

    def test_registration_covers_sources_tests_inputs_and_preservation(self):
        value = self.register()
        self.assertTrue(set(design.FROZEN_FILES) <= value["files"].keys())
        self.assertTrue({"v3/design.py", "v3/test_design.py", "v3/core.py"}
                        <= value["files"].keys())
        with self.committed():
            self.assertEqual(design.registered()["files"], value["files"])
        with self.assertRaises(FileExistsError):
            self.register()

    def test_changed_or_added_frozen_source_blocks_collection(self):
        self.register()
        path = self.base / "core.py"
        original = path.read_bytes()
        path.write_text("# Changed source\n")
        with self.assertRaisesRegex(ValueError, "Frozen file changed"):
            design.registered()
        path.write_bytes(original)
        (self.base / "new_instrument.py").write_text("# Unregistered source\n")
        with self.assertRaisesRegex(ValueError, "file set changed"):
            design.registered()

    def test_missing_or_different_git_registration_blocks_collection(self):
        self.register()
        for raw, code in ((b"{}", 0), (b"", 128)):
            with self.committed(raw, code), self.assertRaisesRegex(ValueError, "committed"):
                design.registered()

    def test_historical_bytes_and_pinned_inputs_are_checked(self):
        self.register()
        (self.root / "v2/observations.json").write_text("Altered history\n")
        with self.assertRaisesRegex(ValueError, "Historical evidence changed"):
            design.registered()
        (self.root / "data/qwen-tokenizer.json").write_text("Different tokenizer\n")
        with self.assertRaisesRegex(ValueError, "Pinned tokenizer differs"):
            design.check_inputs()

    def test_dynamic_semantic_status_and_publication_receipt_are_not_frozen(self):
        self.register()
        for name in ("semantic-status.json", "public-registration.json"):
            (self.base / name).write_text('{"status": "updated after registration"}\n')
        with self.committed():
            self.assertNotIn("v3/semantic-status.json", design.registered()["files"])
            self.assertNotIn("v3/public-registration.json", design.registered()["files"])


if __name__ == "__main__":
    unittest.main()
