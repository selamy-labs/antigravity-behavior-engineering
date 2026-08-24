"""Fail-closed validation for independently materialized protected regressions."""

from __future__ import annotations

import copy
import hashlib
import json
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import canonical_contract_digest, parse_contract


class ProtectedRegressionError(ValueError):
    """Stable failure raised before a protected regression can be replayed."""


def _fail(code: str) -> None:
    raise ProtectedRegressionError(code)


_TARGET_MODELS = ("gemini-3.1-pro-high", "gemini-3.7-flash-high")
_TARGET_CONDITIONS = ("bare", "integrated")


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
    qualification_digest: str,
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
    if producer.get("role") != "independent_evaluation_authority":
        _fail("protected_bundle.invalid_producer")
    if not all(isinstance(producer.get(field), str) and producer[field] for field in ("contextId", "model", "reasoning")):
        _fail("protected_bundle.invalid_producer")
    temporal = _mapping(manifest.get("temporalBoundary"), "protected_bundle.invalid_temporal_boundary")
    if temporal != {
        "candidateCausalityFreezeDigest": candidate_freeze_digest,
        "protectedOutcomesObservedBeforeMaterialization": False,
        "candidateMutationAllowedAfterOutcome": False,
    }:
        _fail("protected_bundle.invalid_temporal_boundary")
    if manifest.get("qualificationDigest") != qualification_digest:
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
) -> dict[str, object]:
    """Project only concrete protected digests into the public regression registry."""

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
        seams["fixtureDigest"] = worker_files["fixture"][2]
        seams["startingStateDigest"] = worker_files["startingState"][2]

    projected["registryId"] = "regression-registry-corrected-2026-08-24"
    temporal = _mapping(manifest.get("temporalBoundary"), "protected_bundle.invalid_temporal_boundary")
    projected["concreteBindingCorrection"] = {
        "schemaVersion": 1,
        "claimBoundary": "semantic_protocols_and_seed_commitments_pre_treatment; concrete_bytes_post_candidate_freeze_pre_outcome",
        "originalRegistryDigest": sha256_digest(canonical_bytes(original)),
        "protectedBundleManifestDigest": sha256_digest(manifest_bytes),
        "candidateCausalityFreezeDigest": temporal.get("candidateCausalityFreezeDigest"),
        "qualificationDigest": manifest.get("qualificationDigest"),
        "scopeAmendmentDigest": amendment_digest,
        "originalConcreteBindingsAvailable": False,
        "candidateMutationAllowedAfterOutcome": False,
    }
    return projected


def build_protected_replay_plan(
    registry: object,
    *,
    manifest_digest: str,
    qualification_digest: str,
    candidate_freeze_digest: str,
    candidate_archive_digest: str,
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
    bindings = {
        "manifestDigest": manifest_digest,
        "qualificationDigest": qualification_digest,
        "candidateCausalityFreezeDigest": candidate_freeze_digest,
        "candidateArchiveDigest": candidate_archive_digest,
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
            {"schemaVersion": 1, "conditionId": "integrated", "candidateArchiveDigest": candidate_archive_digest},
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


def provision_protected_workspace(bundle_root: Path, case: object, workspace: Path) -> Path:
    """Provision worker-readable fixture bytes without exposing controller material."""

    root = Path(bundle_root)
    case_value = _mapping(case, "protected_replay.invalid_case")
    worker = _mapping(case_value.get("workerReadable"), "protected_replay.invalid_case")
    if set(worker) != {"agentInput", "fixture", "startingState"}:
        _fail("protected_replay.invalid_case")
    _, request_bytes, _ = _safe_file(root, worker["agentInput"])
    _, fixture_bytes, _ = _safe_file(root, worker["fixture"])
    _safe_file(root, worker["startingState"])
    try:
        fixture = json.loads(fixture_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("protected_replay.invalid_fixture")
    if not isinstance(fixture, dict) or fixture.get("caseId") != case_value.get("caseId"):
        _fail("protected_replay.fixture_case_mismatch")
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
    request_path = workspace_path.parent / "request.md"
    request_path.write_bytes(request_bytes)
    return request_path


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
                "argv": [cli_path, "--model", model, "--effort", "high"],
                "environment": {
                    "AGY_PERMISSION_MODE": "always-proceed",
                    "AGY_PRINT_TIMEOUT": str(wall_time_cap) + "s",
                },
            },
            "cliDigest": cli_digest,
            "pluginDigest": plugin_digest,
            "dependencyDigests": {"candidateArchive": candidate_archive_digest},
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


def validate_protected_bundle(
    bundle_root: Path,
    *,
    registry: object,
    qualification_digest: str,
    candidate_freeze_digest: str,
) -> dict[str, object]:
    """Validate private bytes and return only a public-safe binding summary."""

    root = Path(bundle_root)
    if root.is_symlink() or not root.is_dir():
        _fail("protected_bundle.missing_root")
    manifest, manifest_bytes = _canonical_manifest(root)
    registry_value = _mapping(registry, "protected_bundle.invalid_registry")
    _validate_manifest_identity(
        manifest,
        registry=registry_value,
        qualification_digest=qualification_digest,
        candidate_freeze_digest=candidate_freeze_digest,
    )

    variants_value = registry_value.get("variants")
    cases_value = manifest.get("cases")
    if not isinstance(variants_value, list) or not isinstance(cases_value, list):
        _fail("protected_bundle.invalid_cases")
    variants = {str(item.get("variantId")): item for item in variants_value if isinstance(item, dict)}
    cases = {str(item.get("caseId")): item for item in cases_value if isinstance(item, dict)}
    if len(variants) != 28 or len(cases) != 28 or set(cases) != set(variants) or manifest.get("caseCount") != 28:
        _fail("protected_bundle.incomplete_taxonomy")
    family_ids = {str(item.get("familyId")) for item in variants.values()}
    roles = {str(item.get("role")) for item in variants.values()}
    if len(family_ids) != 14 or roles != {"positive", "relevant_negative"}:
        _fail("protected_bundle.incomplete_taxonomy")

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
        card = _mapping(variant.get("scenarioCard"), "protected_bundle.invalid_registry_variant")
        if case.get("logicalAgentInputPath") != card.get("agentInput"):
            _fail("protected_bundle.case_binding_mismatch")
        worker = _mapping(case.get("workerReadable"), "protected_bundle.invalid_case")
        controller = _mapping(case.get("controllerOnly"), "protected_bundle.invalid_case")
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
            "fixtureDigest": worker_files["fixture"][2],
            "startingStateDigest": worker_files["startingState"][2],
            "implementationDigest": controller_files["controller"][2],
            "inputDigest": controller_files["graderInput"][2],
            "expectedResultDigest": controller_files["expectedResult"][2],
        }
        if card.get("fixtureDigest") != expected_bindings["fixtureDigest"]:
            _fail("protected_bundle.fixture_binding_mismatch")
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
        if seams.get("fixtureDigest") != expected_bindings["fixtureDigest"] or seams.get("startingStateDigest") != expected_bindings["startingStateDigest"]:
            _fail("protected_bundle.artifact_seam_mismatch")

    return {
        "schemaVersion": 1,
        "manifestDigest": sha256_digest(manifest_bytes),
        "caseCount": len(cases),
        "familyCount": len(family_ids),
        "roles": sorted(roles),
        "qualificationDigest": qualification_digest,
        "candidateCausalityFreezeDigest": candidate_freeze_digest,
        "candidateArchiveDigest": manifest["candidateArchiveDigest"],
        "workerControllerPathsDisjoint": True,
        "allDeclaredDigestsMatch": all_digests_match,
    }


__all__ = [
    "ProtectedRegressionError",
    "build_protected_replay_plan",
    "grade_protected_workspace",
    "materialize_public_registry",
    "protected_replay_condition",
    "provision_protected_workspace",
    "validate_protected_bundle",
]
