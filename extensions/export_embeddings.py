"""Preserve only the exact public-study embedding inputs and cached vectors."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pyarrow as pa
import pyarrow.parquet as pq
from run import MODELS, chunks_for

run = ROOT / 'runs/2026-11-12-rag'
cases = json.loads((run / 'cases.json').read_text())
texts = set()
for case in cases:
    texts.add('search_query: ' + case['question'])
    for size in [2, 3, 6]:
        texts.update('search_document: ' + chunk['text'] for chunk in chunks_for(case, size))
rows=[]
for text in sorted(texts):
    key=hashlib.sha256((MODELS['embedding'][1]+text).encode()).hexdigest()
    path=ROOT/'data/embedding-cache'/(key+'.json')
    vector=json.loads(path.read_text())
    assert len(vector)==768
    rows.append({'key':key,'input_text':text,'vector':vector})
schema=pa.schema([('key',pa.string()),('input_text',pa.string()),('vector',pa.list_(pa.float64(),768))],metadata={b'model_digest':MODELS['embedding'][1].encode(),b'source':b'Actual cached Ollama embeddings used for the frozen public HotpotQA study; no model calls during export.'})
out=ROOT/'embeddings/2026-11-12-nomic.parquet'
pq.write_table(pa.Table.from_pylist(rows,schema=schema),out,compression='zstd')
record={'exported_at_utc':datetime.now(timezone.utc).isoformat(),'vectors':len(rows),'dimensions':768,'source_model_digest':MODELS['embedding'][1],'parquet_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'bytes':out.stat().st_size,'scope':'Exact float64 values loaded from the original JSON cache for all study questions and 2/3/6-sentence chunks. Export time is not the original capture time. Texts are HotpotQA-derived; CC BY-SA 4.0 attribution applies.'}
(ROOT/'embeddings/manifest.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
