# Evidence index

[Results](RESULTS.md), [methods](METHODS.md) and [validity](VALIDITY.md) are the
current reading guides. Files below are captured scientific evidence, with
original bytes and identities retained. Cohorts, pilots and environments remain
distinct even when their records share a storage category.

## Documentary-budget diagnostic

| Evidence | Published location |
| --- | --- |
| Controlled analysis, all arms and paired transitions | [results.json.gz](results/budget/confirmatory-controlled/results.json.gz) |
| Controlled requests, responses and preparation | [controlled records](results/budget/confirmatory-controlled/) |
| Separate pooled-corpus sensitivity | [pooled records](results/budget/confirmatory-pooled/) |
| Technical pilot and limited stability records | [pilot](results/budget/pilot-controlled/), controlled record directory |
| Frozen cohort and generation membership | [cohorts.json](data/budget/cohorts.json) |
| Archive/storage identities | [budget inventory](provenance/archives/budget.json) |
| Registered specification | [captured protocol](provenance/documents/budget/PROTOCOL.md) |
| Comprehensive captured report and claim ledger | [report](provenance/documents/shared/RESULTS.md), [ledger](provenance/documents/shared/ARTICLE_EVIDENCE.md) |
| Semantic status | [status](results/budget/semantic-status.json) |
| Native/Linux calculation checks | [native](results/budget/verification-native.json), [Linux](results/budget/verification-linux.json) |

## Selection comparison

| Evidence | Published location |
| --- | --- |
| Controlled analysis, all arms and paired transitions | [results.json.gz](results/selection/confirmatory-controlled/results.json.gz) |
| Exact main requests, responses, preparation and execution metadata | [controlled records](results/selection/confirmatory-controlled/) |
| Separate pooled-corpus sensitivity | [pooled records](results/selection/confirmatory-pooled/) |
| Excluded initial pilot | [retained records](results/selection/pilot-controlled/) |
| Qualified replacement pilot | [replacement records](results/selection/pilot-01-controlled/) |
| Active cohort and generation membership | [cohort](data/selection/cohorts-amendment-01.json) |
| Lossless archive inventory, 846 files | [selection inventory](provenance/archives/selection.json) |
| Original registered specification and prospective amendment | [protocol](provenance/documents/selection/PROTOCOL.md), [amendment](provenance/documents/selection/AMENDMENT-01.md) |
| Captured result summary and article claim ledger | [summary](provenance/documents/selection/RESULTS.md), [ledger](provenance/documents/selection/ARTICLE_EVIDENCE.md) |
| Human semantic status | [status](results/selection/semantic-status.json) |
| Numerical replay evidence | [reports](provenance/numerical-replay/), [captured explanation](provenance/documents/selection/REPLAY.md) |

## Shared inputs, exploratory observations and provenance

| Evidence | Published location |
| --- | --- |
| Dataset/tokenizer revisions, checksums and official evaluator | [public sources](data/sources.json), [third-party notices](THIRD_PARTY_NOTICES.md) |
| Frozen implementation and controls | [implementations](reproduction/implementations/) |
| Separate 64-question exploratory requests, outputs and controls | [raw observations](results/exploratory/2026-11-12-rag/) |
| Exploratory recomputed metrics, Fiat example and loss reviews | [diagnostics](results/exploratory/diagnostics/) |
| Captured registration files and public receipts | [registrations](provenance/registrations/) |
| Required original commit/tree/blob proofs | [registration proofs](provenance/registration-proofs/) |
| Exact original-to-functional file mapping | [layout map](provenance/layout-map.json) |
| Human review specification | [captured rubric](provenance/documents/budget/ANNOTATION.md) |

Captured documents retain their original wording and internal relative paths.
Those paths describe the captured instrument layout; use this index for current
published locations. The isolated reproduction workspace reconstructs them
exactly. No captured protocol, result, score or failure is rewritten by relocation.

The exploratory sample is not pooled with either controlled cohort. Automatic
judge controls and native/Linux replay reports are diagnostics, not independent
human labels or repetitions of model generation. Private reviewer identities,
mapping keys and unreleased annotation packets are not part of this public snapshot.
