# Selection study: retained computational paths

The repository presents one final study snapshot. Start with the
[main reading guide](../README.md), [results](RESULTS.md),
[article evidence ledger](ARTICLE_EVIDENCE.md), [validity boundaries](VALIDITY.md)
and [method review](LITERATURE.md).

This directory name is retained for exact compatibility with the registered
instrument, archived paths and numerical checks. It does not identify another
supported release. The four policies, fixed cohorts, raw observations, original
qualification decisions and scores remain unchanged.

## Offline verification

Use Python 3.12 and the root dependency lock. Restore all evidence before running
the controls:

```sh
python prepare_data.py
python -m v2.archive restore
python -m v3.archive restore --manifest v3/amendments/01/retained-pilot-archive.json
python -m v3.archive restore
python -m unittest discover -p 'test_*.py' -v
python -m v2.verify --output v2/verification.json
PYTHONHASHSEED=10 python validation/replay_registered.py --require-collected
```

No inference service is used. The wrapper verifies the compact
[registration proof](../provenance/), exposes its original commit/tree/blob objects
only in a temporary object database, and invokes the unchanged registered verifier.
There is no requirement to fetch historical tags or retain old branch history.
The final `main` branch has one commit; the final data tag identifies that snapshot.

Read [the numerical replay note](REPLAY.md): the original collection hash seed
was not captured. Seed 10 is a compatible replay setting found after context
collection using exact ranking fingerprints; it was not preregistered. The
excluded initial pilot remains failed in its original certificate. Its replacement
qualified under the [publicly recorded amendment](AMENDMENT-01.md). Original
publication identities and timestamps remain in the receipts and proof capsule;
the repository's later consolidation is not a new preregistration.

## Independent human review

The [existing rubric](../v2/ANNOTATION.md) and `v3.annotation` support calibration,
reference-blinded phases, locked submissions and independent arbitration. Prepare
packets in a private directory outside this public checkout. All 1,024 primary
outputs, including the five invalid outputs, must remain in scope. The
[semantic status](semantic-status.json) remains pending: prepared packets,
lexical scores and model judgements are not independent human labels.
