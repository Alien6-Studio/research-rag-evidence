"""Label-free indexing, explicit measurement units, and paired statistics."""
from collections import Counter
import hashlib
import json
import math
import random
from statistics import NormalDist

import numpy as np

from run import bm25, pack, render_context
from vendor.hotpot_evaluate_v1 import exact_match_score, f1_score

SEED = 20261113
METHODS = ("bm25", "dense")
POLICIES = ("ranked", "diverse")
BUDGETS = (512, 1536)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def paragraph_key(title, sentences):
    return digest([title, sentences])


def documents(case):
    """Only public question/context fields cross the indexing boundary."""
    return [{"title": title, "sentences": list(sentences),
             "key": paragraph_key(title, sentences)}
            for title, sentences in zip(case["context"]["title"],
                                        case["context"]["sentences"], strict=True)]


def chunks(documents_, size=3):
    result = []
    for index, doc in enumerate(documents_):
        for start in range(0, len(doc["sentences"]), size):
            facts = [{"id": f"d{index:02}s{i:03}", "title": doc["title"],
                      "document": doc["key"], "sentence": i,
                      "text": doc["sentences"][i].strip()}
                     for i in range(start, min(start + size, len(doc["sentences"])))]
            result.append({"id": f"d{index:02}p{start:03}", "title": doc["title"],
                           "facts": facts,
                           "text": doc["title"] + "\n" + " ".join(f["text"] for f in facts)})
    return result


def annotations(case):
    by_title = {d["title"]: d for d in documents(case)}
    if len(by_title) != len(case["context"]["title"]):
        raise ValueError("Ambiguous duplicate source titles")
    result = set()
    for title, sentence in zip(case["supporting_facts"]["title"],
                               case["supporting_facts"]["sent_id"], strict=True):
        if title not in by_title or not 0 <= sentence < len(by_title[title]["sentences"]):
            raise ValueError("Annotation outside its source paragraph")
        result.add((by_title[title]["key"], sentence))
    if not result:
        raise ValueError("Empty annotation set")
    return result


def coordinates(selected):
    return {(f["document"], f["sentence"]) for c in selected for f in c["facts"]}


def ranking(candidates, question, method, embeddings):
    if method == "bm25":
        scores = bm25(candidates, question)
    elif method == "dense":
        matrix = np.asarray([embeddings["search_document: " + c["text"]] for c in candidates], dtype=float)
        query = np.asarray(embeddings["search_query: " + question], dtype=float)
        lengths = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query)
        if not np.all(np.isfinite(matrix)) or not np.all(np.isfinite(query)) or np.any(lengths <= 0):
            raise ValueError("Non-finite or zero-norm embedding")
        scores = matrix @ query / lengths
    else:
        raise ValueError("Unknown retrieval method")
    order = sorted(range(len(candidates)), key=lambda i: (-float(scores[i]), candidates[i]["id"]))
    return [{**candidates[i], "score": float(scores[i])} for i in order]


def context_metrics(case, all_chunks, ranked, selected, tokenizer, budget):
    gold = annotations(case)
    relevant = {c["id"] for c in all_chunks if coordinates([c]) & gold}
    if not relevant:
        raise ValueError("No annotated passage in the indexed corpus")
    retrieved = ranked[:10]
    retained = coordinates(selected)
    context = render_context(selected)
    tokens = len(tokenizer.encode(context).ids)
    if tokens > budget or any(c not in retrieved for c in selected):
        raise ValueError("Invalid context selection")
    # Verify sentence bodies in the string actually placed in the request.
    expected_lines = {f"[{f['id']}] {f['text']}" for c in selected for f in c["facts"]}
    if not all(line in context for line in expected_lines):
        raise ValueError("A selected sentence is missing from the transmitted text")
    ranks = {c["id"]: i + 1 for i, c in enumerate(ranked)}
    sentence_ranks = [{"document": d, "sentence": s,
                       "rank": min(ranks[c["id"]] for c in all_chunks if (d, s) in coordinates([c]))}
                      for d, s in sorted(gold)]
    return {"recall10": len(relevant & {c["id"] for c in retrieved}) / len(relevant),
            "passage_recall_by_k": {str(k): len(relevant & {c['id'] for c in ranked[:k]}) / len(relevant) for k in (5, 10, 20)},
            "retrieved_sentence_coverage_by_k": {str(k): len(gold & coordinates(ranked[:k])) / len(gold) for k in (5, 10, 20)},
            "retrieved_sentence_coverage": len(gold & coordinates(retrieved)) / len(gold),
            "evidence_coverage": len(gold & retained) / len(gold),
            "complete_context": int(gold <= retained), "context_tokens": tokens,
            "annotated_sentence_count": len(gold), "annotated_passage_ranks": sentence_ranks,
            "context": context}


def answer_metrics(case, job, answer):
    lookup = {f["id"]: f for c in job["selected"] for f in c["facts"]}
    citations = set(answer["citations"])
    valid = citations & lookup.keys()
    cited = {(lookup[c]["document"], lookup[c]["sentence"]) for c in valid}
    gold = annotations(case)
    predicted = "" if answer["abstain"] else answer["answer"]
    return {"answer_em": int(exact_match_score(predicted, case["answer"])),
            "answer_f1": f1_score(predicted, case["answer"])[0],
            "abstain": int(answer["abstain"]),
            "citation_validity": len(valid) / len(citations) if citations else 0,
            "annotated_citation_recall": len(gold & cited) / len(gold),
            "invalid_citations": len(citations - lookup.keys())}


def select_cohorts(rows, historical):
    """Outcome-blind, seeded, support-document-disjoint sequential sampling."""
    used_ids = {c["id"] for c in historical}
    used_titles = {t for c in historical for t in c["supporting_facts"]["title"]}
    used_questions = {" ".join(c["question"].lower().split()) for c in historical}
    excluded = Counter()
    result = {}
    for split, count, seed in [("pilot", 4, SEED + 1), ("confirmatory", 128, SEED + 2)]:
        selected = []
        rng = random.Random(seed)
        for kind in ("bridge", "comparison"):
            pool = sorted((c for c in rows if c["type"] == kind), key=lambda c: c["id"])
            rng.shuffle(pool)
            group = []
            for case in pool:
                question = " ".join(case["question"].lower().split())
                titles = set(case["supporting_facts"]["title"])
                reason = ("reused_id" if case["id"] in used_ids else
                          "reused_question" if question in used_questions else
                          "shared_support_title" if titles & used_titles else None)
                try:
                    annotations(case)
                    if len(documents(case)) != 10:
                        reason = "not_ten_paragraphs"
                except (KeyError, ValueError):
                    reason = "invalid_annotation"
                if reason:
                    excluded[f"{split}:{kind}:{reason}"] += 1
                    continue
                group.append(case)
                used_ids.add(case["id"])
                used_questions.add(question)
                used_titles.update(titles)
                if len(group) == count:
                    break
            if len(group) != count:
                raise ValueError(f"Insufficient eligible questions for {split}/{kind}")
            selected.extend(group)
        result[split] = sorted(selected, key=lambda c: c["id"])
    rng = random.Random(SEED + 3)
    generation = sorted(c["id"] for kind in ("bridge", "comparison")
                        for c in rng.sample([c for c in result["confirmatory"] if c["type"] == kind], 64))
    rng = random.Random(SEED + 4)
    stability = sorted(c["id"] for kind in ("bridge", "comparison")
                       for c in rng.sample([c for c in result["confirmatory"] if c["type"] == kind and c["id"] in generation], 8))
    return {"seed": SEED, "pilot": result["pilot"], "confirmatory": result["confirmatory"],
            "generation_ids": generation, "stability_ids": stability,
            "exclusions_examined_before_targets_reached": dict(excluded),
            "selection": "Sequential random-order eligibility sampling, balanced by type; support titles cannot recur across selected questions or the historical cohort. Not a simple random sample of all HotpotQA."}


def exact_mcnemar(before, after):
    gains = sum(a == 0 and b == 1 for a, b in zip(before, after, strict=True))
    losses = sum(a == 1 and b == 0 for a, b in zip(before, after, strict=True))
    n = gains + losses
    p = min(1.0, 2 * sum(math.comb(n, k) for k in range(min(gains, losses) + 1)) / 2 ** n) if n else 1.0
    return {"gains": gains, "losses": losses, "p_exact": p}


def holm(pvalues):
    adjusted = [0.0] * len(pvalues)
    maximum = 0.0
    for rank, index in enumerate(sorted(range(len(pvalues)), key=pvalues.__getitem__)):
        maximum = max(maximum, min(1.0, (len(pvalues) - rank) * pvalues[index]))
        adjusted[index] = maximum
    return adjusted


def paired_interval(before, after, kinds, draws=10000, family=1):
    delta = np.asarray(after, dtype=float) - np.asarray(before, dtype=float)
    rng = np.random.default_rng(SEED)
    groups = [np.flatnonzero(np.asarray(kinds) == kind) for kind in ("bridge", "comparison")]
    samples = np.concatenate([rng.choice(group, (draws, len(group)), replace=True) for group in groups if len(group)], axis=1)
    means = delta[samples].mean(axis=1)
    alpha = .05 / family
    return {"mean_difference": float(delta.mean()), "ci95": list(map(float, np.quantile(means, [.025, .975]))),
            "bonferroni_family_interval": list(map(float, np.quantile(means, [alpha / 2, 1 - alpha / 2]))),
            "draws": draws, "unit": "question, within type", "family_size": family}


def power_planning():
    zpower = NormalDist().inv_cdf(.8)
    return [{"questions": n, "discordance_assumption": discordance,
             "conservative_family_size": 5, "alpha_per_comparison": .01,
             "approximate_80pct_mde": (NormalDist().inv_cdf(.995) + zpower) * math.sqrt(discordance / n)}
            for n in (128, 256) for discordance in (.1, .3, .5)]
