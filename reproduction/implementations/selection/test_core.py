"""Selection controls use synthetic public text, never V3 cohort outcomes."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from run import pack, render_context
from v2.core import chunks, documents
from v3.core import (MMR_LAMBDA, POLICIES, context_metrics, context_redundancy,
                     required_sentence_texts, select, sentence_candidates)


class CharacterTokenizer:
    """Count every header, reference, separator and body character separately."""
    def encode(self, text):
        return SimpleNamespace(ids=list(range(len(text))),
                               offsets=[(i, i + 1) for i in range(len(text))])


def fixture(paragraphs=None, support=None):
    paragraphs = paragraphs or [("One", ["a"]), ("Two", ["b"]),
                                 ("Tri", ["c"]), ("For", ["d"])]
    case = {"id": "synthetic", "question": "Which synthetic fact applies?",
            "answer": "not consulted", "type": "bridge",
            "context": {"title": [p[0] for p in paragraphs],
                        "sentences": [p[1] for p in paragraphs]},
            "supporting_facts": support or {"title": [paragraphs[0][0]], "sent_id": [0]}}
    source = chunks(documents(case))
    ranked = [{**chunk, "score": float(len(source) - i)} for i, chunk in enumerate(source)]
    vectors = {"search_query: " + case["question"]: [1.0, 0.0]}
    for chunk in ranked:
        vectors["search_document: " + chunk["text"]] = [1.0, 0.0]
        for fact in chunk["facts"]:
            vectors["search_document: " + chunk["title"] + "\n" + fact["text"]] = [1.0, 0.0]
    return case, source, ranked, vectors


def partial(parent, facts):
    return {**parent, "facts": facts,
            "text": parent["title"] + "\n" + " ".join(f["text"] for f in facts)}


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.tokenizer = CharacterTokenizer()

    def choose(self, case, ranked, vectors, policy, budget=10000):
        return select(case["question"], ranked, policy, budget, self.tokenizer, vectors)

    def test_ranked_is_exactly_the_original_skip_packer(self):
        case, _, ranked, vectors = fixture([("One", ["a"]), ("Big", ["x" * 300]), ("Tri", ["c"])])
        for budget in (0, 1, 30, 65, 1000):
            with self.subTest(budget=budget):
                actual = self.choose(case, ranked, vectors, "ranked", budget)
                self.assertEqual(actual, pack(ranked, budget, "ranked", self.tokenizer))
                self.assertEqual(render_context(actual), render_context(pack(ranked, budget, "ranked", self.tokenizer)))

    def test_mmr_half_weight_prefers_complementary_accepted_units(self):
        case, _, ranked, vectors = fixture()
        for chunk, score, vector in zip(ranked, (10, 9, 8, 0), ([1, 0], [1, 0], [0, 1], [1, 0]), strict=True):
            chunk["score"] = score
            vectors["search_document: " + chunk["text"]] = vector
        budget = len(render_context([ranked[0], ranked[2]]))
        self.assertEqual(MMR_LAMBDA, .5)
        chosen = self.choose(case, ranked, vectors, "mmr", budget)
        self.assertEqual([c["id"] for c in chosen], [ranked[0]["id"], ranked[2]["id"]])

    def test_mmr_rejected_large_unit_does_not_enter_redundancy_set(self):
        case, _, ranked, vectors = fixture([("Big", ["x" * 300]), ("Two", ["b"]), ("Tri", ["c"])])
        for chunk, vector in zip(ranked, ([1, 0], [1, 0], [0, 1]), strict=True):
            vectors["search_document: " + chunk["text"]] = vector
        chosen = self.choose(case, ranked, vectors, "mmr", len(render_context([ranked[1]])))
        self.assertEqual([c["id"] for c in chosen], [ranked[1]["id"]])

    def test_constant_mmr_relevance_uses_id_ties_not_input_order(self):
        case, _, ranked, vectors = fixture()
        for chunk in ranked:
            chunk["score"] = 7.0
        reversed_ranked = list(reversed(ranked))
        chosen = self.choose(case, reversed_ranked, vectors, "mmr", len(render_context([ranked[0]])))
        self.assertEqual(chosen[0]["id"], min(c["id"] for c in ranked))

    def test_negative_cosine_does_not_create_a_novelty_bonus(self):
        case, _, ranked, vectors = fixture()
        for chunk, score, vector in zip(ranked, (10, 2, 4, 0), ([1, 0], [-1, 0], [0, 1], [1, 0]), strict=True):
            chunk["score"] = score
            vectors["search_document: " + chunk["text"]] = vector
        chosen = self.choose(case, ranked, vectors, "mmr", len(render_context([ranked[0], ranked[2]])))
        self.assertEqual([c["id"] for c in chosen], [ranked[0]["id"], ranked[2]["id"]])

    def test_mmr_output_is_canonical_parent_order(self):
        case, _, ranked, vectors = fixture()
        ranked[0]["score"], ranked[1]["score"] = 1, 20
        chosen = self.choose(case, ranked[:2], vectors, "mmr")
        self.assertEqual([c["id"] for c in chosen], [c["id"] for c in ranked[:2]])
        self.assertEqual(render_context(chosen), render_context(ranked[:2]))

    def test_sentence_packing_skips_large_sentence_and_reuses_one_header(self):
        case, _, ranked, vectors = fixture([("One", ["short", "x" * 300, "last"])] )
        target = partial(ranked[0], [ranked[0]["facts"][0], ranked[0]["facts"][2]])
        budget = len(render_context([target]))
        self.assertEqual(self.choose(case, ranked, vectors, "ranked", budget), [])
        chosen = self.choose(case, ranked, vectors, "sentences", budget)
        self.assertEqual(chosen, [target])
        self.assertEqual(render_context(chosen).count("[d00p000]"), 1)
        self.assertEqual(len(self.tokenizer.encode(render_context(chosen)).ids), budget)

    def test_sentence_mmr_uses_question_relevance_and_original_bodies(self):
        case, _, ranked, vectors = fixture([("One", ["irrelevant", "answerword"])] )
        vectors["search_document: One\nirrelevant"] = [0, 1]
        vectors["search_document: One\nanswerword"] = [1, 0]
        target = partial(ranked[0], [ranked[0]["facts"][1]])
        chosen = self.choose(case, ranked, vectors, "sentence_mmr", len(render_context([target])))
        self.assertEqual(chosen, [target])

    def test_reference_header_and_separator_costs_cannot_be_omitted(self):
        case, _, ranked, vectors = fixture([("Title costs tokens", ["body"])] )
        for policy in POLICIES:
            with self.subTest(policy=policy):
                self.assertEqual(self.choose(case, ranked, vectors, policy, len("body")), [])

    def test_helpers_expand_only_top_ten_with_stable_prefixed_inputs(self):
        paragraphs = [(f"Doc{i:02}", [f"Sentence {i}"]) for i in range(11)]
        _, _, ranked, _ = fixture(paragraphs)
        candidates = sentence_candidates(ranked)
        self.assertEqual(len(candidates), 10)
        self.assertEqual(candidates[0]["parent_rank"], 0)
        expected = ["search_document: " + c["title"] + "\n" + c["facts"][0]["text"] for c in ranked[:10]]
        self.assertEqual(required_sentence_texts(ranked), sorted(expected))

    def test_selectors_are_label_independent_and_do_not_mutate_inputs(self):
        case, _, ranked, vectors = fixture([("One", ["short", "longish", "last"]), ("Two", ["other"])])
        altered = deepcopy(case)
        altered.update(answer="different", type="comparison",
                       supporting_facts={"title": ["not a document"], "sent_id": [999]})
        rebuilt = [{**c, "score": r["score"]} for c, r in zip(chunks(documents(altered)), ranked, strict=True)]
        before = deepcopy(ranked)
        with patch("v3.core.annotations", side_effect=AssertionError("Selector read annotations")):
            for policy in POLICIES:
                with self.subTest(policy=policy):
                    self.assertEqual(render_context(self.choose(case, ranked, vectors, policy, 100)),
                                     render_context(self.choose(altered, rebuilt, vectors, policy, 100)))
        self.assertEqual(ranked, before)

    def test_invalid_policy_and_budget_fail(self):
        case, _, ranked, vectors = fixture()
        for policy, budget in [("unknown", 512), ("ranked", -1), ("ranked", 1.2), ("ranked", True)]:
            with self.subTest(policy=policy, budget=budget), self.assertRaises(ValueError):
                self.choose(case, ranked, vectors, policy, budget)

    def test_empty_retrieval_needs_no_vectors(self):
        for policy in POLICIES:
            self.assertEqual(select("q", [], policy, 0, self.tokenizer, {}), [])

    def test_invalid_mmr_scores_or_embeddings_fail(self):
        case, _, ranked, vectors = fixture()
        bad = deepcopy(ranked)
        bad[0]["score"] = float("nan")
        with self.assertRaises(ValueError):
            self.choose(case, bad, vectors, "mmr")
        for value in ([0, 0], [float("nan"), 0], [[1, 0]], [1, 0, 0]):
            corrupt = deepcopy(vectors)
            corrupt["search_document: " + ranked[1]["text"]] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.choose(case, ranked, corrupt, "mmr")


class ContextMetricTests(unittest.TestCase):
    def setUp(self):
        self.tokenizer = CharacterTokenizer()
        self.case, self.source, self.ranked, self.vectors = fixture(
            [("One", ["first original", "second original", "extra original"])],
            {"title": ["One", "One"], "sent_id": [0, 1]})

    def metrics(self, selected, source=None, ranked=None, case=None, budget=10000):
        return context_metrics(case or self.case, source or self.source,
                               ranked or self.ranked, selected, self.tokenizer, budget)

    def test_packing_loss_and_positions_use_original_sentence_coordinates(self):
        selected = [partial(self.ranked[0], [self.ranked[0]["facts"][1]])]
        result = self.metrics(selected)
        self.assertEqual(result["retrieved_complete_context"], 1)
        self.assertEqual(result["retrieved_sentence_coverage"], 1)
        self.assertEqual(result["evidence_coverage"], .5)
        self.assertEqual(result["packing_lost_annotations_count"], 1)
        self.assertEqual(result["retrieval_missing_annotations_count"], 0)
        self.assertEqual(result["perfect_retrieval_incomplete_context"], 1)
        self.assertEqual(result["distinct_sources"], 1)
        missing, present = result["annotated_positions"]
        self.assertFalse(missing["retained"])
        self.assertIsNone(missing["context_char_start"])
        self.assertTrue(present["retained"])
        self.assertEqual(present["context_sentence_position"], 1)
        start, end = present["context_char_start"], present["context_char_end"]
        self.assertEqual(result["context"][start:end], "second original")
        self.assertEqual((present["context_token_start"], present["context_token_end"]), (start, end))

    def test_retrieval_loss_is_not_counted_as_packing_loss(self):
        paragraphs = [(f"Doc{i:02}", [f"Sentence {i}"]) for i in range(11)]
        case, source, ranked, _ = fixture(paragraphs, {"title": ["Doc10"], "sent_id": [0]})
        result = self.metrics([], source=source, ranked=ranked, case=case)
        self.assertEqual(result["retrieved_complete_context"], 0)
        self.assertEqual(result["retrieval_missing_annotations_count"], 1)
        self.assertEqual(result["packing_lost_annotations_count"], 0)

    def test_every_selected_body_and_coordinate_must_match_its_source(self):
        for field, value in [("text", "fabricated answer"), ("sentence", 999),
                             ("id", "invented"), ("document", "invented")]:
            selected = deepcopy(self.ranked)
            selected[0]["facts"][0][field] = value
            selected[0]["text"] = selected[0]["title"] + "\n" + " ".join(f["text"] for f in selected[0]["facts"])
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.metrics(selected)

    def test_corrupt_index_does_not_override_the_original_public_body(self):
        source, ranked = deepcopy(self.source), deepcopy(self.ranked)
        for chunk in (source[0], ranked[0]):
            chunk["facts"][0]["text"] = "altered source body"
            chunk["text"] = chunk["title"] + "\n" + " ".join(f["text"] for f in chunk["facts"])
        with self.assertRaises(ValueError):
            self.metrics(ranked, source=source, ranked=ranked)

    def test_duplicate_sentences_and_parent_contexts_fail(self):
        duplicated = partial(self.ranked[0], [self.ranked[0]["facts"][0]] * 2)
        for selected in ([duplicated], self.ranked * 2):
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                self.metrics(selected)

    def test_source_chunk_cannot_be_misrepresented_as_another_parent(self):
        case, source, ranked, _ = fixture([("One", ["a"]), ("Two", ["b"])])
        selected = [partial(ranked[0], ranked[1]["facts"])]
        with self.assertRaises(ValueError):
            self.metrics(selected, source=source, ranked=ranked, case=case)

    def test_noncanonical_context_order_and_over_budget_fail(self):
        case, source, ranked, _ = fixture()
        with self.assertRaises(ValueError):
            self.metrics(list(reversed(ranked)), source=source, ranked=ranked, case=case)
        with self.assertRaises(ValueError):
            self.metrics(self.ranked, budget=1)

    def test_redundancy_uses_sentence_units_for_all_policy_granularities(self):
        vectors = {}
        for fact, value in zip(self.ranked[0]["facts"], ([1, 0], [1, 0], [-1, 0]), strict=True):
            vectors["search_document: One\n" + fact["text"]] = value
        result = context_redundancy(self.ranked, vectors)
        self.assertEqual(result["sentence_pairs"], 3)
        self.assertAlmostEqual(result["mean_positive_cosine"], 1 / 3)
        self.assertEqual(result["unit"], "original sentence")
        self.assertEqual(context_redundancy([], {}), {
            "mean_positive_cosine": 0.0, "sentence_pairs": 0, "unit": "original sentence"})

    def test_source_titles_identifiers_and_text_are_counted_in_budget(self):
        result = self.metrics(self.ranked)
        self.assertEqual(result["context_tokens"], len(render_context(self.ranked)))
        self.assertGreater(result["context_tokens"], sum(len(f["text"]) for f in self.ranked[0]["facts"]))


if __name__ == "__main__":
    unittest.main()
