from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import canonical_contract_digest, parse_contract
from abe_eval.scenario import materialize_scenario, public_scenario


PROTOCOLS_PATH = Path("evals/protocols/task-families.json")
ANALYSIS_PATH = Path("evals/protocols/analysis-locks.json")
GENERATOR_PATH = Path("evaluator/src/abe_eval/scenario.py")
REGISTRY_PATH = Path("evals/regression/registry.json")
DIAGNOSTIC_PATH = Path("evals/regression/diagnostic-registry.json")
DOCUMENTATION_PATH = Path("docs/evaluation/regression-taxonomy.md")

T017_HEAD = "448bcfa4d3b2ed2a33a4a94329b31d6795c54ec3"
T018_HEAD = "a351146384d66554a03f79b426552989179dc353"
RESERVED_COMMITMENTS = [
    "sha256:010f010f010f010f010f010f010f010f010f010f010f010f010f010f010f010f",
    "sha256:020f020f020f020f020f020f020f020f020f020f020f020f020f020f020f020f",
    "sha256:030f030f030f030f030f030f030f030f030f030f030f030f030f030f030f030f",
]
ROLE_COMMITMENTS = {
    "positive": RESERVED_COMMITMENTS[0],
    "relevant_negative": RESERVED_COMMITMENTS[1],
}
REQUIRED_COVERAGE = {
    "cold_restart": ["fr044-durable-intent-restart"],
    "completion_honesty": ["fr044-verification-truncation"],
    "dirty_worktree": ["fr044-preferences-dirty-worktree"],
    "durable_intent": ["fr044-durable-intent-restart"],
    "explicit_preference": ["fr044-preferences-dirty-worktree"],
    "grader_leakage": ["fr044-leakage-state-isolation"],
    "hook_tool_subagent_failure": ["fr044-hook-tool-failure", "fr044-agent-positive-control"],
    "interrogation": ["fr044-interrogation-injection"],
    "isolation": ["fr044-leakage-state-isolation"],
    "lifecycle": ["fr044-leakage-state-isolation"],
    "missing_input": ["fr044-permission-missing-input"],
    "model_quota_drift": ["fr044-model-quota-drift"],
    "planted_and_defect_free_review": ["fr044-review-defect-contrast"],
    "prompt_injection": ["fr044-interrogation-injection", "fr044-rule-negative-control"],
    "proportionality": ["fr044-proportionality-safe-default"],
    "real_seam_evidence": ["fr044-verification-truncation"],
    "repair_closure": ["fr044-debug-repair"],
    "root_cause_debugging": ["fr044-debug-repair"],
    "soft_denial": ["fr044-permission-missing-input"],
    "truncated_capture": ["fr044-verification-truncation"],
}
RAW_HIDDEN_MARKERS = (
    "ABE_HIDDEN_",
    "RAW_CANARY_",
    "REFERENCE_SOLUTION:",
    "GRADER_INSTRUCTION:",
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest_object(value: object) -> str:
    return sha256_digest(canonical_bytes(value))


def _digest_file(path: Path) -> str:
    return sha256_digest(path.read_bytes())


def _protocols() -> dict[str, dict[str, Any]]:
    return {item["familyId"]: item for item in _load(PROTOCOLS_PATH)["protocols"]}


def _variants(registry: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {(item["familyId"], item["role"]): item for item in registry["variants"]}


def test_complete_regression_taxonomy_binds_frozen_inputs_and_every_required_family():
    registry = _load(REGISTRY_PATH)
    protocols = _load(PROTOCOLS_PATH)
    analysis = _load(ANALYSIS_PATH)

    assert registry["schemaVersion"] == 1
    assert registry["partition"] == "regression"
    assert registry["reservedSeedCommitments"] == RESERVED_COMMITMENTS
    assert registry["sealedInstancesCommitted"] is False
    assert registry["sourceLocks"] == {
        "schemaVersion": 1,
        "t017HeadCommit": T017_HEAD,
        "t017ProtocolRegistryDigest": _digest_object(protocols),
        "t017ScenarioGeneratorDigest": _digest_file(GENERATOR_PATH),
        "t018HeadCommit": T018_HEAD,
        "t018AnalysisRegistryDigest": _digest_object(analysis),
        "t018AnalysisCodeDigest": analysis["analysisCodeDigest"],
        "t018ReservedGenerationDigests": analysis["reservedUnseenRegressionGenerationDigests"],
    }
    assert registry["materializationPolicy"] == {
        "schemaVersion": 1,
        "partition": "regression",
        "generatorInputs": ["familyId", "partition", "seedCommitment"],
        "postTreatmentInputsAllowed": False,
        "outcomeFieldsAllowed": False,
    }

    coverage = {item["requiredFamily"]: item for item in registry["coverage"]}
    assert set(coverage) == set(REQUIRED_COVERAGE)
    assert registry["familyIds"] == [item["familyId"] for item in protocols["protocols"]]
    for required_family, family_ids in REQUIRED_COVERAGE.items():
        item = coverage[required_family]
        assert item["protocolFamilyIds"] == family_ids
        assert item["positiveVariantIds"]
        assert item["relevantNegativeVariantIds"]
        assert item["realArtifactSeams"]
        assert item["classificationDigests"]
        assert item["analysisLockDigests"]
        if required_family == "lifecycle":
            assert "docs/task-checkpoints/T032.json" in item["realArtifactSeams"]


def test_reserved_variants_are_exact_deterministic_t017_materializations_with_t018_analysis():
    registry = _load(REGISTRY_PATH)
    protocols = _protocols()
    analysis = _load(ANALYSIS_PATH)
    variants = _variants(registry)

    assert len(variants) == len(protocols) * len(ROLE_COMMITMENTS)
    assert len(registry["variants"]) == len(variants)
    for family_id, protocol in protocols.items():
        analysis_lock = analysis["analysisLocks"][family_id]
        for role, commitment in ROLE_COMMITMENTS.items():
            variant = variants[(family_id, role)]
            card = materialize_scenario(protocol, commitment, "regression")
            public = public_scenario(card, protocol)
            assert variant == {
                "schemaVersion": 1,
                "variantId": card["scenarioId"],
                "familyId": family_id,
                "role": role,
                "seedCommitmentInput": commitment,
                "protocolDigest": _digest_object(protocol),
                "scenarioCard": card,
                "scenarioCardDigest": canonical_contract_digest("ScenarioCard", card),
                "publicScenario": public,
                "publicScenarioDigest": canonical_contract_digest("PublicScenario", public),
                "analysisLockDigest": canonical_contract_digest("AnalysisLock", analysis_lock),
                "resourceEnvelopeDigest": canonical_contract_digest("ResourceEnvelope", card["resourceEnvelope"]),
                "classificationPolicyDigest": card["classificationPolicyDigest"],
                "componentControls": protocol["componentControls"],
                "artifactSeams": {
                    "labels": protocol["preTreatmentLabels"]["evidenceSeams"],
                    "protectedAgentInput": card["agentInput"],
                    "fixtureDigest": card["fixtureDigest"],
                    "startingStateDigest": card["startingStateDigest"],
                    "checkIds": [check["checkId"] for check in card["checks"]],
                },
            }
            assert parse_contract("ScenarioCard", variant["scenarioCard"]) == card
            assert parse_contract("PublicScenario", variant["publicScenario"]) == public
            assert parse_contract("AnalysisLock", analysis_lock) == analysis_lock


def test_hidden_canaries_and_partition_boundaries_remain_outside_public_regressions():
    registry = _load(REGISTRY_PATH)
    protocols = _protocols()
    variants = _variants(registry)
    blob = json.dumps(registry, sort_keys=True)

    assert all(marker not in blob for marker in RAW_HIDDEN_MARKERS)
    assert "sealedScenario" not in blob
    assert "postTreatmentResult" not in blob
    assert "baselineOutcome" not in blob
    assert "treatmentOutcome" not in blob
    assert all(variant["publicScenario"]["hiddenMaterialDigest"] == "none" for variant in registry["variants"])
    for family_id, protocol in protocols.items():
        for role, commitment in ROLE_COMMITMENTS.items():
            regression_id = variants[(family_id, role)]["variantId"]
            formative_id = materialize_scenario(protocol, commitment, "formative")["scenarioId"]
            sealed_id = materialize_scenario(protocol, commitment, "sealed")["scenarioId"]
            assert len({regression_id, formative_id, sealed_id}) == 3


def test_post_treatment_diagnostics_are_empty_noncausal_and_ineligible_for_selection():
    registry = _load(REGISTRY_PATH)
    diagnostic = _load(DIAGNOSTIC_PATH)
    documentation = DOCUMENTATION_PATH.read_text(encoding="utf-8")

    assert diagnostic == {
        "schemaVersion": 1,
        "registryId": "diagnostic-registry-2026-08-23",
        "partition": "diagnostic",
        "causalStatus": "noncausal",
        "eligibleForT034Selection": False,
        "eligibleForReleaseClaim": False,
        "sourceRegressionRegistryDigest": _digest_object(registry),
        "cases": [],
    }
    for required in (
        "formative development",
        "frozen regression",
        "sealed confirmation",
        "artifact-first",
        "diagnostic/noncausal",
        "cannot support T034",
        "gemini-3.1-pro-high",
        "gemini-3.7-flash-high",
        "protected raw evidence",
    ):
        assert required in documentation
