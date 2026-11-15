# RAG selection V3 results

prespecified controlled families.

complete lexical collection; independent human annotation pending.

| Configuration | Complete annotated context /256 | Mean sentence coverage | Mean documentary tokens | EM / planned answers | Explicit abstentions | Invalid/failed |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| bm25:ranked:512 | 136 | 0.753 | 479.4 | 62 / 128 | 26 | 1 |
| bm25:ranked:1536 | 223 | 0.941 | 1159.6 | not measured | 0 | 0 |
| bm25:mmr:512 | 126 | 0.733 | 479.6 | 62 / 128 | 25 | 2 |
| bm25:mmr:1536 | 223 | 0.941 | 1160.0 | not measured | 0 | 0 |
| bm25:sentences:512 | 146 | 0.778 | 498.9 | 62 / 128 | 26 | 1 |
| bm25:sentences:1536 | 223 | 0.941 | 1160.1 | not measured | 0 | 0 |
| bm25:sentence_mmr:512 | 203 | 0.907 | 502.3 | 71 / 128 | 15 | 1 |
| bm25:sentence_mmr:1536 | 223 | 0.941 | 1160.4 | not measured | 0 | 0 |
| dense:ranked:512 | 226 | 0.943 | 479.8 | 75 / 128 | 13 | 0 |
| dense:ranked:1536 | 252 | 0.993 | 1137.0 | not measured | 0 | 0 |
| dense:mmr:512 | 222 | 0.935 | 479.9 | 74 / 128 | 13 | 0 |
| dense:mmr:1536 | 252 | 0.993 | 1137.0 | not measured | 0 | 0 |
| dense:sentences:512 | 226 | 0.941 | 498.2 | 75 / 128 | 12 | 0 |
| dense:sentences:1536 | 252 | 0.993 | 1137.0 | not measured | 0 | 0 |
| dense:sentence_mmr:512 | 215 | 0.935 | 502.8 | 72 / 128 | 12 | 0 |
| dense:sentence_mmr:1536 | 252 | 0.993 | 1137.1 | not measured | 0 | 0 |

## Fixed 512-token paired contrasts

Question-level, type-stratified bootstrap: 10,000 draws. Simultaneous intervals use the declared family sizes; Holm correction is separate for preservation (8) and lexical/unanswered (16).

| Family | Before → after | Outcome | 0→1 / 1→0 / unchanged | Difference [simultaneous interval] | Holm p |
| --- | --- | --- | --- | --- | ---: |
| preservation | bm25:ranked:512 → bm25:mmr:512 | complete_context | 7 / 17 / 232 | -0.0391 [-0.0898, +0.0117] | 0.31957 |
| preservation | bm25:ranked:512 → bm25:sentences:512 | complete_context | 15 / 5 / 236 | +0.0391 [-0.0078, +0.0859] | 0.24834 |
| preservation | bm25:sentences:512 → bm25:sentence_mmr:512 | complete_context | 69 / 12 / 175 | +0.2227 [+0.1367, +0.3086] | 4.9231e-10 |
| preservation | bm25:ranked:512 → bm25:sentence_mmr:512 | complete_context | 79 / 12 / 165 | +0.2617 [+0.1758, +0.3545] | 2.3919e-12 |
| preservation | dense:ranked:512 → dense:mmr:512 | complete_context | 1 / 5 / 250 | -0.0156 [-0.0430, +0.0078] | 0.4375 |
| preservation | dense:ranked:512 → dense:sentences:512 | complete_context | 3 / 3 / 250 | +0.0000 [-0.0273, +0.0273] | 1 |
| preservation | dense:sentences:512 → dense:sentence_mmr:512 | complete_context | 15 / 26 / 215 | -0.0430 [-0.1094, +0.0234] | 0.43252 |
| preservation | dense:ranked:512 → dense:sentence_mmr:512 | complete_context | 14 / 25 / 217 | -0.0430 [-0.1094, +0.0234] | 0.43252 |
| lexical | bm25:ranked:512 → bm25:mmr:512 | answer_em | 2 / 2 / 124 | +0.0000 [-0.0469, +0.0469] | 1 |
| lexical | bm25:ranked:512 → bm25:mmr:512 | unanswered | 2 / 2 / 124 | +0.0000 [-0.0469, +0.0469] | 1 |
| lexical | bm25:ranked:512 → bm25:sentences:512 | answer_em | 3 / 3 / 122 | +0.0000 [-0.0547, +0.0547] | 1 |
| lexical | bm25:ranked:512 → bm25:sentences:512 | unanswered | 2 / 2 / 124 | +0.0000 [-0.0469, +0.0469] | 1 |
| lexical | bm25:sentences:512 → bm25:sentence_mmr:512 | answer_em | 12 / 3 / 113 | +0.0703 [-0.0156, +0.1641] | 0.45703 |
| lexical | bm25:sentences:512 → bm25:sentence_mmr:512 | unanswered | 4 / 15 / 109 | -0.0859 [-0.1875, +0.0078] | 0.28816 |
| lexical | bm25:ranked:512 → bm25:sentence_mmr:512 | answer_em | 11 / 2 / 115 | +0.0703 [-0.0078, +0.1562] | 0.31445 |
| lexical | bm25:ranked:512 → bm25:sentence_mmr:512 | unanswered | 3 / 14 / 111 | -0.0859 [-0.1797, +0.0000] | 0.20361 |
| lexical | dense:ranked:512 → dense:mmr:512 | answer_em | 0 / 1 / 127 | -0.0078 [-0.0391, +0.0000] | 1 |
| lexical | dense:ranked:512 → dense:mmr:512 | unanswered | 0 / 0 / 128 | +0.0000 [+0.0000, +0.0000] | 1 |
| lexical | dense:ranked:512 → dense:sentences:512 | answer_em | 2 / 2 / 124 | +0.0000 [-0.0469, +0.0469] | 1 |
| lexical | dense:ranked:512 → dense:sentences:512 | unanswered | 1 / 2 / 125 | -0.0078 [-0.0547, +0.0312] | 1 |
| lexical | dense:sentences:512 → dense:sentence_mmr:512 | answer_em | 4 / 7 / 117 | -0.0234 [-0.1016, +0.0469] | 1 |
| lexical | dense:sentences:512 → dense:sentence_mmr:512 | unanswered | 5 / 5 / 118 | +0.0000 [-0.0733, +0.0703] | 1 |
| lexical | dense:ranked:512 → dense:sentence_mmr:512 | answer_em | 3 / 6 / 119 | -0.0234 [-0.0938, +0.0469] | 1 |
| lexical | dense:ranked:512 → dense:sentence_mmr:512 | unanswered | 3 / 4 / 121 | -0.0078 [-0.0703, +0.0547] | 1 |

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
