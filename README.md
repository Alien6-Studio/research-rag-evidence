# Retrieved information, transmitted context, and answers

Final research snapshot: **`data-2026-11-15-article`**.
This repository contains two distinct controlled studies of information lost
between retrieval and generation. Each has 256 English HotpotQA questions and
a fixed 128-question generation subset. Their cohorts are not pooled.

## Findings

The budget diagnostic holds retrieval rankings fixed while increasing the
documentary cap from 512 to 1,536 tokens. BM25 retains every annotated sentence
for **148/256 to 228/256 questions**; dense retrieval moves from 220/256 to 249/256.

The selection comparison uses another, question- and support-title-disjoint
cohort, the same retrieved top-ten candidates per question/retriever, and four
policies at a 512-token ceiling. BM25 complete annotated contexts rise from
**136/256 with ranked passages to 203/256 with question-aware sentence MMR**.
The paired difference is +26.17 percentage points, with a simultaneous 95%
interval of +17.58 to +35.45 points and Holm p = 2.39e-12. Dense retrieval does
not establish a benefit from that policy.

BM25 exact reference matches rise from **62/128 to 71/128**, but Holm p = 0.314
does not establish an answer gain. None of the sixteen registered lexical and
unanswered comparisons rejects after correction. All 1,024 planned comparison
outputs were captured; five invalid outputs remain in the denominator.
**Independent human semantic annotation remains pending, with zero labels.**

Start with [results](RESULTS.md), [methods](METHODS.md), [validity](VALIDITY.md)
and the [evidence index](EVIDENCE.md). The latter links the exact analyses,
cohorts, raw responses, captured protocols and publication records.

## Repository layout

| Location | Purpose |
| --- | --- |
| `results/budget/` | Documentary-budget diagnostic and its separate pooled sensitivity |
| `results/selection/` | Four-policy comparison and its separate pooled sensitivity |
| `results/exploratory/` | Separate 64-question exploratory observations and diagnostics |
| `data/` | Frozen cohorts, power-planning inputs and public-source identities |
| `methods/` | Recorded execution environments |
| `reproduction/implementations/` | Byte-preserved instruments and controls |
| `provenance/` | Relocation map, registrations, archive inventories and captured documents |

This functional layout preserves 1,384 source files byte for byte. The
[relocation record](provenance/layout-map.json) binds published paths to their
captured identities. Reproduction materializes the original instrument layout
and Git identity only inside an isolated temporary workspace. The public
repository presents one final state without restoring development branches.

## Reproduce without a model

Use Python 3.12 and the pinned dependencies:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-lock.txt
python reproduce.py check
python reproduce.py verify
python reproduce.py test --offline
```

`check` verifies relocated bytes, reconstructed Git identity and registration
proofs without a dataset or network. `verify` replays archived retrieval,
selection, responses and statistical calculations; `test` runs the captured
controls. Neither command calls a model or downloads model weights.

`verify` and `test` obtain the two pinned public inputs when absent from the
default `.cache/inputs` cache. To require a complete existing cache with zero
fetches, pass `--offline`. A custom `--inputs DIR` is read-only. With `--offline`, it must
already contain the exact dataset and tokenizer:

```sh
python reproduce.py verify --offline --inputs /path/to/inputs --output /tmp/rag-verification
```

Choose a new output directory; the default creates a timestamped report directory
under `.cache/reproduction`. See [provenance](provenance/README.md) for the
temporary workspace and the post-collection numerical replay configuration.

Annotation presence, lexical agreement, correctness and documentary support are
different outcomes. The controlled candidate set is ten supplied paragraphs,
not an enterprise collection or full Wikipedia. Local timings are not financial
estimates or production guarantees. Read the [interpretation limits](VALIDITY.md).

Code is Apache-2.0. HotpotQA-derived material retains CC BY-SA 4.0 attribution to
Yang, Qi, Zhang et al., EMNLP 2018; see [third-party notices](THIRD_PARTY_NOTICES.md).
