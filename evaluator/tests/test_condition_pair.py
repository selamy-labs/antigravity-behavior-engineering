import copy

import pytest

from abe_eval.condition_pair import PairValidation, validate_pair
from abe_eval.contracts import canonical_contract_digest, parse_contract


def _digest(seed: str) -> str:
    return "sha256:" + (seed * 64)[:64]


def _condition(condition_id: str, enabled_components: list[str]) -> dict[str, object]:
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
        "enabledComponents": enabled_components,
        "authorityManifestDigest": _digest("d"),
        "resourceEnvelopeDigest": _digest("e"),
        "toolInventoryDigest": _digest("f"),
        "permissionDigest": _digest("1"),
        "environmentDigest": _digest("2"),
        "environmentQualificationDigest": _digest("3"),
    }


def _pair_lock(baseline: dict[str, object], treatment: dict[str, object]) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "pairId": "pair-bare-full",
        "baselineConditionDigest": canonical_contract_digest("ConditionLock", baseline),
        "treatmentConditionDigest": canonical_contract_digest("ConditionLock", treatment),
        "requiredEqualFields": [
            "/authorityManifestDigest",
            "/environmentDigest",
            "/modelRequest",
            "/permissionDigest",
            "/reasoningRequest",
            "/resourceEnvelopeDigest",
            "/toolInventoryDigest",
        ],
        "allowedDifferences": ["/enabledComponents"],
        "validatorDigest": _digest("4"),
        "validatedAt": "2026-08-18T12:00:00Z",
        "result": "pass",
    }


def test_validate_pair_accepts_digest_bound_treatment_component_difference():
    baseline = _condition("bare", [])
    treatment = _condition("full", ["verification-before-completion"])
    lock = _pair_lock(baseline, treatment)

    result = validate_pair(lock, baseline, treatment)

    assert result == PairValidation(
        ok=True,
        reason_code="condition_pair.pass",
        path="$",
        blocked_condition_ids=(),
    )
    assert parse_contract("ConditionPairLock", lock) == lock


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        ("/modelRequest", "gemini-3.1-pro-high"),
        ("/reasoningRequest", "medium"),
        ("/authorityManifestDigest", _digest("5")),
        ("/toolInventoryDigest", _digest("6")),
        ("/permissionDigest", _digest("7")),
        ("/resourceEnvelopeDigest", _digest("8")),
        ("/environmentDigest", _digest("9")),
    ],
)
def test_validate_pair_rejects_required_equal_mismatches_before_either_member_receives_input(path, replacement):
    baseline = _condition("bare", [])
    treatment = _condition("full", ["verification-before-completion"])
    key = path.lstrip("/")
    treatment[key] = replacement
    lock = _pair_lock(baseline, treatment)

    result = validate_pair(lock, baseline, treatment)

    assert not result.ok
    assert result.reason_code == "condition_pair.required_equal_mismatch"
    assert result.path == path
    assert result.blocked_condition_ids == ("bare", "full")


def test_validate_pair_rejects_digest_binding_mismatch_before_input():
    baseline = _condition("bare", [])
    treatment = _condition("full", ["verification-before-completion"])
    lock = _pair_lock(baseline, treatment)
    lock["baselineConditionDigest"] = _digest("0")

    result = validate_pair(lock, baseline, treatment)

    assert not result.ok
    assert result.reason_code == "condition_pair.baseline_digest_mismatch"
    assert result.path == "/baselineConditionDigest"
    assert result.blocked_condition_ids == ("bare", "full")


@pytest.mark.parametrize("forbidden_path", ["pluginDigest", "environmentQualificationDigest"])
def test_validate_pair_rejects_forbidden_condition_difference_before_input(forbidden_path):
    baseline = _condition("bare", [])
    treatment = _condition("full", ["verification-before-completion"])
    treatment[forbidden_path] = _digest("a5")
    lock = _pair_lock(baseline, treatment)

    result = validate_pair(lock, baseline, treatment)

    assert not result.ok
    assert result.reason_code == "condition_pair.forbidden_difference"
    assert result.path == "/" + forbidden_path
    assert result.blocked_condition_ids == ("bare", "full")


def test_validate_pair_returns_stable_invalid_contract_reason():
    baseline = _condition("bare", [])
    treatment = _condition("full", ["verification-before-completion"])
    lock = _pair_lock(baseline, treatment)
    invalid = copy.deepcopy(treatment)
    invalid["fallbackPolicy"] = "silent"

    result = validate_pair(lock, baseline, invalid)

    assert not result.ok
    assert result.reason_code == "condition_pair.invalid_treatment_contract:contract.invalid_field"
    assert result.path == "$.fallbackPolicy"
    assert result.blocked_condition_ids == ("bare", "full")
