"""Produce an evidence ledger, not article prose, from the archived analyses."""
import ast
from pathlib import Path
from v2.benchmark import ROOT, read, run_path


def snippet(path, name):
    text=path.read_text();tree=ast.parse(text)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    return '\n'.join(text.splitlines()[node.lineno-1:node.end_lineno])


def build():
    c=read(run_path('confirmatory','controlled')/'results.json')
    p=read(run_path('confirmatory','pooled')/'results.json')
    d=read(run_path('confirmatory','controlled')/'diagnostics.json')
    lines=['# Article evidence ledger', '',
    'This file indexes the measurements, methods and sources used to prepare the article.', '',
    '## Research question and apparatus', '',
    'Does retrieval preserve its annotated information after context packing, and what can lexical answer scores tell us about that loss? Architectural interest: the retriever and the generator are separated by a measurable, budget-constrained transformation.', '',
    'The controlled candidate set has ten supplied HotpotQA paragraphs per question. Three-sentence chunks; BM25 versus cosine nomic embeddings; ranked versus document-diverse packing; 512/1,536 rendered-context tokens. Retrieval never receives references or support flags. The 256-question preservation cohort and 128-question answer subset are fixed and balanced by question type. Eight conditions produce 1,024 primary outputs. Pilot 64 + primary 1,024 + repeats 32 = 1,120 generations; controlled 2,048 + pooled 2,048 + pilot 64 = 4,160 prepared contexts.', '',
    'Exact model digests/options, tokenizer and dataset revisions: `sources.json`, `run.py`, `v2/registration.json` and `v2/runs/confirmatory-controlled/execution-0-1794550515500955000.json` (find the exact execution filename under that directory if inspecting a restored archive).', '',
    'Hypotheses, refutations and statistical families: [PROTOCOL.md](PROTOCOL.md) and the captured [full specification](v2/PROTOCOL.md). Full results: [RESULTS.md](RESULTS.md).', '',
    '## Citable controlled results', '',
    'All rows below use `v2/runs/confirmatory-controlled/results.json`, `arms[]`. Raw inputs are `jobs.json.gz`, `answers.jsonl.gz` and `preparation.json` in that directory. Restore with `python -m v2.archive restore`. Context completeness counts all annotated sentences, not sufficient evidence; EM is official normalized lexical equality, not semantic accuracy.', '',
    '| Configuration | Complete annotated context /256 | EM /128 | Explicit abstentions /128 | Invalid /128 | Mean lexical F1 /128 |',
    '| --- | ---: | ---: | ---: | ---: | ---: |']
    for a in c['arms']:
        lines.append(f"| {a['configuration']} | {a['complete_context_count']} | {a['exact_matches']} | {a['model_abstentions']} | {a['errors']} | {a['mean_f1_all_planned']:.3f} |")
    lines += ['', '### Paired comparisons and uncertainty', '',
    'Source: the same `results.json`, `preservation_family[]` / `lexical_family[]`. The question is the paired unit. 10,000 type-stratified bootstrap draws; conservative simultaneous intervals within each family; Holm p values separately for five preservation and four lexical/composite tests. No significance inference on truth or support is available. `unanswered` includes invalid outputs and explicit abstentions.', '',
    '| Before → after | Metric | Paired denominator | Difference pp [simultaneous interval] | Holm p |',
    '| --- | --- | ---: | --- | ---: |']
    for a in c['preservation_family']+c['lexical_family']:
        low,high=a['bonferroni_family_interval']
        lines.append(f"| {a['before']} → {a['after']} | {a['metric']} | {a['questions']} questions | {100*a['mean_difference']:+.1f} [{100*low:+.1f}, {100*high:+.1f}] | {a['p_holm']:.5g} |")
    lines += ['', '### Gaps and counter-intuitive observations', '',
    'Source: `v2/runs/confirmatory-controlled/diagnostics.json`, `arms[].deterministic_flags`, `generation_flags`, and per-question records. Flags overlap; do not sum them as disjoint causes. A zero EM includes abstention and is not a factual-error judgement. Partial annotations with EM may reflect alternative sufficient text, prior knowledge or annotation incompleteness.', '',
    '| Configuration | Complete retrieval but incomplete context /256 | Complete context, zero EM /128 | Incomplete context, EM /128 |',
    '| --- | ---: | ---: | ---: |']
    for a in d['arms']:
        lines.append(f"| {a['configuration']} | {a['deterministic_flags']['complete_retrieval_but_incomplete_context']} | {a['generation_flags']['complete_context_zero_exact_match']} | {a['generation_flags']['incomplete_context_exact_match']} |")
    groups=c['identical_prompt_groups']
    lines += ['', f"Source: `results.json`, `identical_prompt_groups`: {len(groups)} identical-payload groups among 2,048 prepared requests. This is a grouping count, not an answer-agreement rate; see `RESULTS.md` for the actually generated subset. Identical requests cannot identify a selection-policy effect. Two extra passes on 16 fixed questions are only a limited stability check, not proof of generator determinism.", '',
    '## Exploratory pooled corpus', '',
    'Source: `v2/runs/confirmatory-pooled/results.json`, `arms[]`, and `preparation.json`; exact contexts: `jobs.json.gz`. Same 256 questions; no generation. The deduplicated question-derived index has 2,547 paragraph versions/4,259 chunks. Annotated sources are present by construction. Global IDs have different token overhead, so cross-environment differences are not pure corpus-size effects.', '',
    '| Configuration | Complete annotated context /256 | Mean passage Recall@10 /256 questions | Mean sentence coverage /256 questions |',
    '| --- | ---: | ---: | ---: |']
    for a in p['arms']:
        lines.append(f"| {a['configuration']} | {a['complete_context_count']} | {a['mean_passage_recall10']:.3f} | {a['mean_sentence_coverage']:.3f} |")
    lines += ['', '## Code excerpts from the actual instrument', '',
    'This payload builder is preserved by the registration source hash. It shows exactly where the rendered context enters the model request; it is not a proposed future library.', '', '```python',snippet(ROOT/'v2/benchmark.py','payload_for'),'```', '',
    'The actual whole-chunk packer counts the fully rendered candidate text. Gold coordinates never guide retrieval or packing.', '', '```python', snippet(ROOT/'run.py','pack'),'```', '',
    '`v2/core.py::context_metrics` checks the fully rendered budget and original sentence bodies; `run.py::pack` implements whole-chunk packing. `v2/checks.py` provides separate reference implementations for replay.', '',
    '## Figures and reproduction', '',
    '| Figure | Exact numerical source | Interpretation |', '| --- | --- | --- |',
    '| `v2/runs/confirmatory-controlled/evidence-and-lexical-outcomes.svg` | controlled `results.json`, `arms[]` | Keep /256 preservation and /128 answer denominators separate |',
    '| `v2/runs/confirmatory-controlled/paired-budget-effects.svg` | controlled `results.json`, paired families | Same questions; simultaneous versus ordinary intervals are explicitly labelled |',
    '| `v2/runs/confirmatory-controlled/annotation-coverage-vs-exact-match.svg` if present | controlled `diagnostics.json` | Inspect exact available filenames; no semantic labels |',
    '| `v2/runs/confirmatory-pooled/evidence-preservation.svg` | pooled `results.json`, `arms[]` | Exploratory, no answer comparison |', '',
    '```sh', 'python prepare_data.py', 'python -m v2.archive restore', 'python -m v2.verify', 'python -m v2.audit --check', 'python -m v2.analysis --environment controlled', 'python -m v2.analysis --environment pooled', 'python -m v2.diagnostics', 'python -m v2.report', 'python -m v2.article_evidence', '```', '',
    '`v2.verify` checks ranking, packing, tokenization, raw responses and numerical report replay without Ollama. The original64-question figures and diagnostics remain under `analysis/2026-11-12-rag/`; cite them only as separate exploratory evidence. `v2/verification-native.json` and `v2/verification-linux.json` document calculation replay, not independent hardware generation.', '',
    '## Human validation and editorial scope', '',
    'Prepared, not performed: two independent annotations of all 1,024 outputs, phase1 context/citation/abstention judgements before reference release, phase2 correctness/reference adequacy, locked submissions and independent third-person arbitration. `v2/ANNOTATION.md` gives the rubric and commands; `v2/semantic-status.json` supplies 0 labels and null semantic results. Lexical scores must never be relabelled human semantic accuracy.', '',
    '**Established on these cohorts:** fixed-budget context selection can discard retrieved annotated sentences; changing budget or retriever changes annotation retention; measured lexical agreement differs in the specified paired comparisons. **Exploratory:** pooled retrieval, flags associating coverage and EM, identical-prompt variability and legacy diagnostic cases. **Pending:** correctness, support, valid-citation entailment and abstention justification across the sample.', '',
    '**Allowed engineering implication:** measure and audit the retrieval-to-context boundary, retaining exact selected text, budget and source coordinates. A reusable evidence-preserving context assembler is an Alien6 engineering hypothesis. These data establish neither its efficacy nor superiority over existing packers/rerankers. A new comparison would need an equal token budget, outcome-blind selection and human-supported endpoints.', '',
    '**Do not claim:** retained annotations guarantee sufficient evidence; EM means truth; a zero EM is a hallucination; dense universally beats BM25; diversity always helps; larger budgets cause semantic faithfulness through coverage alone; production cost/latency/quality gains.', '',
    '## Primary references and attribution', '',
    '- Yang et al., HotpotQA (EMNLP 2018): https://aclanthology.org/D18-1259/ — dataset and supporting-fact task; CC BY-SA 4.0 data attribution in `THIRD_PARTY_NOTICES.md`.',
    '- Official HotpotQA evaluator, byte-pinned under `vendor/`: https://github.com/hotpotqa/hotpot/blob/master/hotpot_evaluate_v1.py — lexical normalization and scoring, not a semantic oracle.',
    '- Robertson & Zaragoza, BM25: https://doi.org/10.1561/1500000019 — retrieval formula; actual implementation/parameters are in `run.py` and independent `v2/checks.py`.',
    '- Nomic embedding model and revision: `sources.json` and archived embedding requests/vectors; do not substitute a current model under the same mutable tag.', '',
    'References define methods and context; they do not independently validate this dataset’s outcomes.']
    # Use only actual archive filenames and actual figure paths.
    execution=next((ROOT/'v2/runs/confirmatory-controlled').glob('execution-0-*.json')).name
    text='\n'.join(lines)+'\n'
    text=text.replace('execution-0-1794550515500955000.json` (find the exact execution filename under that directory if inspecting a restored archive)',execution+'`')
    text=text.replace('`run.py::pack`','`run.py::select_context`' if 'def select_context' in (ROOT/'run.py').read_text() else '`run.py::pack`')
    text='\n'.join(line for line in text.splitlines() if 'if present' not in line)+'\n'
    return text


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    expected=build();destination=ROOT/'ARTICLE_EVIDENCE.md'
    if a.check:
        if destination.read_text()!=expected:raise ValueError('Article evidence differs from archived results')
        print('Verified article evidence ledger')
    else:destination.write_text(expected)
