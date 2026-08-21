"""Frozen classification for T007 staged evaluator outcomes."""

from __future__ import annotations

from typing import Any

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import ContractValidationError, canonical_contract_digest, parse_contract


_REASON_CLASS = {
    "adapter_failure": "infrastructure_failure",
    "budget_exhaustion": "product_failure",
    "grader_leakage": "indeterminate",
    "invalid_controller_input": "infrastructure_failure",
    "malformed_ndjson": "indeterminate",
    "needs_input": "indeterminate",
    "ordinary_artifact_failure": "gradable",
    "pre_start_auth_failure": "infrastructure_failure",
    "product_timeout": "product_failure",
    "safety_refusal": "safety_refusal",
    "success": "gradable",
    "test_flake": "indeterminate",
    "tool_misuse": "product_failure",
    "truncated_ndjson": "indeterminate",
}

_KNOWN_AGENT_STATES = frozenset({"artifact_failed", "completed", "needs_input", "none", "safety_refusal", "tool_misuse"})
_KNOWN_INPUT_STATES = frozenset({"needs_input", "not_requested", "permitted"})
_KNOWN_INFRASTRUCTURE_VALIDITY = frozenset(
    {
        "adapter_failure",
        "capture_malformed",
        "capture_truncated",
        "grader_leakage_detected",
        "invalid_controller_input",
        "pre_start_auth_failure",
        "test_flake",
        "valid",
    }
)


def _fail(reason_code: str, path: str) -> None:
    raise ContractValidationError(reason_code, path)


def _policy_reason_codes(policy: dict[str, Any]) -> frozenset[str]:
    return frozenset(str(rule["reasonCode"]) for rule in policy["reasonCodes"])


def _policy_body_digest(policy: dict[str, Any]) -> str:
    return sha256_digest(canonical_bytes({key: value for key, value in policy.items() if key != "policyDigest"}))


def _integer_at_least(value: object, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _reason_code(outcome: dict[str, Any]) -> str:
    process = outcome["processState"]
    infrastructure = outcome["infrastructureValidity"]
    agent_state = outcome["agentDeclaredState"]
    input_state = outcome["inputPermissionState"]
    consumption = outcome["consumption"]
    qualification = outcome["attemptQualification"]

    if agent_state not in _KNOWN_AGENT_STATES:
        _fail("classification.unknown_terminal_state", "$.agentDeclaredState")
    if input_state not in _KNOWN_INPUT_STATES:
        _fail("classification.unknown_input_permission_state", "$.inputPermissionState")
    if infrastructure not in _KNOWN_INFRASTRUCTURE_VALIDITY:
        _fail("classification.unknown_infrastructure_validity", "$.infrastructureValidity")

    if process["workerProcessState"] == "not_started":
        if qualification["authentication"]["result"] == "fail":
            return "pre_start_auth_failure"
        return "invalid_controller_input"

    if process["timeout"] or process["controllerExitCode"] == 124:
        return "product_timeout"
    if input_state == "needs_input" or agent_state == "needs_input":
        return "needs_input"
    if agent_state == "safety_refusal":
        return "safety_refusal"
    if agent_state == "tool_misuse":
        return "tool_misuse"
    if _integer_at_least(consumption["wallTimeMs"], 600000) or _integer_at_least(consumption["toolCalls"], 20):
        return "budget_exhaustion"

    if infrastructure == "invalid_controller_input":
        return "invalid_controller_input"
    if infrastructure == "capture_malformed":
        return "malformed_ndjson"
    if infrastructure == "capture_truncated":
        return "truncated_ndjson"
    if infrastructure == "grader_leakage_detected":
        return "grader_leakage"
    if infrastructure == "adapter_failure":
        return "adapter_failure"
    if infrastructure == "test_flake":
        return "test_flake"
    if agent_state == "artifact_failed":
        return "ordinary_artifact_failure"
    if agent_state == "completed" and infrastructure == "valid":
        return "success"
    _fail("classification.unknown_terminal_state", "$.agentDeclaredState")


def classify(outcome: object, policy: object, *, expected_policy_digest: str) -> dict[str, object]:
    """Apply the frozen classification table to one unclassified outcome."""

    parsed_outcome = parse_contract("UnclassifiedStagedAttemptOutcome", outcome)
    parsed_policy = parse_contract("ClassificationPolicy", policy)
    if not isinstance(expected_policy_digest, str):
        _fail("classification.invalid_expected_policy_digest", "$.expected_policy_digest")
    if parsed_policy["policyDigest"] != _policy_body_digest(parsed_policy):
        _fail("classification.policy_digest_invalid", "$.policyDigest")
    if parsed_policy["policyDigest"] != expected_policy_digest:
        _fail("classification.policy_digest_mismatch", "$.expected_policy_digest")
    reason_code = _reason_code(parsed_outcome)
    if reason_code not in _REASON_CLASS:
        _fail("classification.unknown_reason", "$.reasonCode")
    if reason_code not in _policy_reason_codes(parsed_policy):
        _fail("classification.reason_not_in_policy", "$.reasonCodes")

    classification = parse_contract(
        "Classification",
        {
            "schemaVersion": 1,
            "class": _REASON_CLASS[reason_code],
            "reasonCode": reason_code,
            "policyDigest": parsed_policy["policyDigest"],
            "retryEligible": parsed_policy["replacementCaps"].get(reason_code, 0) > 0,
            "countsInIntentionToTreat": True,
            "countsInValidRun": _REASON_CLASS[reason_code] == "gradable",
        },
    )
    staged = {
        "schemaVersion": 1,
        "attemptId": parsed_outcome["attemptId"],
        "runId": parsed_outcome["runId"],
        "conditionDigest": parsed_outcome["conditionDigest"],
        "scenarioDigest": parsed_outcome["scenarioDigest"],
        "environmentQualificationDigest": parsed_outcome["environmentQualificationDigest"],
        "lifecycleEventDigests": parsed_outcome["lifecycleEventDigests"],
        "attemptQualification": parsed_outcome["attemptQualification"],
        "observedModel": parsed_outcome["observedModel"],
        "processState": parsed_outcome["processState"],
        "agentDeclaredState": parsed_outcome["agentDeclaredState"],
        "inputPermissionState": parsed_outcome["inputPermissionState"],
        "infrastructureValidity": parsed_outcome["infrastructureValidity"],
        "consumption": parsed_outcome["consumption"],
        "classification": classification,
        "unclassifiedOutcomeDigest": canonical_contract_digest("UnclassifiedStagedAttemptOutcome", parsed_outcome),
        "stagingManifestDigest": parsed_outcome["stagingManifestDigest"],
    }
    parse_contract(
        "StagedAttemptOutcomeBundle",
        {"schemaVersion": 1, "unclassifiedOutcome": parsed_outcome, "stagedOutcome": staged},
    )
    return staged


__all__ = ["classify"]
