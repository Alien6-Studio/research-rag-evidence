# Third-party material

Original code and project documentation are licensed under Apache-2.0.

- HotpotQA, Yang, Qi, Zhang et al., EMNLP 2018: <https://hotpotqa.github.io/>.
  Dataset questions, paragraphs, annotations, and their extracts in `runs/`
  retain the dataset's **CC BY-SA 4.0** terms. Segmentation, context selection,
  and scoring create derived records; they do not replace the source license.
- The official HotpotQA evaluator is preserved in `vendor/hotpot_evaluate_v1.py`,
  under Apache-2.0; its original license is in `vendor/LICENSE.txt`.
- Dataset and Qwen tokenizer references, immutable revisions, and hashes are in
  `sources.json`. Downloaded files and model weights are not bundled.
- Ollama model names and full digests are recorded in the protocol and manifests.
  Each model and tokenizer retains its own upstream license.

A repository license badge refers to the original project code and documentation,
not to a relicensing of datasets, model weights, or third-party software.
