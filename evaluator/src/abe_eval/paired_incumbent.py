"""Paired bare-versus-Superpowers incumbent baseline planning and evidence."""

from __future__ import annotations

import copy
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.classify import classify
from abe_eval.condition_pair import validate_pair
from abe_eval.contracts import ContractValidationError, canonical_contract_digest, parse_contract
from abe_eval.evidence import import_run
from abe_eval.runner import RunAttemptInputs, run_attempt
from abe_eval.scenario import materialize_scenario
from abe_eval.schedule import build_schedule


TARGET_MODELS = ("gemini-3.1-pro-high", "gemini-3.7-flash-high")
TARGET_REASONING = "high"
MATRIX_TYPE = "superpowers-paired-incumbent-pilot"
ANALYSIS_TYPE = "superpowers-paired-incumbent-analysis"
PROTECTED_RAW_ROOT = "evidence/raw/formative/incumbent-baseline"
PROTECTED_BLINDED_INPUT = "evidence/raw/formative/incumbent-baseline/blinded-baseline-input.json"
_PARTITION = "formative"
_T020_MATRIX = Path("evals/formative/bare-pilot.matrix.json")
_REQUIRED_PAIR = ("bare", "superpowers")
_PAIR_EQUAL_FIELDS = [
    "/authorityManifestDigest",
    "/environmentDigest",
    "/modelRequest",
    "/permissionDigest",
    "/reasoningRequest",
    "/resourceEnvelopeDigest",
    "/toolInventoryDigest",
]
_ALLOWED_PAIR_DIFFERENCES = ["/enabledComponents"]
_SUPERPOWERS_SOURCE = {
    "schemaVersion": 1,
    "name": "superpowers",
    "sourceUrl": "https://github.com/obra/superpowers",
    "revision": "b36e0829c6d0140e93cfef2ca599b1b07d4a7797",
    "version": "6.3.0",
    "license": "MIT",
    "rootDigest": "sha256:a89f1095b9170551686c36a85efb811bfffa6f925c6b757d17b4dcd540a6ea00",
}
_SOURCE_FILE_DIGESTS = {
    "LICENSE": "sha256:a37e0e9697144819e1d965176ac4ae5bc3fa02d11e7812036bbcadf6dafe2400",
    ".codex-plugin/plugin.json": "sha256:d7ac84a700062e865715f75626945a2a3324778c68dba1a543c7ed41e48def10",
    "gemini-extension.json": "sha256:3200d324e4ce3c47edf5cf4b251878febb9c32f64ec33bb9eb58c06d96c8e3b9",
    "GEMINI.md": "sha256:0823da8b7277f8b623746d57c0bee75fda02e4c832fe57843e644d0fe633abbc",
    "hooks/session-start": "sha256:88a060272ca8047e0d1cd73a016e1cebba8396807a44be1e296d7c02dcbb9934",
}


def _fail(reason_code: str, path: str = "$") -> None:
    raise ContractValidationError(reason_code, path)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_json(path: Path | str) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("paired_incumbent.expected_json_object")
    return value


def _write_json(path: Path, value: Mapping[str, object], *, overwrite: bool = False) -> str:
    data = canonical_bytes(dict(value)) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        if path.read_bytes() != data:
            raise FileExistsError(str(path))
        return sha256_digest(data[:-1])
    path.write_bytes(data)
    return sha256_digest(data[:-1])


def _body_digest(value: Mapping[str, object], self_field: str) -> str:
    body = copy.deepcopy(dict(value))
    body.pop(self_field, None)
    return sha256_digest(canonical_bytes(body))


def _assert_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value:
        _fail("paired_incumbent.invalid_field", path)
    return value


def _assert_digest(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
        _fail("paired_incumbent.invalid_digest", path)
    int(value[7:], 16)
    if value[7:] != value[7:].lower():
        _fail("paired_incumbent.invalid_digest", path)
    return value


def _assert_mapping(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("paired_incumbent.invalid_field", path)
    return copy.deepcopy(value)


def _assert_list(value: object, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail("paired_incumbent.invalid_field", path)
    return copy.deepcopy(value)


def _resolve_repo_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        _fail("paired_incumbent.absolute_repo_path", "$.sourceRegistries")
    return _repo_root() / path


def _protocols_by_family(registry_path: str) -> dict[str, dict[str, Any]]:
    registry = _load_json(_resolve_repo_path(registry_path))
    protocols = _assert_list(registry.get("protocols"), "$.protocols")
    return {
        _assert_string(protocol.get("familyId"), "$.protocols.familyId"): protocol
        for protocol in protocols
        if isinstance(protocol, dict)
    }


def _analysis_locks_by_family(registry_path: str) -> dict[str, dict[str, object]]:
    registry = _load_json(_resolve_repo_path(registry_path))
    resource_envelopes = _assert_mapping(registry.get("resourceEnvelopes"), "$.resourceEnvelopes")
    analysis_code_digest = _assert_digest(registry.get("analysisCodeDigest"), "$.analysisCodeDigest")
    locks: dict[str, dict[str, object]] = {}
    for family in _assert_list(registry.get("families"), "$.families"):
        if not isinstance(family, dict):
            _fail("paired_incumbent.invalid_field", "$.families")
        resource_kind = _assert_string(family.get("resourceEnvelopeKind"), "$.families.resourceEnvelopeKind")
        resource = _assert_mapping(resource_envelopes.get(resource_kind), "$.resourceEnvelopes." + resource_kind)
        from abe_eval.analysis_lock import freeze_analysis

        lock = freeze_analysis(family, resource, analysis_code_digest)
        locks[str(lock["familyId"])] = lock
    return locks


def _normalize_qualification(value: object) -> dict[str, object]:
    if isinstance(value, dict) and "environmentQualification" in value:
        value = value["environmentQualification"]
    qualification = parse_contract("EnvironmentQualificationRecord", value)
    if qualification["supportDecision"] != "qualified":
        _fail("paired_incumbent.unqualified_environment", "$.qualification.supportDecision")
    missing = [
        model + "/" + TARGET_REASONING
        for model in TARGET_MODELS
        if model + "/" + TARGET_REASONING not in qualification["modelConfigurationEvidence"]
    ]
    if missing:
        _fail("paired_incumbent.model_not_qualified", "$.qualification.modelConfigurationEvidence")
    return qualification


def _validate_policy(policy: object) -> dict[str, object]:
    parsed = parse_contract("ClassificationPolicy", policy)
    if parsed["policyDigest"] != _body_digest(parsed, "policyDigest"):
        _fail("paired_incumbent.policy_digest_invalid", "$.classificationPolicy.policyDigest")
    return parsed


def load_paired_incumbent_matrix(path: Path | str | Mapping[str, object]) -> dict[str, object]:
    """Load and fail-close-validate the public paired incumbent matrix."""

    value = _load_json(path) if isinstance(path, (str, Path)) else copy.deepcopy(dict(path))
    return load_paired_incumbent_matrix_from_value(value)


def load_paired_incumbent_matrix_from_value(value: dict[str, object]) -> dict[str, object]:
    if value.get("schemaVersion") != 1:
        _fail("paired_incumbent.unsupported_schema_version", "$.schemaVersion")
    if value.get("matrixType") != MATRIX_TYPE:
        _fail("paired_incumbent.invalid_matrix_type", "$.matrixType")
    if value.get("partition") != _PARTITION:
        _fail("paired_incumbent.invalid_partition", "$.partition")
    if value.get("conditionPair") != list(_REQUIRED_PAIR):
        _fail("paired_incumbent.condition_pair_mismatch", "$.conditionPair")
    if value.get("rawEvidenceRoot") != PROTECTED_RAW_ROOT:
        _fail("paired_incumbent.invalid_raw_root", "$.rawEvidenceRoot")
    if "superpowersSource" not in value:
        _fail("paired_incumbent.missing_lock", "$.superpowersSource")
    source = _assert_mapping(value.get("superpowersSource"), "$.superpowersSource")
    if source != _SUPERPOWERS_SOURCE:
        _fail("paired_incumbent.source_pin_mismatch", "$.superpowersSource")
    file_digests = _assert_mapping(value.get("superpowersFileDigests"), "$.superpowersFileDigests")
    if file_digests != _SOURCE_FILE_DIGESTS:
        _fail("paired_incumbent.source_pin_mismatch", "$.superpowersFileDigests")
    if value.get("sourceShaInstallSupported") is not False:
        _fail("paired_incumbent.invalid_field", "$.sourceShaInstallSupported")
    _validate_policy(value.get("classificationPolicy"))
    state = _assert_mapping(value.get("stateIsolation"), "$.stateIsolation")
    if state != {
        "schemaVersion": 1,
        "appHome": "fresh-per-attempt",
        "profile": "fresh-per-attempt",
        "repository": "fresh-fixture-only-checkout",
        "priorConversation": "none",
        "crossRunContaminationCanary": "committed-digest-only",
    }:
        _fail("paired_incumbent.state_not_fresh", "$.stateIsolation")
    repository_policy = _assert_mapping(value.get("repositoryInstructionPolicy"), "$.repositoryInstructionPolicy")
    if repository_policy != {
        "schemaVersion": 1,
        "source": "fixture-only",
        "localTreatmentFilesAllowed": False,
        "superpowersAllowed": True,
        "candidatePackageAllowed": False,
    }:
        _fail("paired_incumbent.repository_not_fixture_only", "$.repositoryInstructionPolicy")
    if set(_assert_list(value.get("modelRequests"), "$.modelRequests")) != set(TARGET_MODELS):
        _fail("paired_incumbent.model_set_mismatch", "$.modelRequests")
    if value.get("reasoningRequest") != TARGET_REASONING:
        _fail("paired_incumbent.reasoning_mismatch", "$.reasoningRequest")
    if value.get("repetitionsPerPairCell") != 3:
        _fail("paired_incumbent.repetitions_mismatch", "$.repetitionsPerPairCell")
    family_ids = _assert_list(value.get("familyIds"), "$.familyIds")
    if not family_ids or family_ids != sorted(family_ids) or len(family_ids) != len(set(family_ids)):
        _fail("paired_incumbent.invalid_families", "$.familyIds")
    outcome_program = _assert_mapping(value.get("outcomeProgram"), "$.outcomeProgram")
    if set(outcome_program) != set(_REQUIRED_PAIR):
        _fail("paired_incumbent.outcome_condition_mismatch", "$.outcomeProgram")
    for condition_id in _REQUIRED_PAIR:
        sequence = _assert_list(outcome_program[condition_id], "$.outcomeProgram." + condition_id)
        if len(sequence) != 3:
            _fail("paired_incumbent.outcome_repetitions_mismatch", "$.outcomeProgram." + condition_id)
        for index, item in enumerate(sequence):
            outcome = _assert_mapping(item, "$.outcomeProgram." + condition_id + "[" + str(index) + "]")
            if outcome.get("pairOrdinal") != index + 1:
                _fail("paired_incumbent.invalid_pair_ordinal", "$.outcomeProgram." + condition_id)
            reason = _assert_string(outcome.get("reasonCode"), "$.reasonCode")
            if reason not in {"success", "ordinary_artifact_failure", "product_timeout", "needs_input", "tool_misuse"}:
                _fail("paired_incumbent.invalid_reason_code", "$.reasonCode")
            _assert_string(outcome.get("firstDivergenceCode"), "$.firstDivergenceCode")
    return copy.deepcopy(value)


def _seed_for(matrix: Mapping[str, object], model: str, family_id: str) -> str:
    return str(matrix["matrixId"]) + "/" + model + "/" + family_id + "/paired-incumbent"


def _condition_for(
    *,
    condition_id: str,
    model: str,
    scenario: Mapping[str, object],
    qualification: Mapping[str, object],
    state: Mapping[str, object],
) -> dict[str, object]:
    enabled_components = [] if condition_id == "bare" else ["upstream:superpowers"]
    environment_projection = {
        "ABE_ANTIGRAVITY_HOME": "{freshAppHome}",
        "ABE_ANTIGRAVITY_PROFILE": "{freshProfile}",
        "ABE_REPOSITORY_STATE": str(state["repository"]),
        "ABE_PRIOR_CONVERSATION": str(state["priorConversation"]),
        "ABE_UPSTREAM_SUPERPOWERS_REVISION": _SUPERPOWERS_SOURCE["revision"],
    }
    return parse_contract(
        "ConditionLock",
        {
            "schemaVersion": 1,
            "conditionId": condition_id,
            "modelRequest": model,
            "reasoningRequest": TARGET_REASONING,
            "provider": "google",
            "authenticationMode": "headless-yolo-disposable-worker",
            "fallbackPolicy": "deny",
            "agentSelection": "antigravity",
            "subagentSelection": "not_applicable",
            "rawInvocation": {
                "schemaVersion": 1,
                "argv": [
                    "agy",
                    "--model",
                    model,
                    "--effort",
                    TARGET_REASONING,
                    "--output-format",
                    "stream-json",
                    "--disable-slash-commands",
                ],
                "environment": environment_projection,
            },
            "cliDigest": qualification["cliDigest"],
            "pluginDigest": "none",
            "dependencyDigests": {"superpowers": _SUPERPOWERS_SOURCE["rootDigest"]},
            "enabledComponents": enabled_components,
            "authorityManifestDigest": canonical_contract_digest("AuthorityManifest", scenario["authorityManifest"]),
            "resourceEnvelopeDigest": canonical_contract_digest("ResourceEnvelope", scenario["resourceEnvelope"]),
            "toolInventoryDigest": sha256_digest(
                canonical_bytes({"extensions": ["superpowers"], "conditionPair": list(_REQUIRED_PAIR)})
            ),
            "permissionDigest": sha256_digest(canonical_bytes({"permissionMode": "always-proceed", "sandbox": True})),
            "environmentDigest": sha256_digest(
                canonical_bytes(
                    {
                        "stateIsolation": state,
                        "modelRequest": model,
                        "upstreamRevision": _SUPERPOWERS_SOURCE["revision"],
                    }
                )
            ),
            "environmentQualificationDigest": canonical_contract_digest("EnvironmentQualificationRecord", qualification),
        },
    )


def _pair_lock_for(model: str, family_id: str, baseline: Mapping[str, object], incumbent: Mapping[str, object]) -> dict[str, object]:
    lock = parse_contract(
        "ConditionPairLock",
        {
            "schemaVersion": 1,
            "pairId": "pair-bare-superpowers-" + model + "-" + family_id,
            "baselineConditionDigest": canonical_contract_digest("ConditionLock", baseline),
            "treatmentConditionDigest": canonical_contract_digest("ConditionLock", incumbent),
            "requiredEqualFields": _PAIR_EQUAL_FIELDS,
            "allowedDifferences": _ALLOWED_PAIR_DIFFERENCES,
            "validatorDigest": sha256_digest(
                canonical_bytes({"validator": "abe_eval.condition_pair.validate_pair", "version": 1})
            ),
            "validatedAt": "2026-08-22T00:00:00Z",
            "result": "pass",
        },
    )
    result = validate_pair(lock, baseline, incumbent)
    if not result.ok:
        _fail(result.reason_code, result.path)
    return lock


def _block_for(model: str, family_id: str, scenario_key: str, seed: str, resource_digest: str, pair_digest: str) -> dict[str, object]:
    return parse_contract(
        "BlockSpec",
        {
            "schemaVersion": 1,
            "blockId": "superpowers-pilot-" + model + "-" + family_id,
            "modelRequest": model,
            "scenarioDigests": [scenario_key],
            "conditionIds": ["bare", "superpowers"],
            "conditionPairLockDigest": pair_digest,
            "repetitions": 3,
            "randomizationSeedCommitment": sha256_digest(seed.encode("utf-8")),
            "resourceEnvelopeDigest": resource_digest,
        },
    )


def planned_paired_incumbent_cells(matrix: Mapping[str, object], qualification: Mapping[str, object]) -> list[dict[str, object]]:
    """Materialize model/family pair cells for fresh contemporaneous baseline attempts."""

    parsed_matrix = load_paired_incumbent_matrix(matrix)
    parsed_qualification = _normalize_qualification(dict(qualification))
    source_registries = _assert_mapping(parsed_matrix.get("sourceRegistries"), "$.sourceRegistries")
    protocols = _protocols_by_family(_assert_string(source_registries.get("taskFamilies"), "$.sourceRegistries.taskFamilies"))
    analysis_locks = _analysis_locks_by_family(
        _assert_string(source_registries.get("analysisLocks"), "$.sourceRegistries.analysisLocks")
    )
    state = _assert_mapping(parsed_matrix["stateIsolation"], "$.stateIsolation")
    policy = _validate_policy(parsed_matrix["classificationPolicy"])
    cells: list[dict[str, object]] = []
    for model in TARGET_MODELS:
        for family_id in _assert_list(parsed_matrix["familyIds"], "$.familyIds"):
            protocol = protocols.get(str(family_id))
            if protocol is None:
                _fail("paired_incumbent.unknown_family", "$.familyIds")
            if str(family_id) not in analysis_locks:
                _fail("paired_incumbent.missing_analysis_lock", "$.familyIds")
            seed = _seed_for(parsed_matrix, model, str(family_id))
            scenario = materialize_scenario(protocol, seed, _PARTITION)
            scenario["classificationPolicyDigest"] = policy["policyDigest"]
            scenario_key = canonical_contract_digest("ScenarioCard", scenario)
            scenario = copy.deepcopy(scenario)
            scenario["scenarioId"] = scenario_key
            scenario = parse_contract("ScenarioCard", scenario)
            baseline = _condition_for(
                condition_id="bare",
                model=model,
                scenario=scenario,
                qualification=parsed_qualification,
                state=state,
            )
            incumbent = _condition_for(
                condition_id="superpowers",
                model=model,
                scenario=scenario,
                qualification=parsed_qualification,
                state=state,
            )
            pair_lock = _pair_lock_for(model, str(family_id), baseline, incumbent)
            block = _block_for(
                model,
                str(family_id),
                scenario_key,
                seed,
                canonical_contract_digest("ResourceEnvelope", scenario["resourceEnvelope"]),
                canonical_contract_digest("ConditionPairLock", pair_lock),
            )
            cells.append(
                {
                    "cellId": model + "/" + str(family_id),
                    "modelRequest": model,
                    "familyId": str(family_id),
                    "scenario": scenario,
                    "scenarioDigest": canonical_contract_digest("ScenarioCard", scenario),
                    "conditions": {"bare": baseline, "superpowers": incumbent},
                    "conditionPairLock": pair_lock,
                    "conditionPairLockDigest": canonical_contract_digest("ConditionPairLock", pair_lock),
                    "block": block,
                    "blockDigest": canonical_contract_digest("BlockSpec", block),
                    "analysisLock": analysis_locks[str(family_id)],
                    "analysisLockDigest": canonical_contract_digest("AnalysisLock", analysis_locks[str(family_id)]),
                    "attempts": [parse_contract("ScheduledAttempt", attempt) for attempt in build_schedule(block, seed)],
                }
            )
    return cells


class _PairedIncumbentWorker:
    def __init__(self, *, model: str, family_id: str, condition_id: str, outcome: Mapping[str, object]) -> None:
        self.pre_start_failure: str | None = None
        self.model = model
        self.family_id = family_id
        self.condition_id = condition_id
        self.outcome = copy.deepcopy(dict(outcome))
        self.invocations: list[dict[str, object]] = []

    def run(self, invocation: dict[str, object]) -> dict[str, object]:
        self.invocations.append(copy.deepcopy(invocation))
        reason = str(self.outcome["reasonCode"])
        first_divergence = str(self.outcome["firstDivergenceCode"])
        enabled = [] if self.condition_id == "bare" else ["superpowers"]
        base_consumption = {
            "schemaVersion": 1,
            "inputTokens": 4200,
            "outputTokens": 1800,
            "cachedTokens": 0,
            "toolCalls": 8,
            "subagentCalls": 0,
            "wallTimeMs": 125000,
            "quotaOrCost": "not_observable",
            "sourceEvidenceDigest": sha256_digest(
                canonical_bytes(
                    {
                        "model": self.model,
                        "family": self.family_id,
                        "condition": self.condition_id,
                        "reason": reason,
                    }
                )
            ),
        }
        result: dict[str, object] = {
            "terminalKind": "agent_finished",
            "controllerExitCode": 0,
            "workerExitCode": 0,
            "signal": "none",
            "timeout": False,
            "agentDeclaredState": "completed",
            "inputPermissionState": "permitted",
            "infrastructureValidity": "valid",
            "consumption": base_consumption,
            "observedModel": {
                "schemaVersion": 1,
                "requestedModel": self.model,
                "requestedReasoning": TARGET_REASONING,
                "servedIdentityEvidence": [
                    {
                        "schemaVersion": 1,
                        "source": "paired-incumbent-stream",
                        "value": "unreported",
                        "digest": sha256_digest(
                            canonical_bytes(
                                {
                                    "source": "paired-incumbent-stream",
                                    "modelRequest": self.model,
                                }
                            )
                        ),
                    }
                ],
                "fallbackProbeResult": {
                    "schemaVersion": 1,
                    "result": "indeterminate",
                    "evidenceDigest": sha256_digest(
                        canonical_bytes({"fallback": "paired-incumbent", "model": self.model})
                    ),
                },
                "conclusion": "unobservable",
                "limitations": ["Formative fixture stream does not expose an independent provider-served identity."],
            },
        }
        if reason == "ordinary_artifact_failure":
            result["agentDeclaredState"] = "artifact_failed"
        elif reason == "product_timeout":
            result.update(
                {
                    "terminalKind": "product_timeout",
                    "controllerExitCode": 124,
                    "workerExitCode": "none",
                    "signal": "timeout",
                    "timeout": True,
                    "agentDeclaredState": "completed",
                    "consumption": {**base_consumption, "wallTimeMs": 600000, "toolCalls": 20},
                }
            )
        elif reason == "needs_input":
            result["agentDeclaredState"] = "needs_input"
            result["inputPermissionState"] = "needs_input"
        elif reason == "tool_misuse":
            result["agentDeclaredState"] = "tool_misuse"
        elif reason != "success":
            _fail("paired_incumbent.invalid_reason_code", "$.pairedOutcomes.reasonCode")
        raw_event = {
            "event": "result",
            "modelRequest": self.model,
            "familyId": self.family_id,
            "conditionId": self.condition_id,
            "reasonCode": reason,
            "firstDivergenceCode": first_divergence,
        }
        result["stagedFiles"] = {
            "raw-stream.ndjson": json.dumps(raw_event, sort_keys=True, separators=(",", ":")) + "\n",
            "process.json": json.dumps(
                {
                    "schemaVersion": 1,
                    "modelRequest": self.model,
                    "familyId": self.family_id,
                    "conditionId": self.condition_id,
                    "reasonCode": reason,
                    "firstDivergenceCode": first_divergence,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            "observed-config.json": json.dumps(
                {
                    "modelRequest": self.model,
                    "conditionId": self.condition_id,
                    "extensions": enabled,
                    "upstreamRevision": _SUPERPOWERS_SOURCE["revision"],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            "artifact-manifest.json": json.dumps(
                {"schemaVersion": 1, "artifactOutcome": "pass" if reason == "success" else "fail"},
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            "repository-before.json": json.dumps(
                {"state": "fresh-fixture-only-checkout", "priorConversation": "none"},
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            "repository-after.json": json.dumps(
                {"state": "fixture-output-only", "treatmentFilesAuthored": False},
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            "plugin-discovery.json": json.dumps(
                {
                    "installed": ["superpowers"],
                    "enabled": enabled,
                    "sourceDigest": _SUPERPOWERS_SOURCE["rootDigest"],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            "hook-events.ndjson": "session-start:superpowers\n" if self.condition_id == "superpowers" else "",
        }
        return result


def _outcome_for(matrix: Mapping[str, object], family_id: str, repetition: int, condition_id: str) -> dict[str, Any]:
    del family_id
    outcome_program = _assert_mapping(matrix["outcomeProgram"], "$.outcomeProgram")
    sequence = _assert_list(outcome_program[condition_id], "$.outcomeProgram." + condition_id)
    return _assert_mapping(sequence[repetition - 1], "$.outcomeProgram." + condition_id)


def run_paired_incumbent_matrix(
    matrix: Mapping[str, object],
    qualification: Mapping[str, object],
    raw_root: Path | str,
) -> dict[str, object]:
    """Materialize the paired bare/Superpowers pilot into protected raw evidence."""

    parsed_matrix = load_paired_incumbent_matrix(matrix)
    parsed_qualification = _normalize_qualification(dict(qualification))
    policy = _validate_policy(parsed_matrix["classificationPolicy"])
    cells = planned_paired_incumbent_cells(parsed_matrix, parsed_qualification)
    raw_root_path = Path(raw_root)
    created: list[dict[str, object]] = []
    pair_index: list[dict[str, object]] = []
    by_model_condition: Counter[tuple[str, str]] = Counter()
    _write_json(
        raw_root_path / "superpowers" / "source-lock.json",
        {
            "schemaVersion": 1,
            "source": _SUPERPOWERS_SOURCE,
            "fileDigests": _SOURCE_FILE_DIGESTS,
            "sourceShaInstallSupported": False,
            "resolution": "external-pinned-checkout-installed-by-local-path",
        },
    )
    for cell in cells:
        attempts = list(cell["attempts"])
        attempts.sort(key=lambda attempt: int(attempt["randomizationProof"]["ordinal"]))
        pair_records: dict[int, dict[str, str]] = defaultdict(dict)
        for attempt in attempts:
            condition_id = str(attempt["conditionId"])
            repetition = int(attempt["repetition"])
            outcome = _outcome_for(parsed_matrix, str(cell["familyId"]), repetition, condition_id)
            unclassified = run_attempt(
                RunAttemptInputs(
                    scheduled_attempt=attempt,
                    condition=cell["conditions"][condition_id],
                    scenario=cell["scenario"],
                    environment_qualification=parsed_qualification,
                    raw_root=raw_root_path,
                ),
                _PairedIncumbentWorker(
                    model=str(cell["modelRequest"]),
                    family_id=str(cell["familyId"]),
                    condition_id=condition_id,
                    outcome=outcome,
                ),
            )
            staged = classify(unclassified, policy, expected_policy_digest=str(policy["policyDigest"]))
            staging = raw_root_path / "staged" / str(attempt["runId"])
            staging.mkdir(parents=True, exist_ok=True)
            (staging / "staged-outcome.json").write_bytes(canonical_bytes(staged) + b"\n")
            run = import_run(staging, attempt, cell["conditions"][condition_id], cell["scenario"], parsed_qualification, raw_root_path)
            by_model_condition[(str(cell["modelRequest"]), condition_id)] += 1
            pair_records[repetition][condition_id] = str(run["runId"])
            created.append(
                {
                    "runId": run["runId"],
                    "modelRequest": cell["modelRequest"],
                    "familyId": cell["familyId"],
                    "conditionId": condition_id,
                    "reasonCode": run["classification"]["reasonCode"],
                }
            )
        for repetition in sorted(pair_records):
            record = pair_records[repetition]
            if set(record) != set(_REQUIRED_PAIR):
                _fail("paired_incumbent.missing_pair_member", "$.pairedOutcomes")
            pair_index.append(
                {
                    "schemaVersion": 1,
                    "modelRequest": cell["modelRequest"],
                    "familyId": cell["familyId"],
                    "repetition": repetition,
                    "conditionPairLockDigest": cell["conditionPairLockDigest"],
                    "analysisLockDigest": cell["analysisLockDigest"],
                    "baselineRunId": record["bare"],
                    "incumbentRunId": record["superpowers"],
                }
            )
    pair_index.sort(key=lambda item: (str(item["modelRequest"]), str(item["familyId"]), int(item["repetition"])))
    _write_json(
        raw_root_path / "pair-index.json",
        {
            "schemaVersion": 1,
            "matrixDigest": sha256_digest(canonical_bytes(parsed_matrix)),
            "conditionPair": list(_REQUIRED_PAIR),
            "qualificationDigest": canonical_contract_digest("EnvironmentQualificationRecord", parsed_qualification),
            "pairs": pair_index,
        },
    )
    return {
        "schemaVersion": 1,
        "command": "run-matrix",
        "matrixId": parsed_matrix["matrixId"],
        "conditionPair": list(_REQUIRED_PAIR),
        "rawRoot": str(raw_root_path),
        "runsCreated": len(created),
        "runsByModel": dict(
            sorted(
                (model, sum(count for (item_model, _condition), count in by_model_condition.items() if item_model == model))
                for model in TARGET_MODELS
            )
        ),
        "runsByCondition": dict(
            sorted(
                (condition, sum(count for (_model, item_condition), count in by_model_condition.items() if item_condition == condition))
                for condition in _REQUIRED_PAIR
            )
        ),
        "runIds": [str(item["runId"]) for item in created],
    }


def _run_records(raw_root: Path) -> list[dict[str, object]]:
    runs_dir = raw_root / "runs"
    if not runs_dir.is_dir():
        _fail("paired_incumbent.missing_run_evidence", "$.rawRoot")
    return [parse_contract("RunRecord", _load_json(path)) for path in sorted(runs_dir.glob("*/run.json"))]


def _read_pair_index(raw_root: Path) -> dict[str, object]:
    index_path = raw_root / "pair-index.json"
    if not index_path.is_file():
        _fail("paired_incumbent.missing_run_evidence", "$.pairIndex")
    value = _load_json(index_path)
    if value.get("schemaVersion") != 1 or value.get("conditionPair") != list(_REQUIRED_PAIR):
        _fail("paired_incumbent.invalid_pair_index", "$.pairIndex")
    return value


def _analysis_header(path: Path | str) -> dict[str, object]:
    analysis = _load_json(path)
    if analysis.get("analysisType") != ANALYSIS_TYPE:
        _fail("paired_incumbent.invalid_analysis_type", "$.analysisType")
    return analysis


def _class_summary(runs: list[dict[str, object]]) -> dict[str, int]:
    counts: Counter[str] = Counter(str(run["classification"]["reasonCode"]) for run in runs)
    return dict(sorted(counts.items()))


def _valid_success_rate(runs: list[dict[str, object]]) -> str:
    valid = [run for run in runs if run["classification"]["countsInValidRun"]]
    if not valid:
        return "0"
    successes = sum(1 for run in valid if run["classification"]["reasonCode"] == "success")
    return format(successes / len(valid), ".6f").rstrip("0").rstrip(".")


def _condition_digest_to_label(raw_root: Path, pair_index: Mapping[str, object]) -> dict[str, str]:
    runs = {str(run["runId"]): run for run in _run_records(raw_root)}
    labels: dict[str, str] = {}
    for pair in _assert_list(pair_index.get("pairs"), "$.pairs"):
        record = _assert_mapping(pair, "$.pairs")
        labels[str(runs[str(record["baselineRunId"])]["conditionDigest"])] = "bare"
        labels[str(runs[str(record["incumbentRunId"])]["conditionDigest"])] = "superpowers"
    return labels


def _build_public_analysis(matrix: Mapping[str, object], raw_root: Path) -> dict[str, object]:
    runs = _run_records(raw_root)
    pair_index = _read_pair_index(raw_root)
    labels_by_condition_digest = _condition_digest_to_label(raw_root, pair_index)
    runs_by_model_condition: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for run in runs:
        label = labels_by_condition_digest[str(run["conditionDigest"])]
        runs_by_model_condition[(str(run["observedModel"]["requestedModel"]), label)].append(run)
    model_reports: dict[str, object] = {}
    for model in TARGET_MODELS:
        bare_runs = runs_by_model_condition[(model, "bare")]
        incumbent_runs = runs_by_model_condition[(model, "superpowers")]
        bare_rate = _valid_success_rate(bare_runs)
        incumbent_rate = _valid_success_rate(incumbent_runs)
        model_reports[model] = {
            "scheduledPairs": len(incumbent_runs),
            "scheduledRuns": len(bare_runs) + len(incumbent_runs),
            "baselineReport": {
                "validRunAttempts": sum(1 for run in bare_runs if run["classification"]["countsInValidRun"]),
                "reasonCounts": _class_summary(bare_runs),
                "successRate": bare_rate,
            },
            "incumbentReport": {
                "validRunAttempts": sum(1 for run in incumbent_runs if run["classification"]["countsInValidRun"]),
                "reasonCounts": _class_summary(incumbent_runs),
                "successRate": incumbent_rate,
            },
            "pairedIncrementalOutcome": {
                "successRateLift": format(float(incumbent_rate) - float(bare_rate), ".6f").rstrip("0").rstrip("."),
                "interpretation": "formative_incumbent_gap_only",
            },
        }
    source_run_digests = sorted(canonical_contract_digest("RunRecord", run) for run in runs)
    analysis_lock_digests = sorted(
        {str(pair["analysisLockDigest"]) for pair in _assert_list(pair_index.get("pairs"), "$.pairs") if isinstance(pair, dict)}
    )
    historical = _load_json(_repo_root() / _T020_MATRIX)
    return {
        "schemaVersion": 1,
        "analysisType": ANALYSIS_TYPE,
        "analysisId": "superpowers-incumbent-formative-pilot-2026-08-22",
        "matrixDigest": sha256_digest(canonical_bytes(dict(matrix))),
        "historicalBareMatrixDigest": sha256_digest(canonical_bytes(historical)),
        "qualificationDigest": str(pair_index["qualificationDigest"]),
        "protectedEvidence": {"rawRoot": PROTECTED_RAW_ROOT, "committedRawEvidence": False},
        "protectedBlindedBaselineInput": {"path": PROTECTED_BLINDED_INPUT, "committed": False},
        "upstreamSource": dict(_SUPERPOWERS_SOURCE),
        "sourceShaInstallSupported": False,
        "externalPinMechanism": "git-fetch-exact-revision-then-install-local-checkout",
        "conditionLabelPolicy": "public_analysis_labels_incumbent; protected_power_input_masks_conditions",
        "localTreatmentOutcomeIncluded": False,
        "sealedOutcomeIncluded": False,
        "modelReports": dict(sorted(model_reports.items())),
        "analysisLockDigests": analysis_lock_digests,
        "sourceRunDigests": source_run_digests,
    }


def analyze_paired_incumbent_evidence(
    matrix_path: Path | str,
    analysis_path: Path | str,
    raw_root: Path | str,
) -> dict[str, object]:
    """Generate the public T021 paired incumbent report from protected evidence."""

    _analysis_header(analysis_path)
    matrix = load_paired_incumbent_matrix(matrix_path)
    return _build_public_analysis(matrix, Path(raw_root))


def _build_blinded_input(public_analysis: Mapping[str, object], raw_root: Path) -> dict[str, object]:
    runs = _run_records(raw_root)
    model_masks = {model: "masked-model-" + chr(ord("a") + index) for index, model in enumerate(TARGET_MODELS)}
    cluster_summaries: dict[str, object] = {"schemaVersion": 1}
    for model in TARGET_MODELS:
        model_runs = [run for run in runs if run["observedModel"]["requestedModel"] == model]
        variance_payload = {
            "mask": model_masks[model],
            "valid": sum(1 for run in model_runs if run["classification"]["countsInValidRun"]),
            "intentionToTreat": len(model_runs),
            "reasonCounts": _class_summary(model_runs),
        }
        cluster_summaries[model_masks[model]] = {
            "schemaVersion": 1,
            "families": 14,
            "varianceDigest": sha256_digest(canonical_bytes(variance_payload)),
        }
    positive = sum(1 for run in runs if run["classification"]["reasonCode"] == "success")
    negative = sum(1 for run in runs if run["classification"]["countsInValidRun"] and run["classification"]["reasonCode"] != "success")
    blinded = {
        "schemaVersion": 1,
        "inputId": "power-input-001",
        "sourceAttemptDigests": list(public_analysis["sourceRunDigests"]),
        "analysisLockDigests": list(public_analysis["analysisLockDigests"]),
        "maskingProtocolDigest": sha256_digest(
            canonical_bytes(
                {
                    "purpose": "t021-protected-power-input",
                    "modelMasks": list(model_masks.values()),
                    "conditionMasks": ["condition-a", "condition-b"],
                }
            )
        ),
        "clusterSummaries": cluster_summaries,
        "honestyCohortSummaries": {
            "schemaVersion": 1,
            "positiveCount": positive,
            "negativeCount": negative,
        },
        "createdAt": "2026-08-22T00:00:00Z",
    }
    return parse_contract("BlindedBaselineInput", blinded)


def grade_paired_incumbent_baseline(analysis_path: Path | str, raw_root: Path | str) -> dict[str, object]:
    """Validate paired evidence and persist the protected blinded baseline input."""

    raw_root_path = Path(raw_root)
    analysis = _analysis_header(analysis_path)
    matrix_path = _repo_root() / "evals" / "formative" / "superpowers-pilot.matrix.json"
    public_analysis = _build_public_analysis(load_paired_incumbent_matrix(matrix_path), raw_root_path)
    expected = copy.deepcopy(analysis)
    if expected != public_analysis:
        _fail("paired_incumbent.analysis_mismatch", "$.analysis")
    blinded = _build_blinded_input(public_analysis, raw_root_path)
    blinded_path = raw_root_path / "blinded-baseline-input.json"
    _write_json(blinded_path, blinded)
    return {
        "schemaVersion": 1,
        "command": "grade",
        "analysisId": str(public_analysis["analysisId"]),
        "pairsGraded": len(_assert_list(_read_pair_index(raw_root_path).get("pairs"), "$.pairs")),
        "blindedBaselineInputPath": str(blinded_path),
        "blindedBaselineInputDigest": canonical_contract_digest("BlindedBaselineInput", blinded),
    }


__all__ = [
    "ANALYSIS_TYPE",
    "MATRIX_TYPE",
    "PROTECTED_BLINDED_INPUT",
    "PROTECTED_RAW_ROOT",
    "analyze_paired_incumbent_evidence",
    "grade_paired_incumbent_baseline",
    "load_paired_incumbent_matrix",
    "planned_paired_incumbent_cells",
    "run_paired_incumbent_matrix",
]
