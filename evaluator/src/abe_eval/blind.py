"""Condition- and model-blind run projections for evaluator review."""

from __future__ import annotations

from typing import Any

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import canonical_contract_digest, parse_contract


def _digest_token(prefix: str, seed: object, purpose: str, value: object) -> str:
    digest = sha256_digest(canonical_bytes({"purpose": purpose, "seed": seed, "value": value}))
    return prefix + "-" + digest.removeprefix("sha256:")[:16]


def _grade_digests(policy: dict[str, Any]) -> list[str]:
    values = policy.get("gradeDigests", [])
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise TypeError("blind.invalid_grade_digests")
    return sorted(values)


def blind_run(record: dict[str, object], policy: dict[str, object]) -> dict[str, object]:
    """Return a deterministic blind projection that keeps audit digests only."""

    run = parse_contract("RunRecord", record)
    if not isinstance(policy, dict):
        raise TypeError("blind.invalid_policy")
    seed = policy.get("randomizationSeedDigest")
    if not isinstance(seed, str) or not seed.startswith("sha256:"):
        raise TypeError("blind.invalid_seed")
    model_key = {
        "requestedModel": run["observedModel"]["requestedModel"],
        "requestedReasoning": run["observedModel"]["requestedReasoning"],
    }
    projection = {
        "schemaVersion": 1,
        "publicRunId": _digest_token("blind-run", seed, "run", run["runId"]),
        "blindConditionId": _digest_token("condition", seed, "condition", run["conditionDigest"]),
        "blindModelId": _digest_token("model", seed, "model", model_key),
        "processState": run["processState"],
        "classification": run["classification"],
        "consumption": run["consumption"],
        "auditDigests": {
            "runRecordDigest": canonical_contract_digest("RunRecord", run),
            "rawEvidenceDigest": run["artifactManifestDigest"],
            "transcriptDigest": run["transcriptDigest"],
            "eventStreamDigest": run["eventStreamDigest"],
        },
        "gradeDigests": _grade_digests(policy),
        "limitations": [],
    }
    return projection


__all__ = ["blind_run"]
