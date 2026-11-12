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
The separate document-faithfulness evaluation is complete; analysis follows.
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
