# Deeper RAG diagnostics

This is a post-hoc analysis of the same 64 questions. It adds no independent evidence sample and makes no new semantic-accuracy claim. Original scores are unchanged.

## Distinguish the unit being counted

Changing chunk length changes which passages exist. Passage recall therefore has a changing denominator across segmentations. The new sensitivity table also counts original supporting sentences and questions retaining every annotated sentence, using the same units across chunk sizes. It concerns retrieval only, before a context budget or answer generation.

| Search | Sentences per chunk | Top-k | Questions with all annotated evidence |
| --- | ---: | ---: | ---: |
| bm25 | 2 | 5 | 44/64 |
| bm25 | 2 | 10 | 51/64 |
| bm25 | 2 | 20 | 64/64 |
| bm25 | 3 | 5 | 43/64 |
| bm25 | 3 | 10 | 59/64 |
| bm25 | 3 | 20 | 64/64 |
| bm25 | 6 | 5 | 51/64 |
| bm25 | 6 | 10 | 64/64 |
| bm25 | 6 | 20 | 64/64 |
| dense | 2 | 5 | 53/64 |
| dense | 2 | 10 | 60/64 |
| dense | 2 | 20 | 63/64 |
| dense | 3 | 5 | 59/64 |
| dense | 3 | 10 | 61/64 |
| dense | 3 | 20 | 64/64 |
| dense | 6 | 5 | 58/64 |
| dense | 6 | 10 | 62/64 |
| dense | 6 | 20 | 64/64 |

## Follow the same questions through a change

Exact matching is a lexical reference test, not independently adjudicated truth. `0 -> 1` and `1 -> 0` retain both gains and losses. Identical requests with changed answers are a null-policy diagnostic; they cannot be credited to a different selection policy.

| Before | After | 0 -> 1 | 1 -> 0 | Identical requests | Same sentence set, changed request |
| --- | --- | ---: | ---: | ---: | ---: |
| bm25:ranked:512 | bm25:ranked:1536 | 8 | 3 | 1 | 0 |
| dense:ranked:512 | dense:ranked:1536 | 7 | 0 | 1 | 0 |
| bm25:ranked:512 | bm25:diverse:512 | 2 | 1 | 42 | 3 |
| bm25:ranked:1536 | bm25:diverse:1536 | 3 | 1 | 17 | 47 |
| dense:ranked:512 | dense:diverse:512 | 0 | 1 | 32 | 5 |
| dense:ranked:1536 | dense:diverse:1536 | 1 | 2 | 11 | 53 |

## Check the calibration labels too

The [review of all four rejected positive controls](analysis/2026-11-12-rag/control-review.json) is explicitly assistant-assisted and provisional, not independent human adjudication. Three cases contain an explicit date, alias, or two-sentence chain that the proxy explanation does not use. One case asks which documentary was more successful without defining success or supplying comparative evidence for the second documentary. It must not be assumed to be a valid positive entailment control. The observed 12/16 supported rate is not a clean estimate of judge sensitivity.

## Dependence and repeat variability

The 61 connected components formed by shared annotated-document titles have a largest component of 2 question(s). Cluster-resampling intervals are an exploratory sensitivity analysis; the preregistered within-type intervals remain reported separately.

There are 2 settings with changed normalized answers across the three passes on 16 repeated questions. Their exact requests and outputs remain in `deeper-results.json`; changes must not automatically be interpreted as semantic accuracy changes.

Citation flags identify cases to inspect. Missing annotated citations or incomplete annotated context are not by themselves proof of hallucination, because the annotation set need not enumerate every sufficient formulation.

## What needs new evidence

A larger, prospectively selected question sample is needed for confirmation beyond this exploratory cohort. Semantic correctness and documentary support need a calibrated evaluation protocol and independent adjudication. No CPU, latency, GPU, cost, or production conclusion follows from these offline calculations.

The cached vectors used in the calculation are now public Parquet data in `embeddings/`, with exact inputs, model digest, hashes, and CC BY-SA 4.0 attribution. Export time is recorded separately from original collection.
