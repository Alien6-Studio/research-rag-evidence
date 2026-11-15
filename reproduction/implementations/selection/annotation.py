"""V3 items and final contrasts using the unchanged V2 human-review workflow."""
import argparse
from collections import Counter
import json
from pathlib import Path

from v2 import annotation as workflow
from v3.analysis import (contrasts, evidence_sha, exact_mcnemar, holm,
                         paired_interval, read_json, read_lines,
                         validate_answers, validate_jobs)
from v3.design import BASE, COHORTS, REGISTRATION, ROOT

FIELDS = workflow.FIELDS
validate_label = workflow.validate_label
release = workflow.release
submit = workflow.submit
compare = workflow.compare
arbitrate = workflow.arbitrate
adjudication_packet = workflow.adjudication_packet


def source_manifest():
    directory = BASE / 'runs/confirmatory-controlled'
    return {'cohorts_sha256': evidence_sha(COHORTS),
            'registration_sha256': evidence_sha(REGISTRATION),
            'jobs_sha256': evidence_sha(directory / 'jobs.json'),
            'answers_sha256': evidence_sha(directory / 'answers.jsonl'),
            'protocol_sha256': evidence_sha(BASE / 'PROTOCOL.md'),
            'rubric_sha256': workflow.sha(ROOT / 'v2/ANNOTATION.md'),
            'generation_budget': 512, 'expected_primary_outputs': 1024,
            'semantic_family_size': 16}


def observed_output(record):
    """Expose assistant text or an observed failure, without server metadata."""
    response = record.get('response')
    if 'response_body' in record:
        try:
            response = json.loads(record['response_body'])
        except (TypeError, ValueError):
            response = None
    message = response.get('message') if isinstance(response, dict) else None
    raw = message.get('content') if isinstance(message, dict) else None
    if raw is None and 'error' not in record:
        raise ValueError('Uninterpretable assistant output lacks a recorded failure')
    return {'raw_model_output': raw, 'recorded_output_failure': 'error' in record,
            'output_observation': ('Assistant content preserved as observed.' if raw is not None else
                                   'Request failed; no interpretable assistant content was observed.'),
            'transport_body_archived': 'response_body' in record or 'response_body_base64' in record}


def study_items():
    cohort = read_json(COHORTS)
    cases = {case['id']: case for case in cohort['confirmatory']}
    directory = BASE / 'runs/confirmatory-controlled'
    jobs = validate_jobs(read_json(directory / 'jobs.json'), cases)
    records = read_lines(directory / 'answers.jsonl')
    expected = {key for key, job in jobs.items()
                if job['question_id'] in cohort['generation_ids'] and job['budget'] == 512}
    if len(records) != 1024 or len(expected) != 1024 or {r['id'] for r in records} != expected:
        raise ValueError('Require all 1,024 frozen V3 primary records, including failures')
    validate_answers(records, jobs, cases, expected)
    items = []
    for record in records:
        key = record['id']; job = jobs[key]; case = cases[job['question_id']]
        lookup = {fact['id']: fact['text'] for chunk in job['selected'] for fact in chunk['facts']}
        if any(f'[{key}] {text}' not in job['context'] for key, text in lookup.items()):
            raise ValueError('Packet sources must be exact transmitted sentences')
        observation = observed_output(record)
        raw = observation['raw_model_output']
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            parsed = None
        citations = parsed.get('citations', []) if isinstance(parsed, dict) else []
        if not isinstance(citations, list):
            citations = []
        phase1 = {'question': case['question'], **observation,
                  'reported_answer': parsed.get('answer') if isinstance(parsed, dict) else None,
                  'reported_abstention': parsed.get('abstain') if isinstance(parsed, dict) else None,
                  'transmitted_context': job['context'],
                  'cited_sentences': [{'sentence_id': citation, 'text': lookup.get(citation)} for citation in citations]}
        phase2 = {'reference_answer': case['answer'], 'sources': [
            {'source': f'source-{i:02}', 'title': title,
             'sentences': [{'sentence': j, 'text': text} for j, text in enumerate(sentences)]}
            for i, (title, sentences) in enumerate(zip(case['context']['title'], case['context']['sentences'], strict=True))]}
        items.append({'source_key': key, 'question_id': case['id'], 'kind': case['type'],
                      'recorded_invalid_output': 'error' in record, 'phase1': phase1, 'phase2': phase2})
    return items


def prepare(destination, scope='primary'):
    if scope == 'calibration':
        return workflow.prepare(destination, 'calibration')
    if scope != 'primary':
        raise ValueError('Use primary scope so calibration protection remains active')
    items = study_items()
    metadata = source_manifest()
    result = workflow.prepare(destination, 'primary', items=items)
    destination = Path(destination).resolve()
    path = destination / 'private/v3-study.json'
    workflow.write(path, metadata)
    session_path = destination / 'session.json'
    session = read_json(session_path)
    session['prepared_files']['private/v3-study.json'] = workflow.sha(path)
    session['study'] = 'alien6-rag-v3'
    session_path.write_text(json.dumps(session, indent=2) + '\n')
    session_path.chmod(0o600)
    return {**result, 'study': 'alien6-rag-v3', 'human_annotations_supplied': 0,
            'semantic_results': None, 'primary_phase1_released': False}


def semantic_contrasts(items, resolved):
    by_id = {item['source_key']: item for item in items}
    questions = sorted({item['question_id'] for item in items})
    rows = []
    for before, after in contrasts():
        keys = [(f'{question}:{before}', f'{question}:{after}') for question in questions]
        for field, positive in [('correctness', 'correct'), ('context_support', 'supported')]:
            left = [int(resolved[a][field] == positive) for a, b in keys]
            right = [int(resolved[b][field] == positive) for a, b in keys]
            kinds = [by_id[a]['kind'] for a, b in keys]
            keep = [i for i, (a, b) in enumerate(keys)
                    if not any(resolved[key][field] in ('ambiguous', 'unverifiable') for key in (a, b))]
            details = [{'question_id': question, 'before': l, 'after': r,
                        'label_before': resolved[a][field], 'label_after': resolved[b][field]}
                       for question, (a, b), l, r in zip(questions, keys, left, right, strict=True)]
            rows.append({'before': before, 'after': after, 'metric': field,
                         'planned_questions': len(questions), **paired_interval(left, right, kinds, family=16),
                         **exact_mcnemar(left, right),
                         'unchanged': sum(a == b for a, b in zip(left, right, strict=True)),
                         'question_details': details,
                         'sensitivity_excluding_uncertain_labels': {
                             'questions': len(keep),
                             'estimate': paired_interval([left[i] for i in keep], [right[i] for i in keep],
                                                         [kinds[i] for i in keep], family=16) if keep else None}})
    for row, p in zip(rows, holm([row['p_exact'] for row in rows]), strict=True):
        row['p_holm'] = p
        row['reject_at_family_005'] = p <= .05
    return rows


def finalize(root):
    root = Path(root).resolve()
    session = workflow.session(root)
    if session['scope'] == 'calibration':
        return workflow.finalize(root)
    if session.get('study') != 'alien6-rag-v3' or read_json(root / 'private/v3-study.json') != source_manifest():
        raise ValueError('V3 source evidence or packet identity changed')
    missing = [f'{reviewer}:phase{phase}' for reviewer in session['reviewers'] for phase in (1, 2)
               if not (root / 'locks' / reviewer / f'phase{phase}.json').exists()]
    if missing:
        value = {'complete': False, 'status': 'pending independent human submissions',
                 'missing_submissions': missing, 'semantic_results': None}
        if len(missing) == 4:
            value['human_annotations_supplied'] = 0
        return value
    value, items, decisions, agreements, _ = workflow.compare(root)
    unresolved = [row for row in decisions if row['disputed_fields']]
    resolved = {row['source_key']: row['independent_labels'][0]
                for row in decisions if not row['disputed_fields']}
    if unresolved:
        if not (root / 'locks/arbitration.json').exists():
            return {'complete': False, 'status': 'pending independent third-human arbitration',
                    'unresolved': len(unresolved), 'semantic_results': None}
        metadata = read_json(root / 'locks/arbitration.json')
        labels = root / 'locks/arbitration-labels.jsonl'
        if workflow.sha(labels) != metadata['submission_sha256']:
            raise ValueError('Arbitration labels changed')
        mapping = read_json(root / 'private/adjudication-mapping.json')
        for label in read_lines(labels):
            resolved[mapping[label['item_id']]] = label
    expected = {item['source_key'] for item in study_items()}
    if len(items) != 1024 or set(resolved) != expected:
        raise ValueError('Semantic inference requires all 1,024 frozen V3 outputs')
    categories = {}
    for item in items:
        arm = item['source_key'].split(':', 1)[1]
        group = categories.setdefault(arm, {'items': 0, 'recorded_invalid_outputs': 0,
                                            'labels': {field: Counter() for fields in FIELDS.values() for field in fields}})
        group['items'] += 1
        group['recorded_invalid_outputs'] += int(item.get('recorded_invalid_output', False))
        for field in group['labels']:
            group['labels'][field][resolved[item['source_key']][field]] += 1
    result = {'complete': True, 'study': 'alien6-rag-v3', 'scope': 'primary', 'items': len(items),
              'rubric_sha256': value['rubric_sha256'], 'source_manifest': source_manifest(),
              'agreement_before_arbitration': agreements, 'disagreements_arbitrated': len(unresolved),
              'human_labels': resolved, 'descriptive_categories_by_configuration': categories,
              'semantic_family': semantic_contrasts(items, resolved), 'lexical_results_changed': False,
              'interpretation': 'Only complete agreed or independently adjudicated human labels. No LLM or lexical score supplies a missing label.'}
    workflow.write(root / 'final.json', result)
    return {key: val for key, val in result.items()
            if key not in ('human_labels', 'agreement_before_arbitration', 'semantic_family')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'release', 'submit', 'compare', 'arbitrate', 'finalize'])
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--scope', choices=['calibration', 'primary'], default='primary')
    parser.add_argument('--phase', type=int, choices=[1, 2])
    parser.add_argument('--reviewer')
    parser.add_argument('--submission', type=Path)
    parser.add_argument('--human-id')
    parser.add_argument('--independent-human', action='store_true')
    parser.add_argument('--calibration', type=Path)
    args = parser.parse_args()
    root = args.directory.resolve()
    if args.command == 'prepare':
        result = prepare(root, args.scope)
    elif args.command == 'release':
        if args.phase is None:
            parser.error('--phase is required')
        result = release(root, args.phase, args.calibration)
    elif args.command == 'submit':
        if args.phase is None or args.submission is None or not args.human_id:
            parser.error('--phase, --submission and --human-id are required')
        result = submit(root, args.reviewer, args.phase, args.submission, args.human_id, args.independent_human)
    elif args.command == 'compare':
        result = adjudication_packet(root)
    elif args.command == 'arbitrate':
        if args.submission is None or not args.human_id:
            parser.error('--submission and --human-id are required')
        result = arbitrate(root, args.submission, args.human_id, args.independent_human)
    else:
        result = finalize(root)
    print(json.dumps(result if result is not None else {'saved': True}, indent=2))
