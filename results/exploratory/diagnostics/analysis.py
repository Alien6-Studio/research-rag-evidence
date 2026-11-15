"""Audit the frozen raw records and compute question-level descriptive results."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
from tokenizers import Tokenizer

from run import (ROOT, SEED, OPTIONS, MODELS, ANSWER_SCHEMA, SYSTEM, chunks_for,
                 pack, render_context, retrieval_metrics, parse_answer, score)
from vendor.hotpot_evaluate_v1 import normalize_answer

RUN = ROOT / 'runs/2026-11-12-rag'
OUT = ROOT / 'analysis/2026-11-12-rag'
METRICS = ['recall10', 'evidence_coverage', 'complete_context',
           'perfect_retrieval_incomplete_context', 'answer_em', 'answer_f1',
           'abstain', 'citation_validity', 'sp_prec', 'sp_recall', 'sp_f1']


def records(name):
    return [json.loads(line) for line in (RUN / name).read_text().splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unique(items):
    result = {item['id']: item for item in items}
    assert len(result) == len(items), 'Duplicate record IDs'
    return result


def audit():
    manifest = json.loads((RUN / 'manifest.json').read_text())
    assert manifest['executable_sha256'] == sha(ROOT / 'run.py'), 'Executed source differs'
    sources = json.loads((ROOT / 'sources.json').read_text())
    assert sources['dataset']['sha256'] == sha(ROOT / 'data/hotpot-validation.parquet')
    assert sources['tokenizer']['sha256'] == sha(ROOT / 'data/qwen-tokenizer.json')
    cases = unique(json.loads((RUN / 'cases.json').read_text()))
    jobs = unique(json.loads((RUN / 'jobs.json').read_text()))
    answers = unique(records('answers.jsonl'))
    assert len(cases) == 64 and len(jobs) == 512 and jobs.keys() == answers.keys()
    assert Counter(c['type'] for c in cases.values()) == {'bridge': 32, 'comparison': 32}
    tokenizer = Tokenizer.from_file(str(ROOT / 'data/qwen-tokenizer.json'))
    fixed_candidates = {}
    rows = []
    for key, job in jobs.items():
        case = cases[job['question_id']]
        assert job['question'] == case['question'] and job['type'] == case['type']
        chunks = chunks_for(case)
        candidates = job['retrieved']
        assert len(candidates) <= 10
        assert len({c['id'] for c in candidates}) == len(candidates)
        assert all(c['score'] >= d['score'] for c, d in zip(candidates, candidates[1:]))
        by_id = {c['id']: c for c in chunks}
        for candidate in candidates:
            assert {k: v for k, v in candidate.items() if k != 'score'} == by_id[candidate['id']]
        selection = pack(candidates, job['budget'], job['policy'], tokenizer)
        assert selection == job['selected']
        assert render_context(selection) == job['context']
        assert len(tokenizer.encode(job['context']).ids) == job['context_tokens'] <= job['budget']
        index = (job['question_id'], job['retriever'])
        assert fixed_candidates.setdefault(index, candidates) == candidates
        retrieval = retrieval_metrics(case, chunks, candidates, selection)
        assert all(retrieval[k] == job[k] for k in retrieval)
        answer = answers[key]
        if 'error' in answer:
            measured = {k: 0 for k in METRICS if k not in retrieval}
            measured['abstain'] = 1
        else:
            raw = answer['raw']
            assert parse_answer(raw) == answer['answer']
            expected_prompt = f"Question: {case['question']}\n\nEvidence:\n{job['context']}"
            request = raw['request']
            assert request['messages'] == [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': expected_prompt}]
            assert request['options'] == OPTIONS and request['model'] == MODELS['generator'][0]
            assert request['format'] == ANSWER_SCHEMA and request['think'] is False
            measured = score(case, job, answer['answer'])
            assert measured == answer['metrics'], f'Stored score differs: {key}'
        rows.append({k: job[k] for k in ['id', 'question_id', 'type', 'retriever', 'policy', 'budget']} |
                    retrieval | {k: measured[k] for k in METRICS if k not in retrieval})
    expected_per_question = Counter(row['question_id'] for row in rows)
    assert set(expected_per_question.values()) == {8}
    return cases, jobs, answers, rows


def bootstrap_indices(cases):
    ids = sorted(cases)
    rng = np.random.default_rng(SEED)
    groups = [[i for i, key in enumerate(ids) if cases[key]['type'] == kind] for kind in ['bridge', 'comparison']]
    samples = np.concatenate([rng.choice(group, (2000, len(group)), replace=True) for group in groups], axis=1)
    return ids, samples


def mean_interval(values, samples):
    values = np.asarray(values, dtype=float)
    means = values[samples].mean(axis=1)
    return {'mean': float(values.mean()), 'ci95': [float(x) for x in np.quantile(means, [.025, .975])]}


def analyse():
    OUT.mkdir(parents=True, exist_ok=True)
    cases, jobs, answers, rows = audit()
    ids, samples = bootstrap_indices(cases)
    arms = []
    indexed = {}
    for retriever in ['bm25', 'dense']:
        for policy in ['ranked', 'diverse']:
            for budget in [512, 1536]:
                group = {r['question_id']: r for r in rows if (r['retriever'], r['policy'], r['budget']) == (retriever, policy, budget)}
                assert sorted(group) == ids
                indexed[(retriever, policy, budget)] = group
                metrics = {m: mean_interval([group[key][m] for key in ids], samples) for m in METRICS}
                per_type = {kind: {m: float(np.mean([r[m] for r in group.values() if r['type'] == kind])) for m in METRICS} for kind in ['bridge', 'comparison']}
                arms.append({'retriever': retriever, 'policy': policy, 'budget': budget, 'n_questions': 64, 'metrics': metrics, 'by_question_type': per_type})
    differences = []
    for key, group in indexed.items():
        baseline = indexed[(key[0], 'ranked', 512)]
        if key == (key[0], 'ranked', 512):
            continue
        differences.append({'retriever': key[0], 'policy': key[1], 'budget': key[2], 'baseline': 'ranked:512',
                            'metrics': {m: mean_interval([group[i][m] - baseline[i][m] for i in ids], samples) for m in METRICS}})
    contrasts = []
    for policy in ['ranked', 'diverse']:
        for budget in [512, 1536]:
            left, right = indexed[('bm25', policy, budget)], indexed[('dense', policy, budget)]
            contrasts.append({'contrast': 'dense minus bm25', 'policy': policy, 'budget': budget,
                              'metrics': {m: mean_interval([right[i][m] - left[i][m] for i in ids], samples) for m in METRICS}})
    judge = records('judge.jsonl')
    assert len(unique(judge)) == len(judge)
    expected_judged = {key for key, a in answers.items() if 'error' not in a and not a['answer']['abstain']}
    assert {j['id'] for j in judge if j['kind'] == 'prediction'} == expected_judged
    for item in judge:
        if 'error' not in item:
            assert json.loads(item['raw']['response']['message']['content']) == item['judgement']
    judge_counts = {kind: dict(Counter(j.get('judgement', {}).get('verdict', 'error') for j in judge if j['kind'] == kind)) for kind in ['prediction', 'positive', 'swapped']}
    assert sum(judge_counts['positive'].values()) == sum(judge_counts['swapped'].values()) == 16
    controls = records('generator-controls.jsonl')
    assert len(unique(controls)) == 32
    control_summary = {}
    for kind in ['gold_evidence', 'prior_knowledge']:
        group = [c for c in controls if c['kind'] == kind]
        assert len(group) == 16
        control_summary[kind] = {'n_questions': len(group), 'exact_answers': sum(c.get('answer_em', 0) for c in group), 'mean_f1': float(np.mean([c.get('answer_f1', 0) for c in group])), 'errors': sum('error' in c for c in group)}
    stability = []
    for repeat in [1, 2]:
        repeated = unique(records(f'answers-repeat-{repeat}.jsonl'))
        assert len(repeated) == 128 and {jobs[k]['question_id'] for k in repeated} == set(ids[:16])
        normalized, citations, exact = [], [], []
        for key, item in repeated.items():
            if 'error' in item:
                normalized.append(False); citations.append(False); exact.append(0)
                continue
            assert parse_answer(item['raw']) == item['answer']
            assert score(cases[jobs[key]['question_id']], jobs[key], item['answer']) == item['metrics']
            base = answers[key]['answer']; current = item['answer']
            normalized.append((current['abstain'], normalize_answer(current['answer'])) == (base['abstain'], normalize_answer(base['answer'])))
            citations.append(sorted(set(current['citations'])) == sorted(set(base['citations'])))
            exact.append(item['metrics']['answer_em'])
        stability.append({'repeat': repeat, 'n_questions': 16, 'n_correlated_settings': 128, 'normalized_answer_agreement_count': sum(normalized), 'citation_set_agreement_count': sum(citations), 'exact_answers': sum(exact), 'errors': sum('error' in r for r in repeated.values())})
    # Explicit selection rule prevents choosing a convenient invented illustration.
    candidates = sorted(r['id'] for r in rows if r['retriever'] == 'bm25' and r['policy'] == 'ranked' and r['budget'] == 512 and r['recall10'] == 1 and r['complete_context'] == 0 and r['answer_em'] == 0)
    case_id = jobs[candidates[0]]['question_id'] if candidates else None
    example = None
    if case_id:
        case = cases[case_id]
        example = {'selection_rule': 'First sorted question ID in BM25/ranked/512 with Recall@10=1, incomplete transmitted supporting evidence, and a zero exact-reference-match score (including abstentions).', 'case': case,
                   'configurations': [{'job': j, 'answer_record': answers[j['id']]} for j in jobs.values() if j['question_id'] == case_id]}
    sensitivity = json.loads((RUN / 'retrieval-sensitivity.json').read_text())
    sensitivity_summary = []
    for method in ['bm25', 'dense']:
        for size in [2, 3, 6]:
            for k in [5, 10, 20]:
                group = {s['question_id']: s for s in sensitivity if (s['retriever'], s['chunk_sentences'], s['top_k']) == (method, size, k)}
                assert sorted(group) == ids
                sensitivity_summary.append({'retriever': method, 'chunk_sentences': size, 'top_k': k, 'passage_recall': mean_interval([group[i]['passage_recall'] for i in ids], samples)})
    results = {'analysis_utc': datetime.now(timezone.utc).isoformat(), 'analysis_sha256': sha(Path(__file__)), 'run_executable_sha256': sha(ROOT / 'run.py'), 'questions': 64, 'sampling': '32 bridge and 32 comparison, balanced exploratory sample', 'primary_generations': 512, 'primary_errors': sum('error' in a for a in answers.values()),
               'bootstrap': {'unit': 'question, resampled within type', 'draws': 2000, 'seed': SEED, 'interval': 'percentile 95%, exploratory and not multiplicity-adjusted'}, 'arms': arms, 'paired_differences': differences, 'retriever_contrasts': contrasts, 'judge': judge_counts, 'generator_controls': control_summary, 'repeat_stability': stability, 'retrieval_sensitivity': sensitivity_summary, 'example_question_id': case_id}
    (OUT / 'results.json').write_text(json.dumps(results, indent=2)+'\n')
    (OUT / 'audited-question-metrics.json').write_text(json.dumps(rows, indent=2)+'\n')
    if example: (OUT / 'illustrative-case.json').write_text(json.dumps(example, indent=2, ensure_ascii=False)+'\n')
    report(results)
    figures(results)
    print(json.dumps({'audited_questions':64,'audited_primary_generations':512,'output':str(OUT),'judge':judge_counts,'example_question_id':case_id},indent=2))


def report(results):
    lines=['# Evidence preservation in RAG: observed results', '',
           'Collection and analysis: 12 November 2026. This exploratory, balanced sample contains 64 questions (32 bridge, 32 comparison), not 512 independent questions. Each question supplies ten distractor-setting paragraphs; this is not full-Wikipedia search.', '',
           '## Main observation', '',
           'The same retrieved candidate set can retain different amounts of supporting evidence after context packing. More complete transmitted evidence does not by itself guarantee an exact reference match. Exact matching is a lexical test, not a complete semantic-correctness judgement. The following counts come from the audited raw requests and responses; they are not constructed examples.', '',
           '| Retriever | Packing | Context tokens (maximum) | Mean passage Recall@10 | All supporting sentences retained | Exact reference matches | Abstentions |',
           '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for arm in results['arms']:
        m=arm['metrics']
        lines.append(f"| {arm['retriever']} | {arm['policy']} | {arm['budget']} | {m['recall10']['mean']:.1%} | {round(m['complete_context']['mean']*64)}/64 | {round(m['answer_em']['mean']*64)}/64 | {round(m['abstain']['mean']*64)}/64 |")
    lines+=['','Recall averages a passage-level fraction per question. Evidence completeness and exact-answer counts use a question-level denominator; these measures must not be read as the same quantity.', '',
            '## Paired changes from ranked packing at 512 tokens', '',
            'Intervals resample questions within question type (2,000 draws, seed 20261112). These are exploratory percentile intervals, without multiplicity adjustment. A small sample and correlated configurations limit generalization.', '',
            '| Retriever | Alternative | Evidence-completeness change (percentage points, 95% interval) | Exact-reference-match change (percentage points, 95% interval) |',
            '| --- | --- | ---: | ---: |']
    for item in results['paired_differences']:
        def fmt(metric):
            d=item['metrics'][metric];lo,hi=d['ci95']
            return f"{100*d['mean']:+.1f} [{100*lo:+.1f}, {100*hi:+.1f}]"
        lines.append(f"| {item['retriever']} | {item['policy']}, {item['budget']} tokens | {fmt('complete_context')} | {fmt('answer_em')} |")
    lines+=['','## What the controls do and do not establish','',
            f"The automated judge labels {results['judge']['positive'].get('supported',0)}/16 gold-evidence controls as supported and {results['judge']['swapped'].get('unsupported',0)}/16 swapped-evidence controls as unsupported. Four positive controls are rejected: its verdicts are therefore an imperfect proxy and do not support a strong semantic-faithfulness claim. All individual verdicts, reasons, requests, and responses remain public.",'',
            'The positive and swapped controls are constructed calibration conditions, not independent human labels for the predictions. A structurally valid citation is not proof that an answer follows from that text.', '',
            f"On the 16 diagnostic questions, gold-only evidence yields {results['generator_controls']['gold_evidence']['exact_answers']}/16 exact answers; the separately prompted prior-knowledge condition yields {results['generator_controls']['prior_knowledge']['exact_answers']}/16. These diagnostic conditions do not estimate a causal RAG benefit. Exact-match normalization can also reject semantically acceptable wording; no human answer-equivalence adjudication was performed.", '',
            'Two complete extra passes cover the same first 16 question IDs and eight configurations. Stability figures are in `results.json`; the 128 settings per pass are correlated and are not 128 independent questions.', '',
            '## An observed scoring limitation','',
            'The rule-selected Fiat example exposes a lexical false negative. The model answers `Fiat S.p.A.`, while the reference expects `Fabbrica Italiana Automobili Torino`. The supplied paragraph itself says `Fiat S.p.A., or \"Fabbrica Italiana Automobili Torino\"`. The official exact matcher rejects the short name even though this source identifies the names as aliases. No human semantic adjudication was performed across the sample, and this observation is not used to silently change the registered scores. A zero exact-match score must not be called proof of a factually wrong answer.', '',
            '## Audit and limitations','',
            'The executable analysis rechecks the pinned dataset and tokenizer hashes, source hash, raw answer parsing, exact transmitted prompts, context budgets and selection, official scoring, unique IDs, complete primary arms, and calibration-control counts. It preserves the executed generator source unchanged. Run `python analysis.py` after obtaining the pinned public inputs and installing the recorded dependencies.', '',
            'The sample is small, balanced rather than population-weighted, public, English, and restricted to supplied paragraphs. Prior model exposure to HotpotQA is unknown. The study uses one local quantized generator and one embedding model. It does not establish production performance, customer impact, cost savings, a universal retriever ranking, or semantic faithfulness. Generation timing fields are not a full-pipeline latency benchmark.', '',
            f"The illustration is chosen by a documented rule, not invented: `{results['example_question_id']}`. Its full input and all eight configurations are in `illustrative-case.json`. The selection deliberately illustrates a failure mechanism and is not a prevalence estimate.", '',
            'HotpotQA extracts retain attribution to Yang, Qi, Zhang et al. (EMNLP 2018) and CC BY-SA 4.0. See `THIRD_PARTY_NOTICES.md`.']
    (ROOT/'RESULTS.md').write_text('\n'.join(lines)+'\n')


def figures(results):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    ranked=[a for a in results['arms'] if a['policy']=='ranked']
    for lang in ['en']:
        fig,ax=plt.subplots(figsize=(7.6,4.9),layout='constrained')
        x=np.arange(len(ranked));width=.34
        labels=[f"{a['retriever'].upper()}\n{a['budget']} tokens" for a in ranked]
        for shift,metric,color,label in [(-width/2,'complete_context','#0c8c65','All evidence retained'),(width/2,'answer_em','#17283a','Exact reference match')]:
            values=[a['metrics'][metric]['mean']*100 for a in ranked]
            bars=ax.bar(x+shift,values,width,color=color,label=label)
            ax.bar_label(bars,labels=[f'{round(v*.64)}/64' for v in values],padding=4,fontsize=11)
        ax.set_xticks(x,labels,fontsize=11);ax.set_ylim(0,108)
        ax.set_yticks([0,25,50,75,100],[f'{v} %' for v in [0,25,50,75,100]])
        ax.set_ylabel('Questions (%)',fontsize=12)
        ax.set_title('Transmitted evidence and exact reference matches',fontsize=14,pad=16)
        ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.16);ax.set_axisbelow(True)
        ax.legend(loc='upper left',bbox_to_anchor=(0,-.17),frameon=False,ncols=2,fontsize=11)
        fig.text(.5,-.025,'64 balanced HotpotQA questions · ranked packing · local Qwen · 12 Nov 2026',ha='center',fontsize=9,color='#374151')
        for extension in ['png','svg']:
            path = OUT/f'evidence-and-answers-{lang}.{extension}'
            fig.savefig(path,dpi=180,bbox_inches='tight',facecolor='white')
            if extension == 'svg':
                path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
        plt.close(fig)


if __name__=='__main__':
    analyse()
