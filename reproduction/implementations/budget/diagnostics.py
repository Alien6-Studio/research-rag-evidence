"""Descriptive stage-by-stage diagnostics, kept distinct from primary tests."""
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from v2.benchmark import COHORTS, lines, read, run_path


def classify(job, answer=None):
    retrieved = job["retrieved_sentence_coverage"]
    retained = job["evidence_coverage"]
    result = {"retrieval_annotation_gap": retrieved < 1,
              "packing_loses_retrieved_annotations": retained < retrieved,
              "complete_retrieval_but_incomplete_context": retrieved == 1 and retained < 1,
              "complete_annotated_context": retained == 1}
    if answer is not None:
        error = "error" in answer
        em = 0 if error else answer["metrics"]["answer_em"]
        result.update({"execution_error": error,
                       "explicit_abstention": not error and bool(answer["answer"]["abstain"]),
                       "exact_reference_match": bool(em),
                       "complete_context_zero_exact_match": retained == 1 and em == 0,
                       "incomplete_context_exact_match": retained < 1 and em == 1})
    return result


def main():
    for environment in ("controlled", "pooled"):
        out = run_path("confirmatory", environment)
        if not (out / "results.json").exists(): continue
        jobs = read(out / "jobs.json")
        answers = {a["id"]: a for a in lines(out / "answers.jsonl")}
        result = []
        for suffix in sorted({j["id"].split(":", 1)[1] for j in jobs}):
            selected = [j for j in jobs if j["id"].endswith(":" + suffix)]
            deterministic = Counter()
            generated = Counter()
            contingency = Counter()
            details = []
            for job in selected:
                flags = classify(job, answers.get(job["id"]))
                deterministic.update({k: int(v) for k, v in classify(job).items()})
                if job["id"] in answers:
                    generated.update({k: int(v) for k, v in flags.items()})
                    contingency[(int(flags["complete_annotated_context"]), int(flags["exact_reference_match"]))] += 1
                    details.append({"question_id": job["question_id"], **flags})
            result.append({"configuration": suffix, "deterministic_questions": len(selected),
                           "deterministic_flags": dict(deterministic),
                           "generation_questions": len(details), "generation_flags": dict(generated),
                           "coverage_exact_match_table": [{"complete_context": c, "exact_match": e, "questions": contingency[(c, e)]} for c in (0, 1) for e in (0, 1)],
                           "question_flags": details})
        value = {"environment": environment, "analysis_role": "descriptive diagnostics, not additional confirmatory hypotheses",
                 "semantic_caution": "Annotation gaps, zero exact matches, and missing annotated citations are review flags, not established factual errors or hallucinations. Complete annotated context is not documentary faithfulness.",
                 "arms": result}
        (out / "diagnostics.json").write_text(json.dumps(value, indent=2) + "\n")
        if answers: plot_relationship(value, out)
        plot_effects(read(out / "results.json"), out)
        print(environment, "stage diagnostics reconstructed")


def plot_relationship(result, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(11, 5.3), layout="constrained")
    bottom = [0] * len(result["arms"])
    for complete, exact, color, label in [(1, 1, "#07845c", "Complete annotated context; exact match"),
                                          (1, 0, "#8ccfb7", "Complete annotated context; no exact match"),
                                          (0, 1, "#17283a", "Partial annotated context; exact match"),
                                          (0, 0, "#b7c0c8", "Partial annotated context; no exact match")]:
        counts = [next(r["questions"] for r in a["coverage_exact_match_table"] if (r["complete_context"], r["exact_match"]) == (complete, exact)) for a in result["arms"]]
        ax.bar(range(len(counts)), counts, bottom=bottom, color=color, label=label)
        bottom = [a + b for a, b in zip(bottom, counts, strict=True)]
    ax.set_xticks(range(8), [a["configuration"].replace(":", "\n") for a in result["arms"]], fontsize=9)
    ax.set_ylabel("Questions, out of the same 128 generation cases")
    ax.set_title(f"{result['environment']}: retained annotations and lexical answers")
    ax.legend(loc="upper center", bbox_to_anchor=(.5, -.18), ncol=2, frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    for extension in ("png", "svg"): fig.savefig(out / f"evidence-and-lexical-outcomes.{extension}", dpi=160, bbox_inches="tight")
    plt.close(fig)


def plot_effects(result, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    contrasts = result["preservation_family"][:2]
    contrasts += [c for c in result["lexical_family"] if c["metric"] == "answer_em"]
    if not contrasts: return
    fig, ax = plt.subplots(figsize=(8.8, 4.8), layout="constrained")
    labels = []
    for i, row in enumerate(contrasts):
        center = row["mean_difference"] * 100
        low, high = [v * 100 for v in row["bonferroni_family_interval"]]
        ax.errorbar(center, i, xerr=[[center - low], [high - center]], fmt="o", color="#07845c" if row["metric"] == "complete_context" else "#17283a", capsize=4)
        label = "complete annotated context" if row["metric"] == "complete_context" else "exact reference match"
        labels.append(f"{row['after'].split(':')[0].upper()} · {label} · n={row['questions']}")
    ax.axvline(0, color="#85978d", linestyle="--", linewidth=1)
    ax.set_yticks(range(len(labels)), labels, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel("Paired change for 1536 versus 512 tokens (percentage points)")
    ax.set_title(f"{result['environment']}: budget effects with simultaneous intervals")
    ax.spines[["top", "right"]].set_visible(False)
    for extension in ("png", "svg"): fig.savefig(out / f"paired-budget-effects.{extension}", dpi=160, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__": main()
