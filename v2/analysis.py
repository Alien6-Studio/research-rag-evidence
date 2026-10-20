"""Rebuild paired lexical and preservation results without a model server."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np

from v2.benchmark import COHORTS, file_sha, lines, payload_for, read, run_path
from v2.core import answer_metrics, digest, exact_mcnemar, holm, paired_interval

PRESERVATION = [
    ("bm25:ranked:512", "bm25:ranked:1536"),
    ("dense:ranked:512", "dense:ranked:1536"),
    ("bm25:ranked:512", "bm25:diverse:512"),
    ("dense:ranked:512", "dense:diverse:512"),
    ("bm25:ranked:512", "dense:ranked:512"),
]


def paired(jobs, ids, before, after, metric, family, answers=None):
    kinds = [jobs[f"{q}:{before}"]["type"] for q in ids]
    left, right, details = [], [], []
    for q in ids:
        a, b = jobs[f"{q}:{before}"], jobs[f"{q}:{after}"]
        if answers is None:
            l, r = a[metric], b[metric]
        else:
            def value(job):
                record = answers[job["id"]]
                if metric == "unanswered":
                    return int("error" in record or record["answer"]["abstain"])
                return 0 if "error" in record else record["metrics"][metric]
            l, r = value(a), value(b)
        left.append(l); right.append(r)
        details.append({"question_id": q, "before": l, "after": r,
                        "coverage_before": a["evidence_coverage"], "coverage_after": b["evidence_coverage"],
                        "identical_request": payload_for(a) == payload_for(b)})
    result = {"before": before, "after": after, "metric": metric, "questions": len(ids),
              **paired_interval(left, right, kinds, family=family),
              "question_details": details,
              "identical_requests": sum(x["identical_request"] for x in details),
              "changed_results_under_identical_requests": [x["question_id"] for x in details if x["identical_request"] and x["before"] != x["after"]]}
    if all(x in (0, 1) for x in left + right):
        result.update(exact_mcnemar(left, right))
    return result


def adjust(rows):
    for row, value in zip(rows, holm([r["p_exact"] for r in rows]), strict=True):
        row["p_holm"] = value
        row["reject_at_family_005"] = value <= .05


def analyse(environment):
    out = run_path("confirmatory", environment)
    preparation = read(out / "preparation.json")
    if file_sha(out / "jobs.json") != preparation["jobs_sha256"]:
        raise ValueError("Prepared inputs changed")
    cases = {c["id"]: c for c in read(COHORTS)["confirmatory"]}
    ids = sorted(cases)
    job_list = read(out / "jobs.json")
    jobs = {j["id"]: j for j in job_list}
    if len(jobs) != len(job_list) or len(jobs) != 2048:
        raise ValueError("Incomplete or duplicate deterministic conditions")
    coverage = [paired(jobs, ids, before, after, "complete_context", 5) for before, after in PRESERVATION]
    adjust(coverage)
    fractional = [paired(jobs, ids, before, after, "evidence_coverage", 5) for before, after in PRESERVATION]
    summaries = []
    answers = {a["id"]: a for a in lines(out / "answers.jsonl")}
    planned = read(COHORTS)["generation_ids"] if environment == "controlled" else []
    expected = {j["id"] for j in job_list if j["question_id"] in planned}
    complete = bool(planned) and set(answers) == expected
    if answers and not set(answers) <= expected:
        raise ValueError("Unexpected generation IDs")
    for key, record in answers.items():
        if record.get("request") is not None and record["request"] != payload_for(jobs[key]):
            raise ValueError("Archived request differs from prepared context")
        if "error" not in record:
            response = json.loads(record["response_body"])
            parsed = json.loads(response["message"]["content"])
            if parsed != record["answer"] or answer_metrics(cases[jobs[key]["question_id"]], jobs[key], parsed) != record["metrics"]:
                raise ValueError("Stored generated answer or score differs")
    for suffix in sorted({j["id"].split(":", 1)[1] for j in job_list}):
        group = [j for j in job_list if j["id"].endswith(":" + suffix)]
        generated = [answers[j["id"]] for j in group if j["id"] in answers]
        successful = [a for a in generated if "error" not in a]
        row = {"configuration": suffix, "deterministic_questions": len(group),
               "complete_context_count": sum(j["complete_context"] for j in group),
               "mean_sentence_coverage": float(np.mean([j["evidence_coverage"] for j in group])),
               "mean_passage_recall10": float(np.mean([j["recall10"] for j in group])),
               "mean_context_tokens": float(np.mean([j["context_tokens"] for j in group])),
               "generation_observed": len(generated), "generation_planned": len(planned),
               "errors": len(generated) - len(successful),
               "exact_matches": sum(a["metrics"]["answer_em"] for a in successful),
               "model_abstentions": sum(a["metrics"]["abstain"] for a in successful),
               "mean_f1_all_planned": sum(a["metrics"]["answer_f1"] for a in successful) / len(planned) if complete else None,
               "complete_context_with_zero_exact_match": [j["question_id"] for j in group if j["complete_context"] and j["id"] in answers and ("error" in answers[j["id"]] or not answers[j["id"]]["metrics"]["answer_em"])]}
        summaries.append(row)
    lexical = []
    if complete:
        for before, after in PRESERVATION[:2]:
            for metric in ("answer_em", "unanswered"):
                lexical.append(paired(jobs, sorted(planned), before, after, metric, 4, answers))
        adjust(lexical)
    exploratory = []
    if complete:
        for before, after in PRESERVATION:
            for metric in ("answer_em", "answer_f1", "unanswered"):
                exploratory.append(paired(jobs, sorted(planned), before, after, metric, 1, answers))
    duplicate_groups = defaultdict(list)
    for job in job_list:
        duplicate_groups[digest(payload_for(job))].append(job["id"])
    repeated = []
    for repeat in (1, 2):
        records = lines(out / f"answers-repeat-{repeat}.jsonl")
        changes = []
        for item in records:
            if item.get("request") is not None and item["request"] != payload_for(jobs[item["id"]]):
                raise ValueError("A repeat changed the request")
            base = answers.get(item["id"])
            if base and "error" not in base and "error" not in item and item["answer"] != base["answer"]:
                changes.append({"id": item["id"], "primary": base["answer"], "repeat": item["answer"]})
        repeated.append({"repeat": repeat, "observed": len(records), "planned": 16 if environment == "controlled" else 0, "changed_answers_or_citations": changes})
    result = {"environment": environment,
              "analysis_role": "confirmatory prespecified families" if environment == "controlled" else "separate exploratory pooled-corpus experiment; no confirmatory claim",
              "status": "complete lexical collection; human semantic adjudication pending" if complete else "deterministic results only; generation incomplete or not planned",
              "questions": len(ids), "jobs_sha256": preparation["jobs_sha256"],
              "registration_sha256": preparation["registration_sha256"],
              "generation_sha256": file_sha(out / "answers.jsonl") if answers else None,
              "arms": summaries, "preservation_family": coverage,
              "fractional_coverage_secondary": fractional, "lexical_family": lexical,
              "exploratory_response_contrasts": exploratory,
              "identical_prompt_groups": [group for group in duplicate_groups.values() if len(group) > 1],
              "stability": repeated, "semantic_validation": {"status": "pending two independent human reviewers and arbitration", "observed": None},
              "inference_limits": ["Lexical matching is not factual correctness.", "Annotated evidence coverage is not semantic faithfulness.", "Pooled and ten-paragraph results are separate experiments.", "Eight correlated settings do not multiply the independent sample size.", "Support-title-disjoint sampling does not remove all dependence or model pretraining contamination."]}
    destination = out / "results.json"
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    report(result, out)
    figures(result, out)
    print(json.dumps({"environment": environment, "status": result["status"], "questions": len(ids), "primary_answers": len(answers)}, indent=2))


def report(result, out):
    rows = ["# Prospective V2 results", "", f"Environment: **{result['environment']}**. {result['status']}.", "",
            result["analysis_role"], "",
            "Semantic correctness and documentary support remain unmeasured until independent human adjudication. Exact matches below are lexical observations.", "",
            "| Configuration | Complete annotated context /256 | Mean passage recall@10 | Answers observed/planned | Exact matches | Abstentions | Execution errors |",
            "|---|---:|---:|---:|---:|---:|---:|"]
    for a in result["arms"]:
        rows.append(f"| {a['configuration']} | {a['complete_context_count']} | {a['mean_passage_recall10']:.3f} | {a['generation_observed']}/{a['generation_planned']} | {a['exact_matches'] if a['generation_observed'] else 'not measured'} | {a['model_abstentions'] if a['generation_observed'] else 'not measured'} | {a['errors'] if a['generation_observed'] else 'not measured'} |")
    rows += ["", "## Prespecified paired contrasts", "", "Intervals resample the same questions within type (10,000 draws). Holm correction is applied within the five preservation and four lexical/composite comparisons. Simultaneous conservative intervals use Bonferroni within each family.", "",
             "| Family | Before → after | Outcome | Paired difference | 95% interval | Holm p |",
             "|---|---|---|---:|---|---:|"]
    for family, contrasts in [("preservation", result["preservation_family"]), ("lexical", result["lexical_family"])]:
        for c in contrasts:
            low, high = c["ci95"]
            rows.append(f"| {family} | {c['before']} → {c['after']} | {c['metric']} | {c['mean_difference']:+.4f} | [{low:+.4f}, {high:+.4f}] | {c['p_holm']:.5g} |")
    rows += ["", "The unanswered composite includes explicit abstentions and execution/format failures. These are separately reported; execution errors must not be described as model abstentions.", "",
             "Identical requests are recorded in results.json. A changed answer under an identical request cannot be attributed to a different context-selection policy.", "",
             "## Limits", "", *[f"- {limit}" for limit in result["inference_limits"]], "",
             "Question-level transitions, negative changes, complete-context lexical failures, and repeat differences remain in results.json. Original source annotations and historical scores are unchanged."]
    (out / "RESULTS.md").write_text("\n".join(rows) + "\n")


def figures(result, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 4.8), layout="constrained")
    values = [r["complete_context_count"] for r in result["arms"]]
    bars = ax.bar(range(8), values, color="#07845c")
    ax.bar_label(bars, labels=[f"{v}/256" for v in values], padding=3)
    ax.set_xticks(range(8), [r["configuration"].replace(":", "\n") for r in result["arms"]], fontsize=9)
    ax.set_ylim(0, 280)
    ax.set_ylabel("Questions retaining all annotated sentences")
    ax.set_title(f"V2 {result['environment']}: transmitted annotated evidence")
    ax.spines[["top", "right"]].set_visible(False)
    for extension in ("png", "svg"):
        fig.savefig(out / f"evidence-preservation.{extension}", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", choices=["controlled", "pooled"], required=True)
    analyse(parser.parse_args().environment)
