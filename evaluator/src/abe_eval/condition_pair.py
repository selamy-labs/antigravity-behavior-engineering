"""Condition-pair validation for protected evaluator schedules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from abe_eval.contracts import ContractValidationError, canonical_contract_digest, parse_contract


@dataclass(frozen=True)
class PairValidation:
    """Stable validation result for a baseline/treatment condition pair."""

    ok: bool
    reason_code: str
    path: str
    blocked_condition_ids: tuple[str, ...]


def _condition_ids(baseline: object, treatment: object) -> tuple[str, str]:
    baseline_id = baseline.get("conditionId") if isinstance(baseline, dict) else None
    treatment_id = treatment.get("conditionId") if isinstance(treatment, dict) else None
    return (str(baseline_id or "baseline"), str(treatment_id or "treatment"))


def _fail(reason_code: str, path: str, blocked_condition_ids: tuple[str, str]) -> PairValidation:
    return PairValidation(False, reason_code, path, blocked_condition_ids)


def _json_pointer_token(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def _resolve_pointer(value: Any, pointer: str) -> Any:
    if pointer == "":
        return value
    if not pointer.startswith("/"):
        raise KeyError(pointer)
    current = value
    for raw_part in pointer.split("/")[1:]:
        part = _json_pointer_token(raw_part)
        if isinstance(current, dict):
            current = current[part]
            continue
        if isinstance(current, list):
            current = current[int(part)]
            continue
        raise KeyError(pointer)
    return current


def _pointer_join(parent: str, part: str | int) -> str:
    if isinstance(part, int):
        encoded = str(part)
    else:
        encoded = part.replace("~", "~0").replace("/", "~1")
    return parent + "/" + encoded


def _difference_paths(left: Any, right: Any, path: str = "") -> tuple[str, ...]:
    if left == right:
        return ()
    if isinstance(left, dict) and isinstance(right, dict):
        paths: list[str] = []
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                paths.append(_pointer_join(path, key))
                continue
            paths.extend(_difference_paths(left[key], right[key], _pointer_join(path, key)))
        return tuple(paths)
    if isinstance(left, list) and isinstance(right, list):
        return (path,)
    return (path,)


def _is_allowed_difference(path: str, allowed: frozenset[str]) -> bool:
    if path == "/conditionId":
        return True
    return any(path == allowed_path or path.startswith(allowed_path + "/") for allowed_path in allowed)


def validate_pair(lock: object, baseline: object, treatment: object) -> PairValidation:
    """Validate that two conditions differ only by the frozen treatment surface."""

    blocked_condition_ids = _condition_ids(baseline, treatment)
    try:
        parsed_baseline = parse_contract("ConditionLock", baseline)
    except ContractValidationError as error:
        return _fail("condition_pair.invalid_baseline_contract:" + error.reason_code, error.path, blocked_condition_ids)
    try:
        parsed_treatment = parse_contract("ConditionLock", treatment)
    except ContractValidationError as error:
        return _fail(
            "condition_pair.invalid_treatment_contract:" + error.reason_code,
            error.path,
            blocked_condition_ids,
        )
    blocked_condition_ids = (str(parsed_baseline["conditionId"]), str(parsed_treatment["conditionId"]))
    try:
        parsed_lock = parse_contract("ConditionPairLock", lock)
    except ContractValidationError as error:
        return _fail("condition_pair.invalid_lock_contract:" + error.reason_code, error.path, blocked_condition_ids)

    if parsed_lock["baselineConditionDigest"] != canonical_contract_digest("ConditionLock", parsed_baseline):
        return _fail("condition_pair.baseline_digest_mismatch", "/baselineConditionDigest", blocked_condition_ids)
    if parsed_lock["treatmentConditionDigest"] != canonical_contract_digest("ConditionLock", parsed_treatment):
        return _fail("condition_pair.treatment_digest_mismatch", "/treatmentConditionDigest", blocked_condition_ids)
    if parsed_lock["result"] != "pass":
        return _fail("condition_pair.lock_failed", "/result", blocked_condition_ids)

    for pointer in parsed_lock["requiredEqualFields"]:
        if _resolve_pointer(parsed_baseline, pointer) != _resolve_pointer(parsed_treatment, pointer):
            return _fail("condition_pair.required_equal_mismatch", pointer, blocked_condition_ids)

    allowed = frozenset(parsed_lock["allowedDifferences"])
    for pointer in _difference_paths(parsed_baseline, parsed_treatment):
        if not _is_allowed_difference(pointer, allowed):
            return _fail("condition_pair.forbidden_difference", pointer, blocked_condition_ids)

    return PairValidation(True, "condition_pair.pass", "$", ())


__all__ = ["PairValidation", "validate_pair"]
