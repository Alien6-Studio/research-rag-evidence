# Benchmark and deterministic replay

The benchmark separates annotated-evidence preservation from lexical scoring and
human semantic validation. Read [the protocol](PROTOCOL.md) for the fixed cohorts,
comparison families and scientific limits, and [the complete study](../RESULTS.md)
for results. The controlled and pooled environments remain separate.

## Replay the supplied study without Ollama

Use Python 3.12 and the root lockfile. From the repository root:

```sh
python -m pip install -r requirements-lock.txt
python prepare_data.py
python -m v2.archive restore
python -m unittest discover -p 'test_*.py' -v
python -m v2.verify
python -m v2.audit --check
python -m v2.diagnostics
python -m v2.report
```

Only `prepare_data.py` may download the pinned public dataset/tokenizer if absent.
Replay uses archived embeddings and exact response bodies. It makes no model
calls. `verify.py` independently checks complete BM25/cosine rankings, context
packing, source coordinates, token counts, intents, parsed outputs (including the
invalid response), official lexical/citation scores and all saved statistical
estimates. `archive.py` verifies compressed and restored bytes before use.
Missing evidence is an error, not a skipped V2 check.

`core.py` and `benchmark.py` preserve the collected instrument. `checks.py` supplies
independent numerical references. `analysis.py` recalculates paired comparisons;
`diagnostics.py` locates annotated-information gaps; `report.py` builds the study.
`audit.py` independently rechecks the exploratory 64-question experiment and its
sixteen gold-evidence controls. None of these calculations supplies human labels.

## Human validation

[ANNOTATION.md](ANNOTATION.md) describes the two independent review phases,
private mapping keys, release/locking rules, agreement and third-human arbitration.
`annotation.py` implements them. All1,024 primary outputs must be reviewed,
including abstentions and the invalid output. Empty templates remain pending.
The four-test semantic family cannot be computed before complete agreed or
independently adjudicated labels exist.

## New collections

This snapshot already contains the complete collected experiment. Do not rerun
or replace its requests, answers or failures when reproducing calculations.
A new collection needs an isolated checkout/output directory, the pinned models,
a separately frozen design and the protocol's pilot gate. The benchmark CLI
exposes `cohorts`, `register`, `prepare`, `generate` and `qualify`.
Preserve the supplied observations when collecting a new campaign.

HotpotQA-derived text retains its CC BY-SA 4.0 attribution. Code is Apache-2.0.
