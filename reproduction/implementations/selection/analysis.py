"""Paired V3 preservation and lexical analysis; no model calls or human labels."""
import argparse
import base64
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from v2.benchmark import payload_for
from v2.core import answer_metrics, digest, exact_mcnemar, holm
from v2.verify import checked_answer
from v3.design import BASE, COHORTS, ROOT

SEED = 20261115
METHODS = ('bm25', 'dense')
POLICIES = ('ranked', 'mmr', 'sentences', 'sentence_mmr')
BUDGETS = (512, 1536)
POLICY_CONTRASTS = (('ranked', 'mmr'), ('ranked', 'sentences'),
                    ('sentences', 'sentence_mmr'), ('ranked', 'sentence_mmr'))


def evidence_bytes(path):
    path = Path(path)
    if not path.exists():
        path = path.with_name(path.name + '.gz')
    data = path.read_bytes()
    return gzip.decompress(data) if path.suffix == '.gz' else data


def evidence_sha(path):
    return hashlib.sha256(evidence_bytes(path)).hexdigest()


def read_json(path):
    return json.loads(evidence_bytes(path))


def read_lines(path):
    path = Path(path)
    if not path.exists() and not path.with_name(path.name + '.gz').exists():
        return []
    return [json.loads(line) for line in evidence_bytes(path).splitlines() if line.strip()]


def contrasts(budget=512):
    return [(f'{method}:{left}:{budget}', f'{method}:{right}:{budget}')
            for method in METHODS for left, right in POLICY_CONTRASTS]


def paired_interval(before, after, kinds, draws=10000, family=1):
    if not before or family < 1 or len(before) != len(after) or len(before) != len(kinds):
        raise ValueError('Require nonempty equally sized paired observations')
    if set(kinds) - {'bridge', 'comparison'}:
        raise ValueError('Unexpected question type')
    delta = np.asarray(after, dtype=float) - np.asarray(before, dtype=float)
    if not np.all(np.isfinite(delta)):
        raise ValueError('Non-finite paired observation')
    rng = np.random.default_rng(SEED)
    groups = [np.flatnonzero(np.asarray(kinds) == kind) for kind in ('bridge', 'comparison')]
    samples = np.concatenate([rng.choice(group, (draws, len(group)), replace=True)
                              for group in groups if len(group)], axis=1)
    means = delta[samples].mean(axis=1)
    alpha = .05 / family
    return {'mean_difference': float(delta.mean()),
            'ci95': list(map(float, np.quantile(means, [.025, .975]))),
            'bonferroni_family_interval': list(map(float, np.quantile(means, [alpha / 2, 1 - alpha / 2]))),
            'draws': draws, 'seed': SEED, 'unit': 'question, within type', 'family_size': family}


def paired(jobs, ids, before, after, metric, family, answers=None, infer=True):
    left, right, details, kinds = [], [], [], []
    for question in ids:
        a, b = jobs[f'{question}:{before}'], jobs[f'{question}:{after}']
        if a['type'] != b['type']:
            raise ValueError('Paired question types differ')
        kinds.append(a['type'])
        def value(job):
            if answers is None:
                return job[metric]
            record = answers[job['id']]
            if metric == 'unanswered':
                return int('error' in record or record['answer']['abstain'])
            return 0 if 'error' in record else record['metrics'][metric]
        l, r = value(a), value(b)
        left.append(l); right.append(r)
        details.append({'question_id': question, 'before': l, 'after': r,
                        'coverage_before': a['evidence_coverage'], 'coverage_after': b['evidence_coverage'],
                        'tokens_before': a['context_tokens'], 'tokens_after': b['context_tokens'],
                        'identical_request': payload_for(a) == payload_for(b)})
    row = {'before': before, 'after': after, 'metric': metric, 'questions': len(ids),
           **paired_interval(left, right, kinds, family=family),
           'favorable_direction': 'decrease' if metric == 'unanswered' else 'increase',
           'gains': sum(r > l for l, r in zip(left, right, strict=True)),
           'losses': sum(r < l for l, r in zip(left, right, strict=True)),
           'unchanged': sum(r == l for l, r in zip(left, right, strict=True)),
           'question_details': details,
           'identical_requests': sum(d['identical_request'] for d in details),
           'changed_results_under_identical_requests': [d['question_id'] for d in details
                                                       if d['identical_request'] and d['before'] != d['after']]}
    binary = all(v in (0, 1) for v in left + right)
    if binary:
        row['binary_transitions'] = {f'{a}_to_{b}': sum(l == a and r == b for l, r in zip(left, right, strict=True))
                                     for a in (0, 1) for b in (0, 1)}
        if infer:
            row.update(exact_mcnemar(left, right))
    return row


def adjust(rows):
    for row, p in zip(rows, holm([r['p_exact'] for r in rows]), strict=True):
        row['p_holm'] = p
        row['reject_at_family_005'] = p <= .05


def validate_jobs(job_list, cases):
    jobs = {job['id']: job for job in job_list}
    expected = {f'{question}:{method}:{policy}:{budget}' for question in cases
                for method in METHODS for policy in POLICIES for budget in BUDGETS}
    if len(jobs) != len(job_list) or set(jobs) != expected:
        raise ValueError('Incomplete, unexpected or duplicate deterministic conditions')
    for key, job in jobs.items():
        expected_id = f"{job['question_id']}:{job['retriever']}:{job['policy']}:{job['budget']}"
        if key != expected_id or job['type'] != cases[job['question_id']]['type']:
            raise ValueError('Job identity or question type differs')
        if not 0 <= job['evidence_coverage'] <= 1 or job['complete_context'] not in (0, 1):
            raise ValueError('Invalid preservation metric')
        if not 0 <= job['context_tokens'] <= job['budget']:
            raise ValueError('Context exceeds its documentary budget')
    return jobs


def recorded_transport_failure(record):
    """Reproduce a preserved HTTP or body-decoding failure without a model call."""
    status = record.get('http_status')
    error = record.get('error', '')
    if (not isinstance(status, int) or isinstance(status, bool) or not 100 <= status <= 599
            or not isinstance(error, str) or not error.startswith('RecordedRequestError: ')):
        raise ValueError('Recorded transport failure lacks its HTTP status or original error')
    if 'answer' in record or 'metrics' in record:
        raise ValueError('Failed transport carries successful scores')
    if 'response_body_base64' in record:
        if 'response_body' in record:
            raise ValueError('Transport body has two incompatible encodings')
        raw = base64.b64decode(record['response_body_base64'], validate=True)
        try:
            raw.decode('utf-8')
        except UnicodeDecodeError:
            pass
        else:
            raise ValueError('Base64 transport body was not a UTF-8 decoding failure')
    elif isinstance(record.get('response_body'), str):
        raw = record['response_body'].encode('utf-8')
    else:
        raise ValueError('Recorded transport failure lacks the original body')
    if status >= 400:
        if error != f'RecordedRequestError: HTTP {status}':
            raise ValueError('Recorded HTTP failure differs from its status')
        return
    if error != 'RecordedRequestError: Invalid JSON response':
        raise ValueError('Recorded body-decoding failure has a different cause')
    try:
        json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return
    raise ValueError('A recorded JSON-decoding failure contains valid JSON')


def validate_answers(records, jobs, cases, expected):
    answers = {record['id']: record for record in records}
    if len(answers) != len(records) or not set(answers) <= expected:
        raise ValueError('Unexpected or duplicate generation IDs')
    for key, record in answers.items():
        payload = payload_for(jobs[key])
        if record.get('request') is not None and record['request'] != payload:
            raise ValueError('Archived request differs from the prepared context')
        if record.get('request_sha256') is not None and record['request_sha256'] != digest(payload):
            raise ValueError('Request fingerprint differs')
        if ('http_status' in record or 'response_body_base64' in record
                or str(record.get('error', '')).startswith('RecordedRequestError: ')):
            recorded_transport_failure(record)
            continue
        if 'response_body' not in record:
            if not record.get('error') or 'metrics' in record or 'answer' in record:
                raise ValueError('Unobserved response requires a recorded failure without successful scores')
            continue
        response = json.loads(record['response_body'])
        if record.get('response') is not None and response != record['response']:
            raise ValueError('Raw and parsed response bodies differ')
        try:
            parsed = checked_answer(response)
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            if record.get('error') != f'{type(error).__name__}: {error}':
                raise ValueError('Recorded output failure is not reproduced from its raw response') from error
            if 'metrics' in record or 'answer' in record:
                raise ValueError('Failed output carries successful scores')
            continue
        if 'error' in record:
            raise ValueError('A recorded output failure has no reproduced violation')
        if record.get('request') != payload:
            raise ValueError('A successful generation requires its exact request')
        if parsed != record['answer'] or answer_metrics(cases[jobs[key]['question_id']], jobs[key], parsed) != record['metrics']:
            raise ValueError('Stored generated answer or lexical score differs')
    return answers


def arm_summaries(job_list, answers, planned, complete):
    arms = []
    for method in METHODS:
        for policy in POLICIES:
            for budget in BUDGETS:
                suffix = f'{method}:{policy}:{budget}'
                group = [j for j in job_list if j['id'].endswith(':' + suffix)]
                observed = [answers[j['id']] for j in group if j['id'] in answers]
                usable = [a for a in observed if 'error' not in a]
                planned_count = len(planned) if budget == 512 else 0
                row = {'configuration': suffix, 'retriever': method, 'policy': policy, 'budget': budget,
                       'deterministic_questions': len(group),
                       'complete_context_count': sum(j['complete_context'] for j in group),
                       'mean_sentence_coverage': float(np.mean([j['evidence_coverage'] for j in group])),
                       'mean_passage_recall10': float(np.mean([j['recall10'] for j in group])),
                       'mean_context_tokens': float(np.mean([j['context_tokens'] for j in group])),
                       'retrieval_incomplete_count': sum(j['retrieved_sentence_coverage'] < 1 for j in group),
                       'packing_discards_retrieved_count': sum(j['evidence_coverage'] < j['retrieved_sentence_coverage'] for j in group),
                       'complete_retrieval_incomplete_context_count': sum(j['retrieved_sentence_coverage'] == 1 and not j['complete_context'] for j in group),
                       'mean_distinct_sources': float(np.mean([len({f['document'] for c in j['selected'] for f in c['facts']}) for j in group])),
                       'generation_planned': planned_count, 'generation_observed': len(observed),
                       'lexical_collection_complete': complete and bool(planned_count),
                       'errors': len(observed) - len(usable),
                       'exact_matches': sum(a['metrics']['answer_em'] for a in usable),
                       'model_abstentions': sum(a['metrics']['abstain'] for a in usable),
                       'unanswered': len(observed) - len(usable) + sum(a['metrics']['abstain'] for a in usable),
                       'mean_f1_all_planned': sum(a['metrics']['answer_f1'] for a in usable) / planned_count if complete and planned_count else None,
                       'invalid_citation_ids': sum(a['metrics']['invalid_citations'] for a in usable),
                       'mean_citation_validity_observed_usable': float(np.mean([a['metrics']['citation_validity'] for a in usable])) if usable else None}
                for name in ('warm_selection_seconds', 'selection_wall_seconds', 'selection_seconds', 'positive_cosine_redundancy'):
                    values = [j[name] for j in group if isinstance(j.get(name), (int, float))]
                    if values:
                        row['mean_' + name] = float(np.mean(values))
                redundancies = [j['redundancy']['mean_positive_cosine'] for j in group
                                if isinstance(j.get('redundancy'), dict)]
                row['mean_positive_cosine_redundancy'] = float(np.mean(redundancies)) if redundancies else None
                timings = [a['wall_seconds'] for a in observed if isinstance(a.get('wall_seconds'), (int, float))]
                row['generation_wall_seconds_sum_observed'] = float(sum(timings)) if timings else None
                api = []
                for observation in observed:
                    response = observation.get('response')
                    if not isinstance(response, dict) and observation.get('response_body'):
                        try:
                            response = json.loads(observation['response_body'])
                        except (ValueError, TypeError):
                            continue
                    if isinstance(response, dict):
                        api.append(response)
                row['generation_api_reported_sums'] = {
                    name: {'observations': sum(isinstance(a.get(name), (int, float)) for a in api),
                           'sum': sum(a[name] for a in api if isinstance(a.get(name), (int, float)))}
                    for name in ('load_duration', 'prompt_eval_duration', 'eval_duration',
                                 'prompt_eval_count', 'eval_count')}
                arms.append(row)
    return arms


def analyse(environment, write=True):
    if environment not in ('controlled', 'pooled'):
        raise ValueError('Unknown environment')
    out = BASE / 'runs' / f'confirmatory-{environment}'
    preparation = read_json(out / 'preparation.json')
    if evidence_sha(out / 'jobs.json') != preparation['jobs_sha256']:
        raise ValueError('Prepared inputs changed')
    cohort = read_json(COHORTS)
    cases = {case['id']: case for case in cohort['confirmatory']}
    if len(cases) != 256 or Counter(c['type'] for c in cases.values()) != {'bridge': 128, 'comparison': 128}:
        raise ValueError('Require the complete balanced 256-question cohort')
    job_list = read_json(out / 'jobs.json')
    jobs = validate_jobs(job_list, cases)
    ids = sorted(cases)
    planned = sorted(cohort['generation_ids']) if environment == 'controlled' else []
    if environment == 'controlled' and (len(planned) != 128 or not set(planned) <= cases.keys()
                                       or Counter(cases[q]['type'] for q in planned) != {'bridge': 64, 'comparison': 64}):
        raise ValueError('Require the fixed balanced 128-question generation subset')
    expected = {job['id'] for job in job_list if job['question_id'] in planned and job['budget'] == 512}
    answers = validate_answers(read_lines(out / 'answers.jsonl'), jobs, cases, expected)
    complete = bool(expected) and set(answers) == expected
    preservation = [paired(jobs, ids, a, b, 'complete_context', 8) for a, b in contrasts()]
    adjust(preservation)
    lexical = [paired(jobs, planned, a, b, metric, 16, answers)
               for a, b in contrasts() for metric in ('answer_em', 'unanswered')] if complete else []
    if lexical:
        adjust(lexical)
    secondary = [paired(jobs, ids, a, b, 'evidence_coverage', 1, infer=False)
                 for budget in BUDGETS for a, b in contrasts(budget)]
    secondary += [paired(jobs, ids, a, b, 'complete_context', 1, infer=False) for a, b in contrasts(1536)]
    response_secondary = [paired(jobs, planned, a, b, 'answer_f1', 1, answers, infer=False)
                          for a, b in contrasts()] if complete else []
    groups = defaultdict(list)
    for job in job_list:
        groups[digest(payload_for(job))].append(job['id'])
    result = {'schema': 'alien6-rag-v3-analysis-v1', 'environment': environment,
              'analysis_role': 'prespecified controlled families' if environment == 'controlled' else 'separate exploratory pooled sensitivity',
              'confirmatory_inference': environment == 'controlled',
              'status': ('complete lexical collection; independent human annotation pending' if complete else
                         'complete deterministic collection; generation incomplete' if planned else
                         'complete deterministic exploratory collection; no generation planned'),
              'questions': len(cases), 'generation_questions': len(planned),
              'jobs_sha256': preparation['jobs_sha256'],
              'registration_sha256': preparation.get('registration_sha256'),
              'generation_sha256': evidence_sha(out / 'answers.jsonl') if answers else None,
              'generation_collection_complete': complete,
              'arms': arm_summaries(job_list, answers, planned, complete),
              'preservation_family': preservation, 'lexical_family': lexical,
              'secondary_preservation_descriptive': secondary,
              'secondary_response_descriptive': response_secondary,
              'identical_prompt_groups': [group for group in groups.values() if len(group) > 1],
              'preparation_metadata': preparation,
              'cost_scope': 'Embedding and shared retrieval preparation are charged once in preparation_metadata; warm selection is per arm. API-reported durations are nanoseconds and counts are tokens. Timings are local descriptive evidence.',
              'semantic_validation': {'status': 'pending independent human annotation and arbitration',
                                      'human_annotations_supplied': 0, 'semantic_results': None},
              'inference_limits': ['Annotated sentence retention is not sufficient or exhaustive evidence.',
                                   'Lexical agreement and citation ID validity are not correctness or support.',
                                   'Identical-request answer changes are generation variability.',
                                   'Question is the paired unit; configurations do not multiply sample size.',
                                   'Pooled results are exploratory and are never combined with controlled results.',
                                   'Local preparation/generation timings are not production or financial costs.']}
    if environment == 'pooled':
        for row in preservation:
            row.pop('reject_at_family_005', None)
        result['pooled_statistical_scope'] = 'Intervals and p values are exploratory descriptions, not confirmation.'
    if write:
        (out / 'results.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
        report(result, out)
        figure(result, out)
    return result


def report(result, out):
    rows = ['# RAG selection V3 results', '', result['analysis_role'] + '.', '', result['status'] + '.', '',
            '| Configuration | Complete annotated context /256 | Mean sentence coverage | Mean documentary tokens | EM / planned answers | Explicit abstentions | Invalid/failed |',
            '| --- | ---: | ---: | ---: | --- | ---: | ---: |']
    for arm in result['arms']:
        lexical = (f"{arm['exact_matches']} / {arm['generation_planned']}" if arm['lexical_collection_complete'] else
                   f"incomplete ({arm['generation_observed']}/{arm['generation_planned']} observed)" if arm['generation_planned'] else
                   'not measured')
        rows.append(f"| {arm['configuration']} | {arm['complete_context_count']} | {arm['mean_sentence_coverage']:.3f} | {arm['mean_context_tokens']:.1f} | {lexical} | {arm['model_abstentions']} | {arm['errors']} |")
    rows += ['', '## Fixed 512-token paired contrasts', '',
             'Question-level, type-stratified bootstrap: 10,000 draws. Simultaneous intervals use the declared family sizes; Holm correction is separate for preservation (8) and lexical/unanswered (16).', '',
             '| Family | Before → after | Outcome | 0→1 / 1→0 / unchanged | Difference [simultaneous interval] | Holm p |',
             '| --- | --- | --- | --- | --- | ---: |']
    for name, family in [('preservation', result['preservation_family']), ('lexical', result['lexical_family'])]:
        for row in family:
            lo, hi = row['bonferroni_family_interval']
            rows.append(f"| {name} | {row['before']} → {row['after']} | {row['metric']} | {row['gains']} / {row['losses']} / {row['unchanged']} | {row['mean_difference']:+.4f} [{lo:+.4f}, {hi:+.4f}] | {row['p_holm']:.5g} |")
    rows += ['', 'The unanswered composite includes explicit abstentions and invalid/failed outputs; an increase is adverse. Missing responses keep lexical inference unavailable; failures are retained in the planned denominator.', '',
             'Pooled calculations, partial coverage, F1 and 1,536-token contrasts are secondary/exploratory. No lexical or annotation-coverage measure supplies a human semantic judgement.', '',
             'Exact requests, contexts, costs, coordinates and question-level transitions are retained in the archived inputs and results.json. Timings are local descriptive measurements.', '',
             '## Limits', '', *['- ' + value for value in result['inference_limits']]]
    (out / 'RESULTS.md').write_text('\n'.join(rows) + '\n')


def figure(result, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.8), layout='constrained', sharey=True)
    for ax, method in zip(axes, METHODS, strict=True):
        rows = [a for a in result['arms'] if a['retriever'] == method and a['budget'] == 512]
        bars = ax.bar(range(4), [a['complete_context_count'] for a in rows], color=['#173b59', '#087f5b', '#ad4826', '#6a4c93'])
        ax.bar_label(bars, labels=[f"{a['complete_context_count']}/256" for a in rows], padding=3)
        ax.set_xticks(range(4), ['Ranked', 'Chunk MMR', 'Sentences', 'Sentence MMR'], rotation=18, ha='right')
        ax.set_ylim(0, 280); ax.set_title(method.upper()); ax.spines[['top', 'right']].set_visible(False)
    axes[0].set_ylabel('Questions retaining all annotated sentences')
    fig.suptitle(f"V3 {result['environment']}: identical candidates, 512 documentary tokens")
    for extension in ('svg', 'png'):
        fig.savefig(out / f'assembly-comparison.{extension}', dpi=160)
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--environment', choices=['controlled', 'pooled'], required=True)
    args = parser.parse_args()
    value = analyse(args.environment)
    print(json.dumps({'environment': value['environment'], 'status': value['status'],
                      'questions': value['questions'], 'primary_answers': sum(a['generation_observed'] for a in value['arms'])}, indent=2))
