# V3: selecting evidence under an equal documentary budget

This is a separate prospective extension. V1/V2 observations, annotations,
embeddings and scores remain unchanged. Read [the protocol](PROTOCOL.md),
[amendment 01](AMENDMENT-01.md),
[method review](LITERATURE.md), [power assumptions](data/power-planning.json)
and [active frozen cohort](data/cohorts-amendment-01.json) before interpreting any outcomes.

The original pilot retains 128 contexts and 64 captured responses, but its
certificate remains failed after a metadata-checker defect. The amendment uses
a new disjoint pilot; the main cohort, policies and statistical families are
unchanged. Original records and their failed eligibility remain inspectable.

The completed controlled comparison contains 256 questions, four policies, two
retrievers and two documentary budgets (4,096 contexts). Its fixed 128-question
generation subset uses only 512 tokens (1,024 primary outputs). Eight separate
pilot questions qualify the apparatus on technical criteria. A shared-corpus
sensitivity is exploratory and has no generation arm.

The policies are unchanged ranked chunks, a declared MMR chunk variant, original
sentences in inherited ranking order, and a question-oriented MMR sentence
variant. They are not reproductions of RECOMP, LongLLMLingua or SetR. Every
context pays for titles, original sentence coordinates and separators.

The [scientific results](RESULTS.md), [article evidence ledger](ARTICLE_EVIDENCE.md)
and [local full replay record](replay/local-verification.json) report the completed
collection. The main run retains five invalid outputs among 1,024 observed bodies.
There are no missing main observations and no supplied human semantic labels.
The [lossless manifest](archive-manifest.json) verifies 846 archived files.

## Registration and collection

Use Python 3.12 and the root `requirements-lock.txt`. Obtain the exact public
inputs with `python prepare_data.py`. Only a separately authorized new campaign
with the exact installed models can collect observations. Commands below never
overwrite an earlier collection; failed observations must be retained.

```sh
python -m v3.design cohorts
python -m unittest discover -p 'test_*.py' -v
python -m v3.design register
```

The cohort/registration commands describe the original prospective setup, not
instructions to overwrite supplied files. The active amendment uses separate
registration and cohort paths. Publish its full instrument before any amendment
context/model outcome. Record the real GitHub release timestamp, commit URL and
registration SHA in `public-registration-amendment-01.json`. The collector requires this receipt and the
committed frozen sources; a local file alone is not public preregistration.

```sh
python -m v3.benchmark prepare --split pilot
python -m v3.benchmark generate --split pilot
python -m v3.benchmark qualify
python -m v3.benchmark prepare --split confirmatory
python -m v3.benchmark generate --split confirmatory
python -m v3.benchmark prepare --split confirmatory --environment pooled
python -m v3.analysis --environment controlled
python -m v3.analysis --environment pooled
python -m v3.archive pack
PYTHONHASHSEED=10 python -m v3.verify --require-collected
```

The pilot's three tokenizer probes and all 64 responses must qualify without an
answer-quality threshold before confirmation starts. An interrupted request is
not silently regenerated. Do not collect with a changed model, amended method or
different dependency set under the original registration.

## Offline reproduction

After the complete observations are published, no inference service is needed:
Use a full Git clone, including `protocol-rag-v3-2026-11-15` and
`protocol-rag-v3-2026-11-15-a1`, so the verifier can
inspect the public registration commit even after the development PR is squashed.
An existing shallow clone must fetch that protocol tag before offline replay.

```sh
python prepare_data.py
python -m v2.archive restore
python -m v3.archive restore --manifest v3/amendments/01/retained-pilot-archive.json
python -m v3.archive restore
python -m unittest discover -p 'test_*.py' -v
PYTHONHASHSEED=10 python -m v3.verify --require-collected
```

Read [the post-collection BM25 replay note](REPLAY.md) before reproducing V3.
The original collection hash seed was not recorded. Seed 10 was selected after
context collection using exact ranking fingerprints, and reproduces all 528
BM25 fingerprints without changing the frozen instrument or observations. It
is a replay configuration, not a preregistered collection parameter. The note
preserves the original failure, a divergent seed witness and the full audit.

Before collection, `python -m v3.verify --protocol-only` checks the frozen design
and cohort and explicitly requires the absence of active-amendment outcomes.
The hash-bound excluded original pilot is retained separately. Restore it with
`python -m v3.archive restore --manifest v3/amendments/01/retained-pilot-archive.json`
when reproducing this registration stage before a final archive exists. That
check never claims completed collection. CI chooses the appropriate mode from
the presence of the lossless archive manifest.

## Independent human review

Use [the V2 human rubric](../v2/ANNOTATION.md) and `v3.annotation` with a private
directory outside this public checkout. The V3 adapter preserves calibration,
reference blinding, locked submissions and independent arbitration. Prepare all
1,024 primary records, including invalid outputs; keep reviewer identities and
mapping keys private. Blank packets are not annotations.

`semantic-status.json` remains pending until actual independent human judgements
and any required third-human arbitration exist. Neither EM/F1 nor a language
model fills those labels. Local timing observations are not financial or
production-capacity measurements.
