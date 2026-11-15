# Evidence through a RAG pipeline

A reproducible study of the path from retrieved passages to transmitted evidence
and generated answers. It separates missing evidence, lexical scoring limits,
abstentions, and invalid outputs.

- [V2 study and conclusions](RESULTS.md)
- [V2 experimental protocol](PROTOCOL.md)
- [Material for scientific writing](ARTICLE_EVIDENCE.md)
- [Evidence index](EVIDENCE.md)
- [Scope and limits](VALIDITY.md)
- [Execution and analysis code](v2/)
- [Independent human annotation](v2/ANNOTATION.md) — prepared; not yet performed
- [V3 selection study](v3/README.md), [amendment](v3/AMENDMENT-01.md)
  and [interpretation boundaries](v3/VALIDITY.md)

The V2 controlled experiment covers **256 questions**. Its fixed answer subset has
**128 questions and eight configurations**, yielding **1,024 primary outputs**.
A disjoint pilot and identical-request repeats check the apparatus. A separate
shared-corpus experiment tests retrieval beyond ten preselected paragraphs.

## Equal-budget selection extension (V3)

V3 is a separate prospective comparison of ranked passages, a declared MMR
passage variant, original sentences in inherited rank order, and question-aware
sentence MMR. It fixes the same retrieved candidates and fully rendered token
budget for each paired comparison. The new design contains 256 deterministic
questions and a fixed 128-question generation subset; its primary generation
budget is 512 tokens. Its pooled-corpus sensitivity has no generation arm.

Read the [registered methods](v3/PROTOCOL.md),
[prospective amendment 01](v3/AMENDMENT-01.md),
[primary-source review](v3/LITERATURE.md) and [validity guide](v3/VALIDITY.md).
The original pilot's failed qualification and raw records are retained. The
amendment uses a new disjoint pilot while preserving the original confirmation
cohort, generation membership, policies and analysis families. V3 conclusions
require complete archived observations and successful offline replay; this
navigation entry does not anticipate a policy benefit. All historical V1/V2
observations and scores remain unchanged.

The [V3 results](v3/RESULTS.md) report the completed extension: 4,096 controlled
contexts, 4,096 separate pooled contexts and 1,024 primary generated outputs.
BM25 complete annotated contexts rise from 136/256 with ranked chunks to
203/256 with question-aware sentence MMR at the 512-token cap. Dense results
are mixed, and no lexical/unanswered contrast passes its registered correction.
Five invalid outputs are preserved. Independent human semantic annotation is
still pending. The [article evidence ledger](v3/ARTICLE_EVIDENCE.md) separates
these outcomes and their denominators.

Offline replay verified all 846 V3 lossless archives, active pilot/main records
and the excluded original pilot without model calls. Read the
[post-collection numerical replay note](v3/REPLAY.md): the original hash seed
was not captured; seed 10 is a compatible replay configuration identified on
ranking hashes after context collection, without changing the frozen instrument.

The [V3 guide](v3/README.md) gives separate collection, archive-restoration,
verification and independent-human-review commands. A lexical answer score or
retained annotation is not a human judgement of correctness or support.

## Reproduce the calculations

Use Python 3.12:

```sh
python -m pip install -r requirements-lock.txt
python prepare_data.py
python -m v2.archive restore
python -m unittest discover -p 'test_*.py' -v
python -m v2.verify
python -m v2.audit --check
python -m v2.analysis --environment controlled
python -m v2.analysis --environment pooled
python -m v2.diagnostics
python -m v2.report
python -m v2.article_evidence --check
```

`v2.verify` checks all 4,160 archived contexts and 1,120 generation observations,
including pilot, primary and stability records. Independent BM25/cosine and
packing implementations check full rankings and selected text. Raw response
parsing, tokenizer budgets and paired statistical families are recalculated
without a model server. CI invokes this verifier explicitly and fails on missing
evidence; it also runs the original experiment controls. For a new collection, use a separate checkout and an empty
`v2/runs/` directory, preserving the supplied archives. The local execution
commands are in [the benchmark guide](v2/README.md).

Code is Apache-2.0. HotpotQA-derived data retains CC BY-SA 4.0 attribution to
Yang, Qi, Zhang et al., EMNLP 2018. See [third-party notices](THIRD_PARTY_NOTICES.md).

## What is established and what remains open

The measurements establish changes in retained annotated evidence and official
lexical agreement on the fixed cohorts. The shared-corpus retrieval experiment,
diagnostic case analyses and comparisons outside the declared families are exploratory.
Neither a lexical match nor a valid citation ID proves correctness or support.

Semantic validation is **pending** for all 1,024 primary outputs. The annotation
workflow prepares two independent blinded reviews, locks support judgements
before releasing references, and requires independent arbitration of disagreements.
The sixteen existing gold controls are rubric-calibration material. No human
labels or semantic accuracy estimates are supplied by this snapshot. See
[the rubric and commands](v2/ANNOTATION.md) and [machine-readable status](v2/semantic-status.json).


A Linux replay can also run with networking disabled after restoring the inputs:

```sh
docker build -f validation/Dockerfile.replay -t rag-replay .
mkdir -p /tmp/rag-replay-results
docker run --rm --network none --read-only --tmpfs /tmp \
  --mount "type=bind,source=$(pwd),target=/study,readonly" \
  --mount type=bind,source=/tmp/rag-replay-results,target=/results \
  rag-replay -m v2.verify --output /results/verification.json
```

[The replay environment](validation/replay-environment.json) identifies the
container and dependency lock. This is a calculation check, not another model
experiment or a qualification of physical performance.
