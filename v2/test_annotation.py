"""Exercise the human workflow using synthetic labels, never study annotations."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from v2 import annotation as a


def fixture():
    return {'source_key':'private-question:bm25:ranked:512', 'question_id':'private-question', 'kind':'bridge',
            'phase1':{'question':'Where is the example?', 'raw_model_output':'{"answer":"Paris"}',
                      'reported_answer':'Paris','reported_abstention':False,
                      'transmitted_context':'[d00s000] The example is in Paris.',
                      'cited_sentences':[{'sentence_id':'d00s000','text':'The example is in Paris.'}]},
            'phase2':{'reference_answer':'Paris', 'sources':[{'source':'source-00','title':'Example',
                       'sentences':[{'sentence':0,'text':'The example is in Paris.'}]}]}}


def completed(root, reviewer, phase, changed=False):
    path = root / 'reviewers' / reviewer / f'phase{phase}-labels.jsonl'
    values = a.lines(path)
    for row in values:
        if phase == 1:
            row.update(context_support='insufficient' if changed else 'supported', citation_support='supported',
                       citation_validity='valid_ids',abstention_justification='not_applicable',
                       evidence=['d00s000'],citation_evidence=['d00s000'])
        else:
            row.update(correctness='correct',reference_adequacy='adequate',
                       evidence=[{'source':'source-00','sentence':0}])
        row['rationale'] = f'Synthetic phase {phase} reason; not a study annotation.'
    path.write_text('\n'.join(json.dumps(r) for r in values)+'\n')
    return path


class AnnotationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'session'
        a.prepare(self.root, 'calibration', items=[fixture()])

    def tearDown(self): self.temp.cleanup()

    def submit_phase(self, phase, changed=False):
        for reviewer,human in [('R1','synthetic-human-one'),('R2','synthetic-human-two')]:
            path=completed(self.root,reviewer,phase,changed and reviewer=='R2')
            a.submit(self.root,reviewer,phase,path,human,True)

    def test_phase1_is_blind_and_aliases_are_independent_and_templates_empty(self):
        packets=[a.lines(self.root/'reviewers'/r/'phase1-packet.jsonl')[0] for r in ('R1','R2')]
        self.assertNotEqual(packets[0]['item_id'],packets[1]['item_id'])
        text=json.dumps(packets)
        for forbidden in ['private-question','reference_answer','sources','bm25','budget','answer_em','record_status']:
            self.assertNotIn(forbidden,text)
        self.assertEqual(packets[0]['transmitted_context'],fixture()['phase1']['transmitted_context'])
        labels=a.lines(self.root/'reviewers/R1/phase1-labels.jsonl')[0]
        self.assertTrue(all(labels[k] is None for k in a.FIELDS[1]))
        with self.assertRaises(ValueError):
            a.submit(self.root,'R1',1,self.root/'reviewers/R1/phase1-labels.jsonl','synthetic-human-one',True)

    def test_reference_release_requires_both_locked_independent_reviews(self):
        with self.assertRaises(FileNotFoundError): a.release(self.root,2)
        path=completed(self.root,'R1',1)
        a.submit(self.root,'R1',1,path,'synthetic-human-one',True)
        with self.assertRaises(FileNotFoundError): a.release(self.root,2)
        path=completed(self.root,'R2',1)
        with self.assertRaises(ValueError): a.submit(self.root,'R2',1,path,'SYNTHETIC-HUMAN-ONE',True)
        a.submit(self.root,'R2',1,path,'synthetic-human-two',True)
        a.release(self.root,2)
        self.assertEqual(a.lines(self.root/'reviewers/R1/phase2-packet.jsonl')[0]['reference_answer'],'Paris')

    def test_original_phase1_cannot_be_overwritten_or_silently_changed(self):
        self.submit_phase(1)
        path=completed(self.root,'R1',1)
        with self.assertRaises(FileExistsError): a.submit(self.root,'R1',1,path,'synthetic-human-one',True)
        locked=self.root/'locks/R1/phase1-labels.jsonl'
        locked.write_text('changed')
        with self.assertRaises(ValueError): a.release(self.root,2)

    def test_agreement_retains_both_reasons_and_does_not_fabricate_a_third_review(self):
        self.submit_phase(1)
        a.release(self.root,2)
        self.submit_phase(2)
        _,_,rows,_,_=a.compare(self.root)
        self.assertIn('phase 1',rows[0]['independent_labels'][0]['phase1_rationale'])
        self.assertIn('phase 2',rows[0]['independent_labels'][0]['phase2_rationale'])
        self.assertTrue(a.finalize(self.root)['complete'])
        self.assertFalse((self.root/'locks/arbitration.json').exists())

    def test_disagreement_stays_pending_until_an_independent_third_human_resolves_it(self):
        self.submit_phase(1,changed=True)
        a.release(self.root,2)
        self.submit_phase(2)
        self.assertEqual(a.adjudication_packet(self.root)['disagreements'],1)
        self.assertFalse(a.finalize(self.root)['complete'])
        label=a.lines(self.root/'arbitrator/labels.jsonl')[0]
        label.update(context_support='supported',citation_support='supported',citation_validity='valid_ids',
                     abstention_justification='not_applicable',correctness='correct',reference_adequacy='adequate',
                     context_evidence=['d00s000'],citation_evidence=['d00s000'],
                     source_evidence=[{'source':'source-00','sentence':0}],rationale='Synthetic arbitration only.')
        path=self.root/'third-human.jsonl'
        path.write_text(json.dumps(label)+'\n')
        with self.assertRaises(ValueError): a.arbitrate(self.root,path,'synthetic-human-one',True)
        a.arbitrate(self.root,path,'synthetic-human-three',True)
        self.assertTrue(a.finalize(self.root)['complete'])

    def test_primary_material_is_prepared_but_not_released_before_rubric_calibration(self):
        primary=Path(self.temp.name)/'primary'
        a.prepare(primary,'primary',items=[fixture()])
        self.assertFalse((primary/'reviewers').exists())
        with self.assertRaises(ValueError): a.release(primary,1)

    def test_context_support_does_not_substitute_for_citation_only_evidence(self):
        packet=fixture()['phase1']
        label={'context_support':'supported','citation_support':'supported','citation_validity':'valid_ids',
               'abstention_justification':'not_applicable','rationale':'Synthetic reason',
               'evidence':['d00s000'],'citation_evidence':[]}
        with self.assertRaises(ValueError): a.validate_label(label,1,packet)

    def test_degenerate_kappa_is_undefined_and_confusion_counts_are_kept(self):
        self.assertIsNone(a.agreement(['correct'],['correct'])['kappa'])
        result=a.agreement(['correct','incorrect'],['incorrect','incorrect'])
        self.assertEqual(result['agreement'],.5)
        self.assertEqual(sum(c['count'] for c in result['confusion']),2)

    def test_semantic_family_uses_human_labels_with_question_pairing_and_keeps_uncertainty(self):
        items=[]
        labels={}
        for q,kind in [('one','bridge'),('two','comparison')]:
            for method in ('bm25','dense'):
                for budget in (512,1536):
                    key=f'{q}:{method}:ranked:{budget}'
                    items.append({'source_key':key,'question_id':q,'kind':kind})
                    labels[key]={'correctness':'correct' if budget==1536 else 'incorrect',
                                 'context_support':'ambiguous' if budget==512 else 'supported',
                                 'answer_em':0}  # This automatic/lexical value must never supply a semantic label.
        rows=a.semantic_contrasts(items,labels)
        self.assertEqual(len(rows),4)
        self.assertTrue(all(r['planned_questions']==2 and r['mean_difference']==1 for r in rows))
        self.assertTrue(all(r['gains']==2 and r['losses']==0 and r['p_exact']==.5 and r['p_holm']==1 for r in rows))
        support=next(r for r in rows if r['metric']=='context_support')
        self.assertEqual(support['sensitivity_excluding_uncertain_labels']['questions'],0)
        self.assertIsNone(support['sensitivity_excluding_uncertain_labels']['estimate'])


if __name__=='__main__': unittest.main()
