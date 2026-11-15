# RAG selection V3 results

separate exploratory pooled sensitivity.

complete deterministic exploratory collection; no generation planned.

| Configuration | Complete annotated context /256 | Mean sentence coverage | Mean documentary tokens | EM / planned answers | Explicit abstentions | Invalid/failed |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| bm25:ranked:512 | 115 | 0.695 | 477.8 | not measured | 0 | 0 |
| bm25:ranked:1536 | 191 | 0.876 | 1184.5 | not measured | 0 | 0 |
| bm25:mmr:512 | 106 | 0.676 | 478.0 | not measured | 0 | 0 |
| bm25:mmr:1536 | 191 | 0.876 | 1184.8 | not measured | 0 | 0 |
| bm25:sentences:512 | 118 | 0.708 | 498.3 | not measured | 0 | 0 |
| bm25:sentences:1536 | 191 | 0.876 | 1185.7 | not measured | 0 | 0 |
| bm25:sentence_mmr:512 | 167 | 0.840 | 502.1 | not measured | 0 | 0 |
| bm25:sentence_mmr:1536 | 193 | 0.880 | 1185.8 | not measured | 0 | 0 |
| dense:ranked:512 | 213 | 0.918 | 475.4 | not measured | 0 | 0 |
| dense:ranked:1536 | 243 | 0.976 | 1220.9 | not measured | 0 | 0 |
| dense:mmr:512 | 211 | 0.914 | 475.4 | not measured | 0 | 0 |
| dense:mmr:1536 | 243 | 0.976 | 1220.5 | not measured | 0 | 0 |
| dense:sentences:512 | 211 | 0.913 | 497.6 | not measured | 0 | 0 |
| dense:sentences:1536 | 243 | 0.976 | 1222.2 | not measured | 0 | 0 |
| dense:sentence_mmr:512 | 197 | 0.897 | 502.0 | not measured | 0 | 0 |
| dense:sentence_mmr:1536 | 243 | 0.976 | 1222.9 | not measured | 0 | 0 |

## Fixed 512-token paired contrasts

Question-level, type-stratified bootstrap: 10,000 draws. Simultaneous intervals use the declared family sizes; Holm correction is separate for preservation (8) and lexical/unanswered (16).

| Family | Before → after | Outcome | 0→1 / 1→0 / unchanged | Difference [simultaneous interval] | Holm p |
| --- | --- | --- | --- | --- | ---: |
| preservation | bm25:ranked:512 → bm25:mmr:512 | complete_context | 2 / 11 / 243 | -0.0352 [-0.0742, +0.0000] | 0.1123 |
| preservation | bm25:ranked:512 → bm25:sentences:512 | complete_context | 7 / 4 / 245 | +0.0117 [-0.0234, +0.0469] | 1 |
| preservation | bm25:sentences:512 → bm25:sentence_mmr:512 | complete_context | 58 / 9 / 189 | +0.1914 [+0.1133, +0.2695] | 4.768e-09 |
| preservation | bm25:ranked:512 → bm25:sentence_mmr:512 | complete_context | 61 / 9 / 186 | +0.2031 [+0.1211, +0.2852] | 1.0275e-09 |
| preservation | dense:ranked:512 → dense:mmr:512 | complete_context | 3 / 5 / 248 | -0.0078 [-0.0391, +0.0234] | 1 |
| preservation | dense:ranked:512 → dense:sentences:512 | complete_context | 3 / 5 / 248 | -0.0078 [-0.0391, +0.0195] | 1 |
| preservation | dense:sentences:512 → dense:sentence_mmr:512 | complete_context | 13 / 27 / 216 | -0.0547 [-0.1211, +0.0117] | 0.15391 |
| preservation | dense:ranked:512 → dense:sentence_mmr:512 | complete_context | 12 / 28 / 216 | -0.0625 [-0.1289, +0.0039] | 0.099534 |

The unanswered composite includes explicit abstentions and invalid/failed outputs; an increase is adverse. Missing responses keep lexical inference unavailable; failures are retained in the planned denominator.

Pooled calculations, partial coverage, F1 and 1,536-token contrasts are secondary/exploratory. No lexical or annotation-coverage measure supplies a human semantic judgement.

Exact requests, contexts, costs, coordinates and question-level transitions are retained in the archived inputs and results.json. Timings are local descriptive measurements.

## Limits

- Annotated sentence retention is not sufficient or exhaustive evidence.
- Lexical agreement and citation ID validity are not correctness or support.
- Identical-request answer changes are generation variability.
- Question is the paired unit; configurations do not multiply sample size.
- Pooled results are exploratory and are never combined with controlled results.
- Local preparation/generation timings are not production or financial costs.
