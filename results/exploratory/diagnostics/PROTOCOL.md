# Evidence preservation in RAG

Registered before outcome collection, 12 November 2026. Publication dates of the
articles remain historical; new experiments will be dated as article updates.
No conclusion or article title is a success criterion for this experiment.

## 1. Evidence preservation in RAG

Question: when does retrieving relevant material lead to an answer supported by
that material, and where can evidence be lost?

Use the public HotpotQA development set, **distractor setting**, not full-Wikipedia
search. Each question has ten supplied paragraphs. Index only those paragraphs
for that question. This is a controlled candidate-set study, not an open-domain
retrieval leaderboard. Corpus: https://hotpotqa.github.io/ (CC BY-SA 4.0).

Select 64 questions before measuring outcomes: 32 bridge and 32 comparison
questions, using Python Random(20261112) on IDs sorted within each type. Record
the selected IDs and full dataset SHA-256. No replacement based on model success.
Malformed annotations are recorded and invalidate a case rather than being
silently dropped.

Primary configuration:

- Non-overlapping chunks of three original sentences, with title and original
  sentence IDs preserved. Supporting-fact annotations are used only for scoring.
- Retrieval: BM25 (k1=1.5, b=0.75) and cosine similarity of
  nomic-embed-text embeddings. Use search_document/search_query prefixes.
- Retrieve ten chunks. Compare descending-score packing with document-diverse
  packing (one chunk per title per round, in retrieval order). Both see exactly
  the same top-ten candidates for their retrieval arm and never see annotations.
- Context budgets: 512 and 1536 Qwen tokens, including titles, chunk identifiers
  and separators. Skip chunks that do not fit; never silently truncate a chunk.
- Generator: local Ollama qwen3.6:latest, digest
  07d35212591fc27746f0a317c975a6d68754fb38e9053d82e25f06057af28522,
  Q4_K_M; temperature 0, seed 20261112, thinking disabled, num_ctx 8192,
  num_predict 256. Record Ollama version, prompt, schema, raw response and timings.
- Tokenizer: official Qwen/Qwen3.6-35B-A3B tokenizer; record revision and hash.
  Validate token counts against raw Ollama prompt evaluation before the run.
- Embedding model digest:
  0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f.

This gives 512 answer-generation configurations (64 x 2 x 2 x 2). Keep retrieval,
packing and generation outputs for every configuration, including failures.
Requests are sequential so concurrency does not confound quality comparisons.
Resume only already recorded configuration IDs; do not regenerate failed answers
until they pass. A full repeat is identified separately from the primary run.

Measures, computed per question before aggregation:

1. Passage Recall@10: annotated-relevant chunks found / all annotated-relevant
   chunks under the fixed segmentation. Annotation units are distinct from facts.
2. Evidence coverage: annotated original supporting sentences retained in the
   **actual rendered context** / all supporting sentences. Also report complete
   coverage and the frequency of perfect retrieval with incomplete context.
3. Answer exact match and token F1, using HotpotQA's official normalisation and
   yes/no rules. Parse failures and unsupported abstentions count as failures.
4. Citation validity, supporting-fact precision/recall, and answer abstentions.
   Citation validity alone is not semantic faithfulness.
5. A separately labelled faithfulness proxy: a frozen, different local model
   (dolphin3, digest d5ab9ae8e1f22619a6be52e5694df422b7183a3883990a000188c363781ecb78)
   judges whether the answer follows from the cited text, without gold answers,
   retrieval scores or configuration labels. Return supported/unsupported/uncertain.
   Check the judge on 16 positive gold-evidence controls and 16 swapped-evidence
   controls selected in advance. Report these controls and uncertainty; do not
   describe an LLM judge as human review or ground truth.

Sensitivity: retrieval-only top-k = 5, 10, 20 and sentence chunks = 2, 3, 6.
Generation comparisons use only the primary segmentation to isolate selection.
Before collection, add two diagnostic controls on the first 16 question IDs:
generation with only annotated evidence, and a separately prompted answer from
prior knowledge without supplied evidence. The latter diagnoses possible memory
of a public dataset; it is not a competing retrieval policy or a causal RAG gain.
Repeat the first 16 question IDs in two additional passes for output stability.
Report paired differences and 95% bootstrap intervals by resampling questions
within question type (seed 20261112, 2000 draws). Do not treat 512 configurations
as 512 independent questions. Report all arms, including worse results.

## Publication rule

Keep this article URL: `/fr/research/articles/audit-architecture-rag/`. Write a pedagogical account only after valid runs
exist: the initial question, the investigation, the observations, what they mean
and what remains uncertain. Change a title if the evidence does not support it.
Code and measured data go through the shared GitHub repository, not a ZIP or a
public customer-deliverable page. No client data or proprietary implementation
is used. New evidence changes the article; it does not justify cherry-picking runs.
