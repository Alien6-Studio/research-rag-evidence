# V3 selection study: scientific results

Derived summary, 15 November 2026. The registered sentence-level MMR policy
improved complete annotated-context retention for BM25 at the 512-token cap.
The dense results were mixed, and no lexical-answer or unanswered contrast
passed the registered multiplicity correction. No human semantic validation
has been completed.

## Collection and provenance

The [protocol](PROTOCOL.md), [amendment 01](AMENDMENT-01.md) and their public
receipts distinguish the original registration from the prospective checker
correction. The [original pilot qualification](runs/pilot-controlled/qualification.json.gz)
remains failed and excluded: all 64 responses were captured, but a metadata-scope
check failed. A new disjoint pilot qualified under the
[amended instrument](runs/pilot-01-controlled/qualification.json.gz); its outputs
are not confirmatory observations.

The frozen new cohort contains 256 questions (128 bridge, 128 comparison).
Each environment has all 4,096 planned contexts: two retrievers, four policies,
two caps. The controlled generation subset contains 128 questions (64 per type)
and all 1,024 planned responses at 512 tokens. No generation was planned for
1,536 tokens or the separate pooled environment. V2 observations remain historical
evidence and are not pooled with these new questions.

Complete tables and question-level transitions are available in the
[controlled report](runs/confirmatory-controlled/RESULTS.md) and
[pooled report](runs/confirmatory-pooled/RESULTS.md), with lossless
[controlled JSON](runs/confirmatory-controlled/results.json.gz) and
[pooled JSON](runs/confirmatory-pooled/results.json.gz). The
[post-collection replay note](REPLAY.md) preserves a failed BM25 ranking replay
and documents a compatible hash-seed configuration; the original collection
seed is unknown. It does not change the frozen instrument, observed contexts,
failed pilot status or analysis rules.

## Controlled 512-token outcomes

A is ranked whole-chunk packing; B is chunk MMR; C extracts original sentences
in parent retrieval order; D applies question-aware sentence MMR. Every policy
shares the same retrieved top-ten chunks for its question and retriever.

| Retriever / policy | Complete annotated context /256 | EM /128 | Mean F1, failures = 0 | Valid explicit abstentions | Invalid outputs | Mean context tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 A | 136 | 62 | 0.602 | 26 | 1 | 479.4 |
| BM25 B | 126 | 62 | 0.598 | 25 | 2 | 479.6 |
| BM25 C | 146 | 62 | 0.599 | 26 | 1 | 498.9 |
| BM25 D | 203 | 71 | 0.687 | 15 | 1 | 502.3 |
| Dense A | 226 | 75 | 0.690 | 13 | 0 | 479.8 |
| Dense B | 222 | 74 | 0.684 | 13 | 0 | 479.9 |
| Dense C | 226 | 75 | 0.688 | 12 | 0 | 498.2 |
| Dense D | 215 | 72 | 0.689 | 12 | 0 | 502.8 |

The cap is equal; actual transmitted documentary length is not. In particular,
sentence policies use more of the available cap. D combines a sentence-level
query scorer with a redundancy penalty, so D versus C does not isolate the
effect of the penalty. Its measured mean sentence-pair redundancy is not
uniformly lower: BM25 D is 0.667 versus 0.649 for A.

The primary preservation family uses eight exact two-sided McNemar tests with
Holm correction. Differences and simultaneous intervals below are percentage
points; intervals are the prespecified 10,000-draw, type-stratified paired
bootstrap with conservative family size eight.

| Retriever / contrast | Gains / losses / unchanged | Difference [simultaneous interval] | Holm p |
| --- | ---: | --- | ---: |
| BM25 A → B | 7 / 17 / 232 | −3.91 [−8.98, +1.17] | 0.31957 |
| BM25 A → C | 15 / 5 / 236 | +3.91 [−0.78, +8.59] | 0.24834 |
| BM25 C → D | 69 / 12 / 175 | +22.27 [+13.67, +30.86] | 4.9231e−10 |
| BM25 A → D | 79 / 12 / 165 | +26.17 [+17.58, +35.45] | 2.3919e−12 |
| Dense A → B | 1 / 5 / 250 | −1.56 [−4.30, +0.78] | 0.43750 |
| Dense A → C | 3 / 3 / 250 | 0.00 [−2.73, +2.73] | 1.00000 |
| Dense C → D | 15 / 26 / 215 | −4.30 [−10.94, +2.34] | 0.43252 |
| Dense A → D | 14 / 25 / 217 | −4.30 [−10.94, +2.34] | 0.43252 |

For BM25, all annotated sentences were retrieved within the top ten for 223
questions. A then retained all of them in 136 cases, leaving 87 complete-retrieval
but incomplete-context cases; D reduced that count to 20. The net improvement
of 67 includes both 79 gains and 12 losses. Dense retrieved all annotations for
252 questions, with corresponding packing gaps of 26 for A and 37 for D.
The latter difference is not statistically established by the registered tests.

## Generated answers and uncertainty

The joint lexical/unanswered family contains sixteen tests, with separate Holm
correction from preservation and family-size-sixteen simultaneous intervals.
None rejected at .05. The numerically strongest BM25 answer contrasts remain
inconclusive after correction:

| BM25 contrast / outcome | 0→1 / 1→0 / unchanged | Difference, percentage points [simultaneous interval] | Holm p |
| --- | ---: | --- | ---: |
| A → D, EM | 11 / 2 / 115 | +7.03 [−0.78, +15.63] | 0.31445 |
| C → D, EM | 12 / 3 / 113 | +7.03 [−1.56, +16.41] | 0.45703 |
| A → D, unanswered | 3 / 14 / 111 | −8.59 [−17.97, 0.00] | 0.20361 |
| C → D, unanswered | 4 / 15 / 109 | −8.59 [−18.75, +0.78] | 0.28816 |

For unanswered, a 0→1 transition is adverse. The composite includes valid
explicit abstentions and invalid/failed outputs. Five outputs were retained
as invalid because they declared abstention while supplying a nonempty answer;
all had observed normally terminated response bodies. They score zero for
EM/F1 and one for unanswered. These are distinct from capture failures and
from the valid explicit abstentions in the arm table.

The remaining BM25 A→B/A→C EM differences were zero. Dense EM differences
were −0.78 points for A→B, zero for A→C and −2.34 points for C→D/A→D, all
Holm p = 1. Full intervals and every unanswered transition are in the linked
controlled report. Descriptive F1 rose from 0.602 to 0.687 for BM25 A→D;
F1 was not a confirmatory endpoint. Neither non-significance nor a degenerate
bootstrap interval under zero observed discordance establishes equivalence.

Usable outputs contained six invalid citation IDs in total. Existing IDs merely
identify transmitted sentences; their validity does not establish that the
sentence supports the answer. Across all 1,024 requests, 189 identical full-request
groups contained 431 outputs, including 242 repetitions beyond the first.
No message-content, parsed-answer or score variation was observed within these
groups. This is a local observation, not a guarantee of deterministic generation.

## Secondary settings and costs

At the controlled 1,536-token cap, all four policies had identical complete-context
indicators question by question: 223/256 for BM25 and 252/256 for dense. This is
a descriptive saturation result for these inputs, not general algorithmic
equivalence, and no answers were generated at that cap.

The exploratory pooled index contains 2,557 deduplicated paragraphs and 4,270
chunks from the new cohort. Its 512-token complete-context counts for A/B/C/D
were 115/106/118/167 for BM25 and 213/211/211/197 for dense. Thus the favorable
BM25 and mixed dense pattern also appears in this separate setting. At 1,536
tokens, BM25 counts were 191/191/191/193 and dense counts 243 for every policy.
This question-derived index is neither full-Wikipedia nor enterprise retrieval;
its results are not combined with controlled confirmation.

Controlled preparation acquired 4,478 new retrieval-vector inputs in 26.54 API
wall seconds and 7,341 new sentence-vector inputs in 40.90 seconds. These are
shared preparation costs, charged once rather than once per policy. Mean warm
selection time for A/D was 3.85/10.14 ms for BM25 and 3.60/9.91 ms for dense.
Generation wall times summed to 974.09 seconds across all 1,024 requests
(median 0.962 s, observed 95th percentile 1.185 s). These local observations
do not estimate financial cost, production latency or energy use. Pooled
preparation reused retrieval vectors and acquired 413 new sentence inputs in
2.45 seconds.

## Interpretation boundary

The [semantic status](semantic-status.json) remains pending with zero human
annotations, zero arbitrations and null semantic results. Blank review packets
are not labels; no LLM judge supplies missing decisions. Retaining every annotated
sentence is not proof of sufficient or exhaustive evidence, and lexical agreement
is not factual correctness or documentary support. The evidence supports a
BM25 annotated-preservation gain for this fixed sentence-selection policy,
cohort and cap. It does not establish a universal MMR benefit, a confirmed answer
gain, a dense-retrieval harm, or a causal path from retention to truth.
