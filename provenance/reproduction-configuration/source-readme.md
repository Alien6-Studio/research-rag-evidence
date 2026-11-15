# Retrieved information, transmitted context, and answers

Final research snapshot: **`data-2026-11-15-article`**.
Two separate controlled studies examine where information disappears between
retrieval and generation. Each contains 256 English HotpotQA questions and a
fixed 128-question generation subset. Their cohorts are not pooled.

## Results and interpretation

The [budget diagnostic](v2/runs/confirmatory-controlled/RESULTS.md) keeps retrieval
rankings fixed while changing the documentary cap from 512 to 1,536 tokens.
BM25 retains every annotated sentence for **148/256 to 228/256 questions**;
dense retrieval moves from **220/256 to 249/256**. On the fixed generation subset,
BM25 exact reference matches rise from 60/128 to 80/128. These are lexical scores.

The [selection comparison](v3/RESULTS.md) uses a separate, question- and
support-title-disjoint cohort, identical retrieved top-ten candidates per
question/retriever, and four policies at the same 512-token ceiling:
A ranked passages, B passage MMR, C original sentences in inherited order,
and D question-aware sentence MMR.

BM25 complete annotated contexts are **136/126/146/203 out of 256** for A/B/C/D.
D versus A gains 26.17 percentage points, with a simultaneous 95% interval of
17.58 to 35.45 points and Holm p = 2.39e-12: 79 gains and 12 losses.
Neither B nor C establishes a gain. Dense A/D gives 226/215; the registered
comparisons establish neither a gain nor a deterioration for that pair.

BM25 exact matches rise from **62/128 to 71/128** for A/D, but the adjusted
p = 0.314 does not establish an answer gain. None of the sixteen registered
lexical/unanswered comparisons rejects after correction. All 1,024 planned
comparison outputs were captured, including five invalid outputs kept in the
denominator. **Human annotations = 0; semantic validation remains pending.**

Read the [validity guide](v3/VALIDITY.md), [claim ledger](v3/ARTICLE_EVIDENCE.md),
[registered selection methods](v3/PROTOCOL.md),
[budget methods](v2/PROTOCOL.md) and [primary-source review](v3/LITERATURE.md).
The initial unqualified pilot and its replacement remain documented under the
[prospective amendment](v3/AMENDMENT-01.md); neither is a confirmation cohort.

## Scope

Controlled retrieval searches each question's ten supplied paragraphs; separate
pooled-corpus sensitivities are exploratory and are not combined with confirmation.
The generator is one locally executed, digest-pinned Qwen model. Annotated
sentence retention, lexical agreement, factual correctness and documentary
support are different outcomes. Neither annotation presence nor a valid citation
identifier establishes support. These data do not qualify enterprise retrieval.

The ceiling charges titles, headers, IDs, separators and sentence bodies.
Actual BM25 contexts average 479.4 tokens for A and 502.3 for D; this comparison
does not hold transmitted length exactly constant. Shared embedding preparation
and per-policy selection work are accounted separately. Local timings are not
financial estimates or production latency guarantees.

## Reproduce from the archives

Use Python 3.12 and the exact dependency lock. Setup downloads packages and the
pinned public dataset/tokenizer; **no model weights or inference server are needed**.
The comparison's [lossless manifest](v3/archive-manifest.json) indexes 846 files.
Reproduction restores saved vectors, contexts, raw requests/responses and metadata.

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-lock.txt
python prepare_data.py
python -m v2.archive restore
python -m v3.archive restore --manifest v3/amendments/01/retained-pilot-archive.json
python -m v3.archive restore
python -m unittest discover -p 'test_*.py' -v
python -m v2.verify
PYTHONHASHSEED=10 python validation/replay_registered.py --require-collected
```

The `v2/` and `v3/` names remain technical compatibility paths for frozen code
and archives. The wrapper runs the unchanged registered verifier with original
registration identities supplied by the [provenance capsule](provenance/).
It uses a temporary Git object database, without fetching old tags or adding
public refs. `python validation/replay_registered.py --check-capsule` checks
the capsule alone. Full replay recalculates retrieval, packing, parsing and
paired analyses without model calls; it is not a new generation experiment.

Seed 10 is a compatible **post-collection replay setting**, not the original or
a preregistered collection seed. The original hash seed remains unknown. The
[numerical replay note](v3/REPLAY.md) preserves the failure and diagnostic evidence.

## Independent semantic review

The [machine-readable status](v3/semantic-status.json) records zero supplied human
annotations and arbitrations, with semantic results null. The
[two-reviewer rubric](v2/ANNOTATION.md) separates blinded support assessment,
reference release and independent arbitration. Prepared private packets, lexical
scores and model judgements do not supply missing human labels.

Code is Apache-2.0. HotpotQA-derived material retains CC BY-SA 4.0 attribution to
Yang, Qi, Zhang et al., EMNLP 2018; see [third-party notices](THIRD_PARTY_NOTICES.md).
