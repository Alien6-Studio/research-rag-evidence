# Evidence through a RAG pipeline

A reproducible study of the path from retrieved passages to transmitted evidence
and generated answers. It separates missing evidence, lexical scoring limits,
abstentions, and invalid outputs.

- [Complete study and conclusions](RESULTS.md)
- [Experimental protocol](PROTOCOL.md)
- [Material for scientific writing](ARTICLE_EVIDENCE.md)
- [Evidence index](EVIDENCE.md)
- [Scope and limits](VALIDITY.md)
- [Execution and analysis code](v2/)
- [Independent human annotation](v2/ANNOTATION.md) — prepared; not yet performed

The controlled experiment covers **256 questions**. Its fixed answer subset has
**128 questions and eight configurations**, yielding **1,024 primary outputs**.
A disjoint pilot and identical-request repeats check the apparatus. A separate
shared-corpus experiment tests retrieval beyond ten preselected paragraphs.

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
