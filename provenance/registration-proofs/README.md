# Registered-input provenance

This directory preserves the original registration proofs while the public
repository presents one final state. It does **not** restore earlier branches,
tags or a traversable development history. The scientific inputs, observations,
failures and frozen instruments retain their original bytes and module paths.

## What the dates mean

The [initial receipt](../v3/public-registration.json) records the public pull
request created on **15 November 2026 at 16:53:18 UTC**, associated with original
commit `90fecf74f2cbfeaf52618688681c366430604042`. The
[amendment receipt](../v3/public-registration-amendment-01.json) records the
protocol release published at **17:14:23 UTC**, associated with original commit
`62657fd9774943b09552f8a9895e7877243a8664`.

These are the captured publication records of the original experiment. The
amendment followed the first pilot's technical failure and preceded the new
pilot and confirmation collection. The failed pilot remains excluded. The
consolidated repository commit is a later packaging event: it is neither a new
preregistration nor a retroactive preregistration. No observation or timestamp
was changed to make the collection appear prospective.

[publication-record.json](publication-record.json) retains selected metadata
from the previously captured GitHub release API response, including its release
ID, original target commit and publication time. The original receipts remain
unchanged. Their historical URLs are recorded references; this package does not
promise that retired tags or release URLs still resolve. A captured publication
record is not an independent timestamp attestation, and a Git author/committer
date alone does not establish public availability.

## The partial Merkle proof

- [registration-objects-manifest.json](registration-objects-manifest.json)
  lists both registration identities, publication references, all 56 registered
  path bindings and the hashes, types and sizes of 51 Git objects.
- [registration-objects.json.gz](registration-objects.json.gz) contains a
  standalone Git pack inside compressed JSON. Its 51 objects comprise two
  commits, eight trees and 41 blobs. The capsule is 741,017 bytes; the embedded
  pack is 733,658 bytes.

The proof contains only the commit-to-tree-to-file paths required by the frozen
verifier. Parents of the old commits and unrelated siblings named in their
trees are intentionally absent. It proves the registered bytes under those
commit IDs; it is not a complete old object graph. It must therefore remain
separate from the normal Git object store and should not be mistaken for a
restored repository history.

## Offline checks and replay

Use a Git checkout and the pinned Python environment described in the
[main guide](../README.md). A shallow checkout of the final state is sufficient;
no old tag fetch is required. This lightweight check needs no committed `HEAD`
and makes no model call:

```sh
python validation/replay_registered.py --check-capsule
```

For full verification, first prepare the pinned dataset/tokenizer and restore
the lossless evidence archives using the commands in the main guide. Then run:

```sh
PYTHONHASHSEED=10 python validation/replay_registered.py --require-collected
```

The wrapper checks the compressed and decoded capsule, the pack, every Git
object's SHA-1 identity and SHA-256 content hash, and all 56 Merkle path bindings
against the two anchored registrations and their unchanged public receipts.
Unrelated objects and false path bindings are rejected. It loads the proof only
into a temporary object directory, using the current checkout's object store as
a read-only alternate. It creates no historical refs and does not add the old
objects to the normal `.git/objects`. The temporary directory is removed after
success or failure.

The child command is the unchanged `python -m v3.verify --require-collected`.
Its stdout is forwarded unchanged, so the full replay's JSON remains the sole
stdout report; failures retain their nonzero exit status. The verification uses
saved inputs and responses without calling a model or filling semantic labels.
The numeric hash seed of 10 is the documented
[post-collection replay configuration](../v3/REPLAY.md), not a newly asserted
collection parameter.
