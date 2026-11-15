"""Append-only V3 preparation and generation with frozen, label-free selectors."""
from __future__ import annotations

import argparse
import base64
import gzip
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import time
import urllib.request
import urllib.error

import numpy as np
from tokenizers import Tokenizer

import run as original
from v2.benchmark import archived_vectors, payload_for
from v2.core import answer_metrics, chunks, digest, documents, ranking
from v2.verify import checked_answer
from v3.core import (POLICIES, context_metrics, context_redundancy,
                     required_sentence_texts, select)
from v3.design import (BASE, COHORTS, REGISTRATION, ROOT, append, check_inputs,
                       file_sha, lines, read, registered, utc, write_new)

METHODS = ('bm25', 'dense')
BUDGETS = (512, 1536)
SEED = 20261115


class RecordedRequestError(RuntimeError):
    """Keep even malformed or failed HTTP bodies as observations."""
    def __init__(self, message, raw, elapsed, status):
        super().__init__(message)
        self.record = {'wall_seconds': elapsed, 'http_status': status}
        try:
            self.record['response_body'] = raw.decode('utf-8')
        except UnicodeDecodeError:
            self.record['response_body_base64'] = base64.b64encode(raw).decode('ascii')


def request(endpoint, payload=None):
    encoded = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(original.BASE + endpoint, data=encoded,
                                 headers={'Content-Type': 'application/json'})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            raw = response.read(); status = response.status
    except urllib.error.HTTPError as error:
        raise RecordedRequestError(f'HTTP {error.code}', error.read(),
                                   time.perf_counter() - started, error.code) from error
    elapsed = time.perf_counter() - started
    try:
        body = raw.decode('utf-8'); parsed = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RecordedRequestError('Invalid JSON response', raw, elapsed, status) from error
    return parsed, body, elapsed


def public_registration():
    proof = read(BASE / 'public-registration.json')
    if proof['registration_sha256'] != file_sha(REGISTRATION):
        raise ValueError('Public registration identity differs')
    captured = subprocess.check_output(
        ['git', 'show', proof['commit'] + ':v3/registration.json'], cwd=ROOT)
    if captured != REGISTRATION.read_bytes() or not proof.get('github_pull_request_created_at'):
        raise ValueError('Require the published registration and actual GitHub timestamp')
    return proof


def model_check():
    installed = {m['name']: m for m in request('tags')[0]['models']}
    details = {}
    for role in ('generator', 'embedding'):
        name, expected = original.MODELS[role]
        if installed.get(name, {}).get('digest') != expected:
            raise ValueError('Pinned model differs: ' + role)
        details[role] = {'tag': installed[name], 'show': request('show', {'model': name})[0]}
    environment = read(BASE / 'environment.json')
    dependencies = {n: importlib.metadata.version(n) for n in
                    ('numpy', 'pyarrow', 'tokenizers', 'ujson', 'matplotlib')}
    if any(environment['dependencies'][n] != v for n, v in dependencies.items()):
        raise ValueError('Collection dependencies differ from the frozen environment')
    return {'utc': utc(), 'ollama': request('version')[0], 'models': original.MODELS,
            'model_details': details, 'dependencies': dependencies, 'python': sys.version,
            'system': platform.system(), 'architecture': platform.machine(),
            'logical_cpus': os.cpu_count(), 'load_average': list(os.getloadavg()),
            'code_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'registration_sha256': file_sha(REGISTRATION),
            'public_registration': public_registration(),
            'scope': 'One local quality experiment; timings do not qualify production performance or financial cost.'}


def packet_vectors(packet, vectors):
    if packet['model_digest'] != original.MODELS['embedding'][1]:
        raise ValueError('Embedding model identity differs')
    values = json.loads(packet['response_body'])['embeddings']
    updates = {}
    for text, vector in zip(packet['request']['input'], values, strict=True):
        array = np.asarray(vector, dtype=float)
        if array.shape != (768,) or not np.all(np.isfinite(array)) or np.linalg.norm(array) <= 0:
            raise ValueError('Invalid preserved embedding')
        if text in vectors and not np.allclose(vectors[text], vector, rtol=0, atol=1e-7):
            raise ValueError('Conflicting preserved embeddings for the same input')
        updates[text] = vector
    vectors.update(updates)


def load_vectors():
    vectors = archived_vectors()
    for directory in (ROOT / 'v2/runs/embedding-traces', BASE / 'runs/embedding-traces'):
        for path in sorted(directory.glob('batch-*.json.gz')):
            packet_vectors(json.loads(gzip.decompress(path.read_bytes())), vectors)
    return vectors


def embeddings_for(texts, purpose, vectors=None):
    vectors = load_vectors() if vectors is None else vectors
    directory = BASE / 'runs/embedding-traces'
    directory.mkdir(parents=True, exist_ok=True)
    pending = sorted(set(texts) - vectors.keys())
    summary = {'purpose': purpose, 'requested_unique': len(set(texts)),
               'cached_inputs': len(set(texts)) - len(pending), 'new_inputs': len(pending),
               'api_wall_seconds': 0.0, 'packets': []}
    number = len(list(directory.glob('batch-*.json.gz')))
    for start in range(0, len(pending), 16):
        batch = pending[start:start + 16]
        payload = {'model': original.MODELS['embedding'][0], 'input': batch,
                   'truncate': False, 'keep_alive': '30m', 'options': {'num_thread': 8}}
        packet = {'utc': utc(), 'model_digest': original.MODELS['embedding'][1],
                  'purpose': purpose, 'request': payload,
                  'registration_sha256': file_sha(REGISTRATION)}
        failure = None
        try:
            _, body, elapsed = request('embed', payload)
            packet.update({'response_body': body, 'wall_seconds': elapsed})
            packet_vectors(packet, vectors)
        except Exception as error:
            if isinstance(error, RecordedRequestError): packet.update(error.record)
            packet['error'] = f'{type(error).__name__}: {error}'
            failure = error
        target = directory / f'batch-{number:05}.json.gz'
        with target.open('xb') as output:
            output.write(gzip.compress(json.dumps(packet, ensure_ascii=False).encode(), mtime=0))
        if failure is not None:
            raise RuntimeError('Embedding failure archived; stop the collection') from failure
        summary['packets'].append(str(target.relative_to(ROOT)))
        summary['api_wall_seconds'] += elapsed
        number += 1
        print(f'Embedded {min(start + 16, len(pending))}/{len(pending)} ({purpose})', flush=True)
    return vectors, summary


def run_path(split, environment='controlled'):
    return BASE / 'runs' / f'{split}-{environment}'


def require_pilot():
    out = run_path('pilot')
    certificate = read(out / 'qualification.json')
    if not certificate['passed'] or certificate['registration_sha256'] != file_sha(REGISTRATION):
        raise ValueError('Pilot is not qualified for this registration')
    for name in ('jobs.json', 'answers.jsonl'):
        if certificate[name + '_sha256'] != file_sha(out / name):
            raise ValueError('Pilot evidence changed')
    expected = {p.name: file_sha(p) for p in out.iterdir()
                if p.suffix in ('.json', '.jsonl') and p.name != 'qualification.json'}
    if certificate.get('evidence_sha256') != expected:
        raise ValueError('Pilot preparation, probe or execution evidence changed')


def prepare(split, environment):
    registered(); public_registration()
    if split == 'confirmatory':
        require_pilot()
    if split == 'pilot' and environment != 'controlled':
        raise ValueError('The technical pilot is controlled only')
    out = run_path(split, environment)
    if out.exists() and any(out.iterdir()):
        raise ValueError('A started preparation is retained; use a prospective amendment rather than replaying probes')
    out.mkdir(parents=True, exist_ok=True)
    execution = model_check()
    write_new(out / 'preparation-start.json', execution)
    cases = read(COHORTS)[split]
    tokenizer = Tokenizer.from_file(str(ROOT / 'data/qwen-tokenizer.json'))
    if split == 'pilot':
        calibration = []
        for index, text in enumerate(('Hello world.', 'Thirty seconds, then one retry after two seconds.',
                                      '[d00s002] Paris is in France.')):
            payload = {'model': original.MODELS['generator'][0], 'prompt': text, 'raw': True,
                       'stream': False, 'think': False,
                       'options': {**original.OPTIONS, 'num_predict': 1}}
            append(out / 'tokenizer-calibration-intents.jsonl',
                   {'id': f'probe-{index}', 'utc': utc(), 'request': payload, 'request_sha256': digest(payload)})
            record = {'id': f'probe-{index}', 'utc': utc(), 'request': payload,
                      'tokenizer_tokens': len(tokenizer.encode(text).ids)}
            try:
                response, body, elapsed = request('generate', payload)
                record.update({'response_body': body, 'wall_seconds': elapsed,
                               'ollama_tokens': response['prompt_eval_count']})
            except Exception as error:
                if isinstance(error, RecordedRequestError): record.update(error.record)
                record['error'] = f'{type(error).__name__}: {error}'
                append(out / 'tokenizer-calibration-responses.jsonl', record)
                raise RuntimeError('Tokenizer probe failure retained; stop before confirmation') from error
            append(out / 'tokenizer-calibration-responses.jsonl', record)
            calibration.append(record)
        write_new(out / 'tokenizer-calibration.json', calibration)
        if any(c['tokenizer_tokens'] != c['ollama_tokens'] for c in calibration):
            raise ValueError('Tokenizer calibration failed')
    corpus = {d['key']: d for case in cases for d in documents(case)}
    pooled = chunks([corpus[k] for k in sorted(corpus)]) if environment == 'pooled' else None
    indexed = {case['id']: pooled if pooled is not None else chunks(documents(case)) for case in cases}
    retrieval_texts = {'search_query: ' + c['question'] for c in cases}
    for group in ([pooled] if pooled is not None else indexed.values()):
        retrieval_texts.update('search_document: ' + c['text'] for c in group)
    vectors, retrieval_cost = embeddings_for(retrieval_texts, split + ':' + environment + ':retrieval')
    rankings = {}; retrieval = []; started = time.perf_counter()
    for case in cases:
        for method in METHODS:
            ranked = ranking(indexed[case['id']], case['question'], method, vectors)
            rankings[case['id'], method] = ranked
            retrieval.append({'question_id': case['id'], 'retriever': method,
                              'indexed_chunks': len(ranked),
                              'ranking_sha256': digest([c['id'] for c in ranked]),
                              'top_ten_sha256': digest(ranked[:10])})
    retrieval_seconds = time.perf_counter() - started
    sentence_texts = {text for ranked in rankings.values()
                      for text in required_sentence_texts(ranked[:10])}
    vectors, sentence_cost = embeddings_for(sentence_texts, split + ':' + environment + ':sentences', vectors)
    jobs = []
    for case in cases:
        for method in METHODS:
            ranked = rankings[case['id'], method]
            for policy in POLICIES:
                for budget in BUDGETS:
                    started = time.perf_counter()
                    selected = select(case['question'], ranked[:10], policy, budget, tokenizer, vectors)
                    elapsed = time.perf_counter() - started
                    metrics = context_metrics(case, indexed[case['id']], ranked, selected, tokenizer, budget)
                    jobs.append({'id': f"{case['id']}:{method}:{policy}:{budget}",
                                 'question_id': case['id'], 'question': case['question'],
                                 'type': case['type'], 'retriever': method, 'policy': policy,
                                 'budget': budget, 'environment': environment, 'split': split,
                                 'selected': selected, 'retrieved': ranked[:10],
                                 'warm_selection_seconds': elapsed,
                                 'redundancy': context_redundancy(selected, vectors), **metrics})
        print(f"Prepared {len(jobs)}/{len(cases) * 16} ({split}/{environment})", flush=True)
    random.Random(SEED + 5).shuffle(jobs)
    write_new(out / 'jobs.json', jobs)
    write_new(out / 'preparation.json', {**execution, 'split': split, 'environment': environment,
              'questions': len(cases), 'jobs': len(jobs), 'jobs_sha256': file_sha(out / 'jobs.json'),
              'corpus_paragraphs': len(corpus), 'corpus_chunks': len(pooled) if pooled is not None else None,
              'corpus_sha256': digest([corpus[k] for k in sorted(corpus)]),
              'retrieval': retrieval, 'shared_ranking_wall_seconds': retrieval_seconds,
              'embedding_preparation': [retrieval_cost, sentence_cost],
              'scope': 'Pooled results are separate exploratory question-derived retrieval, without generation.'
                       if pooled is not None else 'Controlled ten supplied paragraphs per question.'})


def generate(split):
    registered(); public_registration()
    if split == 'confirmatory':
        require_pilot()
    out = run_path(split)
    preparation = read(out / 'preparation.json')
    if preparation['jobs_sha256'] != file_sha(out / 'jobs.json'):
        raise ValueError('Prepared inputs changed')
    write_new(out / f'execution-{time.time_ns()}.json', model_check())
    cohort = read(COHORTS); cases = {c['id']: c for c in cohort[split]}
    ids = set(cohort['generation_ids']) if split == 'confirmatory' else set(cases)
    jobs = [j for j in read(out / 'jobs.json') if j['budget'] == 512 and j['question_id'] in ids]
    destination = out / 'answers.jsonl'; intents = out / 'intents.jsonl'
    observed = lines(destination); done = {a['id'] for a in observed}
    if len(done) != len(observed):
        raise ValueError('Duplicate observed generation')
    for intent in lines(intents):
        if intent['id'] not in done:
            append(destination, {'id': intent['id'], 'utc': utc(), 'request': intent['request'],
                                'request_sha256': intent['request_sha256'],
                                'error': 'Interrupted after intent; response unobserved, not regenerated.'})
            done.add(intent['id'])
    errors = 0
    for record in reversed(lines(destination)):
        if 'error' not in record:
            break
        errors += 1
    if errors >= 3 and any(job['id'] not in done for job in jobs):
        raise RuntimeError('Three consecutive retained failures; a recorded prospective resumption is required')
    for job in jobs:
        if job['id'] in done:
            continue
        payload = payload_for(job)
        append(intents, {'id': job['id'], 'utc': utc(), 'request_sha256': digest(payload), 'request': payload})
        result = {'id': job['id'], 'utc': utc(), 'request': payload, 'request_sha256': digest(payload)}
        try:
            response, body, elapsed = request('chat', payload)
            result.update({'response_body': body, 'response': response, 'wall_seconds': elapsed})
            answer = checked_answer(response)
            result.update({'answer': answer, 'metrics': answer_metrics(cases[job['question_id']], job, answer)})
            errors = 0
        except Exception as error:
            if isinstance(error, RecordedRequestError): result.update(error.record)
            result['error'] = f'{type(error).__name__}: {error}'
            errors += 1
        append(destination, result); done.add(job['id'])
        print(f"Generated {len(done)}/{len(jobs)} ({split}); error={'error' in result}", flush=True)
        if errors >= 3:
            raise RuntimeError('Three consecutive failures; raw observations retained')


def qualify():
    registered(); public_registration()
    out = run_path('pilot'); jobs = read(out / 'jobs.json')
    preparation = read(out / 'preparation.json')
    cohort = read(COHORTS)['pilot']
    expected = {f"{c['id']}:{m}:{p}:{b}" for c in cohort for m in METHODS
                for p in POLICIES for b in BUDGETS}
    calibration = read(out / 'tokenizer-calibration.json'); answers = lines(out / 'answers.jsonl')
    planned = {j['id']: j for j in jobs if j['budget'] == 512}
    observed = {a['id']: a for a in answers}
    passed = (len(jobs) == len({j['id'] for j in jobs}) == 128
              and {j['id'] for j in jobs} == expected
              and preparation['jobs_sha256'] == file_sha(out / 'jobs.json')
              and preparation['registration_sha256'] == file_sha(REGISTRATION)
              and len(answers) == len(observed) == len(planned) == 64
              and set(observed) == set(planned) and not any('error' in a for a in answers)
              and len(calibration) == 3 and all(c['tokenizer_tokens'] == c['ollama_tokens'] for c in calibration))
    if any(observed[k].get('request') != payload_for(planned[k]) for k in observed.keys() & planned.keys()):
        passed = False
    verification = None; verification_error = None
    try:
        from v3.verify import verify_pilot_inputs
        verification = verify_pilot_inputs()
        passed = passed and verification['passed']
    except Exception as error:
        verification_error = f'{type(error).__name__}: {error}'
        passed = False
    write_new(out / 'qualification.json', {'utc': utc(), 'passed': passed, 'questions': 8,
              'contexts': len(jobs), 'responses': len(answers), 'errors': sum('error' in a for a in answers),
              'registration_sha256': file_sha(REGISTRATION),
              'jobs.json_sha256': file_sha(out / 'jobs.json'),
              'answers.jsonl_sha256': file_sha(out / 'answers.jsonl'),
              'evidence_sha256': {p.name: file_sha(p) for p in out.iterdir()
                                  if p.suffix in ('.json', '.jsonl') and p.name != 'qualification.json'},
              'independent_replay': verification, 'verification_error': verification_error,
              'criterion': '128 prepared contexts and all 64 planned untruncated instruction-consistent responses, exact tokenizer probes; no answer-quality threshold.'})
    if not passed:
        raise RuntimeError('Pilot failed; preserve it and publish a prospective amendment before confirmation')
    print('Technical pilot qualified; no semantic conclusion follows.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['prepare', 'generate', 'qualify'])
    parser.add_argument('--split', choices=['pilot', 'confirmatory'], default='pilot')
    parser.add_argument('--environment', choices=['controlled', 'pooled'], default='controlled')
    args = parser.parse_args()
    if args.stage == 'prepare': prepare(args.split, args.environment)
    elif args.stage == 'generate': generate(args.split)
    else: qualify()


if __name__ == '__main__':
    main()
