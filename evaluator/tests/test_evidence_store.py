from __future__ import annotations

import copy
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

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
    condition = _condition("bare", environment=environment, scenario=scenario)
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
    assert json.loads(original_run_bytes) == run

    raw_locator = Path(str(run["rawEvidenceLocator"]))
    assert not raw_locator.is_absolute()
    assert ".." not in raw_locator.parts
    raw_manifest = json.loads((tmp_path / raw_locator).read_bytes())
    assert run["artifactManifestDigest"] == sha256_digest(canonical_bytes(raw_manifest))

    entries = {entry["path"]: entry for entry in raw_manifest["entries"]}
    assert entries["raw-stream.ndjson"]["digest"] == run["transcriptDigest"]
    assert entries["process.json"]["digest"] != "none"
    assert entries["stdout.txt"]["present"] is False
    for entry in raw_manifest["entries"]:
        if not entry["present"]:
            assert entry["digest"] == "none"
            continue
        object_path = tmp_path / str(entry["objectLocator"])
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
