from __future__ import annotations

import copy
import json
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest

import abe_eval.regression as regression
from abe_eval.antigravity import (
    release_candidate_capture_boundary_digest,
    release_candidate_invocation_boundary_digest,
)
from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import canonical_contract_digest, parse_contract
from abe_eval.regression import (
    ProtectedRegressionError,
    build_protected_replay_plan,
    grade_protected_workspace,
    materialize_public_registry,
    protected_replay_condition,
    provision_protected_workspace,
    validate_protected_bundle,
    validate_regression_taxonomy,
    verify_protected_replay_condition,
)
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
CANDIDATE_FREEZE_DIGEST = "sha256:eaabda91aea0f2555205bc98ac2337e6c3c6871fc35ba2b4bb1c56d71dd695fa"
SOURCE_QUALIFICATION_DIGEST = "sha256:252cb549dc4dba878a352e049ea75c2d076b59aa9f0dcd111aa5c626cb6699f2"
QUALIFICATION_DIGEST = "sha256:8fcab232e403cbe396dbcf0c808b6dba3fb65aebf860de682d997a77a69c5382"
QUALIFICATION_REPLACEMENT_AMENDMENT_DIGEST = "sha256:f1659df6d7542aec1aac6a812c252268f9b562e8b7295efecfe9872caf8eaf81"
CANDIDATE_ARCHIVE_DIGEST = "sha256:233366d1fd5c2fe513b533fabc106a8683635d95ca6faaf63bd36fb4a8f99d86"
AUTHORIZED_CAUSAL_GAPS = {
    "hook_tool_subagent_failure": ["subagent_failure"],
    "lifecycle": ["lifecycle"],
}
FULLY_UNCOVERED_FAMILIES = ["lifecycle"]
PARTIALLY_UNCOVERED_FAMILIES = [
    {"requiredFamily": "hook_tool_subagent_failure", "uncoveredAspects": ["subagent_failure"]}
]


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


def _write_protected(path: Path, value: bytes, *, root: Path) -> dict[str, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)
    path.chmod(0o400)
    return {"path": path.relative_to(root).as_posix(), "digest": sha256_digest(value)}


def _build_private_bundle(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    registry = copy.deepcopy(_load(REGISTRY_PATH))
    cases: list[dict[str, Any]] = []
    for variant in registry["variants"]:
        case_id = variant["variantId"]
        case_root = root / "cases" / case_id
        check = variant["scenarioCard"]["checks"][0]
        worker_files = {
            "agentInput": _write_protected(
                case_root / "worker" / "agent-input.md",
                ("Execute the frozen " + variant["familyId"] + " " + variant["role"] + " case.\n").encode(),
                root=root,
            ),
            "fixture": _write_protected(
                case_root / "worker" / "fixture.json",
                canonical_bytes(
                    {
                        "schemaVersion": 1,
                        "caseId": case_id,
                        "familyId": variant["familyId"],
                        "role": variant["role"],
                        "fixtureKind": "synthetic-test",
                        "files": [{"path": "task.txt", "content": "before\n"}],
                    }
                ),
                root=root,
            ),
            "startingState": _write_protected(
                case_root / "worker" / "starting-state.json",
                canonical_bytes(
                    {
                        "schemaVersion": 1,
                        "caseId": case_id,
                        "familyId": variant["familyId"],
                        "role": variant["role"],
                        "variantToken": case_id.rsplit("-", 1)[1],
                        "worktree": "clean",
                        "priorContext": "none",
                    }
                ),
                root=root,
            ),
        }
        controller_files = {
            "controller": _write_protected(
                case_root / "controller" / "grader.py",
                (
                    "import argparse,json\n"
                    "p=argparse.ArgumentParser();p.add_argument('--workspace');p.add_argument('--grader-input');"
                    "p.add_argument('--expected-result');p.add_argument('--output');a=p.parse_args()\n"
                    "passed=open(a.workspace+'/task.txt').read()=='after\\n'\n"
                    "open(a.output,'w').write(json.dumps({'caseId':json.load(open(a.grader_input))['caseId'],"
                    "'passed':passed,'reasonCode':'pass' if passed else 'mismatch'}))\n"
                    "raise SystemExit(0 if passed else 1)\n"
                ).encode(),
                root=root,
            ),
            "graderInput": _write_protected(
                case_root / "controller" / "grader-input.json",
                canonical_bytes({"schemaVersion": 1, "caseId": case_id, "hiddenCanary": "test-only-" + case_id}),
                root=root,
            ),
            "expectedResult": _write_protected(
                case_root / "controller" / "expected-result.json",
                canonical_bytes({"schemaVersion": 1, "caseId": case_id, "outcome": "pass"}),
                root=root,
            ),
        }
        variant["scenarioCard"]["fixtureDigest"] = worker_files["fixture"]["digest"]
        variant["scenarioCard"]["startingStateDigest"] = worker_files["startingState"]["digest"]
        check["implementationDigest"] = controller_files["controller"]["digest"]
        check["inputDigest"] = controller_files["graderInput"]["digest"]
        check["expectedResultDigest"] = controller_files["expectedResult"]["digest"]
        variant["scenarioCardDigest"] = canonical_contract_digest("ScenarioCard", variant["scenarioCard"])
        variant["publicScenario"]["fixtureDigest"] = worker_files["fixture"]["digest"]
        variant["protectedMaterialDigest"] = sha256_digest(
            canonical_bytes(sorted(item["digest"] for item in controller_files.values()))
        )
        variant["publicScenarioDigest"] = canonical_contract_digest("PublicScenario", variant["publicScenario"])
        variant["artifactSeams"]["fixtureDigest"] = worker_files["fixture"]["digest"]
        variant["artifactSeams"]["startingStateDigest"] = worker_files["startingState"]["digest"]
        variant["artifactSeams"]["agentInputDigest"] = worker_files["agentInput"]["digest"]
        variant["artifactSeams"].pop("protectedAgentInput", None)
        cases.append(
            {
                "schemaVersion": 1,
                "caseId": case_id,
                "familyId": variant["familyId"],
                "role": variant["role"],
                "partition": "regression",
                "logicalAgentInputPath": worker_files["agentInput"]["path"],
                "workerReadable": worker_files,
                "controllerOnly": controller_files,
            }
        )
    manifest = {
        "schemaVersion": 1,
        "kind": "ProtectedRegressionBundle",
        "bundleId": "t033-test-bundle",
        "createdAt": "2026-08-24T05:00:00Z",
        "producer": {
            "schemaVersion": 1,
            "role": "independent_evaluation_authority",
            "contextId": "test-context",
            "model": "gpt-5.6-terra",
            "reasoning": "high",
        },
        "temporalBoundary": {
            "candidateCausalityFreezeDigest": CANDIDATE_FREEZE_DIGEST,
            "protectedOutcomesObservedBeforeMaterialization": False,
            "candidateMutationAllowedAfterOutcome": False,
        },
        "sourceLocks": copy.deepcopy(registry["sourceLocks"]),
        "candidateArchiveDigest": CANDIDATE_ARCHIVE_DIGEST,
        "qualificationDigest": SOURCE_QUALIFICATION_DIGEST,
        "caseCount": len(cases),
        "cases": cases,
    }
    registry["concreteBindingCorrection"]["protectedBundleManifestDigest"] = sha256_digest(canonical_bytes(manifest))
    (root / "manifest.json").write_bytes(canonical_bytes(manifest))
    (root / "manifest.json").chmod(0o400)
    return registry, manifest


def _replace_starting_state(root: Path, case: dict[str, Any], value: object, *, canonical: bool = True) -> None:
    binding = case["workerReadable"]["startingState"]
    path = root / binding["path"]
    data = canonical_bytes(value) if canonical else bytes(value)
    path.chmod(0o600)
    path.write_bytes(data)
    path.chmod(0o400)
    binding["digest"] = sha256_digest(data)


def _starting_state(case: dict[str, Any], **changes: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schemaVersion": 1,
        "caseId": case["caseId"],
        "familyId": case["familyId"],
        "role": case["role"],
        "variantToken": case["caseId"].rsplit("-", 1)[1],
        "worktree": "clean",
        "priorContext": "none",
    }
    value.update(changes)
    return value


def _validated_bundle_summary(manifest_digest: str) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "manifestDigest": manifest_digest,
        "caseCount": 28,
        "familyCount": 14,
        "roles": ["positive", "relevant_negative"],
        "sourceQualificationDigest": SOURCE_QUALIFICATION_DIGEST,
        "qualificationDigest": QUALIFICATION_DIGEST,
        "qualificationReplacementAmendmentDigest": QUALIFICATION_REPLACEMENT_AMENDMENT_DIGEST,
        "candidateCausalityFreezeDigest": CANDIDATE_FREEZE_DIGEST,
        "candidateArchiveDigest": CANDIDATE_ARCHIVE_DIGEST,
        "workerControllerPathsDisjoint": True,
        "allDeclaredDigestsMatch": True,
        "causalCoverageComplete": False,
        "uncoveredFamilies": FULLY_UNCOVERED_FAMILIES,
        "partiallyUncoveredFamilies": PARTIALLY_UNCOVERED_FAMILIES,
    }


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
    assert validate_regression_taxonomy(registry) == {
        "schemaVersion": 1,
        "causalCoverageComplete": False,
        "uncoveredFamilies": FULLY_UNCOVERED_FAMILIES,
        "partiallyUncoveredFamilies": PARTIALLY_UNCOVERED_FAMILIES,
    }
    for required_family, family_ids in REQUIRED_COVERAGE.items():
        item = coverage[required_family]
        if required_family == "lifecycle":
            assert item == {
                "requiredFamily": required_family,
                "protocolFamilyIds": [],
                "positiveVariantIds": [],
                "relevantNegativeVariantIds": [],
                "realArtifactSeams": [],
                "classificationDigests": [],
                "analysisLockDigests": [],
                "coverageStatus": "uncovered",
                "uncoveredAspects": AUTHORIZED_CAUSAL_GAPS[required_family],
                "eligibleForT034Selection": False,
                "eligibleForReleaseClaim": False,
            }
            continue
        if required_family == "hook_tool_subagent_failure":
            assert item["coverageStatus"] == "partial"
            assert item["coveredAspects"] == ["hook_failure", "tool_failure"]
            assert item["uncoveredAspects"] == ["subagent_failure"]
            assert item["uncoveredAspectsEligibleForT034Selection"] is False
            assert item["uncoveredAspectsEligibleForReleaseClaim"] is False
            family_ids = ["fr044-hook-tool-failure"]
        else:
            assert item["coverageStatus"] == "covered"
        assert item["protocolFamilyIds"] == family_ids
        assert item["positiveVariantIds"]
        assert item["relevantNegativeVariantIds"]
        assert item["realArtifactSeams"]
        assert item["classificationDigests"]
        assert item["analysisLockDigests"]


@pytest.mark.parametrize(
    "broken_binding",
    ["missing_family", "positive", "relevant_negative", "analysis", "classification", "real_seam"],
)
def test_taxonomy_validator_fails_closed_for_every_required_coverage_binding(broken_binding):
    registry = copy.deepcopy(_load(REGISTRY_PATH))
    covered = next(item for item in registry["coverage"] if item["coverageStatus"] == "covered")
    if broken_binding == "missing_family":
        registry["coverage"].remove(covered)
    elif broken_binding == "positive":
        covered["positiveVariantIds"] = []
    elif broken_binding == "relevant_negative":
        covered["relevantNegativeVariantIds"] = []
    elif broken_binding == "analysis":
        covered["analysisLockDigests"] = ["sha256:" + "9" * 64]
    elif broken_binding == "classification":
        covered["classificationDigests"] = ["sha256:" + "9" * 64]
    else:
        covered["realArtifactSeams"] = ["unbound_seam"]

    with pytest.raises(ProtectedRegressionError, match="regression_taxonomy.incomplete_family"):
        validate_regression_taxonomy(registry)


def test_taxonomy_validator_rejects_semantic_mapping_swaps_duplicate_variants_and_missing_digest_seams():
    swapped = copy.deepcopy(_load(REGISTRY_PATH))
    first, second = [item for item in swapped["coverage"] if item["coverageStatus"] == "covered"][:2]
    for field in (
        "protocolFamilyIds",
        "positiveVariantIds",
        "relevantNegativeVariantIds",
        "realArtifactSeams",
        "classificationDigests",
        "analysisLockDigests",
    ):
        first[field], second[field] = second[field], first[field]
    with pytest.raises(ProtectedRegressionError, match="regression_taxonomy.incomplete_family"):
        validate_regression_taxonomy(swapped)

    duplicate = copy.deepcopy(_load(REGISTRY_PATH))
    duplicate["variants"].append(copy.deepcopy(duplicate["variants"][0]))
    with pytest.raises(ProtectedRegressionError, match="regression_taxonomy.incomplete_family"):
        validate_regression_taxonomy(duplicate)

    for seam_field in ("agentInputDigest", "fixtureDigest", "startingStateDigest"):
        missing_seam = copy.deepcopy(_load(REGISTRY_PATH))
        missing_seam["variants"][0]["artifactSeams"].pop(seam_field)
        with pytest.raises(ProtectedRegressionError, match="regression_taxonomy.incomplete_family"):
            validate_regression_taxonomy(missing_seam)


@pytest.mark.parametrize("gap_family", sorted(AUTHORIZED_CAUSAL_GAPS))
def test_explicit_uncovered_families_cannot_be_promoted_to_causal_completeness(gap_family):
    registry = copy.deepcopy(_load(REGISTRY_PATH))
    gap = next(item for item in registry["coverage"] if item["requiredFamily"] == gap_family)
    gap["coverageStatus"] = "covered"

    with pytest.raises(ProtectedRegressionError, match="regression_taxonomy.invalid_gap"):
        validate_regression_taxonomy(registry)


@pytest.mark.parametrize("claim", ["causal_complete", "fully_uncovered", "partially_uncovered"])
def test_taxonomy_validator_rejects_drifted_top_level_coverage_claims(claim):
    registry = copy.deepcopy(_load(REGISTRY_PATH))
    if claim == "causal_complete":
        registry["causalCoverageComplete"] = True
    elif claim == "fully_uncovered":
        registry["uncoveredFamilies"] = []
    else:
        registry["partiallyUncoveredFamilies"] = []

    with pytest.raises(ProtectedRegressionError, match="regression_taxonomy.invalid_gap"):
        validate_regression_taxonomy(registry)


def test_reserved_variants_preserve_pre_treatment_semantics_and_bind_corrected_concrete_bytes():
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
            assert variant["schemaVersion"] == 1
            assert variant["variantId"] == card["scenarioId"]
            assert variant["familyId"] == family_id
            assert variant["role"] == role
            assert variant["seedCommitmentInput"] == commitment
            assert variant["protocolDigest"] == _digest_object(protocol)
            assert variant["analysisLockDigest"] == canonical_contract_digest("AnalysisLock", analysis_lock)
            assert variant["resourceEnvelopeDigest"] == canonical_contract_digest(
                "ResourceEnvelope", card["resourceEnvelope"]
            )
            assert variant["classificationPolicyDigest"] == card["classificationPolicyDigest"]
            assert variant["componentControls"] == protocol["componentControls"]
            assert variant["scenarioCard"]["scenarioId"] == card["scenarioId"]
            assert variant["scenarioCard"]["agentInput"] == variant["variantId"]
            assert "/" not in variant["scenarioCard"]["agentInput"]
            assert variant["scenarioCard"]["resourceEnvelope"] == card["resourceEnvelope"]
            assert variant["scenarioCard"]["classificationPolicyDigest"] == card["classificationPolicyDigest"]
            assert variant["publicScenario"]["publicScenarioId"] == public["publicScenarioId"]
            assert variant["publicScenario"]["hiddenMaterialDigest"] == "none"
            assert variant["artifactSeams"]["labels"] == protocol["preTreatmentLabels"]["evidenceSeams"]
            assert "protectedAgentInput" not in variant["artifactSeams"]
            assert variant["artifactSeams"]["agentInputDigest"].startswith("sha256:")
            assert variant["artifactSeams"]["checkIds"] == [check["checkId"] for check in card["checks"]]
            assert variant["scenarioCardDigest"] == canonical_contract_digest(
                "ScenarioCard", variant["scenarioCard"]
            )
            assert variant["publicScenarioDigest"] == canonical_contract_digest(
                "PublicScenario", variant["publicScenario"]
            )
            assert parse_contract("ScenarioCard", variant["scenarioCard"]) == variant["scenarioCard"]
            assert parse_contract("PublicScenario", variant["publicScenario"]) == variant["publicScenario"]
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


def test_real_private_bundle_is_complete_digest_bound_partitioned_and_worker_isolated(tmp_path):
    root = tmp_path / "protected-bundle"
    registry, manifest = _build_private_bundle(root)

    result = validate_protected_bundle(
        root,
        registry=registry,
        source_qualification_digest=SOURCE_QUALIFICATION_DIGEST,
        qualification_digest=QUALIFICATION_DIGEST,
        qualification_replacement_amendment_digest=QUALIFICATION_REPLACEMENT_AMENDMENT_DIGEST,
        expected_manifest_digest=sha256_digest(canonical_bytes(manifest)),
        candidate_freeze_digest=CANDIDATE_FREEZE_DIGEST,
        expected_candidate_archive_digest=CANDIDATE_ARCHIVE_DIGEST,
    )

    assert result["caseCount"] == 28
    assert result["familyCount"] == 14
    assert result["roles"] == ["positive", "relevant_negative"]
    assert result["manifestDigest"] == sha256_digest(canonical_bytes(manifest))
    assert result["workerControllerPathsDisjoint"] is True
    assert result["allDeclaredDigestsMatch"] is True
    assert stat.S_IMODE((root / "manifest.json").stat().st_mode) == 0o400


def test_public_registry_is_a_deterministic_digest_only_projection_of_private_bindings(tmp_path):
    root = tmp_path / "protected-bundle"
    expected_registry, manifest = _build_private_bundle(root)
    original_registry = _load(REGISTRY_PATH)

    projected = materialize_public_registry(
        root,
        registry=original_registry,
        amendment_digest="sha256:d6210f8a0bc595badf6171a0b8ee671f2f5109433fc7adcf6a7d59fb5995f3f4",
        source_qualification_digest=SOURCE_QUALIFICATION_DIGEST,
        qualification_digest=QUALIFICATION_DIGEST,
        qualification_replacement_amendment_digest=QUALIFICATION_REPLACEMENT_AMENDMENT_DIGEST,
        expected_manifest_digest=sha256_digest(canonical_bytes(manifest)),
        candidate_freeze_digest=CANDIDATE_FREEZE_DIGEST,
        candidate_archive_digest=CANDIDATE_ARCHIVE_DIGEST,
    )

    assert projected["variants"] == expected_registry["variants"]
    assert projected["concreteBindingCorrection"] == {
        "schemaVersion": 1,
        "claimBoundary": "semantic_protocols_and_seed_commitments_pre_treatment; concrete_bytes_post_candidate_freeze_pre_outcome",
        "originalRegistryDigest": original_registry["concreteBindingCorrection"]["originalRegistryDigest"],
        "protectedBundleManifestDigest": sha256_digest(canonical_bytes(manifest)),
        "candidateCausalityFreezeDigest": CANDIDATE_FREEZE_DIGEST,
        "sourceQualificationDigest": SOURCE_QUALIFICATION_DIGEST,
        "qualificationDigest": QUALIFICATION_DIGEST,
        "qualificationReplacementAmendmentDigest": QUALIFICATION_REPLACEMENT_AMENDMENT_DIGEST,
        "scopeAmendmentDigest": "sha256:d6210f8a0bc595badf6171a0b8ee671f2f5109433fc7adcf6a7d59fb5995f3f4",
        "originalConcreteBindingsAvailable": False,
        "candidateMutationAllowedAfterOutcome": False,
    }
    assert "test-only-" not in json.dumps(projected, sort_keys=True)
    assert materialize_public_registry(
        root,
        registry=projected,
        amendment_digest="sha256:d6210f8a0bc595badf6171a0b8ee671f2f5109433fc7adcf6a7d59fb5995f3f4",
        source_qualification_digest=SOURCE_QUALIFICATION_DIGEST,
        qualification_digest=QUALIFICATION_DIGEST,
        qualification_replacement_amendment_digest=QUALIFICATION_REPLACEMENT_AMENDMENT_DIGEST,
        expected_manifest_digest=sha256_digest(canonical_bytes(manifest)),
        candidate_freeze_digest=CANDIDATE_FREEZE_DIGEST,
        candidate_archive_digest=CANDIDATE_ARCHIVE_DIGEST,
    ) == projected


@pytest.mark.parametrize(
    ("drift", "error"),
    [
        ("producer", "protected_bundle.invalid_producer"),
        ("producer_unknown", "protected_bundle.invalid_producer"),
        ("created_at", "protected_bundle.invalid_manifest"),
        ("temporal", "protected_bundle.invalid_temporal_boundary"),
        ("source_locks", "protected_bundle.source_lock_mismatch"),
        ("qualification", "protected_bundle.qualification_mismatch"),
        ("candidate_freeze", "protected_bundle.invalid_temporal_boundary"),
        ("candidate_archive", "protected_bundle.candidate_archive_mismatch"),
        ("case_count", "protected_bundle.incomplete_taxonomy"),
        ("duplicate_case", "protected_bundle.invalid_cases"),
        ("family", "protected_bundle.case_binding_mismatch"),
        ("role", "protected_bundle.case_binding_mismatch"),
    ],
)
def test_public_materialization_rejects_every_provenance_and_taxonomy_binding_drift(tmp_path, drift, error):
    root = tmp_path / "protected-bundle"
    registry, manifest = _build_private_bundle(root)
    if drift == "producer":
        manifest["producer"]["role"] = "candidate_author"
    elif drift == "producer_unknown":
        manifest["producer"]["unknown"] = True
    elif drift == "created_at":
        manifest["createdAt"] = "not-a-timestamp"
    elif drift == "temporal":
        manifest["temporalBoundary"]["protectedOutcomesObservedBeforeMaterialization"] = True
    elif drift == "source_locks":
        manifest["sourceLocks"]["t017HeadCommit"] = "drift"
    elif drift == "qualification":
        manifest["qualificationDigest"] = "sha256:" + "9" * 64
    elif drift == "candidate_freeze":
        manifest["temporalBoundary"]["candidateCausalityFreezeDigest"] = "sha256:" + "9" * 64
    elif drift == "candidate_archive":
        manifest["candidateArchiveDigest"] = "sha256:" + "9" * 64
    elif drift == "case_count":
        manifest["caseCount"] = 27
    elif drift == "duplicate_case":
        manifest["cases"].append(copy.deepcopy(manifest["cases"][0]))
    elif drift == "family":
        manifest["cases"][0]["familyId"] = "different-family"
    else:
        manifest["cases"][0]["role"] = "relevant_negative"
    manifest_path = root / "manifest.json"
    manifest_path.chmod(0o600)
    manifest_path.write_bytes(canonical_bytes(manifest))
    manifest_path.chmod(0o400)

    with pytest.raises(ProtectedRegressionError, match=error):
        materialize_public_registry(
            root,
            registry=registry,
            amendment_digest="sha256:" + "8" * 64,
            source_qualification_digest=SOURCE_QUALIFICATION_DIGEST,
            qualification_digest=QUALIFICATION_DIGEST,
            qualification_replacement_amendment_digest=QUALIFICATION_REPLACEMENT_AMENDMENT_DIGEST,
            expected_manifest_digest=sha256_digest(canonical_bytes(manifest)),
            candidate_freeze_digest=CANDIDATE_FREEZE_DIGEST,
            candidate_archive_digest=CANDIDATE_ARCHIVE_DIGEST,
        )


def test_candidate_archive_mismatch_fails_before_replay_scheduling(tmp_path):
    root = tmp_path / "protected-bundle"
    registry, _ = _build_private_bundle(root)

    with pytest.raises(ProtectedRegressionError, match="protected_bundle.candidate_archive_mismatch"):
        validate_protected_bundle(
            root,
            registry=registry,
            source_qualification_digest=SOURCE_QUALIFICATION_DIGEST,
            qualification_digest=QUALIFICATION_DIGEST,
            qualification_replacement_amendment_digest=QUALIFICATION_REPLACEMENT_AMENDMENT_DIGEST,
            expected_manifest_digest=sha256_digest((root / "manifest.json").read_bytes()),
            candidate_freeze_digest=CANDIDATE_FREEZE_DIGEST,
            expected_candidate_archive_digest="sha256:" + "9" * 64,
        )


def test_authorized_manifest_digest_is_required_before_bundle_validation(tmp_path):
    root = tmp_path / "protected-bundle"
    registry, _ = _build_private_bundle(root)

    with pytest.raises(ProtectedRegressionError, match="protected_bundle.manifest_identity_mismatch"):
        validate_protected_bundle(
            root,
            registry=registry,
            source_qualification_digest=SOURCE_QUALIFICATION_DIGEST,
            qualification_digest=QUALIFICATION_DIGEST,
            qualification_replacement_amendment_digest=QUALIFICATION_REPLACEMENT_AMENDMENT_DIGEST,
            expected_manifest_digest="sha256:" + "9" * 64,
            candidate_freeze_digest=CANDIDATE_FREEZE_DIGEST,
            expected_candidate_archive_digest=CANDIDATE_ARCHIVE_DIGEST,
        )


def test_private_bundle_fails_closed_on_missing_bytes_digest_drift_and_grader_visibility(tmp_path):
    missing_root = tmp_path / "missing"
    missing_registry, missing_manifest = _build_private_bundle(missing_root)
    missing_path = missing_root / missing_manifest["cases"][0]["controllerOnly"]["expectedResult"]["path"]
    missing_path.unlink()
    with pytest.raises(ProtectedRegressionError, match="protected_bundle.missing_file"):
        validate_protected_bundle(
            missing_root,
            registry=missing_registry,
            source_qualification_digest=SOURCE_QUALIFICATION_DIGEST,
            qualification_digest=QUALIFICATION_DIGEST,
            qualification_replacement_amendment_digest=QUALIFICATION_REPLACEMENT_AMENDMENT_DIGEST,
            expected_manifest_digest=sha256_digest((missing_root / "manifest.json").read_bytes()),
            candidate_freeze_digest=CANDIDATE_FREEZE_DIGEST,
            expected_candidate_archive_digest=CANDIDATE_ARCHIVE_DIGEST,
        )

    drift_root = tmp_path / "drift"
    drift_registry, drift_manifest = _build_private_bundle(drift_root)
    drift_path = drift_root / drift_manifest["cases"][0]["workerReadable"]["fixture"]["path"]
    drift_path.chmod(0o600)
    drift_path.write_bytes(b"tampered")
    drift_path.chmod(0o400)
    with pytest.raises(ProtectedRegressionError, match="protected_bundle.digest_mismatch"):
        validate_protected_bundle(
            drift_root,
            registry=drift_registry,
            source_qualification_digest=SOURCE_QUALIFICATION_DIGEST,
            qualification_digest=QUALIFICATION_DIGEST,
            qualification_replacement_amendment_digest=QUALIFICATION_REPLACEMENT_AMENDMENT_DIGEST,
            expected_manifest_digest=sha256_digest((drift_root / "manifest.json").read_bytes()),
            candidate_freeze_digest=CANDIDATE_FREEZE_DIGEST,
            expected_candidate_archive_digest=CANDIDATE_ARCHIVE_DIGEST,
        )

    leak_root = tmp_path / "leak"
    leak_registry, leak_manifest = _build_private_bundle(leak_root)
    leaked = leak_manifest["cases"][0]["controllerOnly"]["graderInput"]
    leak_manifest["cases"][0]["workerReadable"]["graderInput"] = leaked
    (leak_root / "manifest.json").chmod(0o600)
    (leak_root / "manifest.json").write_bytes(canonical_bytes(leak_manifest))
    (leak_root / "manifest.json").chmod(0o400)
    leak_registry["concreteBindingCorrection"]["protectedBundleManifestDigest"] = sha256_digest(
        canonical_bytes(leak_manifest)
    )
    with pytest.raises(ProtectedRegressionError, match="protected_bundle.worker_controller_overlap"):
        validate_protected_bundle(
            leak_root,
            registry=leak_registry,
            source_qualification_digest=SOURCE_QUALIFICATION_DIGEST,
            qualification_digest=QUALIFICATION_DIGEST,
            qualification_replacement_amendment_digest=QUALIFICATION_REPLACEMENT_AMENDMENT_DIGEST,
            expected_manifest_digest=sha256_digest((leak_root / "manifest.json").read_bytes()),
            candidate_freeze_digest=CANDIDATE_FREEZE_DIGEST,
            expected_candidate_archive_digest=CANDIDATE_ARCHIVE_DIGEST,
        )


def test_protected_replay_plan_is_deterministic_complete_paired_and_public_safe():
    registry = _load(REGISTRY_PATH)
    manifest_digest = "sha256:2d0450f5b4455787a1e3563a72e7a148792815c5d65a838a7594b5f5726946f9"
    validated_bundle = _validated_bundle_summary(manifest_digest)

    first = build_protected_replay_plan(
        registry,
        validated_bundle=validated_bundle,
        seed="t033-protected-replay-v1",
    )
    second = build_protected_replay_plan(
        registry,
        validated_bundle=validated_bundle,
        seed="t033-protected-replay-v1",
    )

    assert first == second
    assert first["attemptCount"] == 112
    assert len(first["blocks"]) == 56
    assert {block["modelRequest"] for block in first["blocks"]} == {
        "gemini-3.1-pro-high",
        "gemini-3.7-flash-high",
    }
    assert all({attempt["conditionId"] for attempt in block["attempts"]} == {"bare", "integrated"} for block in first["blocks"])
    assert all(len(block["attempts"]) == 2 for block in first["blocks"])
    assert len({attempt["attemptId"] for block in first["blocks"] for attempt in block["attempts"]}) == 112
    assert manifest_digest in json.dumps(first, sort_keys=True)
    assert "/home/" not in json.dumps(first, sort_keys=True)


def test_protected_controller_bridge_provisions_only_worker_bytes_and_grades_controller_side(tmp_path):
    root = tmp_path / "protected-bundle"
    registry, manifest = _build_private_bundle(root)
    case = manifest["cases"][0]
    workspace = tmp_path / "workspace"

    provisioned = provision_protected_workspace(root, case, workspace)
    request_path = provisioned.request_path
    assert request_path.read_text().startswith("Frozen prior context:\nnone\n\nExecute the frozen")
    assert (workspace / "task.txt").read_text() == "before\n"
    (workspace / "task.txt").write_text("after\n")
    grade = grade_protected_workspace(root, case, workspace, tmp_path / "grade.json")
    assert grade == {"caseId": case["caseId"], "passed": True, "reasonCode": "pass"}

    variant = next(item for item in registry["variants"] if item["variantId"] == case["caseId"])
    bare = protected_replay_condition(
        variant,
        model="gemini-3.7-flash-high",
        condition_id="bare",
        cli_path="/opt/antigravity/bin/agy",
        cli_digest="sha256:68d229d37aeabde76d15af0003d4c1ce07b211414e7452fb0309be9714ae7dd4",
        qualification_digest=QUALIFICATION_DIGEST,
        candidate_archive_digest="sha256:233366d1fd5c2fe513b533fabc106a8683635d95ca6faaf63bd36fb4a8f99d86",
    )
    integrated = protected_replay_condition(
        variant,
        model="gemini-3.7-flash-high",
        condition_id="integrated",
        cli_path="/opt/antigravity/bin/agy",
        cli_digest="sha256:68d229d37aeabde76d15af0003d4c1ce07b211414e7452fb0309be9714ae7dd4",
        qualification_digest=QUALIFICATION_DIGEST,
        candidate_archive_digest="sha256:233366d1fd5c2fe513b533fabc106a8683635d95ca6faaf63bd36fb4a8f99d86",
    )
    assert parse_contract("ConditionLock", bare) == bare
    assert bare["enabledComponents"] == []
    assert bare["pluginDigest"] == "none"
    assert integrated["enabledComponents"] == ["candidate:antigravity-behavior-engineering"]
    assert verify_protected_replay_condition(
        integrated,
        variant=variant,
        model="gemini-3.7-flash-high",
        condition_id="integrated",
        cli_path="/opt/antigravity/bin/agy",
        cli_digest="sha256:68d229d37aeabde76d15af0003d4c1ce07b211414e7452fb0309be9714ae7dd4",
        qualification_digest=QUALIFICATION_DIGEST,
        candidate_archive_digest="sha256:233366d1fd5c2fe513b533fabc106a8683635d95ca6faaf63bd36fb4a8f99d86",
        invocation_boundary_digest=release_candidate_invocation_boundary_digest(),
        capture_boundary_digest=release_candidate_capture_boundary_digest(),
    ) == integrated


@pytest.mark.parametrize(
    "drift",
    [
        "permissions",
        "sandbox",
        "slash_commands",
        "structured_output",
        "logging",
        "timeout",
        "environment",
        "qualification",
        "candidate",
        "invocation_boundary",
        "capture_boundary",
        "cli_path_and_digest",
        "timeout_coordinated",
        "model_coordinated",
        "condition_coordinated",
    ],
)
def test_protected_replay_condition_rejects_every_qualified_boundary_drift_before_valid_start(drift):
    variant = _load(REGISTRY_PATH)["variants"][0]
    candidate = "sha256:233366d1fd5c2fe513b533fabc106a8683635d95ca6faaf63bd36fb4a8f99d86"
    invocation = release_candidate_invocation_boundary_digest()
    capture = release_candidate_capture_boundary_digest()
    condition = protected_replay_condition(
        variant,
        model="gemini-3.7-flash-high",
        condition_id="integrated",
        cli_path="/opt/antigravity/bin/agy",
        cli_digest="sha256:68d229d37aeabde76d15af0003d4c1ce07b211414e7452fb0309be9714ae7dd4",
        qualification_digest=QUALIFICATION_DIGEST,
        candidate_archive_digest=candidate,
    )
    argv = condition["rawInvocation"]["argv"]
    if drift == "permissions":
        argv.remove("--dangerously-skip-permissions")
    elif drift == "sandbox":
        argv.remove("--sandbox")
    elif drift == "slash_commands":
        argv.remove("--disable-slash-commands")
    elif drift == "structured_output":
        argv[argv.index("--output-format") + 1] = "text"
    elif drift == "logging":
        argv[argv.index("--log-file") + 1] = "/tmp/drift.log"
    elif drift == "timeout":
        argv[argv.index("--print-timeout") + 1] = "1s"
    elif drift == "environment":
        condition["rawInvocation"]["environment"]["unknown"] = "drift"
    elif drift == "qualification":
        condition["environmentQualificationDigest"] = "sha256:" + "9" * 64
    elif drift == "candidate":
        condition["pluginDigest"] = "sha256:" + "9" * 64
    elif drift == "invocation_boundary":
        condition["dependencyDigests"]["qualificationInvocationBoundary"] = "sha256:" + "9" * 64
    elif drift == "capture_boundary":
        condition["dependencyDigests"]["qualificationCaptureBoundary"] = "sha256:" + "9" * 64
    elif drift == "cli_path_and_digest":
        argv[0] = "/opt/drift/bin/agy"
        condition["cliDigest"] = "sha256:" + "9" * 64
    elif drift == "timeout_coordinated":
        argv[argv.index("--print-timeout") + 1] = "1s"
        condition["rawInvocation"]["environment"]["AGY_PRINT_TIMEOUT"] = "1s"
    elif drift == "model_coordinated":
        condition["modelRequest"] = "gemini-3.1-pro-high"
        argv[argv.index("--model") + 1] = "gemini-3.1-pro-high"
    else:
        condition["conditionId"] = "bare"
        condition["pluginDigest"] = "none"
        condition["enabledComponents"] = []

    with pytest.raises(ProtectedRegressionError, match="protected_replay.qualification_boundary_mismatch"):
        verify_protected_replay_condition(
            condition,
            variant=variant,
            model="gemini-3.7-flash-high",
            condition_id="integrated",
            cli_path="/opt/antigravity/bin/agy",
            cli_digest="sha256:68d229d37aeabde76d15af0003d4c1ce07b211414e7452fb0309be9714ae7dd4",
            qualification_digest=QUALIFICATION_DIGEST,
            candidate_archive_digest=candidate,
            invocation_boundary_digest=invocation,
            capture_boundary_digest=capture,
        )


def test_starting_state_is_applied_before_agent_input_and_behaviorally_distinct(tmp_path):
    clean_root = tmp_path / "clean-bundle"
    _, clean_manifest = _build_private_bundle(clean_root)
    clean_case = clean_manifest["cases"][0]
    _replace_starting_state(
        clean_root,
        clean_case,
        _starting_state(clean_case, priorContext="clean-context", worktree="clean"),
    )

    dirty_root = tmp_path / "dirty-bundle"
    _, dirty_manifest = _build_private_bundle(dirty_root)
    dirty_case = dirty_manifest["cases"][0]
    _replace_starting_state(
        dirty_root,
        dirty_case,
        _starting_state(dirty_case, priorContext="dirty-context", worktree="dirty_unrelated"),
    )

    clean = provision_protected_workspace(clean_root, clean_case, tmp_path / "clean" / "workspace")
    dirty = provision_protected_workspace(dirty_root, dirty_case, tmp_path / "dirty" / "workspace")

    assert clean.starting_state_digest != dirty.starting_state_digest
    assert clean.applied_state_digest != dirty.applied_state_digest
    assert clean.request_path.read_bytes() != dirty.request_path.read_bytes()
    assert subprocess.run(
        ["git", "-C", str(clean.workspace), "status", "--porcelain=v1"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout == ""
    assert subprocess.run(
        ["git", "-C", str(dirty.workspace), "status", "--porcelain=v1"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout != ""
    assert regression.verify_protected_workspace_application(clean_root, clean_case, clean) == clean.applied_state_digest
    assert regression.verify_protected_workspace_application(dirty_root, dirty_case, dirty) == dirty.applied_state_digest


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        (lambda value: value.pop("priorContext"), "protected_replay.invalid_starting_state"),
        (lambda value: value.update({"unknown": True}), "protected_replay.invalid_starting_state"),
        (lambda value: value.update({"schemaVersion": "1"}), "protected_replay.invalid_starting_state"),
        (lambda value: value.update({"caseId": "different-case"}), "protected_replay.starting_state_case_mismatch"),
        (lambda value: value.update({"familyId": "different-family"}), "protected_replay.starting_state_case_mismatch"),
        (lambda value: value.update({"role": "different-role"}), "protected_replay.invalid_starting_state"),
        (lambda value: value.update({"variantToken": "different-token"}), "protected_replay.starting_state_case_mismatch"),
        (lambda value: value.update({"worktree": "unknown"}), "protected_replay.invalid_starting_state"),
    ],
)
def test_starting_state_closed_schema_rejects_missing_unknown_malformed_and_mismatched_fields(tmp_path, mutation, error):
    root = tmp_path / "protected-bundle"
    _, manifest = _build_private_bundle(root)
    case = manifest["cases"][0]
    value = _starting_state(case)
    mutation(value)
    _replace_starting_state(root, case, value)

    with pytest.raises(ProtectedRegressionError, match=error):
        provision_protected_workspace(root, case, tmp_path / "workspace")


def test_starting_state_rejects_noncanonical_and_frozen_digest_drift(tmp_path):
    malformed_root = tmp_path / "malformed-bundle"
    _, malformed_manifest = _build_private_bundle(malformed_root)
    malformed_case = malformed_manifest["cases"][0]
    _replace_starting_state(malformed_root, malformed_case, b'{"schemaVersion":1,}', canonical=False)
    with pytest.raises(ProtectedRegressionError, match="protected_replay.invalid_starting_state"):
        provision_protected_workspace(malformed_root, malformed_case, tmp_path / "malformed-workspace")

    noncanonical_root = tmp_path / "noncanonical-bundle"
    _, noncanonical_manifest = _build_private_bundle(noncanonical_root)
    noncanonical_case = noncanonical_manifest["cases"][0]
    value = _starting_state(noncanonical_case)
    _replace_starting_state(
        noncanonical_root,
        noncanonical_case,
        json.dumps(value, indent=2, sort_keys=False).encode(),
        canonical=False,
    )
    with pytest.raises(ProtectedRegressionError, match="protected_replay.noncanonical_starting_state"):
        provision_protected_workspace(noncanonical_root, noncanonical_case, tmp_path / "noncanonical-workspace")

    drift_root = tmp_path / "drift-bundle"
    _, drift_manifest = _build_private_bundle(drift_root)
    drift_case = drift_manifest["cases"][0]
    drift_path = drift_root / drift_case["workerReadable"]["startingState"]["path"]
    drift_path.chmod(0o600)
    drift_path.write_bytes(canonical_bytes(_starting_state(drift_case, priorContext="drifted")))
    drift_path.chmod(0o400)
    with pytest.raises(ProtectedRegressionError, match="protected_bundle.digest_mismatch"):
        provision_protected_workspace(drift_root, drift_case, tmp_path / "drift-workspace")


@pytest.mark.parametrize("drift", ["request", "workspace", "partial"])
def test_applied_starting_state_verification_rejects_drift_and_partial_application(tmp_path, drift):
    root = tmp_path / "protected-bundle"
    _, manifest = _build_private_bundle(root)
    case = manifest["cases"][0]
    _replace_starting_state(
        root,
        case,
        _starting_state(case, priorContext="durable-context", worktree="dirty_unrelated"),
    )
    provisioned = provision_protected_workspace(root, case, tmp_path / "workspace")

    if drift == "request":
        provisioned.request_path.write_text("changed after application", encoding="utf-8")
    elif drift == "workspace":
        (provisioned.workspace / "task.txt").write_text("changed after application", encoding="utf-8")
    else:
        (provisioned.workspace / ".abe-starting-state" / "applied.json").unlink()

    with pytest.raises(ProtectedRegressionError, match="protected_replay.applied_starting_state_mismatch"):
        regression.verify_protected_workspace_application(root, case, provisioned)
