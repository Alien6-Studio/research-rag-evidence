# V3 interpretation and validity boundaries

This is a reading guide to the registered selection study, not a change to its
methods. Read the original [protocol](PROTOCOL.md), prospective
[amendment 01](AMENDMENT-01.md), [method review](LITERATURE.md) and the
[active cohort](data/cohorts-amendment-01.json). A completed deterministic
preparation is distinct from a completed generation collection, and both are
distinct from independent semantic validation. Results require the complete
archive and a successful `python -m v3.verify --require-collected` replay.

## What the interventions identify

For each question and retriever, all four policies receive the same saved top-ten
passages of up to three sentences. The documentary budget includes the exact rendered
titles, parent headers, original sentence IDs, separators and sentence bodies.
No method silently truncates a passage or omits reference overhead to gain space.
The primary budget is 512 tokens. The 1,536-token comparisons concern deterministic
preservation only; no V3 generation is planned at that budget.

A (`ranked`) retains V2 whole-passage packing. B (`mmr`) changes selection at that same
granularity. C (`sentences`) changes the selectable unit while following the inherited
ranking. D (`sentence_mmr`) adds question/sentence cosine relevance and redundancy
control to those original-sentence candidates. The sentence comparison therefore
tests a complete query-aware policy; it does not isolate the redundancy penalty
or relevance scorer alone.

The MMR variants fix lambda at 0.5, score normalization, positive-cosine redundancy,
tie rules and handling of units that do not fit. These settings are not optimized
on the new outcomes and are not claimed to be optimal. They are declared variants,
not reproductions of SMART's original experiment, RECOMP, LongLLMLingua or SetR.
No trained compressor or abstractive summarizer is evaluated. Intact-sentence
retention would not by itself fairly score methods that preserve meaning while
removing tokens or rewriting sentences.

Canonical rendering preserves parent retrieval order and original sentence order
after selection. Changed content still changes relative positions, distractors
and the amount of text. A response change cannot be causally attributed solely
to the extra annotated sentences. There is no independent position intervention.

## Population, separation and annotation access

The controlled cohort contains 256 English HotpotQA questions, balanced by type;
the fixed generation subset contains 128, also balanced. These are questions,
not 4,096 independent samples or 1,024 independent questions. Four policies and
two retrievers produce repeated observations of the same cases.

V1's 64 exploratory cases and V2's eight pilot plus 256 confirmatory cases are
excluded by ID, normalized question and supporting-document title. Sampling also
separates support titles within the newly selected cases. Amendment 01 replaces
the complete original V3 pilot with eight new questions, excluding both original
V3 splits under the same rules. Its 256 confirmation cases and 128 generation
IDs are preserved exactly; they are not replaced after inspecting the pilot.

Supporting-fact flags enter eligibility/separation and evaluation, never the
selection-policy interface. Selectors receive the public question, text,
coordinates, ranking and vectors. Document titles are public retrieval and
rendering inputs, not secret relevance flags. They may themselves contain useful
information, so the conclusions concern this title-bearing representation.
Tests check that references, annotations and outcome fields cannot affect
selection. Eligibility based on annotated support titles nevertheless makes the
sample a conditional, sequential sample rather than a simple random sample of
all HotpotQA questions. Common topics, distractor documents and public-dataset
pretraining exposure remain possible.

Each controlled question searches its ten supplied paragraphs. This helps
separate ranking from packing, but it is an assisted candidate set. It is not
retrieval over all Wikipedia or an enterprise document collection. Supporting
sentences are evaluation landmarks, not a complete enumeration of every valid
way to answer a question. Losing an annotation does not prove that all sufficient
evidence was lost; retaining every annotation does not prove that the answer
will be correct or supported.

## Preregistration, failed pilot and amendment

The original registration was published at commit
`90fecf74f2cbfeaf52618688681c366430604042`; PR 15 was created on
15 November 2026 at 16:53:18 UTC, before original collection. The first pilot
retains 128 prepared contexts and 64 responses. Its qualification remains
**failed**, with the recorded error `preparation-start.scope`.

The error was a metadata-checker defect: the execution scope and final corpus
scope intentionally describe different stages. The amended checker validates
each string separately and retains equality checks for the shared metadata.
A corrected diagnostic replay does not retroactively qualify the original
pilot, replace its certificate or count its outputs as replacement-pilot trials.

The amendment was registered at 17:10:51 UTC and published through the
[protected protocol release](https://github.com/Alien6-Studio/research-rag-evidence/releases/tag/protocol-rag-v3-2026-11-15-a1)
at 17:14:23 UTC on 15 November 2026. The replacement pilot started after that
publication. The receipt retains the older PR time as context; verification uses
the release's actual publication timestamp for amendment outcomes. A local Git
commit or a later retrospective statement alone is not public preregistration.

The [prior-evidence inventory](amendments/01/prior-evidence.json) preserves the
original cohort, registration, publication receipt, failed qualification and
observations by hash. Only the specified label-free embedding packets may be
inherited as cached inputs. Their original registration and timestamps remain
visible. Every new packet must carry the amendment identity and follow its
publication time. No old generated answer supplies a new answer.

## Qualification and statistical interpretation

The replacement pilot is a technical gate: all 128 contexts, 64 responses and
three tokenizer probes must replay with correct sources, requests, budgets,
format, completion and metadata. No Exact Match, semantic-quality or effect-size
threshold qualifies it. Complete confirmation remains required even if the
observed effects are negative, mixed or small. Recorded errors stay in the
planned denominator; missing observations cannot be converted into a smaller
completed experiment or silently regenerated.

At 512 tokens, the registered contrasts are B-A, C-A, D-C and D-A for each
retriever. Complete annotated context on 256 paired questions forms a family
of eight exact two-sided McNemar tests with Holm correction. EM and unanswered
outcomes on the same 128 generation questions form one family of sixteen.
Unanswered includes explicit abstention and invalid/failed output; those counts
are also retained separately. Failures score zero in the planned EM/F1 denominator.

Intervals use 10,000 paired bootstrap draws stratified by question type, with
ordinary 95% intervals and conservative simultaneous Bonferroni intervals for
the declared family. This preserves pairing and type balance; it does not make
the selected questions representative of a customer workload or remove possible
topic dependence. Gains, losses and unchanged cases matter alongside averages.
Non-significance is not equivalence. The [power scenarios](data/power-planning.json)
are pre-collection approximations under assumed discordance, not observed power.

Fractional coverage, F1, 1,536-token comparisons and undeclared contrasts are
secondary descriptions. The pooled corpus is a separate exploratory environment,
not another confirmatory replication. Its index is derived from the new cohort's
public paragraphs, with relevant sources present by construction; global IDs
have different token overhead. Do not reuse V2's pooled corpus counts for V3,
pool the two environments, or interpret their difference as corpus size alone.

## Answer quality, costs and reproducibility

The generator, embedding model, tokenizer, prompts, schema and options are fixed.
This is one quantized Qwen model and task environment. Temperature zero and a
fixed seed do not prove deterministic generation. Identical complete requests
are fingerprinted; changed answers under identical requests are generation
variation, not evidence of a selection-policy effect.

EM and F1 measure normalized lexical agreement. Valid citation IDs establish
that a referenced identifier exists, not that its sentence supports the answer.
Semantic correctness, exact-context support, citation support and justified
abstention require the existing two-reviewer, reference-blinded workflow and
independent arbitration. The [machine-readable semantic status](semantic-status.json)
must remain pending until actual complete human decisions exist. Blank packets,
assistant judgements and lexical scores do not supply missing human labels.

Embedding acquisition, shared retrieval, warm selection and generation timings
are recorded separately. Sentence-vector preparation is an additional cost;
shared cached work is not charged once per arm. The inherited pilot packets
remain separately identifiable. Runtime observations depend on this workstation,
cache state and concurrent activity. They do not measure production capacity,
energy, a financial saving or a generally free optimization.

The historical preservation inventory, frozen source registration, public
receipt and lossless compressed/decoded hashes serve different purposes. Offline
replay checks them, reconstructs contexts from preserved vectors and coordinates,
reparses raw responses and recomputes analyses without a model call. It checks
the recorded computation; it neither repeats physical generation on independent
hardware nor independently validates the dataset's semantic labels. Earlier
observations and scores remain unchanged throughout this extension.
