# Article evidence ledger

This file indexes the measurements, methods and sources used to prepare the article.

## Research question and apparatus

Does retrieval preserve its annotated information after context packing, and what can lexical answer scores tell us about that loss? Architectural interest: the retriever and the generator are separated by a measurable, budget-constrained transformation.

The controlled candidate set has ten supplied HotpotQA paragraphs per question. Three-sentence chunks; BM25 versus cosine nomic embeddings; ranked versus document-diverse packing; 512/1,536 rendered-context tokens. Retrieval never receives references or support flags. The 256-question preservation cohort and 128-question answer subset are fixed and balanced by question type. Eight conditions produce 1,024 primary outputs. Pilot 64 + primary 1,024 + repeats 32 = 1,120 generations; controlled 2,048 + pooled 2,048 + pilot 64 = 4,160 prepared contexts.

Exact model digests/options, tokenizer and dataset revisions: `sources.json`, `run.py`, `v2/registration.json` and `v2/runs/confirmatory-controlled/execution-0-1794550515541801000.json`.

Hypotheses, refutations and statistical families: [PROTOCOL.md](PROTOCOL.md) and the captured [full specification](v2/PROTOCOL.md). Full results: [RESULTS.md](RESULTS.md).

## Citable controlled results

All rows below use `v2/runs/confirmatory-controlled/results.json`, `arms[]`. Raw inputs are `jobs.json.gz`, `answers.jsonl.gz` and `preparation.json` in that directory. Restore with `python -m v2.archive restore`. Context completeness counts all annotated sentences, not sufficient evidence; EM is official normalized lexical equality, not semantic accuracy.

| Configuration | Complete annotated context /256 | EM /128 | Explicit abstentions /128 | Invalid /128 | Mean lexical F1 /128 |
| --- | ---: | ---: | ---: | ---: | ---: |
| bm25:diverse:1536 | 228 | 80 | 6 | 0 | 0.758 |
| bm25:diverse:512 | 144 | 67 | 24 | 0 | 0.629 |
| bm25:ranked:1536 | 228 | 80 | 6 | 1 | 0.759 |
| bm25:ranked:512 | 148 | 60 | 26 | 0 | 0.589 |
| dense:diverse:1536 | 249 | 84 | 9 | 0 | 0.778 |
| dense:diverse:512 | 203 | 79 | 14 | 0 | 0.739 |
| dense:ranked:1536 | 249 | 86 | 8 | 0 | 0.781 |
| dense:ranked:512 | 220 | 79 | 19 | 0 | 0.736 |

### Paired comparisons and uncertainty

Source: the same `results.json`, `preservation_family[]` / `lexical_family[]`. The question is the paired unit. 10,000 type-stratified bootstrap draws; conservative simultaneous intervals within each family; Holm p values separately for five preservation and four lexical/composite tests. No significance inference on truth or support is available. `unanswered` includes invalid outputs and explicit abstentions.

| Before → after | Metric | Paired denominator | Difference pp [simultaneous interval] | Holm p |
| --- | --- | ---: | --- | ---: |
| bm25:ranked:512 → bm25:ranked:1536 | complete_context | 256 questions | +31.2 [+24.2, +38.7] | 8.2718e-24 |
| dense:ranked:512 → dense:ranked:1536 | complete_context | 256 questions | +11.3 [+6.6, +16.4] | 1.1176e-08 |
| bm25:ranked:512 → bm25:diverse:512 | complete_context | 256 questions | -1.6 [-5.5, +2.0] | 0.42395 |
| dense:ranked:512 → dense:diverse:512 | complete_context | 256 questions | -6.6 [-11.3, -2.3] | 0.0004425 |
| bm25:ranked:512 → dense:ranked:512 | complete_context | 256 questions | +28.1 [+19.9, +37.1] | 3.3138e-13 |
| bm25:ranked:512 → bm25:ranked:1536 | answer_em | 128 questions | +15.6 [+8.6, +24.2] | 7.6294e-06 |
| bm25:ranked:512 → bm25:ranked:1536 | unanswered | 128 questions | -14.8 [-24.2, -6.2] | 0.00019813 |
| dense:ranked:512 → dense:ranked:1536 | answer_em | 128 questions | +5.5 [-0.8, +12.5] | 0.06543 |
| dense:ranked:512 → dense:ranked:1536 | unanswered | 128 questions | -8.6 [-15.6, -2.3] | 0.0068359 |

### Gaps and counter-intuitive observations

Source: `v2/runs/confirmatory-controlled/diagnostics.json`, `arms[].deterministic_flags`, `generation_flags`, and per-question records. Flags overlap; do not sum them as disjoint causes. A zero EM includes abstention and is not a factual-error judgement. Partial annotations with EM may reflect alternative sufficient text, prior knowledge or annotation incompleteness.

| Configuration | Complete retrieval but incomplete context /256 | Complete context, zero EM /128 | Incomplete context, EM /128 |
| --- | ---: | ---: | ---: |
| bm25:diverse:1536 | 0 | 39 | 3 |
| bm25:diverse:512 | 84 | 21 | 16 |
| bm25:ranked:1536 | 0 | 39 | 3 |
| bm25:ranked:512 | 80 | 27 | 14 |
| dense:diverse:1536 | 0 | 38 | 1 |
| dense:diverse:512 | 46 | 31 | 6 |
| dense:ranked:1536 | 0 | 36 | 1 |
| dense:ranked:512 | 29 | 32 | 3 |

Source: `results.json`, `identical_prompt_groups`: 422 identical-payload groups among 2,048 prepared requests. This is a grouping count, not an answer-agreement rate; see `RESULTS.md` for the actually generated subset. Identical requests cannot identify a selection-policy effect. Two extra passes on 16 fixed questions are only a limited stability check, not proof of generator determinism.

## Exploratory pooled corpus

Source: `v2/runs/confirmatory-pooled/results.json`, `arms[]`, and `preparation.json`; exact contexts: `jobs.json.gz`. Same 256 questions; no generation. The deduplicated question-derived index has 2,547 paragraph versions/4,259 chunks. Annotated sources are present by construction. Global IDs have different token overhead, so cross-environment differences are not pure corpus-size effects.

| Configuration | Complete annotated context /256 | Mean passage Recall@10 /256 questions | Mean sentence coverage /256 questions |
| --- | ---: | ---: | ---: |
| bm25:diverse:1536 | 189 | 0.875 | 0.874 |
| bm25:diverse:512 | 109 | 0.875 | 0.685 |
| bm25:ranked:1536 | 189 | 0.875 | 0.874 |
| bm25:ranked:512 | 115 | 0.875 | 0.703 |
| dense:diverse:1536 | 238 | 0.969 | 0.971 |
| dense:diverse:512 | 195 | 0.969 | 0.884 |
| dense:ranked:1536 | 238 | 0.969 | 0.971 |
| dense:ranked:512 | 208 | 0.969 | 0.910 |

## Code excerpts from the actual instrument

This payload builder is preserved by the registration source hash. It shows exactly where the rendered context enters the model request; it is not a proposed future library.

```python
def payload_for(job):
    return {"model": original.MODELS["generator"][0],
            "messages": [{"role": "system", "content": original.SYSTEM},
                         {"role": "user", "content": f"Question: {job['question']}\n\nEvidence:\n{job['context']}"}],
            "format": original.ANSWER_SCHEMA, "stream": False, "keep_alive": "30m",
            "options": original.OPTIONS, "think": False}
```

The actual whole-chunk packer counts the fully rendered candidate text. Gold coordinates never guide retrieval or packing.

```python
def pack(candidates, budget, policy, tokenizer):
    order = list(candidates)
    if policy == "diverse":
        groups = defaultdict(list)
        for chunk in candidates:
            groups[chunk["title"]].append(chunk)
        order = []
        for round_index in range(max(map(len, groups.values()), default=0)):
            order.extend(items[round_index] for items in groups.values() if round_index < len(items))
    selected = []
    for chunk in order:
        if len(tokenizer.encode(render_context(selected + [chunk])).ids) <= budget:
            selected.append(chunk)
    return selected
```

`v2/core.py::context_metrics` checks the fully rendered budget and original sentence bodies; `run.py::pack` implements whole-chunk packing. `v2/checks.py` provides separate reference implementations for replay.

## Figures and reproduction

| Figure | Exact numerical source | Interpretation |
| --- | --- | --- |
| `v2/runs/confirmatory-controlled/evidence-and-lexical-outcomes.svg` | controlled `results.json`, `arms[]` | Keep /256 preservation and /128 answer denominators separate |
| `v2/runs/confirmatory-controlled/paired-budget-effects.svg` | controlled `results.json`, paired families | Same questions; simultaneous versus ordinary intervals are explicitly labelled |
| `v2/runs/confirmatory-pooled/evidence-preservation.svg` | pooled `results.json`, `arms[]` | Exploratory, no answer comparison |

```sh
python prepare_data.py
python -m v2.archive restore
python -m v2.verify
python -m v2.audit --check
python -m v2.analysis --environment controlled
python -m v2.analysis --environment pooled
python -m v2.diagnostics
python -m v2.report
python -m v2.article_evidence
```

`v2.verify` checks ranking, packing, tokenization, raw responses and numerical report replay without Ollama. The original64-question figures and diagnostics remain under `analysis/2026-11-12-rag/`; cite them only as separate exploratory evidence. `v2/verification-native.json` and `v2/verification-linux.json` document calculation replay, not independent hardware generation.

## Human validation and editorial scope

Prepared, not performed: two independent annotations of all 1,024 outputs, phase1 context/citation/abstention judgements before reference release, phase2 correctness/reference adequacy, locked submissions and independent third-person arbitration. `v2/ANNOTATION.md` gives the rubric and commands; `v2/semantic-status.json` supplies 0 labels and null semantic results. Lexical scores must never be relabelled human semantic accuracy.

**Established on these cohorts:** fixed-budget context selection can discard retrieved annotated sentences; changing budget or retriever changes annotation retention; measured lexical agreement differs in the specified paired comparisons. **Exploratory:** pooled retrieval, flags associating coverage and EM, identical-prompt variability and legacy diagnostic cases. **Pending:** correctness, support, valid-citation entailment and abstention justification across the sample.

**Allowed engineering implication:** measure and audit the retrieval-to-context boundary, retaining exact selected text, budget and source coordinates. A reusable evidence-preserving context assembler is an Alien6 engineering hypothesis. These data establish neither its efficacy nor superiority over existing packers/rerankers. A new comparison would need an equal token budget, outcome-blind selection and human-supported endpoints.

**Do not claim:** retained annotations guarantee sufficient evidence; EM means truth; a zero EM is a hallucination; dense universally beats BM25; diversity always helps; larger budgets cause semantic faithfulness through coverage alone; production cost/latency/quality gains.

## Primary references and attribution

- Yang et al., HotpotQA (EMNLP 2018): https://aclanthology.org/D18-1259/ — dataset and supporting-fact task; CC BY-SA 4.0 data attribution in `THIRD_PARTY_NOTICES.md`.
- Official HotpotQA evaluator, byte-pinned under `vendor/`: https://github.com/hotpotqa/hotpot/blob/master/hotpot_evaluate_v1.py — lexical normalization and scoring, not a semantic oracle.
- Robertson & Zaragoza, BM25: https://doi.org/10.1561/1500000019 — retrieval formula; actual implementation/parameters are in `run.py` and independent `v2/checks.py`.
- Nomic embedding model and revision: `sources.json` and archived embedding requests/vectors; do not substitute a current model under the same mutable tag.

References define methods and context; they do not independently validate this dataset’s outcomes.
