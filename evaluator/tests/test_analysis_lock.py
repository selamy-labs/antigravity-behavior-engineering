from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import ContractValidationError, canonical_contract_digest, parse_contract
from abe_eval.analysis_lock import freeze_analysis, validate_analysis_lock


LOCKS = Path("evals/protocols/analysis-locks.json")
FAMILIES = Path("evals/protocols/task-families.json")


def _locks() -> dict[str, object]:
    return json.loads(LOCKS.read_text(encoding="utf-8"))


def _family(family_id: str) -> dict[str, object]:
    for family in _locks()["families"]:
        if family["familyId"] == family_id:
            return copy.deepcopy(family)
    raise AssertionError(family_id)


def _resource(kind: str = "release") -> dict[str, object]:
    return copy.deepcopy(_locks()["resourceEnvelopes"][kind])


def test_freeze_analysis_materializes_pre_treatment_lock_with_exact_digests():
    registry = _locks()
    family = _family("completion-honesty-critical-negative")
    resource = _resource("release")

    lock = freeze_analysis(family, resource, registry["analysisCodeDigest"])

    assert parse_contract("AnalysisLock", lock) == lock
    assert lock == registry["analysisLocks"]["completion-honesty-critical-negative"]
    assert lock["unitOfAnalysis"] == "scenario_variant"
    assert lock["clusterKey"] == "scenarioId"
    assert lock["modelEffects"] == "separate"
    assert lock["resourceEnvelopeDigest"] == canonical_contract_digest("ResourceEnvelope", resource)
    assert lock["analysisCodeDigest"] == registry["analysisCodeDigest"]
    assert lock["variantReductionPolicyDigest"] == sha256_digest(canonical_bytes(family["variantReductionPolicy"]))
    assert set(lock["cohortDefinitions"]) == {"critical_negative", "positive_working_evidence"}
    assert set(family["cohorts"]["critical_negative"]).isdisjoint(family["cohorts"]["positive_working_evidence"])
    assert all(value != "0" for value in lock["weights"].values())
    assert registry["reservedUnseenRegressionGenerationDigests"]
    assert "baselineOutcome" not in json.dumps(registry, sort_keys=True)
    assert "treatmentOutcome" not in json.dumps(registry, sort_keys=True)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("weights", {"critical_negative": "1.0"}),
        ("exclusions", ["changed_after_treatment"]),
        ("stoppingRule", {"schemaVersion": 1, "name": "sequential-peek", "digest": "sha256:" + "1" * 64}),
        ("resourceEnvelopeDigest", "sha256:" + "2" * 64),
        ("analysisCodeDigest", "sha256:" + "3" * 64),
        ("cohortDefinitions", {"critical_negative": "changed"}),
        ("variantReductionPolicyDigest", "sha256:" + "4" * 64),
        ("modelEffects", "pooled"),
    ],
)
def test_validate_analysis_lock_rejects_tampered_frozen_fields(field, replacement):
    registry = _locks()
    family = _family("completion-honesty-critical-negative")
    resource = _resource("release")
    lock = freeze_analysis(family, resource, registry["analysisCodeDigest"])
    tampered = copy.deepcopy(lock)
    tampered[field] = replacement

    with pytest.raises(ContractValidationError) as excinfo:
        validate_analysis_lock(tampered, family, resource, registry["analysisCodeDigest"])

    assert excinfo.value.reason_code == "analysis_lock.frozen_field_mismatch"
    assert excinfo.value.path == "$." + field


def test_analysis_lock_registry_covers_t017_families_and_model_separation_without_outcomes():
    registry = _locks()
    t017 = json.loads(FAMILIES.read_text(encoding="utf-8"))
    t017_family_ids = {family["familyId"] for family in t017["protocols"]}
    locked_family_ids = {family["familyId"] for family in registry["families"]}

    assert t017_family_ids <= locked_family_ids
    assert registry["releaseModelRequests"] == ["gemini-3.1-pro-high", "gemini-3.7-flash-high"]
    assert registry["conditionCohorts"] == {
        "baseline": "bare",
        "releaseCandidate": "full",
        "allowedDifference": "enabledComponents",
    }
    assert registry["analysisPhase"] == "pre_treatment"
    assert all(lock["modelEffects"] == "separate" for lock in registry["analysisLocks"].values())
    assert all(parse_contract("AnalysisLock", lock) == lock for lock in registry["analysisLocks"].values())
    assert all(
        validate_analysis_lock(
            lock,
            _family(family_id),
            _resource(registry["familiesById"][family_id]["resourceEnvelopeKind"]),
            registry["analysisCodeDigest"],
        )
        == lock
        for family_id, lock in registry["analysisLocks"].items()
    )
