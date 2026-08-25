"""Fail-closed validation for independently materialized protected regressions."""

from __future__ import annotations

import copy
import hashlib
import json
import stat
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from abe_eval.antigravity import (
    release_candidate_capture_boundary_digest,
    release_candidate_invocation_boundary_digest,
)
from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import canonical_contract_digest, parse_contract


class ProtectedRegressionError(ValueError):
    """Stable failure raised before a protected regression can be replayed."""


def _fail(code: str) -> None:
    raise ProtectedRegressionError(code)


_TARGET_MODELS = ("gemini-3.1-pro-high", "gemini-3.7-flash-high")
_TARGET_CONDITIONS = ("bare", "integrated")
_STARTING_STATE_FIELDS = {
    "schemaVersion",
    "caseId",
    "familyId",
    "role",
    "variantToken",
    "worktree",
    "priorContext",
}
_STARTING_STATE_WORKTREES = {"clean", "dirty_unrelated", "fresh"}
_FIXTURE_FIELDS = {"schemaVersion", "caseId", "familyId", "role", "fixtureKind", "files"}
_REQUIRED_COVERAGE_FAMILIES = {
    "cold_restart",
    "completion_honesty",
    "dirty_worktree",
    "durable_intent",
    "explicit_preference",
    "grader_leakage",
    "hook_tool_subagent_failure",
    "interrogation",
    "isolation",
    "lifecycle",
    "missing_input",
    "model_quota_drift",
    "planted_and_defect_free_review",
    "prompt_injection",
    "proportionality",
    "real_seam_evidence",
    "repair_closure",
    "root_cause_debugging",
    "soft_denial",
    "truncated_capture",
}
_AUTHORIZED_CAUSAL_GAPS = {
    "hook_tool_subagent_failure": ["subagent_failure"],
    "lifecycle": ["lifecycle"],
}
_FULLY_UNCOVERED_FAMILIES = ["lifecycle"]
_PARTIALLY_UNCOVERED_FAMILIES = [
    {"requiredFamily": "hook_tool_subagent_failure", "uncoveredAspects": ["subagent_failure"]}
]
_DIRECT_COVERAGE_PROTOCOLS = {
    "cold_restart": ["fr044-durable-intent-restart"],
    "completion_honesty": ["fr044-verification-truncation"],
    "dirty_worktree": ["fr044-preferences-dirty-worktree"],
    "durable_intent": ["fr044-durable-intent-restart"],
    "explicit_preference": ["fr044-preferences-dirty-worktree"],
    "grader_leakage": ["fr044-leakage-state-isolation"],
    "hook_tool_subagent_failure": ["fr044-hook-tool-failure"],
    "interrogation": ["fr044-interrogation-injection"],
    "isolation": ["fr044-leakage-state-isolation"],
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


@dataclass(frozen=True)
class ProvisionedProtectedWorkspace:
    """Controller-only handle for a verified worker-visible starting state."""

    workspace: Path
    request_path: Path
    starting_state_digest: str
    starting_state_semantic_digest: str
    applied_state_digest: str


def _mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(code)
    return value


def _safe_file(root: Path, record: object) -> tuple[Path, bytes, str]:
    binding = _mapping(record, "protected_bundle.invalid_file_binding")
    if set(binding) != {"path", "digest"}:
        _fail("protected_bundle.invalid_file_binding")
    raw_path = binding.get("path")
    digest = binding.get("digest")
    if not isinstance(raw_path, str) or not isinstance(digest, str):
        _fail("protected_bundle.invalid_file_binding")
    pure = PurePosixPath(raw_path)
    if pure.is_absolute() or not pure.parts or any(part in {"", ".", ".."} for part in pure.parts):
        _fail("protected_bundle.unsafe_path")
    current = root
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            _fail("protected_bundle.symlink_forbidden")
    try:
        resolved = current.resolve(strict=True)
    except FileNotFoundError:
        _fail("protected_bundle.missing_file")
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        _fail("protected_bundle.unsafe_path")
    data = resolved.read_bytes()
    if sha256_digest(data) != digest:
        _fail("protected_bundle.digest_mismatch")
    return resolved, data, digest


def _validate_manifest_identity(
    manifest: Mapping[str, Any],
    *,
    registry: Mapping[str, Any],
    source_qualification_digest: str,
    candidate_freeze_digest: str,
) -> None:
    required = {
        "schemaVersion",
        "kind",
        "bundleId",
        "createdAt",
        "producer",
        "temporalBoundary",
        "sourceLocks",
        "candidateArchiveDigest",
        "qualificationDigest",
        "caseCount",
        "cases",
    }
    if set(manifest) != required or manifest.get("schemaVersion") != 1:
        _fail("protected_bundle.invalid_manifest")
    if manifest.get("kind") != "ProtectedRegressionBundle":
        _fail("protected_bundle.invalid_manifest")
    producer = _mapping(manifest.get("producer"), "protected_bundle.invalid_producer")
    if set(producer) != {"schemaVersion", "role", "contextId", "model", "reasoning"} or producer.get(
        "schemaVersion"
    ) != 1 or producer.get("role") != "independent_evaluation_authority":
        _fail("protected_bundle.invalid_producer")
    if not all(isinstance(producer.get(field), str) and producer[field] for field in ("contextId", "model", "reasoning")):
        _fail("protected_bundle.invalid_producer")
    if not isinstance(manifest.get("bundleId"), str) or not manifest["bundleId"]:
        _fail("protected_bundle.invalid_manifest")
    created_at = manifest.get("createdAt")
    try:
        parsed_created_at = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
    except ValueError:
        _fail("protected_bundle.invalid_manifest")
    if not isinstance(created_at, str) or parsed_created_at.tzinfo is None:
        _fail("protected_bundle.invalid_manifest")
    temporal = _mapping(manifest.get("temporalBoundary"), "protected_bundle.invalid_temporal_boundary")
    if temporal != {
        "candidateCausalityFreezeDigest": candidate_freeze_digest,
        "protectedOutcomesObservedBeforeMaterialization": False,
        "candidateMutationAllowedAfterOutcome": False,
    }:
        _fail("protected_bundle.invalid_temporal_boundary")
    if manifest.get("qualificationDigest") != source_qualification_digest:
        _fail("protected_bundle.qualification_mismatch")
    if manifest.get("sourceLocks") != registry.get("sourceLocks"):
        _fail("protected_bundle.source_lock_mismatch")


def _canonical_manifest(root: Path) -> tuple[dict[str, Any], bytes]:
    manifest_path = root / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        _fail("protected_bundle.missing_manifest")
    manifest_bytes = manifest_path.read_bytes()
    try:
        manifest = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("protected_bundle.invalid_manifest")
    if not isinstance(manifest, dict) or manifest_bytes != canonical_bytes(manifest):
        _fail("protected_bundle.noncanonical_manifest")
    return manifest, manifest_bytes


def materialize_public_registry(
    bundle_root: Path,
    *,
    registry: object,
    amendment_digest: str,
    source_qualification_digest: str,
    qualification_digest: str,
    qualification_replacement_amendment_digest: str,
    expected_manifest_digest: str,
    candidate_freeze_digest: str,
    candidate_archive_digest: str,
) -> dict[str, object]:
    """Validate all frozen bindings before projecting protected digests publicly."""

    root = Path(bundle_root)
    if root.is_symlink() or not root.is_dir():
        _fail("protected_bundle.missing_root")
    manifest, manifest_bytes = _canonical_manifest(root)
    original = _mapping(registry, "protected_bundle.invalid_registry")
    projected = copy.deepcopy(original)
    variants_value = projected.get("variants")
    cases_value = manifest.get("cases")
    if not isinstance(variants_value, list) or not isinstance(cases_value, list):
        _fail("protected_bundle.invalid_cases")
    variants = {str(item.get("variantId")): item for item in variants_value if isinstance(item, dict)}
    cases = {str(item.get("caseId")): item for item in cases_value if isinstance(item, dict)}
    if len(variants) != 28 or len(cases) != 28 or set(cases) != set(variants):
        _fail("protected_bundle.incomplete_taxonomy")

    for case_id in sorted(cases):
        case = _mapping(cases[case_id], "protected_bundle.invalid_case")
        variant = _mapping(variants[case_id], "protected_bundle.invalid_registry_variant")
        worker = _mapping(case.get("workerReadable"), "protected_bundle.invalid_case")
        controller = _mapping(case.get("controllerOnly"), "protected_bundle.invalid_case")
        if set(worker) != {"agentInput", "fixture", "startingState"} or set(controller) != {
            "controller",
            "graderInput",
            "expectedResult",
        }:
            _fail("protected_bundle.invalid_case")
        worker_files = {name: _safe_file(root, binding) for name, binding in worker.items()}
        controller_files = {name: _safe_file(root, binding) for name, binding in controller.items()}
        card = _mapping(variant.get("scenarioCard"), "protected_bundle.invalid_registry_variant")
        checks = card.get("checks")
        if not isinstance(checks, list) or len(checks) != 1 or not isinstance(checks[0], dict):
            _fail("protected_bundle.check_binding_mismatch")
        card["fixtureDigest"] = worker_files["fixture"][2]
        card["startingStateDigest"] = worker_files["startingState"][2]
        card["agentInput"] = case_id
        checks[0]["implementationDigest"] = controller_files["controller"][2]
        checks[0]["inputDigest"] = controller_files["graderInput"][2]
        checks[0]["expectedResultDigest"] = controller_files["expectedResult"][2]
        variant["scenarioCardDigest"] = canonical_contract_digest("ScenarioCard", card)
        public = _mapping(variant.get("publicScenario"), "protected_bundle.invalid_registry_variant")
        public["fixtureDigest"] = worker_files["fixture"][2]
        public["hiddenMaterialDigest"] = "none"
        variant["publicScenarioDigest"] = canonical_contract_digest("PublicScenario", public)
        variant["protectedMaterialDigest"] = sha256_digest(
            canonical_bytes(sorted(item[2] for item in controller_files.values()))
        )
        seams = _mapping(variant.get("artifactSeams"), "protected_bundle.invalid_registry_variant")
        seams.pop("protectedAgentInput", None)
        seams["agentInputDigest"] = worker_files["agentInput"][2]
        seams["fixtureDigest"] = worker_files["fixture"][2]
        seams["startingStateDigest"] = worker_files["startingState"][2]

    projected["registryId"] = "regression-registry-corrected-2026-08-24"
    temporal = _mapping(manifest.get("temporalBoundary"), "protected_bundle.invalid_temporal_boundary")
    existing_correction = original.get("concreteBindingCorrection")
    original_registry_digest = (
        existing_correction.get("originalRegistryDigest")
        if isinstance(existing_correction, dict)
        else sha256_digest(canonical_bytes(original))
    )
    projected["concreteBindingCorrection"] = {
        "schemaVersion": 1,
        "claimBoundary": "semantic_protocols_and_seed_commitments_pre_treatment; concrete_bytes_post_candidate_freeze_pre_outcome",
        "originalRegistryDigest": original_registry_digest,
        "protectedBundleManifestDigest": sha256_digest(manifest_bytes),
        "candidateCausalityFreezeDigest": temporal.get("candidateCausalityFreezeDigest"),
        "sourceQualificationDigest": source_qualification_digest,
        "qualificationDigest": qualification_digest,
        "qualificationReplacementAmendmentDigest": qualification_replacement_amendment_digest,
        "scopeAmendmentDigest": amendment_digest,
        "originalConcreteBindingsAvailable": False,
        "candidateMutationAllowedAfterOutcome": False,
    }
    validate_protected_bundle(
        root,
        registry=projected,
        source_qualification_digest=source_qualification_digest,
        qualification_digest=qualification_digest,
        qualification_replacement_amendment_digest=qualification_replacement_amendment_digest,
        expected_manifest_digest=expected_manifest_digest,
        candidate_freeze_digest=candidate_freeze_digest,
        expected_candidate_archive_digest=candidate_archive_digest,
    )
    return projected


def build_protected_replay_plan(
    registry: object,
    *,
    validated_bundle: object,
    seed: str,
) -> dict[str, object]:
    """Build a deterministic, public-safe paired plan without protected paths."""

    registry_value = _mapping(registry, "protected_replay.invalid_registry")
    variants_value = registry_value.get("variants")
    if not isinstance(variants_value, list) or len(variants_value) != 28:
        _fail("protected_replay.incomplete_registry")
    variants = sorted(
        (_mapping(item, "protected_replay.invalid_variant") for item in variants_value),
        key=lambda item: str(item.get("variantId")),
    )
    if len({str(item.get("variantId")) for item in variants}) != 28:
        _fail("protected_replay.duplicate_variant")
    validated = _mapping(validated_bundle, "protected_replay.invalid_validated_bundle")
    expected_summary_fields = {
        "schemaVersion",
        "manifestDigest",
        "caseCount",
        "familyCount",
        "roles",
        "sourceQualificationDigest",
        "qualificationDigest",
        "qualificationReplacementAmendmentDigest",
        "candidateCausalityFreezeDigest",
        "candidateArchiveDigest",
        "workerControllerPathsDisjoint",
        "allDeclaredDigestsMatch",
        "causalCoverageComplete",
        "uncoveredFamilies",
        "partiallyUncoveredFamilies",
    }
    if (
        set(validated) != expected_summary_fields
        or validated.get("schemaVersion") != 1
        or validated.get("caseCount") != 28
        or validated.get("familyCount") != 14
        or validated.get("roles") != ["positive", "relevant_negative"]
        or validated.get("workerControllerPathsDisjoint") is not True
        or validated.get("allDeclaredDigestsMatch") is not True
        or validated.get("causalCoverageComplete") is not False
        or validated.get("uncoveredFamilies") != _FULLY_UNCOVERED_FAMILIES
        or validated.get("partiallyUncoveredFamilies") != _PARTIALLY_UNCOVERED_FAMILIES
    ):
        _fail("protected_replay.invalid_validated_bundle")
    bindings = {
        "manifestDigest": validated["manifestDigest"],
        "qualificationDigest": validated["qualificationDigest"],
        "candidateCausalityFreezeDigest": validated["candidateCausalityFreezeDigest"],
        "candidateArchiveDigest": validated["candidateArchiveDigest"],
    }
    if not seed or any(not isinstance(value, str) or not value.startswith("sha256:") for value in bindings.values()):
        _fail("protected_replay.invalid_binding")

    blocks: list[dict[str, object]] = []
    for model in _TARGET_MODELS:
        for variant in variants:
            case_id = str(variant.get("variantId"))
            family_id = str(variant.get("familyId"))
            role = str(variant.get("role"))
            block_id = "block-" + hashlib.sha256(f"{seed}\0{model}\0{case_id}".encode()).hexdigest()[:32]
            attempts = [
                {
                    "schemaVersion": 1,
                    "attemptId": "attempt-"
                    + hashlib.sha256(f"{seed}\0{model}\0{case_id}\0{condition}".encode()).hexdigest()[:32],
                    "conditionId": condition,
                    "ordinal": 0,
                }
                for condition in _TARGET_CONDITIONS
            ]
            attempts.sort(key=lambda item: hashlib.sha256(f"{seed}\0{block_id}\0{item['conditionId']}".encode()).digest())
            for ordinal, attempt in enumerate(attempts):
                attempt["ordinal"] = ordinal
            blocks.append(
                {
                    "schemaVersion": 1,
                    "blockId": block_id,
                    "modelRequest": model,
                    "reasoningRequest": "high",
                    "caseId": case_id,
                    "familyId": family_id,
                    "role": role,
                    "attempts": attempts,
                }
            )
    return {
        "schemaVersion": 1,
        "kind": "ProtectedRegressionReplayPlan",
        "registryDigest": sha256_digest(canonical_bytes(registry_value)),
        **bindings,
        "seedCommitmentDigest": sha256_digest(seed.encode()),
        "models": list(_TARGET_MODELS),
        "reasoningRequest": "high",
        "conditions": [
            {"schemaVersion": 1, "conditionId": "bare", "candidateArchiveDigest": "none"},
            {
                "schemaVersion": 1,
                "conditionId": "integrated",
                "candidateArchiveDigest": validated["candidateArchiveDigest"],
            },
        ],
        "attemptCount": len(blocks) * 2,
        "blocks": blocks,
    }


def _safe_relative_path(value: object, code: str) -> PurePosixPath:
    if not isinstance(value, str):
        _fail(code)
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        _fail(code)
    return path


def _parse_starting_state(data: bytes, digest: str, case: Mapping[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("protected_replay.invalid_starting_state")
    if not isinstance(value, dict) or set(value) != _STARTING_STATE_FIELDS or value.get("schemaVersion") != 1:
        _fail("protected_replay.invalid_starting_state")
    if data != canonical_bytes(value):
        _fail("protected_replay.noncanonical_starting_state")
    if sha256_digest(canonical_bytes(value)) != digest:
        _fail("protected_replay.starting_state_semantic_mismatch")
    strings = ("caseId", "familyId", "role", "variantToken", "worktree", "priorContext")
    if not all(isinstance(value.get(field), str) and value[field] for field in strings):
        _fail("protected_replay.invalid_starting_state")
    if value["role"] not in {"positive", "relevant_negative"} or value["worktree"] not in _STARTING_STATE_WORKTREES:
        _fail("protected_replay.invalid_starting_state")
    if (
        value["caseId"] != case.get("caseId")
        or value["familyId"] != case.get("familyId")
        or value["role"] != case.get("role")
        or value["variantToken"] != str(case.get("caseId", "")).rsplit("-", 1)[-1]
    ):
        _fail("protected_replay.starting_state_case_mismatch")
    return value


def _parse_fixture(data: bytes, case: Mapping[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("protected_replay.invalid_fixture")
    if not isinstance(value, dict) or set(value) != _FIXTURE_FIELDS or value.get("schemaVersion") != 1:
        _fail("protected_replay.invalid_fixture")
    if data != canonical_bytes(value):
        _fail("protected_replay.invalid_fixture")
    if (
        value.get("caseId") != case.get("caseId")
        or value.get("familyId") != case.get("familyId")
        or value.get("role") != case.get("role")
        or not isinstance(value.get("fixtureKind"), str)
        or not value["fixtureKind"]
        or not isinstance(value.get("files"), list)
    ):
        _fail("protected_replay.fixture_case_mismatch")
    return value


def _starting_state_marker(state: Mapping[str, Any], digest: str) -> bytes:
    return canonical_bytes(
        {
            "schemaVersion": 1,
            "caseId": state["caseId"],
            "startingStateDigest": digest,
            "priorContextDigest": sha256_digest(str(state["priorContext"]).encode("utf-8")),
            "worktreeStateDigest": sha256_digest(str(state["worktree"]).encode("utf-8")),
        }
    )


def _starting_state_request(state: Mapping[str, Any], request_bytes: bytes) -> bytes:
    return b"Frozen prior context:\n" + str(state["priorContext"]).encode("utf-8") + b"\n\n" + request_bytes


def _git(workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(workspace), *args],
        check=True,
        text=True,
        capture_output=True,
        env={
            "PATH": "/usr/bin:/bin",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "frozen-starting-state",
            "GIT_AUTHOR_EMAIL": "frozen-starting-state@example.invalid",
            "GIT_COMMITTER_NAME": "frozen-starting-state",
            "GIT_COMMITTER_EMAIL": "frozen-starting-state@example.invalid",
            "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z",
            "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z",
        },
    )


def _apply_worktree_state(workspace: Path, state: Mapping[str, Any]) -> None:
    worktree = str(state["worktree"])
    if worktree == "fresh":
        return
    _git(workspace, "init", "-q", "-b", "main")
    _git(workspace, "add", "--all")
    _git(workspace, "commit", "-q", "-m", "frozen starting state")
    if worktree == "dirty_unrelated":
        unrelated = workspace / ".abe-starting-state" / "unrelated-change.txt"
        unrelated.write_text("unrelated user change " + str(state["variantToken"]) + "\n", encoding="utf-8")


def _workspace_files(workspace: Path) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for path in sorted(workspace.rglob("*")):
        relative = path.relative_to(workspace)
        if relative.parts[0] == ".git":
            continue
        if path.is_symlink():
            _fail("protected_replay.applied_starting_state_mismatch")
        if path.is_file():
            files.append({"path": relative.as_posix(), "digest": sha256_digest(path.read_bytes())})
    return files


def _application_projection(
    workspace: Path,
    request_path: Path,
    state: Mapping[str, Any],
    starting_state_digest: str,
) -> dict[str, object]:
    worktree = str(state["worktree"])
    try:
        git_status = "not_applicable" if worktree == "fresh" else sha256_digest(
            _git(workspace, "status", "--porcelain=v1", "--untracked-files=all").stdout.encode("utf-8")
        )
        request_digest = sha256_digest(request_path.read_bytes())
    except (FileNotFoundError, subprocess.CalledProcessError):
        _fail("protected_replay.applied_starting_state_mismatch")
    return {
        "schemaVersion": 1,
        "caseId": state["caseId"],
        "startingStateDigest": starting_state_digest,
        "startingStateSemanticDigest": sha256_digest(canonical_bytes(state)),
        "priorContextDigest": sha256_digest(str(state["priorContext"]).encode("utf-8")),
        "worktreeStateDigest": sha256_digest(worktree.encode("utf-8")),
        "requestDigest": request_digest,
        "workspaceFiles": _workspace_files(workspace),
        "gitStatusDigest": git_status,
    }


def _expected_application_projection(
    fixture: Mapping[str, Any],
    request_bytes: bytes,
    state: Mapping[str, Any],
    starting_state_digest: str,
) -> dict[str, object]:
    file_bindings = [
        {"path": str(item["path"]), "digest": sha256_digest(str(item["content"]).encode("utf-8"))}
        for item in fixture["files"]
    ]
    marker = _starting_state_marker(state, starting_state_digest)
    file_bindings.append({"path": ".abe-starting-state/applied.json", "digest": sha256_digest(marker)})
    worktree = str(state["worktree"])
    if worktree == "dirty_unrelated":
        dirty_bytes = ("unrelated user change " + str(state["variantToken"]) + "\n").encode("utf-8")
        file_bindings.append(
            {"path": ".abe-starting-state/unrelated-change.txt", "digest": sha256_digest(dirty_bytes)}
        )
        status = b"?? .abe-starting-state/unrelated-change.txt\n"
    else:
        status = b""
    return {
        "schemaVersion": 1,
        "caseId": state["caseId"],
        "startingStateDigest": starting_state_digest,
        "startingStateSemanticDigest": sha256_digest(canonical_bytes(state)),
        "priorContextDigest": sha256_digest(str(state["priorContext"]).encode("utf-8")),
        "worktreeStateDigest": sha256_digest(worktree.encode("utf-8")),
        "requestDigest": sha256_digest(_starting_state_request(state, request_bytes)),
        "workspaceFiles": sorted(file_bindings, key=lambda item: item["path"]),
        "gitStatusDigest": "not_applicable" if worktree == "fresh" else sha256_digest(status),
    }


def provision_protected_workspace(
    bundle_root: Path,
    case: object,
    workspace: Path,
) -> ProvisionedProtectedWorkspace:
    """Provision and verify the complete worker-visible frozen starting state."""

    root = Path(bundle_root)
    case_value = _mapping(case, "protected_replay.invalid_case")
    worker = _mapping(case_value.get("workerReadable"), "protected_replay.invalid_case")
    if set(worker) != {"agentInput", "fixture", "startingState"}:
        _fail("protected_replay.invalid_case")
    _, request_bytes, _ = _safe_file(root, worker["agentInput"])
    _, fixture_bytes, _ = _safe_file(root, worker["fixture"])
    _, starting_state_bytes, starting_state_digest = _safe_file(root, worker["startingState"])
    starting_state = _parse_starting_state(starting_state_bytes, starting_state_digest, case_value)
    fixture = _parse_fixture(fixture_bytes, case_value)
    files = fixture.get("files")
    if not isinstance(files, list):
        _fail("protected_replay.invalid_fixture")
    workspace_path = Path(workspace)
    if workspace_path.exists() and any(workspace_path.iterdir()):
        _fail("protected_replay.workspace_not_empty")
    workspace_path.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    for item in files:
        file_value = _mapping(item, "protected_replay.invalid_fixture_file")
        if set(file_value) != {"path", "content"} or not isinstance(file_value.get("content"), str):
            _fail("protected_replay.invalid_fixture_file")
        relative = _safe_relative_path(file_value.get("path"), "protected_replay.unsafe_fixture_path")
        relative_text = relative.as_posix()
        if relative_text in seen or relative.parts[0] == ".git":
            _fail("protected_replay.unsafe_fixture_path")
        seen.add(relative_text)
        destination = workspace_path.joinpath(*relative.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink():
            _fail("protected_replay.unsafe_fixture_path")
        destination.write_text(str(file_value["content"]), encoding="utf-8")
    marker_path = workspace_path / ".abe-starting-state" / "applied.json"
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_bytes(_starting_state_marker(starting_state, starting_state_digest))
    request_path = workspace_path.parent / "request.md"
    request_path.write_bytes(_starting_state_request(starting_state, request_bytes))
    _apply_worktree_state(workspace_path, starting_state)
    expected = _expected_application_projection(fixture, request_bytes, starting_state, starting_state_digest)
    observed = _application_projection(workspace_path, request_path, starting_state, starting_state_digest)
    if observed != expected:
        _fail("protected_replay.applied_starting_state_mismatch")
    return ProvisionedProtectedWorkspace(
        workspace=workspace_path,
        request_path=request_path,
        starting_state_digest=starting_state_digest,
        starting_state_semantic_digest=sha256_digest(canonical_bytes(starting_state)),
        applied_state_digest=sha256_digest(canonical_bytes(observed)),
    )


def verify_protected_workspace_application(
    bundle_root: Path,
    case: object,
    provisioned: ProvisionedProtectedWorkspace,
) -> str:
    """Re-verify the frozen binding and the resulting state immediately before agent input."""

    root = Path(bundle_root)
    case_value = _mapping(case, "protected_replay.invalid_case")
    worker = _mapping(case_value.get("workerReadable"), "protected_replay.invalid_case")
    _, request_bytes, _ = _safe_file(root, worker["agentInput"])
    _, fixture_bytes, _ = _safe_file(root, worker["fixture"])
    _, state_bytes, state_digest = _safe_file(root, worker["startingState"])
    state = _parse_starting_state(state_bytes, state_digest, case_value)
    fixture = _parse_fixture(fixture_bytes, case_value)
    expected = _expected_application_projection(fixture, request_bytes, state, state_digest)
    observed = _application_projection(provisioned.workspace, provisioned.request_path, state, state_digest)
    observed_digest = sha256_digest(canonical_bytes(observed))
    if (
        observed != expected
        or provisioned.starting_state_digest != state_digest
        or provisioned.starting_state_semantic_digest != sha256_digest(canonical_bytes(state))
        or provisioned.applied_state_digest != observed_digest
    ):
        _fail("protected_replay.applied_starting_state_mismatch")
    return observed_digest


def grade_protected_workspace(
    bundle_root: Path,
    case: object,
    workspace: Path,
    output_path: Path,
    *,
    timeout_seconds: float = 30,
) -> dict[str, object]:
    """Execute one controller-only grader after the worker attempt terminates."""

    root = Path(bundle_root)
    case_value = _mapping(case, "protected_replay.invalid_case")
    controller = _mapping(case_value.get("controllerOnly"), "protected_replay.invalid_case")
    if set(controller) != {"controller", "graderInput", "expectedResult"}:
        _fail("protected_replay.invalid_case")
    controller_path, _, _ = _safe_file(root, controller["controller"])
    grader_input_path, _, _ = _safe_file(root, controller["graderInput"])
    expected_path, _, _ = _safe_file(root, controller["expectedResult"])
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            sys.executable,
            str(controller_path),
            "--workspace",
            str(Path(workspace)),
            "--grader-input",
            str(grader_input_path),
            "--expected-result",
            str(expected_path),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout_seconds,
    )
    if completed.returncode not in {0, 1} or not output.is_file():
        _fail("protected_replay.grader_failure")
    try:
        grade = json.loads(output.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("protected_replay.invalid_grade")
    if (
        not isinstance(grade, dict)
        or set(grade) != {"caseId", "passed", "reasonCode"}
        or grade.get("caseId") != case_value.get("caseId")
        or not isinstance(grade.get("passed"), bool)
        or not isinstance(grade.get("reasonCode"), str)
        or completed.returncode != (0 if grade["passed"] else 1)
    ):
        _fail("protected_replay.invalid_grade")
    return grade


def protected_replay_condition(
    variant: object,
    *,
    model: str,
    condition_id: str,
    cli_path: str,
    cli_digest: str,
    qualification_digest: str,
    candidate_archive_digest: str,
) -> dict[str, object]:
    """Bind one live CLI invocation to the frozen case and condition."""

    variant_value = _mapping(variant, "protected_replay.invalid_variant")
    if model not in _TARGET_MODELS or condition_id not in _TARGET_CONDITIONS:
        _fail("protected_replay.invalid_condition")
    scenario = _mapping(variant_value.get("scenarioCard"), "protected_replay.invalid_variant")
    resource = _mapping(scenario.get("resourceEnvelope"), "protected_replay.invalid_variant")
    wall_time = _mapping(resource.get("wallTime"), "protected_replay.invalid_variant")
    wall_time_cap = wall_time.get("cap")
    if not isinstance(wall_time_cap, int) or wall_time_cap <= 0:
        _fail("protected_replay.invalid_variant")
    plugin_digest = "none" if condition_id == "bare" else candidate_archive_digest
    enabled = [] if condition_id == "bare" else ["candidate:antigravity-behavior-engineering"]
    invocation_boundary_digest = release_candidate_invocation_boundary_digest()
    capture_boundary_digest = release_candidate_capture_boundary_digest()
    return parse_contract(
        "ConditionLock",
        {
            "schemaVersion": 1,
            "conditionId": condition_id,
            "modelRequest": model,
            "reasoningRequest": "high",
            "provider": "google",
            "authenticationMode": "headless-yolo-disposable-profile",
            "fallbackPolicy": "deny",
            "agentSelection": "antigravity",
            "subagentSelection": "not_applicable",
            "rawInvocation": {
                "schemaVersion": 1,
                "argv": [
                    cli_path,
                    "--dangerously-skip-permissions",
                    "--sandbox",
                    "--disable-slash-commands",
                    "--model",
                    model,
                    "--effort",
                    "high",
                    "-p",
                    "__ABE_VERIFIED_REQUEST__",
                    "--output-format",
                    "stream-json",
                    "--log-file",
                    "/workspace/output/agy.log",
                    "--print-timeout",
                    str(wall_time_cap) + "s",
                ],
                "environment": {
                    "AGY_PERMISSION_MODE": "always-proceed",
                    "AGY_PRINT_TIMEOUT": str(wall_time_cap) + "s",
                    "ABE_INVOCATION_BOUNDARY_DIGEST": invocation_boundary_digest,
                    "ABE_CAPTURE_BOUNDARY_DIGEST": capture_boundary_digest,
                },
            },
            "cliDigest": cli_digest,
            "pluginDigest": plugin_digest,
            "dependencyDigests": {
                "candidateArchive": candidate_archive_digest,
                "qualificationInvocationBoundary": invocation_boundary_digest,
                "qualificationCaptureBoundary": capture_boundary_digest,
            },
            "enabledComponents": enabled,
            "authorityManifestDigest": canonical_contract_digest("AuthorityManifest", scenario["authorityManifest"]),
            "resourceEnvelopeDigest": canonical_contract_digest("ResourceEnvelope", scenario["resourceEnvelope"]),
            "toolInventoryDigest": sha256_digest(canonical_bytes({"sandbox": True, "condition": condition_id})),
            "permissionDigest": sha256_digest(canonical_bytes({"mode": "always-proceed", "sandbox": True})),
            "environmentDigest": sha256_digest(
                canonical_bytes({"profile": "disposable-clone", "caseId": variant_value.get("variantId")})
            ),
            "environmentQualificationDigest": qualification_digest,
        },
    )


def verify_protected_replay_condition(
    condition: object,
    *,
    variant: object,
    model: str,
    condition_id: str,
    cli_path: str,
    cli_digest: str,
    qualification_digest: str,
    candidate_archive_digest: str,
    invocation_boundary_digest: str,
    capture_boundary_digest: str,
) -> dict[str, object]:
    """Reject any condition drift from the qualified invocation before valid start."""

    parsed = parse_contract("ConditionLock", condition)
    if (
        release_candidate_invocation_boundary_digest() != invocation_boundary_digest
        or release_candidate_capture_boundary_digest() != capture_boundary_digest
    ):
        _fail("protected_replay.qualification_boundary_mismatch")
    expected = protected_replay_condition(
        variant,
        model=model,
        condition_id=condition_id,
        cli_path=cli_path,
        cli_digest=cli_digest,
        qualification_digest=qualification_digest,
        candidate_archive_digest=candidate_archive_digest,
    )
    if parsed != expected:
        _fail("protected_replay.qualification_boundary_mismatch")
    return parsed


def validate_regression_taxonomy(registry: object) -> dict[str, object]:
    """Validate direct causal coverage while preserving authorized explicit gaps."""

    value = _mapping(registry, "regression_taxonomy.invalid_registry")
    variants_value = value.get("variants")
    coverage_value = value.get("coverage")
    if not isinstance(variants_value, list) or not isinstance(coverage_value, list):
        _fail("regression_taxonomy.incomplete_family")
    if len(variants_value) != 28:
        _fail("regression_taxonomy.incomplete_family")
    variants = {
        str(item.get("variantId")): _mapping(item, "regression_taxonomy.incomplete_family")
        for item in variants_value
        if isinstance(item, dict)
    }
    if len(variants) != 28 or len({str(item.get("familyId")) for item in variants.values()}) != 14:
        _fail("regression_taxonomy.incomplete_family")
    coverage = {
        str(item.get("requiredFamily")): _mapping(item, "regression_taxonomy.incomplete_family")
        for item in coverage_value
        if isinstance(item, dict)
    }
    if len(coverage) != len(coverage_value) or set(coverage) != _REQUIRED_COVERAGE_FAMILIES:
        _fail("regression_taxonomy.incomplete_family")

    claim_fields = (
        "protocolFamilyIds",
        "positiveVariantIds",
        "relevantNegativeVariantIds",
        "realArtifactSeams",
        "classificationDigests",
        "analysisLockDigests",
    )
    for family_name, item in coverage.items():
        expected_gap = _AUTHORIZED_CAUSAL_GAPS.get(family_name)
        if family_name == "lifecycle":
            if (
                item.get("coverageStatus") != "uncovered"
                or item.get("uncoveredAspects") != expected_gap
                or item.get("eligibleForT034Selection") is not False
                or item.get("eligibleForReleaseClaim") is not False
                or any(item.get(field) != [] for field in claim_fields)
            ):
                _fail("regression_taxonomy.invalid_gap")
            continue

        expected_status = "partial" if expected_gap is not None else "covered"
        if item.get("coverageStatus") != expected_status:
            _fail("regression_taxonomy.invalid_gap" if expected_gap is not None else "regression_taxonomy.incomplete_family")
        if expected_gap is not None and (
            item.get("coveredAspects") != ["hook_failure", "tool_failure"]
            or item.get("uncoveredAspects") != expected_gap
            or item.get("uncoveredAspectsEligibleForT034Selection") is not False
            or item.get("uncoveredAspectsEligibleForReleaseClaim") is not False
        ):
            _fail("regression_taxonomy.invalid_gap")
        positive_ids = item.get("positiveVariantIds")
        negative_ids = item.get("relevantNegativeVariantIds")
        protocol_ids = item.get("protocolFamilyIds")
        seams = item.get("realArtifactSeams")
        classifications = item.get("classificationDigests")
        analyses = item.get("analysisLockDigests")
        if not all(isinstance(field, list) and field for field in (positive_ids, negative_ids, protocol_ids, seams, classifications, analyses)):
            _fail("regression_taxonomy.incomplete_family")
        expected_protocols = _DIRECT_COVERAGE_PROTOCOLS.get(family_name)
        if protocol_ids != expected_protocols:
            _fail("regression_taxonomy.incomplete_family")
        expected_positive = {
            case_id
            for case_id, variant in variants.items()
            if variant.get("familyId") in expected_protocols and variant.get("role") == "positive"
        }
        expected_negative = {
            case_id
            for case_id, variant in variants.items()
            if variant.get("familyId") in expected_protocols and variant.get("role") == "relevant_negative"
        }
        if set(positive_ids) != expected_positive or set(negative_ids) != expected_negative:
            _fail("regression_taxonomy.incomplete_family")
        selected_ids = [*positive_ids, *negative_ids]
        if len(selected_ids) != len(set(selected_ids)) or any(case_id not in variants for case_id in selected_ids):
            _fail("regression_taxonomy.incomplete_family")
        selected = [variants[case_id] for case_id in selected_ids]
        if any(variants[case_id].get("role") != "positive" for case_id in positive_ids):
            _fail("regression_taxonomy.incomplete_family")
        if any(variants[case_id].get("role") != "relevant_negative" for case_id in negative_ids):
            _fail("regression_taxonomy.incomplete_family")
        if set(protocol_ids) != {item_value.get("familyId") for item_value in selected}:
            _fail("regression_taxonomy.incomplete_family")
        if set(classifications) != {item_value.get("classificationPolicyDigest") for item_value in selected}:
            _fail("regression_taxonomy.incomplete_family")
        if set(analyses) != {item_value.get("analysisLockDigest") for item_value in selected}:
            _fail("regression_taxonomy.incomplete_family")
        declared_seams = {
            seam
            for item_value in selected
            for seam in _mapping(item_value.get("artifactSeams"), "regression_taxonomy.incomplete_family").get("labels", [])
        }
        if set(seams) != declared_seams:
            _fail("regression_taxonomy.incomplete_family")

    for variant in variants.values():
        card = _mapping(variant.get("scenarioCard"), "regression_taxonomy.incomplete_family")
        seams = _mapping(variant.get("artifactSeams"), "regression_taxonomy.incomplete_family")
        if set(seams) != {
            "labels",
            "agentInputDigest",
            "fixtureDigest",
            "startingStateDigest",
            "checkIds",
        }:
            _fail("regression_taxonomy.incomplete_family")
        labels = seams.get("labels")
        check_ids = seams.get("checkIds")
        checks = card.get("checks")
        if (
            not isinstance(labels, list)
            or not labels
            or not isinstance(check_ids, list)
            or not check_ids
            or not isinstance(checks, list)
            or check_ids != [check.get("checkId") for check in checks if isinstance(check, dict)]
            or seams.get("fixtureDigest") != card.get("fixtureDigest")
            or seams.get("startingStateDigest") != card.get("startingStateDigest")
            or not isinstance(seams.get("agentInputDigest"), str)
            or not seams["agentInputDigest"].startswith("sha256:")
        ):
            _fail("regression_taxonomy.incomplete_family")

    fully_uncovered = sorted(
        family_name for family_name, item in coverage.items() if item.get("coverageStatus") == "uncovered"
    )
    partially_uncovered = [
        {"requiredFamily": family_name, "uncoveredAspects": item.get("uncoveredAspects")}
        for family_name, item in sorted(coverage.items())
        if item.get("coverageStatus") == "partial"
    ]
    causal_coverage_complete = not fully_uncovered and not partially_uncovered
    if (
        value.get("causalCoverageComplete") is not causal_coverage_complete
        or value.get("uncoveredFamilies") != fully_uncovered
        or value.get("partiallyUncoveredFamilies") != partially_uncovered
    ):
        _fail("regression_taxonomy.invalid_gap")

    return {
        "schemaVersion": 1,
        "causalCoverageComplete": causal_coverage_complete,
        "uncoveredFamilies": fully_uncovered,
        "partiallyUncoveredFamilies": partially_uncovered,
    }


def validate_protected_bundle(
    bundle_root: Path,
    *,
    registry: object,
    source_qualification_digest: str,
    qualification_digest: str,
    qualification_replacement_amendment_digest: str,
    expected_manifest_digest: str,
    candidate_freeze_digest: str,
    expected_candidate_archive_digest: str,
) -> dict[str, object]:
    """Validate private bytes and return only a public-safe binding summary."""

    root = Path(bundle_root)
    if root.is_symlink() or not root.is_dir():
        _fail("protected_bundle.missing_root")
    manifest, manifest_bytes = _canonical_manifest(root)
    if sha256_digest(manifest_bytes) != expected_manifest_digest:
        _fail("protected_bundle.manifest_identity_mismatch")
    registry_value = _mapping(registry, "protected_bundle.invalid_registry")
    taxonomy = validate_regression_taxonomy(registry_value)
    _validate_manifest_identity(
        manifest,
        registry=registry_value,
        source_qualification_digest=source_qualification_digest,
        candidate_freeze_digest=candidate_freeze_digest,
    )
    if manifest.get("candidateArchiveDigest") != expected_candidate_archive_digest:
        _fail("protected_bundle.candidate_archive_mismatch")

    variants_value = registry_value.get("variants")
    cases_value = manifest.get("cases")
    if (
        not isinstance(variants_value, list)
        or not isinstance(cases_value, list)
        or len(variants_value) != 28
        or len(cases_value) != 28
    ):
        _fail("protected_bundle.invalid_cases")
    variants = {str(item.get("variantId")): item for item in variants_value if isinstance(item, dict)}
    cases = {str(item.get("caseId")): item for item in cases_value if isinstance(item, dict)}
    if len(variants) != 28 or len(cases) != 28 or set(cases) != set(variants) or manifest.get("caseCount") != 28:
        _fail("protected_bundle.incomplete_taxonomy")
    family_ids = {str(item.get("familyId")) for item in variants.values()}
    roles = {str(item.get("role")) for item in variants.values()}
    if len(family_ids) != 14 or roles != {"positive", "relevant_negative"}:
        _fail("protected_bundle.incomplete_taxonomy")
    family_roles = {(str(item.get("familyId")), str(item.get("role"))) for item in variants.values()}
    if len(family_roles) != 28:
        _fail("protected_bundle.incomplete_taxonomy")
    correction = _mapping(registry_value.get("concreteBindingCorrection"), "protected_bundle.invalid_registry")
    if (
        correction.get("protectedBundleManifestDigest") != expected_manifest_digest
        or correction.get("sourceQualificationDigest") != source_qualification_digest
        or correction.get("qualificationDigest") != qualification_digest
        or correction.get("qualificationReplacementAmendmentDigest") != qualification_replacement_amendment_digest
        or correction.get("candidateCausalityFreezeDigest") != candidate_freeze_digest
    ):
        _fail("protected_bundle.correction_binding_mismatch")

    public_bytes = canonical_bytes(registry_value)
    all_paths: set[str] = set()
    all_digests_match = True
    for case_id in sorted(cases):
        case = _mapping(cases[case_id], "protected_bundle.invalid_case")
        variant = _mapping(variants[case_id], "protected_bundle.invalid_registry_variant")
        if case.get("schemaVersion") != 1 or case.get("partition") != "regression":
            _fail("protected_bundle.partition_mismatch")
        if case.get("familyId") != variant.get("familyId") or case.get("role") != variant.get("role"):
            _fail("protected_bundle.case_binding_mismatch")
        worker = _mapping(case.get("workerReadable"), "protected_bundle.invalid_case")
        controller = _mapping(case.get("controllerOnly"), "protected_bundle.invalid_case")
        card = _mapping(variant.get("scenarioCard"), "protected_bundle.invalid_registry_variant")
        try:
            _safe_relative_path(case.get("logicalAgentInputPath"), "protected_bundle.case_binding_mismatch")
        except ProtectedRegressionError:
            _fail("protected_bundle.case_binding_mismatch")
        worker_paths = {str(_mapping(value, "protected_bundle.invalid_file_binding").get("path")) for value in worker.values()}
        controller_paths = {
            str(_mapping(value, "protected_bundle.invalid_file_binding").get("path")) for value in controller.values()
        }
        if worker_paths & controller_paths:
            _fail("protected_bundle.worker_controller_overlap")
        if set(worker) != {"agentInput", "fixture", "startingState"} or set(controller) != {
            "controller",
            "graderInput",
            "expectedResult",
        }:
            _fail("protected_bundle.invalid_case")
        if all_paths & (worker_paths | controller_paths):
            _fail("protected_bundle.duplicate_path")
        all_paths.update(worker_paths | controller_paths)

        worker_files = {name: _safe_file(root, binding) for name, binding in worker.items()}
        controller_files = {name: _safe_file(root, binding) for name, binding in controller.items()}
        for file_path, _, _ in controller_files.values():
            if stat.S_IMODE(file_path.stat().st_mode) & 0o077:
                _fail("protected_bundle.controller_permissions")
        controller_path_bytes = [path_value.encode("utf-8") for path_value in controller_paths]
        for _, data, _ in worker_files.values():
            if any(marker in data for marker in (b"RAW_CANARY_", b"GRADER_INSTRUCTION:", *controller_path_bytes)):
                _fail("protected_bundle.grader_leakage")
        for _, data, _ in (*worker_files.values(), *controller_files.values()):
            if len(data) >= 8 and data in public_bytes:
                _fail("protected_bundle.public_byte_leak")

        checks = card.get("checks")
        if not isinstance(checks, list) or len(checks) != 1 or not isinstance(checks[0], dict):
            _fail("protected_bundle.check_binding_mismatch")
        check = checks[0]
        expected_bindings = {
            "agentInputDigest": worker_files["agentInput"][2],
            "fixtureDigest": worker_files["fixture"][2],
            "startingStateDigest": worker_files["startingState"][2],
            "implementationDigest": controller_files["controller"][2],
            "inputDigest": controller_files["graderInput"][2],
            "expectedResultDigest": controller_files["expectedResult"][2],
        }
        if card.get("fixtureDigest") != expected_bindings["fixtureDigest"]:
            _fail("protected_bundle.fixture_binding_mismatch")
        if card.get("agentInput") != case_id:
            _fail("protected_bundle.public_binding_mismatch")
        if card.get("startingStateDigest") != expected_bindings["startingStateDigest"]:
            _fail("protected_bundle.starting_state_binding_mismatch")
        for field in ("implementationDigest", "inputDigest", "expectedResultDigest"):
            if check.get(field) != expected_bindings[field]:
                _fail("protected_bundle.check_binding_mismatch")
        if variant.get("scenarioCardDigest") != canonical_contract_digest("ScenarioCard", card):
            _fail("protected_bundle.scenario_digest_mismatch")
        public = parse_contract("PublicScenario", variant.get("publicScenario"))
        hidden_digest = sha256_digest(canonical_bytes(sorted(item[2] for item in controller_files.values())))
        if public.get("fixtureDigest") != expected_bindings["fixtureDigest"] or public.get("hiddenMaterialDigest") != "none":
            _fail("protected_bundle.public_binding_mismatch")
        if variant.get("protectedMaterialDigest") != hidden_digest:
            _fail("protected_bundle.public_binding_mismatch")
        if variant.get("publicScenarioDigest") != canonical_contract_digest("PublicScenario", public):
            _fail("protected_bundle.public_binding_mismatch")
        seams = _mapping(variant.get("artifactSeams"), "protected_bundle.invalid_registry_variant")
        if (
            "protectedAgentInput" in seams
            or seams.get("agentInputDigest") != expected_bindings["agentInputDigest"]
            or seams.get("fixtureDigest") != expected_bindings["fixtureDigest"]
            or seams.get("startingStateDigest") != expected_bindings["startingStateDigest"]
        ):
            _fail("protected_bundle.artifact_seam_mismatch")

    return {
        "schemaVersion": 1,
        "manifestDigest": sha256_digest(manifest_bytes),
        "caseCount": len(cases),
        "familyCount": len(family_ids),
        "roles": sorted(roles),
        "sourceQualificationDigest": source_qualification_digest,
        "qualificationDigest": qualification_digest,
        "qualificationReplacementAmendmentDigest": qualification_replacement_amendment_digest,
        "candidateCausalityFreezeDigest": candidate_freeze_digest,
        "candidateArchiveDigest": manifest["candidateArchiveDigest"],
        "workerControllerPathsDisjoint": True,
        "allDeclaredDigestsMatch": all_digests_match,
        "causalCoverageComplete": taxonomy["causalCoverageComplete"],
        "uncoveredFamilies": taxonomy["uncoveredFamilies"],
        "partiallyUncoveredFamilies": taxonomy["partiallyUncoveredFamilies"],
    }


__all__ = [
    "ProvisionedProtectedWorkspace",
    "ProtectedRegressionError",
    "build_protected_replay_plan",
    "grade_protected_workspace",
    "materialize_public_registry",
    "protected_replay_condition",
    "provision_protected_workspace",
    "validate_protected_bundle",
    "validate_regression_taxonomy",
    "verify_protected_replay_condition",
    "verify_protected_workspace_application",
]
