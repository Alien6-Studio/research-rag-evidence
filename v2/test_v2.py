"""Offline controls for the prospective measurement and cohort boundaries."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np
from tokenizers import Tokenizer

import run as historical
from test_run import fixture
from v2.core import (annotations, answer_metrics, chunks, context_metrics, documents,
                     exact_mcnemar, holm, paired_interval, ranking, select_cohorts)


def synthetic(index, kind):
    case = copy.deepcopy(fixture())
    case.update(id=f"{kind}-{index:05}", type=kind, question=f"Question {kind} {index}?")
    titles = [f"Document {kind} {index} {j}" for j in range(10)]
    case["context"] = {"title": titles, "sentences": [[f"Text {index} {j}."] for j in range(10)]}
    case["supporting_facts"] = {"title": titles[:2], "sent_id": [0, 0]}
    return case


class ProspectiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tokenizer = Tokenizer.from_file(str(historical.ROOT / "data/qwen-tokenizer.json"))

    def test_selection_is_outcome_blind_balanced_reproducible_and_disjoint(self):
        rows = [synthetic(i, kind) for kind in ("bridge", "comparison") for i in range(160)]
        historical_cases = [rows[0]]
        result = select_cohorts(rows, historical_cases)
        self.assertEqual(result, select_cohorts(list(reversed(rows)), historical_cases))
        self.assertEqual(len(result["pilot"]), 8)
        self.assertEqual(len(result["confirmatory"]), 256)
        self.assertEqual(len(result["generation_ids"]), 128)
        self.assertEqual(len(result["stability_ids"]), 16)
        self.assertTrue(set(result["stability_ids"]) <= set(result["generation_ids"]))
        combined = historical_cases + result["pilot"] + result["confirmatory"]
        titles = [t for c in combined for t in set(c["supporting_facts"]["title"])]
        self.assertEqual(len(titles), len(set(titles)))
        self.assertEqual(len(combined), len({c["id"] for c in combined}))
        for split, count in [("pilot", 4), ("confirmatory", 128)]:
            self.assertEqual(sum(c["type"] == "bridge" for c in result[split]), count)

    def test_insufficient_pool_does_not_silently_shrink_the_cohort(self):
        with self.assertRaises(ValueError):
            select_cohorts([synthetic(1, "bridge")], [])

    def test_indexing_has_no_answer_or_annotation_dependency(self):
        case = fixture()
        before = chunks(documents(case))
        case["answer"] = "A different reference"
        case["supporting_facts"] = {"title": ["nonexistent"], "sent_id": [999]}
        after = chunks(documents(case))
        self.assertEqual(before, after)
        self.assertEqual(ranking(before, case["question"], "bm25", {}), ranking(after, case["question"], "bm25", {}))

    def test_controlled_rendering_matches_the_historical_format(self):
        case = fixture()
        self.assertEqual(historical.render_context(chunks(documents(case))),
                         historical.render_context(historical.chunks_for(case)))

    def test_tokens_include_headers_and_skipped_chunks_are_not_truncated(self):
        case = fixture()
        candidates = chunks(documents(case))
        for budget in (0, 16, 40, 80, 160):
            for policy in ("ranked", "diverse"):
                selected = historical.pack(candidates, budget, policy, self.tokenizer)
                metrics = context_metrics(case, candidates, candidates, selected, self.tokenizer, budget)
                self.assertLessEqual(metrics["context_tokens"], budget)
                self.assertTrue(all(c in candidates for c in selected))
        with self.assertRaises(ValueError):
            context_metrics(case, candidates, candidates, candidates, self.tokenizer, 0)

    def test_retrieval_and_transmitted_units_are_distinct(self):
        case = fixture()
        candidates = chunks(documents(case))
        result = context_metrics(case, candidates, candidates, candidates[:1], self.tokenizer, 1536)
        self.assertEqual(result["recall10"], 1)
        self.assertEqual(result["retrieved_sentence_coverage"], 1)
        self.assertEqual(result["evidence_coverage"], .5)
        self.assertEqual(result["complete_context"], 0)

    def test_same_title_with_different_paragraph_is_not_gold_evidence(self):
        case = fixture()
        altered = documents(case)
        altered[0] = {"title": "Timeout", "sentences": ["Different source."], "key": "other-version"}
        selected = chunks(altered)
        reference = chunks(documents(case))
        metrics = context_metrics(case, reference + selected, reference + selected, selected, self.tokenizer, 1536)
        self.assertEqual(metrics["evidence_coverage"], .5)

    def test_invalid_citations_and_abstention_keep_lexical_limits(self):
        case = fixture()
        job = {"selected": chunks(documents(case))}
        metrics = answer_metrics(case, job, {"answer": case["answer"], "abstain": False, "citations": ["d00s000", "invented"]})
        self.assertEqual(metrics["answer_em"], 1)
        self.assertEqual(metrics["invalid_citations"], 1)
        self.assertEqual(metrics["citation_validity"], .5)
        self.assertEqual(answer_metrics(case, job, {"answer": case["answer"], "abstain": True, "citations": []})["answer_em"], 0)

    def test_dense_cosine_and_tie_order_and_bad_vectors(self):
        candidates = [{"id": "b", "text": "one"}, {"id": "a", "text": "two"}]
        vectors = {"search_document: one": [1., 0.], "search_document: two": [1., 0.], "search_query: q": [1., 0.]}
        self.assertEqual([c["id"] for c in ranking(candidates, "q", "dense", vectors)], ["a", "b"])
        vectors["search_query: q"] = [0., 0.]
        with self.assertRaises(ValueError): ranking(candidates, "q", "dense", vectors)

    def test_paired_tests_keep_losses_and_correct_multiple_comparisons(self):
        self.assertEqual(exact_mcnemar([0] * 7, [1] * 7)["p_exact"], .015625)
        self.assertEqual(exact_mcnemar([1, 0], [0, 1])["p_exact"], 1)
        self.assertEqual(exact_mcnemar([1, 1], [1, 1])["p_exact"], 1)
        np.testing.assert_allclose(holm([.01, .03, .2]), [.03, .06, .2])
        result = paired_interval([0, 1, 0, 1], [1, 0, 0, 1], ["bridge", "bridge", "comparison", "comparison"], draws=100)
        self.assertEqual(result["mean_difference"], 0)
        self.assertEqual(result["unit"], "question, within type")

    def test_pilot_qualification_checks_exact_requests_and_calibration(self):
        from v2 import benchmark
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            registration = out / "registration.json"
            registration.write_text("{}")
            jobs = [{"id": str(i), "question": "q", "context": "context"} for i in range(64)]
            answers = [{"id": j["id"], "request": benchmark.payload_for(j)} for j in jobs]
            (out / "jobs.json").write_text(json.dumps(jobs))
            (out / "answers.jsonl").write_text("\n".join(json.dumps(a) for a in answers))
            (out / "tokenizer-calibration.json").write_text(json.dumps([{"tokenizer_tokens": 3, "ollama_tokens": 3}] * 3))
            with mock.patch.object(benchmark, "registered"), mock.patch.object(benchmark, "run_path", return_value=out), mock.patch.object(benchmark, "REGISTRATION", registration):
                benchmark.qualify()
                self.assertTrue(json.loads((out / "qualification.json").read_text())["passed"])
                benchmark.require_pilot()
                (out / "answers.jsonl").write_text("altered")
                with self.assertRaises(ValueError): benchmark.require_pilot()


if __name__ == "__main__":
    unittest.main()
