# Evidence preservation in RAG: observed results

Collection and analysis: 12 November 2026. This exploratory, balanced sample contains 64 questions (32 bridge, 32 comparison), not 512 independent questions. Each question supplies ten distractor-setting paragraphs; this is not full-Wikipedia search.

## Main observation

The same retrieved candidate set can retain different amounts of supporting evidence after context packing. More complete transmitted evidence does not by itself guarantee an exact reference match. Exact matching is a lexical test, not a complete semantic-correctness judgement. The following counts come from the audited raw requests and responses; they are not constructed examples.

| Retriever | Packing | Context tokens (maximum) | Mean passage Recall@10 | All supporting sentences retained | Exact reference matches | Abstentions |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| bm25 | ranked | 512 | 96.5% | 38/64 | 32/64 | 18/64 |
| bm25 | ranked | 1536 | 96.5% | 59/64 | 37/64 | 7/64 |
| bm25 | diverse | 512 | 96.5% | 38/64 | 33/64 | 18/64 |
| bm25 | diverse | 1536 | 96.5% | 59/64 | 39/64 | 6/64 |
| dense | ranked | 512 | 97.9% | 55/64 | 32/64 | 14/64 |
| dense | ranked | 1536 | 97.9% | 61/64 | 39/64 | 4/64 |
| dense | diverse | 512 | 97.9% | 47/64 | 31/64 | 17/64 |
| dense | diverse | 1536 | 97.9% | 61/64 | 38/64 | 5/64 |

Recall averages a passage-level fraction per question. Evidence completeness and exact-answer counts use a question-level denominator; these measures must not be read as the same quantity.

## Paired changes from ranked packing at 512 tokens

Intervals resample questions within question type (2,000 draws, seed 20261112). These are exploratory percentile intervals, without multiplicity adjustment. A small sample and correlated configurations limit generalization.

| Retriever | Alternative | Evidence-completeness change (percentage points, 95% interval) | Exact-reference-match change (percentage points, 95% interval) |
| --- | --- | ---: | ---: |
| bm25 | ranked, 1536 tokens | +32.8 [+21.9, +43.8] | +7.8 [-1.6, +17.2] |
| bm25 | diverse, 512 tokens | +0.0 [-7.8, +7.8] | +1.6 [-3.1, +6.2] |
| bm25 | diverse, 1536 tokens | +32.8 [+21.9, +43.8] | +10.9 [+1.6, +20.3] |
| dense | ranked, 1536 tokens | +9.4 [+3.1, +17.2] | +10.9 [+4.7, +18.8] |
| dense | diverse, 512 tokens | -12.5 [-20.3, -4.7] | -1.6 [-4.7, +0.0] |
| dense | diverse, 1536 tokens | +9.4 [+3.1, +17.2] | +9.4 [+1.6, +18.8] |

## What the controls do and do not establish

The automated judge labels 12/16 gold-evidence controls as supported and 16/16 swapped-evidence controls as unsupported. Four positive controls are rejected: its verdicts are therefore an imperfect proxy and do not support a strong semantic-faithfulness claim. All individual verdicts, reasons, requests, and responses remain public.

The positive and swapped controls are constructed calibration conditions, not independent human labels for the predictions. A structurally valid citation is not proof that an answer follows from that text.

On the 16 diagnostic questions, gold-only evidence yields 5/16 exact answers; the separately prompted prior-knowledge condition yields 4/16. These diagnostic conditions do not estimate a causal RAG benefit. Exact-match normalization can also reject semantically acceptable wording; no human answer-equivalence adjudication was performed.

Two complete extra passes cover the same first 16 question IDs and eight configurations. Stability figures are in `results.json`; the 128 settings per pass are correlated and are not 128 independent questions.

## An observed scoring limitation

The rule-selected Fiat example exposes a lexical false negative. The model answers `Fiat S.p.A.`, while the reference expects `Fabbrica Italiana Automobili Torino`. The supplied paragraph itself says `Fiat S.p.A., or "Fabbrica Italiana Automobili Torino"`. The official exact matcher rejects the short name even though this source identifies the names as aliases. No human semantic adjudication was performed across the sample, and this observation is not used to silently change the registered scores. A zero exact-match score must not be called proof of a factually wrong answer.

## Audit and limitations

The executable analysis rechecks the pinned dataset and tokenizer hashes, source hash, raw answer parsing, exact transmitted prompts, context budgets and selection, official scoring, unique IDs, complete primary arms, and calibration-control counts. It preserves the executed generator source unchanged. Run `python analysis.py` after obtaining the pinned public inputs and installing the recorded dependencies.

The sample is small, balanced rather than population-weighted, public, English, and restricted to supplied paragraphs. Prior model exposure to HotpotQA is unknown. The study uses one local quantized generator and one embedding model. It does not establish production performance, customer impact, cost savings, a universal retriever ranking, or semantic faithfulness. Generation timing fields are not a full-pipeline latency benchmark.

The illustration is chosen by a documented rule, not invented: `5a7299465542992359bc3131`. Its full input and all eight configurations are in `illustrative-case.json`. The selection deliberately illustrates a failure mechanism and is not a prevalence estimate.

HotpotQA extracts retain attribution to Yang, Qi, Zhang et al. (EMNLP 2018) and CC BY-SA 4.0. See `THIRD_PARTY_NOTICES.md`.
