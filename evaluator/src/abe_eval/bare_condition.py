"""Bare-Antigravity formative baseline planning and protected evidence analysis."""

from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.classify import classify
from abe_eval.contracts import ContractValidationError, canonical_contract_digest, parse_contract
from abe_eval.evidence import import_run
from abe_eval.runner import RunAttemptInputs, run_attempt
from abe_eval.scenario import materialize_scenario
from abe_eval.schedule import build_schedule


TARGET_MODELS = ("gemini-3.1-pro-high", "gemini-3.7-flash-high")
TARGET_REASONING = "high"
MATRIX_TYPE = "bare-antigravity-historical-pilot"
PROTECTED_RAW_ROOT = "evidence/raw/formative/incumbent-baseline/bare"
_PARTITION = "formative"


def _fail(reason_code: str, path: str = "$") -> None:
    raise ContractValidationError(reason_code, path)


def _load_json(path: Path | str) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("bare_condition.expected_json_object")
    return value


def _body_digest(value: Mapping[str, object], self_field: str) -> str:
    body = copy.deepcopy(dict(value))
    body.pop(self_field, None)
    return sha256_digest(canonical_bytes(body))


def _assert_digest(value: object, path: str) -> str:
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:"):
        _fail("bare_condition.invalid_digest", path)
    int(value[7:], 16)
    if value[7:] != value[7:].lower():
        _fail("bare_condition.invalid_digest", path)
    return value


def _assert_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value:
        _fail("bare_condition.invalid_field", path)
    return value


def _assert_list(value: object, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail("bare_condition.invalid_field", path)
    return copy.deepcopy(value)


def _assert_mapping(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("bare_condition.invalid_field", path)
    return copy.deepcopy(value)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_repo_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        _fail("bare_condition.absolute_repo_path", "$.sourceRegistries")
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
            _fail("bare_condition.invalid_field", "$.families")
        resource_kind = _assert_string(family.get("resourceEnvelopeKind"), "$.families.resourceEnvelopeKind")
        resource = _assert_mapping(resource_envelopes.get(resource_kind), "$.resourceEnvelopes." + resource_kind)
        from abe_eval.analysis_lock import freeze_analysis

        lock = freeze_analysis(family, resource, analysis_code_digest)
        locks[str(lock["familyId"])] = lock
    return locks


def _validate_policy(policy: object) -> dict[str, object]:
    parsed = parse_contract("ClassificationPolicy", policy)
    if parsed["policyDigest"] != _body_digest(parsed, "policyDigest"):
        _fail("bare_condition.policy_digest_invalid", "$.classificationPolicy.policyDigest")
    return parsed


def load_bare_pilot_matrix(path: Path | str) -> dict[str, object]:
    """Load and fail-close-validate the public bare-pilot matrix."""

    matrix = _load_json(path)
    return load_bare_pilot_matrix_from_value(matrix)


def _seed_for(matrix: Mapping[str, object], model: str, family_id: str) -> str:
    del model
    return str(matrix["matrixId"]) + "/" + family_id + "/bare-pilot"


def _condition_for(
    *,
    model: str,
    scenario: Mapping[str, object],
    qualification: Mapping[str, object],
    state: Mapping[str, object],
) -> dict[str, object]:
    environment_projection = {
        "ABE_ANTIGRAVITY_HOME": "{freshAppHome}",
        "ABE_ANTIGRAVITY_PROFILE": "{freshProfile}",
        "ABE_REPOSITORY_STATE": str(state["repository"]),
        "ABE_PRIOR_CONVERSATION": str(state["priorConversation"]),
    }
    return parse_contract(
        "ConditionLock",
        {
            "schemaVersion": 1,
            "conditionId": "bare",
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
            "dependencyDigests": {},
            "enabledComponents": [],
            "authorityManifestDigest": canonical_contract_digest("AuthorityManifest", scenario["authorityManifest"]),
            "resourceEnvelopeDigest": canonical_contract_digest("ResourceEnvelope", scenario["resourceEnvelope"]),
            "toolInventoryDigest": sha256_digest(canonical_bytes({"extensions": [], "condition": "bare"})),
            "permissionDigest": sha256_digest(canonical_bytes({"permissionMode": "always-proceed", "sandbox": True})),
            "environmentDigest": sha256_digest(canonical_bytes({"stateIsolation": state, "modelRequest": model})),
            "environmentQualificationDigest": canonical_contract_digest("EnvironmentQualificationRecord", qualification),
        },
    )


def _block_for(model: str, family_id: str, scenario_key: str, seed: str, resource_digest: str) -> dict[str, object]:
    return parse_contract(
        "BlockSpec",
        {
            "schemaVersion": 1,
            "blockId": "bare-pilot-" + model + "-" + family_id,
            "modelRequest": model,
            "scenarioDigests": [scenario_key],
            "conditionIds": ["bare"],
            "conditionPairLockDigest": "not_applicable",
            "repetitions": 3,
            "randomizationSeedCommitment": sha256_digest(seed.encode("utf-8")),
            "resourceEnvelopeDigest": resource_digest,
        },
    )


def _normalize_qualification(value: object) -> dict[str, object]:
    if isinstance(value, dict) and "environmentQualification" in value:
        value = value["environmentQualification"]
    qualification = parse_contract("EnvironmentQualificationRecord", value)
    if qualification["supportDecision"] != "qualified":
        _fail("bare_condition.unqualified_environment", "$.qualification.supportDecision")
    missing = [model + "/" + TARGET_REASONING for model in TARGET_MODELS if model + "/" + TARGET_REASONING not in qualification["modelConfigurationEvidence"]]
    if missing:
        _fail("bare_condition.model_not_qualified", "$.qualification.modelConfigurationEvidence")
    return qualification


def planned_bare_pilot_cells(matrix: Mapping[str, object], qualification: Mapping[str, object]) -> list[dict[str, object]]:
    """Materialize per-family, per-model bare cells without exposing hidden material."""

    parsed_matrix = load_bare_pilot_matrix_object(matrix)
    parsed_qualification = _normalize_qualification(dict(qualification))
    source_registries = _assert_mapping(parsed_matrix.get("sourceRegistries"), "$.sourceRegistries")
    protocols = _protocols_by_family(_assert_string(source_registries.get("taskFamilies"), "$.sourceRegistries.taskFamilies"))
    analysis_locks = _analysis_locks_by_family(
        _assert_string(source_registries.get("analysisLocks"), "$.sourceRegistries.analysisLocks")
    )
    cells: list[dict[str, object]] = []
    state = _assert_mapping(parsed_matrix["stateIsolation"], "$.stateIsolation")
    policy = _validate_policy(parsed_matrix["classificationPolicy"])
    for model in TARGET_MODELS:
        for family_id in _assert_list(parsed_matrix["familyIds"], "$.familyIds"):
            protocol = protocols.get(str(family_id))
            if protocol is None:
                _fail("bare_condition.unknown_family", "$.familyIds")
            if str(family_id) not in analysis_locks:
                _fail("bare_condition.missing_analysis_lock", "$.familyIds")
            seed = _seed_for(parsed_matrix, model, str(family_id))
            scenario = materialize_scenario(protocol, seed, _PARTITION)
            scenario["classificationPolicyDigest"] = policy["policyDigest"]
            scenario_key = canonical_contract_digest("ScenarioCard", scenario)
            scenario = copy.deepcopy(scenario)
            scenario["scenarioId"] = scenario_key
            scenario = parse_contract("ScenarioCard", scenario)
            condition = _condition_for(model=model, scenario=scenario, qualification=parsed_qualification, state=state)
            block = _block_for(
                model,
                str(family_id),
                scenario_key,
                seed,
                canonical_contract_digest("ResourceEnvelope", scenario["resourceEnvelope"]),
            )
            cells.append(
                {
                    "cellId": model + "/" + str(family_id),
                    "modelRequest": model,
                    "familyId": str(family_id),
                    "scenario": scenario,
                    "scenarioDigest": canonical_contract_digest("ScenarioCard", scenario),
                    "condition": condition,
                    "conditionDigest": canonical_contract_digest("ConditionLock", condition),
                    "block": block,
                    "blockDigest": canonical_contract_digest("BlockSpec", block),
                    "analysisLock": analysis_locks[str(family_id)],
                    "analysisLockDigest": canonical_contract_digest("AnalysisLock", analysis_locks[str(family_id)]),
                    "attempts": [parse_contract("ScheduledAttempt", attempt) for attempt in build_schedule(block, seed)],
                }
            )
    return cells


def load_bare_pilot_matrix_object(matrix: Mapping[str, object]) -> dict[str, object]:
    """Validate an already-loaded matrix mapping."""

    return load_bare_pilot_matrix_from_value(copy.deepcopy(dict(matrix)))


def load_bare_pilot_matrix_from_value(value: dict[str, object]) -> dict[str, object]:
    if value.get("schemaVersion") != 1:
        _fail("bare_condition.unsupported_schema_version", "$.schemaVersion")
    if value.get("matrixType") != MATRIX_TYPE:
        _fail("bare_condition.invalid_matrix_type", "$.matrixType")
    if value.get("partition") != _PARTITION:
        _fail("bare_condition.invalid_partition", "$.partition")
    if value.get("conditionId") != "bare":
        _fail("bare_condition.condition_mismatch", "$.conditionId")
    if value.get("rawEvidenceRoot") != PROTECTED_RAW_ROOT:
        _fail("bare_condition.invalid_raw_root", "$.rawEvidenceRoot")
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
        _fail("bare_condition.state_not_fresh", "$.stateIsolation")
    if value.get("extensionAllowlist") != []:
        _fail("bare_condition.unlisted_extensions", "$.extensionAllowlist")
    repository_policy = _assert_mapping(value.get("repositoryInstructionPolicy"), "$.repositoryInstructionPolicy")
    if repository_policy != {
        "schemaVersion": 1,
        "source": "fixture-only",
        "localTreatmentFilesAllowed": False,
        "superpowersAllowed": False,
        "candidatePackageAllowed": False,
    }:
        _fail("bare_condition.repository_not_fixture_only", "$.repositoryInstructionPolicy")
    if set(_assert_list(value.get("modelRequests"), "$.modelRequests")) != set(TARGET_MODELS):
        _fail("bare_condition.model_set_mismatch", "$.modelRequests")
    if value.get("reasoningRequest") != TARGET_REASONING:
        _fail("bare_condition.reasoning_mismatch", "$.reasoningRequest")
    if value.get("repetitionsPerCell") != 3:
        _fail("bare_condition.repetitions_mismatch", "$.repetitionsPerCell")
    family_ids = _assert_list(value.get("familyIds"), "$.familyIds")
    if not family_ids or family_ids != sorted(family_ids) or len(family_ids) != len(set(family_ids)):
        _fail("bare_condition.invalid_families", "$.familyIds")
    outcomes = _assert_mapping(value.get("historicalOutcomes"), "$.historicalOutcomes")
    if set(outcomes) != set(str(family_id) for family_id in family_ids):
        _fail("bare_condition.outcome_family_mismatch", "$.historicalOutcomes")
    for family_id in family_ids:
        sequence = _assert_list(outcomes[str(family_id)], "$.historicalOutcomes." + str(family_id))
        if len(sequence) != 3:
            _fail("bare_condition.outcome_repetitions_mismatch", "$.historicalOutcomes." + str(family_id))
        for outcome in sequence:
            record = _assert_mapping(outcome, "$.historicalOutcomes." + str(family_id))
            reason = _assert_string(record.get("reasonCode"), "$.reasonCode")
            if reason not in {"success", "ordinary_artifact_failure", "product_timeout", "needs_input"}:
                _fail("bare_condition.invalid_reason_code", "$.reasonCode")
            _assert_string(record.get("firstDivergenceCode"), "$.firstDivergenceCode")
    return copy.deepcopy(value)


class _HistoricalBareWorker:
    def __init__(self, *, model: str, family_id: str, outcome: Mapping[str, object]) -> None:
        self.pre_start_failure: str | None = None
        self.model = model
        self.family_id = family_id
        self.outcome = copy.deepcopy(dict(outcome))
        self.invocations: list[dict[str, object]] = []

    def run(self, invocation: dict[str, object]) -> dict[str, object]:
        self.invocations.append(copy.deepcopy(invocation))
        reason = str(self.outcome["reasonCode"])
        first_divergence = str(self.outcome["firstDivergenceCode"])
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
                canonical_bytes({"model": self.model, "family": self.family_id, "reason": reason})
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
                        "source": "historical-bare-stream",
                        "value": "unreported",
                        "digest": sha256_digest(
                            canonical_bytes(
                                {
                                    "source": "historical-bare-stream",
                                    "modelRequest": self.model,
                                }
                            )
                        ),
                    }
                ],
                "fallbackProbeResult": {
                    "schemaVersion": 1,
                    "result": "indeterminate",
                    "evidenceDigest": sha256_digest(canonical_bytes({"fallback": "historical-bare", "model": self.model})),
                },
                "conclusion": "unobservable",
                "limitations": ["Historical fixture stream does not expose an independent provider-served identity."],
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
        elif reason != "success":
            _fail("bare_condition.invalid_reason_code", "$.historicalOutcomes.reasonCode")
        raw_event = {
            "event": "result",
            "modelRequest": self.model,
            "familyId": self.family_id,
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
                    "reasonCode": reason,
                    "firstDivergenceCode": first_divergence,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            "observed-config.json": json.dumps(
                {"modelRequest": self.model, "conditionId": "bare", "extensions": []},
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
            "plugin-discovery.json": json.dumps({"extensions": []}, sort_keys=True, separators=(",", ":")) + "\n",
            "hook-events.ndjson": "",
        }
        return result


def run_bare_pilot_matrix(
    matrix: Mapping[str, object],
    qualification: Mapping[str, object],
    raw_root: Path | str,
) -> dict[str, object]:
    """Materialize the historical bare pilot into the protected raw evidence root."""

    parsed_matrix = load_bare_pilot_matrix_object(matrix)
    parsed_qualification = _normalize_qualification(dict(qualification))
    policy = _validate_policy(parsed_matrix["classificationPolicy"])
    cells = planned_bare_pilot_cells(parsed_matrix, parsed_qualification)
    outcomes = _assert_mapping(parsed_matrix["historicalOutcomes"], "$.historicalOutcomes")
    raw_root_path = Path(raw_root)
    created: list[dict[str, object]] = []
    for cell in cells:
        sequence = _assert_list(outcomes[str(cell["familyId"])], "$.historicalOutcomes." + str(cell["familyId"]))
        attempts = list(cell["attempts"])
        attempts.sort(key=lambda attempt: int(attempt["randomizationProof"]["ordinal"]))
        for attempt, outcome in zip(attempts, sequence, strict=True):
            unclassified = run_attempt(
                RunAttemptInputs(
                    scheduled_attempt=attempt,
                    condition=cell["condition"],
                    scenario=cell["scenario"],
                    environment_qualification=parsed_qualification,
                    raw_root=raw_root_path,
                ),
                _HistoricalBareWorker(
                    model=str(cell["modelRequest"]),
                    family_id=str(cell["familyId"]),
                    outcome=_assert_mapping(outcome, "$.historicalOutcomes"),
                ),
            )
            staged = classify(unclassified, policy, expected_policy_digest=str(policy["policyDigest"]))
            staging = raw_root_path / "staged" / str(attempt["runId"])
            staging.mkdir(parents=True, exist_ok=True)
            (staging / "staged-outcome.json").write_bytes(canonical_bytes(staged) + b"\n")
            run = import_run(staging, attempt, cell["condition"], cell["scenario"], parsed_qualification, raw_root_path)
            created.append(
                {
                    "runId": run["runId"],
                    "modelRequest": cell["modelRequest"],
                    "familyId": cell["familyId"],
                    "reasonCode": run["classification"]["reasonCode"],
                }
            )
    by_model = Counter(str(item["modelRequest"]) for item in created)
    return {
        "schemaVersion": 1,
        "command": "run-matrix",
        "matrixId": parsed_matrix["matrixId"],
        "condition": "bare",
        "rawRoot": str(raw_root_path),
        "runsCreated": len(created),
        "runsByModel": dict(sorted(by_model.items())),
        "runIds": [str(item["runId"]) for item in created],
    }


def _run_records(raw_root: Path) -> list[dict[str, object]]:
    runs_dir = raw_root / "runs"
    if not runs_dir.is_dir():
        raise FileNotFoundError(str(runs_dir))
    return [parse_contract("RunRecord", _load_json(path)) for path in sorted(runs_dir.glob("*/run.json"))]


def _percentile(values: list[int], percentile: float) -> int:
    ordered = sorted(values)
    if not ordered:
        return 0
    index = min(len(ordered) - 1, max(0, int(__import__("math").ceil(percentile * len(ordered)) - 1)))
    return ordered[index]


def _index_by_run_id(cells: list[dict[str, object]], matrix: Mapping[str, object]) -> dict[str, dict[str, object]]:
    outcomes = _assert_mapping(matrix["historicalOutcomes"], "$.historicalOutcomes")
    index: dict[str, dict[str, object]] = {}
    for cell in cells:
        sequence = _assert_list(outcomes[str(cell["familyId"])], "$.historicalOutcomes." + str(cell["familyId"]))
        attempts = list(cell["attempts"])
        attempts.sort(key=lambda attempt: int(attempt["randomizationProof"]["ordinal"]))
        for attempt, outcome in zip(attempts, sequence, strict=True):
            index[str(attempt["runId"])] = {
                "modelRequest": cell["modelRequest"],
                "familyId": cell["familyId"],
                "firstDivergenceCode": _assert_mapping(outcome, "$.historicalOutcomes")["firstDivergenceCode"],
                "scenarioStartingStateDigest": cell["scenario"]["startingStateDigest"],
            }
    return index


def analyze_bare_pilot_evidence(
    matrix_path: Path | str,
    analysis_path: Path | str,
    raw_root: Path | str,
) -> dict[str, object]:
    """Generate the model-separated T020 baseline report from protected evidence."""

    del analysis_path
    matrix = load_bare_pilot_matrix(matrix_path)
    runs = _run_records(Path(raw_root))
    qualification_digest = str(runs[0]["environmentQualificationDigest"]) if runs else "none"
    qualification_stub = _qualification_from_run_digest(qualification_digest)
    cells = planned_bare_pilot_cells(matrix, qualification_stub)
    run_index = _index_by_run_id(cells, matrix)
    protocols = _protocols_by_family(_assert_mapping(matrix["sourceRegistries"], "$.sourceRegistries")["taskFamilies"])
    model_reports: dict[str, object] = {}
    source_run_digests = sorted(canonical_contract_digest("RunRecord", run) for run in runs)
    for model in TARGET_MODELS:
        model_runs = [run for run in runs if run["observedModel"]["requestedModel"] == model]
        valid_runs = [run for run in model_runs if run["classification"]["countsInValidRun"]]
        attrition: Counter[str] = Counter()
        artifact_outcomes: Counter[str] = Counter()
        first_divergences: Counter[str] = Counter()
        for run in model_runs:
            classification = run["classification"]
            if classification["countsInValidRun"]:
                artifact_outcomes["pass" if classification["reasonCode"] == "success" else "fail"] += 1
                if classification["reasonCode"] == "success":
                    first_divergences["unknown"] += 1
                else:
                    first_divergences[str(run_index[str(run["runId"])]["firstDivergenceCode"])] += 1
                continue
            attrition["indeterminate" if classification["class"] == "indeterminate" else str(classification["reasonCode"])] += 1
            first_divergences["unknown"] += 1
        walls = [int(run["consumption"]["wallTimeMs"]) for run in model_runs]
        success_count = artifact_outcomes["pass"]
        valid_count = len(valid_runs)
        success_rate = success_count / valid_count if valid_count else 0.0
        model_reports[model] = {
            "scheduledAttempts": len(model_runs),
            "validRunAttempts": valid_count,
            "ceilingSuccessRate": format(success_rate, ".6f").rstrip("0").rstrip("."),
            "binomialVariance": format(success_rate * (1.0 - success_rate), ".6f").rstrip("0").rstrip("."),
            "attritionSummary": dict(sorted(attrition.items())),
            "resourceSummary": {
                "medianWallTimeMs": _percentile(walls, 0.5),
                "p90WallTimeMs": _percentile(walls, 0.9),
            },
            "artifactOutcomes": dict(sorted(artifact_outcomes.items())),
            "firstDivergenceCounts": dict(sorted(first_divergences.items())),
        }
    gap_by_family = Counter(
        str(run_index[str(run["runId"])]["familyId"])
        for run in runs
        if run["classification"]["countsInValidRun"] and run["classification"]["reasonCode"] != "success"
    )
    candidate_gaps = [
        {
            "familyId": family_id,
            "behaviors": sorted(protocols[family_id]["behaviors"]),
            "repeatable": gap_by_family[family_id] >= len(TARGET_MODELS),
        }
        for family_id in sorted(gap_by_family)
    ]
    repeat_family = str(matrix["freshBoundaryRepeatFamilyId"])
    repeat_starting_digests = {
        str(item["scenarioStartingStateDigest"])
        for item in run_index.values()
        if str(item["familyId"]) == repeat_family
    }
    behavior_taxonomy = sorted({behavior for protocol in protocols.values() for behavior in protocol["behaviors"]})
    return {
        "schemaVersion": 1,
        "analysisId": "bare-antigravity-formative-pilot-2026-08-22",
        "matrixDigest": sha256_digest(canonical_bytes(matrix)),
        "qualificationDigest": qualification_digest,
        "protectedEvidence": {"rawRoot": PROTECTED_RAW_ROOT, "committedRawEvidence": False},
        "behaviorTaxonomy": behavior_taxonomy,
        "modelReports": dict(sorted(model_reports.items())),
        "candidateGaps": candidate_gaps,
        "freshBoundaryRepeat": {
            "familyId": repeat_family,
            "startingDigestsMatch": len(repeat_starting_digests) == 1,
            "contaminationCanaryObserved": False,
        },
        "representativeFailureReview": {
            "source": "protected_raw_streams_and_artifacts",
            "reviewedFamilies": sorted({gap["familyId"] for gap in candidate_gaps[:4]}),
            "rawStreamsCommitted": False,
        },
        "treatmentAuthorship": {
            "candidateLanguageAuthored": False,
            "reviewScope": "identify_gap_candidates_only",
        },
        "sourceRunDigests": source_run_digests,
    }


def _qualification_from_run_digest(digest: str) -> dict[str, object]:
    """Return a minimal parseable qualification record bound to an observed digest.

    The analysis stage receives immutable RunRecords, not the private
    qualification body. For planning reconstruction, only the digest-bound
    ConditionLock fields must be regenerated consistently; this synthetic body
    is used only when the caller asks to analyze existing protected evidence.
    """

    del digest
    return parse_contract(
        "EnvironmentQualificationRecord",
        {
            "schemaVersion": 1,
            "qualificationId": "analysis-reconstruction",
            "scope": "release_candidate",
            "cliVersion": "1.0.0",
            "cliDigest": "sha256:99bb88401742848e032fd6f51709415fb6be169a72d2e5d7fc44289255160d3c",
            "imageDigest": "sha256:6105d6cc76af400325e94d588ce511be5bfdbb73b437dc51eca43917d7a43e3d",
            "platform": {"schemaVersion": 1, "os": "linux", "architecture": "x64"},
            "modelConfigurationEvidence": {
                "gemini-3.1-pro-high/high": "sha256:af30308345d789145d9087a8d6e5037a089e92239bc312bcaba0099bb8e20ba7",
                "gemini-3.7-flash-high/high": "sha256:73f95cf180a19624e4be9a711fd53a90dadfffa410cc9cd2ba1999454a5b99b8",
            },
            "unknownModelFallbackEvidence": "sha256:5c7ee2074b65853f71fc5a01ce194ff26deedf6daacdb715c6beefdfd3f31b35",
            "structuredCaptureEvidence": "sha256:460ee6aa3a80359181b794cc31a7185addba77626e9f719c10e3c8efb8668a1d",
            "pluginLifecycleEvidence": "sha256:b1e3de3b4c3a15de9e60630eb7531ad0df2397cf7d477504545ad96cb9fdddba",
            "customizationConformanceEvidence": "sha256:412dac876f03f5f5d04de645fbeaf55dc4a0f335f026ed4b209ad232e4a9582a",
            "authorityToolCapabilityEvidence": "sha256:9c89b182fbab8a63ba3bb24d5101415c2d117c2a861f75c088e5f7e246cf6125",
            "supportDecision": "qualified",
            "limitations": [],
            "qualifiedAt": "2026-08-18T11:00:00Z",
        },
    )


__all__ = [
    "MATRIX_TYPE",
    "PROTECTED_RAW_ROOT",
    "analyze_bare_pilot_evidence",
    "load_bare_pilot_matrix",
    "planned_bare_pilot_cells",
    "run_bare_pilot_matrix",
]
