# Evidence preservation in RAG

[![Research CI](https://github.com/Alien6-Studio/research-rag-evidence/actions/workflows/ci.yml/badge.svg)](https://github.com/Alien6-Studio/research-rag-evidence/actions/workflows/ci.yml)
[![Code license: Apache-2.0](https://img.shields.io/badge/code%20license-Apache--2.0-blue)](LICENSE)


An empirical study for the existing Alien6 article at
`/en/research/articles/rag-architecture-audit/`.

**Research question:** when does finding the right sources lead to an answer
that is actually supported by those sources?

## Current status

The primary collection is complete: **64 distinct questions and 512 answer
configurations**, with no JSON parsing failures. An additional 32 diagnostic
controls and two repeat passes of 128 answers each have been collected.
The [audited analysis](RESULTS.md) is complete, including the separate
faithfulness-proxy controls and the limits of lexical answer scoring.
A valid output format does not establish answer correctness or faithfulness.
[The evidence index](EVIDENCE.md) explains the retained records.

- [Protocol](PROTOCOL.md): hypotheses, variables, measurements, and limits.
- [Experiment executable](run.py): segmentation, indexing, BM25 and dense
  retrieval, context selection, Ollama generation, and evaluation.
- [Tests](test_run.py): original evidence coordinates, context budgets,
  annotation isolation, and scoring rules.
- [Pinned sources](sources.json) and [dependencies](requirements-lock.txt).
- [Raw runs](runs/2026-11-12-rag/): selected questions, contexts, requests,
  responses, failures, and diagnostic controls.

The first study uses HotpotQA's **distractor setting**: ten supplied paragraphs
per question, not unrestricted search across Wikipedia. The sample contains
32 bridge and 32 comparison questions. Model digests are checked at execution.

## Results and interpretation

[Audited results](RESULTS.md) include every arm, question-level uncertainty,
controls, a rule-selected source example, and scoring limitations.
`analysis.py` rechecks the raw prompts, packing, hashes, and official scores
before producing the tables and figures. Exact reference matching is not a
complete semantic-correctness assessment.

## Deeper diagnostics

[The exploratory follow-up](DEEPER_ANALYSIS.md) follows gains and losses on the
same questions, holds the evidence-counting unit constant across chunk sizes,
checks repeated identical requests, and inspects ambiguous calibration labels.
It does not turn the original 64 questions into a new independent sample.

The exact cached embedding inputs and vectors are available in
[`embeddings/`](embeddings/manifest.json). No running Ollama server is needed to
reproduce all 1,152 retrieval diagnostics and the six paired contrasts:

```bash
.venv/bin/python extensions/deeper_analysis.py --check
```

The [review of all three lexical-score losses](analysis/2026-11-12-rag/exact-match-loss-review.json)
keeps original scores and every relevant context. It distinguishes a wording
change, contradictory source dates, and unsupported filming-location inference.
These are provisional assistant reviews, not independent human adjudication or a
replacement semantic-accuracy estimate.

## Reproduce

```bash
uv venv --python 3.12
uv pip install --python .venv/bin/python -r requirements-lock.txt
.venv/bin/python prepare_data.py
.venv/bin/python -m unittest discover -p 'test_*.py'
.venv/bin/python run.py prepare --out runs/new-study
.venv/bin/python run.py generate --out runs/new-study
.venv/bin/python run.py controls --out runs/new-study
.venv/bin/python run.py generate --repeat 1 --out runs/new-study
.venv/bin/python run.py generate --repeat 2 --out runs/new-study
.venv/bin/python run.py judge --out runs/new-study
# Analyse the archived campaign after preparing its pinned public inputs:
.venv/bin/python analysis.py
```

Use the model versions and parameters recorded in the protocol. Keep new runs
in a new directory. Parsing failures and abstentions remain in the records;
answers are not regenerated until they pass. Downloaded inputs and the Python
environment are excluded from Git. Each run records the executable's checksum.

## Attribution

HotpotQA: Yang, Qi, Zhang et al., EMNLP 2018,
<https://hotpotqa.github.io/>, dataset under CC BY-SA 4.0. Questions, evidence,
and derived dataset extracts retain that attribution and license. The official
evaluator is preserved unchanged in `vendor/`, with its Apache-2.0 license.
The tokenizer comes from the official Qwen repository pinned in `sources.json`.

## Article history

Original article publication: **2026-10-20**. Dedicated repository and new
experimental work: **12 November 2026**. See [the chronology](CHRONOLOGY.md)
for the distinction between historical publication and newly collected evidence.

The maintained environment includes patched pyarrow and ujson after concrete dependency
alerts were reported. The exact environment used for original measurements is
preserved in [the environment record](environments/2026-11-12-original.json)
and the protected protocol tag. This maintenance change does not rewrite those
measurements. The Linux portability check uses the patched versions.

[Validity and limits](VALIDITY.md) separate the reproduced packing calculation
from model-quality, hardware, timing, and sampling claims.

Reviewed maintenance upgrades are checked against every archived primary record
in CI. The original generation environment and its protected protocol tag remain
unchanged. The public package manifests describe the current maintained tools.
