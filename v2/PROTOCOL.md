# Prospective RAG validation V2

Registration date: 13 November 2026. This is a new prospective study, not a
backdated extension of the 12 November exploratory campaign. The historical
protocol, annotations, raw generations, and scores remain unchanged. No article
or website changes are part of this mission.

The public registration commit must contain this document, the cohort file,
analysis code, execution code, tests, and their SHA-256 registration inventory
**before the first V2 outcome is collected**. Any amendment must be published
before affected collection and must retain the original registration and failed
pilot. Outcome-driven amendments do not become confirmatory results.

## Questions and possible refutations

H1: with the same retrieved top-ten chunks, changing the context budget or
selection policy can change retained annotated sentences. Measure this before
answer generation, directly from the exact rendered/tokenized context. A zero
paired change or a loss is a valid result. Annotated coverage is not a semantic
faithfulness label.

H2: does greater retained coverage accompany different answer outcomes? Measure
lexical agreement, explicit abstention, execution failure, independently judged
correctness, and independently judged support separately. Do not assume a linear
relationship. Report all cases with complete annotated context and zero lexical
match, including abstentions. These flags do not establish factual error.
Budget interventions also change length, distractors, and possibly ordering;
their effect cannot be attributed causally to coverage alone.

H3: at the same budget, compare BM25/dense and ranked/diverse selection. No MMR,
reranker, prompt optimization, or new model is included in confirmation.

## Data and outcome-blind selection

Use the exact pinned HotpotQA distractor validation Parquet in `sources.json`.
Retain its CC BY-SA 4.0 attribution (Yang, Qi, Zhang et al., EMNLP 2018).

- Pilot: 8 new questions, 4 bridge and 4 comparison; all eight configurations
  (64 generations). This tests the instrument, not answer quality.
- Deterministic confirmation: 256 new questions, 128 per type; all eight
  configurations (2,048 contexts).
- Generation confirmation: 128 of those questions, 64 per type, selected before
  outcomes (1,024 primary generations).
- Stability: 16 of the generation questions, 8 per type; two additional runs of
  the identical BM25/ranked/512 request (32 generations). These do not increase
  the primary question denominator and do not replace primary answers.

`select_cohorts` sorts the pinned data by ID, shuffles with the recorded seeds,
and takes the first eligible questions within type. The pilot is selected first.
Exclude historical IDs, duplicate normalized question strings, invalid source
coordinates, cases without ten paragraphs, and any supporting-document title
already used by a historical, pilot, or selected confirmatory question. Record
the exclusions actually encountered. The confirmatory generation and stability
subsets are separate seeded draws from the eligible frozen cohort.

This support-document-disjoint sequential design prioritizes separation. It is
not a simple random sample of all HotpotQA and may underrepresent frequently
reused entities. Shared distractors, common topics, public-data pretraining, and
other dependence remain possible. Balanced samples do not estimate an unknown
production question distribution.

Do not replace questions based on difficulty, model success, annotation
controversy discovered after collection, or observed effect size. Maintain
intention-to-collect denominators. Any revised-reference analysis is exploratory
and preserves the official original scores.

## Instrument and fixed comparisons

Keep the original generator and embedding digests, tokenizer revision and hash,
JSON schema, system prompt, temperature 0, seed 20261112, num_ctx 8192,
num_predict 256, num_thread 8, thinking disabled, and sequential requests.
The new cohort/randomization seed is 20261113; it does not change the model seed.

Controlled indexing uses only each question's ten supplied paragraphs, without
answer references or support annotations. Three original sentences per chunk,
without overlap or sentence truncation; titles and coordinates are preserved.
The rendered controlled context must match the historical format exactly.

BM25 uses k1=1.5, b=.75, nonnegative Robertson-style IDF, lowercase Unicode word
tokens, unique query terms, and no stemming/stopword removal. Dense search uses
the same nomic prefixes, cosine similarity, and float64 archived vectors. Break
score ties by chunk ID. Rank all chunks, retrieve ten, then select ranked or
document-diverse (one title per round) chunks under 512/1536 tokenizer tokens.
Skip whole non-fitting chunks; the budget includes headers, IDs, and separators.

Indexing is label-free. Annotation validation and scoring are separate. In the
pooled corpus, title alone cannot identify a paragraph version: use a hash of
the title and complete original sentence array plus the sentence coordinate.

## Technical pilot gate

Before confirmation, the three fixed raw-prompt tokenizer calibration texts must
agree with Ollama's prompt token counts. All 64 pilot requests must be archived
exactly once, use their prepared contexts, finish without truncation, and produce
valid, instruction-consistent JSON. Explicit abstention is a valid response;
no exact-match or semantic-quality threshold is used. A failed pilot stops
confirmation. Diagnose it, preserve its data, and publish an amendment/new
disjoint pilot before affected collection. Do not tune until a desired answer
score is achieved.

Model digests are checked at each execution stage. Record code/registration
hashes, dependencies, Ollama version, actual requests and response bodies,
timestamps, and basic host metadata. These records are not a hardware throughput
qualification or independent attestation of the model server internals.

## Primary and secondary measures

For every deterministic context archive passage Recall@5/10/20, annotated
sentence ranks, retrieved sentence coverage, transmitted annotated sentence
coverage, complete-context indicator, rendered context, selected/retrieved
chunks, and actual tokenizer count. Passage and sentence denominators differ.

For every generation retain the exact request and raw response body, parsed
answer/citations/abstention, official HotpotQA EM/F1, invalid citation IDs,
citation validity, and annotated citation recall. Neither valid citation IDs nor
annotation recall proves documentary support.

An execution/parse/truncation failure scores zero for lexical outcomes and is
reported separately from a model abstention. The `unanswered` composite counts
either failure or explicit abstention; it must not be described as abstention
alone. Keep failures and all planned denominators. Archive request intents before
sending. On resume, never regenerate recorded failures. An intent without an
observed response becomes a separately recorded interrupted/unknown outcome.
Stop after three consecutive failures; record any resumed execution separately.

## Prespecified statistical families

The experimental unit is the question. Never treat eight settings as eight
independent questions. Use paired differences and 10,000 bootstrap resamples
within question type, seed 20261113. Report unadjusted 95% percentile intervals
and conservative simultaneous Bonferroni intervals. For binary endpoints use a
two-sided exact McNemar test and Holm family-wise correction at .05. Report gains
and losses, not only net gains. Tests assume the question-level sampling units
are sufficiently independent; selection constraints do not prove this.

Preservation family (five primary tests on all 256 questions), endpoint complete
annotated context:

1. BM25/ranked 1536 minus BM25/ranked 512.
2. Dense/ranked 1536 minus dense/ranked 512.
3. BM25/diverse 512 minus BM25/ranked 512.
4. Dense/diverse 512 minus dense/ranked 512.
5. Dense/ranked 512 minus BM25/ranked 512.

Fractional annotated coverage for the same contrasts is secondary; do not promote
it to a primary endpoint after examining results.

Lexical/composite family (four primary tests on the frozen 128 questions): the
first two budget contrasts, for EM and `unanswered`. F1 and the remaining
selection/retrieval response contrasts are exploratory and reported as such.
Lexical rejection of a null does not establish improved factual correctness.

Human semantic family (four tests, not computable until independent annotation
is complete): the first two budget contrasts, for correctness and whole-context
support. Correctness and support have separate labels. Only an adjudicated
`correct` or `supported` label scores 1; uncertain/unverifiable labels score 0
for the conservative primary endpoint and remain a separately reported category.
Report sensitivity excluding unresolved cases, including changed denominators.
Apply Holm within this separate family. Do not compute this family from an LLM
judge or assistant provisional review.

Archive identical full-request fingerprints and per-question transitions.
Identical prompts must be identified in each contrast: generation variability
under an unchanged request cannot be credited to a selection-policy change.
Group coverage/answer relationships descriptively; no causal mediation or linear
coverage-to-truth claim is registered.

## Power, feasibility, and stopping

The paired binary normal-approximation planning scenarios are executable in
`data/power-planning.json`. With conservative alpha .01 and 80% target power,
discordance rates .1/.3/.5 give approximate detectable absolute differences of
9.6/16.5/21.4 percentage points at n=128 and 6.8/11.7/15.1 at n=256. These are
assumptions, not guarantees or results. Small answer improvements can remain
inconclusive. The study is better sized for substantial preservation changes
than small semantic gains. Do not interpret non-significance as equivalence.

Retain the requested 256/128 sizes. Historical execution logs contain about 559
seconds for 512 generations on this workstation; this only guides scheduling,
not a portable speed claim. The registered 1,120 generations and new embedding
calls fit a staged local campaign if the pinned models and instrument pass.
Do not lower sample sizes or stop on significance. Resource interruption means
incomplete collection with archived failures, not a smaller completed study.

## Separate pooled-corpus experiment

After the controlled pilot, construct the union of the 256 confirmatory
questions' public context paragraphs, deduplicated by exact title/sentence-array
hash. Preserve versions separately when a title has different text. Every
annotated paragraph must be present by construction. Index the common corpus
without per-query paragraph filtering. Use the same three-sentence chunking,
retrievers, selection rules, and budgets on all 256 questions.

This deterministic experiment is **exploratory**, not a second confirmatory
family, and has no registered generation arm. It deliberately increases
competition while ensuring relevant sources exist. It is neither full-Wikipedia
retrieval nor production retrieval. Archive corpus identity, indexed size, and
all contexts. Report it in its own directory, tables, and graphs; never pool its
numbers with the ten-paragraph results. Multiple-comparison values in its output
are descriptive exploratory calculations, not confirmatory discoveries.

## Independent annotation protocol, frozen before new answers

Two different human reviewers independently annotate randomized, pseudonymous
packets with no configuration, budget, method, model, outcome score, or gold
support-sentence flag. Reviewers must not inspect the public raw configuration
records or each other's labels. Context length and natural text can indirectly
reveal a condition; record this unavoidable blinding limitation. Mapping keys
must stay outside the public repository and outside reviewer packets.

First, show question, model answer, abstention flag, exact transmitted context,
and cited text. Record whole-context support and citation-only support separately
as `supported`, `contradicted`, `insufficient`, or `ambiguous`; for an abstention
use `not_applicable` for support and separately label it `justified`,
`unjustified`, or `uncertain`. A cautious abstention on insufficient evidence is
not automatically a model error.

After locking that phase, provide the reference answer and full original source
paragraphs in a second packet. Independently record semantic correctness as
`correct`, `incorrect`, `ambiguous`, or `unverifiable` (`not_applicable` for an
abstention), reference adequacy, aliases, contradictions, and exact source
coordinates supporting the decision. Do not assume the provided reference or
its support annotations are sufficient. Distinguish factual correctness from
what a supplied/cited text establishes. External verification, if necessary,
requires a recorded URL and date and remains distinguishable from context-only
support. An assistant review or LLM verdict is never a human label.

Start human rubric calibration on the 16 historical gold controls, without
showing the assistant's provisional classifications. Discuss rubric ambiguities
only after both independent submissions are locked. Record agreement, a nominal
confusion table, Cohen's kappa with its prevalence limitation, and every
disagreement; an independent third human arbitrates disagreements with reasons.
If no third reviewer is available, mark unresolved and do not claim completed
semantic validation. No label is filled automatically to make the study pass.

Freeze any rubric clarification prospectively before V2 annotations. Keep the
original rubric and amendment. Annotate all 1,024 primary V2 outputs for the
semantic family; allow no configuration-dependent subsampling. Keep annotation
status pending until the complete agreed/adjudicated labels exist. LLM judges
may only be explored in a separately registered, human-calibrated analysis.

## Reproduction and interpretation

See `README.md` for offline tests, staged local execution, and analysis commands.
Raw archives, failure records, and selected contexts are append-only.
Computational portability checks do not create independent model replications.
No latency, cost, production, universal retriever, or semantic-accuracy claim
follows from this controlled study without the corresponding evidence.

Sources: [HotpotQA paper](https://aclanthology.org/D18-1259/),
[official HotpotQA evaluator](https://github.com/hotpotqa/hotpot/blob/master/hotpot_evaluate_v1.py),
[exact McNemar implementation reference](https://www.statsmodels.org/stable/generated/statsmodels.stats.contingency_tables.mcnemar.html).
