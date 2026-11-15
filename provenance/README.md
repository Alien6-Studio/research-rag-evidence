# Provenance and lossless relocation

The repository presents one final research state, organized by purpose. Original
scientific files retain their bytes, modes, timestamps recorded inside evidence,
observed failures and scores. Relocation does not create a new experiment,
preregistration or semantic validation.

## File and Git identity

[layout-map.json](layout-map.json) maps 1,384 original paths to published
functional paths, with 162,369,940 source bytes. Every entry records its byte
length, SHA-256, Git blob identity and mode. The map also retains the captured
source commit and root-tree identities. New reading guides and the reproduction
launcher are separate from these preserved files.

`python reproduce.py check`, run from the repository root, checks the relocated
files and reconstructs their captured Git tree and commit in an isolated
temporary workspace. It also validates the compact
[registration proofs](registration-proofs/), which bind the original registered
file bytes to their original commit identities. It requires neither a dataset
nor a network connection, and makes no model call.

The temporary workspace restores the original paths required by the unchanged
instrument. It does not add historical objects or development refs to the
public checkout's Git store. The public repository and its final data tag
identify one current snapshot; captured Git identities are evidence carried as data.

## Registration, collection and later packaging

The [registration records](registrations/) retain the captured public receipts
and their dates. The initial pilot's qualification remains failed. A prospective
amendment preceded a distinct replacement pilot and confirmation collection;
the failed pilot is not relabelled or reused as confirmation evidence.

The [captured publication metadata](registration-proofs/publication-record.json)
and [original API response](registration-proofs/original-release-response.json)
retain the original publication context. A later repository commit or file
relocation is not evidence of earlier public availability. Git dates and captured
publication records are not independent timestamp attestations. Recorded
historical URLs may no longer resolve after public refs are retired.

## Archive and numerical replay boundaries

[Archive inventories](archives/) distinguish compressed storage hashes from
restored-content hashes. [Preservation inventories](inventories/) retain the
input and excluded-pilot identities. Captured specifications, reports and review
material are in [documents](documents/); their internal links retain the original
layout. [EVIDENCE.md](../EVIDENCE.md) supplies current functional locations.

Full `python reproduce.py verify` restores the evidence in the isolated workspace
and invokes the frozen verification chain. It checks saved vectors, rankings,
selected source text, budgets, raw requests/responses and paired analyses without
requesting model generation. `test` runs the preserved controls. Reports are
written to a new output directory rather than into the evidence records.

The numerical replay setting of `PYTHONHASHSEED=10` was found after context
collection by comparing ranking fingerprints. The original collection seed
remains unknown. This setting is not retroactively preregistered. The
[captured note](documents/selection/REPLAY.md) and
[diagnostic records](numerical-replay/) preserve the failed replay and the search.
Numerical reconstruction is neither independent physical generation nor human
semantic adjudication. Those interpretation limits remain in [VALIDITY.md](../VALIDITY.md).
