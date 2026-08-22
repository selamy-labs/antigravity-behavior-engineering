from __future__ import annotations

import copy
import json
from pathlib import Path

from abe_eval.blind import blind_run
from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import canonical_contract_digest, parse_contract
from abe_eval.grade import append_grade
from abe_eval.redact import redact_run
from test_immutable_regrading import _finalized_run, _grade


def _json_text(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _assert_no_canary(value: object, canaries: list[str]) -> None:
    rendered = _json_text(value)
    for canary in canaries:
        assert canary not in rendered


def _finalized_run_with_grade(tmp_path: Path) -> tuple[dict[str, object], Path, str, bytes, bytes]:
    run, _attempt, run_path, raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    grade = _grade(str(run["runId"]), "cb")
    grade_digest = append_grade(str(run["runId"]), grade, tmp_path)
    return run, run_path, grade_digest, run_path.read_bytes(), raw_manifest_before


def test_blind_projection_normalizes_model_and_condition_canaries_but_retains_audit_digests(tmp_path):
    run, _run_path, grade_digest, _run_bytes_before, _raw_manifest_before = _finalized_run_with_grade(tmp_path)
    canary_run = copy.deepcopy(run)
    model_canary = "gemini-3.7-flash-high"
    served_identity_canary = "CREDENTIAL_CANARY_T009"
    private_path_canary = "/workspace/private/t009"
    canary_run["observedModel"]["requestedModel"] = model_canary
    canary_run["observedModel"]["servedIdentityEvidence"][0]["value"] = served_identity_canary
    canary_run["rawEvidenceLocator"] = private_path_canary
    canary_run = parse_contract("RunRecord", canary_run)
    policy = {
        "schemaVersion": 1,
        "policyId": "blind-policy-t009",
        "randomizationSeedDigest": "sha256:" + "91" * 32,
        "normalizationVersion": "t009-v1",
        "gradeDigests": [grade_digest],
    }

    projection = blind_run(canary_run, policy)

    assert projection["schemaVersion"] == 1
    assert projection["publicRunId"].startswith("blind-run-")
    assert projection["blindConditionId"].startswith("condition-")
    assert projection["blindModelId"].startswith("model-")
    assert projection["auditDigests"] == {
        "runRecordDigest": canonical_contract_digest("RunRecord", canary_run),
        "rawEvidenceDigest": canary_run["artifactManifestDigest"],
        "transcriptDigest": canary_run["transcriptDigest"],
        "eventStreamDigest": canary_run["eventStreamDigest"],
    }
    assert projection["classification"] == canary_run["classification"]
    assert projection["gradeDigests"] == [grade_digest]
    _assert_no_canary(projection, [model_canary, served_identity_canary, private_path_canary, str(canary_run["conditionDigest"])])


def test_redaction_writes_separate_publishable_tree_with_dispositions_and_preserves_protected_bytes(tmp_path):
    run, run_path, grade_digest, run_bytes_before, raw_manifest_before = _finalized_run_with_grade(tmp_path)
    public_root = tmp_path / "public-redacted"
    canaries = [
        str(run["rawEvidenceLocator"]),
        str(run["observedModel"]["requestedModel"]),
        str(run["conditionDigest"]),
        "CREDENTIAL_CANARY_T009",
    ]
    policy = {
        "schemaVersion": 1,
        "policyId": "redaction-policy-t009",
        "publicRoot": str(public_root),
        "scenarioFamilyId": "family-alpha",
        "publicConfigurationDigest": "sha256:" + "a7" * 32,
        "gradeDigests": [grade_digest],
        "canaries": canaries,
    }

    redacted = redact_run(run, policy)

    parse_contract("RedactedRun", redacted)
    assert redacted["publicRunId"].startswith("public-run-")
    assert redacted["publicRunId"] != run["runId"]
    assert redacted["scenarioFamilyId"] == "family-alpha"
    assert redacted["gradeDigests"] == [grade_digest]
    _assert_no_canary(redacted, canaries)
    public_run_dir = public_root / "runs" / str(redacted["publicRunId"])
    redacted_path = public_run_dir / "run.json"
    manifest_path = public_run_dir / "artifacts" / "artifact-manifest.json"
    report_path = public_root / "reports" / "redaction-policy-t009" / (str(redacted["publicRunId"]) + "-redaction-report.json")
    assert json.loads(redacted_path.read_text(encoding="utf-8")) == redacted
    report = json.loads(report_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert redacted["redactionReportDigest"] == sha256_digest(canonical_bytes(report))
    assert redacted["artifactManifestDigest"] == sha256_digest(canonical_bytes(manifest))
    assert report["sourceRunDigest"] == canonical_contract_digest("RunRecord", run)
    assert report["protectedMappingDigest"] == sha256_digest(
        canonical_bytes({"publicRunId": redacted["publicRunId"], "rawRunId": run["runId"]})
    )
    assert set(report["fieldDispositions"]) == set(run)
    assert report["fieldDispositions"] == {
        "agentDeclaredState": "kept",
        "artifactManifestDigest": "transformed",
        "attemptId": "withheld",
        "attemptQualification": "transformed",
        "classification": "kept",
        "conditionDigest": "withheld",
        "consumption": "kept",
        "environmentQualificationDigest": "transformed",
        "eventStreamDigest": "transformed",
        "infrastructureValidity": "kept",
        "inputPermissionState": "kept",
        "observedModel": "withheld",
        "processState": "kept",
        "rawEvidenceLocator": "withheld",
        "redactedEvidenceLocator": "transformed",
        "runId": "transformed",
        "scenarioDigest": "transformed",
        "schemaVersion": "kept",
        "transcriptDigest": "transformed",
    }
    assert manifest["entries"] == [
        {
            "digest": redacted["redactionReportDigest"],
            "mediaType": "application/json",
            "path": "reports/redaction-policy-t009/" + str(redacted["publicRunId"]) + "-redaction-report.json",
            "redactionDisposition": "kept",
        }
    ]
    for path in [redacted_path, manifest_path, report_path]:
        _assert_no_canary(path.read_text(encoding="utf-8"), canaries)
    assert run_path.read_bytes() == run_bytes_before
    assert (tmp_path / str(run["rawEvidenceLocator"])).read_bytes() == raw_manifest_before
