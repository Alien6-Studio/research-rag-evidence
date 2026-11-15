"""Synthetic collection controls; these tests make no model calls."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import run as original
from v2.benchmark import payload_for
from v2.core import digest
from v3 import benchmark
from v3.design import file_sha, lines


class DummyResponse:
    status = 200
    def __init__(self, body): self.body = body
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return self.body


class CollectorControls(unittest.TestCase):
    def test_malformed_utf8_and_json_bodies_are_preserved(self):
        for raw in (b'not-json', b'\xff\xfe'):
            with patch('urllib.request.urlopen', return_value=DummyResponse(raw)):
                with self.assertRaises(benchmark.RecordedRequestError) as caught:
                    benchmark.request('chat', {'synthetic': True})
            fields = caught.exception.record
            self.assertTrue('response_body' in fields or 'response_body_base64' in fields)
            self.assertEqual(fields['http_status'], 200)

    def test_embedding_validation_is_atomic(self):
        packet = {'model_digest': original.MODELS['embedding'][1],
                  'request': {'input': ['valid', 'invalid']},
                  'response_body': json.dumps({'embeddings': [[1.0] * 768, [0.0] * 768]})}
        vectors = {}
        with self.assertRaises(ValueError): benchmark.packet_vectors(packet, vectors)
        self.assertEqual(vectors, {})

    def test_three_errors_stop_and_recorded_errors_are_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); out = root / 'pilot'; out.mkdir()
            cohorts = root / 'cohorts.json'
            cohorts.write_text(json.dumps({'pilot': [{'id': 'q', 'question': 'Synthetic?'}]}))
            jobs = [{'id': f'q:bm25:{policy}:512', 'question_id': 'q', 'budget': 512,
                     'question': 'Synthetic?', 'context': ''} for policy in ('ranked', 'mmr', 'sentences')]
            (out / 'jobs.json').write_text(json.dumps(jobs))
            (out / 'preparation.json').write_text(json.dumps({'jobs_sha256': file_sha(out / 'jobs.json')}))
            error = benchmark.RecordedRequestError('HTTP 500', b'{"synthetic_error":true}', .01, 500)
            with patch.object(benchmark, 'registered'), patch.object(benchmark, 'public_registration'), \
                 patch.object(benchmark, 'model_check', return_value={}), \
                 patch.object(benchmark, 'run_path', return_value=out), \
                 patch.object(benchmark, 'COHORTS', cohorts), \
                 patch.object(benchmark, 'request', side_effect=error) as request:
                with self.assertRaises(RuntimeError): benchmark.generate('pilot')
                self.assertEqual(request.call_count, 3)
                benchmark.generate('pilot')
                self.assertEqual(request.call_count, 3)
            records = lines(out / 'answers.jsonl')
            self.assertEqual(len(records), 3)
            self.assertTrue(all(row['http_status'] == 500 and 'response_body' in row for row in records))
            self.assertEqual(len(lines(out / 'intents.jsonl')), 3)

    def test_unobserved_intent_becomes_failure_without_regeneration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); out = root / 'pilot'; out.mkdir()
            cohorts = root / 'cohorts.json'; cohorts.write_text(json.dumps({'pilot': [{'id': 'q'}]}))
            job = {'id': 'q:bm25:ranked:512', 'question_id': 'q', 'budget': 512,
                   'question': 'Synthetic?', 'context': ''}
            (out / 'jobs.json').write_text(json.dumps([job]))
            (out / 'preparation.json').write_text(json.dumps({'jobs_sha256': file_sha(out / 'jobs.json')}))
            payload = payload_for(job)
            (out / 'intents.jsonl').write_text(json.dumps({'id': job['id'], 'request': payload,
                                                        'request_sha256': digest(payload)}) + '\n')
            with patch.object(benchmark, 'registered'), patch.object(benchmark, 'public_registration'), \
                 patch.object(benchmark, 'model_check', return_value={}), \
                 patch.object(benchmark, 'run_path', return_value=out), \
                 patch.object(benchmark, 'COHORTS', cohorts), \
                 patch.object(benchmark, 'request') as request:
                benchmark.generate('pilot'); request.assert_not_called()
            record = lines(out / 'answers.jsonl')[0]
            self.assertIn('Interrupted', record['error'])
            self.assertEqual(record['request'], payload)


if __name__ == '__main__': unittest.main()
