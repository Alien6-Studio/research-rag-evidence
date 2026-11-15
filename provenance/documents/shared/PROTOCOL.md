# Experimental protocol

The question is whether passages found by retrieval still carry their annotated
sentences after a fixed token budget, and how those measurements relate to
lexical agreement in generated answers. Annotation coverage, lexical agreement
and human semantic judgement are separate endpoints.

## Design and populations

The [captured full protocol](v2/PROTOCOL.md) specifies the hypotheses, parameters,
selection, prompts, statistical families and human evaluation. Its source hashes
are recorded in `v2/registration.json`.

| Population | Size | Role |
| --- | ---: | --- |
| Existing exploratory HotpotQA cohort | 64 questions, 512 primary answers | Audited separately; never pooled with the main sample |
| Disjoint technical pilot | 8 questions, 64 answers | Tokenizer, request and output-format qualification |
| Main deterministic cohort | 256 questions, 128 bridge + 128 comparison | Retrieval and context preservation |
| Fixed generation subset | 128 questions, 64 of each type | 8 conditions; 1,024 primary outputs |
| Identical-request repeats | 16 questions, 32 additional outputs | Limited stability diagnostic |
| Pooled corpus | Same 256 questions | Separate exploratory retrieval/context analysis, no generated answers |

Seeded selection checks IDs, normalized question text and supporting-document
titles against earlier samples. See `v2/data/cohorts.json` and the independently
recomputed selection in `v2/verify.py`. Dataset pretraining exposure is unknown.

## Variables and measurement

BM25 and cosine dense retrieval operate on three-sentence chunks without answer
references or supporting-fact flags. Controlled retrieval searches ten supplied
paragraphs per question. Pooled retrieval searches the deduplicated union of
2,547 paragraph versions / 4,259 chunks. Both retain the top ten ranked chunks.
Ranked and document-diverse packing skip whole chunks that do not fit. Budgets
are 512 or 1,536 tokens of the fully rendered context, including titles, sentence
IDs and separators. They are not full request or model context-window limits.

`sources.json`, the captured protocol and raw
execution/preparation records identify dataset revision, tokenizer, exact model
digests, vectors, prompts, options and hardware. No model server is needed to
replay preserved embeddings, contexts and responses. See `v2/README.md` for
commands to collect a separate new run; never overwrite the supplied observations.

Passage Recall@10 counts retrieved annotated paragraphs per question. Sentence
coverage counts annotated sentences in the transmitted context. Complete context
means all annotated sentences are retained; it does not mean the evidence is
sufficient or exhaustive. HotpotQA EM/F1 use the unchanged official evaluator.
Invalid outputs remain in the planned denominator. Explicit abstentions and
invalid outputs are reported separately; their union is the unanswered composite.

The [independent checks](v2/checks.py) recompute BM25, cosine rankings and packing.
The verifier rechecks exact transmitted text, tokenizer budgets, archived raw
response parsing, scoring and statistical calculations for all **4,160 prepared
contexts and 1,120 generation observations**. It also reproduces the readable
results; missing evidence fails the CI.

## Inference and human evaluation

Question is the paired statistical unit. Five preservation comparisons and four
lexical/composite comparisons use separate Holm families; bootstrap resampling
keeps question types balanced (10,000 draws). Report the simultaneous family
intervals and losses as well as gains. Other contrasts, pooled retrieval and
legacy diagnostics remain exploratory. Planning assumptions are in
`v2/data/power-planning.json`; non-significance does not establish equivalence.

[Human annotation](v2/ANNOTATION.md) is prepared but **not performed**. Two
independent reviewers first assess context/citation support and abstention before
reference release, then judge correctness and reference ambiguity. Per-reviewer
aliases, locked submissions, evidence/rationale requirements and a third-person
arbitration separate these dimensions from lexical scores. The calibration set
has 16 diagnostic controls. All 1,024 primary outputs, including the invalid one,
remain to be annotated. No automatic judge substitutes for those labels.

The original 64-question protocol and report are retained with the original
source under `analysis/2026-11-12-rag/`. They document that cohort's parameters,
not a second current protocol. [RESULTS.md](RESULTS.md) and
[VALIDITY.md](VALIDITY.md) define the resulting scope.
