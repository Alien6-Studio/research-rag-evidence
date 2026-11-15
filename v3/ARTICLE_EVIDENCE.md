# Article evidence ledger: V2 and the separate V3 extension

This derived ledger maps editorial claims to preserved observations. It does not change the frozen protocol or supply human semantic labels. Read [validity](VALIDITY.md), [the replay configuration](REPLAY.md) and [results](RESULTS.md).

## Historical V2

- Main evidence: [controlled results](../v2/runs/confirmatory-controlled/RESULTS.md), [exact archived analysis](../v2/runs/confirmatory-controlled/results.json.gz).
- Ranked BM25 retains all annotated sentences for 148/256 questions at 512 tokens and 228/256 at 1,536; ranked dense retrieval gives 220/256 and 249/256.
- The same BM25 retrieval contains all annotations for 228/256 questions; at 512 tokens 80 of these do not retain them all in the transmitted context.
- BM25 official EM is 60/128 at 512 and 80/128 at 1,536. These are lexical scores on the fixed generation subset, not semantic correctness.
- V2 has one invalid primary output, retained in the planned denominator. Human semantic annotation remains pending.
- The [Fiat illustration](../analysis/2026-11-12-rag/illustrative-case.json) belongs to exploratory V1, not V2/V3. Under BM25 ranked, 512 tokens retains 2/3 annotations and abstains; 1,536 retains 3/3 and returns Fiat S.p.A. Both score EM=0 against Fabbrica Italiana Automobili Torino. Dense 512 also answers Fiat with 2/3: do not claim that the third sentence was necessary.

## New V3 controlled observations

256 new balanced questions; 128 fixed balanced generation questions. Same retrieved top ten per question/retriever, four policies, the same documentary-token ceiling. Generation is measured only at 512. A/B/C/D refer to ranked chunks, chunk MMR, inherited-order original sentences, and query-aware sentence MMR.

| Retriever | Policy | Complete annotations /256 | EM /128 | Explicit abstentions /128 | Invalid /128 |
| --- | --- | ---: | ---: | ---: | ---: |
| bm25 | ranked | 136 | 62 | 26 | 1 |
| bm25 | mmr | 126 | 62 | 25 | 2 |
| bm25 | sentences | 146 | 62 | 26 | 1 |
| bm25 | sentence_mmr | 203 | 71 | 15 | 1 |
| dense | ranked | 226 | 75 | 13 | 0 |
| dense | mmr | 222 | 74 | 13 | 0 |
| dense | sentences | 226 | 75 | 12 | 0 |
| dense | sentence_mmr | 215 | 72 | 12 | 0 |

- Only BM25 D-A and D-C reject in the eight-test preservation family. BM25 D-A is +67/256 (+26.171875 percentage points), with 79 gains and 12 losses; its simultaneous interval is [17.578125; 35.450439] points and Holm p=2.391922432013805e-12.
- BM25 C-A is +10/256; chunk MMR B-A is -10/256. Neither is an established gain under the declared correction.
- Dense D-A is -11/256, without rejection after Holm. Do not infer equivalence or confirmed harm.
- No contrast rejects in the sixteen-test EM/unanswered family. BM25 D-A EM is +9/128, with 11 gains and 2 losses, simultaneous interval [-0.78125; +15.625] points and Holm p=0.314453125.
- All 1,024 response bodies were observed. Five outputs violate instructions (abstain=true with a nonempty answer), are preserved and score zero in planned EM/F1 denominators. There are six invalid citation IDs. Valid IDs are not evidence of support.
- At 1,536 tokens all four policies have the same complete-context indicator per question: 223/256 BM25 and 252/256 dense. This is deterministic sensitivity, with no generation at that budget.
- The [pooled results](runs/confirmatory-pooled/RESULTS.md) are exploratory and separate: 2,557 paragraph versions, 4,270 chunks, no generation. At 512, BM25 A/B/C/D=115/106/118/167 and dense=213/211/211/197, each /256.
- A fixed 512-token ceiling is not an identical transmitted length: controlled BM25 means are 479.4 tokens A, 498.9 C and 502.3 D. Headers, titles, IDs and separators are charged.
- Controlled sentence-vector preparation acquired 7,341 new inputs, with 519 cached; API wall time 40.90 seconds is shared preparation, not a financial/production measure or a cost charged per arm.
- 189 groups among observed main generations contain strictly identical requests (431 records); no assistant-message or lexical-score variation was observed within them. This is not a proof of universal deterministic generation.

## Model and provenance

The [main execution metadata](runs/confirmatory-controlled/execution-1794763739192774000.json.gz) records generator tag qwen3.6:latest, SHA256 digest 07d35212591fc27746f0a317c975a6d68754fb38e9053d82e25f06057af28522, registry parameter_size=36.0B and quantization_level=Q4_K_M. The embedding tag is nomic-embed-text:latest with its pinned digest. Avoid treating a tag alone as model identity.

- V3 linked compressed analysis SHA256: `088194e03984b2c1690878fefb8769644802a2e10d4de6dfae263e6b1c743dc6`.
- Active cohort SHA256: `2adb7f010e3bee6df7786ee585ef37f13c14f0fcc9ebf0823761e7e08a2e1a9d`.
- Active registration SHA256: `0b868b6460492e8f0784b94ea9a69dc389cf0f96a7aedd2414267b92bac896db`.

The original failed pilot remains excluded and preserved. The replacement pilot qualified under the publicly timestamped amendment. The numerical replay seed was selected after context collection on ranking hashes only and is not claimed as the original seed. No source, context, answer, annotation or score was rewritten.

## Semantic boundary

Human annotations=0; adjudications=0; semantic results=null for V3. The two-reviewer primary packets cover all 1,024 outputs, including failures, and remain private/unreleased pending real calibration. Calibration material has 16 controls. The public [semantic status](semantic-status.json) records preparation only.

Annotated sentences are landmarks, not an exhaustive set of sufficient evidence. Retention, official EM/F1, factual correctness and whole-context/citation support are separate outcomes. Selection D changes content, positions and distractors together; there is no causal mediation test that isolates extra annotations as the reason for a response change.
