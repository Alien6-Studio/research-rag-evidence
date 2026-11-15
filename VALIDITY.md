# Validity and interpretation

The evidence establishes recorded computations and outcomes on fixed cohorts.
It does not establish a generally optimal architecture, production capacity or
human semantic accuracy. Read [results](RESULTS.md), [methods](METHODS.md) and
the [evidence index](EVIDENCE.md) together.

## Separate outcomes

Annotated sentences are evaluation landmarks, not an exhaustive set of necessary
or sufficient evidence. Losing one does not prove that every valid route to an
answer was lost. Retaining them all does not prove that the model used them or
that its answer is correct. A lexical match does not establish documentary support;
a valid citation ID only establishes that the identifier exists.

Independent semantic review is pending. The
[selection status](results/selection/semantic-status.json) records zero human
annotations, zero arbitrations and null semantic results. Blank packets,
automatic judgements, EM and F1 cannot replace those labels. The
[diagnostic status](results/budget/semantic-status.json) remains separate.

## What the interventions identify

The budget diagnostic changes documentary capacity while keeping rankings fixed.
The selection comparison tests complete policies. D adds sentence-level query
relevance and a redundancy penalty to C, so it does not isolate either component.
Its measured redundancy is not uniformly lower: BM25 D averages 0.667 versus
0.649 for A on the common sentence-pair metric.

All policies pay the full rendered reference overhead. Their actual lengths
differ: BM25 A/D averages 479.4/502.3 tokens at the same 512-token ceiling.
Changing retained content also changes positions and distractors. There is no
causal mediation test attributing an answer change solely to extra annotations,
and no independent position intervention.

The positive result is BM25 annotated-preservation improvement for the specified
sentence policy, cohort and ceiling. It is not a universal MMR benefit. Dense
results do not confirm a benefit or a deterioration for D against A. None of
the sixteen registered lexical/unanswered contrasts establishes an answer gain.
Failure to reject is not equivalence; descriptive F1 is not a confirmatory endpoint.

## Population and dependence

Each controlled question searches ten supplied paragraphs, an assisted candidate
set. Separate pooled indexes are derived from the cohorts and remain exploratory;
they are neither full-Wikipedia nor enterprise retrieval. Different global IDs
also change token overhead, so cross-environment differences are not corpus size alone.

Cohorts are separated by question and supporting-document title, but topics and
distractors may remain shared. Eligibility/separation using support annotations
makes sampling conditional and sequential, not a simple random sample of every
HotpotQA question. Public-dataset pretraining exposure is unknown. The studies use
English questions and one quantized Qwen generator; transfer remains unmeasured.
Repeated configurations do not multiply the independent number of questions.

## Failures, timing and reproducibility

Invalid outputs remain in the planned denominator. The selection comparison's
five invalid outputs were observed, normally terminated responses with an
instruction violation, not capture failures. Valid explicit abstentions and
invalid outputs are reported separately as well as in the unanswered composite.
The initial unqualified pilot remains excluded and byte-preserved; its replacement
followed a documented prospective amendment without an answer-quality gate.

Embedding acquisition, shared preparation, warm selection and generation have
different cost scopes. Cached work is not charged once per policy. Local runtime
depends on the workstation and concurrent activity; it does not measure money,
energy, sustainable throughput or guaranteed production latency.

The original interpreter hash seed was not captured. A compatible seed of 10
was identified after context collection from ranking fingerprints, without using
answer quality or policy effects. It is a post-collection numerical replay setting,
not a preregistered collection parameter or proof of the original seed.
The [captured replay note](provenance/documents/selection/REPLAY.md) preserves
the initial failure, divergent ranking witness and diagnostic search.

Reproduction checks relocated bytes, original Git identity, sources, saved
vectors, contexts, raw response parsing and statistical analyses. It makes no
new model calls. It neither repeats physical generation on another machine nor
independently validates semantic labels. Later path relocation is packaging,
not a new or retroactive preregistration; see [provenance](provenance/README.md).
