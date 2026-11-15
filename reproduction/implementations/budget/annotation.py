"""Blinded human annotation, locked phases and independent arbitration; no model calls."""
import argparse
from collections import Counter
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import secrets
from urllib.parse import urlsplit

from v2.benchmark import COHORTS, lines, read, run_path
from v2.core import exact_mcnemar, holm, paired_interval

ROOT = Path(__file__).resolve().parents[1]
SUPPORT = ('supported', 'contradicted', 'insufficient', 'ambiguous', 'not_applicable')
FIELDS = {
    1: {'context_support': SUPPORT, 'citation_support': SUPPORT,
        'citation_validity': ('valid_ids', 'invalid_ids', 'no_citations', 'not_applicable'),
        'abstention_justification': ('justified', 'unjustified', 'uncertain', 'not_applicable')},
    2: {'correctness': ('correct', 'incorrect', 'ambiguous', 'unverifiable', 'not_applicable'),
        'reference_adequacy': ('adequate', 'incomplete', 'ambiguous', 'contradictory', 'unverifiable')},
}


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(value): return ' '.join(value.strip().casefold().split())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    path.chmod(0o600)


def write_lines(path, values):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open('x', encoding='utf-8') as handle:
        for value in values: handle.write(json.dumps(value, ensure_ascii=False) + '\n')
    path.chmod(0o600)


def study_items(scope):
    """References and source keys stay in coordinator storage, never phase one."""
    if scope == 'primary':
        cohorts = read(COHORTS)
        cases = {c['id']: c for c in cohorts['confirmatory']}
        jobs = {j['id']: j for j in read(run_path('confirmatory', 'controlled') / 'jobs.json')}
        records = lines(run_path('confirmatory', 'controlled') / 'answers.jsonl')
        expected = {key for key, job in jobs.items() if job['question_id'] in cohorts['generation_ids']}
        if len(records) != 1024 or len(expected) != 1024 or {r['id'] for r in records} != expected:
            raise ValueError('Require all 1,024 primary records, including the invalid output')
        entries = [(r['id'], cases[jobs[r['id']]['question_id']], jobs[r['id']]['context'],
                    r.get('response', {}).get('message', {}).get('content'), 'error' in r,
                    {f['id']:f['text'] for chunk in jobs[r['id']]['selected'] for f in chunk['facts']}) for r in records]
    else:
        cases = read(ROOT / 'runs/2026-11-12-rag/cases.json')[:16]
        controls = {r['id']: r for r in lines(ROOT / 'runs/2026-11-12-rag/generator-controls.jsonl')}
        entries = []
        for case in cases:
            key = case['id'] + ':gold_evidence'
            raw = controls[key]['raw']
            context = raw['request']['messages'][1]['content'].split('\n\nEvidence:\n', 1)[1]
            from run import chunks_for
            visible = set(re.findall(r'^\[(d\d+s\d+)\] ',context,re.M))
            lookup = {f['id']:f['text'] for chunk in chunks_for(case) for f in chunk['facts'] if f['id'] in visible}
            entries.append((key, case, context, raw['response']['message']['content'], False, lookup))
    result = []
    for key, case, context, raw, invalid, lookup in entries:
        try: parsed = json.loads(raw)
        except (TypeError, ValueError): parsed = None
        if any(f'[{key}] {text}' not in context for key,text in lookup.items()):
            raise ValueError('Cited source bodies must remain exact transmitted text')
        citations = parsed.get('citations', []) if isinstance(parsed, dict) else []
        if not isinstance(citations, list): citations = []
        packet = {'question': case['question'], 'raw_model_output': raw,
                  'reported_answer': parsed.get('answer') if isinstance(parsed, dict) else None,
                  'reported_abstention': parsed.get('abstain') if isinstance(parsed, dict) else None,
                  'transmitted_context': context,
                  'cited_sentences': [{'sentence_id': value, 'text': lookup.get(value)} for value in citations]}
        references = {'reference_answer': case['answer'], 'sources': [
            {'source': f'source-{i:02}', 'title': title,
             'sentences': [{'sentence': j, 'text': text} for j, text in enumerate(sentences)]}
            for i, (title, sentences) in enumerate(zip(case['context']['title'], case['context']['sentences'], strict=True))]}
        result.append({'source_key': key, 'question_id': case['id'], 'kind': case['type'], 'recorded_invalid_output':invalid,
                       'phase1': packet, 'phase2': references})
    return result


def prepare(destination, scope, reviewers=('R1', 'R2'), items=None):
    destination = destination.resolve()
    if destination.is_relative_to(ROOT.resolve()) or destination.exists():
        raise ValueError('Use a new coordinator directory outside the public repository')
    if len(set(reviewers)) != 2 or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', r) for r in reviewers):
        raise ValueError('Require two distinct safe reviewer aliases')
    if items is None:
        from v2.archive import restore
        restore()
        inputs=read(ROOT/'v2/data/historical-inputs.json')['files']
        for name in ['runs/2026-11-12-rag/cases.json','runs/2026-11-12-rag/generator-controls.jsonl']:
            if sha(ROOT/name) != inputs[name]: raise ValueError('Calibration source record changed')
        items=study_items(scope)
    if not items or len({r['source_key'] for r in items}) != len(items):
        raise ValueError('Missing or duplicated source items')
    destination.mkdir(mode=0o700)
    mapping = {reviewer: {} for reviewer in reviewers}
    for reviewer in reviewers:
        order = list(items)
        random.SystemRandom().shuffle(order)
        for phase in (1, 2):
            packets, templates = [], []
            for item in order:
                key = item['source_key']
                if phase == 1: mapping[reviewer][key] = secrets.token_hex(12)
                identifier = mapping[reviewer][key]
                packet = {'item_id': identifier, **item['phase1']}
                if phase == 2: packet.update(item['phase2'])
                packets.append(packet)
                templates.append({'item_id': identifier, **{k: None for k in FIELDS[phase]},
                                  'rationale': None, 'evidence': [],
                                  **({'aliases': [], 'external_checks': []} if phase == 2 else {'citation_evidence': []})})
            base = destination / 'private' / reviewer
            write_lines(base / f'phase{phase}-packet.jsonl', packets)
            write_lines(base / f'phase{phase}-labels.jsonl', templates)
    write(destination / 'private/items.json', items)
    write(destination / 'private/mapping.json', mapping)
    files = {str(p.relative_to(destination)): sha(p) for p in (destination / 'private').rglob('*') if p.is_file()}
    write(destination / 'session.json', {'scope': scope, 'items': len(items), 'reviewers': list(reviewers),
          'created_utc': datetime.now(timezone.utc).isoformat(), 'prepared_files': files,
          'status': 'Prepared only; no human annotation has been supplied',
          'rubric_sha256': sha(ROOT / 'v2/ANNOTATION.md')})
    if scope == 'calibration': release(destination, 1)
    return {'scope': scope, 'prepared_items': len(items), 'human_labels': 0}


def session(root):
    root = root.resolve()
    if root.is_relative_to(ROOT.resolve()): raise ValueError('Coordinator keys cannot live in the public repository')
    value = read(root / 'session.json')
    for path, expected in value['prepared_files'].items():
        target = (root / path).resolve()
        if not target.is_relative_to(root) or sha(target) != expected:
            raise ValueError('Prepared packet or private mapping changed')
    if value['rubric_sha256'] != sha(ROOT / 'v2/ANNOTATION.md'):
        raise ValueError('Rubric changed; do not mix annotations under different instructions')
    return value


def locked(root, reviewer, phase):
    metadata = read(root / 'locks' / reviewer / f'phase{phase}.json')
    path = root / 'locks' / reviewer / f'phase{phase}-labels.jsonl'
    if sha(path) != metadata['submission_sha256']: raise ValueError('Locked labels changed')
    return {r['item_id']: r for r in lines(path)}, metadata


def release(root, phase, calibration=None):
    value = session(root)
    calibrated_humans = None
    if value['scope'] == 'primary' and phase == 1:
        if calibration is None: raise ValueError('Complete human rubric calibration before releasing primary packets')
        calibrated = session(calibration)
        certificate = read(calibration / 'final.json')
        compare(calibration)  # Also check the locked independent submissions, not just a claimed certificate.
        if calibrated['items'] != 16 or certificate['scope'] != 'calibration' or not certificate['complete'] or certificate['rubric_sha256'] != value['rubric_sha256']:
            raise ValueError('Require a complete calibrated rubric under these same instructions')
        calibrated_humans = {reviewer:identity(locked(calibration,reviewer,1)[1]['human_id']) for reviewer in value['reviewers']}
    if phase == 2:
        for reviewer in value['reviewers']: locked(root, reviewer, 1)
    for reviewer in value['reviewers']:
        for kind in ('packet', 'labels'):
            source = root / 'private' / reviewer / f'phase{phase}-{kind}.jsonl'
            target = root / 'reviewers' / reviewer / source.name
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with target.open('xb') as handle: handle.write(source.read_bytes())
            target.chmod(0o600)
        notice=root/'reviewers'/reviewer/'NOTICE.txt'
        if not notice.exists():
            notice.write_text('Question and source text derived from HotpotQA, Yang, Qi, Zhang et al., EMNLP 2018.\nSource: https://hotpotqa.github.io/\nDataset-derived text is CC BY-SA 4.0: https://creativecommons.org/licenses/by-sa/4.0/\nPackets are formatted and pseudonymized for human evaluation; no gold support flags are included.\n',encoding='utf-8')
            notice.chmod(0o600)
    write(root / f'phase{phase}-released.json', {'phase': phase, 'released_utc': datetime.now(timezone.utc).isoformat(),
          'calibration_final_sha256': sha(calibration / 'final.json') if calibration else None,
          'calibrated_humans':calibrated_humans})


def validate_label(label, phase, packet):
    if any(label.get(field) not in choices for field, choices in FIELDS[phase].items()):
        raise ValueError('Every human categorical label must be explicitly supplied; null is pending')
    if not isinstance(label.get('rationale'), str) or not label['rationale'].strip():
        raise ValueError('A human rationale is required for every item')
    evidence = label.get('evidence')
    if not isinstance(evidence, list): raise ValueError('Evidence must be a list of source coordinates')
    if phase == 1:
        valid = set(re.findall(r'^\[(d\d+s\d+)\] ', packet['transmitted_context'], re.M))
        if any(not isinstance(v, str) or v not in valid for v in evidence):
            raise ValueError('Support coordinates must identify transmitted sentences')
        if label['context_support'] == 'supported' and not evidence:
            raise ValueError('A supported label needs transmitted source coordinates')
        cited = {c['sentence_id'] for c in packet['cited_sentences'] if c['text'] is not None}
        citation_evidence = label.get('citation_evidence')
        if not isinstance(citation_evidence, list) or any(not isinstance(c, str) or c not in cited for c in citation_evidence):
            raise ValueError('Citation-only evidence must actually be cited and present')
        if label['citation_support'] == 'supported' and not citation_evidence:
            raise ValueError('Citation-only support needs cited coordinates, separately from whole context')
    else:
        valid = {(source['source'], s['sentence']) for source in packet['sources'] for s in source['sentences']}
        if any(not isinstance(v, dict) or (v.get('source'), v.get('sentence')) not in valid for v in evidence):
            raise ValueError('Correctness evidence must identify full-source coordinates')
        checks = label.get('external_checks')
        if not isinstance(checks, list) or not isinstance(label.get('aliases'), list) or any(not isinstance(a, str) for a in label['aliases']):
            raise ValueError('Preserve explicit aliases and external-check lists')
        for check in checks:
            if urlsplit(check.get('url', '')).scheme not in ('https', 'http'):
                raise ValueError('An external check requires a URL')
            date.fromisoformat(check['date'])
        if label['correctness'] == 'correct' and not evidence and not checks:
            raise ValueError('Correctness needs source coordinates or a dated external check')


def submit(root, reviewer, phase, source, human_id, independent_human=False):
    value = session(root)
    if reviewer not in value['reviewers'] or not independent_human or not identity(human_id):
        raise ValueError('Require an identified human declaring independent annotation')
    if not (root / f'phase{phase}-released.json').exists(): raise ValueError('This phase has not been released')
    if value['scope'] == 'primary' and phase == 1:
        calibrated=read(root/'phase1-released.json')['calibrated_humans']
        if calibrated.get(reviewer) != identity(human_id): raise ValueError('Primary reviewers must complete the rubric calibration themselves')
    if phase == 2:
        prior = locked(root, reviewer, 1)[1]
        if identity(prior['human_id']) != identity(human_id): raise ValueError('The same reviewer must complete both phases')
    for other in set(value['reviewers']) - {reviewer}:
        path = root / 'locks' / other / f'phase{phase}.json'
        if path.exists() and identity(read(path)['human_id']) == identity(human_id):
            raise ValueError('Two aliases cannot stand in for two independent humans')
    packets = {r['item_id']: r for r in lines(root / 'private' / reviewer / f'phase{phase}-packet.jsonl')}
    labels = lines(source)
    if len(labels) != len(packets) or {r['item_id'] for r in labels} != set(packets):
        raise ValueError('Require every item exactly once, including abstentions and invalid outputs')
    for label in labels: validate_label(label, phase, packets[label['item_id']])
    target = root / 'locks' / reviewer / f'phase{phase}-labels.jsonl'
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with target.open('xb') as handle: handle.write(source.read_bytes())
    target.chmod(0o600)
    write(target.with_name(f'phase{phase}.json'), {'human_id': human_id, 'reviewer_alias': reviewer,
          'independent_human_declaration': True, 'submission_sha256': sha(target),
          'locked_utc': datetime.now(timezone.utc).isoformat(), 'items': len(labels),
          'limit': 'A recorded human declaration is not technical proof of identity or independence.'})


def agreement(left, right):
    table = Counter(zip(left, right, strict=True))
    n = len(left)
    actual = sum(a == b for a, b in zip(left, right, strict=True)) / n
    a, b = Counter(left), Counter(right)
    expected = sum(a[k] * b[k] for k in a.keys() | b.keys()) / n ** 2
    return {'n': n, 'agreement': actual, 'kappa': (actual - expected) / (1 - expected) if expected < 1 else None,
            'confusion': [{'left': x, 'right': y, 'count': count} for (x,y), count in sorted(table.items())],
            'limit': 'Nominal kappa depends on prevalence; it is undefined when chance agreement is one.'}


def compare(root):
    value = session(root)
    mapping = read(root / 'private/mapping.json')
    items = read(root / 'private/items.json')
    result, agreements = [], {}
    humans = set()
    labels = {}
    for reviewer in value['reviewers']:
        for phase in (1,2):
            labels[reviewer, phase], metadata = locked(root, reviewer, phase)
            humans.add(identity(metadata['human_id']))
    if len(humans) != 2: raise ValueError('Require two independent human identities across both phases')
    for item in items:
        decisions = []
        for reviewer in value['reviewers']:
            identifier = mapping[reviewer][item['source_key']]
            first, second = labels[reviewer,1][identifier], labels[reviewer,2][identifier]
            decisions.append({**{field:first[field] for field in FIELDS[1]},
                              **{field:second[field] for field in FIELDS[2]},
                              'phase1_rationale':first['rationale'], 'phase2_rationale':second['rationale'],
                              'context_evidence':first['evidence'], 'citation_evidence':first['citation_evidence'],
                              'source_evidence':second['evidence'], 'aliases':second['aliases'],
                              'external_checks':second['external_checks']})
        fields = [field for group in FIELDS.values() for field in group]
        disputed = [field for field in fields if decisions[0][field] != decisions[1][field]]
        result.append({'source_key': item['source_key'], 'disputed_fields': disputed, 'independent_labels': decisions})
    for phase, fields in FIELDS.items():
        for field in fields:
            agreements[field] = agreement([r['independent_labels'][0][field] for r in result],
                                          [r['independent_labels'][1][field] for r in result])
    return value, items, result, agreements, humans


def adjudication_packet(root):
    value, items, decisions, agreements, _ = compare(root)
    lookup = {r['source_key']: r for r in items}
    packets, templates, mapping = [], [], {}
    for row in decisions:
        if not row['disputed_fields']: continue
        item = lookup[row['source_key']]
        identifier = secrets.token_hex(12)
        mapping[identifier] = row['source_key']
        packets.append({'item_id': identifier, **item['phase1'], **item['phase2'],
                        'disputed_fields': row['disputed_fields'],
                        'independent_labels': [{k:v for k,v in labels.items() if k != 'item_id'} for labels in row['independent_labels']]})
        templates.append({'item_id': identifier, **{k:None for fields in FIELDS.values() for k in fields},
                          'rationale': None, 'context_evidence': [], 'citation_evidence': [], 'source_evidence': [], 'aliases': [], 'external_checks': []})
    random.SystemRandom().shuffle(packets)
    write(root / 'private/adjudication-mapping.json', mapping)
    write_lines(root / 'arbitrator/packet.jsonl', packets)
    write_lines(root / 'arbitrator/labels.jsonl', templates)
    write(root / 'agreement.json', {'scope': value['scope'], 'fields': agreements,
          'disagreements': len(packets), 'before_arbitration': True})
    return {'items': len(items), 'disagreements': len(packets), 'semantic_validation': 'pending' if packets else 'agreement complete'}


def arbitrate(root, source, human_id, independent_human=False):
    _, _, _, _, humans = compare(root)
    if not independent_human or not identity(human_id) or identity(human_id) in humans:
        raise ValueError('Arbitration requires a third independent human')
    packets = {r['item_id']: r for r in lines(root / 'arbitrator/packet.jsonl')}
    labels = lines(source)
    if len(labels) != len(packets) or {r['item_id'] for r in labels} != set(packets):
        raise ValueError('All disagreements must be explicitly resolved; unresolved cases remain pending')
    for label in labels:
        for phase in (1,2):
            view = {**label, 'evidence': label.get('context_evidence' if phase == 1 else 'source_evidence')}
            validate_label(view, phase, packets[label['item_id']])
    target = root / 'locks/arbitration-labels.jsonl'
    with target.open('xb') as handle: handle.write(source.read_bytes())
    target.chmod(0o600)
    write(root / 'locks/arbitration.json', {'human_id':human_id, 'independent_human_declaration': True,
          'submission_sha256':sha(target), 'locked_utc':datetime.now(timezone.utc).isoformat()})


def semantic_contrasts(items, resolved):
    result = []
    by_id = {r['source_key']: r for r in items}
    questions = sorted({r['question_id'] for r in items})
    for method in ('bm25','dense'):
        for field, positive in [('correctness','correct'), ('context_support','supported')]:
            keys = [(f'{q}:{method}:ranked:512', f'{q}:{method}:ranked:1536') for q in questions]
            left = [int(resolved[a][field] == positive) for a,b in keys]
            right = [int(resolved[b][field] == positive) for a,b in keys]
            kinds = [by_id[a]['kind'] for a,b in keys]
            keep = [i for i,(a,b) in enumerate(keys) if not any(resolved[k][field] in ('ambiguous','unverifiable') for k in (a,b))]
            sensitivity = paired_interval([left[i] for i in keep], [right[i] for i in keep], [kinds[i] for i in keep], family=4) if keep else None
            result.append({'method':method,'metric':field,'planned_questions':len(questions),
                           **paired_interval(left,right,kinds,family=4), **exact_mcnemar(left,right),
                           'sensitivity_excluding_uncertain_labels': {'questions':len(keep), 'estimate':sensitivity}})
    for row,p in zip(result,holm([r['p_exact'] for r in result]),strict=True): row['p_holm'] = p
    return result


def finalize(root):
    value, items, decisions, agreements, _ = compare(root)
    unresolved = [r for r in decisions if r['disputed_fields']]
    resolved = {r['source_key']: r['independent_labels'][0] for r in decisions if not r['disputed_fields']}
    if unresolved:
        path = root / 'locks/arbitration.json'
        if not path.exists(): return {'complete':False,'unresolved':len(unresolved),'semantic_results':None}
        metadata = read(path)
        labels = root / 'locks/arbitration-labels.jsonl'
        if sha(labels) != metadata['submission_sha256']: raise ValueError('Arbitration labels changed')
        mapping = read(root / 'private/adjudication-mapping.json')
        for label in lines(labels): resolved[mapping[label['item_id']]] = label
    if len(resolved) != len(items): raise ValueError('Incomplete agreed/adjudicated annotation')
    if value['scope'] == 'primary':
        expected={f'{q}:{m}:{p}:{b}' for q in read(COHORTS)['generation_ids']
                  for m in ('bm25','dense') for p in ('ranked','diverse') for b in (512,1536)}
        if len(items) != 1024 or set(resolved) != expected:
            raise ValueError('The semantic family requires all 1,024 frozen primary outputs')
    counts={}
    for item in items:
        arm=item['source_key'].split(':',1)[1]
        group=counts.setdefault(arm,{'items':0,'recorded_invalid_outputs':0,'labels':{field:Counter() for fields in FIELDS.values() for field in fields}})
        group['items'] += 1
        group['recorded_invalid_outputs'] += int(item.get('recorded_invalid_output',False))
        for field in group['labels']: group['labels'][field][resolved[item['source_key']][field]] += 1
    result = {'complete':True,'scope':value['scope'],'items':len(items),'rubric_sha256':value['rubric_sha256'],
              'agreement_before_arbitration':agreements,'disagreements_arbitrated':len(unresolved),
              'human_labels':resolved,
              'descriptive_categories_by_configuration':counts,
              'semantic_family':semantic_contrasts(items,resolved) if value['scope'] == 'primary' else None,
              'lexical_results_changed':False,
              'interpretation':'Agreed/adjudicated human labels only. No lexical score or automatic judge supplies a missing semantic label.'}
    write(root / 'final.json', result)
    return {k:v for k,v in result.items() if k not in ('human_labels','agreement_before_arbitration','semantic_family')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare','release','submit','compare','arbitrate','finalize'])
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--scope',choices=['calibration','primary'],default='primary')
    parser.add_argument('--phase',type=int,choices=[1,2])
    parser.add_argument('--reviewer')
    parser.add_argument('--submission',type=Path)
    parser.add_argument('--human-id')
    parser.add_argument('--independent-human',action='store_true')
    parser.add_argument('--calibration',type=Path)
    args = parser.parse_args()
    if args.command in ('release','submit') and args.phase is None: parser.error('--phase is required')
    if args.command in ('submit','arbitrate') and (args.submission is None or not args.human_id):
        parser.error('--submission and --human-id are required')
    root = args.directory.resolve()
    if args.command == 'prepare': result = prepare(root,args.scope)
    elif args.command == 'release': result = release(root,args.phase,args.calibration)
    elif args.command == 'submit': result = submit(root,args.reviewer,args.phase,args.submission,args.human_id or '',args.independent_human)
    elif args.command == 'compare': result = adjudication_packet(root)
    elif args.command == 'arbitrate': result = arbitrate(root,args.submission,args.human_id or '',args.independent_human)
    else: result = finalize(root)
    print(json.dumps(result if result is not None else {'saved':True},indent=2))


if __name__ == '__main__': main()
