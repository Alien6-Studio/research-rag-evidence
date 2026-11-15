"""Fail closed on missing evidence and replay invalid outputs from their actual body."""
import json
from pathlib import Path
import tempfile
import unittest
import yaml

import run
from test_run import fixture
from v2.archive import MANIFEST
from v2.benchmark import payload_for
from v2.core import answer_metrics, chunks, digest, documents
from v2.verify import verify_answers


class RecordedStudyTests(unittest.TestCase):
    def test_ci_explicitly_runs_full_v2_replay_without_soft_failure(self):
        workflow=yaml.safe_load((Path(__file__).resolve().parents[1]/'.github/workflows/ci.yml').read_text())
        job=workflow['jobs']['checks']
        steps=[s for s in job['steps'] if 'python -m v2.verify' in s.get('run','')]
        self.assertEqual(len(steps),1)
        self.assertNotIn('if',steps[0])
        self.assertFalse(steps[0].get('continue-on-error',False))
        self.assertFalse(job.get('continue-on-error',False))

    def test_required_evidence_is_present_instead_of_silently_skipping_v2(self):
        self.assertTrue(MANIFEST.is_file(),'The published study must include its complete V2 archive')
        self.assertEqual(len(json.loads(MANIFEST.read_text())['files']),315)

    def test_recorded_error_must_be_reproduced_and_cannot_hide_a_success_or_changed_body(self):
        case=fixture()
        job={'id':'unit','question_id':case['id'],'question':case['question'],
             'selected':chunks(documents(case)),'context':'controlled fixture'}
        answer={'answer':case['answer'],'citations':['d00s000'],'abstain':False}
        response={'model':run.MODELS['generator'][0],'done':True,'done_reason':'stop','prompt_eval_count':100,
                  'message':{'role':'assistant','content':json.dumps(answer)}}
        request=payload_for(job)
        record={'id':'unit','request':request,'request_sha256':digest(request),'response':response,
                'response_body':json.dumps(response),'answer':answer,'metrics':answer_metrics(case,job,answer)}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'intents.jsonl').write_text(json.dumps({'id':'unit','request':request,'request_sha256':digest(request)})+'\n')
            def check():
                (root/'answers.jsonl').write_text(json.dumps(record)+'\n')
                return verify_answers(root,{'unit':job},{case['id']:case},{'unit'})
            self.assertEqual(check()['errors'],0)
            record['error']='ValueError: invented failure'
            with self.assertRaises(ValueError): check()
            del record['answer']; del record['metrics']
            response['message']['content']=json.dumps({**answer,'abstain':True})
            record['response_body']=json.dumps(response)
            record['error']='ValueError: Output violates the registered response instructions'
            self.assertEqual(check()['failures_reconstructed_from_raw_response'],1)
            record['response_body']='{}'
            with self.assertRaises(ValueError): check()
