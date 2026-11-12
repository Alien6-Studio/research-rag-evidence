# What this experiment establishes

## Deterministic evidence-loss observation

The primary result follows from fixed public texts, annotated sentence coordinates,
retrieved candidates, tokenizer, and packing rules. `analysis.py` recomputes the
selected context and official scores for all 512 settings before aggregation.
The portability validator also recomputes all 128 retrieval rankings from the
preserved embedding vectors. It never calls a model.

`evidence/portability-native.json` and `evidence/portability-linux-container.json`
record the macOS and constrained Linux-container audits. Their canonical
per-question metric digests are identical. The Linux audit uses patched pyarrow
and ujson versions; the original measured environment remains archived separately.

This controls a platform or dependency explanation for the observed **packing
and scoring calculation**. It is not a second independent physical host, a new
embedding campaign, a repeated generation campaign, or a speed benchmark.
Both environments ultimately share the same workstation.

## Generation and evaluation limits

- One local quantized generator and one embedding model were measured. Model
  digests, requests, context limits, raw outputs, parsing errors, and timings are
  retained. The main 512 generations have no parse errors.
- Two complete extra passes on the same 16 questions agree with the primary
  normalized answer in 126 of 128 correlated settings per pass. Temperature zero
  is not proof of perfectly deterministic generation.
- Lexical exact matching rejects the observed Fiat alias despite the paragraph
  identifying both company names. No sample-wide human semantic adjudication was
  performed. A zero lexical score is not proof that a response is factually false.
- The automated faithfulness judge rejects four of sixteen positive controls.
  It is an imperfect proxy and cannot establish strong semantic faithfulness.
- Prior model exposure to the public dataset is unknown. The prior-knowledge and
  gold-evidence controls are diagnostics, not a causal estimate of RAG benefit.
- Host/GPU interference was not continuously measured in the original quality
  campaign. Do not infer throughput, comparative latency, energy, or cost from its
  timing fields. They are raw execution records, not a qualified capacity study.

## Sampling and conclusions

There are 64 questions balanced across two types, not 512 independent questions.
Intervals resample questions within type. The sample is small, English, public,
and restricted to ten supplied paragraphs per question. Annotation completeness
and answer-reference wording are possible measurement limitations.

The supported conclusion is that the specified packing step loses annotated
evidence on some cases even when retrieval found it. Answer-score changes are
conditional observations with uncertainty. Universal retriever rankings, semantic
correctness improvements, production benefits, hardware-independent performance,
and financial savings are not established.

Original publication dates and actual research dates are separate; see
[CHRONOLOGY.md](CHRONOLOGY.md). Later controls do not become earlier evidence.
