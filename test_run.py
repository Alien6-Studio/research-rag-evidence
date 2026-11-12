import copy
from pathlib import Path
import unittest

from tokenizers import Tokenizer

from run import ROOT, bm25, chunks_for, fact_set, pack, render_context, retrieval_metrics, score


def fixture():
    return {"id": "fixture", "answer": "62 seconds", "type": "bridge", "question": "How long is the retry budget?",
            "context": {"title": ["Timeout", "Retry"],
                        "sentences": [["Wait up to 30 seconds.", "Unrelated detail.", "More noise.", "Another sentence."],
                                      ["Retry once after 2 seconds.", "Another detail."]]},
            "supporting_facts": {"title": ["Timeout", "Retry"], "sent_id": [0, 0]}}


class StudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tokenizer = Tokenizer.from_file(str(ROOT / "data/qwen-tokenizer.json"))

    def test_original_sentence_coordinates_survive_chunking(self):
        chunks = chunks_for(fixture())
        self.assertEqual([f["sentence"] for f in chunks[1]["facts"]], [3])
        self.assertEqual(chunks[2]["facts"][0]["title"], "Retry")
        self.assertEqual(chunks[2]["facts"][0]["sentence"], 0)

    def test_recall_and_transmitted_evidence_are_separate(self):
        case = fixture()
        chunks = chunks_for(case)
        metrics = retrieval_metrics(case, chunks, chunks, chunks[:1])
        self.assertEqual(metrics["recall10"], 1)
        self.assertEqual(metrics["evidence_coverage"], 0.5)
        self.assertEqual(metrics["perfect_retrieval_incomplete_context"], 1)

    def test_retrieval_denominator_includes_missing_relevant_chunks(self):
        case = fixture()
        chunks = chunks_for(case)
        metrics = retrieval_metrics(case, chunks, chunks[:1], chunks[:1])
        self.assertEqual(metrics["recall10"], 0.5)

    def test_budget_applies_to_fully_rendered_context(self):
        chunks = chunks_for(fixture())
        for budget in [0, 16, 40, 80, 160]:
            selected = pack(chunks, budget, "ranked", self.tokenizer)
            self.assertLessEqual(len(self.tokenizer.encode(render_context(selected)).ids), budget)
            self.assertTrue(all(chunk in chunks for chunk in selected))

    def test_annotations_do_not_change_selection(self):
        case = fixture()
        changed = copy.deepcopy(case)
        changed["supporting_facts"]["sent_id"] = [1, 1]
        left, right = chunks_for(case), chunks_for(changed)
        self.assertEqual(bm25(left, case["question"]), bm25(right, changed["question"]))
        for policy in ["ranked", "diverse"]:
            self.assertEqual(pack(left, 80, policy, self.tokenizer), pack(right, 80, policy, self.tokenizer))

    def test_bm25_prefers_the_matching_text(self):
        chunks = [{"text": "copper copper metal"}, {"text": "rubber material"}]
        self.assertGreater(bm25(chunks, "copper")[0], bm25(chunks, "copper")[1])

    def test_invalid_citation_is_not_accepted_as_support(self):
        case = fixture()
        chunks = chunks_for(case)
        result = score(case, {"selected": chunks}, {"answer": "62 seconds", "abstain": False,
                                                   "citations": ["d00s000", "d01s000", "invented"]})
        self.assertEqual(result["answer_em"], 1)
        self.assertEqual(result["sp_recall"], 1)
        self.assertAlmostEqual(result["sp_prec"], 2 / 3)
        self.assertEqual(result["invalid_citations"], 1)

    def test_abstention_does_not_get_credit_for_a_filled_answer(self):
        case = fixture()
        result = score(case, {"selected": chunks_for(case)}, {"answer": "62 seconds", "abstain": True, "citations": []})
        self.assertEqual(result["answer_em"], 0)

    def test_bad_source_annotation_stops_the_case(self):
        case = fixture()
        case["supporting_facts"]["sent_id"][0] = 99
        with self.assertRaises(ValueError):
            chunks_for(case)


if __name__ == "__main__":
    unittest.main()
