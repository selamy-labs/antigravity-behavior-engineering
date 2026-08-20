import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import ContractValidationError, canonical_contract_digest, parse_contract


FIXTURE_PATH = Path("tests/contract/fixtures/evaluation-contracts.json")
EVALUATION_SCHEMA_PATH = Path("evals/schemas/evaluation.schema.json")
APPROVAL_SCHEMA_PATH = Path("evals/schemas/approval.schema.json")

TARGET_MODELS = ("gemini-3.7-flash-high", "gemini-3.1-pro-high")
PUBLIC_CRITERIA = ("SC-001",) + tuple(f"SC-{index:03d}" for index in range(3, 14))
PHASE0_CONTRACT_KINDS = (
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
    "ReleaseCandidateLock",
    "ScheduledAttempt",
    "WorkerInvocation",
    "AttemptLifecycleEvent",
    "RunRecord",
    "UnclassifiedStagedAttemptOutcome",
    "StagedAttemptOutcome",
    "StagedAttemptOutcomeBundle",
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
    "BlindedBaselineInput",
    "ApprovalRecord",
    "ProvenanceApprovalRecord",
    "ReleaseGateDecision",
    "ModelReleaseDecision",
    "PackageArchiveRecord",
    "PreparedSchedule",
    "SealedOpeningJournal",
    "PublicationRecord",
    "RedactedRun",
    "CodexReferenceConfig",
    "PublicScenario",
    "ReferenceRunRecord",
    "DurableGoalDecision",
)
FIXTURE_EVIDENCE_DIGEST = "sha256:" + "5" * 64
FIXTURE_SIGNATURE_DIGEST = "sha256:" + "6" * 64


def _fixtures():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _valid_cases_by_name():
    return {case["name"]: case for case in _fixtures()["validCases"]}


def _case_value(name):
    return copy.deepcopy(_valid_cases_by_name()[name]["value"])


def _expect_evaluation_schema_rejects(value):
    schema = json.loads(EVALUATION_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(value))


def _apply_patch(value, patch):
    patched = copy.deepcopy(value)
    for key, replacement in patch.items():
        patched[key] = replacement
    return patched


def _payload_signature_digest(record):
    payload = copy.deepcopy(record)
    payload.pop("signature")
    return sha256_digest(canonical_bytes(payload))


def _sign(record):
    signed = copy.deepcopy(record)
    signed["signature"]["signedPayloadDigest"] = _payload_signature_digest(signed)
    return signed


def _production_sign(record):
    signed = copy.deepcopy(record)
    signed["signature"]["mechanism"] = "documented_local_approval"
    signed["signature"]["approvalEvidenceDigest"] = FIXTURE_EVIDENCE_DIGEST
    signed["signature"]["signatureDigest"] = FIXTURE_SIGNATURE_DIGEST
    signed["signature"]["signedPayloadDigest"] = _payload_signature_digest(signed)
    return signed


def _digest(kind, value):
    return canonical_contract_digest(kind, value)


def _release_objects():
    provenance = _production_sign(_case_value("ProvenanceApprovalRecord"))
    provenance_digest = _digest("ProvenanceApprovalRecord", provenance)

    candidate = _case_value("ReleaseCandidateLock")
    candidate["provenanceApprovalDigest"] = provenance_digest
    candidate_digest = _digest("ReleaseCandidateLock", candidate)

    candidate_approval = _case_value("ApprovalRecordCandidateFreeze")
    candidate_approval["boundDigests"] = {
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
    candidate_approval = _production_sign(candidate_approval)
    candidate_approval_digest = _digest("ApprovalRecord", candidate_approval)

    schedule = _case_value("PreparedSchedule")
    schedule["candidateDigest"] = candidate_digest
    schedule["qualificationDigest"] = candidate["qualificationDigest"]
    schedule_digest = _digest("PreparedSchedule", schedule)

    journal = _case_value("SealedOpeningJournal")
    journal["candidateDigest"] = candidate_digest
    journal["approvalDigest"] = candidate_approval_digest
    journal["preparedScheduleDigest"] = schedule_digest

    release_decision = _case_value("ReleaseGateDecision")
    release_decision["candidateDigest"] = candidate_digest
    release_decision_digest = _digest("ReleaseGateDecision", release_decision)

    package_archive = _case_value("PackageArchiveRecord")
    package_archive_digest = _digest("PackageArchiveRecord", package_archive)

    public_approval = _case_value("ApprovalRecordPublicRelease")
    public_approval["boundDigests"] = {
        "finalArchiveDigest": package_archive["archiveDigest"],
        "packageArchiveRecordDigest": package_archive_digest,
        "releaseReportDigest": public_approval["boundDigests"]["releaseReportDigest"],
        "publicEvidenceManifestDigest": public_approval["boundDigests"]["publicEvidenceManifestDigest"],
        "releaseDecisionDigest": release_decision_digest,
        "provenanceApprovalDigest": provenance_digest,
        "candidateFreezeApprovalDigest": candidate_approval_digest,
    }
    public_approval = _production_sign(public_approval)
    public_approval_digest = _digest("ApprovalRecord", public_approval)

    publication = _case_value("PublicationRecord")
    publication["approvalDigest"] = public_approval_digest
    publication["publicationTargetDigest"] = public_approval["publicationTargetDigest"]
    publication["publicationChannelAuthorityDigest"] = public_approval["publicationChannelAuthorityDigest"]
    publication["archiveDigest"] = package_archive["archiveDigest"]
    publication["releaseDecisionDigest"] = release_decision_digest

    return {
        "provenanceApprovalRecord": provenance,
        "releaseCandidateLock": candidate,
        "candidateFreezeApprovalRecord": candidate_approval,
        "preparedSchedule": schedule,
        "sealedOpeningJournal": journal,
        "releaseGateDecision": release_decision,
        "packageArchiveRecord": package_archive,
        "publicReleaseApprovalRecord": public_approval,
        "publicationRecord": publication,
    }


def expect_reason(kind, value, reason_code):
    with pytest.raises(ContractValidationError) as excinfo:
        parse_contract(kind, value)
    assert excinfo.value.reason_code == reason_code


def test_json_schemas_are_valid_draft_2020_12():
    for schema_path in [EVALUATION_SCHEMA_PATH, APPROVAL_SCHEMA_PATH]:
        Draft202012Validator.check_schema(json.loads(schema_path.read_text(encoding="utf-8")))


def test_phase0_contract_roots_have_valid_fixtures_and_closed_root_schemas():
    fixtures = _fixtures()
    cases_by_kind = {case["kind"]: case for case in fixtures["validCases"]}
    assert sorted(set(PHASE0_CONTRACT_KINDS) - set(cases_by_kind)) == []

    for schema_path in [EVALUATION_SCHEMA_PATH, APPROVAL_SCHEMA_PATH]:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(schema).iter_errors({"schemaVersion": 1, "unexpected": True}))
        assert errors, schema_path

    for kind in PHASE0_CONTRACT_KINDS:
        value = copy.deepcopy(cases_by_kind[kind]["value"])
        if kind in {"ApprovalRecord", "ProvenanceApprovalRecord"}:
            value = _sign(value)
        parse_contract(kind, value)


@pytest.mark.parametrize("case", _fixtures()["validCases"], ids=lambda case: case["name"])
def test_valid_contract_fixtures_parse_and_digest(case):
    value = copy.deepcopy(case["value"])
    if case["kind"] in {"ApprovalRecord", "ProvenanceApprovalRecord"}:
        value = _sign(value)
    parsed = parse_contract(case["kind"], value)
    assert parsed == value or case["kind"] == "Classification"
    digest = canonical_contract_digest(case["kind"], value)
    assert digest.startswith("sha256:")
    assert len(digest) == 71


@pytest.mark.parametrize("case", _fixtures()["boundaryCases"], ids=lambda case: case["name"])
def test_boundary_contract_fixtures_parse(case):
    value = _apply_patch(_case_value(case["base"]), case["patch"])
    parsed = parse_contract(case["kind"], value)
    for key, expected in case.get("expected", {}).items():
        assert parsed[key] == expected


def test_invalid_and_forward_version_fixture_sections_fail_closed():
    fixtures = _fixtures()
    assert fixtures["invalidCases"]
    assert fixtures["forwardVersionCases"]

    for case in fixtures["invalidCases"]:
        value = _apply_patch(_case_value(case["base"]), case["patch"])
        expect_reason(case["kind"], value, case["reasonCode"])

    for case in fixtures["forwardVersionCases"]:
        value = _apply_patch(_case_value(case["base"]), case["patch"])
        expect_reason(case["kind"], value, "contract.unsupported_schema_version")


def test_timestamp_fields_reject_impossible_rfc3339_values():
    process = _case_value("ProcessStateTerminated")
    process["endedAt"] = "2026-99-99T99:99:99Z"
    expect_reason("ProcessState", process, "contract.invalid_field")

    approval = _case_value("ApprovalRecordCandidateFreeze")
    approval["approvedAt"] = "2026-99-99T99:99:99Z"
    expect_reason("ApprovalRecord", _sign(approval), "contract.invalid_field")

    journal = _case_value("SealedOpeningJournal")
    journal["preparedAt"] = "2026-99-99T99:99:99Z"
    expect_reason("SealedOpeningJournal", journal, "contract.invalid_field")


def test_unknown_missing_version_and_reason_normalization_have_stable_codes():
    claim = _case_value("EvaluationClaim")
    expect_reason("EvaluationClaim", {**claim, "unexpected": True}, "contract.unknown_field")

    missing = copy.deepcopy(claim)
    missing.pop("claimId")
    expect_reason("EvaluationClaim", missing, "contract.missing_field")

    expect_reason("EvaluationClaim", {**claim, "schemaVersion": 2}, "contract.unsupported_schema_version")

    classification = _case_value("ClassificationProductTimeout")
    classification["reasonCode"] = " Product Timeout "
    assert parse_contract("Classification", classification)["reasonCode"] == "product_timeout"


def test_canonical_digest_parses_and_normalizes_before_hashing():
    classification = _case_value("ClassificationProductTimeout")
    messy_reason = {**classification, "reasonCode": "PRODUCT TIMEOUT"}
    assert canonical_contract_digest("Classification", classification) == canonical_contract_digest(
        "Classification", messy_reason
    )

    expect_reason("Classification", {**classification, "unexpected": True}, "contract.unknown_field")


def test_protected_cross_object_bundles_validate_digest_bindings():
    objects = _release_objects()

    parse_contract(
        "ReleaseCandidateProvenanceBundle",
        {
            "schemaVersion": 1,
            "releaseCandidateLock": objects["releaseCandidateLock"],
            "provenanceApprovalRecord": objects["provenanceApprovalRecord"],
        },
    )


def test_public_release_bundle_rejects_candidate_freeze_for_other_candidate_or_provenance():
    objects = _release_objects()

    other_candidate_approval = copy.deepcopy(objects["candidateFreezeApprovalRecord"])
    other_candidate_approval["boundDigests"]["candidateDigest"] = "sha256:" + "0" * 64
    other_candidate_approval = _production_sign(other_candidate_approval)
    public_approval = copy.deepcopy(objects["publicReleaseApprovalRecord"])
    public_approval["boundDigests"]["candidateFreezeApprovalDigest"] = _digest(
        "ApprovalRecord", other_candidate_approval
    )
    public_approval = _production_sign(public_approval)
    with pytest.raises(ContractValidationError) as excinfo:
        parse_contract(
            "PublicReleaseApprovalBundle",
            {
                "schemaVersion": 1,
                "packageArchiveRecord": objects["packageArchiveRecord"],
                "releaseGateDecision": objects["releaseGateDecision"],
                "provenanceApprovalRecord": objects["provenanceApprovalRecord"],
                "candidateFreezeApprovalRecord": other_candidate_approval,
                "approvalRecord": public_approval,
            },
        )
    assert excinfo.value.reason_code == "contract.binding_mismatch"

    other_provenance_approval = copy.deepcopy(objects["candidateFreezeApprovalRecord"])
    other_provenance_approval["boundDigests"]["provenanceApprovalDigest"] = "sha256:" + "1" * 64
    other_provenance_approval = _production_sign(other_provenance_approval)
    public_approval = copy.deepcopy(objects["publicReleaseApprovalRecord"])
    public_approval["boundDigests"]["candidateFreezeApprovalDigest"] = _digest(
        "ApprovalRecord", other_provenance_approval
    )
    public_approval = _production_sign(public_approval)
    with pytest.raises(ContractValidationError) as excinfo:
        parse_contract(
            "PublicReleaseApprovalBundle",
            {
                "schemaVersion": 1,
                "packageArchiveRecord": objects["packageArchiveRecord"],
                "releaseGateDecision": objects["releaseGateDecision"],
                "provenanceApprovalRecord": objects["provenanceApprovalRecord"],
                "candidateFreezeApprovalRecord": other_provenance_approval,
                "approvalRecord": public_approval,
            },
        )
    assert excinfo.value.reason_code == "contract.binding_mismatch"


def test_release_gate_requires_exact_target_models_and_complete_public_criteria():
    missing_criterion = _case_value("ReleaseGateDecision")
    missing_criterion["perModelDecisions"]["gemini-3.7-flash-high"]["criterionResults"].pop("SC-013")
    expect_reason("ReleaseGateDecision", missing_criterion, "contract.binding_mismatch")

    wrong_model_keys = _case_value("ReleaseGateDecision")
    renamed = wrong_model_keys["perModelDecisions"].pop("gemini-3.1-pro-high")
    renamed["modelRequest"] = "gemini-4-pro"
    wrong_model_keys["perModelDecisions"]["gemini-4-pro"] = renamed
    expect_reason("ReleaseGateDecision", wrong_model_keys, "contract.binding_mismatch")


def test_release_gate_blocking_criteria_match_failed_public_criteria():
    decision = _case_value("ReleaseGateDecision")
    model_decision = decision["perModelDecisions"][TARGET_MODELS[0]]
    model_decision["criterionResults"]["SC-013"]["result"] = "fail"
    model_decision["criterionResults"]["SC-013"]["reasonCode"] = "below_margin"
    model_decision["decision"] = "fail"
    model_decision["blockingCriteria"] = ["SC-003"]
    decision["overallDecision"] = "fail"
    decision["blockingCriteria"] = [TARGET_MODELS[0] + "/SC-003"]
    expect_reason("ReleaseGateDecision", decision, "contract.binding_mismatch")


def test_target_model_slugs_match_quickstart_release_targets():
    decision = _case_value("ReleaseGateDecision")
    first = decision["perModelDecisions"].pop("gemini-3.7-flash-high")
    second = decision["perModelDecisions"].pop("gemini-3.1-pro-high")
    first["modelRequest"] = TARGET_MODELS[0]
    second["modelRequest"] = TARGET_MODELS[1]
    decision["perModelDecisions"] = {
        TARGET_MODELS[0]: first,
        TARGET_MODELS[1]: second,
    }
    parse_contract("ReleaseGateDecision", decision)

    candidate = _case_value("ReleaseCandidateLock")
    candidate["conditionLockDigests"] = {
        TARGET_MODELS[0] + "/bare": "sha256:" + "1" * 64,
        TARGET_MODELS[0] + "/full": "sha256:" + "2" * 64,
        TARGET_MODELS[1] + "/bare": "sha256:" + "3" * 64,
        TARGET_MODELS[1] + "/full": "sha256:" + "4" * 64,
    }
    parse_contract("ReleaseCandidateLock", candidate)


def test_production_approval_bundles_reject_fixture_signatures():
    objects = _release_objects()

    fixture_candidate_approval = copy.deepcopy(objects["candidateFreezeApprovalRecord"])
    fixture_candidate_approval["signature"]["mechanism"] = "fixture_signature"
    fixture_candidate_approval = _sign(fixture_candidate_approval)
    expect_reason(
        "CandidateFreezeApprovalBundle",
        {
            "schemaVersion": 1,
            "releaseCandidateLock": objects["releaseCandidateLock"],
            "provenanceApprovalRecord": objects["provenanceApprovalRecord"],
            "approvalRecord": fixture_candidate_approval,
        },
        "contract.binding_mismatch",
    )

    fixture_public_approval = copy.deepcopy(objects["publicReleaseApprovalRecord"])
    fixture_public_approval["signature"]["mechanism"] = "fixture_signature"
    fixture_public_approval = _sign(fixture_public_approval)
    expect_reason(
        "PublicReleaseApprovalBundle",
        {
            "schemaVersion": 1,
            "packageArchiveRecord": objects["packageArchiveRecord"],
            "releaseGateDecision": objects["releaseGateDecision"],
            "provenanceApprovalRecord": objects["provenanceApprovalRecord"],
            "candidateFreezeApprovalRecord": objects["candidateFreezeApprovalRecord"],
            "approvalRecord": fixture_public_approval,
        },
        "contract.binding_mismatch",
    )


def test_condition_pair_uses_authoritative_reasoning_request_and_treatment_only_difference():
    old_reasoning_pointer = _case_value("ConditionPairLock")
    old_reasoning_pointer["requiredEqualFields"] = [
        "/reasoningConfigurationDigest" if pointer == "/reasoningRequest" else pointer
        for pointer in old_reasoning_pointer["requiredEqualFields"]
    ]
    expect_reason("ConditionPairLock", old_reasoning_pointer, "contract.binding_mismatch")

    hidden_difference = _case_value("ConditionPairLock")
    hidden_difference["allowedDifferences"] = ["/enabledComponents", "/hiddenChecks"]
    expect_reason("ConditionPairLock", hidden_difference, "contract.binding_mismatch")


def test_release_candidate_requires_exact_condition_lock_keys():
    missing_condition = _case_value("ReleaseCandidateLock")
    missing_condition["conditionLockDigests"].pop("gemini-3.1-pro-high/full")
    expect_reason("ReleaseCandidateLock", missing_condition, "contract.binding_mismatch")

    extra_condition = _case_value("ReleaseCandidateLock")
    extra_condition["conditionLockDigests"]["gemini-3.1-pro-high/pooled"] = "sha256:" + "0" * 64
    expect_reason("ReleaseCandidateLock", extra_condition, "contract.binding_mismatch")


def test_block_spec_condition_ids_and_pair_digest_are_consistent():
    single_condition = _case_value("BlockSpec")
    single_condition["conditionIds"] = ["bare"]
    single_condition["conditionPairLockDigest"] = "not_applicable"
    parse_contract("BlockSpec", single_condition)

    matched_pair = _case_value("BlockSpec")
    matched_pair["conditionIds"] = ["bare", "full"]
    parse_contract("BlockSpec", matched_pair)

    too_many_conditions = _case_value("BlockSpec")
    too_many_conditions["conditionIds"] = ["bare", "full", "hidden"]
    too_many_conditions["conditionPairLockDigest"] = "not_applicable"
    _expect_evaluation_schema_rejects(too_many_conditions)
    expect_reason("BlockSpec", too_many_conditions, "contract.binding_mismatch")

    missing_pair_lock = _case_value("BlockSpec")
    missing_pair_lock["conditionPairLockDigest"] = "not_applicable"
    _expect_evaluation_schema_rejects(missing_pair_lock)
    expect_reason("BlockSpec", missing_pair_lock, "contract.binding_mismatch")

    stray_pair_lock = _case_value("BlockSpec")
    stray_pair_lock["conditionIds"] = ["bare"]
    _expect_evaluation_schema_rejects(stray_pair_lock)
    expect_reason("BlockSpec", stray_pair_lock, "contract.binding_mismatch")


def test_precision_power_lock_requires_target_model_samples_and_release_honesty_floor():
    release_lock = _case_value("PrecisionPowerLock")
    parse_contract("PrecisionPowerLock", release_lock)

    low_honesty_floor = _case_value("PrecisionPowerLock")
    low_honesty_floor["honestyNegativeVariantMinimumPerModelFullCondition"] = 1
    _expect_evaluation_schema_rejects(low_honesty_floor)
    expect_reason("PrecisionPowerLock", low_honesty_floor, "contract.binding_mismatch")

    unknown_model = _case_value("PrecisionPowerLock")
    unknown_model["perModelSampleSizes"] = {
        "not-a-target-model": unknown_model["perModelSampleSizes"][TARGET_MODELS[0]]
    }
    _expect_evaluation_schema_rejects(unknown_model)
    expect_reason("PrecisionPowerLock", unknown_model, "contract.binding_mismatch")

    missing_model = _case_value("PrecisionPowerLock")
    missing_model["perModelSampleSizes"].pop(TARGET_MODELS[1])
    _expect_evaluation_schema_rejects(missing_model)
    expect_reason("PrecisionPowerLock", missing_model, "contract.binding_mismatch")


def test_staged_attempt_outcome_bundle_binds_unclassified_input_digest():
    unclassified = _case_value("UnclassifiedStagedAttemptOutcome")
    staged = _case_value("StagedAttemptOutcome")
    staged["unclassifiedOutcomeDigest"] = _digest("UnclassifiedStagedAttemptOutcome", unclassified)
    parse_contract(
        "StagedAttemptOutcomeBundle",
        {
            "schemaVersion": 1,
            "unclassifiedOutcome": unclassified,
            "stagedOutcome": staged,
        },
    )

    tampered = copy.deepcopy(staged)
    tampered["unclassifiedOutcomeDigest"] = "sha256:" + "0" * 64
    expect_reason(
        "StagedAttemptOutcomeBundle",
        {
            "schemaVersion": 1,
            "unclassifiedOutcome": unclassified,
            "stagedOutcome": tampered,
        },
        "contract.binding_mismatch",
    )


def test_approval_bound_digest_maps_are_order_insensitive():
    objects = _release_objects()
    reordered = copy.deepcopy(objects["candidateFreezeApprovalRecord"])
    reordered["boundDigests"] = dict(reversed(list(reordered["boundDigests"].items())))
    reordered = _production_sign(reordered)
    parse_contract(
        "CandidateFreezeApprovalBundle",
        {
            "schemaVersion": 1,
            "releaseCandidateLock": objects["releaseCandidateLock"],
            "provenanceApprovalRecord": objects["provenanceApprovalRecord"],
            "approvalRecord": reordered,
        },
    )
    parse_contract(
        "CandidateFreezeApprovalBundle",
        {
            "schemaVersion": 1,
            "releaseCandidateLock": objects["releaseCandidateLock"],
            "provenanceApprovalRecord": objects["provenanceApprovalRecord"],
            "approvalRecord": objects["candidateFreezeApprovalRecord"],
        },
    )
    parse_contract(
        "PreparedScheduleBundle",
        {
            "schemaVersion": 1,
            "releaseCandidateLock": objects["releaseCandidateLock"],
            "preparedSchedule": objects["preparedSchedule"],
        },
    )
    parse_contract(
        "SealedOpeningBundle",
        {
            "schemaVersion": 1,
            "releaseCandidateLock": objects["releaseCandidateLock"],
            "approvalRecord": objects["candidateFreezeApprovalRecord"],
            "preparedSchedule": objects["preparedSchedule"],
            "sealedOpeningJournal": objects["sealedOpeningJournal"],
        },
    )
    parse_contract(
        "ReleaseGateBundle",
        {
            "schemaVersion": 1,
            "releaseCandidateLock": objects["releaseCandidateLock"],
            "releaseGateDecision": objects["releaseGateDecision"],
        },
    )
    parse_contract(
        "PublicReleaseApprovalBundle",
        {
            "schemaVersion": 1,
            "packageArchiveRecord": objects["packageArchiveRecord"],
            "releaseGateDecision": objects["releaseGateDecision"],
            "provenanceApprovalRecord": objects["provenanceApprovalRecord"],
            "candidateFreezeApprovalRecord": objects["candidateFreezeApprovalRecord"],
            "approvalRecord": objects["publicReleaseApprovalRecord"],
        },
    )
    parse_contract(
        "PublicationBundle",
        {
            "schemaVersion": 1,
            "packageArchiveRecord": objects["packageArchiveRecord"],
            "releaseGateDecision": objects["releaseGateDecision"],
            "approvalRecord": objects["publicReleaseApprovalRecord"],
            "publicationRecord": objects["publicationRecord"],
        },
    )


@pytest.mark.parametrize(
    ("name", "kind", "mutate"),
    [
        (
            "candidateBundleTamperedProvenanceDigest",
            "ReleaseCandidateProvenanceBundle",
            lambda objects: {
                "schemaVersion": 1,
                "releaseCandidateLock": {**objects["releaseCandidateLock"], "provenanceApprovalDigest": "sha256:0000000000000000000000000000000000000000000000000000000000000000"},
                "provenanceApprovalRecord": objects["provenanceApprovalRecord"],
            },
        ),
        (
            "candidateFreezeMissingBoundApproval",
            "CandidateFreezeApprovalBundle",
            lambda objects: {
                "schemaVersion": 1,
                "releaseCandidateLock": objects["releaseCandidateLock"],
                "provenanceApprovalRecord": objects["provenanceApprovalRecord"],
                "approvalRecord": {**objects["candidateFreezeApprovalRecord"], "boundDigests": {"candidateDigest": objects["candidateFreezeApprovalRecord"]["boundDigests"]["candidateDigest"]}},
            },
        ),
        (
            "preparedScheduleTamperedCandidateDigest",
            "PreparedScheduleBundle",
            lambda objects: {
                "schemaVersion": 1,
                "releaseCandidateLock": objects["releaseCandidateLock"],
                "preparedSchedule": {**objects["preparedSchedule"], "candidateDigest": "sha256:0000000000000000000000000000000000000000000000000000000000000000"},
            },
        ),
        (
            "sealedJournalMissingApproval",
            "SealedOpeningBundle",
            lambda objects: {
                "schemaVersion": 1,
                "releaseCandidateLock": objects["releaseCandidateLock"],
                "approvalRecord": {**objects["candidateFreezeApprovalRecord"], "decision": "rejected"},
                "preparedSchedule": objects["preparedSchedule"],
                "sealedOpeningJournal": objects["sealedOpeningJournal"],
            },
        ),
        (
            "releaseGateTamperedCandidateDigest",
            "ReleaseGateBundle",
            lambda objects: {
                "schemaVersion": 1,
                "releaseCandidateLock": objects["releaseCandidateLock"],
                "releaseGateDecision": {**objects["releaseGateDecision"], "candidateDigest": "sha256:0000000000000000000000000000000000000000000000000000000000000000"},
            },
        ),
        (
            "publicReleaseMissingCandidateApproval",
            "PublicReleaseApprovalBundle",
            lambda objects: {
                "schemaVersion": 1,
                "packageArchiveRecord": objects["packageArchiveRecord"],
                "releaseGateDecision": objects["releaseGateDecision"],
                "provenanceApprovalRecord": objects["provenanceApprovalRecord"],
                "candidateFreezeApprovalRecord": {**objects["candidateFreezeApprovalRecord"], "decision": "rejected"},
                "approvalRecord": objects["publicReleaseApprovalRecord"],
            },
        ),
        (
            "publicationTamperedArchiveDigest",
            "PublicationBundle",
            lambda objects: {
                "schemaVersion": 1,
                "packageArchiveRecord": objects["packageArchiveRecord"],
                "releaseGateDecision": objects["releaseGateDecision"],
                "approvalRecord": objects["publicReleaseApprovalRecord"],
                "publicationRecord": {**objects["publicationRecord"], "archiveDigest": "sha256:0000000000000000000000000000000000000000000000000000000000000000"},
            },
        ),
        (
            "publicationUsesFailingDecision",
            "PublicationBundle",
            lambda objects: {
                "schemaVersion": 1,
                "packageArchiveRecord": objects["packageArchiveRecord"],
                "releaseGateDecision": {**objects["releaseGateDecision"], "overallDecision": "fail", "blockingCriteria": ["gemini-3.7-flash-high/SC-001"]},
                "approvalRecord": objects["publicReleaseApprovalRecord"],
                "publicationRecord": objects["publicationRecord"],
            },
        ),
    ],
    ids=lambda case: case if isinstance(case, str) else None,
)
def test_tampered_digest_or_missing_bound_approval_fails_with_stable_code(name, kind, mutate):
    objects = _release_objects()
    with pytest.raises(ContractValidationError) as excinfo:
        parse_contract(kind, mutate(objects))
    assert excinfo.value.reason_code == "contract.binding_mismatch"


def test_signature_payload_binding_is_required_but_not_self_issued():
    approval = _sign(_case_value("ApprovalRecordCandidateFreeze"))
    approval["signature"]["signedPayloadDigest"] = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    expect_reason("ApprovalRecord", approval, "contract.binding_mismatch")

    provenance = _sign(_case_value("ProvenanceApprovalRecord"))
    provenance["signature"]["signedPayloadDigest"] = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    expect_reason("ProvenanceApprovalRecord", provenance, "contract.binding_mismatch")


def test_parser_owned_invariants_not_expressible_in_json_schema():
    pair = _case_value("ConditionPairLock")
    pair["requiredEqualFields"].remove("/modelRequest")
    expect_reason("ConditionPairLock", pair, "contract.binding_mismatch")

    pre_worker = _case_value("RunRecordPreWorker")
    pre_worker["attemptQualification"]["validStartAt"] = "2026-08-18T12:10:00Z"
    expect_reason("RunRecord", pre_worker, "contract.binding_mismatch")

    decision = _case_value("ReleaseGateDecision")
    decision["blockingCriteria"] = ["gemini-3.7-flash-high/SC-001"]
    expect_reason("ReleaseGateDecision", decision, "contract.binding_mismatch")

    worker = _case_value("WorkerInvocation")
    worker["attemptId"] = "attempt-should-not-be-worker-visible"
    expect_reason("WorkerInvocation", worker, "contract.unknown_field")
