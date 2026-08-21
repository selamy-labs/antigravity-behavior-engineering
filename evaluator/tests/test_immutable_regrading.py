from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from abe_eval.canonical import canonical_bytes
from abe_eval.contracts import ContractValidationError, canonical_contract_digest, parse_contract
from abe_eval.evidence import import_run
from abe_eval.grade import append_grade
from test_evidence_store import _case_value, _stage_classified_attempt


def _grade(run_id: str, grader_seed: str = "cb") -> dict[str, object]:
    grade = _case_value("GradeRecord")
    grade["runId"] = run_id
    grade["gradeId"] = "grade-" + grader_seed
    grade["graderDigest"] = "sha256:" + (grader_seed * 64)[:64]
    grade["deterministicChecks"][0]["evidenceDigest"] = "sha256:" + ((grader_seed + "a") * 64)[:64]
    grade["diagnostics"]["sourceDigest"] = "sha256:" + ((grader_seed + "b") * 64)[:64]
    return parse_contract("GradeRecord", grade)


def _finalized_run(tmp_path: Path) -> tuple[dict[str, object], dict[str, object], Path, bytes, str]:
    staging, attempt, condition, scenario, environment, _staged = _stage_classified_attempt(tmp_path)
    run = import_run(staging, attempt, condition, scenario, environment, tmp_path)
    run_path = tmp_path / "runs" / str(run["runId"]) / "run.json"
    raw_manifest_path = tmp_path / str(run["rawEvidenceLocator"])
    raw_manifest_before = raw_manifest_path.read_bytes()
    return run, attempt, run_path, raw_manifest_before, canonical_contract_digest("RunRecord", run)


def test_append_grade_is_append_only_by_grader_digest_and_keeps_run_immutable(tmp_path):
    run, _attempt, run_path, raw_manifest_before, run_digest_before = _finalized_run(tmp_path)
    attempt_path = tmp_path / "attempts" / str(run["attemptId"]) / "attempt.json"
    lifecycle_path = tmp_path / "attempts" / str(run["attemptId"]) / "lifecycle.ndjson"
    attempt_bytes_before = attempt_path.read_bytes()
    lifecycle_bytes_before = lifecycle_path.read_bytes()
    run_bytes_before = run_path.read_bytes()
    grade = _grade(str(run["runId"]), "cb")

    grade_digest = append_grade(str(run["runId"]), grade, tmp_path)

    assert grade_digest == canonical_contract_digest("GradeRecord", grade)
    grade_path = tmp_path / "runs" / str(run["runId"]) / "grades" / grade["graderDigest"].removeprefix("sha256:") / "grade.json"
    assert json.loads(grade_path.read_bytes()) == grade
    assert run_path.read_bytes() == run_bytes_before
    assert canonical_contract_digest("RunRecord", json.loads(run_bytes_before)) == run_digest_before
    assert (tmp_path / str(run["rawEvidenceLocator"])).read_bytes() == raw_manifest_before
    assert attempt_path.read_bytes() == attempt_bytes_before
    assert lifecycle_path.read_bytes() == lifecycle_bytes_before


def test_repeated_grader_digest_cannot_replace_existing_grade(tmp_path):
    run, _attempt, run_path, raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    first = _grade(str(run["runId"]), "cb")
    append_grade(str(run["runId"]), first, tmp_path)
    original_grade_bytes = (
        tmp_path / "runs" / str(run["runId"]) / "grades" / first["graderDigest"].removeprefix("sha256:") / "grade.json"
    ).read_bytes()
    replacement = copy.deepcopy(first)
    replacement["outcome"] = "fail"

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), replacement, tmp_path)

    assert excinfo.value.reason_code == "grade.grader_digest_already_exists"
    assert run_path.exists()
    assert (tmp_path / str(run["rawEvidenceLocator"])).read_bytes() == raw_manifest_before
    assert (
        tmp_path / "runs" / str(run["runId"]) / "grades" / first["graderDigest"].removeprefix("sha256:") / "grade.json"
    ).read_bytes() == original_grade_bytes


def test_second_grader_appends_without_mutating_first_grade_or_raw_evidence(tmp_path):
    run, _attempt, run_path, raw_manifest_before, run_digest_before = _finalized_run(tmp_path)
    attempt_path = tmp_path / "attempts" / str(run["attemptId"]) / "attempt.json"
    lifecycle_path = tmp_path / "attempts" / str(run["attemptId"]) / "lifecycle.ndjson"
    attempt_bytes_before = attempt_path.read_bytes()
    lifecycle_bytes_before = lifecycle_path.read_bytes()
    first = _grade(str(run["runId"]), "cb")
    second = _grade(str(run["runId"]), "de")
    first_digest = append_grade(str(run["runId"]), first, tmp_path)
    first_path = tmp_path / "runs" / str(run["runId"]) / "grades" / first["graderDigest"].removeprefix("sha256:") / "grade.json"
    first_bytes = first_path.read_bytes()

    second_digest = append_grade(str(run["runId"]), second, tmp_path)

    assert second_digest == canonical_contract_digest("GradeRecord", second)
    assert second_digest != first_digest
    assert first_path.read_bytes() == first_bytes
    assert canonical_contract_digest("RunRecord", json.loads(run_path.read_bytes())) == run_digest_before
    assert (tmp_path / str(run["rawEvidenceLocator"])).read_bytes() == raw_manifest_before
    assert attempt_path.read_bytes() == attempt_bytes_before
    assert lifecycle_path.read_bytes() == lifecycle_bytes_before


def test_append_grade_rejects_run_id_mismatch_and_missing_run(tmp_path):
    run, _attempt, _run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    mismatched = _grade("other-run", "cb")

    with pytest.raises(ContractValidationError) as mismatch:
        append_grade(str(run["runId"]), mismatched, tmp_path)
    assert mismatch.value.reason_code == "grade.run_id_mismatch"

    missing = _grade("missing-run", "de")
    with pytest.raises(ContractValidationError) as missing_exc:
        append_grade("missing-run", missing, tmp_path)
    assert missing_exc.value.reason_code == "grade.run_missing"
