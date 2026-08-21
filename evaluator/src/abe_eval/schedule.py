"""Deterministic schedule creation for immutable evaluator attempts."""

from __future__ import annotations

from typing import Any

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import ContractValidationError, canonical_contract_digest, parse_contract

_SCHEDULED_AT = "2026-08-18T12:00:00Z"


def _digest_payload(payload: dict[str, object]) -> str:
    return sha256_digest(canonical_bytes(payload))


def _hex_suffix(digest: str, length: int = 32) -> str:
    return digest.removeprefix("sha256:")[:length]


def _schedule_sort_key(seed: str, block: dict[str, object], scenario_id: str, repetition: int) -> str:
    return _digest_payload(
        {
            "purpose": "t006.schedule.unit-order",
            "seed": seed,
            "blockId": block["blockId"],
            "scenarioId": scenario_id,
            "repetition": repetition,
        }
    )


def _condition_sort_key(
    seed: str, block: dict[str, object], scenario_id: str, repetition: int, condition_id: str
) -> str:
    return _digest_payload(
        {
            "purpose": "t006.schedule.condition-order",
            "seed": seed,
            "blockId": block["blockId"],
            "scenarioId": scenario_id,
            "repetition": repetition,
            "conditionId": condition_id,
        }
    )


def _identity(
    prefix: str,
    seed: str,
    block: dict[str, object],
    scenario_id: str,
    repetition: int,
    condition_id: str,
    ordinal: int,
) -> str:
    digest = _digest_payload(
        {
            "purpose": "t006.schedule." + prefix,
            "seed": seed,
            "blockId": block["blockId"],
            "scenarioId": scenario_id,
            "conditionId": condition_id,
            "repetition": repetition,
            "ordinal": ordinal,
        }
    )
    return prefix + "-" + _hex_suffix(digest)


def build_schedule(block: object, seed: str) -> tuple[dict[str, object], ...]:
    """Return the complete immutable attempt schedule for a block and seed."""

    if not isinstance(seed, str) or not seed:
        raise ContractValidationError("schedule.invalid_seed", "$seed")
    parsed_block = parse_contract("BlockSpec", block)
    units = [
        (str(scenario_id), repetition)
        for scenario_id in parsed_block["scenarioDigests"]
        for repetition in range(1, int(parsed_block["repetitions"]) + 1)
    ]
    units.sort(key=lambda unit: _schedule_sort_key(seed, parsed_block, unit[0], unit[1]))

    attempts: list[dict[str, object]] = []
    for scenario_id, repetition in units:
        conditions = sorted(
            (str(condition_id) for condition_id in parsed_block["conditionIds"]),
            key=lambda condition_id: _condition_sort_key(seed, parsed_block, scenario_id, repetition, condition_id),
        )
        for condition_id in conditions:
            ordinal = len(attempts)
            attempt = {
                "schemaVersion": 1,
                "attemptId": _identity("attempt", seed, parsed_block, scenario_id, repetition, condition_id, ordinal),
                "blockId": parsed_block["blockId"],
                "scenarioId": scenario_id,
                "conditionId": condition_id,
                "repetition": repetition,
                "scheduledAt": _SCHEDULED_AT,
                "randomizationProof": {
                    "schemaVersion": 1,
                    "seedCommitmentDigest": parsed_block["randomizationSeedCommitment"],
                    "ordinal": ordinal,
                },
                "runId": _identity("run", seed, parsed_block, scenario_id, repetition, condition_id, ordinal),
                "replacementForAttemptId": "none",
                "retryOrdinal": 0,
            }
            attempts.append(parse_contract("ScheduledAttempt", attempt))
    return tuple(attempts)


def import_scheduled_attempt(attempt: object, expected_digest: str) -> dict[str, object]:
    """Import one scheduled attempt only if its hash still matches."""

    parsed_attempt = parse_contract("ScheduledAttempt", attempt)
    if canonical_contract_digest("ScheduledAttempt", parsed_attempt) != expected_digest:
        raise ContractValidationError("schedule.attempt_digest_mismatch", "$")
    return parsed_attempt


__all__ = ["build_schedule", "import_scheduled_attempt"]
