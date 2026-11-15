"""Exploratory diagnostics on immutable observations; no new model calls."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import pyarrow.parquet as pq
import run as study
from vendor.hotpot_evaluate_v1 import normalize_answer

RUN=ROOT/'runs/2026-11-12-rag'
OUT=ROOT/'analysis/2026-11-12-rag'


def load_lines(name):
    return [json.loads(line) for line in (RUN/name).read_text().splitlines()]


def main():
    cases={c['id']:c for c in json.loads((RUN/'cases.json').read_text())}
    jobs={j['id']:j for j in json.loads((RUN/'jobs.json').read_text())}
    answers={a['id']:a for a in load_lines('answers.jsonl')}
    metadata=json.loads((ROOT/'embeddings/manifest.json').read_text())
    vectors={}
    for entry in metadata['files']:
        archive=ROOT/entry['path']
        assert hashlib.sha256(archive.read_bytes()).hexdigest()==entry['sha256']
        rows=pq.read_table(archive).to_pylist()
        assert len(rows)==entry['rows']
        for row in rows:
            assert row['key'] not in vectors
            vectors[row['key']]=row
    assert len(vectors)==metadata['vectors']
    def offline_embed(texts,cache):
        result=[]
        for text in texts:
            key=hashlib.sha256((study.MODELS['embedding'][1]+text).encode()).hexdigest()
            row=vectors[key]
            assert row['input_text']==text
            result.append(row['vector'])
        return np.asarray(result,dtype=np.float64)
    study.embed=offline_embed
    def deny_api(*args,**kwargs):
        raise RuntimeError('This analysis never calls a model')
    study.api=deny_api
    original_sensitivity={(s['question_id'],s['retriever'],s['chunk_sentences'],s['top_k']):s for s in json.loads((RUN/'retrieval-sensitivity.json').read_text())}
    sensitivity=[]
    for case in cases.values():
        for size in [2,3,6]:
            chunks=study.chunks_for(case,size)
            for method in ['bm25','dense']:
                ranked=study.rank(chunks,case['question'],method,ROOT/'data/embedding-cache')
                for k in [5,10,20]:
                    chosen=ranked[:k]
                    metrics=study.retrieval_metrics(case,chunks,chosen,chosen)
                    prior=original_sensitivity[(case['id'],method,size,k)]
                    assert abs(metrics['recall10']-prior['passage_recall'])<1e-12
                    sensitivity.append({'question_id':case['id'],'type':case['type'],'chunk_sentences':size,'retriever':method,'top_k':k,'passage_recall':metrics['recall10'],'annotated_sentence_coverage':metrics['evidence_coverage'],'all_annotated_evidence_retrieved':metrics['complete_context']})
    summaries=[]
    for method in ['bm25','dense']:
        for size in [2,3,6]:
            for k in [5,10,20]:
                group=[r for r in sensitivity if (r['retriever'],r['chunk_sentences'],r['top_k'])==(method,size,k)]
                summaries.append({'retriever':method,'chunk_sentences':size,'top_k':k,'questions':len(group),'mean_passage_recall':float(np.mean([r['passage_recall'] for r in group])),'mean_annotated_sentence_coverage':float(np.mean([r['annotated_sentence_coverage'] for r in group])),'complete_retrieved_evidence_count':sum(r['all_annotated_evidence_retrieved'] for r in group)})
    ids=sorted(cases)
    def key(q,method,policy,budget):return f'{q}:{method}:{policy}:{budget}'
    contrasts=[]
    pairs=[(method,'ranked',512,method,'ranked',1536,'budget') for method in ['bm25','dense']]
    pairs += [(method,'ranked',budget,method,'diverse',budget,'packing') for method in ['bm25','dense'] for budget in [512,1536]]
    for lm,lp,lb,rm,rp,rb,kind in pairs:
        transitions=Counter();details=[];evidence_transitions=Counter();abstention_transitions=Counter();same_input_changes=[]
        for q in ids:
            lkey,rkey=key(q,lm,lp,lb),key(q,rm,rp,rb)
            left,right=jobs[lkey],jobs[rkey];la,ra=answers[lkey],answers[rkey]
            lscore,rscore=la['metrics']['answer_em'],ra['metrics']['answer_em']
            transition=f'{lscore}->{rscore}';transitions[transition]+=1
            evidence_transitions[f"{left['complete_context']}->{right['complete_context']}"]+=1
            abstention_transitions[f"{la['metrics']['abstain']}->{ra['metrics']['abstain']}"]+=1
            same_request=la['raw']['request']==ra['raw']['request']
            same_sentences=study.fact_set(left['selected'])==study.fact_set(right['selected'])
            same_answer=(la['answer']['abstain'],normalize_answer(la['answer']['answer']))==(ra['answer']['abstain'],normalize_answer(ra['answer']['answer']))
            if same_request and not same_answer:same_input_changes.append(q)
            details.append({'question_id':q,'type':cases[q]['type'],'exact_match_transition':transition,'evidence_before':left['complete_context'],'evidence_after':right['complete_context'],'identical_request':same_request,'same_selected_sentence_set':same_sentences,'same_normalized_answer':same_answer})
        contrasts.append({'kind':kind,'before':f'{lm}:{lp}:{lb}','after':f'{rm}:{rp}:{rb}','n_questions':64,'exact_match_transitions':dict(transitions),'evidence_transitions':dict(evidence_transitions),'abstention_transitions':dict(abstention_transitions),'identical_request_questions':sum(x['identical_request'] for x in details),'same_sentences_different_request_questions':sum(x['same_selected_sentence_set'] and not x['identical_request'] for x in details),'changed_answers_with_identical_request':same_input_changes,'question_details':details})
    grounding=[]
    for method in ['bm25','dense']:
        for policy in ['ranked','diverse']:
            for budget in [512,1536]:
                selected=[(jobs[key(q,method,policy,budget)],answers[key(q,method,policy,budget)]) for q in ids]
                grounding.append({'retriever':method,'policy':policy,'budget':budget,'exact_match_without_all_annotated_context':sum(a['metrics']['answer_em']==1 and j['complete_context']==0 for j,a in selected),'exact_match_without_all_annotated_citations':sum(a['metrics']['answer_em']==1 and a['metrics']['sp_recall']<1 for j,a in selected),'invalid_citation_answers':sum(a['metrics']['invalid_citations']>0 for j,a in selected),'note':'Diagnostic flags for review, not proof of hallucination: annotations need not list every sufficient source sentence.'})
    # Identify possible question dependence through shared annotated support documents.
    parent={q:q for q in ids}
    def find(q):
        while parent[q]!=q:
            parent[q]=parent[parent[q]];q=parent[q]
        return q
    by_title=defaultdict(list)
    for q,c in cases.items():
        for title in set(c['supporting_facts']['title']):by_title[title].append(q)
    for group in by_title.values():
        for q in group[1:]:parent[find(q)]=find(group[0])
    clusters=defaultdict(list)
    for q in ids:clusters[find(q)].append(q)
    cluster_groups=list(clusters.values());rng=np.random.default_rng(study.SEED)
    cluster_intervals=[]
    for method in ['bm25','dense']:
        delta={q:answers[key(q,method,'ranked',1536)]['metrics']['answer_em']-answers[key(q,method,'ranked',512)]['metrics']['answer_em'] for q in ids}
        draws=[]
        for _ in range(2000):
            sample=[q for i in rng.integers(0,len(cluster_groups),len(cluster_groups)) for q in cluster_groups[int(i)]]
            draws.append(sum(delta[q] for q in sample)/len(sample))
        cluster_intervals.append({'retriever':method,'contrast':'ranked1536 minus ranked512','mean':sum(delta.values())/64,'ci95':list(map(float,np.quantile(draws,[.025,.975]))),'scope':'Post-hoc cluster-bootstrap sensitivity by shared gold-document title; not the preregistered within-type interval.'})
    repeat1={a['id']:a for a in load_lines('answers-repeat-1.jsonl')};repeat2={a['id']:a for a in load_lines('answers-repeat-2.jsonl')}
    repeat_disagreements=[]
    for k in repeat1:
        seq=[answers[k],repeat1[k],repeat2[k]]
        values=[(a['answer']['abstain'],normalize_answer(a['answer']['answer'])) for a in seq]
        if len(set(values))>1:repeat_disagreements.append({'configuration_id':k,'answers':[a['answer'] for a in seq],'exact_match_scores':[a['metrics']['answer_em'] for a in seq],'identical_requests':all(a['raw']['request']==seq[0]['raw']['request'] for a in seq)})
    result={'analysis_utc':datetime.now(timezone.utc).isoformat(),'analysis_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'scope':'Exploratory extensions on the same frozen 64 questions; no independent new sample or new model generation. Original metrics and labels remain unchanged.','sensitivity':summaries,'paired_contrasts':contrasts,'grounding_diagnostics':grounding,'shared_gold_document_clusters':{'count':len(cluster_groups),'largest':max(map(len,cluster_groups)),'non_singleton_clusters':[g for g in cluster_groups if len(g)>1]},'cluster_bootstrap_sensitivity':cluster_intervals,'repeat_disagreements':repeat_disagreements}
    if '--check' in sys.argv:
        saved=json.loads((OUT/'deeper-results.json').read_text())
        for key in ['analysis_utc','analysis_sha256']:
            saved.pop(key)
        computed={key:value for key,value in result.items() if key not in ['analysis_utc','analysis_sha256']}
        assert saved==computed, 'Published deeper aggregates differ from the preserved inputs'
        assert json.loads((OUT/'retrieval-sentence-sensitivity.json').read_text())==sensitivity
        print('Reproduced all 1152 retrieval diagnostics and six paired contrasts without model calls.')
        return
    (OUT/'deeper-results.json').write_text(json.dumps(result,indent=2)+'\n')
    (OUT/'retrieval-sentence-sensitivity.json').write_text(json.dumps(sensitivity,indent=2)+'\n')
    figures(summaries)
    lines=['# Deeper RAG diagnostics','','This is a post-hoc analysis of the same 64 questions. It adds no independent evidence sample and makes no new semantic-accuracy claim. Original scores are unchanged.','','## Distinguish the unit being counted','','Changing chunk length changes which passages exist. Passage recall therefore has a changing denominator across segmentations. The new sensitivity table also counts original supporting sentences and questions retaining every annotated sentence, using the same units across chunk sizes. It concerns retrieval only, before a context budget or answer generation.','','| Search | Sentences per chunk | Top-k | Questions with all annotated evidence |','| --- | ---: | ---: | ---: |']
    for r in summaries:lines.append(f"| {r['retriever']} | {r['chunk_sentences']} | {r['top_k']} | {r['complete_retrieved_evidence_count']}/64 |")
    lines+=['','## Follow the same questions through a change','','Exact matching is a lexical reference test, not independently adjudicated truth. `0 -> 1` and `1 -> 0` retain both gains and losses. Identical requests with changed answers are a null-policy diagnostic; they cannot be credited to a different selection policy.','','| Before | After | 0 -> 1 | 1 -> 0 | Identical requests | Same sentence set, changed request |','| --- | --- | ---: | ---: | ---: | ---: |']
    for c in contrasts:lines.append(f"| {c['before']} | {c['after']} | {c['exact_match_transitions'].get('0->1',0)} | {c['exact_match_transitions'].get('1->0',0)} | {c['identical_request_questions']} | {c['same_sentences_different_request_questions']} |")
    lines+=['','## Check the calibration labels too','','The [review of all four rejected positive controls](analysis/2026-11-12-rag/control-review.json) is explicitly assistant-assisted and provisional, not independent human adjudication. Three cases contain an explicit date, alias, or two-sentence chain that the proxy explanation does not use. One case asks which documentary was more successful without defining success or supplying comparative evidence for the second documentary. It must not be assumed to be a valid positive entailment control. The observed 12/16 supported rate is not a clean estimate of judge sensitivity.','','## Dependence and repeat variability','',f"The {len(cluster_groups)} connected components formed by shared annotated-document titles have a largest component of {max(map(len,cluster_groups))} question(s). Cluster-resampling intervals are an exploratory sensitivity analysis; the preregistered within-type intervals remain reported separately.",'',f"There are {len(repeat_disagreements)} settings with changed normalized answers across the three passes on 16 repeated questions. Their exact requests and outputs remain in `deeper-results.json`; changes must not automatically be interpreted as semantic accuracy changes.",'','Citation flags identify cases to inspect. Missing annotated citations or incomplete annotated context are not by themselves proof of hallucination, because the annotation set need not enumerate every sufficient formulation.','','## What needs new evidence','','A larger, prospectively selected question sample is needed for confirmation beyond this exploratory cohort. Semantic correctness and documentary support need a calibrated evaluation protocol and independent adjudication. No CPU, latency, GPU, cost, or production conclusion follows from these offline calculations.','', 'The cached vectors used in the calculation are now public Parquet data in `embeddings/`, with exact inputs, model digest, hashes, and CC BY-SA 4.0 attribution. Export time is recorded separately from original collection.']
    (ROOT/'DEEPER_ANALYSIS.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'retrieval_conditions':len(summaries),'paired_contrasts':[{k:v for k,v in c.items() if k not in ['question_details','changed_answers_with_identical_request']} for c in contrasts],'shared_clusters':result['shared_gold_document_clusters'],'repeat_disagreements':len(repeat_disagreements)},indent=2))


def figures(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(8.4,4.3),layout='constrained')
    for ax,method in zip(axes,['bm25','dense']):
        values=np.array([[next(r['complete_retrieved_evidence_count'] for r in rows if (r['retriever'],r['chunk_sentences'],r['top_k'])==(method,size,k)) for k in [5,10,20]] for size in [2,3,6]])
        ax.imshow(values,vmin=0,vmax=64,cmap='YlGn',aspect='auto')
        ax.set_title(method.upper(),fontsize=14)
        ax.set_xticks(range(3),[5,10,20]);ax.set_xlabel('Retrieved chunks (top-k)',fontsize=11)
        ax.set_yticks(range(3),[2,3,6]);ax.set_ylabel('Sentences per chunk',fontsize=11)
        for i in range(3):
            for j in range(3):ax.text(j,i,f'{values[i,j]}/64',ha='center',va='center',fontsize=13,color='white' if values[i,j]>=40 else '#17283a')
    fig.suptitle('Questions with all annotated evidence retrieved',fontsize=14)
    for ext in ['png','svg']:
        path=OUT/f'retrieval-sentence-sensitivity-en.{ext}';fig.savefig(path,dpi=180,bbox_inches='tight',facecolor='white')
        if ext=='svg':path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    plt.close(fig)


if __name__=='__main__':main()
