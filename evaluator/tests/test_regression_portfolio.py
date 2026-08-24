from __future__ import annotations

import copy
import json
import stat
from pathlib import Path
from typing import Any

import pytest

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
QUALIFICATION_DIGEST = "sha256:252cb549dc4dba878a352e049ea75c2d076b59aa9f0dcd111aa5c626cb6699f2"


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
                        "fixture": variant["familyId"],
                        "files": [{"path": "task.txt", "content": "before\n"}],
                    }
                ),
                root=root,
            ),
            "startingState": _write_protected(
                case_root / "worker" / "starting-state.json",
                canonical_bytes({"schemaVersion": 1, "caseId": case_id, "state": variant["role"]}),
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
        cases.append(
            {
                "schemaVersion": 1,
                "caseId": case_id,
                "familyId": variant["familyId"],
                "role": variant["role"],
                "partition": "regression",
                "logicalAgentInputPath": variant["scenarioCard"]["agentInput"],
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
        "sourceLocks": registry["sourceLocks"],
        "candidateArchiveDigest": "sha256:233366d1fd5c2fe513b533fabc106a8683635d95ca6faaf63bd36fb4a8f99d86",
        "qualificationDigest": QUALIFICATION_DIGEST,
        "caseCount": len(cases),
        "cases": cases,
    }
    (root / "manifest.json").write_bytes(canonical_bytes(manifest))
    (root / "manifest.json").chmod(0o400)
    return registry, manifest


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
            assert variant["scenarioCard"]["agentInput"] == card["agentInput"]
            assert variant["scenarioCard"]["resourceEnvelope"] == card["resourceEnvelope"]
            assert variant["scenarioCard"]["classificationPolicyDigest"] == card["classificationPolicyDigest"]
            assert variant["publicScenario"]["publicScenarioId"] == public["publicScenarioId"]
            assert variant["publicScenario"]["hiddenMaterialDigest"] == "none"
            assert variant["artifactSeams"]["labels"] == protocol["preTreatmentLabels"]["evidenceSeams"]
            assert variant["artifactSeams"]["protectedAgentInput"] == card["agentInput"]
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
        qualification_digest=QUALIFICATION_DIGEST,
        candidate_freeze_digest=CANDIDATE_FREEZE_DIGEST,
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
    )

    assert projected["variants"] == expected_registry["variants"]
    assert projected["concreteBindingCorrection"] == {
        "schemaVersion": 1,
        "claimBoundary": "semantic_protocols_and_seed_commitments_pre_treatment; concrete_bytes_post_candidate_freeze_pre_outcome",
        "originalRegistryDigest": _digest_object(original_registry),
        "protectedBundleManifestDigest": sha256_digest(canonical_bytes(manifest)),
        "candidateCausalityFreezeDigest": CANDIDATE_FREEZE_DIGEST,
        "qualificationDigest": QUALIFICATION_DIGEST,
        "scopeAmendmentDigest": "sha256:d6210f8a0bc595badf6171a0b8ee671f2f5109433fc7adcf6a7d59fb5995f3f4",
        "originalConcreteBindingsAvailable": False,
        "candidateMutationAllowedAfterOutcome": False,
    }
    assert "test-only-" not in json.dumps(projected, sort_keys=True)


def test_private_bundle_fails_closed_on_missing_bytes_digest_drift_and_grader_visibility(tmp_path):
    missing_root = tmp_path / "missing"
    missing_registry, missing_manifest = _build_private_bundle(missing_root)
    missing_path = missing_root / missing_manifest["cases"][0]["controllerOnly"]["expectedResult"]["path"]
    missing_path.unlink()
    with pytest.raises(ProtectedRegressionError, match="protected_bundle.missing_file"):
        validate_protected_bundle(
            missing_root,
            registry=missing_registry,
            qualification_digest=QUALIFICATION_DIGEST,
            candidate_freeze_digest=CANDIDATE_FREEZE_DIGEST,
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
            qualification_digest=QUALIFICATION_DIGEST,
            candidate_freeze_digest=CANDIDATE_FREEZE_DIGEST,
        )

    leak_root = tmp_path / "leak"
    leak_registry, leak_manifest = _build_private_bundle(leak_root)
    leaked = leak_manifest["cases"][0]["controllerOnly"]["graderInput"]
    leak_manifest["cases"][0]["workerReadable"]["graderInput"] = leaked
    (leak_root / "manifest.json").chmod(0o600)
    (leak_root / "manifest.json").write_bytes(canonical_bytes(leak_manifest))
    (leak_root / "manifest.json").chmod(0o400)
    with pytest.raises(ProtectedRegressionError, match="protected_bundle.worker_controller_overlap"):
        validate_protected_bundle(
            leak_root,
            registry=leak_registry,
            qualification_digest=QUALIFICATION_DIGEST,
            candidate_freeze_digest=CANDIDATE_FREEZE_DIGEST,
        )


def test_protected_replay_plan_is_deterministic_complete_paired_and_public_safe():
    registry = _load(REGISTRY_PATH)
    manifest_digest = "sha256:2d0450f5b4455787a1e3563a72e7a148792815c5d65a838a7594b5f5726946f9"
    candidate_archive_digest = "sha256:233366d1fd5c2fe513b533fabc106a8683635d95ca6faaf63bd36fb4a8f99d86"

    first = build_protected_replay_plan(
        registry,
        manifest_digest=manifest_digest,
        qualification_digest=QUALIFICATION_DIGEST,
        candidate_freeze_digest=CANDIDATE_FREEZE_DIGEST,
        candidate_archive_digest=candidate_archive_digest,
        seed="t033-protected-replay-v1",
    )
    second = build_protected_replay_plan(
        registry,
        manifest_digest=manifest_digest,
        qualification_digest=QUALIFICATION_DIGEST,
        candidate_freeze_digest=CANDIDATE_FREEZE_DIGEST,
        candidate_archive_digest=candidate_archive_digest,
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

    request_path = provision_protected_workspace(root, case, workspace)
    assert request_path.read_text().startswith("Execute the frozen")
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
