"""Known mathematical references, rather than only calls back into the collector."""
import math
import unittest
from v2.checks import ReferenceBM25, reference_cosine


class IndependentChecks(unittest.TestCase):
    def test_bm25_has_known_length_normalization_and_uses_unique_query_terms(self):
        candidates=[{'text':s} for s in ['alpha alpha beta','beta gamma','gamma gamma']]
        index=ReferenceBM25(candidates)
        self.assertAlmostEqual(index.scores('alpha')[0],math.log(8/3)*140/107,places=14)
        self.assertEqual(list(index.scores('alpha alpha')),list(index.scores('alpha')))
        self.assertEqual(index.scores('unknown').tolist(),[0,0,0])

    def test_cosine_is_scale_invariant_with_negative_and_orthogonal_controls(self):
        candidates=[{'text':s} for s in ['positive','orthogonal','negative']]
        vectors={'search_query: q':[2,0],'search_document: positive':[7,0],
                 'search_document: orthogonal':[0,1],'search_document: negative':[-3,0]}
        self.assertEqual(reference_cosine(candidates,'q',vectors).tolist(),[1,0,-1])
