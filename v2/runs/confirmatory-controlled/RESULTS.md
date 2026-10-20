# Prospective V2 results

Environment: **controlled**. complete lexical collection; human semantic adjudication pending.

confirmatory prespecified families

Semantic correctness and documentary support remain unmeasured until independent human adjudication. Exact matches below are lexical observations.

| Configuration | Complete annotated context /256 | Mean passage recall@10 | Answers observed/planned | Exact matches | Abstentions | Execution errors |
|---|---:|---:|---:|---:|---:|---:|
| bm25:diverse:1536 | 228 | 0.948 | 128/128 | 80 | 6 | 0 |
| bm25:diverse:512 | 144 | 0.948 | 128/128 | 67 | 24 | 0 |
| bm25:ranked:1536 | 228 | 0.948 | 128/128 | 80 | 6 | 1 |
| bm25:ranked:512 | 148 | 0.948 | 128/128 | 60 | 26 | 0 |
| dense:diverse:1536 | 249 | 0.989 | 128/128 | 84 | 9 | 0 |
| dense:diverse:512 | 203 | 0.989 | 128/128 | 79 | 14 | 0 |
| dense:ranked:1536 | 249 | 0.989 | 128/128 | 86 | 8 | 0 |
| dense:ranked:512 | 220 | 0.989 | 128/128 | 79 | 19 | 0 |

## Prespecified paired contrasts

Intervals resample the same questions within type (10,000 draws). Holm correction is applied within the five preservation and four lexical/composite comparisons. Simultaneous conservative intervals use Bonferroni within each family.

| Family | Before → after | Outcome | Paired difference | 95% interval | Holm p |
|---|---|---|---:|---|---:|
| preservation | bm25:ranked:512 → bm25:ranked:1536 | complete_context | +0.3125 | [+0.2539, +0.3711] | 8.2718e-24 |
| preservation | dense:ranked:512 → dense:ranked:1536 | complete_context | +0.1133 | [+0.0781, +0.1523] | 1.1176e-08 |
| preservation | bm25:ranked:512 → bm25:diverse:512 | complete_context | -0.0156 | [-0.0431, +0.0117] | 0.42395 |
| preservation | dense:ranked:512 → dense:diverse:512 | complete_context | -0.0664 | [-0.1016, -0.0352] | 0.0004425 |
| preservation | bm25:ranked:512 → dense:ranked:512 | complete_context | +0.2812 | [+0.2148, +0.3477] | 3.3138e-13 |
| lexical | bm25:ranked:512 → bm25:ranked:1536 | answer_em | +0.1562 | [+0.0938, +0.2188] | 7.6294e-06 |
| lexical | bm25:ranked:512 → bm25:ranked:1536 | unanswered | -0.1484 | [-0.2188, -0.0859] | 0.00019813 |
| lexical | dense:ranked:512 → dense:ranked:1536 | answer_em | +0.0547 | [+0.0078, +0.1094] | 0.06543 |
| lexical | dense:ranked:512 → dense:ranked:1536 | unanswered | -0.0859 | [-0.1406, -0.0391] | 0.0068359 |

The unanswered composite includes explicit abstentions and execution/format failures. These are separately reported; execution errors must not be described as model abstentions.

Identical requests are recorded in results.json. A changed answer under an identical request cannot be attributed to a different context-selection policy.

## Limits

- Lexical matching is not factual correctness.
- Annotated evidence coverage is not semantic faithfulness.
- Pooled and ten-paragraph results are separate experiments.
- Eight correlated settings do not multiply the independent sample size.
- Support-title-disjoint sampling does not remove all dependence or model pretraining contamination.

Question-level transitions, negative changes, complete-context lexical failures, and repeat differences remain in results.json. Original source annotations and historical scores are unchanged.
