# V3 amendment 01: metadata verification and a replacement technical pilot

Amendment date: 15 November 2026. This amendment is published before any
confirmation or replacement-pilot outcome. The original registration remains
at `90fecf74f2cbfeaf52618688681c366430604042`, tag
`protocol-rag-v3-2026-11-15`, and PR 15 was created at
2026-11-15T16:53:18Z. Original V3 collection started afterwards.

## Observed technical failure

The original eight-question pilot prepared 128 contexts and archived all 64
planned responses without capture errors. Its qualification remains **failed**:
the independent checker reported
`Replayed value differs: preparation-start.scope`.

The checker compared every start-record field to the final preparation record.
The start's `scope` describes local quality measurement, while the final record's
`scope` describes the controlled corpus. These strings intentionally describe
different things. Their inequality is a checker defect, not a model-quality
criterion. No response is corrected or regenerated, and the failed certificate
is never replaced with a passing one.

## Prospective correction and unchanged comparisons

Validate shared scientific execution metadata identically, and validate the two
scope descriptions separately for their respective stages. Retain all ranking,
source-coordinate, rendering, tokenizer, request, raw-response, error, timestamp
and model-identity checks. An end-to-end synthetic pilot exercises the collector
and verifier together before the amended instrument is frozen.

The four policies, lambda, similarities, canonical rendering, retrievers,
budgets, generator, prompts, options, analysis families and the full 256-question
confirmation cohort and 128 generation IDs are unchanged. No main-cohort outcome
has been collected. No answer-quality measure determines the amendment or the
selection of the replacement pilot.

Choose eight replacement questions with seed 20261216, four per type, under the
same eligibility rules. Exclude V1, both V2 samples, the original V3 pilot and
all already frozen V3 confirmation questions by ID, normalized question and
supporting-document title. Preserve the original confirmation cases and
generation membership byte for byte as values. Record the new selection's
actual timestamp and exclusions; do not change any cohort after its outcomes.

The original files remain at `data/cohorts.json`, `registration.json`,
`public-registration.json` and `runs/pilot-controlled/`. The active files are
`data/cohorts-amendment-01.json`, `registration-amendment-01.json`,
`public-registration-amendment-01.json` and `runs/pilot-01-controlled/`.
`PROTOCOL.md` remains the original text; this document records the prospective
changes rather than editing that historical registration.

## Retained evidence and inherited vectors

[`amendments/01/prior-evidence.json`](amendments/01/prior-evidence.json) binds the
original failed pilot, cohort, registration, public receipt and cached embedding
packets to exact hashes. Its separate lossless archive preserves raw timestamps
and bodies. The original executed source remains inspectable in the protected
protocol tag. A corrected diagnostic replay may describe the original records;
it never changes their failed eligibility or uses them as new pilot repetitions.

Only label-free embedding vectors from those exact packets may be reused as
cached inputs. Their hashes and original publication/collection chronology are
checked separately. New packets and replacement-pilot/main outcomes must follow
the amended publication timestamp. No old generated answer supplies a new answer.

## Public amendment and qualification

Publish the amended registration and complete instrument under protected tag
`protocol-rag-v3-2026-11-15-a1`. The active receipt records the actual GitHub
protocol-release publication timestamp. The older PR creation time is preserved
as context and is not reused as the amendment's publication time.

The new pilot must independently pass all 128 contexts, 64 raw responses, three
tokenizer probes, source/metadata guards and exact preparation/request checks.
The certificate binds every pilot input and execution file. Confirmation remains
blocked until that new certificate passes. The earlier failed pilot is retained
in the final archive and reported separately. Human semantic labels remain
pending, and no automatic judge supplies them.
