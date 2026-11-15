# Prospective RAG selection study V3

Protocol date: 15 November 2026. This extension preserves V1/V2 observations,
annotations, scores and source identities. Its registration, cohort, executable
instrument and tests must be publicly committed before any V3 model or context
outcome is collected. Actual GitHub publication and collection timestamps are
retained; this is not a backdated registration.

## Questions and fixed scope

At identical retrieved top-ten passages and documentary token budget, do MMR
or original-sentence extraction retain more annotated information than V2
ranked packing? Do the same paired questions show changes in lexical answers
or unanswered outcomes? Preserved annotations, lexical agreement, semantic
correctness and documentary support are distinct endpoints.

The primary budget is 512 tokens. A 1,536-token deterministic sensitivity is
secondary; no additional generation is planned at that budget. A new controlled
cohort supplies 256 questions, balanced 128 bridge/128 comparison. A fixed,
outcome-blind subset of 128 (64 each type) supplies 1,024 generated answers.
An independent eight-question technical pilot supplies 128 prepared contexts
and 64 generations at 512 tokens. No cohort is reduced after observing outcomes.

## Feasibility and power before collection

The pinned data contain 7,405 questions. Excluding all 64 exploratory, eight V2
pilot and 256 V2 confirmation cases leaves at least 1,219 comparison and 5,705
bridge candidates before internal V3 support-title separation. This supports the
requested sizes without reusing the earlier samples as prospective evidence.

The retained V2 512-token requests took 510.45 seconds for 512 outputs on this
workstation. Extrapolation gives about 17 minutes for 1,024 V3 outputs, plus
loading, embeddings and pilot work. These historical timing estimates are not
V3 observations or portable latency claims. Both exact Ollama model digests,
the pinned dataset/tokenizer, 128 GiB host memory and the maintained dependency
lock are available. The main deterministic design has 4,096 contexts.

`data/power-planning.json` records paired-binary normal-approximation scenarios
at 80% power with assumed 10/30/50% discordance. The preservation family has
eight tests (conservative alpha=.05/8); the lexical/unanswered family has sixteen
(alpha=.05/16). These are planning assumptions, not observed power. Small answer
effects may remain inconclusive. Non-significance never establishes equivalence.

## Cohort selection and separation

Use exactly the dataset/tokenizer in `sources.json`. New cohort seed is
20261115; pilot, confirmation, generation subset and job order use offsets
+1/+2/+3/+5. Sampling sorts by ID, seeded-shuffles within type, then takes the
first eligible cases. Exclude IDs, normalized questions and supporting-document
titles from V1, the V2 pilot and V2 confirmation, then from already selected V3
cases. Require valid annotations and ten supplied paragraphs. Pilot is selected
first. Freeze all IDs and generation membership before outcomes.

Support flags are used only for eligibility/separation and subsequent evaluation.
The selectors receive the question, public retrieved text/coordinates and
vectors, never references, annotations, type labels or generated outcomes.
Explicit tests change/remove answers and support flags and require identical
selections and transmitted text. Support-title-disjoint sampling is not a simple
random sample; shared distractors, topics and pretraining exposure remain possible.

## Four policies and exact rendering

Retrieval is V2 BM25 or nomic cosine search on non-overlapping three-sentence
chunks; top ten, tie by chunk ID. All four policies share the same saved ranking
for a question/retriever. All policies receive the same frozen retrieval ranking;
selection never changes retrieval and never uses reference annotations.

* **A `ranked`:** V2 whole-chunk packing, unchanged, skipping a chunk that does
  not fit before trying later chunks.
* **B `mmr`:** greedy MMR of those ten chunks. Relevance is the original retriever
  score min-max normalized within the ten candidates; a constant score maps to
  zero. Redundancy is maximum positive cosine similarity of nomic chunk vectors
  to accepted chunks (zero for an empty set). Score is
  `0.5 * relevance - 0.5 * redundancy`. Ties use chunk ID. Non-fitting candidates
  are skipped without entering the accepted set.
* **C `sentences`:** original sentences from those same ten chunks, traversed by
  parent retrieval rank then original sentence position. Skip a non-fitting
  sentence and continue. No additional relevance model is used.
* **D `sentence_mmr`:** the same sentence candidates, with greedy MMR. Relevance
  is min-max normalized cosine to the same question embedding; sentence vectors
  embed `search_document: TITLE\nSENTENCE`. Redundancy, lambda, empty-set rule,
  skipping and deterministic ID ties follow B. This combines a sentence-level
  query scorer with redundancy control; C/D does not isolate the penalty alone.

All selections render canonically in original parent retrieval order and source
sentence order. Selected sentences sharing a parent use its original chunk
header once. A/B use the original V2 context representation exactly. C/D preserve
the original sentence IDs, bodies, titles and parent coordinates. Every proposed
addition is tokenized after full rendering, including headers, IDs and separators.
Final contexts may not exceed their budget; nothing is silently truncated.
Canonical rendering controls gratuitous selection-order changes, but changed
content still changes relative positions and distractors.

B/D are explicitly specified modern MMR variants, not reproductions of SMART,
RECOMP, LongLLMLingua or SetR. Lambda and all rules above are fixed without
optimizing on pilot answer quality or new annotations. Learned/abstractive/token
compression is excluded: it adds substantial dependencies and would require a
different semantic measure from intact original-sentence retention.

## Instrument, pilot gate and stopping

Use the original `run.MODELS` generator/embedding digests, pinned tokenizer,
`run.SYSTEM`, answer schema and generation options unchanged: temperature zero,
seed 20261112, num_ctx 8192, num_predict 256, eight threads, thinking disabled.
Record live model metadata, Ollama version, Python/dependencies, host metadata,
source/registration hashes, exact requests, raw response bodies and real times.
No optional judge model is used and no new model weights are needed.

Before confirmation, three fixed V2 raw-prompt tokenizer probes must match Ollama
prompt token counts. All 128 pilot contexts must pass membership, budget and
label-free selection checks; all 64 planned pilot responses must be archived
once, untruncated and instruction-consistent JSON. Explicit abstention is valid;
no EM or semantic-quality threshold determines qualification. A failed pilot is
retained and stops confirmation. A correction needs a recorded prospective
amendment and a new disjoint pilot, never selective regeneration.

Sequential generation archives a request intent before sending. Every planned
request remains in its denominator. Recorded errors are never retried. An intent
without an observed response becomes an interrupted/unknown error on resume.
Stop after three consecutive failures, preserve them and record any resumed
execution. Restarting the process does not reset the consecutive-failure gate;
resumption after that gate needs a prospective recorded amendment. Do not stop
on effect size or significance. Missing resources or
interruption imply incomplete collection, never a reduced completed cohort.

## Measures and statistical families

Question is the paired unit. For each retriever at 512 tokens the four fixed
contrasts are B-A, C-A, D-C and D-A. Primary preservation uses complete annotated
context on 256 questions: eight two-sided exact McNemar tests with Holm at .05.
Report gains, losses and unchanged outcomes, 10,000 type-stratified paired
bootstrap draws (seed 20261115), ordinary 95% and conservative simultaneous
Bonferroni intervals for the declared family of eight.

On the fixed 128 generation questions, EM and unanswered (explicit abstention
or invalid/failed output) use the same eight contrasts in one family of sixteen
Holm-corrected tests and simultaneous intervals. Failures score zero for EM/F1;
explicit abstentions and invalid outputs remain separately counted. F1,
fractional coverage, 1,536-token contrasts and other contrasts are secondary
descriptive outcomes, not additional confirmatory discoveries.

Archive partial annotated coverage, exact tokens, retrieval loss versus packing
loss, annotated source ranks and context positions, distinct sources and pairwise
positive cosine redundancy. Retain EM/F1, citations/invalid IDs, abstention,
individual transitions and identical full-request fingerprints. Different answers
under identical prompts cannot be credited to different selection policies.

Embedding acquisition, shared retrieval preparation, warm policy selection and
generation wall/API timings are instrumented separately. Additional sentence
vectors are an explicit preparation cost; shared cached work is not billed once
per arm. Timing is local descriptive evidence, not financial, energy or production
cost. No causal mediation claim links coverage changes to truthful answers.

## Separate pooled sensitivity

The new cohort's public paragraphs form a separate deduplicated shared index,
using title/full-sentence-array hashes. Apply the same retrievers, four policies
and budgets to all 256 questions, without generation. Its question-derived
candidate competition and longer global IDs differ from the controlled setting.
All relevant sources exist by construction. Report this exploratory environment
separately; do not pool it with controlled results or call it full-Wikipedia or
enterprise retrieval. V2's pooled experiment remains unchanged and separate.
The V3 index is rebuilt from the new cohort: reusing only V2's 2,547 paragraphs
would not ensure the new, support-disjoint cohort's annotated sources are present.

## Human evaluation and publication

Reuse V2's rubric, two independent reviewers, calibration lock, reference-blinded
first phase, locked submissions and independent third-human arbitration. A V3
adapter supplies its own items/final contrasts while retaining `scope=primary`
calibration protection. Mapping keys/identities remain outside the public repo.
Prepare blank packets for all 1,024 outputs; no LLM or assistant fills any label.
Semantic validation remains pending until actual complete adjudicated decisions.

If complete human decisions become available, the eight registered 512-token
contrasts for correctness and whole-context support form a separate family of
sixteen exact McNemar/Holm tests with the same paired bootstrap intervals.
Only `correct` or `supported` scores one for its respective endpoint; uncertain
or unverifiable decisions score zero in the conservative primary estimate and
remain separately tabulated. Report a sensitivity excluding uncertain pairs
with its changed denominator. Citation-only support and abstention justification
remain separately described. No such family is computed from automatic labels.

Publish all outcomes, including negative or mixed effects. Preserve V2 and V3
denominators and distinguish annotation coverage from sufficient evidence,
lexical match from factual truth, and valid IDs from supported citations. V3
claims concern these frozen policies, data and one model. The French article may
use only qualified observations and must state the real human-review status.

See `LITERATURE.md` for primary sources and the evaluated implementation scope.
