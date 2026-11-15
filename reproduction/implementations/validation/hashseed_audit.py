"""Post-collection, offline BM25 fingerprint audit; no model or source patches.

Run this file with the pinned research environment after restoring the published
archives. Each requested hash seed is applied to a fresh interpreter. The frozen
v2.core.ranking calls the original run.bm25 without rounding or replacement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGET = "5a739ef955429978a71e904b"
SCOPES = {
    "confirmatory-controlled": ("cohorts-amendment-01.json", "confirmatory", "confirmatory-controlled", "controlled"),
    "confirmatory-pooled": ("cohorts-amendment-01.json", "confirmatory", "confirmatory-pooled", "pooled"),
    "pilot-01-controlled": ("cohorts-amendment-01.json", "pilot", "pilot-01-controlled", "controlled"),
    "excluded-original-pilot": ("cohorts.json", "pilot", "pilot-controlled", "controlled"),
}


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(seed, scope, question_id):
    if os.environ.get("PYTHONHASHSEED") != str(seed):
        raise ValueError("Hash seed must be set before interpreter startup")
    sys.path.insert(0, str(ROOT))
    import run as original
    from v2.core import chunks, digest, documents, ranking

    scopes = list(SCOPES) if scope == "all" else [scope]
    records = []
    inputs = {}
    for label in scopes:
        cohort_name, split, run_name, environment = SCOPES[label]
        cohort_path = ROOT / "v3/data" / cohort_name
        cases = read(cohort_path)[split]
        out = ROOT / "v3/runs" / run_name
        preparation = read(out / "preparation.json")
        jobs = read(out / "jobs.json")
        stored = {j["question_id"]: j for j in jobs if j["retriever"] == "bm25"
                  and j["policy"] == "ranked" and j["budget"] == 512}
        fingerprints = {r["question_id"]: r for r in preparation["retrieval"]
                        if r["retriever"] == "bm25"}
        corpus = {d["key"]: d for case in cases for d in documents(case)}
        pooled = chunks([corpus[k] for k in sorted(corpus)]) if environment == "pooled" else None
        for path in (cohort_path, out / "preparation.json", out / "jobs.json"):
            inputs[str(path.relative_to(ROOT))] = sha(path)
        rows = []
        for case in cases:
            if question_id is not None and case["id"] != question_id:
                continue
            indexed = pooled if pooled is not None else chunks(documents(case))
            ranked = ranking(indexed, case["question"], "bm25", {})
            expected = fingerprints[case["id"]]["ranking_sha256"]
            actual = digest([c["id"] for c in ranked])
            saved = stored[case["id"]]["retrieved"]
            old_scores = {c["id"]: c["score"] for c in saved}
            row = {
                "question_id": case["id"], "expected_sha": expected,
                "replayed_sha": actual, "matches": actual == expected,
                "top_ten_matches": [c["id"] for c in ranked[:10]] == [c["id"] for c in saved],
                "current_top_ten": [c["id"] for c in ranked[:10]],
                "archived_top_ten": [c["id"] for c in saved],
                "max_common_top_ten_score_delta": max(
                    (abs(c["score"] - old_scores[c["id"]]) for c in ranked[:10]
                     if c["id"] in old_scores), default=0),
            }
            if question_id is not None:
                row.update({
                    "query_terms_iteration": list(set(original.words(case["question"]))),
                    "full_order": [c["id"] for c in ranked],
                    "full_scores": [c["score"] for c in ranked],
                })
            rows.append(row)
        if question_id is not None and not rows:
            raise ValueError("Question is absent from requested scope: " + label)
        records.append({
            "scope": label, "questions": len(rows),
            "fingerprint_mismatches": sum(not r["matches"] for r in rows),
            "top_ten_mismatches": sum(not r["top_ten_matches"] for r in rows),
            "cases": rows,
        })
    return {
        "schema": "alien6-rag-v3-postcollection-hashseed-replay-v1",
        "python_hash_seed": str(seed), "python": sys.version.split()[0],
        "scope": scope, "question_id": question_id, "collections": records,
        "source_sha256": {name: sha(ROOT / name)
                          for name in ("run.py", "v2/core.py", "v3/verify.py")},
        "input_sha256": inputs, "model_calls": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", default="10", help="Comma-separated interpreter hash seeds")
    parser.add_argument("--scope", choices=["all", *SCOPES], default="all")
    parser.add_argument("--question", help="Optional exact question ID; includes full order and scores")
    parser.add_argument("--output", type=Path, help="Write a new derived report; refuses overwrite")
    parser.add_argument("--worker", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker is not None:
        print(json.dumps(audit(args.worker, args.scope, args.question)))
        return
    seeds = [int(value) for value in args.seeds.split(",")]
    if not seeds or len(seeds) != len(set(seeds)) or any(not 0 <= s <= 4294967295 for s in seeds):
        raise ValueError("Seeds must be unique integers from 0 through 4294967295")
    reports = []
    for seed in seeds:
        command = [sys.executable, str(Path(__file__).resolve()), "--worker", str(seed), "--scope", args.scope]
        if args.question is not None:
            command.extend(["--question", args.question])
        result = subprocess.run(command, env={**os.environ, "PYTHONHASHSEED": str(seed)},
                                cwd=ROOT, capture_output=True, text=True, check=True)
        report = json.loads(result.stdout)
        reports.append(report)
        summary = {"seed": str(seed), "collections": [
            {k: v for k, v in collection.items() if k != "cases"}
            for collection in report["collections"]]}
        print(json.dumps(summary), file=sys.stderr)
    value = {"purpose": "post-collection computational replay; original collection seed was not recorded",
             "reports": reports}
    text = json.dumps(value, indent=2) + "\n"
    if args.output is not None:
        with args.output.open("x") as output:
            output.write(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
