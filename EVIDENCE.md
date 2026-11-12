# Evidence and provenance

The primary collection contains **64 distinct questions**, each evaluated in
eight configurations, producing **512 actual model responses**. These are not
512 independent questions.

| Evidence | Location | What it establishes |
| --- | --- | --- |
| Protocol registered before collection | [PROTOCOL.md](PROTOCOL.md), commit `abe5f87` | Planned questions, variables, and criteria |
| Executed program | [run.py](run.py), checksum in the manifest | Retrieval, packing, model calls, and scores |
| Pinned inputs | [sources.json](sources.json) | Dataset and tokenizer revisions and checksums |
| Environment | [requirements-lock.txt](requirements-lock.txt) | Python dependency versions |
| Control tests | [test_run.py](test_run.py), [execution record](evidence/unit-tests.json) | Evidence coordinates, budgets, and scoring rules |
| Primary collection | [Raw run directory](runs/2026-11-12-rag/) | Selected questions, transmitted contexts, requests, and responses |
| Diagnostic generation controls | [Control responses](runs/2026-11-12-rag/generator-controls.jsonl) | Gold-evidence and prior-knowledge conditions |
| Faithfulness proxy and calibration controls | [Judge records](runs/2026-11-12-rag/judge.jsonl) | All 423 non-abstained answers and 32 controls; analysis pending |
| Repeat passes | [First](runs/2026-11-12-rag/answers-repeat-1.jsonl), [second](runs/2026-11-12-rag/answers-repeat-2.jsonl) | Output stability on the same 16 questions |

The manifest records full model digests, Ollama version, parameters, source
commit, executable checksum, and preparation time. Each response retains the
actual request, raw service response, and Ollama timing fields. Checksums for
the immutable primary artifacts are in `evidence/checksums-primary.sha256`.

Document-faithfulness judgements and their gold-evidence and swapped-evidence
controls are stored separately. An automated judge is a measured proxy, not a
human annotation. Aggregate results are accompanied by the executable analysis
and the study's limits.

HotpotQA-derived data is attributed to Yang, Qi, Zhang et al. (EMNLP 2018), under
CC BY-SA 4.0. Checksums establish file identity; scientific interpretation still
depends on the protocol and its controls.
