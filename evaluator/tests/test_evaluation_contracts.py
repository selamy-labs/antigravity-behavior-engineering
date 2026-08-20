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


def _fixtures():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _valid_cases_by_name():
    return {case["name"]: case for case in _fixtures()["validCases"]}


def _case_value(name):
    return copy.deepcopy(_valid_cases_by_name()[name]["value"])


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


def _digest(kind, value):
    return canonical_contract_digest(kind, value)


def _release_objects():
    provenance = _sign(_case_value("ProvenanceApprovalRecord"))
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
    candidate_approval = _sign(candidate_approval)
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
    public_approval = _sign(public_approval)
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
                "releaseGateDecision": {**objects["releaseGateDecision"], "overallDecision": "fail", "blockingCriteria": ["gemini-2.5-pro/SC-001"]},
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
    decision["blockingCriteria"] = ["gemini-2.5-pro/SC-001"]
    expect_reason("ReleaseGateDecision", decision, "contract.binding_mismatch")

    worker = _case_value("WorkerInvocation")
    worker["attemptId"] = "attempt-should-not-be-worker-visible"
    expect_reason("WorkerInvocation", worker, "contract.unknown_field")
