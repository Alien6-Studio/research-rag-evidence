"""Build the final readable study from the complete archived observations."""
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vendor.hotpot_evaluate_v1 import normalize_answer
from v2.benchmark import COHORTS, lines, read, run_path


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def interval(row, simultaneous=False):
    low, high = row["bonferroni_family_interval"] if simultaneous else row["ci95"]
    return f"{100 * row['mean_difference']:+.1f} [{100 * low:+.1f}, {100 * high:+.1f}]"


def main():
    controlled_dir = run_path("confirmatory", "controlled")
    pooled_dir = run_path("confirmatory", "pooled")
    controlled, pooled = read(controlled_dir / "results.json"), read(pooled_dir / "results.json")
    diagnostic = read(controlled_dir / "diagnostics.json")
    if any(a["generation_observed"] != 128 for a in controlled["arms"]):
        raise ValueError("The final report requires all 1,024 primary observations")
    answers = {a["id"]: a for a in lines(controlled_dir / "answers.jsonl")}
    jobs = {j["id"]: j for j in read(controlled_dir / "jobs.json")}
    cohort = read(COHORTS)
    audit = read(ROOT / "v2/reports/audit/audit-results.json")
    preparation = read(pooled_dir / "preparation.json")
    text = ["# Following evidence from retrieval to answer", "",
            "A search system can find a useful passage without placing it in the text a language model actually reads. A model can also give a reasonable answer that fails a strict reference-string comparison. This study separates those two problems instead of interpreting one aggregate answer score as an explanation.", "",
            "We follow the same questions through retrieval, context selection, and generation. The measurements below concern retained annotated sentences and lexical answer agreement. Factual correctness and documentary support have not been independently adjudicated.", "",
            "## Experimental design", "",
            "| Component | Questions | Purpose |",
            "|---|---:|---|",
            "| Exploratory cohort | 64 | Audit the existing eight-condition experiment and answer controls |",
            "| Technical pilot | 8 | Check all eight requests per question, tokenization, output format, and truncation |",
            "| Controlled preservation study | 256 | Compare retrieval and context selection without requiring generation |",
            "| Controlled answer study | 128 of those 256 | Eight configurations each: 1,024 primary responses |",
            "| Stability checks | 16 of those 128 | Two additional identical-request passes: 32 responses |",
            "| Pooled-corpus study | The same 256 | Separate exploratory retrieval/context experiment; no generation arm |", "",
            "The 256 cases contain 128 bridge and 128 comparison questions. The generation subset contains 64 of each. Selection was seeded and fixed before inspecting the answers. Pilot and confirmation questions reuse neither question IDs, normalized question texts, nor supporting-document titles from the exploratory cohort. The newly selected questions are mutually disjoint under those checks. This prevents direct support-document reuse; it does not eliminate common topics, shared distractors, or public-dataset pretraining exposure.", "",
            "The controlled setting searches only the ten paragraphs supplied with each HotpotQA question. It is a controlled candidate-set experiment, not open-Wikipedia retrieval. Chunks contain three original sentences. We compare BM25 and dense retrieval, ranked and document-diverse packing, and budgets of 512 and 1,536 tokens. Retrieval and packing never receive answer references or supporting-fact flags.", "",
            "The pinned Qwen generator, nomic embedding model, prompts, and generation settings are kept fixed. A context budget counts the fully rendered titles, sentence IDs, and separators. Whole chunks that do not fit are skipped. The technical pilot passed all 64 requests and the three tokenizer probes without using answer quality as a pass criterion.", "",
            "## What the audit establishes", "",
            f"The audit reconstructed the 64 selected IDs, {audit['independently_recomputed_rankings']} retrieval rankings, and all {audit['independently_checked_transmitted_contexts_and_lexical_scores']} transmitted contexts and lexical scores. The original aggregates and paired bootstrap intervals reproduce. Raw observations, original annotations, and recorded scores are unchanged.", "",
            "BM25 follows the documented bag-of-words formula; dense search uses cosine similarity of the preserved vectors. Annotated passage recall and annotated sentence coverage have different denominators. Token budgets are checked against the rendered context, and the archived user prompt must contain exactly that context. Annotations enter scoring and source validation, not ranking or selection.", "",
            "The initial sample has 64 questions, not 512 independent observations. Shared supporting-document titles connect a few of those questions; the supplied cluster-bootstrap sensitivity analysis keeps that limitation visible. Its sixteen diagnostic controls are the first sorted question IDs, including ten comparison and six bridge questions. They are useful cases to inspect, not a representative estimate of factual accuracy.", "",
            "### Why five exact matches out of sixteen is not an accuracy estimate", "",
            "The gold-evidence controls give five exact reference matches out of sixteen. Neither that count nor a zero lexical score establishes semantic correctness. The supplied references, answers and contexts remain available for independent human rubric calibration. This diagnostic subset is not a representative accuracy sample.", "",
            "The automated faithfulness proxy also rejects four of sixteen nominal positive controls. One of those controls asks which documentary was more successful without defining success or supplying comparable evidence. Its reference label cannot simply be assumed to establish entailment. The observed positive-control rate therefore does not calibrate the judge into a truth oracle.", "",
            "## Controlled results", "",
            "Context completeness uses all 256 questions. Answer scores use the fixed 128-question subset. The two denominators must not be compared as if they counted the same sample.", "",
            "| Configuration | Complete annotated context /256 | Exact matches /128 | Explicit abstentions /128 | Invalid/failed outputs /128 | Mean lexical F1 |",
            "|---|---:|---:|---:|---:|---:|"]
    for arm in controlled["arms"]:
        text.append(f"| {arm['configuration']} | {arm['complete_context_count']} | {arm['exact_matches']} | {arm['model_abstentions']} | {arm['errors']} | {arm['mean_f1_all_planned']:.3f} |")
    failures = [record for record in answers.values() if "error" in record]
    if failures:
        noun = "One invalid output remains" if len(failures) == 1 else f"{len(failures)} invalid outputs remain"
        text += ["", f"{noun} in the denominator, without regeneration. A recorded response returns an answer and citation while setting `abstain=true`, violating the registered consistency instruction despite having valid JSON. This is an output-consistency failure. Explicit abstention counts above exclude invalid outputs; the unanswered composite includes both."]
    text += ["", "![Retained annotations and lexical outcomes](v2/runs/confirmatory-controlled/evidence-and-lexical-outcomes.png)", "",
             "A complete annotated context and an exact answer match are separate outcomes. An exact match with partial annotated evidence can reflect sufficient alternative text, prior knowledge, or incomplete annotations. A zero exact match with complete annotated evidence can reflect generation, prompt constraints, reference wording, or source ambiguity. Neither flag identifies factual error on its own.", "",
             "### Protocol-specified paired comparisons", "",
             "Each difference compares the same questions. Intervals resample questions within type with 10,000 draws. The five preservation tests and four lexical/composite tests each use Holm correction. The intervals below are conservative simultaneous intervals within the corresponding family; all unadjusted intervals and individual gains/losses remain in the result data.", "",
             "| Comparison | Outcome | Questions | Difference in percentage points [simultaneous interval] | Holm p |",
             "|---|---|---:|---|---:|"]
    for row in controlled["preservation_family"] + controlled["lexical_family"]:
        text.append(f"| {row['before']} → {row['after']} | {row['metric']} | {row['questions']} | {interval(row, True)} | {row['p_holm']:.5g} |")
    text += ["", "The unanswered composite includes explicit abstentions and execution/format failures; the preceding table keeps those counts separate. F1 and the other response contrasts are exploratory. A significant lexical change is not a demonstrated improvement in factual truth.", "",
             "![Paired budget effects](v2/runs/confirmatory-controlled/paired-budget-effects.png)", "",
             "### Locate the annotated-information gaps", "",
             "| Configuration | Retrieval misses some annotations /256 | Packing discards retrieved annotations /256 | Complete retrieval, incomplete context /256 | Complete context, zero exact match /128 |",
             "|---|---:|---:|---:|---:|"]
    for arm in diagnostic["arms"]:
        d, g = arm["deterministic_flags"], arm["generation_flags"]
        text.append(f"| {arm['configuration']} | {d['retrieval_annotation_gap']} | {d['packing_loses_retrieved_annotations']} | {d['complete_retrieval_but_incomplete_context']} | {g['complete_context_zero_exact_match']} |")
    text += ["", "These gap counts can overlap and must not be added to estimate independent failures. They locate annotated-information loss; they do not allocate every apparent answer failure to a unique cause.", "",
             "### Results by question type", "",
             "| Configuration | Bridge exact matches /64 | Comparison exact matches /64 |",
             "|---|---:|---:|"]
    for arm in controlled["arms"]:
        suffix = arm["configuration"]
        counts = Counter()
        for key, answer in answers.items():
            if key.endswith(":" + suffix) and "error" not in answer:
                counts[jobs[key]["type"]] += answer["metrics"]["answer_em"]
        text.append(f"| {suffix} | {counts['bridge']} | {counts['comparison']} |")
    text += ["", "This type breakdown is descriptive. Balanced types do not establish the distribution of questions in a customer corpus.", "",
             "## Separate pooled-corpus experiment", "",
             f"The common corpus contains {preparation['corpus_paragraphs']:,} distinct title/sentence-array paragraph versions and {preparation['retrieval'][0]['indexed_chunks']:,} three-sentence chunks, built from the 256 questions' supplied public paragraphs. All relevant annotated paragraphs are present by construction. Every query searches this complete shared index; its own ten paragraphs are not preselected at retrieval time. This creates more competition while retaining an intentionally restricted, question-derived corpus.", "",
             "The following results are exploratory and are kept separate from the controlled experiment. They do not estimate unrestricted search or production behavior.", "",
             "| Configuration | Mean passage Recall@10 | Complete annotated context /256 | Mean annotated-sentence coverage |",
             "|---|---:|---:|---:|"]
    for arm in pooled["arms"]:
        text.append(f"| {arm['configuration']} | {arm['mean_passage_recall10']:.3f} | {arm['complete_context_count']} | {arm['mean_sentence_coverage']:.3f} |")
    text += ["", "Pooled document IDs are global and can consume more tokens than the controlled setting's short IDs. Comparisons between corpora therefore include identifier overhead as well as retrieval competition; comparisons within each environment keep that formatting fixed.", "",
             "![Pooled-corpus annotated evidence](v2/runs/confirmatory-pooled/evidence-preservation.png)", "",
             "## Identical prompts and stability", ""]
    duplicate = controlled["identical_prompt_groups"]
    actual_duplicate = [group for group in duplicate if sum(key in answers for key in group) > 1]
    text.append(f"Among the 2,048 prepared controlled requests, {len(duplicate)} groups have identical complete payloads across configuration labels. Of those groups, {len(actual_duplicate)} contain at least two actually generated requests in the fixed answer subset. They are retained explicitly rather than credited as different model inputs. A changed answer under an identical request is generation variability, not a selection-policy effect.")
    text += ["", "| Actual answer-study comparison | Identical request pairs /128 | Changed exact score under an identical request |",
             "|---|---:|---:|"]
    for row in controlled["exploratory_response_contrasts"]:
        if row["metric"] == "answer_em":
            text.append(f"| {row['before']} → {row['after']} | {row['identical_requests']} | {len(row['changed_results_under_identical_requests'])} |")
    text += ["", "| Additional pass | Identical planned requests | Changed normalized answer/abstention | Changed citation set | Unusable comparison pairs |",
             "|---|---:|---:|---:|---:|"]
    for repeat in (1, 2):
        records = lines(controlled_dir / f"answers-repeat-{repeat}.jsonl")
        changes = citations = errors = 0
        for record in records:
            base = answers[record["id"]]
            if "error" in record or "error" in base: errors += 1; continue
            left, right = base["answer"], record["answer"]
            changes += (left["abstain"], normalize_answer(left["answer"])) != (right["abstain"], normalize_answer(right["answer"]))
            citations += set(left["citations"]) != set(right["citations"])
        text.append(f"| {repeat} | {len(records)} | {changes} | {citations} | {errors} |")
    text += ["", "These sixteen questions do not establish stability on every question or across models and machines. Temperature zero is not a proof of deterministic generation.", "",
             "## Independent semantic validation", "",
             "All 1,024 primary outputs require two independent human reviews. Phase one judges exact-context support, citation-only support, citation IDs and abstention justification without a reference answer. After both submissions are locked, phase two reveals references and complete original paragraphs for correctness and reference-adequacy judgements. A third independent human arbitrates categorical disagreements with reasons.", "",
             "[The annotation guide](v2/ANNOTATION.md) and executable workflow generate separately randomized packets, keep mapping keys outside the public repository, enforce phase release, preserve both independent submissions and report agreement before arbitration. Null templates are not annotations. The semantic family remains unavailable until the complete agreed/adjudicated labels exist; lexical matches and automatic judges never fill missing human decisions.", "",
             "## What can be said in the article", "",
             "**Supported by the measurements:** retrieval and context selection are distinct points of annotated-evidence loss. The same top-ten results can produce different retained evidence under a changed budget or packing policy. The tables quantify those changes on the fixed cohort, including negative outcomes.", "",
             "**Conditional observations:** the answer study measures lexical agreement, F1, abstention, and execution failure for one quantized model and the registered settings. Paired estimates and their uncertainty describe those outcomes; they do not identify a universally better retriever or establish that retaining more annotations causes more truthful answers.", "",
             "**Still open:** semantic correctness, whether the exact cited or transmitted text supports each answer, and the share of true answer failures attributable to generation versus evaluation. The controls show why a zero lexical score cannot answer those questions. There is no independently adjudicated semantic result to substitute for that missing measurement.", "",
             "## Limits", "",
             "The sample is English, public, balanced by type, and selected with document-disjoint eligibility rules. A public pretrained model may already know some questions. All primary generation results use one local model and workstation. Replaying cached vectors, packing, and scoring checks calculations; it does not repeat model generation on independent hardware. Host timing records are not a qualified latency, throughput, energy, or cost benchmark.", "",
             "The approximate power scenarios are in [the sampling data](v2/data/power-planning.json). Under the stated 10–50% discordance assumptions and conservative alpha .01, the 80%-power detectable differences are roughly 9.6–21.4 percentage points at 128 questions and 6.8–15.1 at 256. These are planning assumptions, not observed power. Small response effects can remain inconclusive after multiplicity correction. Failure to reject a null is not evidence of equivalence. No production or financial claim follows from either corpus.", "",
             "HotpotQA-derived data retains attribution to Yang, Qi, Zhang et al., EMNLP 2018, and its CC BY-SA 4.0 license. Code and original evaluator licensing are preserved in the repository."]
    (ROOT / "RESULTS.md").write_text("\n".join(text) + "\n")
    print("Built RESULTS.md from the complete stored results.")


if __name__ == "__main__": main()
