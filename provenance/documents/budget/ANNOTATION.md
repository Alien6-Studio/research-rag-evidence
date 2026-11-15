# Independent human semantic validation

**Status: not performed.** All 1,024 primary outputs still require two independent
human annotations. The software prepares material, validates submissions and
computes agreement; it supplies no semantic judgement. Empty templates, lexical
matches, assistant interpretations and LLM verdicts are never human labels.

This guide implements the human protocol in [PROTOCOL.md](PROTOCOL.md). Freeze
these instructions before annotation. Calibrate the rubric on all 16 existing
gold-evidence controls, without showing earlier assistant readings. Discuss
ambiguities only after both submissions are locked. Complete any independent
arbitration and freeze a clarified rubric before primary annotation. If the rubric
changes, create fresh packets under its new hash; do not mix incompatible labels.

## Keep five questions separate

| Dimension | Question | Evidence and labels |
| --- | --- | --- |
| Lexical agreement | Does the normalized string match the official reference? | Existing HotpotQA EM/F1, computed independently of this workflow. A lexical mismatch is not a semantic verdict. |
| Semantic correctness | Does the answer correctly answer the question? | Phase2: `correct`, `incorrect`, `ambiguous`, `unverifiable`, or `not_applicable` for an abstention. Consider aliases and source/reference defects. |
| Whole-context support | Does the exact transmitted text establish every part of the answer? | Phase1: `supported`, `contradicted`, `insufficient`, `ambiguous`, or `not_applicable` for an abstention. |
| Citation validity and support | Do the IDs exist, and do the cited sentences establish the answer? | Record ID validity separately from citation-only support. A valid ID can cite irrelevant or incomplete evidence. |
| Abstention justification | Was declining to answer justified by the transmitted evidence? | Phase1: `justified`, `unjustified`, `uncertain`, or `not_applicable`. Do not equate a cautious refusal with an incorrect factual answer. |

`contradicted` requires affirmative conflicting text. `insufficient` means that
the supplied text does not establish the whole claim; it does not imply that the
claim is false. `ambiguous` records multiple reasonable readings. Do not use
prior knowledge in a context-only support judgement. Phase2 permits a separately
recorded external check, with URL and date, when the original sources cannot
settle correctness. Reference adequacy is a separate categorical label; an alias
or defective reference never silently changes the official lexical score.

Require a written rationale for every item. Supported labels need the relevant
sentence IDs; citation-only evidence must be among the sentences actually cited.
Correctness needs full-source coordinates or a dated external check. Alternative
evidence is legitimate even when it differs from HotpotQA's annotated sentences.

Retain the invalid/inconsistent output as one of the 1,024 items. Inspect its raw
model text rather than inventing a repaired response. Judge interpretable content
explicitly and describe any contradictory answer/abstention flags in the rationale.
Use uncertainty or non-applicability when a semantic judgement cannot be made.
No format failure automatically supplies a semantic label. Its original failure
and zero lexical score remain unchanged.

## Blinding and access

Two different reviewers receive separately randomized packets and different
random item aliases. Phase1 contains the question, raw answer, reported
abstention, exact transmitted context and cited text. It contains no reference
answer, gold support flags, question ID, configuration, model name, token budget
or lexical score. Phase2 adds the reference answer and all ten original source
paragraphs, without gold-support annotations, only after **both** reviewers have
locked their phase1 submissions.

The coordinator directory and mapping keys must be outside the public checkout.
Share only each reviewer's own released directory, never the coordinator root,
private data, other reviewer's labels, public result tables or raw configurations.
Public questions, repeated natural text and context length can still reveal or
suggest a condition. This is an unavoidable limitation, not perfect blinding.

Source packet hashes and rubric hashes bind submissions to their material.
Locking makes a preserved copy and checksum; it is an audit trail, not a secure
access-control system against a malicious coordinator. Human identities and
independence are declared by participants, not technologically proven.

## Prepare and release

Restore the supplied archives first. None of these commands calls Ollama.

```sh
python -m v2.archive restore
python -m v2.annotation prepare --scope calibration --directory /tmp/rag-calibration
python -m v2.annotation prepare --scope primary --directory /tmp/rag-primary
```

Calibration phase1 is released to `reviewers/R1/` and `reviewers/R2/` immediately.
The1,024 primary packets are prepared privately but stay unreleased until rubric
calibration is complete. Label templates contain null categories and blank
rationales. Reviewers fill every item; they must not edit their private originals.
They can use any local annotation editor preserving these JSONL fields and IDs.

Each reviewer submits a completed phase1 file independently:

```sh
python -m v2.annotation submit --directory /tmp/rag-calibration \
  --reviewer R1 --phase 1 --submission /path/to/R1-phase1.jsonl \
  --human-id reviewer-one --independent-human
python -m v2.annotation submit --directory /tmp/rag-calibration \
  --reviewer R2 --phase 1 --submission /path/to/R2-phase1.jsonl \
  --human-id reviewer-two --independent-human
python -m v2.annotation release --directory /tmp/rag-calibration --phase 2
```

After each independently completes phase2, submit using the same command with
`--phase 2` and that reviewer's phase2 file. The same human completes both phases.
No phase2 material is released if either phase1 is missing or incomplete.

## Disagreements and independent arbitration

```sh
python -m v2.annotation compare --directory /tmp/rag-calibration
```

This reports per-dimension agreement, nominal confusion tables and Cohen's
kappa **before arbitration**. Kappa depends on label prevalence; it is undefined
when expected chance agreement is one. Disagreements concern categorical labels;
different rationales or alternative source coordinates alone are not disagreement.
Both original rationales and evidence selections are retained.

The `arbitrator/` directory contains every disagreement, both independent label
sets, sources and an empty decision template. A third human who performed neither
initial review resolves every disputed item and supplies source evidence and a
reason. The arbitrator may choose a different label from both reviewers.

```sh
python -m v2.annotation arbitrate --directory /tmp/rag-calibration \
  --submission /path/to/arbitrator.jsonl --human-id reviewer-three --independent-human
python -m v2.annotation finalize --directory /tmp/rag-calibration
python -m v2.annotation release --directory /tmp/rag-primary --phase 1 \
  --calibration /tmp/rag-calibration
```

If there are no disagreements, `finalize` uses the two agreeing human labels.
Without an independent arbitrator for disagreements, status stays pending and no
semantic family is computed. This rule also applies to primary annotation.
Repeat the same two-phase submission, comparison and arbitration procedure for
the full primary directory, then finalize it. Never sample only convenient
configurations or discard abstentions, uncertainty or the invalid output.

## Analysis and publication

Only a complete agreed/adjudicated 1,024-item set enables the four protocol
comparisons: BM25 and dense ranked 512→1536, each for semantic correctness and
whole-context support, paired over the same 128 questions. Only `correct` or
`supported` scores 1. Uncertain/unverifiable and non-applicable labels remain
separate categories and score 0 for the conservative endpoint. A sensitivity
analysis excludes pairs with ambiguous/unverifiable labels and reports its
changed denominator. Missing human annotations are never scored as failure.

The script uses the protocol's 10,000 question-within-type bootstrap draws,
simultaneous Bonferroni intervals, exact McNemar tests and Holm correction within
the separate four-test semantic family. It never alters the lexical family.
Citation validity, citation-only support and abstention justification remain
separate descriptive results; they do not become extra primary tests.

Keep participant identities and mapping files private. After validation, the
coordinator can release appropriately anonymized labels and aggregate results
with participant permission. Until then, the public semantic status is pending.
