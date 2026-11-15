"""Independent numerical references for archived ranking and packing checks."""
from collections import Counter
import math
import re
import numpy as np


class ReferenceBM25:
    def __init__(self, candidates):
        self.bags = [Counter(re.findall(r'\w+', c['text'].lower())) for c in candidates]
        self.lengths = [sum(bag.values()) for bag in self.bags]
        self.mean_length = sum(self.lengths) / len(self.lengths)
        self.frequency = Counter(term for bag in self.bags for term in bag)

    def scores(self, question):
        result = []
        terms = sorted(set(re.findall(r'\w+', question.lower())))
        for bag,length in zip(self.bags,self.lengths,strict=True):
            score = 0.
            for term in terms:
                if term not in bag: continue
                probability = (len(self.bags) - self.frequency[term] + .5) / (self.frequency[term] + .5)
                normalization = 1.5 * (1 - .75 + .75 * length / self.mean_length)
                score += math.log1p(probability) * 2.5 * bag[term] / (bag[term] + normalization)
            result.append(score)
        return np.asarray(result)


def reference_cosine(candidates, question, vectors):
    matrix=np.array([vectors['search_document: '+c['text']] for c in candidates],dtype=np.float64)
    query=np.array(vectors['search_query: '+question],dtype=np.float64)
    numerator=np.sum(matrix * query,axis=1)
    denominator=np.sqrt(np.sum(matrix * matrix,axis=1) * np.sum(query * query))
    if not np.all(np.isfinite(numerator)) or np.any(denominator <= 0):
        raise ValueError('Invalid independent cosine inputs')
    return numerator / denominator


def reference_pack(candidates, budget, policy, tokenizer):
    if policy == 'ranked': ordered=list(candidates)
    elif policy == 'diverse':
        queues={}
        for item in candidates: queues.setdefault(item['title'],[]).append(item)
        ordered=[]
        while any(queues.values()):
            for queue in queues.values():
                if queue: ordered.append(queue.pop(0))
    else: raise ValueError('Unknown packing policy')
    chosen=[]
    rendered=[]
    for item in ordered:
        block=f"[{item['id']}] {item['title']}\n"+'\n'.join(f"[{f['id']}] {f['text']}" for f in item['facts'])
        if len(tokenizer.encode('\n\n'.join(rendered+[block])).ids) <= budget:
            chosen.append(item['id'])
            rendered.append(block)
    return chosen
