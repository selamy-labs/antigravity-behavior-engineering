from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from abe_eval.classify import classify
from abe_eval.contracts import ContractValidationError, canonical_contract_digest, parse_contract
from abe_eval.runner import RunAttemptInputs, run_attempt
from abe_eval.schedule import build_schedule
from fakes.fake_worker import MATRIX, FakeWorker


FIXTURE = Path("evals/protocols/fake-block.json")
CONTRACT_FIXTURES = Path("tests/contract/fixtures/evaluation-contracts.json")


def _digest(seed: str) -> str:
    return "sha256:" + (seed * 64)[:64]


def _case_value(name: str) -> dict[str, object]:
    fixture = json.loads(CONTRACT_FIXTURES.read_text())
    for case in fixture["validCases"]:
        if case["name"] == name:
            return copy.deepcopy(case["value"])
    raise AssertionError(name)


def _condition(condition_id: str) -> dict[str, object]:
    return {
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
        "cliDigest": _digest("a"),
        "pluginDigest": _digest("b"),
        "dependencyDigests": {"superpowers": _digest("c")},
        "enabledComponents": [] if condition_id == "bare" else ["verification-before-completion"],
        "authorityManifestDigest": _digest("d"),
        "resourceEnvelopeDigest": _digest("e"),
        "toolInventoryDigest": _digest("f"),
        "permissionDigest": _digest("1"),
        "environmentDigest": _digest("2"),
        "environmentQualificationDigest": _digest("3"),
    }


def _policy() -> dict[str, object]:
    reason_codes = sorted({str(value["reasonCode"]) for value in MATRIX.values()})
    return {
        "schemaVersion": 1,
        "policyId": "classification-policy-t007",
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


def _attempt(condition_id: str = "bare") -> dict[str, object]:
    payload = json.loads(FIXTURE.read_text())
    attempt = parse_contract("ScheduledAttempt", build_schedule(payload["block"], payload["seed"])[0])
    attempt["conditionId"] = condition_id
    return parse_contract("ScheduledAttempt", attempt)


def _scenario(attempt: dict[str, object], policy: dict[str, object]) -> dict[str, object]:
    scenario = _case_value("ScenarioCard")
    scenario["scenarioId"] = attempt["scenarioId"]
    scenario["classificationPolicyDigest"] = policy["policyDigest"]
    return parse_contract("ScenarioCard", scenario)


def _environment() -> dict[str, object]:
    env = _case_value("EnvironmentQualificationRecord")
    env["cliDigest"] = _digest("a")
    return parse_contract("EnvironmentQualificationRecord", env)


def _inputs(tmp_path: Path, case_id: str) -> tuple[RunAttemptInputs, FakeWorker, dict[str, object]]:
    policy = _policy()
    attempt = _attempt("bare")
    condition = _condition("bare")
    worker = FakeWorker(case_id)
    if case_id == "invalid_controller_input":
        condition = _condition("full")
    return (
        RunAttemptInputs(
            scheduled_attempt=attempt,
            condition=condition,
            scenario=_scenario(attempt, policy),
            environment_qualification=_environment(),
            raw_root=tmp_path,
        ),
        worker,
        policy,
    )


@pytest.mark.parametrize("case_id", sorted(MATRIX))
def test_frozen_classification_matrix_separates_valid_start_from_exit_status(tmp_path, case_id):
    inputs, worker, policy = _inputs(tmp_path, case_id)

    unclassified = run_attempt(inputs, worker)
    staged = classify(unclassified, policy)
    classification = staged["classification"]
    expected = MATRIX[case_id]

    assert parse_contract("UnclassifiedStagedAttemptOutcome", unclassified) == unclassified
    assert parse_contract(
        "StagedAttemptOutcomeBundle",
        {"schemaVersion": 1, "unclassifiedOutcome": unclassified, "stagedOutcome": staged},
    )
    assert classification == parse_contract("Classification", classification)
    assert classification["class"] == expected["class"]
    assert classification["reasonCode"] == expected["reasonCode"]
    assert classification["policyDigest"] == policy["policyDigest"]
    assert classification["retryEligible"] == expected["retryEligible"]
    assert classification["countsInIntentionToTreat"] is True
    assert classification["countsInValidRun"] == expected["countsInValidRun"]
    assert unclassified["processState"]["workerProcessState"] == expected["workerProcessState"]
    assert staged["unclassifiedOutcomeDigest"] == canonical_contract_digest(
        "UnclassifiedStagedAttemptOutcome", unclassified
    )

    if expected["workerProcessState"] == "not_started":
        assert unclassified["attemptQualification"]["validStartAt"] == "none"
        assert worker.invocations == []
    else:
        assert unclassified["attemptQualification"]["validStartAt"] != "none"
        assert len(worker.invocations) == 1


def test_exit_zero_soft_denial_is_never_reclassified_as_success(tmp_path):
    inputs, worker, policy = _inputs(tmp_path, "soft_denial_exit_zero")

    staged = classify(run_attempt(inputs, worker), policy)

    assert staged["processState"]["controllerExitCode"] == 0
    assert staged["processState"]["workerExitCode"] == 0
    assert staged["agentDeclaredState"] == "needs_input"
    assert staged["classification"]["class"] == "indeterminate"
    assert staged["classification"]["reasonCode"] == "needs_input"
    assert staged["classification"]["countsInValidRun"] is False


def test_unknown_reason_code_policy_fails_closed(tmp_path):
    inputs, worker, policy = _inputs(tmp_path, "tool_misuse")
    policy["reasonCodes"] = [rule for rule in policy["reasonCodes"] if rule["reasonCode"] != "tool_misuse"]

    with pytest.raises(ContractValidationError) as excinfo:
        classify(run_attempt(inputs, worker), policy)

    assert excinfo.value.reason_code == "classification.reason_not_in_policy"
    assert excinfo.value.path == "$.reasonCodes"
