"""Replay V3 evidence offline; never call a model or fill semantic labels."""
from __future__ import annotations

import argparse
import base64
from datetime import datetime
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess

import pyarrow.parquet as pq
from tokenizers import Tokenizer

import run as original
from v2.benchmark import payload_for
from v2.core import answer_metrics, chunks, digest, documents, ranking
from v2.verify import checked_answer
from v3 import design
from v3.benchmark import BUDGETS, METHODS, load_vectors
from v3.core import (POLICIES, context_metrics, context_redundancy,
                     required_sentence_texts, select)
from v3.design import (BASE, COHORTS, REGISTRATION, PUBLIC_REGISTRATION,
                       PILOT_RUN_NAME, ROOT, file_sha, lines, read)

PROBES = ("Hello world.", "Thirty seconds, then one retry after two seconds.",
          "[d00s002] Paris is in France.")
EXECUTION_SCOPE = "One local quality experiment; timings do not qualify production performance or financial cost."
PREPARATION_SCOPES = {
    "controlled": "Controlled ten supplied paragraphs per question.",
    "pooled": "Pooled results are separate exploratory question-derived retrieval, without generation.",
}


def equal(actual, expected, where="value"):
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or actual.keys() != expected.keys():
            raise ValueError(f"Replayed keys differ: {where}")
        for key in expected:
            equal(actual[key], expected[key], where + "." + str(key))
    elif isinstance(expected, (list, tuple)):
        if not isinstance(actual, (list, tuple)) or len(actual) != len(expected):
            raise ValueError(f"Replayed sequence differs: {where}")
        for index, (a, b) in enumerate(zip(actual, expected, strict=True)):
            equal(a, b, f"{where}[{index}]")
    elif isinstance(expected, bool):
        if type(actual) is not bool or actual != expected:
            raise ValueError(f"Replayed flag differs: {where}")
    elif isinstance(expected, (int, float)):
        if (isinstance(actual, bool) or not isinstance(actual, (int, float))
                or not math.isfinite(actual) or not math.isfinite(expected)
                or not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-12)):
            raise ValueError(f"Replayed number differs: {where}")
    elif actual != expected:
        raise ValueError(f"Replayed value differs: {where}")


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("An evidence timestamp must specify its timezone")
    return result


def after_publication(value, proof):
    if timestamp(value) < publication_time(proof):
        raise ValueError("An outcome predates public registration")


def publication_time(proof):
    if proof.get("publication_kind") == "release":
        return timestamp(proof["published_at"])
    if proof.get("publication_kind") not in (None, "pull_request"):
        raise ValueError("Unknown publication evidence kind")
    return timestamp(proof["github_pull_request_created_at"])


def nonnegative(value, name):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0):
        raise ValueError("Non-finite or negative recorded cost: " + name)


def verify_cohorts():
    design.check_inputs()
    historical = read(ROOT / design.HISTORICAL_CASES)
    v2 = read(ROOT / design.V2_COHORTS)
    if (len(historical), len(v2["pilot"]), len(v2["confirmatory"])) != (64, 8, 256):
        raise ValueError("Historical cohort counts differ")
    cohort = read(COHORTS)
    rows = pq.read_table(ROOT / "data/hotpot-validation.parquet").to_pylist()
    original_cohort = read(design.LEGACY_COHORTS)
    expected = design.amendment_cohort(rows, historical, v2, original_cohort, cohort["selected_utc"])
    equal(cohort, expected, "cohort")
    return cohort


def verify_public_registration(registration, cohort, registration_path=None, proof_path=None):
    registration_path = Path(registration_path) if registration_path is not None else REGISTRATION
    proof_path = Path(proof_path) if proof_path is not None else PUBLIC_REGISTRATION
    proof = read(proof_path)
    if proof["registration_sha256"] != file_sha(registration_path):
        raise ValueError("Public registration fingerprint differs")
    if not (timestamp(cohort["selected_utc"]) <= timestamp(registration["registered_utc"])
            <= publication_time(proof)):
        raise ValueError("Cohort/registration/publication chronology differs")
    for name, expected in {**registration["files"],
                           str(registration_path.relative_to(ROOT)): file_sha(registration_path)}.items():
        result = subprocess.run(["git", "show", proof["commit"] + ":" + name],
                                cwd=ROOT, capture_output=True)
        if result.returncode or hashlib.sha256(result.stdout).hexdigest() != expected:
            raise ValueError("The public commit lacks a frozen input: " + name)
    return proof


def verify_metadata(value, proof, scope=EXECUTION_SCOPE):
    after_publication(value["utc"], proof)
    if value["registration_sha256"] != proof["registration_sha256"]:
        raise ValueError("Execution registration differs")
    equal(value["models"], json.loads(json.dumps(original.MODELS)), "execution.models")
    environment = read(BASE / "environment.json")
    for key, version in value["dependencies"].items():
        if environment["dependencies"][key] != version:
            raise ValueError("Collection dependency differs: " + key)
    if value["python"] != environment["python"]:
        raise ValueError("Collection Python differs from the registered environment")
    equal(value["public_registration"], proof, "execution.public_registration")
    equal(value["scope"], scope, "metadata.scope")


def verify_preparation(out, cases, split, environment, tokenizer, vectors, proof):
    preparation = read(out / "preparation.json")
    verify_metadata(preparation, proof, PREPARATION_SCOPES[environment])
    start = read(out / "preparation-start.json")
    verify_metadata(start, proof)
    for key in start.keys() - {"scope"}:
        equal(preparation[key], start[key], "preparation-start." + key)
    job_list = read(out / "jobs.json")
    if preparation["jobs_sha256"] != file_sha(out / "jobs.json"):
        raise ValueError("Prepared context fingerprint differs")
    expected_ids = {f"{c['id']}:{m}:{p}:{b}" for c in cases
                    for m in METHODS for p in POLICIES for b in BUDGETS}
    jobs = {job["id"]: job for job in job_list}
    if len(jobs) != len(job_list) or set(jobs) != expected_ids:
        raise ValueError("Incomplete, unexpected or duplicate deterministic jobs")
    corpus = {d["key"]: d for case in cases for d in documents(case)}
    pooled = chunks([corpus[k] for k in sorted(corpus)]) if environment == "pooled" else None
    retrieval = []
    retrieval_inputs = {"search_query: " + c["question"] for c in cases}
    sentence_inputs = set()
    order = []
    for case in cases:
        indexed = pooled if pooled is not None else chunks(documents(case))
        retrieval_inputs.update("search_document: " + c["text"] for c in indexed)
        for method in METHODS:
            ranked = ranking(indexed, case["question"], method, vectors)
            sentence_inputs.update(required_sentence_texts(ranked[:10]))
            stored_top_ten = jobs[f"{case['id']}:{method}:ranked:512"]["retrieved"]
            retrieval.append({"question_id": case["id"], "retriever": method,
                              "indexed_chunks": len(ranked),
                              "ranking_sha256": digest([c["id"] for c in ranked]),
                              "top_ten_sha256": digest(stored_top_ten)})
            for policy in POLICIES:
                for budget in BUDGETS:
                    key = f"{case['id']}:{method}:{policy}:{budget}"
                    order.append(key)
                    job = jobs[key]
                    expected = {"id": key, "question_id": case["id"],
                                "question": case["question"], "type": case["type"],
                                "retriever": method, "policy": policy, "budget": budget,
                                "split": split, "environment": environment}
                    for name, value in expected.items():
                        equal(job[name], value, key + "." + name)
                    equal(job["retrieved"], ranked[:10], key + ".retrieved")
                    selected = select(case["question"], ranked[:10], policy, budget, tokenizer, vectors)
                    equal(job["selected"], selected, key + ".selected")
                    for name, value in context_metrics(case, indexed, ranked, selected, tokenizer, budget).items():
                        equal(job[name], value, key + "." + name)
                    equal(job["redundancy"], context_redundancy(selected, vectors), key + ".redundancy")
                    nonnegative(job["warm_selection_seconds"], "warm selection")
    random.Random(design.SEED + 5).shuffle(order)
    equal([j["id"] for j in job_list], order, "job order")
    equal(preparation["retrieval"], retrieval, "retrieval fingerprints")
    for name, value in {"split": split, "environment": environment,
                        "questions": len(cases), "jobs": len(job_list),
                        "corpus_paragraphs": len(corpus),
                        "corpus_chunks": len(pooled) if pooled is not None else None,
                        "corpus_sha256": digest([corpus[k] for k in sorted(corpus)])}.items():
        equal(preparation[name], value, "preparation." + name)
    nonnegative(preparation["shared_ranking_wall_seconds"], "shared retrieval")
    packet_paths = []
    summaries = preparation["embedding_preparation"]
    if len(summaries) != 2:
        raise ValueError("Missing separate retrieval/sentence preparation costs")
    for summary, stage, inputs in zip(summaries, ("retrieval", "sentences"),
                                      (retrieval_inputs, sentence_inputs), strict=True):
        if summary["purpose"] != f"{split}:{environment}:{stage}" or summary["requested_unique"] != len(inputs):
            raise ValueError("Embedding preparation scope differs")
        for key in ("requested_unique", "cached_inputs", "new_inputs", "api_wall_seconds"):
            nonnegative(summary[key], "embedding " + key)
        if summary["requested_unique"] != summary["cached_inputs"] + summary["new_inputs"]:
            raise ValueError("Embedding preparation counts differ")
        packets = []
        for name in summary["packets"]:
            path = ROOT / name
            if not path.resolve().is_relative_to((BASE / "runs/embedding-traces").resolve()):
                raise ValueError("Unexpected embedding packet path")
            packet = json.loads(gzip.decompress(path.read_bytes()))
            after_publication(packet["utc"], proof)
            if packet["registration_sha256"] != proof["registration_sha256"] or packet["purpose"] != summary["purpose"]:
                raise ValueError("Embedding packet provenance differs")
            equal(packet["request"]["model"], original.MODELS["embedding"][0], "embedding model")
            if packet["request"].get("truncate") is not False or "error" in packet:
                raise ValueError("An unsuccessful or truncated embedding entered preparation")
            nonnegative(packet["wall_seconds"], "embedding API")
            packets.append(packet); packet_paths.append(name)
        equal(summary["new_inputs"], sum(len(p["request"]["input"]) for p in packets), "new embedding inputs")
        equal(summary["api_wall_seconds"], sum(p["wall_seconds"] for p in packets), "embedding API sum")
    return jobs, packet_paths


def observed_response(record):
    """Reconstruct output failures, retaining transport/unknown outcomes separately."""
    if "response_body_base64" in record:
        raw = base64.b64decode(record["response_body_base64"], validate=True)
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            pass
        else:
            raise ValueError("A UTF-8 body was incorrectly classified as undecodable")
        expected = (f"RecordedRequestError: HTTP {record['http_status']}"
                    if record.get("http_status", 200) >= 400
                    else "RecordedRequestError: Invalid JSON response")
        if record.get("error") != expected:
            raise ValueError("Undecodable response failure differs")
        return None
    if "response_body" not in record:
        if not isinstance(record.get("error"), str) or not record["error"] or "response" in record:
            raise ValueError("Neither an exact response nor a retained failure")
        return None
    if record.get("http_status", 200) >= 400:
        if record.get("error") != f"RecordedRequestError: HTTP {record['http_status']}":
            raise ValueError("HTTP failure classification differs")
        return None
    try:
        response = json.loads(record["response_body"])
    except json.JSONDecodeError:
        if record.get("error") != "RecordedRequestError: Invalid JSON response":
            raise ValueError("Malformed JSON failure differs")
        return None
    if record.get("response") is not None:
        equal(record["response"], response, "raw response")
    return response


def verify_answers(records, intents, jobs, cases, expected, proof, complete=True):
    answers = {record["id"]: record for record in records}
    requests = {record["id"]: record for record in intents}
    if (len(answers) != len(records) or len(requests) != len(intents)
            or not set(answers) <= set(requests) <= expected):
        raise ValueError("Duplicate, retried or unexpected response/intent")
    if complete and (set(answers) != expected or set(requests) != expected):
        raise ValueError("Incomplete planned generation denominator")
    errors = reconstructed = unknown = 0
    for key, intent in requests.items():
        payload = payload_for(jobs[key])
        equal(intent["request"], payload, "intent request")
        equal(intent["request_sha256"], digest(payload), "intent fingerprint")
        after_publication(intent["utc"], proof)
    for key, record in answers.items():
        payload = payload_for(jobs[key])
        equal(record["request"], payload, "observed request")
        equal(record["request_sha256"], digest(payload), "request fingerprint")
        after_publication(record["utc"], proof)
        if timestamp(record["utc"]) < timestamp(requests[key]["utc"]):
            raise ValueError("A response record predates its request intent")
        if "wall_seconds" in record:
            nonnegative(record["wall_seconds"], "generation wall time")
        response = observed_response(record)
        if response is None:
            errors += 1; unknown += 1
            if "metrics" in record or "answer" in record:
                raise ValueError("A failed request carries successful scores")
            continue
        for name in ("total_duration", "load_duration", "prompt_eval_count", "prompt_eval_duration", "eval_count", "eval_duration"):
            if name in response:
                nonnegative(response[name], "generation API " + name)
        try:
            answer = checked_answer(response)
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            if record.get("error") != f"{type(error).__name__}: {error}":
                raise ValueError("Recorded output failure cannot be reproduced") from error
            if "metrics" in record or "answer" in record:
                raise ValueError("An invalid output carries successful scores")
            errors += 1; reconstructed += 1
            continue
        if "error" in record:
            raise ValueError("A successful output was relabelled as a failure")
        equal(record["answer"], answer, "parsed answer")
        equal(record["metrics"], answer_metrics(cases[jobs[key]["question_id"]], jobs[key], answer), "lexical/citation metrics")
    return {"planned": len(expected), "observed": len(answers), "errors": errors,
            "output_failures_reconstructed": reconstructed,
            "transport_or_unknown_failures": unknown,
            "unobserved_intents": len(set(requests) - answers.keys())}


def verify_probes(out, tokenizer, proof):
    rows = read(out / "tokenizer-calibration.json")
    observed = lines(out / "tokenizer-calibration-responses.jsonl")
    intents = lines(out / "tokenizer-calibration-intents.jsonl")
    equal(rows, observed, "tokenizer final versus append-only responses")
    expected_ids = {f"probe-{index}" for index in range(3)}
    if (len(rows) != len(intents) or len(rows) != 3
            or {r["id"] for r in rows} != expected_ids
            or {r["id"] for r in intents} != expected_ids):
        raise ValueError("Missing, duplicate or retried tokenizer probes")
    by_id = {r["id"]: r for r in rows}
    for index, text in enumerate(PROBES):
        intent = intents[index]; record = by_id[f"probe-{index}"]
        payload = {"model": original.MODELS["generator"][0], "prompt": text, "raw": True,
                   "stream": False, "think": False,
                   "options": {**original.OPTIONS, "num_predict": 1}}
        equal(intent["id"], f"probe-{index}", "probe order")
        equal(intent["request"], payload, "tokenizer intent")
        equal(intent["request_sha256"], digest(payload), "tokenizer intent fingerprint")
        equal(record["request"], payload, "tokenizer request")
        after_publication(intent["utc"], proof); after_publication(record["utc"], proof)
        if timestamp(record["utc"]) < timestamp(intent["utc"]):
            raise ValueError("Tokenizer response predates intent")
        if "error" in record:
            raise ValueError("A failed tokenizer probe cannot qualify the pilot")
        response = json.loads(record["response_body"])
        if response.get("model") != original.MODELS["generator"][0] or response.get("done") is not True:
            raise ValueError("Tokenizer response model or completion differs")
        equal(record["ollama_tokens"], response["prompt_eval_count"], "native prompt count")
        equal(record["tokenizer_tokens"], len(tokenizer.encode(text).ids), "tokenizer count")
        equal(record["ollama_tokens"], record["tokenizer_tokens"], "tokenizer calibration")
        nonnegative(record["wall_seconds"], "tokenizer probe")
    return {"probes": 3, "model_calls_on_replay": 0}


def verify_pilot_certificate(out, answers, proof):
    certificate = read(out / "qualification.json")
    after_publication(certificate["utc"], proof)
    for name, value in {"passed": True, "questions": 8, "contexts": 128,
                        "responses": 64, "errors": 0,
                        "registration_sha256": proof["registration_sha256"],
                        "jobs.json_sha256": file_sha(out / "jobs.json"),
                        "answers.jsonl_sha256": file_sha(out / "answers.jsonl")}.items():
        equal(certificate[name], value, "pilot certificate." + name)
    evidence = {path.name: file_sha(path) for path in sorted(out.iterdir())
                if path.is_file() and path.suffix in (".json", ".jsonl")
                and path.name != "qualification.json"}
    equal(certificate["evidence_sha256"], evidence, "pilot certificate evidence")
    for record in lines(out / "answers.jsonl") + lines(out / "tokenizer-calibration-responses.jsonl"):
        if timestamp(certificate["utc"]) < timestamp(record["utc"]):
            raise ValueError("Pilot certificate predates its observations")
    if answers["errors"] or answers["observed"] != 64:
        raise ValueError("A failed or incomplete pilot cannot qualify confirmation")
    return certificate


def verify_pilot_inputs(proof=None):
    """Independently replay the complete pilot before its certificate is written."""
    registration = design.registered()
    cohort = verify_cohorts()
    published = verify_public_registration(registration, cohort)
    if proof is not None:
        equal(proof, published, "pilot publication receipt")
    proof = published
    out = BASE / "runs" / PILOT_RUN_NAME
    tokenizer = Tokenizer.from_file(str(ROOT / "data/qwen-tokenizer.json"))
    vectors = load_vectors()
    jobs, packets = verify_preparation(out, cohort["pilot"], "pilot", "controlled",
                                       tokenizer, vectors, proof)
    cases = {c["id"]: c for c in cohort["pilot"]}
    expected = {key for key, job in jobs.items() if job["budget"] == 512}
    result = verify_answers(lines(out / "answers.jsonl"), lines(out / "intents.jsonl"),
                            jobs, cases, expected, proof, complete=True)
    probes = verify_probes(out, tokenizer, proof)
    executions = sorted(out.glob("execution-*.json"))
    if not executions:
        raise ValueError("Pilot lacks generation execution metadata")
    for execution in executions:
        verify_metadata(read(execution), proof)
    if len(cases) != 8 or len(jobs) != 128 or result["observed"] != 64 or result["errors"]:
        raise ValueError("Pilot inputs are incomplete or contain a recorded failure")
    return {"passed": True, "questions": len(cases), "contexts": len(jobs),
            "responses": result["observed"], "errors": result["errors"],
            "tokenizer_probes": probes["probes"], "embedding_packets": len(packets),
            "model_calls": 0}


def prior_allowed_files():
    """Only the hash-bound original pilot may predate amendment publication."""
    path = BASE / "amendments/01/prior-evidence.json"
    if not path.exists():
        return {}
    prior = read(path)
    allowed = dict(prior["files"])
    allowed.update(prior["inherited_embedding_packets"])
    archive = read(ROOT / prior["legacy_archive"])
    for row in archive["files"]:
        allowed[row["path"]] = row["sha256"]
    for name, expected in allowed.items():
        if not (ROOT / name).is_file() or file_sha(ROOT / name) != expected:
            raise ValueError("Retained original-pilot evidence differs: " + name)
    return allowed


def verify_embedding_epochs(proof):
    prior_path = BASE / "amendments/01/prior-evidence.json"
    prior = read(prior_path) if prior_path.exists() else {"inherited_embedding_packets": {}}
    original_proof = read(design.LEGACY_PUBLIC_REGISTRATION) if prior_path.exists() else None
    inherited = prior["inherited_embedding_packets"]
    for path in sorted((BASE / "runs/embedding-traces").glob("batch-*.json.gz")):
        name = str(path.relative_to(ROOT))
        packet = json.loads(gzip.decompress(path.read_bytes()))
        if name in inherited:
            if file_sha(path) != inherited[name]:
                raise ValueError("Inherited embedding packet changed")
            if packet["registration_sha256"] != original_proof["registration_sha256"]:
                raise ValueError("Inherited embedding registration differs")
            after_publication(packet["utc"], original_proof)
        else:
            if packet["registration_sha256"] != proof["registration_sha256"]:
                raise ValueError("New embedding packet lacks amendment identity")
            after_publication(packet["utc"], proof)
    return set(inherited)


def diagnostic_original_pilot():
    """Replay a corrected check without replacing the failed qualification."""
    prior = design.check_prior_evidence()
    original_cohort = read(design.LEGACY_COHORTS)
    registration = read(design.LEGACY_REGISTRATION)
    proof = verify_public_registration(registration, original_cohort,
                                       design.LEGACY_REGISTRATION,
                                       design.LEGACY_PUBLIC_REGISTRATION)
    out = ROOT / prior["original_failed_pilot"]
    tokenizer = Tokenizer.from_file(str(ROOT / "data/qwen-tokenizer.json"))
    vectors = load_vectors()
    jobs, packets = verify_preparation(out, original_cohort["pilot"], "pilot", "controlled",
                                       tokenizer, vectors, proof)
    cases = {c["id"]: c for c in original_cohort["pilot"]}
    expected = {key for key, job in jobs.items() if job["budget"] == 512}
    answers = verify_answers(lines(out / "answers.jsonl"), lines(out / "intents.jsonl"),
                             jobs, cases, expected, proof, complete=True)
    probes = verify_probes(out, tokenizer, proof)
    for execution in out.glob("execution-*.json"):
        verify_metadata(read(execution), proof)
    recorded = read(out / "qualification.json")
    if recorded["passed"] is not False:
        raise ValueError("The original failed qualification was relabelled")
    for name, expected in prior["qualification_preserved"].items():
        equal(recorded[name], expected, "retained failed qualification." + name)
    return {"role": "diagnostic replay only; original pilot remains excluded",
            "included_for_confirmation": False, "recorded_passed": False,
            "corrected_input_replay_passed": not answers["errors"],
            "contexts": len(jobs), "responses": answers["observed"],
            "errors": answers["errors"], "tokenizer_probes": probes["probes"],
            "embedding_packets": len(packets), "model_calls": 0}


def verify(protocol_only=False, require_collected=False):
    prior_path = BASE / "amendments/01/prior-evidence.json"
    if prior_path.exists():
        from v3.archive import restore
        restore(root=ROOT, manifest_path=read(prior_path)["legacy_archive"])
    registration = design.registered()
    cohort = verify_cohorts()
    if timestamp(cohort["selected_utc"]) > timestamp(registration["registered_utc"]):
        raise ValueError("Cohort was selected after registration")
    allowed = prior_allowed_files()
    outcome_files = [p for p in (BASE / "runs").rglob("*") if p.is_file()
                     and str(p.relative_to(ROOT)) not in allowed]
    manifest_path = BASE / "archive-manifest.json"
    archive = None
    if manifest_path.exists():
        from v3.archive import restore
        archive = restore(root=ROOT)
    if protocol_only:
        if outcome_files or archive is not None:
            raise ValueError("Protocol-only verification requires absence of amendment outcomes")
        return {"status": "registered prospective amendment; no amendment outcomes collected",
                "original_pilot": "retained excluded under its original failed qualification",
                "pilot_questions": 8, "deterministic_questions": 256,
                "generation_questions": 128, "model_calls": 0}
    if not outcome_files:
        if require_collected:
            raise ValueError("V3 observations have not been collected")
        return {"status": "registered protocol; collection pending", "model_calls": 0}
    proof = verify_public_registration(registration, cohort)
    inherited_packets = verify_embedding_epochs(proof)
    tokenizer = Tokenizer.from_file(str(ROOT / "data/qwen-tokenizer.json"))
    vectors = load_vectors()
    reports = {}; packet_paths = []; missing = []
    pilot_certificate = None
    for split, environment in (("pilot", "controlled"), ("confirmatory", "controlled"),
                               ("confirmatory", "pooled")):
        out = BASE / "runs" / (PILOT_RUN_NAME if split == "pilot" else f"{split}-{environment}")
        if not (out / "preparation.json").exists():
            missing.append(f"{split}-{environment}")
            continue
        if split == "confirmatory" and pilot_certificate is None:
            raise ValueError("Confirmation lacks a verified complete pilot")
        if split == "confirmatory" and timestamp(read(out / "preparation-start.json")["utc"]) < timestamp(pilot_certificate["utc"]):
            raise ValueError("Confirmation preparation predates pilot qualification")
        jobs, packets = verify_preparation(out, cohort[split], split, environment, tokenizer, vectors, proof)
        packet_paths.extend(packets)
        cases = {c["id"]: c for c in cohort[split]}
        ids = set(cohort["generation_ids"]) if split == "confirmatory" else set(cases)
        expected = {key for key, job in jobs.items() if job["budget"] == 512
                    and job["question_id"] in ids} if environment == "controlled" else set()
        answers = verify_answers(lines(out / "answers.jsonl"), lines(out / "intents.jsonl"),
                                 jobs, cases, expected, proof, complete=require_collected or split == "pilot")
        executions = sorted(out.glob("execution-*.json"))
        if answers["observed"] and not executions:
            raise ValueError("Generation execution metadata is missing")
        for execution in executions:
            verify_metadata(read(execution), proof)
        if split == "pilot":
            verify_probes(out, tokenizer, proof)
            pilot_certificate = verify_pilot_certificate(out, answers, proof)
        if split == "confirmatory":
            from v3.analysis import analyse
            if (out / "results.json").exists():
                equal(read(out / "results.json"), analyse(environment, write=False), environment + " analysis")
            elif require_collected:
                raise ValueError("Missing archived analysis: " + environment)
        reports[f"{split}-{environment}"] = {"contexts": len(jobs), **answers}
    packets = {str(p.relative_to(ROOT)) for p in (BASE / "runs/embedding-traces").glob("batch-*.json.gz")}
    if len(packet_paths) != len(set(packet_paths)):
        raise ValueError("Embedding preparation cost was assigned more than once")
    orphan_packets = sorted(packets - set(packet_paths) - inherited_packets)
    if require_collected:
        if missing or orphan_packets or archive is None:
            raise ValueError("Incomplete final collection, archive, or preparation accounting")
        manifest = read(manifest_path)
        indexed = {r["source_path"] for r in manifest["files"]}
        actual = {str(p.relative_to(ROOT)) for p in (BASE / "runs").rglob("*")
                  if p.is_file() and (p.suffix in (".json", ".jsonl")
                                      or p.parent.name == "embedding-traces" and p.name.endswith(".json.gz"))}
        if indexed != actual:
            raise ValueError("An observation is absent from the lossless archive inventory")
    return {"status": "complete archived collection verified" if not missing and require_collected
                      else "available observations verified; incomplete collection is not a completed experiment",
            "collections": reports, "missing_collections": missing,
            "retained_original_pilot": diagnostic_original_pilot(),
            "inherited_embedding_packets": len(inherited_packets),
            "unassigned_embedding_packets": orphan_packets, "archive": archive,
            "semantic_validation": "pending independent human annotation",
            "model_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--protocol-only", action="store_true")
    group.add_argument("--require-collected", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.protocol_only, args.require_collected), indent=2))


if __name__ == "__main__":
    main()
