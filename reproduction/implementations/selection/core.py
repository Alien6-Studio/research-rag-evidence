"""Frozen, label-free passage/sentence selection and documentary measurements."""
from __future__ import annotations

from itertools import combinations
import math

import numpy as np

from run import pack as original_pack, render_context
from v2.core import annotations, coordinates, documents


POLICIES = ("ranked", "mmr", "sentences", "sentence_mmr")
MMR_LAMBDA = 0.5


def _budget(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("The documentary budget must be a nonnegative integer")


def _fact_key(fact):
    return (fact["id"], fact["title"], fact["document"],
            fact["sentence"], fact["text"])


def _chunk_text(title, facts):
    return title + "\n" + " ".join(f["text"] for f in facts)


def _validate_chunks(candidates):
    ids, fact_ids, locations = set(), set(), set()
    for chunk in candidates:
        if (not isinstance(chunk["id"], str) or chunk["id"] in ids
                or not isinstance(chunk["title"], str) or not chunk["facts"]):
            raise ValueError("Expected unique public chunks with original sentences")
        ids.add(chunk["id"])
        for fact in chunk["facts"]:
            if (not isinstance(fact["id"], str) or fact["id"] in fact_ids
                    or fact["title"] != chunk["title"]
                    or not isinstance(fact["document"], str)
                    or isinstance(fact["sentence"], bool)
                    or not isinstance(fact["sentence"], int) or fact["sentence"] < 0
                    or not isinstance(fact["text"], str)
                    or (fact["document"], fact["sentence"]) in locations):
                raise ValueError("Duplicate or invalid original sentence coordinates")
            fact_ids.add(fact["id"])
            locations.add((fact["document"], fact["sentence"]))
        if chunk["text"] != _chunk_text(chunk["title"], chunk["facts"]):
            raise ValueError("Chunk embedding text differs from its public sentence bodies")


def sentence_candidates(retrieved):
    """Expand only the saved top-ten passages, without reading any labels."""
    retrieved = list(retrieved)[:10]
    _validate_chunks(retrieved)
    return [{"id": fact["id"], "parent_id": chunk["id"],
             "parent_rank": rank, "parent": chunk, "fact": fact,
             "text": chunk["title"] + "\n" + fact["text"]}
            for rank, chunk in enumerate(retrieved)
            for fact in sorted(chunk["facts"], key=lambda f: f["sentence"])]


def required_sentence_texts(retrieved):
    """Return exact, prefixed embedding inputs for the public sentence universe."""
    return sorted({"search_document: " + item["text"]
                   for item in sentence_candidates(retrieved)})


def _assemble_sentences(items, retrieved):
    accepted = {item["id"] for item in items}
    result = []
    for parent in retrieved:
        facts = sorted((f for f in parent["facts"] if f["id"] in accepted),
                       key=lambda f: f["sentence"])
        if facts:
            result.append({**parent, "facts": facts,
                           "text": _chunk_text(parent["title"], facts)})
    return result


def _unit_vector(vectors, key, dimension=None):
    value = np.asarray(vectors[key], dtype=np.float64)
    norm = float(np.linalg.norm(value))
    if (value.ndim != 1 or not len(value) or not np.all(np.isfinite(value))
            or not math.isfinite(norm) or norm <= 0
            or (dimension is not None and len(value) != dimension)):
        raise ValueError("Expected finite, nonzero, dimension-compatible embeddings")
    return value / norm


def _normalized(values):
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("Selection relevance must be finite")
    low, high = min(values), max(values)
    if not math.isfinite(high - low):
        raise ValueError("Selection relevance range must be finite")
    return [0.0 for _ in values] if high == low else [
        float((value - low) / (high - low)) for value in values]


def _positive_cosine(left, right):
    return max(0.0, min(1.0, float(left @ right)))


def _mmr(candidates, relevance, vectors, render, tokenizer, budget):
    remaining, selected = list(candidates), []
    while remaining:
        def score(item):
            redundancy = max((_positive_cosine(vectors[item["id"]], vectors[x["id"]])
                              for x in selected), default=0.0)
            return MMR_LAMBDA * relevance[item["id"]] - (1 - MMR_LAMBDA) * redundancy
        item = min(remaining, key=lambda candidate: (-score(candidate), candidate["id"]))
        remaining.remove(item)
        # A skipped unit never enters the redundancy set. The next proposal is
        # rendered again because grouping changes header/separator overhead.
        if len(tokenizer.encode(render_context(render(selected + [item]))).ids) <= budget:
            selected.append(item)
    return render(selected)


def select(question, retrieved, policy, budget, tokenizer, vectors):
    """Select public units only; answers, support flags and outcomes are absent."""
    _budget(budget)
    if policy not in POLICIES:
        raise ValueError("Unknown V3 selection policy")
    retrieved = list(retrieved)[:10]
    _validate_chunks(retrieved)
    if policy == "ranked":
        result = original_pack(retrieved, budget, "ranked", tokenizer)
    elif not retrieved:
        result = []
    elif policy == "sentences":
        accepted = []
        for item in sentence_candidates(retrieved):
            proposal = _assemble_sentences(accepted + [item], retrieved)
            if len(tokenizer.encode(render_context(proposal)).ids) <= budget:
                accepted.append(item)
        result = _assemble_sentences(accepted, retrieved)
    elif policy == "mmr":
        units, dimension = {}, None
        for chunk in retrieved:
            vector = _unit_vector(vectors, "search_document: " + chunk["text"], dimension)
            units[chunk["id"]] = vector
            dimension = len(vector)
        relevance = dict(zip((c["id"] for c in retrieved),
                             _normalized([float(c["score"]) for c in retrieved]), strict=True))
        ranks = {c["id"]: rank for rank, c in enumerate(retrieved)}
        result = _mmr(retrieved, relevance, units,
                      lambda items: sorted(items, key=lambda c: ranks[c["id"]]),
                      tokenizer, budget)
    else:
        items = sentence_candidates(retrieved)
        query = _unit_vector(vectors, "search_query: " + question)
        units = {item["id"]: _unit_vector(vectors, "search_document: " + item["text"], len(query))
                 for item in items}
        values = [float(units[item["id"]] @ query) for item in items]
        relevance = dict(zip((item["id"] for item in items), _normalized(values), strict=True))
        result = _mmr(items, relevance, units,
                      lambda chosen: _assemble_sentences(chosen, retrieved), tokenizer, budget)
    if len(tokenizer.encode(render_context(result)).ids) > budget:
        raise ValueError("The empty or selected context exceeds its documentary budget")
    return result


def _positions(selected, encoding):
    result, cursor, ordinal = {}, 0, 0
    for index, chunk in enumerate(selected):
        cursor += (2 if index else 0) + len(f"[{chunk['id']}] {chunk['title']}\n")
        for position, fact in enumerate(chunk["facts"]):
            cursor += (1 if position else 0) + len(f"[{fact['id']}] ")
            start, end = cursor, cursor + len(fact["text"])
            offsets = getattr(encoding, "offsets", None)
            overlap = ([i for i, (a, b) in enumerate(offsets) if b > start and a < end]
                       if offsets is not None else [])
            result[(fact["document"], fact["sentence"])] = {
                "context_sentence_position": ordinal + 1,
                "context_char_start": start, "context_char_end": end,
                "context_token_start": min(overlap) if overlap else None,
                "context_token_end": max(overlap) + 1 if overlap else None}
            ordinal += 1
            cursor = end
    return result


def context_metrics(case, all_chunks, ranked, selected, tokenizer, budget):
    """Measure annotations only after a label-free selection has been made."""
    _budget(budget)
    gold = annotations(case)
    _validate_chunks(all_chunks)
    originals = {c["id"]: c for c in all_chunks}
    if len({c["id"] for c in ranked}) != len(ranked):
        raise ValueError("A ranking repeats a source chunk")
    known = {(d["key"], i): (d["title"], body.strip())
             for d in documents(case) for i, body in enumerate(d["sentences"])}
    for chunk in all_chunks:
        for fact in chunk["facts"]:
            location = (fact["document"], fact["sentence"])
            if location in known and known[location] != (fact["title"], fact["text"]):
                raise ValueError("Indexed sentence differs from the original public paragraph")
    for chunk in ranked:
        original = originals.get(chunk["id"])
        if (original is None or chunk["title"] != original["title"]
                or chunk["text"] != original["text"]
                or [_fact_key(f) for f in chunk["facts"]] != [_fact_key(f) for f in original["facts"]]):
            raise ValueError("Ranking differs from its source corpus")
    retrieved = list(ranked[:10])
    parents = {c["id"]: c for c in retrieved}
    parent_ranks = {c["id"]: rank for rank, c in enumerate(retrieved)}
    if (len({c["id"] for c in selected}) != len(selected)
            or [parent_ranks.get(c["id"], -1) for c in selected]
            != sorted(parent_ranks.get(c["id"], -1) for c in selected)):
        raise ValueError("Context parents must be unique and in canonical retrieval order")
    retained_facts = []
    for chunk in selected:
        original = parents.get(chunk["id"])
        if original is None or chunk["title"] != original["title"] or not chunk["facts"]:
            raise ValueError("Selected parent was not retrieved")
        expected = {_fact_key(f) for f in original["facts"]}
        if (any(_fact_key(f) not in expected for f in chunk["facts"])
                or [f["sentence"] for f in chunk["facts"]] != sorted(f["sentence"] for f in chunk["facts"])
                or chunk["text"] != _chunk_text(chunk["title"], chunk["facts"])):
            raise ValueError("Selected sentence body, coordinates or ordering changed")
        retained_facts.extend(chunk["facts"])
    if (len({_fact_key(f) for f in retained_facts}) != len(retained_facts)
            or len({(f["document"], f["sentence"]) for f in retained_facts}) != len(retained_facts)):
        raise ValueError("A sentence is transmitted more than once")
    relevant = {c["id"] for c in all_chunks if coordinates([c]) & gold}
    if not relevant:
        raise ValueError("No annotated passage in the indexed corpus")
    retained, found = coordinates(selected), coordinates(retrieved)
    context = render_context(selected)
    encoding = tokenizer.encode(context)
    if len(encoding.ids) > budget:
        raise ValueError("Rendered context exceeds its budget")
    positions = _positions(selected, encoding)
    ranks = {c["id"]: i + 1 for i, c in enumerate(ranked)}
    sentence_ranks = [{"document": d, "sentence": s,
                       "rank": min(ranks[c["id"]] for c in all_chunks
                                   if (d, s) in coordinates([c]))}
                      for d, s in sorted(gold)]
    annotated_positions = [{**row, "retained": (row["document"], row["sentence"]) in retained,
                            **positions.get((row["document"], row["sentence"]), {
                                "context_sentence_position": None, "context_char_start": None,
                                "context_char_end": None, "context_token_start": None,
                                "context_token_end": None})}
                           for row in sentence_ranks]
    return {"recall10": len(relevant & {c["id"] for c in retrieved}) / len(relevant),
            "passage_recall_by_k": {str(k): len(relevant & {c["id"] for c in ranked[:k]}) / len(relevant)
                                     for k in (5, 10, 20)},
            "retrieved_sentence_coverage_by_k": {str(k): len(gold & coordinates(ranked[:k])) / len(gold)
                                                  for k in (5, 10, 20)},
            "retrieved_sentence_coverage": len(gold & found) / len(gold),
            "evidence_coverage": len(gold & retained) / len(gold),
            "complete_context": int(gold <= retained), "context_tokens": len(encoding.ids),
            "annotated_sentence_count": len(gold), "annotated_passage_ranks": sentence_ranks,
            "retrieved_complete_context": int(gold <= found),
            "packing_lost_annotations_count": len((gold & found) - retained),
            "retrieval_missing_annotations_count": len(gold - found),
            "perfect_retrieval_incomplete_context": int(gold <= found and not gold <= retained),
            "distinct_sources": len({f["document"] for f in retained_facts}),
            "selected_sentence_count": len(retained_facts), "annotated_positions": annotated_positions,
            "context": context}


def context_redundancy(selected, vectors):
    """Use original sentences for every arm so granularity is not the metric."""
    units, dimension = [], None
    for chunk in selected:
        for fact in chunk["facts"]:
            value = _unit_vector(vectors, "search_document: " + chunk["title"] + "\n" + fact["text"], dimension)
            units.append(value)
            dimension = len(value)
    pairs = [_positive_cosine(left, right) for left, right in combinations(units, 2)]
    return {"mean_positive_cosine": float(sum(pairs) / len(pairs)) if pairs else 0.0,
            "sentence_pairs": len(pairs), "unit": "original sentence"}
