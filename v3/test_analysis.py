"""Synthetic paired-analysis controls; no experimental outcome collection."""
import copy
import base64
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run as original
from v2.benchmark import payload_for
from v2.core import answer_metrics, digest, paragraph_key
from v3 import analysis
from v3.analysis import (arm_summaries, contrasts, evidence_bytes, evidence_sha, paired,
                         paired_interval, validate_answers, validate_jobs)


def paired_jobs(before, after):
    jobs = {}
    for i, (a, b) in enumerate(zip(before, after, strict=True)):
        for policy, value in [('ranked', a), ('mmr', b)]:
            key = f'q{i}:bm25:{policy}:512'
            jobs[key] = {'id': key, 'question_id': f'q{i}', 'question': f'Question {i}',
                         'type': 'bridge' if i % 2 == 0 else 'comparison',
                         'context': 'Identical source text', 'context_tokens': 8,
                         'evidence_coverage': value, 'complete_context': value}
    return jobs


class PairedAnalysisTests(unittest.TestCase):
    def test_binary_transitions_keep_losses_and_identical_prompts(self):
        jobs = paired_jobs([0, 1, 1, 0], [1, 0, 1, 0])
        row = paired(jobs, [f'q{i}' for i in range(4)],
                     'bm25:ranked:512', 'bm25:mmr:512', 'complete_context', 8)
        self.assertEqual((row['gains'], row['losses'], row['unchanged']), (1, 1, 2))
        self.assertEqual(row['mean_difference'], 0)
        self.assertEqual(row['p_exact'], 1)
        self.assertEqual(row['identical_requests'], 4)
        self.assertEqual(row['changed_results_under_identical_requests'], ['q0', 'q1'])
        self.assertEqual(sum(row['binary_transitions'].values()), 4)

    def test_failed_output_scores_zero_without_becoming_an_abstention(self):
        jobs = paired_jobs([0], [1])
        answers = {'q0:bm25:ranked:512': {'error': 'interrupted', 'metrics': {'answer_em': 1}},
                   'q0:bm25:mmr:512': {'answer': {'abstain': False}, 'metrics': {'answer_em': 1}}}
        em = paired(jobs, ['q0'], 'bm25:ranked:512', 'bm25:mmr:512', 'answer_em', 16, answers)
        unanswered = paired(jobs, ['q0'], 'bm25:ranked:512', 'bm25:mmr:512', 'unanswered', 16, answers)
        self.assertEqual(em['mean_difference'], 1)
        self.assertEqual(unanswered['mean_difference'], -1)
        self.assertEqual(unanswered['favorable_direction'], 'decrease')
        self.assertEqual(unanswered['question_details'][0]['before'], 1)

    def test_bootstrap_is_paired_reproducible_and_family_interval_is_conservative(self):
        before, after = [0, 0, 1, 1], [1, 0, 1, 0]
        kinds = ['bridge', 'bridge', 'comparison', 'comparison']
        first = paired_interval(before, after, kinds, family=8)
        self.assertEqual(first, paired_interval(before, after, kinds, family=8))
        self.assertEqual(first['seed'], 20261115)
        self.assertLessEqual(first['bonferroni_family_interval'][0], first['ci95'][0])
        self.assertGreaterEqual(first['bonferroni_family_interval'][1], first['ci95'][1])
        with self.assertRaises(ValueError):
            paired_interval([], [], [], family=8)

    def test_contrasts_are_fixed_within_retriever_and_budget(self):
        self.assertEqual(len(contrasts()), 8)
        self.assertIn(('dense:sentences:512', 'dense:sentence_mmr:512'), contrasts())
        self.assertTrue(all(a.split(':')[0] == b.split(':')[0] for a, b in contrasts()))
        self.assertTrue(all(a.endswith(':1536') and b.endswith(':1536') for a, b in contrasts(1536)))

    def test_gzip_restore_has_the_same_scientific_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'jobs.json'
            raw = b'[{"id":"one"}]\n'
            path.with_name(path.name + '.gz').write_bytes(gzip.compress(raw, mtime=0))
            self.assertEqual(evidence_bytes(path), raw)
            self.assertEqual(evidence_sha(path), hashlib.sha256(raw).hexdigest())


class InputIntegrityTests(unittest.TestCase):
    def fixture(self):
        case = {'id': 'q', 'type': 'bridge', 'question': 'Which city?', 'answer': 'Paris',
                'context': {'title': ['City'], 'sentences': [['Paris.']]},
                'supporting_facts': {'title': ['City'], 'sent_id': [0]}}
        fact = {'id': 'd00s000', 'title': 'City', 'document': paragraph_key('City', ['Paris.']),
                'sentence': 0, 'text': 'Paris.'}
        job = {'id': 'q:bm25:ranked:512', 'question_id': 'q', 'question': case['question'],
               'context': '[d00p000] City\n[d00s000] Paris.', 'selected': [{'facts': [fact]}]}
        answer = {'answer': 'Paris', 'citations': ['d00s000'], 'abstain': False}
        response = {'model': original.MODELS['generator'][0], 'done': True, 'done_reason': 'stop', 'prompt_eval_count': 30,
                    'message': {'content': json.dumps(answer)}}
        record = {'id': job['id'], 'request': payload_for(job), 'request_sha256': digest(payload_for(job)),
                  'response': response, 'response_body': json.dumps(response), 'answer': answer,
                  'metrics': answer_metrics(case, job, answer)}
        return case, job, record

    def test_duplicate_or_modified_response_cannot_silently_replace_an_observation(self):
        case, job, record = self.fixture()
        args = ({job['id']: job}, {'q': case}, {job['id']})
        self.assertEqual(len(validate_answers([record], *args)), 1)
        with self.assertRaises(ValueError):
            validate_answers([record, record], *args)
        changed = copy.deepcopy(record)
        changed['answer']['answer'] = 'Rome'
        with self.assertRaises(ValueError):
            validate_answers([changed], *args)
        changed = copy.deepcopy(record)
        changed['request']['messages'][1]['content'] += 'extra text'
        with self.assertRaises(ValueError):
            validate_answers([changed], *args)

    def test_interrupted_observation_is_retained_and_missing_outputs_are_not_synthesized(self):
        case, job, record = self.fixture()
        error = {'id': job['id'], 'error': 'Response unobserved', 'request_sha256': digest(payload_for(job))}
        self.assertEqual(validate_answers([error], {job['id']: job}, {'q': case}, {job['id']}), {job['id']: error})
        self.assertEqual(validate_answers([], {job['id']: job}, {'q': case}, {job['id']}), {})

    def test_model_tag_and_raw_output_failures_use_the_same_collection_guard(self):
        case, job, record = self.fixture()
        args = ({job['id']: job}, {'q': case}, {job['id']})
        record['response']['model'] = 'different-model'
        record['response_body'] = json.dumps(record['response'])
        with self.assertRaises(ValueError):
            validate_answers([record], *args)
        record.pop('answer'); record.pop('metrics')
        record['error'] = 'ValueError: Unexpected recorded response model'
        self.assertEqual(validate_answers([record], *args)[job['id']]['error'], record['error'])
        record['error'] = 'ValueError: a different cause'
        with self.assertRaises(ValueError):
            validate_answers([record], *args)

    def test_malformed_and_non_utf8_http_bodies_remain_failed_observations(self):
        case, job, _ = self.fixture()
        args = ({job['id']: job}, {'q': case}, {job['id']})
        for fields in [
            {'http_status': 200, 'response_body': 'not JSON', 'error': 'RecordedRequestError: Invalid JSON response'},
            {'http_status': 500, 'response_body': 'server error', 'error': 'RecordedRequestError: HTTP 500'},
            {'http_status': 200, 'response_body_base64': base64.b64encode(b'\xff').decode(),
             'error': 'RecordedRequestError: Invalid JSON response'},
        ]:
            record = {'id': job['id'], 'request': payload_for(job), **fields}
            self.assertIn(job['id'], validate_answers([record], *args))
        record = {'id': job['id'], 'http_status': 200, 'response_body': '{}',
                  'error': 'RecordedRequestError: Invalid JSON response'}
        with self.assertRaises(ValueError):
            validate_answers([record], *args)

    def test_incomplete_deterministic_factorial_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_jobs([], {'q': {'type': 'bridge'}})

    def test_arm_counts_keep_errors_abstentions_and_unmeasured_budget_separate(self):
        jobs, answers = [], {}
        for method in analysis.METHODS:
            for policy in analysis.POLICIES:
                for budget in analysis.BUDGETS:
                    key = f'q:{method}:{policy}:{budget}'
                    jobs.append({'id': key, 'complete_context': 1, 'evidence_coverage': 1,
                                 'recall10': 1, 'context_tokens': 100, 'retrieved_sentence_coverage': 1,
                                 'selected': [], 'warm_selection_seconds': .01,
                                 'redundancy': {'mean_positive_cosine': .25}})
                    if budget == 512:
                        answers[key] = {'metrics': {'answer_em': 0, 'abstain': 1, 'answer_f1': 0,
                                                    'invalid_citations': 0, 'citation_validity': 0}}
        answers['q:bm25:ranked:512'] = {'error': 'RecordedRequestError: Invalid JSON response', 'response_body': 'invalid JSON'}
        arms = arm_summaries(jobs, answers, ['q'], True)
        failed = next(a for a in arms if a['configuration'] == 'bm25:ranked:512')
        abstained = next(a for a in arms if a['configuration'] == 'bm25:mmr:512')
        large = next(a for a in arms if a['configuration'] == 'bm25:ranked:1536')
        self.assertEqual((failed['errors'], failed['model_abstentions'], failed['unanswered']), (1, 0, 1))
        self.assertEqual((abstained['errors'], abstained['model_abstentions'], abstained['unanswered']), (0, 1, 1))
        self.assertEqual(large['generation_planned'], 0)
        self.assertIsNone(large['mean_f1_all_planned'])
        self.assertEqual(failed['mean_warm_selection_seconds'], .01)
        self.assertEqual(failed['mean_positive_cosine_redundancy'], .25)

    def test_complete_contexts_do_not_enable_lexical_inference_with_missing_answers(self):
        cases = [{'id': f'q{i:03}', 'type': 'bridge' if i < 128 else 'comparison'} for i in range(256)]
        generation = [c['id'] for c in cases[:64] + cases[128:192]]
        jobs = []
        for case in cases:
            for method in analysis.METHODS:
                for policy in analysis.POLICIES:
                    for budget in analysis.BUDGETS:
                        jobs.append({'id': f"{case['id']}:{method}:{policy}:{budget}",
                                     'question_id': case['id'], 'type': case['type'], 'question': 'Synthetic question',
                                     'retriever': method, 'policy': policy, 'budget': budget,
                                     'context': '', 'context_tokens': 0, 'complete_context': 0,
                                     'evidence_coverage': 0, 'recall10': 1,
                                     'retrieved_sentence_coverage': 1, 'selected': []})
        def read(path):
            name = Path(path).name
            return {'confirmatory': cases, 'generation_ids': generation} if name == 'cohorts.json' else (
                {'jobs_sha256': 'synthetic'} if name == 'preparation.json' else jobs)
        with patch.object(analysis, 'read_json', side_effect=read), \
                patch.object(analysis, 'read_lines', return_value=[]), \
                patch.object(analysis, 'evidence_sha', return_value='synthetic'):
            result = analysis.analyse('controlled', write=False)
        self.assertFalse(result['generation_collection_complete'])
        self.assertEqual(len(result['preservation_family']), 8)
        self.assertEqual(result['lexical_family'], [])
        self.assertEqual(result['semantic_validation']['human_annotations_supplied'], 0)
        self.assertTrue(all(a['generation_planned'] == (128 if a['budget'] == 512 else 0) for a in result['arms']))
        self.assertTrue(all(a['generation_observed'] == 0 and a['mean_f1_all_planned'] is None for a in result['arms']))
        with tempfile.TemporaryDirectory() as directory:
            analysis.report(result, Path(directory))
            text = (Path(directory) / 'RESULTS.md').read_text()
            self.assertIn('incomplete (0/128 observed)', text)
            self.assertIn('not measured', text)


if __name__ == '__main__':
    unittest.main()
