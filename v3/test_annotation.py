"""Synthetic controls for V3 reuse of the independent human rubric."""
import json
import base64
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from v3 import annotation
from v3.analysis import METHODS, POLICIES


def item(question, kind, method='bm25', policy='ranked'):
    return {'source_key': f'{question}:{method}:{policy}:512', 'question_id': question, 'kind': kind,
            'recorded_invalid_output': False,
            'phase1': {'question': 'Which city?', 'raw_model_output': '{"answer":"Paris"}',
                       'reported_answer': 'Paris', 'reported_abstention': False,
                       'transmitted_context': '[d00s000] Paris.',
                       'cited_sentences': [{'sentence_id': 'd00s000', 'text': 'Paris.'}]},
            'phase2': {'reference_answer': 'Paris', 'sources': [
                {'source': 'source-00', 'title': 'City', 'sentences': [{'sentence': 0, 'text': 'Paris.'}]}]}}


class AnnotationAdapterTests(unittest.TestCase):
    def prepared(self, directory):
        metadata = {'expected_primary_outputs': 1024, 'test_only': True}
        patches = (patch.object(annotation, 'study_items', return_value=[item('q0', 'bridge'), item('q1', 'comparison')]),
                   patch.object(annotation, 'source_manifest', return_value=metadata))
        return metadata, patches

    def test_prepare_keeps_null_labels_private_and_requires_real_calibration(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'review'
            _, patches = self.prepared(directory)
            with patches[0], patches[1]:
                result = annotation.prepare(directory)
                self.assertEqual(result['human_annotations_supplied'], 0)
                self.assertIsNone(result['semantic_results'])
                self.assertFalse((directory / 'reviewers').exists())
                template = annotation.read_lines(directory / 'private/R1/phase1-labels.jsonl')
                self.assertTrue(all(record[field] is None for record in template for field in annotation.FIELDS[1]))
                with self.assertRaises(ValueError):
                    annotation.release(directory, 1)
                status = annotation.finalize(directory)
                self.assertFalse(status['complete'])
                self.assertEqual(status['human_annotations_supplied'], 0)
                self.assertIsNone(status['semantic_results'])
                self.assertFalse((directory / 'final.json').exists())

    def test_source_binding_uses_the_active_amended_registration(self):
        amended = annotation.BASE / 'registration-amendment-01.json'
        with patch.object(annotation, 'REGISTRATION', amended), \
                patch.object(annotation, 'evidence_sha', side_effect=lambda path: str(path)), \
                patch.object(annotation.workflow, 'sha', return_value='rubric'):
            self.assertEqual(annotation.source_manifest()['registration_sha256'], str(amended))

    def test_changed_source_binding_is_detected_before_human_finalization(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'review'
            _, patches = self.prepared(directory)
            with patches[0], patches[1]:
                annotation.prepare(directory)
                target = directory / 'private/v3-study.json'
                value = json.loads(target.read_text()); value['expected_primary_outputs'] = 1
                target.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    annotation.finalize(directory)

    def test_changed_current_source_is_detected_with_unchanged_private_packets(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / 'review'
            _, patches = self.prepared(directory)
            with patches[0], patches[1]:
                annotation.prepare(directory)
                session = annotation.workflow.session(directory)
                self.assertIn('private/v3-study.json', session['prepared_files'])
            with patch.object(annotation, 'source_manifest', return_value={'changed': True}):
                with self.assertRaises(ValueError):
                    annotation.finalize(directory)

    def test_failed_transport_is_visible_without_model_metadata_or_invented_answer(self):
        records = [
            {'error': 'RecordedRequestError: Invalid JSON response', 'response_body': 'unparseable model/server text'},
            {'error': 'RecordedRequestError: Invalid JSON response', 'response_body_base64': base64.b64encode(b'\xff').decode()},
            {'error': 'RecordedRequestError: HTTP 500', 'response_body': '{"model":"hidden-model","budget":512,"error":"failed"}'},
        ]
        for record in records:
            value = annotation.observed_output(record)
            self.assertIsNone(value['raw_model_output'])
            self.assertTrue(value['recorded_output_failure'])
            self.assertTrue(value['transport_body_archived'])
            self.assertNotIn('hidden-model', json.dumps(value))
            self.assertNotIn('512', json.dumps(value))
        value = annotation.observed_output({'response_body': '{"model":"hidden-model","message":{"content":"raw invalid answer"}}',
                                            'error': 'JSONDecodeError: response content was not JSON'})
        self.assertEqual(value['raw_model_output'], 'raw invalid answer')
        self.assertNotIn('hidden-model', json.dumps(value))

    def test_mapping_keys_cannot_be_prepared_inside_public_checkout(self):
        _, patches = self.prepared(None)
        with patches[0], patches[1]:
            with self.assertRaises(ValueError):
                annotation.prepare(annotation.ROOT / 'v3/private-review-must-not-exist')

    def test_semantic_endpoints_remain_separate_with_the_prespecified_family(self):
        items = [item(question, kind, method, policy)
                 for question, kind in [('q0', 'bridge'), ('q1', 'comparison')]
                 for method in METHODS for policy in POLICIES]
        resolved = {entry['source_key']: {'correctness': 'incorrect', 'context_support': 'insufficient'} for entry in items}
        resolved['q0:bm25:mmr:512']['correctness'] = 'correct'
        resolved['q1:bm25:sentence_mmr:512']['correctness'] = 'ambiguous'
        rows = annotation.semantic_contrasts(items, resolved)
        self.assertEqual(len(rows), 16)
        self.assertTrue(all(row['family_size'] == 16 and row['planned_questions'] == 2 for row in rows))
        match = next(row for row in rows if row['before'] == 'bm25:ranked:512'
                     and row['after'] == 'bm25:mmr:512' and row['metric'] == 'correctness')
        self.assertEqual((match['gains'], match['losses'], match['mean_difference']), (1, 0, .5))
        self.assertTrue(all(row['mean_difference'] == 0 for row in rows if row['metric'] == 'context_support'))
        uncertain = next(row for row in rows if row['after'] == 'bm25:sentence_mmr:512'
                         and row['before'] == 'bm25:ranked:512' and row['metric'] == 'correctness')
        self.assertEqual(uncertain['planned_questions'], 2)
        self.assertEqual(uncertain['sensitivity_excluding_uncertain_labels']['questions'], 1)


if __name__ == '__main__':
    unittest.main()
