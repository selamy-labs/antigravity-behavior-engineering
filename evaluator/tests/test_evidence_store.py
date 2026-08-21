from __future__ import annotations

import copy
import json
import stat
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

import abe_eval.evidence as evidence_module
from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.classify import classify
from abe_eval.contracts import ContractValidationError, canonical_contract_digest, parse_contract
from abe_eval.evidence import import_run
from abe_eval.runner import RunAttemptInputs, run_attempt
from abe_eval.schedule import build_schedule
from fakes.fake_worker import MATRIX, FakeWorker


BLOCK_FIXTURE = Path("evals/protocols/fake-block.json")
CONTRACT_FIXTURES = Path("tests/contract/fixtures/evaluation-contracts.json")


def _digest(seed: str) -> str:
    return "sha256:" + (seed * 64)[:64]


def _case_value(name: str) -> dict[str, object]:
    fixture = json.loads(CONTRACT_FIXTURES.read_text())
    for case in fixture["validCases"]:
        if case["name"] == name:
            return copy.deepcopy(case["value"])
    raise AssertionError(name)


def _policy_body_digest(policy: dict[str, object]) -> str:
    body = copy.deepcopy(policy)
    body.pop("policyDigest", None)
    return sha256_digest(canonical_bytes(body))


def _policy() -> dict[str, object]:
    reason_codes = sorted({str(value["reasonCode"]) for value in MATRIX.values()})
    policy = {
        "schemaVersion": 1,
        "policyId": "classification-policy-t008",
        "reasonCodes": [
            {"schemaVersion": 1, "reasonCode": reason_code, "priority": index + 1}
            for index, reason_code in enumerate(reason_codes)
        ],
        "replacementCaps": {
            "adapter_failure": 1,
            "malformed_ndjson": 1,
            "pre_start_auth_failure": 1,
            "test_flake": 1,
            "truncated_ndjson": 1,
        },
        "validRunProjection": "gradable_only",
        "policyDigest": _digest("df"),
    }
    policy["policyDigest"] = _policy_body_digest(policy)
    return policy


def _environment() -> dict[str, object]:
    env = _case_value("EnvironmentQualificationRecord")
    env["cliDigest"] = _digest("a")
    return parse_contract("EnvironmentQualificationRecord", env)


def _attempt(condition_id: str = "bare") -> dict[str, object]:
    payload = json.loads(BLOCK_FIXTURE.read_text())
    attempt = parse_contract("ScheduledAttempt", build_schedule(payload["block"], payload["seed"])[0])
    attempt["conditionId"] = condition_id
    return parse_contract("ScheduledAttempt", attempt)


def _scenario(attempt: dict[str, object], policy: dict[str, object]) -> dict[str, object]:
    scenario = _case_value("ScenarioCard")
    scenario["scenarioId"] = attempt["scenarioId"]
    scenario["classificationPolicyDigest"] = policy["policyDigest"]
    return parse_contract("ScenarioCard", scenario)


def _condition(
    condition_id: str,
    *,
    environment: dict[str, object],
    scenario: dict[str, object],
) -> dict[str, object]:
    return parse_contract(
        "ConditionLock",
        {
            "schemaVersion": 1,
            "conditionId": condition_id,
            "modelRequest": "gemini-3.7-flash-high",
            "reasoningRequest": "high",
            "provider": "google",
            "authenticationMode": "scoped",
            "fallbackPolicy": "deny",
            "agentSelection": "antigravity",
            "subagentSelection": "not_applicable",
            "rawInvocation": {
                "schemaVersion": 1,
                "argv": ["agy", "--model", "gemini-3.7-flash-high", "--effort", "high"],
                "environment": {"AGY_PROFILE": "fresh"},
            },
            "cliDigest": environment["cliDigest"],
            "pluginDigest": _digest("b"),
            "dependencyDigests": {"superpowers": _digest("c")},
            "enabledComponents": [] if condition_id == "bare" else ["verification-before-completion"],
            "authorityManifestDigest": canonical_contract_digest("AuthorityManifest", scenario["authorityManifest"]),
            "resourceEnvelopeDigest": canonical_contract_digest("ResourceEnvelope", scenario["resourceEnvelope"]),
            "toolInventoryDigest": _digest("f"),
            "permissionDigest": _digest("1"),
            "environmentDigest": _digest("2"),
            "environmentQualificationDigest": canonical_contract_digest("EnvironmentQualificationRecord", environment),
        },
    )


def _stage_classified_attempt(tmp_path: Path, case_id: str = "success") -> tuple[Path, dict[str, object], dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    policy = _policy()
    attempt = _attempt("bare")
    scenario = _scenario(attempt, policy)
    environment = _environment()
    condition_id = "full" if case_id == "invalid_controller_input" else "bare"
    condition = _condition(condition_id, environment=environment, scenario=scenario)
    unclassified = run_attempt(
        RunAttemptInputs(
            scheduled_attempt=attempt,
            condition=condition,
            scenario=scenario,
            environment_qualification=environment,
            raw_root=tmp_path,
        ),
        FakeWorker(case_id),
    )
    staged = classify(unclassified, policy, expected_policy_digest=str(policy["policyDigest"]))
    staging = tmp_path / "staged" / str(attempt["runId"])
    (staging / "staged-outcome.json").write_bytes(canonical_bytes(staged) + b"\n")
    return staging, attempt, condition, scenario, environment, staged


def _read_lifecycle(root: Path, attempt_id: str) -> list[dict[str, object]]:
    lifecycle = root / "attempts" / attempt_id / "lifecycle.ndjson"
    return [json.loads(line) for line in lifecycle.read_text().splitlines() if line]


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.write_bytes(canonical_bytes(value) + b"\n")


def _write_lifecycle(root: Path, attempt_id: str, events: list[dict[str, object]]) -> None:
    lifecycle = root / "attempts" / attempt_id / "lifecycle.ndjson"
    lifecycle.write_bytes(b"".join(canonical_bytes(parse_contract("AttemptLifecycleEvent", event)) + b"\n" for event in events))


def _rewrite_outcomes(staging: Path, unclassified: dict[str, object], staged: dict[str, object]) -> None:
    staged["unclassifiedOutcomeDigest"] = canonical_contract_digest("UnclassifiedStagedAttemptOutcome", unclassified)
    _write_json(staging / "unclassified-outcome.json", parse_contract("UnclassifiedStagedAttemptOutcome", unclassified))
    _write_json(staging / "staged-outcome.json", parse_contract("StagedAttemptOutcome", staged))


def _rewrite_paired_outcomes(staging: Path, mutator: Callable[[dict[str, object]], None]) -> None:
    unclassified = json.loads((staging / "unclassified-outcome.json").read_text())
    staged = json.loads((staging / "staged-outcome.json").read_text())
    mutator(unclassified)
    mutator(staged)
    _rewrite_outcomes(staging, unclassified, staged)


def _rewrite_manifest_and_bind_outcomes(staging: Path, manifest: dict[str, object]) -> None:
    _write_json(staging / "staging-manifest.json", manifest)
    digest = sha256_digest(canonical_bytes(manifest))

    def update_manifest_digest(outcome: dict[str, object]) -> None:
        outcome["stagingManifestDigest"] = digest

    _rewrite_paired_outcomes(staging, update_manifest_digest)


def _present_staged_files(staging: Path) -> dict[str, str]:
    manifest = json.loads((staging / "staging-manifest.json").read_text())
    return {
        entry["path"]: (staging / "output" / entry["path"]).read_text()
        for entry in manifest["entries"]
        if entry["present"]
    }


def _terminal_evidence_from_staged(staging: Path, staged: dict[str, object], terminal_kind: str) -> dict[str, object]:
    process = staged["processState"]
    return {
        "terminalKind": terminal_kind,
        "controllerExitCode": process["controllerExitCode"],
        "workerExitCode": process["workerExitCode"],
        "signal": process["signal"],
        "timeout": process["timeout"],
        "agentDeclaredState": staged["agentDeclaredState"],
        "inputPermissionState": staged["inputPermissionState"],
        "infrastructureValidity": staged["infrastructureValidity"],
        "consumption": staged["consumption"],
        "observedModel": staged["observedModel"],
        "stagedFiles": _present_staged_files(staging),
    }


def _rewrite_started_terminal_evidence_and_outcomes(
    tmp_path: Path,
    staging: Path,
    attempt_id: str,
    mutator: Callable[[dict[str, object]], None],
) -> None:
    unclassified = json.loads((staging / "unclassified-outcome.json").read_text())
    staged = json.loads((staging / "staged-outcome.json").read_text())
    mutator(unclassified)
    mutator(staged)
    events = _read_lifecycle(tmp_path, attempt_id)
    events[-1]["evidenceDigest"] = sha256_digest(
        canonical_bytes(_terminal_evidence_from_staged(staging, staged, str(events[-1]["terminalKind"])))
    )
    _write_lifecycle(tmp_path, attempt_id, events)
    digests = [canonical_contract_digest("AttemptLifecycleEvent", event) for event in events]
    unclassified["lifecycleEventDigests"] = digests
    staged["lifecycleEventDigests"] = digests
    _rewrite_outcomes(staging, unclassified, staged)


def _rewrite_outcomes_with_lifecycle_digests(tmp_path: Path, staging: Path, attempt_id: str) -> None:
    events = _read_lifecycle(tmp_path, attempt_id)
    digests = [canonical_contract_digest("AttemptLifecycleEvent", event) for event in events]
    unclassified = json.loads((staging / "unclassified-outcome.json").read_text())
    staged = json.loads((staging / "staged-outcome.json").read_text())
    unclassified["lifecycleEventDigests"] = digests
    staged["lifecycleEventDigests"] = digests
    _rewrite_outcomes(staging, unclassified, staged)


def test_import_run_content_addresses_raw_evidence_and_finalizes_once(tmp_path):
    staging, attempt, condition, scenario, environment, staged = _stage_classified_attempt(tmp_path)

    run = import_run(staging, attempt, condition, scenario, environment, tmp_path)

    parsed_run = parse_contract("RunRecord", run)
    assert parsed_run == run
    assert run["runId"] == attempt["runId"]
    assert run["attemptId"] == attempt["attemptId"]
    assert run["conditionDigest"] == canonical_contract_digest("ConditionLock", condition)
    assert run["scenarioDigest"] == canonical_contract_digest("ScenarioCard", scenario)
    assert run["environmentQualificationDigest"] == canonical_contract_digest("EnvironmentQualificationRecord", environment)
    assert run["classification"] == staged["classification"]
    assert run["redactedEvidenceLocator"] == "not_redacted"

    run_json = tmp_path / "runs" / str(attempt["runId"]) / "run.json"
    original_run_bytes = run_json.read_bytes()
    assert stat.S_IMODE(run_json.stat().st_mode) & stat.S_IWUSR == 0
    assert json.loads(original_run_bytes) == run

    raw_locator = Path(str(run["rawEvidenceLocator"]))
    assert not raw_locator.is_absolute()
    assert ".." not in raw_locator.parts
    assert raw_locator.parts[:4] == ("runs", str(run["runId"]), "artifacts", "sha256")
    raw_manifest_path = tmp_path / raw_locator
    assert stat.S_IMODE(raw_manifest_path.stat().st_mode) & stat.S_IWUSR == 0
    raw_manifest = json.loads(raw_manifest_path.read_bytes())
    assert run["artifactManifestDigest"] == sha256_digest(canonical_bytes(raw_manifest))

    entries = {entry["path"]: entry for entry in raw_manifest["entries"]}
    assert entries["raw-stream.ndjson"]["digest"] == run["transcriptDigest"]
    assert entries["process.json"]["digest"] != "none"
    assert entries["stdout.txt"]["present"] is False
    for entry in raw_manifest["entries"]:
        assert entry["sourceZone"] == "protected_raw_staging"
        assert entry["redactionDisposition"] == "protected_only_pending_redaction"
        assert isinstance(entry["mediaType"], str) and entry["mediaType"]
        if not entry["present"]:
            assert entry["digest"] == "none"
            continue
        object_locator = Path(str(entry["objectLocator"]))
        assert object_locator.parts[:4] == ("runs", str(run["runId"]), "artifacts", "sha256")
        object_path = tmp_path / str(entry["objectLocator"])
        assert stat.S_IMODE(object_path.stat().st_mode) & stat.S_IWUSR == 0
        staged_bytes = (staging / "output" / entry["path"]).read_bytes()
        assert object_path.read_bytes() == staged_bytes
        assert sha256_digest(staged_bytes) == entry["digest"]

    events = _read_lifecycle(tmp_path, str(attempt["attemptId"]))
    assert [event["phase"] for event in events] == ["scheduled", "preflight", "valid_started", "execution_terminal", "run_finalized"]
    assert events[-1]["terminalKind"] == "none"
    assert events[-1]["evidenceDigest"] == canonical_contract_digest("RunRecord", run)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)
    assert excinfo.value.reason_code == "evidence.run_already_finalized"
    assert run_json.read_bytes() == original_run_bytes


def test_import_run_finalizes_pre_worker_controller_failure_with_explicit_missing_outputs(tmp_path):
    staging, attempt, condition, scenario, environment, staged = _stage_classified_attempt(tmp_path, "invalid_controller_input")

    run = import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert run["processState"]["workerProcessState"] == "not_started"
    assert run["classification"]["reasonCode"] == "invalid_controller_input"
    assert run["transcriptDigest"] == "none"
    raw_manifest = json.loads((tmp_path / str(run["rawEvidenceLocator"])).read_bytes())
    entries = {entry["path"]: entry for entry in raw_manifest["entries"]}
    assert entries["raw-stream.ndjson"]["present"] is False
    assert entries["raw-stream.ndjson"]["digest"] == "none"
    assert entries["raw-stream.ndjson"]["byteLength"] == 0
    assert entries["process.json"]["present"] is False
    assert entries["process.json"]["digest"] == "none"
    assert entries["process.json"]["byteLength"] == 0
    assert staged["classification"]["countsInValidRun"] is False
    assert _read_lifecycle(tmp_path, str(attempt["attemptId"]))[-1]["phase"] == "run_finalized"


def test_import_run_rejects_missing_required_staged_output_without_fabricating_empty_transcript(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    (staging / "output" / "raw-stream.ndjson").unlink()

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.missing_staged_output"
    assert excinfo.value.path == "$.output.raw-stream.ndjson"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()
    assert not any((tmp_path / "objects").rglob("*")) if (tmp_path / "objects").exists() else True


@pytest.mark.parametrize("unsafe_name", ["../escape.txt", "nested/escape.txt", "bad\\\\name.txt", "nul\x00name.txt"])
def test_import_run_rejects_unsafe_staged_output_paths_before_finalization(tmp_path, unsafe_name):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    manifest_path = staging / "staging-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["entries"].append({"path": unsafe_name, "present": True, "digest": _digest("ef"), "byteLength": 1})
    manifest_path.write_bytes(canonical_bytes(manifest) + b"\n")

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.unsafe_staged_path"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_requires_explicit_missing_marker_for_every_runner_output(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    manifest_path = staging / "staging-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["entries"] = [entry for entry in manifest["entries"] if entry["path"] != "stderr.txt"]
    _write_json(manifest_path, manifest)
    unclassified = json.loads((staging / "unclassified-outcome.json").read_text())
    staged = json.loads((staging / "staged-outcome.json").read_text())
    unclassified["stagingManifestDigest"] = sha256_digest(canonical_bytes(manifest))
    staged["stagingManifestDigest"] = sha256_digest(canonical_bytes(manifest))
    _rewrite_outcomes(staging, unclassified, staged)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.missing_staged_output_marker"
    assert excinfo.value.path == "$.output.stderr.txt"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_staging_manifest_run_id_relabel_even_when_digest_matches(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    manifest = json.loads((staging / "staging-manifest.json").read_text())
    manifest["runId"] = "other-run-id"
    _rewrite_manifest_and_bind_outcomes(staging, manifest)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.stagingManifest.runId"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_manifested_unknown_staged_output_even_when_terminal_digest_matches(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    extra = staging / "output" / "extra.txt"
    extra.write_text("extra evidence\n")
    manifest = json.loads((staging / "staging-manifest.json").read_text())
    extra_data = extra.read_bytes()
    manifest["entries"].append(
        {"path": "extra.txt", "present": True, "digest": sha256_digest(extra_data), "byteLength": len(extra_data)}
    )
    _rewrite_manifest_and_bind_outcomes(staging, manifest)
    _rewrite_started_terminal_evidence_and_outcomes(tmp_path, staging, str(attempt["attemptId"]), lambda _outcome: None)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.unexpected_staged_output"
    assert excinfo.value.path == "$.entries[10].path"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_symlinked_staged_output(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    target = tmp_path / "outside-secret.txt"
    target.write_text("do not import\n")
    raw_stream = staging / "output" / "raw-stream.ndjson"
    raw_stream.unlink()
    raw_stream.symlink_to(target)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.symlink_staged_output"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_unmanifested_staged_output_before_finalization(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    (staging / "output" / "unmanifested-extra.txt").write_text("extra\n")

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.unmanifested_staged_output"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_unmanifested_staged_symlink_before_finalization(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    target = tmp_path / "outside-secret.txt"
    target.write_text("do not import\n")
    (staging / "output" / "unmanifested-link.txt").symlink_to(target)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.symlink_staged_output"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_supplied_attempt_that_differs_from_stored_attempt(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    tampered_attempt = copy.deepcopy(attempt)
    tampered_attempt["scheduledAt"] = "2026-08-18T13:09:00Z"
    tampered_attempt = parse_contract("ScheduledAttempt", tampered_attempt)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, tampered_attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.attemptDigest"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_lifecycle_event_digest_that_does_not_bind_attempt(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    lifecycle_path = tmp_path / "attempts" / str(attempt["attemptId"]) / "lifecycle.ndjson"
    events = _read_lifecycle(tmp_path, str(attempt["attemptId"]))
    events[0]["evidenceDigest"] = _digest("ab")
    lifecycle_path.write_bytes(b"".join(canonical_bytes(parse_contract("AttemptLifecycleEvent", event)) + b"\n" for event in events))
    _rewrite_outcomes_with_lifecycle_digests(tmp_path, staging, str(attempt["attemptId"]))

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.lifecycleEventDigests[0].evidenceDigest"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_lifecycle_event_attempt_id_relabel_even_when_digests_match(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    events = _read_lifecycle(tmp_path, str(attempt["attemptId"]))
    for event in events:
        event["attemptId"] = "wrong-attempt-id"
    _write_lifecycle(tmp_path, str(attempt["attemptId"]), events)
    _rewrite_outcomes_with_lifecycle_digests(tmp_path, staging, str(attempt["attemptId"]))

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.lifecycleEventDigests[0].attemptId"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_terminal_lifecycle_event_digest_that_does_not_bind_worker_result(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    events = _read_lifecycle(tmp_path, str(attempt["attemptId"]))
    events[-1]["evidenceDigest"] = _digest("34")
    _write_lifecycle(tmp_path, str(attempt["attemptId"]), events)
    _rewrite_outcomes_with_lifecycle_digests(tmp_path, staging, str(attempt["attemptId"]))

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.lifecycleEventDigests[3].evidenceDigest"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_classification_policy_digest_relabel(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    staged = json.loads((staging / "staged-outcome.json").read_text())
    staged["classification"]["policyDigest"] = _digest("12")
    _write_json(staging / "staged-outcome.json", parse_contract("StagedAttemptOutcome", staged))

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.classification.policyDigest"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_classification_reason_relabel(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    staged = json.loads((staging / "staged-outcome.json").read_text())
    staged["classification"].update(
        {
            "class": "product_failure",
            "reasonCode": "product_timeout",
            "retryEligible": False,
            "countsInValidRun": False,
        }
    )
    _write_json(staging / "staged-outcome.json", parse_contract("StagedAttemptOutcome", staged))

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.classification.reasonCode"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_classification_retry_eligibility_relabel(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    staged = json.loads((staging / "staged-outcome.json").read_text())
    staged["classification"]["retryEligible"] = True
    _write_json(staging / "staged-outcome.json", parse_contract("StagedAttemptOutcome", staged))

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.classification.retryEligible"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_started_attempt_with_failed_preflight_relabel(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)

    def fail_authentication(outcome: dict[str, object]) -> None:
        outcome["attemptQualification"]["authentication"]["result"] = "fail"

    _rewrite_paired_outcomes(staging, fail_authentication)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.attemptQualification.authentication.result"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_preflight_evidence_digest_relabel(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)

    def relabel_preflight_digest(outcome: dict[str, object]) -> None:
        outcome["attemptQualification"]["authentication"]["evidenceDigest"] = _digest("12")

    _rewrite_paired_outcomes(staging, relabel_preflight_digest)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.attemptQualification.authentication.evidenceDigest"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_not_started_attempt_without_failed_preflight_relabel(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path, "invalid_controller_input")

    def pass_all_preflights(outcome: dict[str, object]) -> None:
        for key, value in outcome["attemptQualification"].items():
            if isinstance(value, dict) and "result" in value:
                value["result"] = "pass"

    _rewrite_paired_outcomes(staging, pass_all_preflights)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.attemptQualification"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_pre_worker_terminal_state_relabel(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path, "invalid_controller_input")
    unclassified = json.loads((staging / "unclassified-outcome.json").read_text())
    staged = json.loads((staging / "staged-outcome.json").read_text())
    unclassified["processState"]["controllerExitCode"] = 0
    staged["processState"]["controllerExitCode"] = 0
    _rewrite_outcomes(staging, unclassified, staged)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.processState.controllerExitCode"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_pre_worker_infrastructure_relabel(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path, "invalid_controller_input")

    def relabel_infrastructure(outcome: dict[str, object]) -> None:
        outcome["infrastructureValidity"] = "valid"

    _rewrite_paired_outcomes(staging, relabel_infrastructure)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.infrastructureValidity"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_pre_worker_stderr_digest_relabel(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path, "invalid_controller_input")

    def relabel_stderr_digest(outcome: dict[str, object]) -> None:
        outcome["processState"]["stderrDigest"] = _digest("99")

    _rewrite_paired_outcomes(staging, relabel_stderr_digest)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.processState.stderrDigest"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_pre_worker_observed_model_relabel(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path, "invalid_controller_input")

    def relabel_observed_model(outcome: dict[str, object]) -> None:
        outcome["observedModel"]["servedIdentityEvidence"][0]["value"] = "claimed"

    _rewrite_paired_outcomes(staging, relabel_observed_model)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.observedModel.servedIdentityEvidence"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_pre_worker_consumption_relabel(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path, "invalid_controller_input")

    def relabel_consumption(outcome: dict[str, object]) -> None:
        outcome["consumption"]["toolCalls"] = 123

    _rewrite_paired_outcomes(staging, relabel_consumption)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.consumption"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


@pytest.mark.parametrize(
    ("field", "value", "path"),
    [
        ("workerProcessState", "started", "$.processState.workerProcessState"),
        ("startedAt", "2026-08-18T12:09:59Z", "$.processState.startedAt"),
        ("stderrDigest", _digest("99"), "$.processState.stderrDigest"),
    ],
)
def test_import_run_rejects_started_process_state_relabel(tmp_path, field, value, path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)

    def relabel_process(outcome: dict[str, object]) -> None:
        outcome["processState"][field] = value

    _rewrite_paired_outcomes(staging, relabel_process)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == path
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_valid_started_invalid_controller_relabel_even_when_terminal_digest_matches(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)

    def relabel_as_controller_input_failure(outcome: dict[str, object]) -> None:
        outcome["infrastructureValidity"] = "invalid_controller_input"
        if "classification" in outcome:
            outcome["classification"] = {
                "schemaVersion": 1,
                "policyDigest": outcome["classification"]["policyDigest"],
                "reasonCode": "invalid_controller_input",
                "class": "infrastructure_failure",
                "countsInIntentionToTreat": True,
                "countsInValidRun": False,
                "retryEligible": False,
            }

    _rewrite_started_terminal_evidence_and_outcomes(
        tmp_path, staging, str(attempt["attemptId"]), relabel_as_controller_input_failure
    )

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.infrastructureValidity"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_timeout_terminal_kind_relabel_to_adapter_failure(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path, "valid_start_timeout")
    unclassified = json.loads((staging / "unclassified-outcome.json").read_text())
    staged = json.loads((staging / "staged-outcome.json").read_text())
    unclassified["infrastructureValidity"] = "adapter_failure"
    staged["infrastructureValidity"] = "adapter_failure"
    events = _read_lifecycle(tmp_path, str(attempt["attemptId"]))
    events[-1]["terminalKind"] = "adapter_failure"
    events[-1]["evidenceDigest"] = sha256_digest(
        canonical_bytes(_terminal_evidence_from_staged(staging, staged, str(events[-1]["terminalKind"])))
    )
    _write_lifecycle(tmp_path, str(attempt["attemptId"]), events)
    digests = [canonical_contract_digest("AttemptLifecycleEvent", event) for event in events]
    unclassified["lifecycleEventDigests"] = digests
    staged["lifecycleEventDigests"] = digests
    _rewrite_outcomes(staging, unclassified, staged)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.lifecycleEventDigests[3].terminalKind"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_observed_model_relabel_even_when_terminal_digest_matches(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)

    def relabel_observed_model(outcome: dict[str, object]) -> None:
        outcome["observedModel"]["requestedModel"] = "gemini-3.1-pro-high"
        outcome["observedModel"]["requestedReasoning"] = "medium"

    _rewrite_started_terminal_evidence_and_outcomes(tmp_path, staging, str(attempt["attemptId"]), relabel_observed_model)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.observedModel.requestedModel"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_terminal_kind_relabel_even_with_matching_terminal_digest(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    staged = json.loads((staging / "staged-outcome.json").read_text())
    process = staged["processState"]
    staged_files = {
        entry["path"]: (staging / "output" / entry["path"]).read_text()
        for entry in json.loads((staging / "staging-manifest.json").read_text())["entries"]
        if entry["present"]
    }
    terminal_evidence = {
        "terminalKind": "adapter_failure",
        "controllerExitCode": process["controllerExitCode"],
        "workerExitCode": process["workerExitCode"],
        "signal": process["signal"],
        "timeout": process["timeout"],
        "agentDeclaredState": staged["agentDeclaredState"],
        "inputPermissionState": staged["inputPermissionState"],
        "infrastructureValidity": staged["infrastructureValidity"],
        "consumption": staged["consumption"],
        "observedModel": staged["observedModel"],
        "stagedFiles": staged_files,
    }
    events = _read_lifecycle(tmp_path, str(attempt["attemptId"]))
    events[-1]["terminalKind"] = "adapter_failure"
    events[-1]["evidenceDigest"] = sha256_digest(canonical_bytes(terminal_evidence))
    _write_lifecycle(tmp_path, str(attempt["attemptId"]), events)
    _rewrite_outcomes_with_lifecycle_digests(tmp_path, staging, str(attempt["attemptId"]))

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.lifecycleEventDigests[3].terminalKind"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_condition_id_cross_bind_that_is_not_controller_failure(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    tampered_condition = copy.deepcopy(condition)
    tampered_condition["conditionId"] = "full"
    tampered_condition["enabledComponents"] = ["verification-before-completion"]
    tampered_condition = parse_contract("ConditionLock", tampered_condition)
    events = _read_lifecycle(tmp_path, str(attempt["attemptId"]))
    events[1]["evidenceDigest"] = sha256_digest(canonical_bytes({"condition": tampered_condition, "scenario": scenario}))
    _write_lifecycle(tmp_path, str(attempt["attemptId"]), events)
    digests = [canonical_contract_digest("AttemptLifecycleEvent", event) for event in events]
    tampered_condition_digest = canonical_contract_digest("ConditionLock", tampered_condition)
    unclassified = json.loads((staging / "unclassified-outcome.json").read_text())
    staged = json.loads((staging / "staged-outcome.json").read_text())
    unclassified["conditionDigest"] = tampered_condition_digest
    staged["conditionDigest"] = tampered_condition_digest
    unclassified["lifecycleEventDigests"] = digests
    staged["lifecycleEventDigests"] = digests
    _rewrite_outcomes(staging, unclassified, staged)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, tampered_condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.conditionDigest"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_valid_start_time_that_disagrees_with_lifecycle(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    unclassified = json.loads((staging / "unclassified-outcome.json").read_text())
    staged = json.loads((staging / "staged-outcome.json").read_text())
    unclassified["attemptQualification"]["validStartAt"] = "2026-08-18T12:10:01Z"
    staged["attemptQualification"]["validStartAt"] = "2026-08-18T12:10:01Z"
    _rewrite_outcomes(staging, unclassified, staged)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.attemptQualification.validStartAt"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_rejects_condition_environment_qualification_mismatch(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    tampered_condition = copy.deepcopy(condition)
    tampered_condition["environmentQualificationDigest"] = _digest("cd")
    tampered_condition = parse_contract("ConditionLock", tampered_condition)
    tampered_condition_digest = canonical_contract_digest("ConditionLock", tampered_condition)
    unclassified = json.loads((staging / "unclassified-outcome.json").read_text())
    staged = json.loads((staging / "staged-outcome.json").read_text())
    unclassified["conditionDigest"] = tampered_condition_digest
    staged["conditionDigest"] = tampered_condition_digest
    _rewrite_outcomes(staging, unclassified, staged)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, tampered_condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.environmentQualificationDigest"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_import_run_requires_bindings_to_controller_objects(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    tampered_condition = copy.deepcopy(condition)
    tampered_condition["conditionId"] = "full"
    tampered_condition["enabledComponents"] = ["verification-before-completion"]
    tampered_condition = parse_contract("ConditionLock", tampered_condition)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, tampered_condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.binding_mismatch"
    assert excinfo.value.path == "$.conditionDigest"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_concurrent_import_publishes_one_run_without_changing_bytes(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)

    successes: list[dict[str, object]] = []
    failures: list[ContractValidationError] = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(import_run, staging, attempt, condition, scenario, environment, tmp_path) for _ in range(2)]
        for future in as_completed(futures):
            try:
                successes.append(future.result())
            except ContractValidationError as exc:
                failures.append(exc)

    assert len(successes) == 1
    assert [failure.reason_code for failure in failures] == ["evidence.run_already_finalized"]
    first = successes[0]
    first_bytes = (tmp_path / "runs" / str(attempt["runId"]) / "run.json").read_bytes()
    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.run_already_finalized"
    assert (tmp_path / "runs" / str(attempt["runId"]) / "run.json").read_bytes() == first_bytes
    assert json.loads(first_bytes) == first
    assert [event["phase"] for event in _read_lifecycle(tmp_path, str(attempt["attemptId"]))].count("run_finalized") == 1


def test_import_run_does_not_publish_run_json_when_lifecycle_append_is_not_available(tmp_path):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    lifecycle_path = tmp_path / "attempts" / str(attempt["attemptId"]) / "lifecycle.ndjson"
    lifecycle_path.chmod(0o400)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.lifecycle_not_appendable"
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()
    assert _read_lifecycle(tmp_path, str(attempt["attemptId"]))[-1]["phase"] == "execution_terminal"


def test_import_run_rolls_back_run_directory_when_lifecycle_append_write_fails(tmp_path, monkeypatch):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    run_dir = tmp_path / "runs" / str(attempt["runId"])

    def fail_append(_stream, _event):
        raise ContractValidationError("evidence.lifecycle_not_appendable", "$.attemptId")

    monkeypatch.setattr(evidence_module, "_append_run_finalized_event", fail_append)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.lifecycle_not_appendable"
    assert not run_dir.exists()
    assert _read_lifecycle(tmp_path, str(attempt["attemptId"]))[-1]["phase"] == "execution_terminal"


def test_import_run_keeps_run_when_lifecycle_append_failure_left_final_event_visible(tmp_path, monkeypatch):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    run_dir = tmp_path / "runs" / str(attempt["runId"])

    def append_then_report_failure(stream, event):
        stream.write(canonical_bytes(event) + b"\n")
        stream.flush()
        raise ContractValidationError("evidence.lifecycle_not_appendable", "$.attemptId")

    monkeypatch.setattr(evidence_module, "_append_run_finalized_event", append_then_report_failure)

    run = import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert json.loads((run_dir / "run.json").read_bytes()) == run
    assert _read_lifecycle(tmp_path, str(attempt["attemptId"]))[-1]["phase"] == "run_finalized"


def test_import_run_truncates_partial_lifecycle_append_before_rollback(tmp_path, monkeypatch):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    run_dir = tmp_path / "runs" / str(attempt["runId"])
    lifecycle_path = tmp_path / "attempts" / str(attempt["attemptId"]) / "lifecycle.ndjson"
    lifecycle_before = lifecycle_path.read_bytes()

    def append_partial_then_report_failure(stream, _event):
        stream.write(b"{")
        stream.flush()
        raise ContractValidationError("evidence.lifecycle_not_appendable", "$.attemptId")

    monkeypatch.setattr(evidence_module, "_append_run_finalized_event", append_partial_then_report_failure)

    with pytest.raises(ContractValidationError) as excinfo:
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert excinfo.value.reason_code == "evidence.lifecycle_not_appendable"
    assert not run_dir.exists()
    assert lifecycle_path.read_bytes() == lifecycle_before


def test_import_run_rolls_back_run_directory_when_finalized_chmod_fails(tmp_path, monkeypatch):
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    run_dir = tmp_path / "runs" / str(attempt["runId"])
    original_chmod = Path.chmod

    def fail_finalized_run_json_chmod(self, mode, *args, **kwargs):
        if Path(self) == run_dir / "run.json":
            raise OSError(5, "simulated chmod failure after rename")
        return original_chmod(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "chmod", fail_finalized_run_json_chmod)

    with pytest.raises(OSError):
        import_run(staging, attempt, condition, scenario, environment, tmp_path)

    assert not run_dir.exists()
    assert _read_lifecycle(tmp_path, str(attempt["attemptId"]))[-1]["phase"] == "execution_terminal"
