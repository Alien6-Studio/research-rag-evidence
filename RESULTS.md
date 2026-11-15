# Research results

The two controlled studies answer different questions on separate 256-question
cohorts. Each has a fixed 128-question generation subset. Counts of retained
annotations use 256 as their denominator; answer counts use 128. Configurations
are repeated observations of the same questions, not additional independent samples.

## Documentary-budget diagnostic

Retrieval rankings remain fixed while the documentary cap changes. Complete
annotated context means that every annotated source sentence is transmitted.

| Retriever, ranked passages | Complete annotations at 512 tokens /256 | At 1,536 tokens /256 | Exact matches at 512 tokens /128 | At 1,536 tokens /128 |
| --- | ---: | ---: | ---: | ---: |
| BM25 | 148 | 228 | 60 | 80 |
| Dense | 220 | 249 | 79 | 86 |

BM25 retrieval contains every annotation for 228 questions; at 512 tokens,
80 of these lose at least one annotation during context assembly. More space
changes what reaches the generator without changing the retrieval ranking.

The registered preservation family has five comparisons, and its answer/unanswered
family has four. The two budget contrasts below retain their full-family
Bonferroni simultaneous intervals and Holm adjustments, rather than recalculating
correction for the displayed subset.

| Ranked 512 to 1,536 tokens | Preservation difference, percentage points | Simultaneous 95% interval | Holm p |
| --- | ---: | --- | ---: |
| BM25 | +31.25 | [+24.22, +38.67] | 8.27e-24 |
| Dense | +11.33 | [+6.64, +16.41] | 1.12e-8 |

The [exact controlled analysis](results/budget/confirmatory-controlled/results.json.gz)
retains every arm, question-level transition and registered contrast. These
lexical answer scores are not human judgements of correctness or support.

## Selection under a 512-token ceiling

All four policies receive the same retrieved top-ten passages for their question
and retriever. A retains ranked passages; B uses passage MMR; C selects original
sentences in inherited order; D uses question-aware sentence MMR.

| Retriever / policy | Complete annotations /256 | Exact matches /128 | Valid explicit abstentions /128 | Invalid outputs /128 | Mean documentary tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| BM25 A | 136 | 62 | 26 | 1 | 479.4 |
| BM25 B | 126 | 62 | 25 | 2 | 479.6 |
| BM25 C | 146 | 62 | 26 | 1 | 498.9 |
| BM25 D | 203 | 71 | 15 | 1 | 502.3 |
| Dense A | 226 | 75 | 13 | 0 | 479.8 |
| Dense B | 222 | 74 | 13 | 0 | 479.9 |
| Dense C | 226 | 75 | 12 | 0 | 498.2 |
| Dense D | 215 | 72 | 12 | 0 | 502.8 |

The registered preservation family contains eight paired tests. Its simultaneous
intervals use the prespecified, type-stratified 10,000-draw bootstrap with
Bonferroni family size eight; p values use exact two-sided McNemar tests and Holm.

| Preservation contrast | Gains / losses / unchanged | Difference, percentage points [simultaneous interval] | Holm p |
| --- | ---: | --- | ---: |
| BM25 A to B | 7 / 17 / 232 | -3.91 [-8.98, +1.17] | 0.31957 |
| BM25 A to C | 15 / 5 / 236 | +3.91 [-0.78, +8.59] | 0.24834 |
| BM25 C to D | 69 / 12 / 175 | +22.27 [+13.67, +30.86] | 4.92e-10 |
| BM25 A to D | 79 / 12 / 165 | +26.17 [+17.58, +35.45] | 2.39e-12 |
| Dense A to B | 1 / 5 / 250 | -1.56 [-4.30, +0.78] | 0.43750 |
| Dense A to C | 3 / 3 / 250 | 0.00 [-2.73, +2.73] | 1.00000 |
| Dense C to D | 15 / 26 / 215 | -4.30 [-10.94, +2.34] | 0.43252 |
| Dense A to D | 14 / 25 / 217 | -4.30 [-10.94, +2.34] | 0.43252 |

Only BM25 D against A and C rejects after correction. Passage diversification
and sentence extraction alone do not establish a gain. Dense results establish
neither a gain nor a deterioration for D against A; non-significance is not equivalence.

## Generated answers remain inconclusive

BM25 A to D exact matches increase by 9/128, or 7.03 percentage points, with
11 gains and two losses. The simultaneous interval is [-0.78, +15.63] points
and Holm p = 0.31445. None of the sixteen registered exact-match/unanswered
comparisons rejects at .05. Unanswered includes valid explicit abstentions and
invalid/failed outputs; these components are also reported separately.

All 1,024 planned response bodies were observed. Five outputs declared
abstention while supplying a nonempty answer; they remain invalid and score
zero in the planned EM/F1 denominators. Six citation IDs are invalid. An
existing ID only identifies transmitted text; it does not establish support.
There are no supplied independent human semantic labels.

## Secondary settings and measured work

At the controlled 1,536-token ceiling, all four selection policies have identical
complete-context indicators question by question: 223/256 BM25 and 252/256 dense.
No answers were generated at that ceiling. This is a descriptive saturation
observation, not general policy equivalence.

The selection study's separate pooled index contains 2,557 paragraph versions
and 4,270 passages. Its 512-token A/B/C/D counts are 115/106/118/167 for BM25 and
213/211/211/197 for dense, each out of 256. It has no generation arm and is
exploratory. The budget study's separate pooled index contains 2,547 paragraph
versions and 4,259 passages; the two indexes and their results are not combined.

Controlled selection preparation acquired 4,478 retrieval-vector inputs in
26.54 API wall seconds and 7,341 sentence-vector inputs in 40.90 seconds.
Preparation is shared, not charged once per policy. Mean warm A/D selection
times are 3.85/10.14 ms for BM25 and 3.60/9.91 ms for dense. These local timings
do not estimate financial cost, production latency or energy use.

The [exact selection analysis](results/selection/confirmatory-controlled/results.json.gz)
preserves all outcomes and contrasts. The [evidence index](EVIDENCE.md) locates
raw observations and captured reports. Read [methods](METHODS.md) and
[validity](VALIDITY.md) before attributing an answer change to extra annotations
or transferring these findings to another retriever, model or document collection.
