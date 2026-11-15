"""Recheck the complete stored study without contacting a model server."""
import gzip
import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import math
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
from tokenizers import Tokenizer

import run as original
from v2.benchmark import (COHORTS, REGISTRATION, archived_vectors, file_sha, lines,
                          payload_for, read, run_path, check_inputs, require_pilot)
from v2.core import (answer_metrics, chunks, context_metrics, digest, documents,
                     ranking, select_cohorts)
from v2.checks import ReferenceBM25, reference_cosine, reference_pack


def checked_answer(response):
    if response.get('model') != original.MODELS['generator'][0]:
        raise ValueError('Unexpected recorded response model')
    if not response.get('done') or response.get('done_reason') != 'stop':
        raise ValueError('Generation did not finish normally')
    if response['prompt_eval_count'] + original.OPTIONS['num_predict'] > original.OPTIONS['num_ctx']:
        raise ValueError('Possible context truncation')
    answer = original.parse_answer({'response':response})
    if set(answer) != {'answer','citations','abstain'} or (answer['abstain'] and (answer['answer'] or answer['citations'])):
        raise ValueError('Output violates the registered response instructions')
    return answer


def verify_answers(out, jobs, cases, expected, repeat=0):
    path = out / (f"answers-repeat-{repeat}.jsonl" if repeat else "answers.jsonl")
    records = lines(path)
    if len(records) != len(expected) or {r["id"] for r in records} != expected:
        raise ValueError(f"Incomplete/duplicate recorded generations: {path}")
    intent_path = out / (f"intents-repeat-{repeat}.jsonl" if repeat else "intents.jsonl")
    intents = lines(intent_path)
    if len(intents) != len(expected) or {item["id"] for item in intents} != expected:
        raise ValueError("Missing or duplicate request intents")
    for intent in intents:
        expected_request = payload_for(jobs[intent["id"]])
        if intent["request"] != expected_request or intent["request_sha256"] != digest(expected_request):
            raise ValueError("A request intent differs from the actual prepared request")
    errors = 0
    failures_reconstructed = 0
    for record in records:
        job = jobs[record["id"]]
        if record.get("request") is not None:
            if record["request"] != payload_for(job) or record["request_sha256"] != digest(payload_for(job)):
                raise ValueError("Archived request differs from the prepared context")
        if "response_body" not in record:
            if not record.get('error'): raise ValueError('Neither response nor recorded failure')
            errors += 1
            continue  # Unobserved transport/interruption outcome is retained, not regenerated.
        response = json.loads(record["response_body"])
        if record['response'] != response: raise ValueError('Stored response differs from its exact raw body')
        try:
            answer = checked_answer(response)
        except (ValueError, KeyError, TypeError) as error:
            if record.get('error') != f'{type(error).__name__}: {error}':
                raise ValueError('Recorded output failure is not reproduced from its raw response') from error
            errors += 1
            failures_reconstructed += 1
            if 'metrics' in record or 'answer' in record: raise ValueError('A failed output carries successful scores')
            continue
        if 'error' in record: raise ValueError('A recorded failure has no reproduced output violation')
        if record["answer"] != answer:
            raise ValueError("Stored parsed generation differs from its raw response body")
        if answer_metrics(cases[job["question_id"]], job, answer) != record["metrics"]:
            raise ValueError("Stored lexical/citation score differs")
    return {"observations": len(records), "errors": errors,
            'failures_reconstructed_from_raw_response':failures_reconstructed,
            'failures_without_observed_response':errors-failures_reconstructed}


def verify_statistics():
    from v2 import analysis
    from v2 import diagnostics
    observed = []

    def compare(left, right):
        if isinstance(left, dict):
            if left.keys() != right.keys(): raise ValueError("Aggregate result keys differ")
            for key in left: compare(left[key], right[key])
        elif isinstance(left, list):
            if len(left) != len(right): raise ValueError("Aggregate result lengths differ")
            for a, b in zip(left, right, strict=True): compare(a, b)
        elif isinstance(left, (float, int)) and not isinstance(left, bool):
            if not math.isclose(left, right, rel_tol=0, abs_tol=1e-12):
                raise ValueError("Aggregate estimate, interval, or p-value differs")
        elif left != right:
            raise ValueError("Aggregate result differs")

    saved_path, saved_report, saved_figures = analysis.run_path, analysis.report, analysis.figures
    try:
        analysis.report = lambda *_: None
        analysis.figures = lambda *_: None
        for environment in ("controlled", "pooled"):
            source = saved_path("confirmatory", environment)
            expected = read(source / "results.json")
            with tempfile.TemporaryDirectory() as temp:
                destination = Path(temp)
                for name in ("jobs.json", "preparation.json", "answers.jsonl", "answers-repeat-1.jsonl", "answers-repeat-2.jsonl"):
                    if (source / name).exists():
                        (destination / name).symlink_to(source / name)
                analysis.run_path = lambda *_, path=destination: path
                analysis.analyse(environment)
                compare(expected, read(destination / "results.json"))
                original_path = diagnostics.run_path
                original_relationship, original_effects = diagnostics.plot_relationship, diagnostics.plot_effects
                try:
                    diagnostics.run_path = lambda split, env: destination if env == environment else destination / 'absent'
                    diagnostics.plot_relationship = lambda *_: None
                    diagnostics.plot_effects = lambda *_: None
                    diagnostics.main()
                    compare(read(source/'diagnostics.json'),read(destination/'diagnostics.json'))
                finally:
                    diagnostics.run_path = original_path
                    diagnostics.plot_relationship, diagnostics.plot_effects = original_relationship, original_effects
            observed.append({"environment": environment, "estimates_intervals_pvalues_reproduced": True,
                             "numeric_tolerance": 1e-12, 'diagnostic_tables_reproduced':True})
    finally:
        analysis.run_path, analysis.report, analysis.figures = saved_path, saved_report, saved_figures
    from v2 import report
    saved_root = report.ROOT
    try:
        with tempfile.TemporaryDirectory() as temp:
            report.ROOT=Path(temp)
            (report.ROOT/'v2').symlink_to(ROOT/'v2',target_is_directory=True)
            report.main()
            if (report.ROOT/'RESULTS.md').read_bytes() != (ROOT/'RESULTS.md').read_bytes():
                raise ValueError('The published study is not reproduced from its recorded numerical tables')
    finally: report.ROOT=saved_root
    return observed


def verify(output=None):
    import pyarrow.parquet as pq
    from v2.archive import restore
    restore()
    check_inputs()
    cohorts = read(COHORTS)
    historical = read(ROOT / "runs/2026-11-12-rag/cases.json")
    rows = pq.read_table(ROOT / "data/hotpot-validation.parquet").to_pylist()
    recomputed = select_cohorts(rows, historical)
    for key in recomputed:
        if recomputed[key] != cohorts[key]: raise ValueError(f"Frozen cohort differs: {key}")
    registration = read(REGISTRATION)
    if file_sha(ROOT/'sources.json') != registration['sources_sha256'] or file_sha(ROOT/'run.py') != registration['original_generator_source_sha256']:
        raise ValueError('Recorded scientific inputs or original generator changed')
    if file_sha(ROOT/'vendor/hotpot_evaluate_v1.py') != read(ROOT/'sources.json')['evaluator']['sha256']:
        raise ValueError('Official lexical evaluator identity changed')
    for name, expected in registration["files"].items():
        if file_sha(ROOT / name) != expected: raise ValueError(f"Frozen source changed: {name}")
    tokenizer = Tokenizer.from_file(str(ROOT / "data/qwen-tokenizer.json"))
    vectors = archived_vectors()
    for path in sorted((ROOT / "v2/runs/embedding-traces").glob("*.json.gz")):
        packet = json.loads(gzip.decompress(path.read_bytes()))
        if packet["model_digest"] != original.MODELS["embedding"][1]: raise ValueError("Different embedding model")
        response = json.loads(packet["response_body"])
        expected_request = {'model':original.MODELS['embedding'][0], 'input':packet['request']['input'],
                            'truncate':False,'keep_alive':'30m','options':{'num_thread':8}}
        if packet['request'] != expected_request: raise ValueError('Embedding request parameters differ')
        for text, vector in zip(packet["request"]["input"], response["embeddings"], strict=True):
            if len(vector) != 768 or not np.all(np.isfinite(vector)):
                raise ValueError("Invalid preserved embedding")
            if text in vectors and not np.allclose(vectors[text],vector,rtol=0,atol=1e-12):
                raise ValueError('Different preserved vectors for the same input text')
            vectors[text] = vector
    total_contexts = 0
    total_answers = 0
    report = []
    for split, environment in [("pilot", "controlled"), ("confirmatory", "controlled"), ("confirmatory", "pooled")]:
        out = run_path(split, environment)
        preparation = read(out / "preparation.json")
        if file_sha(out / "jobs.json") != preparation["jobs_sha256"]:
            raise ValueError("Prepared job file changed")
        if preparation["registration_sha256"] != file_sha(REGISTRATION):
            raise ValueError("Registration identity differs")
        cases = {c["id"]: c for c in cohorts[split]}
        stored = read(out / "jobs.json")
        jobs = {j["id"]: j for j in stored}
        if len(jobs) != len(cases) * 8 or len(jobs) != len(stored):
            raise ValueError("Missing/duplicate deterministic contexts")
        corpus = {doc["key"]: doc for case in cases.values() for doc in documents(case)}
        if len(corpus) != preparation['corpus_paragraphs'] or digest([corpus[key] for key in sorted(corpus)]) != preparation['corpus_sha256']:
            raise ValueError('Shared source corpus identity differs')
        shared = chunks([corpus[key] for key in sorted(corpus)]) if environment == "pooled" else None
        shared_bm25 = ReferenceBM25(shared) if shared is not None else None
        recorded_rankings = {(r['question_id'],r['retriever']):r for r in preparation['retrieval']}
        for case in cases.values():
            candidates = shared if shared is not None else chunks(documents(case))
            independent_bm25 = shared_bm25 if shared_bm25 is not None else ReferenceBM25(candidates)
            for method in ("bm25", "dense"):
                ranked = ranking(candidates, case["question"], method, vectors)
                scores = independent_bm25.scores(case['question']) if method == 'bm25' else reference_cosine(candidates,case['question'],vectors)
                expected_order = sorted(range(len(candidates)),key=lambda i:(-float(scores[i]),candidates[i]['id']))
                independent_order = [candidates[i]['id'] for i in expected_order]
                if [c['id'] for c in ranked] != independent_order or any(abs(float(scores[i])-c['score']) > 1e-10 for i,c in zip(expected_order,ranked,strict=True)):
                    raise ValueError('Independent BM25/cosine calculation differs')
                trace = recorded_rankings[case['id'],method]
                if trace['indexed_chunks'] != len(candidates) or trace['ranked_ids_sha256'] != digest(independent_order):
                    raise ValueError('Complete recorded ranking identity differs')
                for policy in ("ranked", "diverse"):
                    for budget in (512, 1536):
                        job = jobs[f"{case['id']}:{method}:{policy}:{budget}"]
                        if job["question"] != case["question"] or job["type"] != case["type"]:
                            raise ValueError("Question text/type changed")
                        if [c["id"] for c in job["retrieved"]] != [c["id"] for c in ranked[:10]]:
                            raise ValueError("Retrieved ranking differs")
                        if any({k: v for k, v in a.items() if k != "score"} != {k: v for k, v in b.items() if k != "score"} for a, b in zip(job["retrieved"], ranked[:10], strict=True)):
                            raise ValueError("A retrieved passage differs from its original source")
                        if any(abs(c["score"] - d["score"]) > 1e-10 for c, d in zip(job["retrieved"], ranked[:10], strict=True)):
                            raise ValueError("Retrieved score differs")
                        selected = original.pack(ranked[:10], budget, policy, tokenizer)
                        if [c['id'] for c in selected] != reference_pack(ranked[:10],budget,policy,tokenizer):
                            raise ValueError('Independent token packing differs')
                        if [c["id"] for c in selected] != [c["id"] for c in job["selected"]]:
                            raise ValueError("Context selection differs")
                        if any({k: v for k, v in a.items() if k != "score"} != {k: v for k, v in b.items() if k != "score"} for a, b in zip(job["selected"], selected, strict=True)):
                            raise ValueError("A selected passage differs from its original source")
                        metrics = context_metrics(case, candidates, ranked, selected, tokenizer, budget)
                        if any(job[key] != value for key, value in metrics.items()):
                            raise ValueError("Context text, token count, or evidence measurement differs")
                        total_contexts += 1
        record = {"split": split, "environment": environment, "contexts": len(jobs)}
        if split == "pilot":
            expected = set(jobs)
            record["generation"] = verify_answers(out, jobs, cases, expected)
            calibration = read(out / "tokenizer-calibration.json")
            if len(calibration) != 3 or any(item["tokenizer_tokens"] != item["ollama_tokens"] for item in calibration):
                raise ValueError("Tokenizer calibration differs")
            probes = ['Hello world.','Thirty seconds, then one retry after two seconds.','[d00s002] Paris is in France.']
            for item,text in zip(calibration,probes,strict=True):
                expected_request = {'model':original.MODELS['generator'][0],'prompt':text,'raw':True,
                                    'stream':False,'think':False,'options':{**original.OPTIONS,'num_predict':1}}
                response = json.loads(item['response_body'])
                if item['request'] != expected_request or item['ollama_tokens'] != response['prompt_eval_count'] or item['tokenizer_tokens'] != len(tokenizer.encode(text).ids):
                    raise ValueError('Calibration counts are not reproduced from actual probes and responses')
            if not read(out / "qualification.json")["passed"]:
                raise ValueError("Pilot was not qualified")
            require_pilot()
        elif environment == "controlled":
            expected = {j["id"] for j in stored if j["question_id"] in cohorts["generation_ids"]}
            record["generation"] = verify_answers(out, jobs, cases, expected)
            expected_repeats = {f"{q}:bm25:ranked:512" for q in cohorts["stability_ids"]}
            record["repeats"] = [verify_answers(out, jobs, cases, expected_repeats, repeat) for repeat in (1, 2)]
            total_answers += sum(r["observations"] for r in record["repeats"])
        if "generation" in record: total_answers += record["generation"]["observations"]
        report.append(record)
        print(f"Verified {split}/{environment}: {len(jobs)} contexts", flush=True)
    statistics = verify_statistics()
    value = {"contexts_verified": total_contexts, "generation_observations_verified": total_answers,
             "model_calls_during_verification": 0, "groups": report,
             "statistical_replay": statistics,
             'independent_references':'All recorded full BM25/cosine rankings and token-packing selections recomputed independently.',
             "environment": {"system": platform.system(), "machine": platform.machine(),
                             "dependencies": {name: importlib.metadata.version(name) for name in ("numpy", "pyarrow", "tokenizers", "ujson")}},
             "semantic_scope": "Reproduced retrieval, selected text, tokenization, requests, parsing, and lexical/citation calculations. This is not a judgement of factual correctness."}
    (output or ROOT / "v2/verification.json").write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps(value, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    verify(parser.parse_args().output)
