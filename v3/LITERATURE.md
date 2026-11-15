# Selection and compression: scope of V3

Primary publications and official implementations were examined on 15 November
2026, before V3 outcome collection. This review motivates the registered
interventions; it does not predict their performance. The archived V2 outcomes
remain a development and diagnostic resource, not unseen prospective evidence.

## Maximal Marginal Relevance

Carbonell and Goldstein's [SIGIR 1998 paper](https://doi.org/10.1145/290941.291025)
combines query relevance with novelty relative to previously selected units.
The authors' [CMU-hosted paper](https://www.cs.cmu.edu/~jgc/publication/The_Use_MMR_Diversity_Based_LTMIR_1998.pdf)
provides the rule and discusses both documents and sentence extraction:

```text
argmax_i [lambda * relevance(i, question)
          - (1 - lambda) * max_j similarity(i, already_selected_j)]
```

The formula is implementable without training or a framework. The choice of
similarity functions, score normalization, lambda, ties and rendering still
defines a particular variant. The original work used contemporary retrieval
and cosine representations; using nomic embeddings is not a reproduction of
its SMART-based experimental system.

V3 B uses min-max normalized original retriever scores and positive cosine
redundancy between nomic passage vectors. V3 D uses min-max normalized
question/sentence cosine and positive cosine sentence redundancy. Both fix
lambda at 0.5. This is a declared setting, not a demonstrated optimum. A
non-fitting unit does not enter the accepted redundancy set. Constant relevance
maps to zero and ties use the original unit ID.

## Set selection with SetR

Lee et al., [ACL 2025](https://aclanthology.org/2025.acl-long.861/), select
passages collectively to address the information requirements of a question,
using a trained selector and reasoning instructions. The
[official repository](https://github.com/LGAI-Research/SetR/tree/d1ac78b7e41f7c6a2cd8d582934fbba02893f343)
is BSD-3-Clause licensed (`License.md`). Its documented path generates training
responses, trains a Llama 3.1 8B model, and generates selection responses.
The README's final evaluation section is still marked `TBD` at this revision.

The published dependency files include Torch 2.7.1, Transformers 4.48.3,
DeepSpeed, PEFT, bitsandbytes and FlashAttention 2.4.2, with separate local and
Docker environments. These add training, accelerator and model-provenance
requirements beyond this fixed four-policy study. V3 does not run SetR and
does not describe sentence MMR as a simplified reproduction of it.

## Learned compression with RECOMP

Xu, Shi and Choi, [ICLR 2024](https://proceedings.iclr.cc/paper_files/paper/2024/hash/bda88ed2892f5e61c9a9bf215c566913-Abstract-Conference.html),
describe two different learned compressors. The extractive branch selects
original sentences; the abstractive branch generates a summary. Both are
trained for downstream language-model utility and can return an empty text
when augmentation supplies no useful information.

The [official MIT-licensed implementation](https://github.com/carriex/recomp/tree/51d4432151efb3275257a9407dc71d1e5ec6634d)
links extractive and abstractive checkpoints for Natural Questions, TriviaQA
and HotpotQA. Its historical requirements pin Torch 1.13.0, Transformers 4.24.0
and Tokenizers 0.13.2, alongside datasets and Pyserini. The extractive script
loads models on CUDA. Reusing its checkpoint in another execution environment
would require a separately identified adapter and dependency lock. The public
[HotpotQA extractive checkpoint](https://huggingface.co/fangyuan/hotpotqa_extractive_compressor)
has no model card at review time; code licensing must not be silently treated
as a complete statement about model-weight provenance and terms.

V3 C/D retain original sentences but use no learned RECOMP compressor. They
measure finer selection granularity and a declared query-aware MMR policy.
They are not named RECOMP or presented as its replication.

## Token compression with LongLLMLingua

Jiang et al., [ACL 2024](https://aclanthology.org/2024.acl-long.91/), combine
question-aware compression, budget allocation and document reordering to
improve the information presented to a downstream model. Their
[official MIT-licensed package](https://github.com/microsoft/LLMLingua/tree/01b9e9481d7395e1e83a48df4a062b11f6304325)
depends on Torch, Transformers, Accelerate, Tiktoken, NLTK and NumPy. Its
default compressor at this revision is `NousResearch/Llama-2-7b-hf` on CUDA;
the code also exposes CPU/MPS and alternative-model paths. These choices need
their own model and execution qualification. LongLLMLingua and LLMLingua-2 are
distinct methods, not interchangeable package labels.

Token removal can preserve some meaning without preserving an annotated
sentence intact. Abstractive compression can change all of its wording.
Counting complete original-sentence retention would therefore not constitute
a sufficient or fair evaluation of those transformations. V3 keeps its main
candidate units extractive and whole-sentence preserving; a token/abstractive
compression study would need a different support evaluation and traceable
source mappings. No published cost or accuracy gain from these papers is
transferred to the Alien6 apparatus.

## Position and answer evaluation

Liu et al., [Lost in the Middle, TACL 2024](https://aclanthology.org/2024.tacl-1.9/),
show that changing relevant information's position can change model behavior
in their tested long-context tasks. Their
[official code](https://github.com/nelson-liu/lost-in-the-middle/tree/29b8a6d042ce29abccee3db1a73171a107d7e6af)
is MIT licensed. V3 does not add a position intervention. It canonically renders
parent retrieval order and source sentence order, records positions, and
acknowledges that changing content still changes positions and distractors.
A lexical answer change cannot be attributed solely to preserved annotations.

Es et al., [RAGAs, EACL 2024](https://aclanthology.org/2024.eacl-demo.16/),
distinguish context relevance, faithful use and answer quality through automatic
evaluation. The historical official repository redirects to
[vibrantlabsai/ragas](https://github.com/vibrantlabsai/ragas/tree/8c63f10d500c44efbf24fdb9e2920de2104c321c),
licensed Apache-2.0. Its current package includes substantial dataset, LLM and
framework dependencies. Automatic scores are not independent human labels for
the present study.

Saad-Falcon et al., [ARES, NAACL 2024](https://aclanthology.org/2024.naacl-long.20/),
train lightweight judges using synthetic data and correct aggregate estimates
using human-labelled examples through prediction-powered inference. The
[official Apache-2.0 implementation](https://github.com/stanford-futuredata/ARES/tree/c7c9018a755faf8347c4da415632bae1593ef104)
requires a human validation set; its README specifies at least 50 examples and
ideally several hundred. Its training/dependency stack is separate from the
deterministic replay here. Installing ARES would not resolve unavailable human
review. V3 reuses the existing two-reviewer, blinded-phase and arbitration
workflow without substituting model-generated labels.

## Controlled implementation decision

V3 compares four interventions on exactly the same saved top-ten candidates:

| Policy | Unit | Selection |
| --- | --- | --- |
| A `ranked` | Original three-sentence passage | Existing V2 ranked packing, unchanged |
| B `mmr` | Same passage | Frozen retriever-score/cosine MMR variant |
| C `sentences` | Original sentences from the same passages | Parent retrieval rank, then source position |
| D `sentence_mmr` | Same original sentences as C | Frozen query-cosine/sentence-redundancy MMR variant |

A/C examines finer granularity under inherited order. C/D examines a complete
query-aware selection policy, not the redundancy penalty alone. All policies
charge the fully rendered header, sentence IDs, separators and bodies against
the same generator tokenizer. C/D share the original parent header once when
multiple sentences from that parent are retained. Nothing is silently truncated.

Additional sentence-vector acquisition is a preparation cost and is archived.
Documentary redundancy is evaluated on original sentence vectors for every arm,
so the metric's unit does not switch from passages to sentences between policies.
Paired effects, failures, negative outcomes and identical complete prompts remain
visible. No policy consults supporting-fact flags, answer references, type labels
or generated outcomes during selection.
