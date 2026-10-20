"""Retrospective independent checks; never overwrite historical observations."""
from collections import Counter, defaultdict
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pyarrow.parquet as pq
from tokenizers import Tokenizer

import importlib.util

# Execute the byte-preserved analysis whose self-hash is recorded in the raw-era
# results. The current convenience CLI has a different report destination.
_spec = importlib.util.spec_from_file_location(
    'captured_historical_analysis', ROOT / 'analysis/2026-11-12-rag/analysis.py')
historical_analysis = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(historical_analysis)
import run as historical
from vendor.hotpot_evaluate_v1 import exact_match_score, f1_score
from v2.benchmark import archived_vectors, file_sha, lines, read
from v2.core import chunks, documents

OUT = ROOT / "v2/reports/audit"
RUN = ROOT / "runs/2026-11-12-rag"

def reference_bm25(candidates, question):
    """Separate implementation of the documented bag-of-words formula."""
    bags = [Counter(re.findall(r"\w+", c["text"].lower())) for c in candidates]
    lengths = [sum(bag.values()) for bag in bags]
    average = sum(lengths) / len(lengths)
    terms = sorted(set(re.findall(r"\w+", question.lower())))
    result = []
    for bag, length in zip(bags, lengths, strict=True):
        result.append(sum(math.log(1 + (len(bags) - sum(term in b for b in bags) + .5) /
                                   (sum(term in b for b in bags) + .5)) *
                          bag[term] * (1.5 + 1) /
                          (bag[term] + 1.5 * (1 - .75 + .75 * length / average))
                          for term in terms if bag[term]))
    return result


def verify_unchanged():
    baseline = read(ROOT / "v2/data/historical-inputs.json")
    checked = 0
    for name, expected in baseline["files"].items():
        if file_sha(ROOT / name) != expected:
            raise ValueError(f"Historical file changed: {name}")
        checked += 1
    return checked


def audit(check=False):
    OUT.mkdir(parents=True, exist_ok=True)
    unchanged = verify_unchanged()
    source = read(ROOT / "sources.json")
    assert file_sha(ROOT / "data/hotpot-validation.parquet") == source["dataset"]["sha256"]
    assert file_sha(ROOT / "data/qwen-tokenizer.json") == source["tokenizer"]["sha256"]
    assert file_sha(ROOT / "vendor/hotpot_evaluate_v1.py") == source["evaluator"]["sha256"]
    cases = read(RUN / "cases.json")
    assert historical.load_cases() == cases
    jobs = {j["id"]: j for j in read(RUN / "jobs.json")}
    answers = {a["id"]: a for a in lines(RUN / "answers.jsonl")}
    tokenizer = Tokenizer.from_file(str(ROOT / "data/qwen-tokenizer.json"))
    vectors = archived_vectors()
    rankings = 0
    checked_contexts = 0
    within_type = Counter()
    answer_done = Counter()
    for case in cases:
        built = chunks(documents(case))
        for method in ("bm25", "dense"):
            if method == "bm25":
                scores = reference_bm25(built, case["question"])
                assert np.allclose(scores, historical.bm25(built, case["question"]), atol=1e-12, rtol=0)
            else:
                query = np.asarray(vectors["search_query: " + case["question"]])
                matrix = np.asarray([vectors["search_document: " + c["text"]] for c in built])
                scores = (matrix @ query) / (np.linalg.norm(matrix, axis=1) * np.linalg.norm(query))
            order = sorted(range(len(built)), key=lambda i: (-float(scores[i]), built[i]["id"]))
            saved = jobs[f"{case['id']}:{method}:ranked:512"]["retrieved"]
            assert [built[i]["id"] for i in order[:10]] == [c["id"] for c in saved]
            assert all(abs(float(scores[i]) - c["score"]) < 1e-10 for i, c in zip(order[:10], saved, strict=True))
            rankings += 1
        gold = set(zip(case["supporting_facts"]["title"], case["supporting_facts"]["sent_id"], strict=True))
        source_facts = {f["id"]: f for c in built for f in c["facts"]}
        for method in ("bm25", "dense"):
            for policy in ("ranked", "diverse"):
                for budget in (512, 1536):
                    job = jobs[f"{case['id']}:{method}:{policy}:{budget}"]
                    record = answers[job["id"]]
                    context = record["raw"]["request"]["messages"][1]["content"].split("\n\nEvidence:\n", 1)[1]
                    assert context == job["context"]
                    transmitted_ids = re.findall(r"^\[(d\d+s\d+)\] ", context, re.M)
                    facts = {(source_facts[key]["title"], source_facts[key]["sentence"]) for key in transmitted_ids}
                    assert len(gold & facts) / len(gold) == job["evidence_coverage"]
                    assert len(tokenizer.encode(context).ids) == job["context_tokens"] <= budget
                    parsed = json.loads(record["raw"]["response"]["message"]["content"])
                    predicted = "" if parsed["abstain"] else parsed["answer"]
                    assert int(exact_match_score(predicted, case["answer"])) == record["metrics"]["answer_em"]
                    assert f1_score(predicted, case["answer"])[0] == record["metrics"]["answer_f1"]
                    assert record["raw"]["request"]["options"] == historical.OPTIONS
                    answer_done[record["raw"]["response"].get("done_reason", "missing")] += 1
                    checked_contexts += 1
        within_type[case["type"]] += 1
    # Re-run the complete original aggregate/interval program in a new destination.
    saved=historical_analysis.OUT,historical_analysis.report,historical_analysis.figures
    try:
        with tempfile.TemporaryDirectory() as temporary:
            historical_analysis.OUT = Path(temporary)
            historical_analysis.report = lambda result: None
            historical_analysis.figures = lambda result: None
            historical_analysis.analyse()
            recomputed = read(historical_analysis.OUT / "results.json")
    finally:
        historical_analysis.OUT,historical_analysis.report,historical_analysis.figures=saved
    archived = read(ROOT / "analysis/2026-11-12-rag/results.json")
    for key in set(archived) - {"analysis_utc"}:
        assert recomputed[key] == archived[key], key
    controls = lines(RUN / "generator-controls.jsonl")
    gold_controls = []
    for case in cases[:16]:
        record = next(c for c in controls if c["id"] == case["id"] + ":gold_evidence")
        parsed = json.loads(record["raw"]["response"]["message"]["content"])
        assert parsed == record["answer"]
        predicted = "" if parsed["abstain"] else parsed["answer"]
        assert int(exact_match_score(predicted, case["answer"])) == record["answer_em"]
        assert f1_score(predicted, case["answer"])[0] == record["answer_f1"]
        gold = historical.gold_facts(case)
        evidence = [{**c, "facts": [f for f in c["facts"] if (f["title"], f["sentence"]) in gold]}
                    for c in historical.chunks_for(case) if historical.fact_set([c]) & gold]
        expected = f"Question: {case['question']}\n\nEvidence:\n{historical.render_context(evidence)}"
        assert record["raw"]["request"]["messages"] == [{"role":"system","content":historical.SYSTEM}, {"role":"user","content":expected}]
        gold_controls.append(record)
    manifest = read(RUN / "manifest.json")
    by_title = defaultdict(list)
    for case in cases:
        for title in set(case["context"]["title"]): by_title[title].append(case["id"])
    summary = {"audit_utc": datetime.now(timezone.utc).isoformat(), "auditor_sha256": file_sha(Path(__file__)),
               "historical_files_unchanged": unchanged, "selected_question_ids_reproduced": 64,
               "question_types": dict(within_type), "independently_recomputed_rankings": rankings,
               "independently_checked_transmitted_contexts_and_lexical_scores": checked_contexts,
               "historical_aggregate_and_intervals_reproduced": True,
               "generator_completion_reasons": dict(answer_done),
               "control_question_types": dict(Counter(c["type"] for c in cases[:16])),
               "gold_control_count":len(gold_controls),
               "gold_control_exact_matches":sum(r["answer_em"] for r in gold_controls),
               "shared_any_context_titles": {title: ids for title, ids in by_title.items() if len(ids) > 1},
               "models_and_parameters_declared": {"models": manifest["models"], "options": manifest["options"], "ollama": manifest["ollama"]},
               "interpretation_limit": "Source hashes identify the measured instrument. No semantic labels are produced by this audit.",
               "semantic_validation_status": "pending independent humans"}
    if check:
        expected=read(OUT/'audit-results.json')
        if {k:v for k,v in summary.items() if k != 'audit_utc'} != {k:v for k,v in expected.items() if k != 'audit_utc'}:
            raise ValueError('Recorded numerical audit does not reproduce')
    else:
        (OUT / "audit-results.json").write_text(json.dumps(summary, indent=2) + "\n")
    assert verify_unchanged() == unchanged
    print(json.dumps({k: v for k, v in summary.items() if k not in ["shared_any_context_titles", "models_and_parameters_declared"]}, indent=2))


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    audit(parser.parse_args().check)
