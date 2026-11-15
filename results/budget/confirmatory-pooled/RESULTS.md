# Prospective V2 results

Environment: **pooled**. deterministic results only; generation incomplete or not planned.

separate exploratory pooled-corpus experiment; no confirmatory claim

Semantic correctness and documentary support remain unmeasured until independent human adjudication. Exact matches below are lexical observations.

| Configuration | Complete annotated context /256 | Mean passage recall@10 | Answers observed/planned | Exact matches | Abstentions | Execution errors |
|---|---:|---:|---:|---:|---:|---:|
| bm25:diverse:1536 | 189 | 0.875 | 0/0 | not measured | not measured | not measured |
| bm25:diverse:512 | 109 | 0.875 | 0/0 | not measured | not measured | not measured |
| bm25:ranked:1536 | 189 | 0.875 | 0/0 | not measured | not measured | not measured |
| bm25:ranked:512 | 115 | 0.875 | 0/0 | not measured | not measured | not measured |
| dense:diverse:1536 | 238 | 0.969 | 0/0 | not measured | not measured | not measured |
| dense:diverse:512 | 195 | 0.969 | 0/0 | not measured | not measured | not measured |
| dense:ranked:1536 | 238 | 0.969 | 0/0 | not measured | not measured | not measured |
| dense:ranked:512 | 208 | 0.969 | 0/0 | not measured | not measured | not measured |

## Prespecified paired contrasts

Intervals resample the same questions within type (10,000 draws). Holm correction is applied within the five preservation and four lexical/composite comparisons. Simultaneous conservative intervals use Bonferroni within each family.

| Family | Before → after | Outcome | Paired difference | 95% interval | Holm p |
|---|---|---|---:|---|---:|
| preservation | bm25:ranked:512 → bm25:ranked:1536 | complete_context | +0.2891 | [+0.2344, +0.3438] | 4.2352e-22 |
| preservation | dense:ranked:512 → dense:ranked:1536 | complete_context | +0.1172 | [+0.0781, +0.1562] | 5.5879e-09 |
| preservation | bm25:ranked:512 → bm25:diverse:512 | complete_context | -0.0234 | [-0.0469, +0.0000] | 0.10938 |
| preservation | dense:ranked:512 → dense:diverse:512 | complete_context | -0.0508 | [-0.0820, -0.0195] | 0.0088501 |
| preservation | bm25:ranked:512 → dense:ranked:512 | complete_context | +0.3633 | [+0.3008, +0.4258] | 1.6782e-23 |

The unanswered composite includes explicit abstentions and execution/format failures. These are separately reported; execution errors must not be described as model abstentions.

Identical requests are recorded in results.json. A changed answer under an identical request cannot be attributed to a different context-selection policy.

## Limits

- Lexical matching is not factual correctness.
- Annotated evidence coverage is not semantic faithfulness.
- Pooled and ten-paragraph results are separate experiments.
- Eight correlated settings do not multiply the independent sample size.
- Support-title-disjoint sampling does not remove all dependence or model pretraining contamination.

Question-level transitions, negative changes, complete-context lexical failures, and repeat differences remain in results.json. Original source annotations and historical scores are unchanged.
