"""Frozen prospective cohort, local execution, and append-only raw records."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pyarrow.parquet as pq
from tokenizers import Tokenizer

import run as original
from v2.core import (BUDGETS, METHODS, POLICIES, SEED, answer_metrics, chunks,
                     context_metrics, digest, documents, power_planning, ranking,
                     select_cohorts)

BASE = ROOT / "v2"
COHORTS = BASE / "data/cohorts.json"
REGISTRATION = BASE / "registration.json"


def utc():
    return datetime.now(timezone.utc).isoformat()


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.write("\n")


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def append(path, value):
    with path.open("a") as output:
        output.write(json.dumps(value, ensure_ascii=False) + "\n")
        output.flush()
        os.fsync(output.fileno())


def check_inputs():
    sources = read(ROOT / "sources.json")
    for key, name in [("dataset", "hotpot-validation.parquet"), ("tokenizer", "qwen-tokenizer.json")]:
        if file_sha(ROOT / "data" / name) != sources[key]["sha256"]:
            raise ValueError(f"Pinned {key} differs")


def freeze_cohorts():
    check_inputs()
    rows = pq.read_table(ROOT / "data/hotpot-validation.parquet").to_pylist()
    historical = read(ROOT / "runs/2026-11-12-rag/cases.json")
    result = select_cohorts(rows, historical)
    result.update({"selected_utc": utc(), "dataset_sha256": file_sha(ROOT / "data/hotpot-validation.parquet"),
                   "historical_cases_sha256": file_sha(ROOT / "runs/2026-11-12-rag/cases.json")})
    write_new(COHORTS, result)
    write_new(BASE / "data/power-planning.json", {"method": "Normal approximation for a paired binary difference with specified discordance; conservative alpha=.01. Planning assumptions, not observed power.", "scenarios": power_planning()})
    print("Frozen 8 pilot questions, 256 deterministic questions, 128 generation IDs, and 16 stability IDs.")


def register():
    check_inputs()
    paths = [*BASE.glob("*.py"), BASE / "PROTOCOL.md", COHORTS, BASE / "data/power-planning.json"]
    value = {"registered_utc": utc(), "historical_commit": "066be354481550e73d7c8336a8f4768328fe19a3",
             "files": {str(p.relative_to(ROOT)): file_sha(p) for p in sorted(paths)},
             "sources_sha256": file_sha(ROOT / "sources.json"),
             "original_generator_source_sha256": file_sha(ROOT / "run.py"),
             "models": original.MODELS, "generation_options": original.OPTIONS,
             "source_provenance": "Commit this registration and all frozen files to the dedicated public branch before any V2 outcome collection. Dates are actual registration dates."}
    write_new(REGISTRATION, value)
    print("Registration created. Commit and publish it before running prepare or generate.")


def registered():
    check_inputs()
    registration = read(REGISTRATION)
    for name, expected in registration["files"].items():
        if file_sha(ROOT / name) != expected:
            raise ValueError(f"Frozen file changed: {name}; an explicit amendment is required")
    if file_sha(ROOT / "run.py") != registration["original_generator_source_sha256"]:
        raise ValueError("Historical generator source changed")
    committed = subprocess.check_output(["git", "show", "HEAD:v2/registration.json"], cwd=ROOT)
    if committed != REGISTRATION.read_bytes():
        raise ValueError("Registration must be committed before outcomes are collected")
    return registration


def request(endpoint, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(original.BASE + endpoint, data=data,
                                 headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=180) as response:
        body = response.read().decode()
    return json.loads(body), body, time.perf_counter() - started


def model_check():
    installed = {m["name"]: m for m in request("tags")[0]["models"]}
    for role in ("generator", "embedding"):
        name, expected = original.MODELS[role]
        if installed.get(name, {}).get("digest") != expected:
            raise ValueError(f"Pinned {role} is not installed")
    return {"utc": utc(), "ollama": request("version")[0], "models": original.MODELS,
            "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "registration_sha256": file_sha(REGISTRATION), "python": sys.version,
            "system": platform.system(), "architecture": platform.machine(),
            "logical_cpus": os.cpu_count(), "load_average": list(os.getloadavg()),
            "dependencies": {name: importlib.metadata.version(name) for name in ("numpy", "pyarrow", "tokenizers", "ujson")},
            "scope": "Quality study; host records do not qualify latency, throughput, cost, or hardware independence."}


def archived_vectors():
    manifest = read(ROOT / "embeddings/manifest.json")
    vectors = {}
    for item in manifest["files"]:
        path = ROOT / item["path"]
        if file_sha(path) != item["sha256"]:
            raise ValueError("Historical embedding archive changed")
        for row in pq.read_table(path).to_pylist():
            vectors[row["input_text"]] = row["vector"]
    return vectors


def embeddings_for(texts, directory):
    vectors = archived_vectors()
    directory.mkdir(parents=True, exist_ok=True)
    packets = sorted(directory.glob("batch-*.json.gz"))
    for path in packets:
        packet = json.loads(gzip.decompress(path.read_bytes()))
        response = json.loads(packet["response_body"])
        for text, vector in zip(packet["request"]["input"], response["embeddings"], strict=True):
            vectors[text] = vector
    pending = sorted(set(texts) - vectors.keys())
    for start in range(0, len(pending), 16):
        batch = pending[start:start + 16]
        payload = {"model": original.MODELS["embedding"][0], "input": batch,
                   "truncate": False, "keep_alive": "30m", "options": {"num_thread": 8}}
        response, raw, elapsed = request("embed", payload)
        values = response["embeddings"]
        if len(values) != len(batch) or any(len(v) != 768 or not np.all(np.isfinite(v)) or np.linalg.norm(v) <= 0 for v in values):
            raise ValueError("Invalid embedding response")
        packet = {"utc": utc(), "model_digest": original.MODELS["embedding"][1],
                  "request": payload, "response_body": raw, "wall_seconds": elapsed}
        path = directory / f"batch-{len(packets):05}.json.gz"
        with path.open("xb") as output:
            output.write(gzip.compress(json.dumps(packet, ensure_ascii=False).encode(), mtime=0))
        packets.append(path)
        vectors.update(zip(batch, values, strict=True))
        print(f"Embedded {min(start + 16, len(pending))}/{len(pending)} new inputs", flush=True)
    return vectors


def run_path(split, environment):
    return BASE / "runs" / f"{split}-{environment}"


def require_pilot():
    out = run_path("pilot", "controlled")
    certificate = read(out / "qualification.json")
    if not certificate["passed"] or certificate["registration_sha256"] != file_sha(REGISTRATION):
        raise ValueError("Pilot is not qualified for this registration")
    if any(certificate[f"{name}_sha256"] != file_sha(out / filename) for name, filename in [("jobs", "jobs.json"), ("answers", "answers.jsonl")]):
        raise ValueError("Pilot evidence changed after qualification")


def prepare(split, environment):
    registered()
    if split == "confirmatory":
        require_pilot()
    if split == "pilot" and environment != "controlled":
        raise ValueError("The technical pilot uses only the controlled corpus")
    out = run_path(split, environment)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "jobs.json").exists():
        raise ValueError("Prepared jobs are immutable; reuse them without overwriting")
    execution = model_check()
    cohort = read(COHORTS)
    cases = cohort[split]
    tokenizer = Tokenizer.from_file(str(ROOT / "data/qwen-tokenizer.json"))
    if split == "pilot":
        calibration = []
        for text in ("Hello world.", "Thirty seconds, then one retry after two seconds.", "[d00s002] Paris is in France."):
            payload = {"model": original.MODELS["generator"][0], "prompt": text, "raw": True,
                       "stream": False, "think": False,
                       "options": {**original.OPTIONS, "num_predict": 1}}
            response, body, elapsed = request("generate", payload)
            expected = len(tokenizer.encode(text).ids)
            calibration.append({"request": payload, "response_body": body, "wall_seconds": elapsed,
                                "tokenizer_tokens": expected, "ollama_tokens": response["prompt_eval_count"]})
        write_new(out / "tokenizer-calibration.json", calibration)
        if any(item["tokenizer_tokens"] != item["ollama_tokens"] for item in calibration):
            raise ValueError("Tokenizer calibration failed; confirmation must not start")
    corpus = {}
    for case in cases:
        for doc in documents(case):
            corpus[doc["key"]] = doc
    shared = chunks([corpus[key] for key in sorted(corpus)]) if environment == "pooled" else None
    all_chunks = {case["id"]: shared if shared is not None else chunks(documents(case)) for case in cases}
    texts = {"search_query: " + c["question"] for c in cases}
    for group in ([shared] if shared is not None else all_chunks.values()):
        texts.update("search_document: " + chunk["text"] for chunk in group)
    vectors = embeddings_for(texts, BASE / "runs/embedding-traces")
    jobs = []
    retrieval = []
    for case in cases:
        candidates = all_chunks[case["id"]]
        for method in METHODS:
            ranked = ranking(candidates, case["question"], method, vectors)
            for policy in POLICIES:
                for budget in BUDGETS:
                    selected = original.pack(ranked[:10], budget, policy, tokenizer)
                    metrics = context_metrics(case, candidates, ranked, selected, tokenizer, budget)
                    job = {"id": f"{case['id']}:{method}:{policy}:{budget}", "question_id": case["id"],
                           "question": case["question"], "type": case["type"], "retriever": method,
                           "policy": policy, "budget": budget, "environment": environment, "split": split,
                           "selected": selected, "retrieved": ranked[:10], **metrics}
                    jobs.append(job)
            retrieval.append({"question_id": case["id"], "retriever": method, "indexed_chunks": len(candidates),
                              "ranked_ids_sha256": digest([c["id"] for c in ranked])})
        print(f"Prepared {case['id']} ({environment})", flush=True)
    random.Random(SEED + 5).shuffle(jobs)
    write_new(out / "jobs.json", jobs)
    write_new(out / "preparation.json", {**execution, "split": split, "environment": environment,
               "questions": len(cases), "jobs": len(jobs), "jobs_sha256": file_sha(out / "jobs.json"),
               "corpus_paragraphs": len(corpus), "corpus_sha256": digest([corpus[key] for key in sorted(corpus)]),
               "retrieval": retrieval, "pooled_scope": "Union of this cohort's supplied public paragraphs, deduplicated by title and full sentence array. Support documents are present by construction; not open-Wikipedia retrieval." if shared is not None else None})


def payload_for(job):
    return {"model": original.MODELS["generator"][0],
            "messages": [{"role": "system", "content": original.SYSTEM},
                         {"role": "user", "content": f"Question: {job['question']}\n\nEvidence:\n{job['context']}"}],
            "format": original.ANSWER_SCHEMA, "stream": False, "keep_alive": "30m",
            "options": original.OPTIONS, "think": False}


def generate(split, repeat=0):
    registered()
    if split == "confirmatory":
        require_pilot()
    if repeat and split != "confirmatory":
        raise ValueError("Repeated generations are separately registered on the confirmatory subset")
    out = run_path(split, "controlled")
    preparation = read(out / "preparation.json")
    if preparation["jobs_sha256"] != file_sha(out / "jobs.json"):
        raise ValueError("Prepared inputs changed")
    execution = model_check()
    stamp = out / f"execution-{repeat}-{time.time_ns()}.json"
    write_new(stamp, execution)
    cohort = read(COHORTS)
    cases = {c["id"]: c for c in cohort[split]}
    jobs = read(out / "jobs.json")
    if split == "confirmatory":
        ids = set(cohort["stability_ids"] if repeat else cohort["generation_ids"])
        jobs = [j for j in jobs if j["question_id"] in ids and (not repeat or (j["retriever"], j["policy"], j["budget"]) == ("bm25", "ranked", 512))]
    destination = out / (f"answers-repeat-{repeat}.jsonl" if repeat else "answers.jsonl")
    intents = out / (f"intents-repeat-{repeat}.jsonl" if repeat else "intents.jsonl")
    observed = lines(destination)
    done = {item["id"] for item in observed}
    if len(done) != len(observed):
        raise ValueError("Duplicate generation record")
    for item in lines(intents):
        if item["id"] not in done:
            append(destination, {"id": item["id"], "utc": utc(), "error": "Interrupted after request intent; response unobserved. Not regenerated.", "request_sha256": item["request_sha256"]})
            done.add(item["id"])
    errors = 0
    for job in jobs:
        if job["id"] in done:
            continue
        payload = payload_for(job)
        append(intents, {"id": job["id"], "utc": utc(), "request_sha256": digest(payload), "request": payload})
        result = {"id": job["id"], "utc": utc(), "request": payload, "request_sha256": digest(payload)}
        try:
            response, body, elapsed = request("chat", payload)
            result.update({"response_body": body, "response": response, "wall_seconds": elapsed})
            if not response.get("done") or response.get("done_reason") != "stop":
                raise ValueError("Generation did not finish normally")
            if response["prompt_eval_count"] + original.OPTIONS["num_predict"] > original.OPTIONS["num_ctx"]:
                raise ValueError("Possible context truncation")
            answer = original.parse_answer({"response": response})
            if set(answer) != {"answer", "citations", "abstain"} or (answer["abstain"] and (answer["answer"] or answer["citations"])):
                raise ValueError("Output violates the registered response instructions")
            result.update({"answer": answer, "metrics": answer_metrics(cases[job["question_id"]], job, answer)})
            errors = 0
        except Exception as error:
            result["error"] = f"{type(error).__name__}: {error}"
            errors += 1
        append(destination, result)
        done.add(job["id"])
        print(f"Generated {len(done)}/{len(jobs)} ({split}, repeat={repeat}); error={'error' in result}", flush=True)
        if errors >= 3:
            raise RuntimeError("Three consecutive failures; raw observations preserved")


def qualify():
    registered()
    out = run_path("pilot", "controlled")
    jobs = read(out / "jobs.json")
    calibration = read(out / "tokenizer-calibration.json")
    answers = lines(out / "answers.jsonl")
    by_id = {item["id"]: item for item in answers}
    passed = (len(jobs) == len(answers) == len(by_id) == 64 and
              set(by_id) == {j["id"] for j in jobs} and not any("error" in item for item in answers) and
              len(calibration) == 3 and all(c["tokenizer_tokens"] == c["ollama_tokens"] for c in calibration))
    for job in jobs:
        if job["id"] in by_id and by_id[job["id"]].get("request") != payload_for(job):
            passed = False
    write_new(out / "qualification.json", {"utc": utc(), "passed": passed,
              "questions": 8, "configurations": len(answers), "errors": sum("error" in a for a in answers),
              "registration_sha256": file_sha(REGISTRATION),
              "jobs_sha256": file_sha(out / "jobs.json"), "answers_sha256": file_sha(out / "answers.jsonl"),
              "criterion": "All 64 planned requests archived once, untruncated, instruction-consistent JSON, with exact prepared requests; no answer-quality or exact-match threshold."})
    if not passed:
        raise RuntimeError("Pilot failed. Do not start confirmation; record a prospective amendment and a new disjoint pilot.")
    print("Pilot qualified on technical criteria only; no semantic conclusion follows.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["cohorts", "register", "prepare", "generate", "qualify"])
    parser.add_argument("--split", choices=["pilot", "confirmatory"], default="pilot")
    parser.add_argument("--environment", choices=["controlled", "pooled"], default="controlled")
    parser.add_argument("--repeat", type=int, choices=[0, 1, 2], default=0)
    args = parser.parse_args()
    if args.stage == "cohorts": freeze_cohorts()
    elif args.stage == "register": register()
    elif args.stage == "prepare": prepare(args.split, args.environment)
    elif args.stage == "generate": generate(args.split, args.repeat)
    else: qualify()


if __name__ == "__main__":
    main()
