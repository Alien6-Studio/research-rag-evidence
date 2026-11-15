# Post-collection BM25 replay configuration

This note records a computational reproducibility issue discovered **after the
V3 contexts had been collected**, while the planned response collection was
still running. `PYTHONHASHSEED=10` is an explicit **post-collection replay
configuration**. It was not preregistered. The original collection hash seed was
not captured and remains unknown; finding a compatible replay seed does not
identify it.

The public [initial registration](registration.json),
[original publication receipt](public-registration.json),
[amendment registration](registration-amendment-01.json) and
[amendment publication receipt](public-registration-amendment-01.json) remain
unchanged. The [excluded initial pilot](amendments/01/prior-evidence.json) retains
its original failed qualification. This note does not requalify that pilot.

## Failure and cause

The [original failed replay log](replay/initial-failed-replay.log) is preserved
byte for byte. The frozen verifier rejected
`retrieval fingerprints[28].ranking_sha256` in the pooled environment. The
failure occurred after its checks of the saved top ten chunks, selected
contexts and context metrics; a hash of the complete ranking then differed.
The seed of that initial failed replay was also not recorded.

The original [BM25 function](../run.py) iterates over
`set(words(question))` and adds term contributions in that iteration order.
Python's interpreter hash seed can change that order. Floating-point addition
can consequently differ by a few units in the last place. The frozen
[ranking function](../v2/core.py) sorts by the resulting exact floating-point
score, then chunk ID. No rounding, score replacement, tie permutation or
monkeypatch was introduced to handle this issue. The frozen
[V3 verifier](verify.py) and its existing numeric tolerance are unchanged.

## Controlled diagnostic

The diagnostic examined ranking fingerprints and input chunks only, without
using answer quality or policy outcome differences to choose a seed. Fresh
interpreters tried seeds 0 through 10 on question
`5a739ef955429978a71e904b` in the pooled corpus. Seeds 0–9 reproduced the same
nonmatching complete ranking; seed 10 was the first matching seed in that
search. The [search record](replay/seed-search.json) records every attempt.

The [complete target ranking under seed 0](replay/target-seed0.json) and
[matching ranking under seed 10](replay/target-seed10.json) differ only at **one-based
ranks 226 and 227**, far below the top ten:

| Seed | Rank 226 | Rank 227 |
| --- | --- | --- |
| 0 | `d1377p000`, 4.114400305226006 | `d1767p000`, 4.114400305226006 |
| 10 | `d1767p000`, 4.114400305226007 | `d1377p000`, 4.114400305226006 |

The changed score differs by `8.881784197001252e-16`. The maximum difference
over all scores in these two rankings is `3.552713678800501e-15`. These
differences are below the verifier's pre-existing absolute numeric tolerance
of `1e-12`; the complete-order SHA check remains exact and was not relaxed.
All ten retrieved chunk IDs remain identical.

A complete BM25 inventory under seed 10 reproduces **528 of 528 full-order
fingerprints**, with **zero top-ten ID differences**:

| Collection | Full rankings | Exact fingerprint matches |
| --- | ---: | ---: |
| Confirmatory controlled | 256 | 256 |
| Confirmatory pooled | 256 | 256 |
| Active amendment pilot | 8 | 8 |
| Excluded original pilot, diagnostic only | 8 | 8 |

These are 528 ranking records, rather than 528 distinct questions. The
[controlled report](replay/bm25-controlled-seed10.json),
[pooled report](replay/bm25-pooled-seed10.json) and
[pilot report](replay/bm25-pilots-seed10.json) retain each expected and replayed
SHA. For comparison, seed 0 reproduces all 256
[controlled rankings](replay/bm25-controlled-seed0.json), and 255 of 256
[pooled rankings](replay/bm25-pooled-seed0.json), again with zero top-ten ID
differences. This diagnostic covers BM25 ranking fingerprints. The complete
frozen verifier separately checks dense retrieval, selection, archived responses,
provenance and analyses; a compatible BM25 inventory alone is not a completed
experiment verification.

The [diagnostic inventory](replay/diagnostic.json) binds these reports, the
original failure log, the reproduction helper and frozen source hashes. At this
audit, all 420 historical files, 38 retained prior-evidence files and 30 active
registered files matched their preserved hashes. No frozen source or
observation was rewritten, and no model was called for the diagnostic.

## Offline reproduction

Use the pinned Python environment and restore the published archives as
described in [the V3 README](README.md#offline-reproduction). The helper is
deliberately outside the registered `v3/*.py` instrument:

```sh
python validation/v3_hashseed_audit.py --seeds 10 --output replay-local-seed10.json
python validation/v3_hashseed_audit.py --seeds 0,10 --scope confirmatory-pooled \
  --question 5a739ef955429978a71e904b --output replay-local-target.json
PYTHONHASHSEED=10 python -m v3.verify --require-collected
```

The helper starts a fresh interpreter for each requested seed and calls the
unchanged original ranking implementation. It refuses to overwrite its output
report. To repeat the entire target search, use `--seeds 0,1,2,3,4,5,6,7,8,9,10`
with the same target and pooled scope. No inference endpoint is used.

CI sets `PYTHONHASHSEED: '10'` only on its V3 verification step. This provides a
compatible replay configuration for the published bytes, not a promise of
bitwise replay across every Python implementation, platform or dependency
version. A future collection should preregister a hash seed or a deterministic
summation order prospectively. Neither correction has been retroactively
inserted into this frozen experiment.
