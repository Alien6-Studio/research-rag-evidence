# Evidence

| Records | Location |
|---|---|
| Public inputs, tokenizer, and source hashes | `sources.json` |
| Exploratory questions, prompts, outputs, and controls | `runs/2026-11-12-rag/` |
| Recomputed exploratory metrics and source cases | `analysis/2026-11-12-rag/` |
| Outcome-blind cohorts and generation subset | `v2/data/cohorts.json` |
| Pilot requests and qualification | `v2/runs/pilot-controlled/` |
| 256-question controlled study and 1,024 primary outputs | `v2/runs/confirmatory-controlled/` |
| Separate shared-corpus experiment | `v2/runs/confirmatory-pooled/` |
| New embedding requests and exact response bodies | `v2/runs/embedding-traces/` |
| Numerical audit of the 64-question exploratory study and 16 gold controls | `v2/reports/audit/audit-results.json` |
| Immutable scientific-input inventory | `v2/data/historical-inputs.json` |
| Independent human rubric and tools | `v2/ANNOTATION.md`, `v2/annotation.py` |
| Human semantic status | `v2/semantic-status.json` — pending |
| Native and Linux calculation checks | `v2/verification-native.json`, `v2/verification-linux.json` |

Large raw JSON records are losslessly compressed. Their exact byte hashes and
storage locations are in `v2/evidence-manifest.json`.

```sh
python -m v2.archive restore
python -m v2.archive verify
python -m v2.verify
```

The archives retain the actual requests, responses, errors, abstentions, model
identities, parameters, and execution timestamps. Original annotations and
recorded scores are preserved. These records establish what was measured;
independent semantic judgements are not supplied by the lexical evaluator.


The supplied design record `v2/registration.json` binds instrument/cohort hashes.
`v2.verify` checks complete rankings against independent BM25/cosine calculations,
selection against a separate whole-chunk packer, raw outputs including the invalid
record, the calibration probes, corpus identities and all saved intervals/p-values.
Native/Linux replay is computational portability, not independent model generation.
