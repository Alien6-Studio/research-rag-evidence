"""Require archived question-level measurements to survive maintenance updates."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import audit

cases, jobs, answers, rows = audit()
canonical = json.dumps(sorted(rows, key=lambda row: row['id']), sort_keys=True, separators=(',', ':')).encode()
observed = hashlib.sha256(canonical).hexdigest()
expected = json.loads((ROOT / 'evidence/portability-native.json').read_text())['canonical_question_metrics_sha256']
assert observed == expected, 'Archived question-level measurements changed'
print(f'Audited {len(cases)} questions and {len(answers)} primary responses: {observed}')
