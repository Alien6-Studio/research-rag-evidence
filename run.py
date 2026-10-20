"""Controlled HotpotQA distractor study; see PROTOCOL.md."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

import numpy as np
import pyarrow.parquet as pq
from tokenizers import Tokenizer

from vendor.hotpot_evaluate_v1 import exact_match_score, f1_score, update_sp

ROOT = Path(__file__).resolve().parent
SEED = 20261112
BASE = "http://127.0.0.1:11434/api/"
MODELS = {
    "generator": ("qwen3.6:latest", "07d35212591fc27746f0a317c975a6d68754fb38e9053d82e25f06057af28522"),
    "embedding": ("nomic-embed-text:latest", "0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f"),
    "judge": ("dolphin3:latest", "d5ab9ae8e1f22619a6be52e5694df422b7183a3883990a000188c363781ecb78"),
}
OPTIONS = {"temperature": 0, "seed": SEED, "num_ctx": 8192, "num_predict": 256, "num_thread": 8}
ANSWER_SCHEMA = {
    "type": "object", "properties": {
        "answer": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
        "abstain": {"type": "boolean"},
    }, "required": ["answer", "citations", "abstain"], "additionalProperties": False,
}
SYSTEM = (
    "Answer the question using only the supplied evidence. Give a short exact answer, "
    "not an explanation. Cite the sentence IDs (such as d00s002) needed to support "
    "every part of the answer. Do not cite chunk IDs. If the evidence does not support "
    "a complete answer, set abstain to true, answer to an empty string and citations "
    "to an empty array. Do not use facts from memory. Return the required JSON object."
)
JUDGE_SYSTEM = (
    "Judge whether the proposed answer is supported by the cited evidence alone. "
    "Do not use outside knowledge. supported means the cited text establishes the "
    "whole answer to this question; unsupported means it contradicts the text or "
    "asserts facts the text does not establish; uncertain means the evidence is "
    "ambiguous. A fact that you know is true can still be unsupported. Return JSON "
    "with verdict (supported, unsupported, uncertain) and a short reason."
)
JUDGE_SCHEMA = {
    "type": "object", "properties": {
        "verdict": {"type": "string", "enum": ["supported", "unsupported", "uncertain"]},
        "reason": {"type": "string"},
    }, "required": ["verdict", "reason"], "additionalProperties": False,
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def api(endpoint, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(BASE + endpoint, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)


def verify_models():
    installed = {m["name"]: m for m in api("tags")["models"]}
    for name, digest in MODELS.values():
        if installed.get(name, {}).get("digest") != digest:
            raise RuntimeError(f"Model digest differs from protocol: {name}")
    return installed


def load_cases():
    rows = pq.read_table(ROOT / "data/hotpot-validation.parquet").to_pylist()
    rng = random.Random(SEED)
    selected = []
    for kind in ("bridge", "comparison"):
        group = sorted((r for r in rows if r["type"] == kind), key=lambda r: r["id"])
        selected.extend(rng.sample(group, 32))
    return sorted(selected, key=lambda r: r["id"])


def chunks_for(case, size=3):
    chunks = []
    titles = case["context"]["title"]
    if len(set(titles)) != len(titles):
        raise ValueError(f"Duplicate paragraph title: {case['id']}")
    for doc_index, (title, sentences) in enumerate(zip(titles, case["context"]["sentences"], strict=True)):
        for start in range(0, len(sentences), size):
            facts = [{"id": f"d{doc_index:02}s{i:03}", "title": title, "sentence": i, "text": sentences[i].strip()}
                     for i in range(start, min(start + size, len(sentences)))]
            chunks.append({"id": f"d{doc_index:02}p{start:03}", "title": title, "facts": facts,
                           "text": title + "\n" + " ".join(f["text"] for f in facts)})
    known = {(f["title"], f["sentence"]) for c in chunks for f in c["facts"]}
    if not gold_facts(case) <= known:
        raise ValueError(f"Supporting fact absent from source: {case['id']}")
    return chunks


def gold_facts(case):
    return set(zip(case["supporting_facts"]["title"], case["supporting_facts"]["sent_id"], strict=True))


def fact_set(chunks):
    return {(f["title"], f["sentence"]) for c in chunks for f in c["facts"]}


def words(text):
    return re.findall(r"\w+", text.lower())


def bm25(chunks, question):
    counts = [Counter(words(c["text"])) for c in chunks]
    lengths = [sum(c.values()) for c in counts]
    average = sum(lengths) / len(lengths)
    query = set(words(question))
    df = {term: sum(term in c for c in counts) for term in query}
    scores = []
    for count, length in zip(counts, lengths, strict=True):
        value = 0.0
        for term in query:
            tf = count[term]
            if tf:
                idf = math.log(1 + (len(chunks) - df[term] + 0.5) / (df[term] + 0.5))
                value += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * length / average))
        scores.append(value)
    return scores


def embed(texts, cache):
    result = [None] * len(texts)
    pending = []
    for index, text in enumerate(texts):
        path = cache / (hashlib.sha256((MODELS["embedding"][1] + text).encode()).hexdigest() + ".json")
        if path.exists():
            result[index] = json.loads(path.read_text())
        else:
            pending.append((index, text, path))
    for start in range(0, len(pending), 16):
        batch = pending[start:start + 16]
        vectors = api("embed", {"model": MODELS["embedding"][0], "input": [item[1] for item in batch],
                               "truncate": False, "keep_alive": "30m", "options": {"num_thread": 8}})["embeddings"]
        for (index, _, path), vector in zip(batch, vectors, strict=True):
            path.write_text(json.dumps(vector))
            result[index] = vector
    return np.asarray(result, dtype=np.float64)


def rank(chunks, question, method, cache):
    if method == "bm25":
        scores = bm25(chunks, question)
    else:
        docs = embed(["search_document: " + c["text"] for c in chunks], cache)
        query = embed(["search_query: " + question], cache)[0]
        scores = (docs @ query) / (np.linalg.norm(docs, axis=1) * np.linalg.norm(query))
    order = sorted(range(len(chunks)), key=lambda i: (-float(scores[i]), chunks[i]["id"]))
    return [{**chunks[i], "score": float(scores[i])} for i in order]


def render_context(chunks):
    return "\n\n".join(f"[{c['id']}] {c['title']}\n" + "\n".join(
        f"[{f['id']}] {f['text']}" for f in c["facts"]) for c in chunks)


def pack(candidates, budget, policy, tokenizer):
    order = list(candidates)
    if policy == "diverse":
        groups = defaultdict(list)
        for chunk in candidates:
            groups[chunk["title"]].append(chunk)
        order = []
        for round_index in range(max(map(len, groups.values()), default=0)):
            order.extend(items[round_index] for items in groups.values() if round_index < len(items))
    selected = []
    for chunk in order:
        if len(tokenizer.encode(render_context(selected + [chunk])).ids) <= budget:
            selected.append(chunk)
    return selected


def retrieval_metrics(case, all_chunks, retrieved, selected):
    gold = gold_facts(case)
    relevant = {c["id"] for c in all_chunks if fact_set([c]) & gold}
    recall = len(relevant & {c["id"] for c in retrieved}) / len(relevant)
    coverage = len(gold & fact_set(selected)) / len(gold)
    return {"recall10": recall, "evidence_coverage": coverage,
            "complete_context": int(coverage == 1),
            "perfect_retrieval_incomplete_context": int(recall == 1 and coverage < 1)}


def stamp():
    return {"utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
            "machine": platform.machine(), "ollama": api("version")["version"],
            "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "executable_sha256": sha(__file__), "dataset": json.loads((ROOT / "data/dataset-source.json").read_text()),
            "tokenizer": json.loads((ROOT / "data/tokenizer-source.json").read_text()),
            "models": {k: {"name": v[0], "digest": v[1]} for k, v in MODELS.items()},
            "options": OPTIONS, "seed": SEED}


def prepare(out):
    if (out / "answers.jsonl").exists():
        raise RuntimeError("Cannot overwrite inputs after answer collection has started")
    verify_models()
    tokenizer = Tokenizer.from_file(str(ROOT / "data/qwen-tokenizer.json"))
    cases = load_cases()
    cache = ROOT / "data/embedding-cache"
    cache.mkdir(exist_ok=True)
    (out / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2))
    (out / "manifest.json").write_text(json.dumps(stamp(), indent=2))
    calibration = []
    for text in ("Hello world.", "Thirty seconds, then one retry after two seconds.", "[d00s002] Paris is in France."):
        response = api("generate", {"model": MODELS["generator"][0], "prompt": text, "raw": True,
                                    "stream": False, "think": False, "options": {**OPTIONS, "num_predict": 1}})
        expected = len(tokenizer.encode(text).ids)
        calibration.append({"text": text, "tokenizer": expected, "ollama": response["prompt_eval_count"]})
        if expected != response["prompt_eval_count"]:
            raise RuntimeError(f"Tokenizer mismatch: {calibration[-1]}")
    (out / "tokenizer-calibration.json").write_text(json.dumps(calibration, indent=2))
    jobs, sensitivity = [], []
    for index, case in enumerate(cases):
        for size in (2, 3, 6):
            chunks = chunks_for(case, size)
            for method in ("bm25", "dense"):
                ranked = rank(chunks, case["question"], method, cache)
                for k in (5, 10, 20):
                    metrics = retrieval_metrics(case, chunks, ranked[:k], ranked[:k])
                    sensitivity.append({"question_id": case["id"], "type": case["type"], "chunk_sentences": size,
                                        "retriever": method, "top_k": k, "passage_recall": metrics["recall10"]})
                if size != 3:
                    continue
                for policy in ("ranked", "diverse"):
                    for budget in (512, 1536):
                        selected = pack(ranked[:10], budget, policy, tokenizer)
                        context = render_context(selected)
                        jobs.append({"id": f"{case['id']}:{method}:{policy}:{budget}", "question_id": case["id"],
                                     "question": case["question"], "type": case["type"], "retriever": method,
                                     "policy": policy, "budget": budget, "context": context,
                                     "context_tokens": len(tokenizer.encode(context).ids), "selected": selected,
                                     "retrieved": ranked[:10], **retrieval_metrics(case, chunks, ranked[:10], selected)})
        (out / "jobs.json").write_text(json.dumps(jobs, ensure_ascii=False))
        (out / "retrieval-sensitivity.json").write_text(json.dumps(sensitivity))
        print(f"Prepared {index + 1}/{len(cases)} questions", flush=True)
    rng = random.Random(SEED)
    rng.shuffle(jobs)
    (out / "jobs.json").write_text(json.dumps(jobs, ensure_ascii=False))
    (out / "preparation-complete.json").write_text(json.dumps({"jobs": len(jobs), "questions": len(cases)}))


def chat(model, system, prompt, schema, options=None):
    payload = {"model": model, "messages": [{"role": "system", "content": system},
                                             {"role": "user", "content": prompt}],
               "format": schema, "stream": False, "keep_alive": "30m", "options": options or OPTIONS}
    if model == MODELS["generator"][0]:
        payload["think"] = False
    start = time.perf_counter()
    response = api("chat", payload)
    return {"request": payload, "response": response, "wall_seconds": time.perf_counter() - start}


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def append(path, value):
    with path.open("a") as file:
        file.write(json.dumps(value, ensure_ascii=False) + "\n")
        file.flush()


def parse_answer(raw):
    value = json.loads(raw["response"]["message"]["content"])
    if not isinstance(value.get("answer"), str) or not isinstance(value.get("abstain"), bool):
        raise ValueError("Invalid answer schema")
    if not isinstance(value.get("citations"), list) or any(not isinstance(v, str) for v in value["citations"]):
        raise ValueError("Invalid citations")
    return value


def score(case, job, answer):
    lookup = {f["id"]: f for c in job["selected"] for f in c["facts"]}
    citations = set(answer["citations"])
    valid = [lookup[c] for c in sorted(citations & lookup.keys())]
    predicted_facts = [(f["title"], f["sentence"]) for f in valid]
    metrics = {"sp_em": 0, "sp_f1": 0, "sp_prec": 0, "sp_recall": 0}
    # Invalid citation IDs count as false positives in support scoring.
    predicted_facts += [("__invalid__", c) for c in citations - lookup.keys()]
    update_sp(metrics, predicted_facts, list(gold_facts(case)))
    predicted = "" if answer["abstain"] else answer["answer"]
    return {"answer_em": int(exact_match_score(predicted, case["answer"])),
            "answer_f1": f1_score(predicted, case["answer"])[0], "abstain": int(answer["abstain"]),
            "citation_validity": len(valid) / len(citations) if citations else 0,
            "invalid_citations": len(citations - lookup.keys()), **metrics,
            "cited_text": "\n".join(f"[{f['id']}] {f['title']}: {f['text']}" for f in valid)}


def generate(out, limit=None, repeat=0):
    verify_models()
    if not (out / "preparation-complete.json").exists():
        raise RuntimeError("Preparation is incomplete")
    jobs = json.loads((out / "jobs.json").read_text())
    cases = {c["id"]: c for c in json.loads((out / "cases.json").read_text())}
    if repeat:
        ids = sorted(cases)[:16]
        jobs = [j for j in jobs if j["question_id"] in ids]
    path = out / (f"answers-repeat-{repeat}.jsonl" if repeat else "answers.jsonl")
    done = {r["id"] for r in records(path)}
    pending = [j for j in jobs if j["id"] not in done]
    if limit:
        pending = pending[:limit]
    service_failures = 0
    for index, job in enumerate(pending):
        record = {"id": job["id"], "utc": datetime.now(timezone.utc).isoformat()}
        try:
            raw = chat(MODELS["generator"][0], SYSTEM,
                       f"Question: {job['question']}\n\nEvidence:\n{job['context']}", ANSWER_SCHEMA)
            record["raw"] = raw
            if raw["response"]["prompt_eval_count"] + 256 > OPTIONS["num_ctx"]:
                raise RuntimeError("Model context may have been truncated")
            answer = parse_answer(raw)
            record.update({"answer": answer, "metrics": score(cases[job["question_id"]], job, answer)})
            service_failures = 0
        except Exception as error:
            record["error"] = f"{type(error).__name__}: {error}"
            service_failures = service_failures + 1 if isinstance(error, (urllib.error.URLError, TimeoutError)) else 0
        append(path, record)
        print(f"Generated {len(done) + index + 1}/{len(jobs)}; valid={'error' not in record}", flush=True)
        if service_failures >= 3:
            raise RuntimeError("Three service errors; stopping collection with failures preserved")


def controls(out):
    verify_models()
    cases = json.loads((out / "cases.json").read_text())[:16]
    path = out / "generator-controls.jsonl"
    done = {r["id"] for r in records(path)}
    for case in cases:
        gold = gold_facts(case)
        evidence = [{**chunk, "facts": [f for f in chunk["facts"] if (f["title"], f["sentence"]) in gold]}
                    for chunk in chunks_for(case) if fact_set([chunk]) & gold]
        for kind in ("gold_evidence", "prior_knowledge"):
            key = f"{case['id']}:{kind}"
            if key in done:
                continue
            system = SYSTEM if kind == "gold_evidence" else (
                "Answer this question from your knowledge with a short exact answer. "
                "Return JSON with answer, empty citations and abstain=false. If you "
                "do not know, use an empty answer and abstain=true."
            )
            prompt = f"Question: {case['question']}"
            if kind == "gold_evidence":
                prompt += "\n\nEvidence:\n" + render_context(evidence)
            result = {"id": key, "kind": kind, "question": case["question"], "reference": case["answer"]}
            try:
                raw = chat(MODELS["generator"][0], system, prompt, ANSWER_SCHEMA)
                parsed = parse_answer(raw)
                predicted = "" if parsed["abstain"] else parsed["answer"]
                result.update({"raw": raw, "answer": parsed,
                               "answer_em": int(exact_match_score(predicted, case["answer"])),
                               "answer_f1": f1_score(predicted, case["answer"])[0]})
            except Exception as error:
                result["error"] = f"{type(error).__name__}: {error}"
            append(path, result)
            print(f"Control {key}", flush=True)


def judge(out):
    verify_models()
    answers = records(out / "answers.jsonl")
    jobs = {j["id"]: j for j in json.loads((out / "jobs.json").read_text())}
    tasks = []
    for answer in answers:
        if "error" in answer or answer["answer"]["abstain"]:
            continue
        job = jobs[answer["id"]]
        tasks.append({"id": answer["id"], "question": job["question"], "answer": answer["answer"]["answer"],
                      "evidence": answer["metrics"]["cited_text"], "kind": "prediction"})
    cases = json.loads((out / "cases.json").read_text())
    for index, case in enumerate(cases[:16]):
        full = chunks_for(case)
        evidence = "\n".join(f"{f['title']}: {f['text']}" for c in full for f in c["facts"]
                             if (f["title"], f["sentence"]) in gold_facts(case))
        other = cases[(index + 1) % len(cases)]
        unrelated = "\n".join(f"{f['title']}: {f['text']}" for c in chunks_for(other) for f in c["facts"]
                               if (f["title"], f["sentence"]) in gold_facts(other))
        for kind, text in (("positive", evidence), ("swapped", unrelated)):
            tasks.append({"id": f"control:{case['id']}:{kind}", "question": case["question"],
                          "answer": case["answer"], "evidence": text, "kind": kind})
    random.Random(SEED).shuffle(tasks)
    path = out / "judge.jsonl"
    done = {r["id"] for r in records(path)}
    for index, task in enumerate(t for t in tasks if t["id"] not in done):
        result = {"id": task["id"], "kind": task["kind"]}
        try:
            raw = chat(MODELS["judge"][0], JUDGE_SYSTEM,
                       f"Question: {task['question']}\nProposed answer: {task['answer']}\nCited evidence:\n{task['evidence']}",
                       JUDGE_SCHEMA, {**OPTIONS, "num_predict": 192})
            result.update({"raw": raw, "judgement": json.loads(raw["response"]["message"]["content"])})
        except Exception as error:
            result["error"] = f"{type(error).__name__}: {error}"
        append(path, result)
        print(f"Judged {len(done) + index + 1}/{len(tasks)}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["prepare", "generate", "controls", "judge"])
    parser.add_argument("--out", type=Path, default=ROOT / "runs/2026-11-12-rag")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--repeat", type=int, default=0)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.stage == "prepare":
        prepare(args.out)
    elif args.stage == "generate":
        generate(args.out, args.limit, args.repeat)
    elif args.stage == "controls":
        controls(args.out)
    else:
        judge(args.out)


if __name__ == "__main__":
    main()
