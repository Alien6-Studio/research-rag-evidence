# Methods

This is the functional reading guide to two registered studies. Their exact
protocols, instruments, registrations, observations and original identifiers are
preserved as captured evidence. This guide does not amend those specifications.

## Populations and controlled retrieval

Both studies use English [HotpotQA](https://hotpotqa.github.io/) questions,
balanced between bridge and comparison types. Each controlled cohort has
256 questions, and each fixed generation subset has 128, balanced 64 per type.
The budget and selection cohorts are separated by question identity, normalized
question text and supporting-document titles. They are not pooled for inference.

Each controlled question searches its ten supplied paragraphs. Non-overlapping
passages contain up to three original sentences. BM25 and nomic cosine retrieval
rank them, and the top ten are retained. Supporting-fact flags affect cohort
eligibility/separation and evaluation, never the selection-policy interface.
Selectors receive the public question, text, coordinates, ranking and vectors.

The same digest-pinned local Qwen generator, tokenizer, prompts and fixed
generation options identify the apparatus. Model identities and options are in
the captured registrations and execution records listed in [EVIDENCE.md](EVIDENCE.md).
No weights or inference endpoint are needed to replay those observations.

## Budget diagnostic

The diagnostic compares two retrievers, ranked or document-diverse passage
packing, and documentary caps of 512 or 1,536 tokens. Document-diverse packing
alternates documents; it is distinct from the MMR policies in the selection study.
There are eight conditions per question and 1,024 primary generated outputs on
the fixed 128-question subset. The disjoint technical pilot has eight questions;
limited identical-request repeats are a separate stability diagnostic.

Whole passages that do not fit are skipped before later passages are tried.
The two budgets share the same retrieval rankings. The registered preservation
family contains five comparisons; the lexical/unanswered family contains four.
The pooled-corpus setting and other diagnostic contrasts are exploratory.

## Selection comparison

The comparison fixes the same saved top-ten candidates for every policy within
a question/retriever. Two retrievers, four policies and two documentary ceilings
produce 4,096 contexts per environment. The primary ceiling is 512 tokens.
Only that ceiling has generation: eight conditions on 128 questions, or
1,024 planned outputs. The 1,536-token sensitivity is deterministic only.

| Policy | Selectable unit | Rule |
| --- | --- | --- |
| A | Original passage | Ranked whole-passage packing |
| B | The same passages | Original retriever relevance and positive-cosine redundancy penalty |
| C | Original sentences from those passages | Parent retrieval rank, then source sentence position |
| D | The same sentences | Question/sentence cosine relevance and positive-cosine redundancy penalty |

The two MMR variants normalize relevance within their candidates and fix the
relevance/redundancy weights at 0.5/0.5. Ties use original IDs; units that do not
fit are skipped without entering the accepted redundancy set. These settings
are fixed, not optimized on the new outcomes.

Selected text is rendered in parent retrieval order and original sentence order,
with the original parent header charged once. Every proposed addition is counted
after rendering titles, headers, sentence IDs, separators and bodies. Nothing
is silently truncated. The documentary cap is not a full-request token limit,
and equal ceilings do not imply identical transmitted lengths.

The initial eight-question pilot retained its failed technical qualification.
A documented amendment introduced a distinct replacement pilot without changing
confirmation membership or policy/statistical rules. The replacement qualified
on completion, format, source, budget and metadata checks, with no answer-quality
threshold. Pilots are not confirmation observations.

## Outcomes and paired inference

Complete annotated context means that all annotated source sentences are
transmitted. Coverage is fractional sentence retention. Official EM/F1 measure
normalized lexical agreement. Citation-ID validity checks identifier existence.
Correctness, whole-context support, citation support and justified abstention
remain separate human outcomes.

Question is the paired unit. The selection preservation family has eight
two-sided exact McNemar tests with Holm correction. Its EM/unanswered family
has sixteen, corrected separately. Unanswered includes valid explicit abstention
and invalid/failed outputs. Failures remain in planned denominators, with zero
EM/F1. Intervals use 10,000 paired bootstrap draws within question type;
simultaneous intervals use conservative Bonferroni adjustment for the full family.

Independent review uses two reference-blinded phases, locked submissions and
independent arbitration. The rubric is captured in the
[human-review specification](provenance/documents/budget/ANNOTATION.md).
Prepared private packets are not supplied human labels.

## Relationship to published methods

[Carbonell and Goldstein's MMR](https://www.cs.cmu.edu/~jgc/publication/The_Use_MMR_Diversity_Based_LTMIR_1998.pdf)
combines query relevance and novelty. [SetR](https://aclanthology.org/2025.acl-long.861/)
addresses collective passage selection; [RECOMP](https://proceedings.iclr.cc/paper_files/paper/2024/hash/bda88ed2892f5e61c9a9bf215c566913-Abstract-Conference.html)
learns extractive or abstractive compression; [LongLLMLingua](https://aclanthology.org/2024.acl-long.91/)
compresses prompts with question awareness. Those systems were not reproduced
or benchmarked here. Original-sentence retention alone would not fairly measure
transformations that preserve meaning while rewriting or removing tokens.

[Lost in the Middle](https://aclanthology.org/2024.tacl-1.9/) motivates care about
position, which this apparatus does not independently manipulate.
[RAGAs](https://aclanthology.org/2024.eacl-demo.16/) separates evaluation dimensions;
[ARES](https://aclanthology.org/2024.naacl-long.20/) uses human examples to correct
estimates. Neither framework supplies missing human decisions for these studies.
The [captured source review](provenance/documents/selection/LITERATURE.md) records
the primary papers, official implementations, licenses and feasibility assessment.
