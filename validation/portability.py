"""Audit fixed evidence and packing under a second operating-system environment."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import audit
import run as experiment
from run import chunks_for, rank

def offline_api(*args, **kwargs):
    raise RuntimeError("Portability audit requires the preserved embedding cache; it never calls a model")

experiment.api = offline_api

cases, jobs, answers, rows = audit()
reranked = 0
for case in cases.values():
    for method in ['bm25', 'dense']:
        candidates = rank(chunks_for(case), case['question'], method, ROOT / 'data/embedding-cache')[:10]
        saved = next(job['retrieved'] for job in jobs.values()
                     if job['question_id'] == case['id'] and job['retriever'] == method)
        assert [c['id'] for c in candidates] == [c['id'] for c in saved]
        assert all(abs(c['score']-d['score']) < 1e-10 for c,d in zip(candidates,saved))
        reranked += 1
canonical = json.dumps(sorted(rows, key=lambda row: row['id']), sort_keys=True, separators=(',', ':')).encode()
print(json.dumps({'utc':datetime.now(timezone.utc).isoformat(), 'system':platform.system(),
                 'machine':platform.machine(), 'python':sys.version,
                 'validator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 'dependencies':{name:importlib.metadata.version(name) for name in ['numpy','pyarrow','tokenizers','ujson']},
                 'audited_questions':len(cases), 'audited_primary_generations':len(answers),
                 'recomputed_rankings':reranked, 'canonical_question_metrics_sha256':hashlib.sha256(canonical).hexdigest(),
                 'scope':'Recomputes rankings from cached embedding vectors, context selection, budgets, prompts, and official scoring. Does not rerun embedding or answer generation and does not benchmark speed.'},indent=2))
