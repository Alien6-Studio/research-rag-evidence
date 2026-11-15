"""Exercise the collector/replayer contract using only synthetic HTTP evidence."""
from contextlib import ExitStack, redirect_stdout
from io import StringIO
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import run as original
from v3 import benchmark, design, verify


class SyntheticTokenizer:
    """A deterministic tokenizer that charges every reference and separator."""
    def encode(self, text):
        return SimpleNamespace(ids=list(range(len(text))),
                               offsets=[(i, i + 1) for i in range(len(text))])


class SyntheticHTTPResponse:
    status = 200

    def __init__(self, value):
        self.body = json.dumps(value, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


def synthetic_cases(start=0):
    cases = []
    for index in range(start, start + 8):
        titles = [f"Synthetic {index:02} source {document:02}" for document in range(10)]
        cases.append({"id": f"synthetic-{index:02}",
                      "question": f"Which original synthetic fact applies to item {index}?",
                      "type": "bridge" if index < start + 4 else "comparison",
                      "answer": "A deliberately unmatched reference",
                      "context": {"title": titles,
                                  "sentences": [[f"Public original fact {index}-{document}-{sentence}."
                                                 for sentence in range(3)]
                                                for document in range(10)]},
                      "supporting_facts": {"title": [titles[0], titles[1]], "sent_id": [0, 1]}})
    return cases


class CollectorReplayIntegrationTests(unittest.TestCase):
    """Do not mock selection, metadata, context, answer or probe verification."""
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.base = self.root / "v3"
        self.base.mkdir()
        self.registration = self.base / "registration-amendment-01.json"
        self.registration.write_text(json.dumps({"registered_utc": "2026-11-15T00:00:00+00:00"}) + "\n")
        self.cohorts = self.base / "cohorts-amendment-01.json"
        self.cases = synthetic_cases()
        self.cohort = {"pilot": self.cases, "confirmatory": synthetic_cases(8), "generation_ids": [],
                       "selected_utc": "2026-11-14T23:00:00+00:00"}
        self.cohorts.write_text(json.dumps(self.cohort) + "\n")
        self.public = self.base / "public-registration-amendment-01.json"
        self.proof = {"commit": "synthetic-published-commit",
                      "registration_sha256": design.file_sha(self.registration),
                      "github_pull_request_created_at": "2026-11-15T00:01:00+00:00"}
        self.public.write_text(json.dumps(self.proof) + "\n")
        dependencies = {name: importlib.metadata.version(name) for name in
                        ("numpy", "pyarrow", "tokenizers", "ujson", "matplotlib")}
        (self.base / "environment.json").write_text(json.dumps({
            "python": sys.version, "dependencies": dependencies}) + "\n")
        (self.root / "data").mkdir()
        (self.root / "data/qwen-tokenizer.json").write_text("synthetic-tokenizer-stand-in\n")
        self.tokenizer = SyntheticTokenizer()
        self.counts = {"tags": 0, "show": 0, "version": 0,
                       "embed": 0, "generate": 0, "chat": 0}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for module in (design, benchmark, verify):
            self.stack.enter_context(patch.multiple(
                module, ROOT=self.root, BASE=self.base,
                COHORTS=self.cohorts, REGISTRATION=self.registration))
            self.stack.enter_context(patch.object(module, "PUBLIC_REGISTRATION", self.public, create=True))
            self.stack.enter_context(patch.object(module, "PILOT_RUN_NAME", "pilot-01-controlled", create=True))
        self.stack.enter_context(patch.object(benchmark, "Tokenizer", SimpleNamespace(from_file=lambda _: self.tokenizer)))
        self.stack.enter_context(patch.object(verify, "Tokenizer", SimpleNamespace(from_file=lambda _: self.tokenizer)))
        # Publication/source guards are exercised elsewhere with actual Git and
        # pinned data. Only those external prerequisites are synthetic here.
        self.stack.enter_context(patch.object(benchmark, "registered", return_value=json.loads(self.registration.read_text())))
        self.stack.enter_context(patch.object(design, "registered", return_value=json.loads(self.registration.read_text())))
        self.stack.enter_context(patch.object(benchmark, "public_registration", return_value=self.proof))
        self.stack.enter_context(patch.object(verify, "verify_cohorts", return_value=self.cohort))
        self.stack.enter_context(patch.object(verify, "verify_public_registration", return_value=self.proof))
        self.stack.enter_context(patch.object(benchmark, "archived_vectors", return_value={}))
        self.stack.enter_context(patch.object(
            benchmark.subprocess, "check_output", side_effect=lambda *args, **kwargs:
            "synthetic-current-commit\n" if kwargs.get("text") else b"synthetic-current-commit\n"))
        self.stack.enter_context(patch("urllib.request.urlopen", side_effect=self.fake_http))
        self.output = StringIO()
        self.stack.enter_context(redirect_stdout(self.output))

    def fake_http(self, request, timeout=None):
        endpoint = request.full_url.rsplit("/", 1)[-1]
        if endpoint not in self.counts:
            raise AssertionError("Unexpected external endpoint: " + endpoint)
        self.counts[endpoint] += 1
        payload = json.loads(request.data) if request.data else {}
        if endpoint == "tags":
            return SyntheticHTTPResponse({"models": [
                {"name": original.MODELS[role][0], "digest": original.MODELS[role][1]}
                for role in ("generator", "embedding")]})
        if endpoint == "show":
            return SyntheticHTTPResponse({"details": {"family": "synthetic fixture"},
                                          "model_info": {"general.name": payload["model"]}})
        if endpoint == "version":
            return SyntheticHTTPResponse({"version": "synthetic fixture"})
        if endpoint == "embed":
            self.assertEqual(payload["model"], original.MODELS["embedding"][0])
            self.assertIs(payload["truncate"], False)
            vectors = []
            for text in payload["input"]:
                digest = hashlib.sha256(text.encode("utf-8")).digest()
                vectors.append([1.0 + digest[i % len(digest)] / 255 for i in range(768)])
            return SyntheticHTTPResponse({"model": original.MODELS["embedding"][0],
                                          "embeddings": vectors})
        if endpoint == "generate":
            self.assertIn(payload["prompt"], verify.PROBES)
            return SyntheticHTTPResponse({"model": original.MODELS["generator"][0],
                                          "done": True, "done_reason": "stop",
                                          "prompt_eval_count": len(self.tokenizer.encode(payload["prompt"]).ids)})
        self.assertEqual(endpoint, "chat")
        self.assertEqual(payload["model"], original.MODELS["generator"][0])
        self.assertEqual(payload["messages"][0], {"role": "system", "content": original.SYSTEM})
        self.assertEqual(payload["options"], original.OPTIONS)
        self.assertIs(payload["think"], False)
        # All lexical outcomes are zero on purpose. Technical qualification
        # cannot depend on getting the synthetic reference answer right.
        answer = {"answer": "", "citations": [], "abstain": True}
        return SyntheticHTTPResponse({"model": original.MODELS["generator"][0],
                                      "done": True, "done_reason": "stop",
                                      "prompt_eval_count": 100,
                                      "message": {"role": "assistant", "content": json.dumps(answer)},
                                      "eval_count": 8, "eval_duration": 1000})

    def collect(self):
        benchmark.prepare("pilot", "controlled")
        benchmark.generate("pilot")
        out = benchmark.run_path("pilot")
        self.assertEqual(out.name, "pilot-01-controlled")
        self.assertEqual(len(design.read(out / "jobs.json")), 128)
        answers = design.lines(out / "answers.jsonl")
        self.assertEqual(len(answers), 64)
        self.assertTrue(all(row["metrics"]["answer_em"] == 0 and row["answer"]["abstain"] for row in answers))
        self.assertEqual(self.counts["generate"], 3)
        self.assertEqual(self.counts["chat"], 64)
        self.assertGreater(self.counts["embed"], 0)
        return out

    def test_full_pilot_qualifies_with_distinct_scopes_and_zero_exact_matches(self):
        out = self.collect()
        start, preparation = (design.read(out / name) for name in
                              ("preparation-start.json", "preparation.json"))
        self.assertIn("One local quality experiment", start["scope"])
        self.assertEqual(preparation["scope"], "Controlled ten supplied paragraphs per question.")
        self.assertNotEqual(start["scope"], preparation["scope"])
        jobs = design.read(out / "jobs.json")
        for case in self.cases:
            for method in benchmark.METHODS:
                arms = [job for job in jobs if job["question_id"] == case["id"] and job["retriever"] == method]
                self.assertEqual(len(arms), 8)
                self.assertTrue(all(job["retrieved"] == arms[0]["retrieved"] for job in arms))
                self.assertTrue(all(job["context_tokens"] <= job["budget"] for job in arms))
        before_replay = dict(self.counts)
        benchmark.qualify()
        certificate = design.read(out / "qualification.json")
        self.assertTrue(certificate["passed"])
        self.assertIsNone(certificate["verification_error"])
        self.assertEqual(certificate["independent_replay"]["contexts"], 128)
        self.assertEqual(certificate["independent_replay"]["responses"], 64)
        self.assertEqual(certificate["errors"], 0)
        replay = verify.verify_pilot_inputs()
        self.assertTrue(replay["passed"])
        answer_summary = {"errors": 0, "observed": 64}
        verify.verify_pilot_certificate(out, answer_summary, self.proof)
        benchmark.require_pilot()
        self.assertEqual(self.counts, before_replay, "Offline qualification or replay called an API")

    def test_wrong_corpus_scope_fails_qualification_despite_valid_responses(self):
        out = self.collect()
        path = out / "preparation.json"
        preparation = design.read(path)
        preparation["scope"] = "One local quality experiment; this is not the controlled corpus scope."
        path.write_text(json.dumps(preparation) + "\n")
        with self.assertRaisesRegex(ValueError, "scope"):
            verify.verify_pilot_inputs()
        with self.assertRaisesRegex(RuntimeError, "Pilot failed"):
            benchmark.qualify()
        certificate = design.read(out / "qualification.json")
        self.assertFalse(certificate["passed"])
        self.assertEqual(certificate["errors"], 0)
        self.assertEqual(certificate["responses"], 64)
        with self.assertRaisesRegex(ValueError, "not qualified"):
            benchmark.require_pilot()

    def test_pooled_preparation_has_its_own_scope_and_never_generates_answers(self):
        self.collect()
        benchmark.qualify()
        benchmark.prepare("confirmatory", "pooled")
        out = benchmark.run_path("confirmatory", "pooled")
        start, preparation = (design.read(out / name) for name in
                              ("preparation-start.json", "preparation.json"))
        self.assertIn("One local quality experiment", start["scope"])
        self.assertEqual(preparation["scope"],
                         "Pooled results are separate exploratory question-derived retrieval, without generation.")
        self.assertNotEqual(start["scope"], preparation["scope"])
        self.assertFalse((out / "answers.jsonl").exists())
        self.assertFalse((out / "intents.jsonl").exists())
        self.assertEqual(self.counts["chat"], 64)
        before_replay = dict(self.counts)
        jobs, _ = verify.verify_preparation(
            out, self.cohort["confirmatory"], "confirmatory", "pooled",
            self.tokenizer, benchmark.load_vectors(), self.proof)
        self.assertEqual(len(jobs), 128)
        self.assertEqual(self.counts, before_replay)

    def test_all_other_shared_execution_metadata_still_must_match(self):
        out = self.collect()
        path = out / "preparation.json"
        preparation = design.read(path)
        preparation["logical_cpus"] += 1
        path.write_text(json.dumps(preparation) + "\n")
        with self.assertRaisesRegex(ValueError, "preparation-start.logical_cpus"):
            verify.verify_pilot_inputs()


if __name__ == "__main__":
    unittest.main()
