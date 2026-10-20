# Scope and limits

The controlled study searches ten supplied HotpotQA paragraphs per question.
The separate shared-corpus study searches their deduplicated union. Neither is
open-Wikipedia retrieval or a production benchmark. Relevant paragraphs are
present in the pooled index by construction.

The 256-question cohort is balanced by type and separated from the earlier
cohort by question identities and supporting-document titles. Its 128-question
generation subset is fixed before answer inspection. These are question-level
samples; eight configurations do not create eight independent questions.
Shared topics, distractors, annotation imperfections, and pretraining exposure
remain possible limitations.

Preserved annotated sentences and exact reference matches are distinct
measurements. An annotated set need not be sufficient or exhaustive. References
can have aliases, excessive wording, ambiguity, or contradictions. Semantic
correctness and support have not been independently adjudicated. The sixteen
gold-evidence controls are rubric-calibration material; no independent human
semantic labels or corrections are supplied.

Larger budgets change length, distractors, and ordering as well as evidence
coverage. Their answer effects cannot be assigned solely to coverage. Pooled
identifiers can also cost more tokens than controlled identifiers, so corpus
comparisons include that overhead. Identical requests are explicitly tracked;
changes under the same request are not selection-policy effects.

The paired analysis preserves losses, invalid outputs, and all planned
denominators. Multiplicity is handled within the declared statistical families.
Small response effects can remain inconclusive; non-significance is not evidence
of equivalence. The power assumptions are supplied with the cohort data.

Generation uses one local model and workstation. Native/Linux replay verifies
rankings, packing, token counts, scoring, and statistical calculations from
preserved vectors and responses. It does not repeat generation on independent
hardware. Timing records establish no latency, throughput, energy, or cost claim.


Human annotation remains pending until two complete independent submissions
and any required third-human arbitration exist.
