"""Prospective V3 cohorts, immutable records, and source registration."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess

import pyarrow.parquet as pq

import run as original
from v2.core import annotations, documents

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "v3"
LEGACY_COHORTS = BASE / "data/cohorts.json"
LEGACY_REGISTRATION = BASE / "registration.json"
LEGACY_PUBLIC_REGISTRATION = BASE / "public-registration.json"
COHORTS = BASE / "data/cohorts-amendment-01.json"
REGISTRATION = BASE / "registration-amendment-01.json"
PUBLIC_REGISTRATION = BASE / "public-registration-amendment-01.json"
PILOT_RUN_NAME = "pilot-01-controlled"
PRIOR_EVIDENCE = "v3/amendments/01/prior-evidence.json"
AMENDMENT_PILOT_SEED = 20261216
SEED = 20261115
HISTORICAL_CASES = "runs/2026-11-12-rag/cases.json"
V2_COHORTS = "v2/data/cohorts.json"
PRESERVATION = "v3/historical-preservation.json"
FROZEN_FILES = (
    "v3/PROTOCOL.md", "v3/LITERATURE.md", "v3/environment.json",
    "v3/data/cohorts.json", "v3/registration.json", "v3/public-registration.json",
    "v3/data/cohorts-amendment-01.json", "v3/data/power-planning.json", PRESERVATION,
    "v3/AMENDMENT-01.md", PRIOR_EVIDENCE,
    "requirements-lock.txt", "sources.json", "run.py",
)


def utc():
    return datetime.now(timezone.utc).isoformat()


def file_sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_new(path, value):
    """Create a record once; never replace an earlier observation or decision."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def lines(path):
    path = Path(path)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()] if path.exists() else []


def append(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def check_inputs():
    sources = read(ROOT / "sources.json")
    for key, name in (("dataset", "hotpot-validation.parquet"),
                      ("tokenizer", "qwen-tokenizer.json")):
        if file_sha(ROOT / "data" / name) != sources[key]["sha256"]:
            raise ValueError(f"Pinned {key} differs")


def check_historical():
    """Check retained bytes, not a regenerated interpretation of earlier data."""
    manifest = read(ROOT / PRESERVATION)
    for name, expected in manifest["files"].items():
        path = ROOT / name
        if not path.is_file() or file_sha(path) != expected:
            raise ValueError(f"Historical evidence changed: {name}")
    return manifest


def normalized_question(case):
    return " ".join(case["question"].lower().split())


def check_prior_evidence():
    """Retain the failed first pilot and its original publication identities."""
    manifest = read(ROOT / PRIOR_EVIDENCE)
    for name, expected in manifest["files"].items():
        path = ROOT / name
        if not path.is_file() or file_sha(path) != expected:
            raise ValueError("Original V3 evidence changed: " + name)
    for name, expected in manifest["inherited_embedding_packets"].items():
        if manifest["files"].get(name) != expected or file_sha(ROOT / name) != expected:
            raise ValueError("Inherited embedding identity differs: " + name)
    return manifest


def select_cohorts(rows, historical):
    """Fixed-size, seeded, outcome-blind sampling with support-title separation."""
    used_ids = {case["id"] for case in historical}
    used_questions = {normalized_question(case) for case in historical}
    used_titles = {title for case in historical
                   for title in case["supporting_facts"]["title"]}
    excluded = Counter()
    result = {}
    for split, per_type, offset in (("pilot", 4, 1), ("confirmatory", 128, 2)):
        selected = []
        rng = random.Random(SEED + offset)
        for kind in ("bridge", "comparison"):
            candidates = sorted((case for case in rows if case["type"] == kind),
                                key=lambda case: case["id"])
            rng.shuffle(candidates)
            group = []
            for case in candidates:
                try:
                    annotations(case)
                    if len(documents(case)) != 10:
                        raise ValueError("Expected ten supplied paragraphs")
                except (KeyError, ValueError, TypeError, IndexError):
                    excluded[f"{split}:{kind}:invalid_case"] += 1
                    continue
                question = normalized_question(case)
                titles = set(case["supporting_facts"]["title"])
                reason = ("reused_id" if case["id"] in used_ids else
                          "reused_question" if question in used_questions else
                          "shared_support_title" if titles & used_titles else None)
                if reason:
                    excluded[f"{split}:{kind}:{reason}"] += 1
                    continue
                group.append(case)
                used_ids.add(case["id"])
                used_questions.add(question)
                used_titles.update(titles)
                if len(group) == per_type:
                    break
            if len(group) != per_type:
                raise ValueError(f"Insufficient eligible questions for {split}/{kind}")
            selected.extend(group)
        result[split] = sorted(selected, key=lambda case: case["id"])
    rng = random.Random(SEED + 3)
    generation = sorted(case["id"] for kind in ("bridge", "comparison")
                        for case in rng.sample(
                            [case for case in result["confirmatory"]
                             if case["type"] == kind], 64))
    return {"seed": SEED, "pilot": result["pilot"],
            "confirmatory": result["confirmatory"], "generation_ids": generation,
            "seeds": {"pilot": SEED + 1, "confirmatory": SEED + 2,
                      "generation": SEED + 3, "job_order": SEED + 5},
            "exclusions_examined_before_targets_reached": dict(excluded),
            "selection": "Sequential seeded random-order eligibility sampling, "
                         "balanced by type, excluding historical IDs, normalized "
                         "questions and support titles; selected V3 support titles "
                         "cannot recur. This is not a simple random sample."}


def select_amendment_cohorts(rows, historical, original_cohort):
    """Replace the complete failed pilot; preserve every confirmation decision."""
    previous = historical + original_cohort["pilot"] + original_cohort["confirmatory"]
    used_ids = {c["id"] for c in previous}
    used_questions = {normalized_question(c) for c in previous}
    used_titles = {title for c in previous for title in c["supporting_facts"]["title"]}
    rng = random.Random(AMENDMENT_PILOT_SEED)
    excluded = Counter(); selected = []
    for kind in ("bridge", "comparison"):
        pool = sorted((c for c in rows if c["type"] == kind), key=lambda c: c["id"])
        rng.shuffle(pool); group = []
        for case in pool:
            try:
                annotations(case)
                if len(documents(case)) != 10:
                    raise ValueError("Expected ten supplied paragraphs")
            except (KeyError, ValueError, TypeError, IndexError):
                excluded[f"pilot:{kind}:invalid_case"] += 1
                continue
            question = normalized_question(case)
            titles = set(case["supporting_facts"]["title"])
            reason = ("reused_id" if case["id"] in used_ids else
                      "reused_question" if question in used_questions else
                      "shared_support_title" if titles & used_titles else None)
            if reason:
                excluded[f"pilot:{kind}:{reason}"] += 1
                continue
            group.append(case); used_ids.add(case["id"])
            used_questions.add(question); used_titles.update(titles)
            if len(group) == 4:
                break
        if len(group) != 4:
            raise ValueError("Insufficient eligible amendment pilot questions: " + kind)
        selected.extend(group)
    if len(original_cohort["confirmatory"]) != 256 or len(original_cohort["generation_ids"]) != 128:
        raise ValueError("The original confirmation design must be preserved completely")
    return {"amendment": "01", "seed": SEED,
            "pilot": sorted(selected, key=lambda c: c["id"]),
            "confirmatory": original_cohort["confirmatory"],
            "generation_ids": original_cohort["generation_ids"],
            "seeds": {**original_cohort["seeds"], "pilot": AMENDMENT_PILOT_SEED},
            "exclusions_examined_before_targets_reached": dict(excluded),
            "selection": "Amendment 01 replaces all eight pilot questions using "
                         "seed 20261216. V1, V2 and both original V3 splits are "
                         "excluded by ID, normalized question and support title. "
                         "The original 256 confirmation cases and 128 generation "
                         "IDs are preserved exactly; no confirmation outcome was inspected."}


def amendment_cohort(rows, historical, v2, original_cohort, selected_utc):
    """Construct the complete hash-bound amendment record for freezing/replay."""
    result = select_amendment_cohorts(rows, historical + v2["pilot"] + v2["confirmatory"], original_cohort)
    result.update({"selected_utc": selected_utc,
                   "confirmation_selected_utc": original_cohort["selected_utc"],
                   "dataset_sha256": file_sha(ROOT / "data/hotpot-validation.parquet"),
                   "tokenizer_sha256": file_sha(ROOT / "data/qwen-tokenizer.json"),
                   "historical_inputs": {name: file_sha(ROOT / name) for name in
                                         (HISTORICAL_CASES, V2_COHORTS, "v3/data/cohorts.json")},
                   "historical_counts": {"v1": 64, "v2_pilot": 8, "v2_confirmatory": 256,
                                         "original_v3_pilot": 8, "original_v3_confirmatory": 256},
                   "original_registration_sha256": file_sha(LEGACY_REGISTRATION),
                   "prior_evidence_sha256": file_sha(ROOT / PRIOR_EVIDENCE)})
    return result


def freeze_cohorts():
    if COHORTS.exists():
        raise FileExistsError("V3 cohort already frozen; do not replace it")
    check_inputs()
    check_historical()
    check_prior_evidence()
    historical = read(ROOT / HISTORICAL_CASES)
    v2 = read(ROOT / V2_COHORTS)
    if (len(historical), len(v2["pilot"]), len(v2["confirmatory"])) != (64, 8, 256):
        raise ValueError("Historical cohort inventory differs")
    rows = pq.read_table(ROOT / "data/hotpot-validation.parquet").to_pylist()
    original_cohort = read(LEGACY_COHORTS)
    result = amendment_cohort(rows, historical, v2, original_cohort, utc())
    write_new(COHORTS, result)
    print("Frozen 8 pilot, 256 deterministic questions and 128 generation IDs.")
    return result


def registration_paths():
    paths = {ROOT / name for name in FROZEN_FILES} | set(BASE.glob("*.py"))
    if not (BASE / "design.py").is_file():
        raise ValueError("V3 design source is missing")
    for path in paths:
        if not path.is_file():
            raise ValueError(f"Frozen input is missing: {path.relative_to(ROOT)}")
    return sorted(paths)


def register():
    check_inputs()
    historical = check_historical()
    prior = check_prior_evidence()
    value = {"registered_utc": utc(),
             "git_base": subprocess.check_output(
                 ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
             "historical_commit": historical["baseline_commit"],
             "amendment": "01", "original_registration_commit": prior["original_registration_commit"],
             "original_registration_sha256": file_sha(LEGACY_REGISTRATION),
             "excluded_original_pilot": prior["original_failed_pilot"],
             "files": {str(path.relative_to(ROOT)): file_sha(path)
                       for path in registration_paths()},
             "sources_sha256": file_sha(ROOT / "sources.json"),
             "original_generator_source_sha256": file_sha(ROOT / "run.py"),
             "models": {role: original.MODELS[role]
                        for role in ("generator", "embedding")},
             "generation_options": original.OPTIONS,
             "source_provenance": "Publish this amendment and every frozen "
                                  "file before new pilot or confirmation outcomes. "
                                  "The failed original pilot remains excluded. Local "
                                  "Git checks do not prove public availability; "
                                  "record that evidence separately. Dates are real."}
    write_new(REGISTRATION, value)
    print("Registration created; publish the frozen instrument before collection.")
    return value


def registered():
    check_inputs()
    check_historical()
    check_prior_evidence()
    registration = read(REGISTRATION)
    required = {str(path.relative_to(ROOT)) for path in registration_paths()}
    if set(registration["files"]) != required:
        raise ValueError("Frozen V3 file set changed; an amendment is required")
    for name, expected in registration["files"].items():
        if file_sha(ROOT / name) != expected:
            raise ValueError(f"Frozen file changed: {name}; an amendment is required")
    committed = subprocess.run(["git", "show", "HEAD:" + str(REGISTRATION.relative_to(ROOT))],
                               cwd=ROOT, capture_output=True)
    if committed.returncode or committed.stdout != REGISTRATION.read_bytes():
        raise ValueError("Registration must be committed before outcomes")
    return registration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("cohorts", "register", "check"))
    args = parser.parse_args()
    if args.stage == "cohorts":
        freeze_cohorts()
    elif args.stage == "register":
        register()
    else:
        registered()
        print("Committed V3 registration and historical evidence verified.")


if __name__ == "__main__":
    main()
