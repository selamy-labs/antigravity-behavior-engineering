"""Protected evaluator contract parsing and canonical digests."""

from __future__ import annotations

import copy
import datetime as dt
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from abe_eval.canonical import MAX_SAFE_INTEGER, canonical_bytes, sha256_digest


class ReasonCodes:
    NOT_OBJECT = "contract.not_object"
    MISSING_FIELD = "contract.missing_field"
    UNKNOWN_FIELD = "contract.unknown_field"
    UNSUPPORTED_SCHEMA_VERSION = "contract.unsupported_schema_version"
    INVALID_FIELD = "contract.invalid_field"
    INVALID_NUMBER = "contract.invalid_number"
    INVALID_KIND = "contract.invalid_kind"
    BINDING_MISMATCH = "contract.binding_mismatch"


class ContractValidationError(TypeError):
    """Stable protected-contract validation error."""

    def __init__(self, reason_code: str, path: str = "$") -> None:
        super().__init__(reason_code + " at " + path)
        self.reason_code = reason_code
        self.reasonCode = reason_code
        self.path = path


_ROOT = Path(__file__).resolve().parents[3]
_EVALUATION_SCHEMA_PATH = _ROOT / "evals" / "schemas" / "evaluation.schema.json"
_APPROVAL_SCHEMA_PATH = _ROOT / "evals" / "schemas" / "approval.schema.json"

_EVALUATION_KINDS = frozenset(
    {
        "PackageLock",
        "ComponentLock",
        "DependencyLock",
        "EvaluationClaim",
        "ScenarioCard",
        "ConditionLock",
        "ConditionPairLock",
        "BlockSpec",
        "MatrixLock",
        "AnalysisLock",
        "PrecisionPowerLock",
        "ResourceEnvelope",
        "ScheduledAttempt",
        "BlindedBaselineInput",
        "WorkerInvocation",
        "AttemptLifecycleEvent",
        "ProcessState",
        "EnvironmentQualificationRecord",
        "QualificationProtocol",
        "AttemptQualificationRecord",
        "GradeRecord",
        "Scorecard",
        "SafetyReport",
        "ProvenanceInventory",
        "AuthorityManifest",
        "CheckLock",
        "ClassificationPolicy",
        "ObservedModel",
        "ConsumptionRecord",
        "CheckResult",
        "ReviewerGrade",
        "TrajectoryDiagnostics",
        "Classification",
        "UnclassifiedStagedAttemptOutcome",
        "StagedAttemptOutcome",
        "StagedAttemptOutcomeBundle",
        "RunRecord",
        "RedactedRun",
        "CodexReferenceConfig",
        "PublicScenario",
        "ReferenceRunRecord",
        "DurableGoalDecision",
    }
)

_APPROVAL_KINDS = frozenset(
    {
        "ReleaseCandidateLock",
        "ProvenanceApprovalRecord",
        "ApprovalRecord",
        "ModelReleaseDecision",
        "ReleaseGateDecision",
        "PackageArchiveRecord",
        "PreparedSchedule",
        "SealedOpeningJournal",
        "PublicationRecord",
        "ReleaseCandidateProvenanceBundle",
        "CandidateFreezeApprovalBundle",
        "PreparedScheduleBundle",
        "SealedOpeningBundle",
        "ReleaseGateBundle",
        "PublicReleaseApprovalBundle",
        "PublicationBundle",
    }
)

_REQUIRED_PAIR_EQUAL_FIELDS = frozenset(
    {
        "/modelRequest",
        "/reasoningRequest",
        "/authorityManifestDigest",
        "/toolInventoryDigest",
        "/permissionDigest",
        "/resourceEnvelopeDigest",
        "/environmentDigest",
    }
)

_ALLOWED_CONDITION_PAIR_DIFFERENCES = frozenset({"/enabledComponents"})

_TARGET_MODEL_KEYS = frozenset({"gemini-3.7-flash-high", "gemini-3.1-pro-high"})

_REQUIRED_CONDITION_LOCK_DIGEST_KEYS = frozenset(
    model + "/" + condition for model in _TARGET_MODEL_KEYS for condition in ("bare", "full")
)

_PUBLIC_CRITERIA = frozenset({"SC-001", *("SC-" + f"{index:03d}" for index in range(3, 14))})

_PRODUCTION_APPROVAL_MECHANISMS = frozenset({"documented_local_approval", "external_signature"})

_QUALIFICATION_PREFLIGHTS = (
    "authentication",
    "fixture_provisioning",
    "model_preflight",
    "fallback_probe",
    "plugin_component_discovery",
    "structured_capture_preflight",
    "authority_tool_inventory",
)

_TIMESTAMP_FIELDS = frozenset(
    {
        "approvedAt",
        "completedAt",
        "createdAt",
        "decidedAt",
        "endedAt",
        "expiresAt",
        "frozenAt",
        "generatedAt",
        "occurredAt",
        "preparedAt",
        "publishedAt",
        "qualifiedAt",
        "scheduledAt",
        "startedAt",
        "validStartAt",
        "validatedAt",
    }
)

_TIMESTAMP_SENTINELS = frozenset({"none", "not_applicable", "not_completed", "not_resumed"})

_CANDIDATE_FREEZE_BOUND_FIELDS = (
    "candidateDigest",
    "qualificationDigest",
    "protocolDigests",
    "analysisLockDigests",
    "precisionPowerLockDigest",
    "sampleAllocationDigest",
    "stoppingRuleDigests",
    "exclusionPolicyDigests",
    "resourceEnvelopeDigests",
    "provenanceApprovalDigest",
)

_PUBLIC_RELEASE_BOUND_FIELDS = (
    "finalArchiveDigest",
    "packageArchiveRecordDigest",
    "releaseReportDigest",
    "publicEvidenceManifestDigest",
    "releaseDecisionDigest",
    "provenanceApprovalDigest",
    "candidateFreezeApprovalDigest",
)


def _fail(reason_code: str, path: str = "$") -> None:
    raise ContractValidationError(reason_code, path)


def _path(parts: object) -> str:
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += "[" + str(part) + "]"
        else:
            path += "." + str(part)
    return path


def _assert_well_formed_unicode(value: str, path: str) -> None:
    for character in value:
        code_point = ord(character)
        if 0xD800 <= code_point <= 0xDFFF:
            _fail(ReasonCodes.INVALID_FIELD, path)


def _clone_shared_json(value: Any, path: str = "$", ancestors: set[int] | None = None) -> Any:
    if ancestors is None:
        ancestors = set()
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        _assert_well_formed_unicode(value, path)
        return value
    if isinstance(value, int):
        if abs(value) > MAX_SAFE_INTEGER:
            _fail(ReasonCodes.INVALID_NUMBER, path)
        return value
    if isinstance(value, float):
        _fail(ReasonCodes.INVALID_NUMBER, path)
    if isinstance(value, list):
        identifier = id(value)
        if identifier in ancestors:
            _fail(ReasonCodes.INVALID_FIELD, path)
        ancestors.add(identifier)
        try:
            return [_clone_shared_json(item, path + "[" + str(index) + "]", ancestors) for index, item in enumerate(value)]
        finally:
            ancestors.remove(identifier)
    if isinstance(value, dict):
        identifier = id(value)
        if identifier in ancestors:
            _fail(ReasonCodes.INVALID_FIELD, path)
        ancestors.add(identifier)
        try:
            result: dict[str, Any] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    _fail(ReasonCodes.INVALID_FIELD, path)
                _assert_well_formed_unicode(key, path)
                result[key] = _clone_shared_json(item, path + "." + key, ancestors)
            return result
        finally:
            ancestors.remove(identifier)
    _fail(ReasonCodes.INVALID_FIELD, path)


def _normalize_reason_code(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    normalized = re.sub(r"_+", "_", normalized)
    return normalized


def _normalize_reason_codes(value: Any) -> Any:
    if isinstance(value, list):
        return [_normalize_reason_codes(item) for item in value]
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if key == "reasonCode" and isinstance(item, str):
                normalized[key] = _normalize_reason_code(item)
            else:
                normalized[key] = _normalize_reason_codes(item)
        return normalized
    return value


@lru_cache(maxsize=2)
def _load_schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema_path_for(kind: str) -> Path:
    if kind in _EVALUATION_KINDS:
        return _EVALUATION_SCHEMA_PATH
    if kind in _APPROVAL_KINDS:
        return _APPROVAL_SCHEMA_PATH
    _fail(ReasonCodes.INVALID_KIND, "$kind")


@lru_cache(maxsize=None)
def _validator_for(kind: str) -> Draft202012Validator:
    schema = copy.deepcopy(_load_schema(_schema_path_for(kind)))
    schema.pop("oneOf", None)
    schema["$ref"] = "#/$defs/" + kind
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _check_rfc3339_utc_seconds(value: str, path: str) -> None:
    if value in _TIMESTAMP_SENTINELS:
        return
    try:
        dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        _fail(ReasonCodes.INVALID_FIELD, path)


def _check_timestamp_fields(value: Any, path: str = "$") -> None:
    if isinstance(value, list):
        for index, item in enumerate(value):
            _check_timestamp_fields(item, path + "[" + str(index) + "]")
        return
    if not isinstance(value, dict):
        return
    for key, item in value.items():
        item_path = path + "." + key
        if key in _TIMESTAMP_FIELDS and isinstance(item, str):
            _check_rfc3339_utc_seconds(item, item_path)
        _check_timestamp_fields(item, item_path)


def _schema_reason(error: ValidationError) -> str:
    if error.validator == "required":
        return ReasonCodes.MISSING_FIELD
    if error.validator in {"additionalProperties", "unevaluatedProperties"}:
        return ReasonCodes.UNKNOWN_FIELD
    if error.validator == "const" and list(error.absolute_path)[-1:] == ["schemaVersion"]:
        return ReasonCodes.UNSUPPORTED_SCHEMA_VERSION
    if not error.absolute_path and error.validator == "type":
        return ReasonCodes.NOT_OBJECT
    if error.validator == "type" and any(type_name == "integer" for type_name in error.validator_value if isinstance(error.validator_value, list)):
        return ReasonCodes.INVALID_NUMBER
    if error.validator == "type" and error.validator_value == "integer":
        return ReasonCodes.INVALID_NUMBER
    return ReasonCodes.INVALID_FIELD


def _validate_schema(kind: str, value: dict[str, Any]) -> None:
    errors = sorted(
        _validator_for(kind).iter_errors(value),
        key=lambda error: (tuple(error.absolute_path), str(error.validator), str(error.message)),
    )
    if errors:
        error = errors[0]
        _fail(_schema_reason(error), _path(error.absolute_path))


def _require_sorted_unique(items: list[Any], path: str) -> None:
    if len(items) != len(set(items)) or items != sorted(items):
        _fail(ReasonCodes.INVALID_FIELD, path)


def _require_target_model_map(value: dict[str, Any], path: str) -> None:
    if set(value) != _TARGET_MODEL_KEYS:
        _fail(ReasonCodes.BINDING_MISMATCH, path)


def _require_exact_map(actual: dict[str, Any], expected: dict[str, Any], path: str = "$.boundDigests") -> None:
    if set(actual) != set(expected):
        _fail(ReasonCodes.BINDING_MISMATCH, path)
    if any(actual[key] != expected[key] for key in expected):
        _fail(ReasonCodes.BINDING_MISMATCH, path)


def _payload_digest(record: dict[str, Any]) -> str:
    payload = copy.deepcopy(record)
    payload.pop("signature")
    return sha256_digest(canonical_bytes(payload))


def _check_signature_payload(record: dict[str, Any], path: str = "$.signature.signedPayloadDigest") -> None:
    if record["signature"]["signedPayloadDigest"] != _payload_digest(record):
        _fail(ReasonCodes.BINDING_MISMATCH, path)


def _check_production_approval(record: dict[str, Any], path: str) -> None:
    signature = record["signature"]
    if signature["mechanism"] not in _PRODUCTION_APPROVAL_MECHANISMS:
        _fail(ReasonCodes.BINDING_MISMATCH, path + ".signature.mechanism")
    if "approvalEvidenceDigest" not in signature:
        _fail(ReasonCodes.BINDING_MISMATCH, path + ".signature.approvalEvidenceDigest")
    if signature["signatureDigest"] == signature["signedPayloadDigest"]:
        _fail(ReasonCodes.BINDING_MISMATCH, path + ".signature.signatureDigest")
    if signature["approvalEvidenceDigest"] == signature["signedPayloadDigest"]:
        _fail(ReasonCodes.BINDING_MISMATCH, path + ".signature.approvalEvidenceDigest")


def _digest_value(kind: str, value: dict[str, Any]) -> str:
    parsed = parse_contract(kind, value)
    if kind == "ReleaseCandidateLock":
        parsed = {key: item for key, item in parsed.items() if key != "frozenAt"}
    return sha256_digest(canonical_bytes(parsed))


def _check_condition_pair(value: dict[str, Any]) -> None:
    required = set(value["requiredEqualFields"])
    allowed = set(value["allowedDifferences"])
    if required != _REQUIRED_PAIR_EQUAL_FIELDS or required.intersection(allowed):
        _fail(ReasonCodes.BINDING_MISMATCH, "$.requiredEqualFields")
    if allowed != _ALLOWED_CONDITION_PAIR_DIFFERENCES:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.allowedDifferences")
    _require_sorted_unique(value["requiredEqualFields"], "$.requiredEqualFields")
    _require_sorted_unique(value["allowedDifferences"], "$.allowedDifferences")


def _check_package_lock(value: dict[str, Any]) -> None:
    component_keys = [(component["kind"], component["name"]) for component in value["components"]]
    if len(component_keys) != len(set(component_keys)):
        _fail(ReasonCodes.BINDING_MISMATCH, "$.components")
    for path in value["files"]:
        if path.startswith("/") or ".." in path.split("/") or "\\" in path or "\x00" in path or not path:
            _fail(ReasonCodes.INVALID_FIELD, "$.files")


def _check_condition_lock(value: dict[str, Any]) -> None:
    if value["modelRequest"] not in _TARGET_MODEL_KEYS:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.modelRequest")
    _require_sorted_unique(value["enabledComponents"], "$.enabledComponents")


def _check_block_spec(value: dict[str, Any]) -> None:
    if value["modelRequest"] not in _TARGET_MODEL_KEYS:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.modelRequest")
    _require_sorted_unique(value["scenarioDigests"], "$.scenarioDigests")


def _check_matrix_lock(value: dict[str, Any]) -> None:
    _require_sorted_unique(value["conditionDigests"], "$.conditionDigests")
    _require_sorted_unique(value["analysisLockDigests"], "$.analysisLockDigests")


def _check_resource_envelope(value: dict[str, Any]) -> None:
    if value["overagePolicy"] != "fail_profile":
        _fail(ReasonCodes.BINDING_MISMATCH, "$.overagePolicy")


def _check_scheduled_attempt(value: dict[str, Any]) -> None:
    if value["replacementForAttemptId"] == "none" and value["retryOrdinal"] != 0:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.retryOrdinal")
    if value["replacementForAttemptId"] != "none" and value["retryOrdinal"] < 1:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.retryOrdinal")


def _check_lifecycle_event(value: dict[str, Any]) -> None:
    terminal_phases = {"execution_terminal"}
    if value["phase"] in terminal_phases and value["terminalKind"] == "none":
        _fail(ReasonCodes.BINDING_MISMATCH, "$.terminalKind")
    if value["phase"] not in terminal_phases and value["terminalKind"] != "none":
        _fail(ReasonCodes.BINDING_MISMATCH, "$.terminalKind")


def _check_environment_qualification(value: dict[str, Any]) -> None:
    if value["scope"] == "release_candidate":
        if value["pluginLifecycleEvidence"] == "not_applicable" or value["customizationConformanceEvidence"] == "not_applicable":
            _fail(ReasonCodes.BINDING_MISMATCH, "$.scope")
    if value["scope"] == "cli_core":
        return


def _check_qualification_protocol(value: dict[str, Any]) -> None:
    if value["customizationScope"] == "release_candidate":
        models = {request["modelRequest"] for request in value["modelRequests"]}
        _require_target_model_map({model: True for model in models}, "$.modelRequests")
    if tuple(value["requiredPreflights"]) != _QUALIFICATION_PREFLIGHTS:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.requiredPreflights")


def _check_scorecard(value: dict[str, Any]) -> None:
    if value["modelRequest"] not in _TARGET_MODEL_KEYS:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.modelRequest")


def _check_durable_goal_decision(value: dict[str, Any]) -> None:
    _require_target_model_map(value["perModelMarginDecisions"], "$.perModelMarginDecisions")
    _require_sorted_unique(value["blockingPredicates"], "$.blockingPredicates")
    all_models_pass = all(decision["decision"] == "pass" for decision in value["perModelMarginDecisions"].values())
    can_pass = all_models_pass and value["desktopCalibrationComplete"] and value["publicationRecordDigest"] != "not_published"
    if value["overallDecision"] == "pass" and (not can_pass or value["blockingPredicates"]):
        _fail(ReasonCodes.BINDING_MISMATCH, "$.overallDecision")
    if value["overallDecision"] != "pass" and can_pass and not value["blockingPredicates"]:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.blockingPredicates")


def _check_process_state(value: dict[str, Any], path: str = "$.processState") -> None:
    if value["workerProcessState"] == "not_started" and (
        value["workerExitCode"] != "none" or value["startedAt"] != "none"
    ):
        _fail(ReasonCodes.BINDING_MISMATCH, path)


def _check_pre_worker_run(value: dict[str, Any]) -> None:
    process = value["processState"]
    _check_process_state(process)
    if process["workerProcessState"] == "not_started" and (
        value["attemptQualification"]["validStartAt"] != "none" or value["agentDeclaredState"] != "none"
    ):
        _fail(ReasonCodes.BINDING_MISMATCH, "$.attemptQualification.validStartAt")


def _check_model_release_decision(value: dict[str, Any], path: str = "$") -> None:
    _require_sorted_unique(value["blockingCriteria"], path + ".blockingCriteria")
    if value["modelRequest"] not in _TARGET_MODEL_KEYS:
        _fail(ReasonCodes.BINDING_MISMATCH, path + ".modelRequest")
    if set(value["criterionResults"]) != _PUBLIC_CRITERIA:
        _fail(ReasonCodes.BINDING_MISMATCH, path + ".criterionResults")
    failed = sorted(criterion for criterion, result in value["criterionResults"].items() if result["result"] != "pass")
    if value["decision"] == "pass" and (failed or value["blockingCriteria"]):
        _fail(ReasonCodes.BINDING_MISMATCH, path + ".decision")
    if value["decision"] == "fail" and (not failed or value["blockingCriteria"] != failed):
        _fail(ReasonCodes.BINDING_MISMATCH, path + ".decision")


def _check_release_gate_decision(value: dict[str, Any]) -> None:
    _require_sorted_unique(value["blockingCriteria"], "$.blockingCriteria")
    if set(value["perModelDecisions"]) != _TARGET_MODEL_KEYS:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.perModelDecisions")
    for key, decision in value["perModelDecisions"].items():
        if key != decision["modelRequest"]:
            _fail(ReasonCodes.BINDING_MISMATCH, "$.perModelDecisions." + key)
        _check_model_release_decision(decision, "$.perModelDecisions." + key)
    failed = sorted(
        key + "/" + criterion
        for key, decision in value["perModelDecisions"].items()
        for criterion in decision["blockingCriteria"]
    )
    if value["overallDecision"] == "pass" and (failed or value["blockingCriteria"]):
        _fail(ReasonCodes.BINDING_MISMATCH, "$.overallDecision")
    if value["overallDecision"] == "fail" and (not failed or value["blockingCriteria"] != failed):
        _fail(ReasonCodes.BINDING_MISMATCH, "$.overallDecision")


def _check_approval_record(value: dict[str, Any]) -> None:
    _check_signature_payload(value)
    if value["gate"] == "candidate_freeze":
        if value["publicationTargetDigest"] != "not_applicable" or value["publicationChannelAuthorityDigest"] != "not_applicable":
            _fail(ReasonCodes.BINDING_MISMATCH, "$.publicationTargetDigest")
        if set(value["boundDigests"]) != set(_CANDIDATE_FREEZE_BOUND_FIELDS):
            _fail(ReasonCodes.BINDING_MISMATCH, "$.boundDigests")
        for field in ("protocolDigests", "analysisLockDigests", "stoppingRuleDigests", "exclusionPolicyDigests", "resourceEnvelopeDigests"):
            _require_sorted_unique(value["boundDigests"][field], "$.boundDigests." + field)
        return
    if value["publicationTargetDigest"] == "not_applicable" or value["publicationChannelAuthorityDigest"] == "not_applicable":
        _fail(ReasonCodes.BINDING_MISMATCH, "$.publicationTargetDigest")
    if set(value["boundDigests"]) != set(_PUBLIC_RELEASE_BOUND_FIELDS):
        _fail(ReasonCodes.BINDING_MISMATCH, "$.boundDigests")


def _check_provenance_approval(value: dict[str, Any]) -> None:
    _check_signature_payload(value)


def _check_release_candidate(value: dict[str, Any]) -> None:
    if set(value["conditionLockDigests"]) != _REQUIRED_CONDITION_LOCK_DIGEST_KEYS:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.conditionLockDigests")
    for field in (
        "taskFamilyProtocolDigests",
        "analysisLockDigests",
        "stoppingRuleDigests",
        "exclusionPolicyDigests",
        "resourceEnvelopeDigests",
    ):
        _require_sorted_unique(value[field], "$" + "." + field)


def _check_precision_power(value: dict[str, Any]) -> None:
    _require_sorted_unique(value["analysisLockDigests"], "$.analysisLockDigests")
    if value["honestyNegativeVariantMinimumPerModelFullCondition"] != "not_applicable":
        if value["honestyNegativeVariantMinimumPerModelFullCondition"] < 1:
            _fail(ReasonCodes.INVALID_NUMBER, "$.honestyNegativeVariantMinimumPerModelFullCondition")


def _check_blinded_baseline(value: dict[str, Any]) -> None:
    _require_sorted_unique(value["sourceAttemptDigests"], "$.sourceAttemptDigests")
    _require_sorted_unique(value["analysisLockDigests"], "$.analysisLockDigests")


def _check_prepared_schedule(value: dict[str, Any]) -> None:
    _require_sorted_unique(value["pairLockDigests"], "$.pairLockDigests")
    _require_sorted_unique(value["resourceEnvelopeDigests"], "$.resourceEnvelopeDigests")


def _check_evaluation_claim(value: dict[str, Any]) -> None:
    _require_sorted_unique(value["taskFamilyIds"], "$.taskFamilyIds")


def _check_candidate_freeze_bundle(value: dict[str, Any]) -> None:
    candidate = parse_contract("ReleaseCandidateLock", value["releaseCandidateLock"])
    provenance = parse_contract("ProvenanceApprovalRecord", value["provenanceApprovalRecord"])
    approval = parse_contract("ApprovalRecord", value["approvalRecord"])
    _check_production_approval(provenance, "$.provenanceApprovalRecord")
    _check_production_approval(approval, "$.approvalRecord")
    candidate_digest = _digest_value("ReleaseCandidateLock", candidate)
    provenance_digest = _digest_value("ProvenanceApprovalRecord", provenance)
    if provenance["decision"] != "approved" or approval["decision"] != "approved" or approval["gate"] != "candidate_freeze":
        _fail(ReasonCodes.BINDING_MISMATCH, "$.approvalRecord")
    if candidate["provenanceApprovalDigest"] != provenance_digest:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.releaseCandidateLock.provenanceApprovalDigest")
    expected = {
        "candidateDigest": candidate_digest,
        "qualificationDigest": candidate["qualificationDigest"],
        "protocolDigests": candidate["taskFamilyProtocolDigests"],
        "analysisLockDigests": candidate["analysisLockDigests"],
        "precisionPowerLockDigest": candidate["precisionPowerLockDigest"],
        "sampleAllocationDigest": candidate["sampleAllocationDigest"],
        "stoppingRuleDigests": candidate["stoppingRuleDigests"],
        "exclusionPolicyDigests": candidate["exclusionPolicyDigests"],
        "resourceEnvelopeDigests": candidate["resourceEnvelopeDigests"],
        "provenanceApprovalDigest": provenance_digest,
    }
    _require_exact_map(approval["boundDigests"], expected)
    value["releaseCandidateLock"] = candidate
    value["provenanceApprovalRecord"] = provenance
    value["approvalRecord"] = approval


def _check_release_candidate_provenance_bundle(value: dict[str, Any]) -> None:
    candidate = parse_contract("ReleaseCandidateLock", value["releaseCandidateLock"])
    provenance = parse_contract("ProvenanceApprovalRecord", value["provenanceApprovalRecord"])
    _check_production_approval(provenance, "$.provenanceApprovalRecord")
    if provenance["decision"] != "approved":
        _fail(ReasonCodes.BINDING_MISMATCH, "$.provenanceApprovalRecord.decision")
    if candidate["provenanceApprovalDigest"] != _digest_value("ProvenanceApprovalRecord", provenance):
        _fail(ReasonCodes.BINDING_MISMATCH, "$.releaseCandidateLock.provenanceApprovalDigest")
    value["releaseCandidateLock"] = candidate
    value["provenanceApprovalRecord"] = provenance


def _check_prepared_schedule_bundle(value: dict[str, Any]) -> None:
    candidate = parse_contract("ReleaseCandidateLock", value["releaseCandidateLock"])
    schedule = parse_contract("PreparedSchedule", value["preparedSchedule"])
    if schedule["candidateDigest"] != _digest_value("ReleaseCandidateLock", candidate):
        _fail(ReasonCodes.BINDING_MISMATCH, "$.preparedSchedule.candidateDigest")
    if schedule["qualificationDigest"] != candidate["qualificationDigest"]:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.preparedSchedule.qualificationDigest")
    value["releaseCandidateLock"] = candidate
    value["preparedSchedule"] = schedule


def _check_sealed_opening_bundle(value: dict[str, Any]) -> None:
    candidate = parse_contract("ReleaseCandidateLock", value["releaseCandidateLock"])
    approval = parse_contract("ApprovalRecord", value["approvalRecord"])
    schedule = parse_contract("PreparedSchedule", value["preparedSchedule"])
    journal = parse_contract("SealedOpeningJournal", value["sealedOpeningJournal"])
    _check_production_approval(approval, "$.approvalRecord")
    candidate_digest = _digest_value("ReleaseCandidateLock", candidate)
    approval_digest = _digest_value("ApprovalRecord", approval)
    schedule_digest = _digest_value("PreparedSchedule", schedule)
    if approval["gate"] != "candidate_freeze" or approval["decision"] != "approved":
        _fail(ReasonCodes.BINDING_MISMATCH, "$.approvalRecord")
    if approval["boundDigests"]["candidateDigest"] != candidate_digest:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.approvalRecord.boundDigests.candidateDigest")
    if schedule["candidateDigest"] != candidate_digest:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.preparedSchedule.candidateDigest")
    if journal["candidateDigest"] != candidate_digest or journal["approvalDigest"] != approval_digest:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.sealedOpeningJournal.approvalDigest")
    if journal["preparedScheduleDigest"] != schedule_digest:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.sealedOpeningJournal.preparedScheduleDigest")
    value["releaseCandidateLock"] = candidate
    value["approvalRecord"] = approval
    value["preparedSchedule"] = schedule
    value["sealedOpeningJournal"] = journal


def _check_release_gate_bundle(value: dict[str, Any]) -> None:
    candidate = parse_contract("ReleaseCandidateLock", value["releaseCandidateLock"])
    decision = parse_contract("ReleaseGateDecision", value["releaseGateDecision"])
    if decision["candidateDigest"] != _digest_value("ReleaseCandidateLock", candidate):
        _fail(ReasonCodes.BINDING_MISMATCH, "$.releaseGateDecision.candidateDigest")
    value["releaseCandidateLock"] = candidate
    value["releaseGateDecision"] = decision


def _check_public_release_bundle(value: dict[str, Any]) -> None:
    package = parse_contract("PackageArchiveRecord", value["packageArchiveRecord"])
    decision = parse_contract("ReleaseGateDecision", value["releaseGateDecision"])
    provenance = parse_contract("ProvenanceApprovalRecord", value["provenanceApprovalRecord"])
    candidate_approval = parse_contract("ApprovalRecord", value["candidateFreezeApprovalRecord"])
    approval = parse_contract("ApprovalRecord", value["approvalRecord"])
    _check_production_approval(provenance, "$.provenanceApprovalRecord")
    _check_production_approval(candidate_approval, "$.candidateFreezeApprovalRecord")
    _check_production_approval(approval, "$.approvalRecord")
    if decision["overallDecision"] != "pass" or provenance["decision"] != "approved":
        _fail(ReasonCodes.BINDING_MISMATCH, "$.releaseGateDecision")
    if candidate_approval["gate"] != "candidate_freeze" or candidate_approval["decision"] != "approved":
        _fail(ReasonCodes.BINDING_MISMATCH, "$.candidateFreezeApprovalRecord")
    if approval["gate"] != "public_release" or approval["decision"] != "approved":
        _fail(ReasonCodes.BINDING_MISMATCH, "$.approvalRecord")
    provenance_digest = _digest_value("ProvenanceApprovalRecord", provenance)
    if candidate_approval["boundDigests"]["candidateDigest"] != decision["candidateDigest"]:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.candidateFreezeApprovalRecord.boundDigests.candidateDigest")
    if candidate_approval["boundDigests"]["provenanceApprovalDigest"] != provenance_digest:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.candidateFreezeApprovalRecord.boundDigests.provenanceApprovalDigest")
    expected = copy.deepcopy(approval["boundDigests"])
    expected.update(
        {
            "finalArchiveDigest": package["archiveDigest"],
            "packageArchiveRecordDigest": _digest_value("PackageArchiveRecord", package),
            "releaseDecisionDigest": _digest_value("ReleaseGateDecision", decision),
            "provenanceApprovalDigest": provenance_digest,
            "candidateFreezeApprovalDigest": _digest_value("ApprovalRecord", candidate_approval),
        }
    )
    _require_exact_map(approval["boundDigests"], expected)
    value["packageArchiveRecord"] = package
    value["releaseGateDecision"] = decision
    value["provenanceApprovalRecord"] = provenance
    value["candidateFreezeApprovalRecord"] = candidate_approval
    value["approvalRecord"] = approval


def _check_publication_bundle(value: dict[str, Any]) -> None:
    package = parse_contract("PackageArchiveRecord", value["packageArchiveRecord"])
    decision = parse_contract("ReleaseGateDecision", value["releaseGateDecision"])
    approval = parse_contract("ApprovalRecord", value["approvalRecord"])
    publication = parse_contract("PublicationRecord", value["publicationRecord"])
    _check_production_approval(approval, "$.approvalRecord")
    if decision["overallDecision"] != "pass" or approval["gate"] != "public_release" or approval["decision"] != "approved":
        _fail(ReasonCodes.BINDING_MISMATCH, "$.approvalRecord")
    if approval["boundDigests"]["finalArchiveDigest"] != package["archiveDigest"]:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.approvalRecord.boundDigests.finalArchiveDigest")
    if approval["boundDigests"]["packageArchiveRecordDigest"] != _digest_value("PackageArchiveRecord", package):
        _fail(ReasonCodes.BINDING_MISMATCH, "$.approvalRecord.boundDigests.packageArchiveRecordDigest")
    release_decision_digest = _digest_value("ReleaseGateDecision", decision)
    if approval["boundDigests"]["releaseDecisionDigest"] != release_decision_digest:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.approvalRecord.boundDigests.releaseDecisionDigest")
    if publication["approvalDigest"] != _digest_value("ApprovalRecord", approval):
        _fail(ReasonCodes.BINDING_MISMATCH, "$.publicationRecord.approvalDigest")
    if publication["publicationTargetDigest"] != approval["publicationTargetDigest"]:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.publicationRecord.publicationTargetDigest")
    if publication["publicationChannelAuthorityDigest"] != approval["publicationChannelAuthorityDigest"]:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.publicationRecord.publicationChannelAuthorityDigest")
    if publication["archiveDigest"] != package["archiveDigest"]:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.publicationRecord.archiveDigest")
    if publication["releaseDecisionDigest"] != release_decision_digest:
        _fail(ReasonCodes.BINDING_MISMATCH, "$.publicationRecord.releaseDecisionDigest")
    value["packageArchiveRecord"] = package
    value["releaseGateDecision"] = decision
    value["approvalRecord"] = approval
    value["publicationRecord"] = publication


def _check_staged_outcome_bundle(value: dict[str, Any]) -> None:
    unclassified = parse_contract("UnclassifiedStagedAttemptOutcome", value["unclassifiedOutcome"])
    staged = parse_contract("StagedAttemptOutcome", value["stagedOutcome"])
    if staged["unclassifiedOutcomeDigest"] != _digest_value("UnclassifiedStagedAttemptOutcome", unclassified):
        _fail(ReasonCodes.BINDING_MISMATCH, "$.stagedOutcome.unclassifiedOutcomeDigest")
    for field in (
        "attemptId",
        "runId",
        "conditionDigest",
        "scenarioDigest",
        "environmentQualificationDigest",
        "lifecycleEventDigests",
        "attemptQualification",
        "observedModel",
        "processState",
        "agentDeclaredState",
        "inputPermissionState",
        "infrastructureValidity",
        "consumption",
        "stagingManifestDigest",
    ):
        if staged[field] != unclassified[field]:
            _fail(ReasonCodes.BINDING_MISMATCH, "$.stagedOutcome." + field)
    value["unclassifiedOutcome"] = unclassified
    value["stagedOutcome"] = staged


def _run_parser_checks(kind: str, value: dict[str, Any]) -> None:
    if kind == "PackageLock":
        _check_package_lock(value)
    elif kind == "EvaluationClaim":
        _check_evaluation_claim(value)
    elif kind == "ConditionLock":
        _check_condition_lock(value)
    elif kind == "ConditionPairLock":
        _check_condition_pair(value)
    elif kind == "BlockSpec":
        _check_block_spec(value)
    elif kind == "MatrixLock":
        _check_matrix_lock(value)
    elif kind == "ResourceEnvelope":
        _check_resource_envelope(value)
    elif kind == "PrecisionPowerLock":
        _check_precision_power(value)
    elif kind == "BlindedBaselineInput":
        _check_blinded_baseline(value)
    elif kind in {"ProcessState"}:
        _check_process_state(value, "$")
    elif kind == "ScheduledAttempt":
        _check_scheduled_attempt(value)
    elif kind == "AttemptLifecycleEvent":
        _check_lifecycle_event(value)
    elif kind == "EnvironmentQualificationRecord":
        _check_environment_qualification(value)
    elif kind == "QualificationProtocol":
        _check_qualification_protocol(value)
    elif kind == "Scorecard":
        _check_scorecard(value)
    elif kind == "DurableGoalDecision":
        _check_durable_goal_decision(value)
    elif kind == "StagedAttemptOutcomeBundle":
        _check_staged_outcome_bundle(value)
    elif kind == "RunRecord":
        _check_pre_worker_run(value)
    elif kind == "ReleaseCandidateLock":
        _check_release_candidate(value)
    elif kind == "ProvenanceApprovalRecord":
        _check_provenance_approval(value)
    elif kind == "ApprovalRecord":
        _check_approval_record(value)
    elif kind == "ModelReleaseDecision":
        _check_model_release_decision(value)
    elif kind == "ReleaseGateDecision":
        _check_release_gate_decision(value)
    elif kind == "PreparedSchedule":
        _check_prepared_schedule(value)
    elif kind == "ReleaseCandidateProvenanceBundle":
        _check_release_candidate_provenance_bundle(value)
    elif kind == "CandidateFreezeApprovalBundle":
        _check_candidate_freeze_bundle(value)
    elif kind == "PreparedScheduleBundle":
        _check_prepared_schedule_bundle(value)
    elif kind == "SealedOpeningBundle":
        _check_sealed_opening_bundle(value)
    elif kind == "ReleaseGateBundle":
        _check_release_gate_bundle(value)
    elif kind == "PublicReleaseApprovalBundle":
        _check_public_release_bundle(value)
    elif kind == "PublicationBundle":
        _check_publication_bundle(value)


def parse_contract(kind: str, value: object) -> dict[str, object]:
    """Return a normalized protected contract or raise ContractValidationError."""

    if not isinstance(kind, str):
        _fail(ReasonCodes.INVALID_KIND, "$kind")
    cloned = _normalize_reason_codes(_clone_shared_json(value))
    if not isinstance(cloned, dict):
        _fail(ReasonCodes.NOT_OBJECT)
    _schema_path_for(kind)
    _validate_schema(kind, cloned)
    _check_timestamp_fields(cloned)
    _run_parser_checks(kind, cloned)
    return cloned


def canonical_contract_digest(kind: str, value: object) -> str:
    """Digest the canonical bytes for the parsed, normalized protected contract."""

    parsed = parse_contract(kind, value)
    if kind == "ReleaseCandidateLock":
        parsed = {key: item for key, item in parsed.items() if key != "frozenAt"}
    return sha256_digest(canonical_bytes(parsed))


__all__ = ["ContractValidationError", "ReasonCodes", "canonical_contract_digest", "parse_contract"]
