"""Synthetic controls for offline evidence replay; no benchmark observations."""
import base64
import copy
import gzip
import json
from pathlib import Path
import random
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import run as original
from v2.benchmark import payload_for
from v2.core import answer_metrics, chunks, digest, documents, ranking
from v2.verify import checked_answer
from v3 import verify
from v3.core import context_metrics, context_redundancy, required_sentence_texts, select


PROOF = {"github_pull_request_created_at": "2026-11-15T12:00:00+00:00"}
INTENT_UTC = "2026-11-15T12:01:00+00:00"
RECORD_UTC = "2026-11-15T12:01:01+00:00"


class TestTokenizer:
    def encode(self, text):
        return SimpleNamespace(ids=list(range(len(text.split()))))


def synthetic_case():
    titles = [f"Synthetic document {index}" for index in range(10)]
    return {"id": "synthetic-question", "question": "Which synthetic document?",
            "type": "bridge", "answer": "Synthetic answer",
            "context": {"title": titles,
                        "sentences": [[f"Original synthetic sentence {index}."]
                                      for index in range(10)]},
            "supporting_facts": {"title": [titles[0]], "sent_id": [0]}}


def answer_fixture():
    case = synthetic_case()
    selected = chunks(documents(case))[:1]
    context = original.render_context(selected)
    key = case["id"] + ":bm25:ranked:512"
    job = {"id": key, "question_id": case["id"], "question": case["question"],
           "selected": selected, "context": context}
    answer = {"answer": case["answer"], "citations": [selected[0]["facts"][0]["id"]],
              "abstain": False}
    response = {"model": original.MODELS["generator"][0], "done": True,
                "done_reason": "stop", "prompt_eval_count": 50,
                "message": {"content": json.dumps(answer)}}
    payload = payload_for(job)
    intent = {"id": key, "utc": INTENT_UTC, "request": payload,
              "request_sha256": digest(payload)}
    record = {"id": key, "utc": RECORD_UTC, "request": payload,
              "request_sha256": digest(payload), "response": response,
              "response_body": json.dumps(response), "wall_seconds": 1.25,
              "answer": answer, "metrics": answer_metrics(case, job, answer)}
    return case, {key: job}, intent, record


class AnswerReplayTests(unittest.TestCase):
    def replay(self, intents=None, records=None):
        case, jobs, intent, record = answer_fixture()
        return verify.verify_answers(records if records is not None else [record],
                                     intents if intents is not None else [intent],
                                     jobs, {case["id"]: case}, set(jobs), PROOF)

    def test_exact_success_replays_without_a_model(self):
        result = self.replay()
        self.assertEqual((result["planned"], result["observed"], result["errors"]), (1, 1, 0))

    def test_duplicate_intent_detects_a_retry_even_when_response_is_unique(self):
        _, _, intent, _ = answer_fixture()
        with self.assertRaisesRegex(ValueError, "retried"):
            self.replay(intents=[intent, copy.deepcopy(intent)])

    def test_missing_observation_does_not_shrink_denominator(self):
        with self.assertRaisesRegex(ValueError, "denominator"):
            self.replay(records=[])

    def test_changed_payload_digest_or_scores_are_rejected(self):
        for field in ("request_sha256", "metrics"):
            _, _, _, record = answer_fixture()
            record[field] = "changed" if field == "request_sha256" else {**record[field], "answer_em": 0}
            with self.assertRaises(ValueError):
                self.replay(records=[record])

    def test_raw_output_failure_is_reproduced_and_keeps_zero_score(self):
        _, _, _, record = answer_fixture()
        record.pop("answer"); record.pop("metrics")
        record["response"]["done_reason"] = "length"
        record["response_body"] = json.dumps(record["response"])
        try:
            checked_answer(record["response"])
        except ValueError as error:
            record["error"] = f"{type(error).__name__}: {error}"
        result = self.replay(records=[record])
        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["output_failures_reconstructed"], 1)
        record["metrics"] = {"answer_em": 1}
        with self.assertRaisesRegex(ValueError, "successful scores"):
            self.replay(records=[record])

    def test_valid_response_cannot_be_relabelled_as_error(self):
        _, _, _, record = answer_fixture()
        record["error"] = "Chosen after reading the result"
        with self.assertRaisesRegex(ValueError, "relabelled"):
            self.replay(records=[record])

    def test_unobserved_transport_outcome_is_retained(self):
        _, _, _, record = answer_fixture()
        for name in ("answer", "metrics", "response", "response_body", "wall_seconds"):
            record.pop(name)
        record["error"] = "Interrupted after intent; response unobserved, not regenerated."
        self.assertEqual(self.replay(records=[record])["transport_or_unknown_failures"], 1)

    def test_malformed_http_and_non_utf8_bodies_are_preserved(self):
        for raw, status, message in (("{", 200, "Invalid JSON response"),
                                     ('{"error":"failure"}', 503, "HTTP 503"),
                                     (b"\xff", 200, "Invalid JSON response"),
                                     (b"\xff", 503, "HTTP 503")):
            _, _, _, record = answer_fixture()
            for name in ("answer", "metrics", "response", "response_body"):
                record.pop(name)
            record["http_status"] = status
            record["error"] = "RecordedRequestError: " + message
            record["response_body_base64" if isinstance(raw, bytes) else "response_body"] = (
                base64.b64encode(raw).decode() if isinstance(raw, bytes) else raw)
            self.assertEqual(self.replay(records=[record])["errors"], 1)

    def test_negative_nan_timing_and_prepublication_request_are_rejected(self):
        for value in (-1, float("nan"), float("inf")):
            _, _, _, record = answer_fixture()
            record["wall_seconds"] = value
            with self.assertRaisesRegex(ValueError, "recorded cost"):
                self.replay(records=[record])
        _, _, intent, _ = answer_fixture()
        intent["utc"] = "2026-11-14T12:00:00+00:00"
        with self.assertRaisesRegex(ValueError, "predates public"):
            self.replay(intents=[intent])


class PreparationReplayTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.base = self.root / "v3"; self.base.mkdir()
        self.out = self.base / "runs/pilot-controlled"; self.out.mkdir(parents=True)
        self.registration = self.base / "registration.json"; self.registration.write_text("{}\n")
        self.tokenizer = TestTokenizer(); self.case = synthetic_case()
        indexed = chunks(documents(self.case))
        self.vectors = {"search_query: " + self.case["question"]: [1., .5, .2]}
        for index, chunk in enumerate(indexed):
            self.vectors["search_document: " + chunk["text"]] = [1., float(index + 1), .5]
            for text in required_sentence_texts([chunk]):
                self.vectors[text] = [1., float(index + 1), .5]
        metadata = {"utc": RECORD_UTC, "registration_sha256": verify.file_sha(self.registration),
                    "models": json.loads(json.dumps(original.MODELS)),
                    "dependencies": {"numpy": "synthetic fixture"},
                    "python": "synthetic fixture", "scope": verify.EXECUTION_SCOPE}
        self.proof = {**PROOF, "registration_sha256": verify.file_sha(self.registration)}
        metadata["public_registration"] = self.proof
        (self.base / "environment.json").write_text(json.dumps({
            "dependencies": metadata["dependencies"], "python": metadata["python"]}))
        self.jobs = []; retrieval = []; sentence_inputs = set()
        for method in verify.METHODS:
            ranked = ranking(indexed, self.case["question"], method, self.vectors)
            retrieval.append({"question_id": self.case["id"], "retriever": method,
                              "indexed_chunks": len(ranked), "ranking_sha256": digest([c["id"] for c in ranked]),
                              "top_ten_sha256": digest(ranked[:10])})
            sentence_inputs.update(required_sentence_texts(ranked[:10]))
            for policy in verify.POLICIES:
                for budget in verify.BUDGETS:
                    selected = select(self.case["question"], ranked[:10], policy,
                                      budget, self.tokenizer, self.vectors)
                    self.jobs.append({"id": f"{self.case['id']}:{method}:{policy}:{budget}",
                                      "question_id": self.case["id"], "question": self.case["question"],
                                      "type": self.case["type"], "retriever": method,
                                      "policy": policy, "budget": budget, "split": "pilot",
                                      "environment": "controlled", "retrieved": ranked[:10],
                                      "selected": selected, "warm_selection_seconds": .01,
                                      "redundancy": context_redundancy(selected, self.vectors),
                                      **context_metrics(self.case, indexed, ranked, selected,
                                                        self.tokenizer, budget)})
        random.Random(verify.design.SEED + 5).shuffle(self.jobs)
        corpus = {d["key"]: d for d in documents(self.case)}
        counts = [len({"search_query: " + self.case["question"]}
                      | {"search_document: " + c["text"] for c in indexed}), len(sentence_inputs)]
        self.preparation = {**metadata, "split": "pilot", "environment": "controlled",
                            "scope": verify.PREPARATION_SCOPES["controlled"],
                            "questions": 1, "jobs": 16, "corpus_paragraphs": len(corpus),
                            "corpus_chunks": None, "corpus_sha256": digest([corpus[k] for k in sorted(corpus)]),
                            "retrieval": retrieval, "shared_ranking_wall_seconds": .01,
                            "embedding_preparation": [{"purpose": "pilot:controlled:" + stage,
                                "requested_unique": count, "cached_inputs": count,
                                "new_inputs": 0, "api_wall_seconds": 0., "packets": []}
                                for stage, count in zip(("retrieval", "sentences"), counts, strict=True)]}
        (self.out / "preparation-start.json").write_text(json.dumps(metadata))
        self.save()
        self.context = patch.multiple(verify, ROOT=self.root, BASE=self.base, REGISTRATION=self.registration)
        self.context.start()

    def tearDown(self):
        self.context.stop(); self.directory.cleanup()

    def save(self):
        (self.out / "jobs.json").write_text(json.dumps(self.jobs))
        self.preparation["jobs_sha256"] = verify.file_sha(self.out / "jobs.json")
        (self.out / "preparation.json").write_text(json.dumps(self.preparation))

    def replay(self):
        return verify.verify_preparation(self.out, [self.case], "pilot", "controlled",
                                         self.tokenizer, self.vectors, self.proof)

    def test_every_policy_replays_from_same_saved_candidates(self):
        jobs, packets = self.replay()
        self.assertEqual(len(jobs), 16); self.assertEqual(packets, [])

    def test_a_changed_source_sentence_is_rejected_even_with_updated_file_hash(self):
        self.jobs[0]["selected"][0]["facts"][0]["text"] = "Fabricated sentence"
        self.save()
        with self.assertRaises(ValueError):
            self.replay()

    def test_changed_top_ten_or_missing_condition_is_rejected(self):
        self.jobs[0]["retrieved"] = self.jobs[0]["retrieved"][:-1]
        self.save()
        with self.assertRaisesRegex(ValueError, "sequence differs"):
            self.replay()
        self.jobs.pop(); self.save()
        with self.assertRaisesRegex(ValueError, "deterministic jobs"):
            self.replay()

    def test_nonfinite_policy_cost_is_rejected(self):
        self.jobs[0]["warm_selection_seconds"] = float("nan")
        self.save()
        with self.assertRaisesRegex(ValueError, "recorded cost"):
            self.replay()

    def test_stage_scopes_are_distinct_but_each_is_validated(self):
        self.assertNotEqual(self.preparation["scope"], verify.EXECUTION_SCOPE)
        self.replay()
        self.preparation["scope"] = verify.EXECUTION_SCOPE
        self.save()
        with self.assertRaisesRegex(ValueError, "metadata.scope"):
            self.replay()
        self.preparation["scope"] = verify.PREPARATION_SCOPES["controlled"]
        self.save()
        path = self.out / "preparation-start.json"
        start = json.loads(path.read_text())
        start["scope"] = verify.PREPARATION_SCOPES["controlled"]
        path.write_text(json.dumps(start))
        with self.assertRaisesRegex(ValueError, "metadata.scope"):
            self.replay()


class ProtocolOnlyTests(unittest.TestCase):
    def test_absence_of_outcomes_is_explicit_and_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with patch.multiple(verify, BASE=base, ROOT=base), patch.object(
                    verify.design, "registered", return_value={"registered_utc": INTENT_UTC}), patch.object(
                    verify, "verify_cohorts", return_value={"selected_utc": PROOF["github_pull_request_created_at"]}):
                self.assertIn("no amendment outcomes", verify.verify(protocol_only=True)["status"])
                (base / "runs").mkdir(); (base / "runs/response.json").write_text("{}")
                with self.assertRaisesRegex(ValueError, "absence"):
                    verify.verify(protocol_only=True)

    def test_numeric_replay_checks_reject_nonfinite_values(self):
        with self.assertRaisesRegex(ValueError, "number differs"):
            verify.equal({"gain": float("nan")}, {"gain": .2})

    def test_only_hash_bound_prior_outcomes_and_gzip_aliases_are_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); base = root / "v3"; old = base / "runs/pilot-controlled"
            old.mkdir(parents=True)
            raw = old / "synthetic.json"; raw.write_text('{"synthetic":"prior"}\n')
            stored = raw.with_name(raw.name + ".gz")
            stored.write_bytes(gzip.compress(raw.read_bytes(), mtime=0))
            legacy = base / "amendments/01/retained-pilot-archive.json"
            legacy.parent.mkdir(parents=True)
            legacy.write_text(json.dumps({"schema": "alien6-rag-v3-lossless-archive-v1", "files": [{
                "source_path": str(raw.relative_to(root)), "path": str(stored.relative_to(root)),
                "encoding": "gzip", "bytes": stored.stat().st_size, "sha256": verify.file_sha(stored),
                "decoded_bytes": raw.stat().st_size, "decoded_sha256": verify.file_sha(raw)}]}))
            (legacy.parent / "prior-evidence.json").write_text(json.dumps({
                "files": {str(raw.relative_to(root)): verify.file_sha(raw),
                          str(legacy.relative_to(root)): verify.file_sha(legacy)},
                "inherited_embedding_packets": {}, "legacy_archive": str(legacy.relative_to(root))}))
            with patch.multiple(verify, ROOT=root, BASE=base), patch.object(
                    verify.design, "registered", return_value={"registered_utc": INTENT_UTC}), patch.object(
                    verify, "verify_cohorts", return_value={"selected_utc": PROOF["github_pull_request_created_at"]}):
                self.assertIn("no amendment outcomes", verify.verify(protocol_only=True)["status"])
                new = base / "runs" / verify.PILOT_RUN_NAME; new.mkdir()
                (new / "synthetic.json").write_text("{}")
                with self.assertRaisesRegex(ValueError, "absence"):
                    verify.verify(protocol_only=True)

    def test_new_packets_cannot_borrow_the_old_publication_epoch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); base = root / "v3"
            packets = base / "runs/embedding-traces"; packets.mkdir(parents=True)
            prior = base / "amendments/01/prior-evidence.json"; prior.parent.mkdir(parents=True)
            old = packets / "batch-00000.json.gz"
            old.write_bytes(gzip.compress(json.dumps({"utc": RECORD_UTC,
                                                     "registration_sha256": "old-registration"}).encode(), mtime=0))
            prior.write_text(json.dumps({"inherited_embedding_packets": {
                str(old.relative_to(root)): verify.file_sha(old)}}))
            old_proof = base / "public-registration.json"
            old_proof.write_text(json.dumps({**PROOF, "registration_sha256": "old-registration"}))
            proof = {"publication_kind": "release", "published_at": "2026-11-15T13:00:00Z",
                     "registration_sha256": "amendment-registration"}
            with patch.multiple(verify, ROOT=root, BASE=base), patch.object(
                    verify.design, "LEGACY_PUBLIC_REGISTRATION", old_proof):
                self.assertEqual(len(verify.verify_embedding_epochs(proof)), 1)
                new = packets / "batch-00001.json.gz"
                new.write_bytes(gzip.compress(json.dumps({"utc": RECORD_UTC,
                                                          "registration_sha256": "amendment-registration"}).encode(), mtime=0))
                with self.assertRaisesRegex(ValueError, "predates public"):
                    verify.verify_embedding_epochs(proof)


class TokenizerProbeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.out = Path(self.directory.name)
        self.tokenizer = TestTokenizer()
        self.records = []; self.intents = []
        for index, text in enumerate(verify.PROBES):
            payload = {"model": original.MODELS["generator"][0], "prompt": text,
                       "raw": True, "stream": False, "think": False,
                       "options": {**original.OPTIONS, "num_predict": 1}}
            count = len(self.tokenizer.encode(text).ids)
            response = {"model": original.MODELS["generator"][0], "done": True,
                        "prompt_eval_count": count}
            self.intents.append({"id": f"probe-{index}", "utc": INTENT_UTC,
                                 "request": payload, "request_sha256": digest(payload)})
            self.records.append({"id": f"probe-{index}", "utc": RECORD_UTC,
                                 "request": payload, "response_body": json.dumps(response),
                                 "tokenizer_tokens": count, "ollama_tokens": count,
                                 "wall_seconds": .1})
        self.save()

    def tearDown(self):
        self.directory.cleanup()

    def save(self):
        (self.out / "tokenizer-calibration.json").write_text(json.dumps(self.records))
        for name, rows in (("tokenizer-calibration-responses.jsonl", self.records),
                           ("tokenizer-calibration-intents.jsonl", self.intents)):
            (self.out / name).write_text("".join(json.dumps(row) + "\n" for row in rows))

    def test_original_three_probes_replay_without_generation(self):
        result = verify.verify_probes(self.out, self.tokenizer, PROOF)
        self.assertEqual(result, {"probes": 3, "model_calls_on_replay": 0})

    def test_changed_native_count_cannot_redefine_the_tokenizer(self):
        self.records[0]["ollama_tokens"] += 1
        body = json.loads(self.records[0]["response_body"])
        body["prompt_eval_count"] += 1
        self.records[0]["response_body"] = json.dumps(body)
        self.save()
        with self.assertRaisesRegex(ValueError, "tokenizer calibration"):
            verify.verify_probes(self.out, self.tokenizer, PROOF)

    def test_probe_retry_is_not_silently_accepted(self):
        self.intents.append(copy.deepcopy(self.intents[0])); self.save()
        with self.assertRaisesRegex(ValueError, "retried tokenizer probes"):
            verify.verify_probes(self.out, self.tokenizer, PROOF)


class PublicRegistrationTests(unittest.TestCase):
    def test_release_timestamp_takes_precedence_over_the_old_pull_request(self):
        proof = {**PROOF, "publication_kind": "release", "published_at": "2026-11-15T13:00:00Z"}
        with self.assertRaisesRegex(ValueError, "predates public"):
            verify.after_publication(RECORD_UTC, proof)
        verify.after_publication("2026-11-15T13:00:01+00:00", proof)

    def test_all_frozen_sources_must_exist_in_the_public_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); base = root / "v3"; base.mkdir()
            instrument = base / "instrument.py"; instrument.write_text("# frozen\n")
            registration_path = base / "registration.json"; registration_path.write_text("{}\n")
            registration = {"registered_utc": "2026-11-15T11:00:00+00:00",
                            "files": {"v3/instrument.py": verify.file_sha(instrument)}}
            proof = {**PROOF, "registration_sha256": verify.file_sha(registration_path),
                     "commit": "published-commit"}
            receipt = base / "public-registration-amendment-01.json"
            receipt.write_text(json.dumps(proof))
            def captured(command, **kwargs):
                name = command[-1].split(":", 1)[1]
                return SimpleNamespace(returncode=0, stdout=(root / name).read_bytes())
            cohort = {"selected_utc": "2026-11-15T10:00:00+00:00"}
            with patch.multiple(verify, ROOT=root, BASE=base, REGISTRATION=registration_path,
                                PUBLIC_REGISTRATION=receipt), patch.object(
                    verify.subprocess, "run", side_effect=captured):
                self.assertEqual(verify.verify_public_registration(registration, cohort), proof)
                with patch.object(verify.subprocess, "run", return_value=SimpleNamespace(
                        returncode=0, stdout=b"different public source")):
                    with self.assertRaisesRegex(ValueError, "public commit lacks"):
                        verify.verify_public_registration(registration, cohort)


class PilotGateTests(unittest.TestCase):
    def test_certificate_binds_probe_and_execution_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            registration = out / "registration.bin"; registration.write_text("{}\n")
            (out / "jobs.json").write_text("[]\n")
            (out / "answers.jsonl").write_text(json.dumps({"utc": RECORD_UTC}) + "\n")
            probe = out / "tokenizer-calibration-responses.jsonl"
            probe.write_text(json.dumps({"utc": RECORD_UTC}) + "\n")
            (out / "execution-1.json").write_text('{"metadata":"original"}\n')
            certificate = {"utc": "2026-11-15T12:02:00+00:00", "passed": True,
                           "questions": 8, "contexts": 128, "responses": 64, "errors": 0,
                           "registration_sha256": verify.file_sha(registration),
                           "jobs.json_sha256": verify.file_sha(out / "jobs.json"),
                           "answers.jsonl_sha256": verify.file_sha(out / "answers.jsonl"),
                           "evidence_sha256": {p.name: verify.file_sha(p) for p in out.iterdir()
                                               if p.suffix in (".json", ".jsonl")}}
            (out / "qualification.json").write_text(json.dumps(certificate))
            with patch.object(verify, "REGISTRATION", registration):
                receipt = {**PROOF, "registration_sha256": verify.file_sha(registration)}
                self.assertTrue(verify.verify_pilot_certificate(
                    out, {"observed": 64, "errors": 0}, receipt)["passed"])
                (out / "execution-1.json").write_text('{"metadata":"altered"}\n')
                with self.assertRaisesRegex(ValueError, "certificate evidence"):
                    verify.verify_pilot_certificate(out, {"observed": 64, "errors": 0}, receipt)

    def test_input_gate_runs_before_certificate_and_archive_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); out = base / "runs" / verify.PILOT_RUN_NAME
            out.mkdir(parents=True); (out / "execution-1.json").write_text("{}")
            cases = [{"id": f"synthetic-{i}"} for i in range(8)]
            jobs = {f"{c['id']}:{method}:{policy}:{budget}": {"budget": budget}
                    for c in cases for method in verify.METHODS
                    for policy in verify.POLICIES for budget in verify.BUDGETS}
            result = {"observed": 64, "errors": 0}
            with patch.object(verify, "BASE", base), patch.object(verify.design, "registered", return_value={}), patch.object(
                    verify, "verify_cohorts", return_value={"pilot": cases}), patch.object(
                    verify, "verify_public_registration", return_value=PROOF), patch.object(
                    verify.Tokenizer, "from_file", return_value=TestTokenizer()), patch.object(
                    verify, "load_vectors", return_value={}), patch.object(
                    verify, "verify_preparation", return_value=(jobs, [])), patch.object(
                    verify, "verify_answers", return_value=result), patch.object(
                    verify, "verify_probes", return_value={"probes": 3}), patch.object(
                    verify, "verify_metadata"):
                self.assertTrue(verify.verify_pilot_inputs()["passed"])
                self.assertFalse((out / "qualification.json").exists())
                self.assertFalse((base / "archive-manifest.json").exists())
                result["errors"] = 1
                with self.assertRaisesRegex(ValueError, "recorded failure"):
                    verify.verify_pilot_inputs()


if __name__ == "__main__":
    unittest.main()
