from __future__ import annotations

import copy
import json
import stat
from pathlib import Path

import pytest

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import ContractValidationError, canonical_contract_digest, parse_contract
from abe_eval.evidence import import_run
from abe_eval.grade import append_grade
from test_evidence_store import _case_value, _digest, _read_lifecycle, _stage_classified_attempt, _write_lifecycle


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


def _grade_path(root: Path, run: dict[str, object], grade: dict[str, object]) -> Path:
    return root / "runs" / str(run["runId"]) / "grades" / str(grade["graderDigest"]).removeprefix("sha256:") / "grade.json"


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
    grade_path = _grade_path(tmp_path, run, grade)
    assert stat.S_IMODE(grade_path.stat().st_mode) & stat.S_IWUSR == 0
    assert json.loads(grade_path.read_bytes()) == grade
    assert run_path.read_bytes() == run_bytes_before
    assert canonical_contract_digest("RunRecord", json.loads(run_bytes_before)) == run_digest_before
    assert (tmp_path / str(run["rawEvidenceLocator"])).read_bytes() == raw_manifest_before
    assert attempt_path.read_bytes() == attempt_bytes_before
    assert lifecycle_path.read_bytes() == lifecycle_bytes_before


def test_append_grade_rejects_mutable_run_json_even_when_contents_match(tmp_path):
    run, _attempt, run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    run_path.chmod(0o600)
    grade = _grade(str(run["runId"]), "ef")

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), grade, tmp_path)

    assert excinfo.value.reason_code == "grade.run_record_mutable"
    assert excinfo.value.path == "$.runId"
    assert not _grade_path(tmp_path, run, grade).exists()


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


def test_repeated_grader_digest_cannot_recreate_missing_grade_slot(tmp_path):
    run, _attempt, _run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    first = _grade(str(run["runId"]), "cb")
    append_grade(str(run["runId"]), first, tmp_path)
    first_path = _grade_path(tmp_path, run, first)
    first_path.chmod(0o600)
    first_path.unlink()
    replacement = copy.deepcopy(first)
    replacement["outcome"] = "fail"

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), replacement, tmp_path)

    assert excinfo.value.reason_code == "grade.grader_digest_already_exists"
    assert not first_path.exists()


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


def test_append_grade_rejects_symlinked_run_directory_without_writing_outside_root(tmp_path):
    run, _attempt, run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    run_dir = run_path.parent
    outside_run_dir = tmp_path.with_name(tmp_path.name + "-outside-run")
    run_dir.rename(outside_run_dir)
    run_dir.symlink_to(outside_run_dir, target_is_directory=True)
    grade = _grade(str(run["runId"]), "ab")

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), grade, tmp_path)

    assert excinfo.value.reason_code == "grade.run_missing"
    assert not (outside_run_dir / "grades").exists()


def test_append_grade_rejects_run_directory_with_mismatched_run_record(tmp_path):
    run, _attempt, _run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    other_run_id = "other-run"
    other_run_dir = tmp_path / "runs" / other_run_id
    other_run_dir.mkdir()
    (other_run_dir / "run.json").write_bytes(canonical_bytes(run) + b"\n")
    (other_run_dir / "run.json").chmod(0o400)
    grade = _grade(other_run_id, "ef")

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(other_run_id, grade, tmp_path)

    assert excinfo.value.reason_code == "grade.run_record_mismatch"
    assert not (other_run_dir / "grades").exists()


def test_append_grade_rejects_tampered_run_json_that_no_longer_matches_finalization_event(tmp_path):
    run, _attempt, run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    tampered = copy.deepcopy(run)
    tampered["redactedEvidenceLocator"] = "tampered-after-finalization"
    run_path.chmod(0o600)
    run_path.write_bytes(canonical_bytes(parse_contract("RunRecord", tampered)) + b"\n")
    run_path.chmod(0o400)
    grade = _grade(str(run["runId"]), "ef")

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), grade, tmp_path)

    assert excinfo.value.reason_code == "grade.run_finalization_digest_mismatch"
    assert not (tmp_path / "runs" / str(run["runId"]) / "grades").exists()


def test_append_grade_rejects_self_consistent_run_json_and_finalization_tamper(tmp_path):
    run, attempt, run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    tampered = copy.deepcopy(run)
    tampered["conditionDigest"] = _digest("99")
    tampered = parse_contract("RunRecord", tampered)
    run_path.chmod(0o600)
    run_path.write_bytes(canonical_bytes(tampered) + b"\n")
    run_path.chmod(0o400)
    events = _read_lifecycle(tmp_path, str(attempt["attemptId"]))
    events[-1]["evidenceDigest"] = canonical_contract_digest("RunRecord", tampered)
    _write_lifecycle(tmp_path, str(attempt["attemptId"]), events)
    grade = _grade(str(run["runId"]), "ef")

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), grade, tmp_path)

    assert excinfo.value.reason_code == "grade.run_finalization_digest_mismatch"
    assert excinfo.value.path == "$.runId"
    assert not _grade_path(tmp_path, run, grade).exists()


def test_append_grade_rejects_lifecycle_finalization_attempt_id_tamper(tmp_path):
    run, attempt, _run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    events = _read_lifecycle(tmp_path, str(attempt["attemptId"]))
    events[-1]["attemptId"] = "other-attempt"
    _write_lifecycle(tmp_path, str(attempt["attemptId"]), events)
    grade = _grade(str(run["runId"]), "ef")

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), grade, tmp_path)

    assert excinfo.value.reason_code == "grade.run_finalization_digest_mismatch"
    assert excinfo.value.path == "$.lifecycleEventDigests[4].attemptId"
    assert not (tmp_path / "runs" / str(run["runId"]) / "grades").exists()


def test_append_grade_rejects_lifecycle_finalization_time_tamper(tmp_path):
    run, attempt, _run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    events = _read_lifecycle(tmp_path, str(attempt["attemptId"]))
    events[-1]["occurredAt"] = "2026-08-18T13:13:13Z"
    _write_lifecycle(tmp_path, str(attempt["attemptId"]), events)
    grade = _grade(str(run["runId"]), "ef")

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), grade, tmp_path)

    assert excinfo.value.reason_code == "grade.run_finalization_digest_mismatch"
    assert excinfo.value.path == "$.lifecycleEventDigests[4].occurredAt"
    assert not (tmp_path / "runs" / str(run["runId"]) / "grades").exists()


def test_append_grade_rejects_tampered_raw_manifest(tmp_path):
    run, _attempt, _run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    raw_manifest_path = tmp_path / str(run["rawEvidenceLocator"])
    raw_manifest_path.chmod(0o600)
    raw_manifest_path.write_bytes(b"{}\n")
    grade = _grade(str(run["runId"]), "ef")

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), grade, tmp_path)

    assert excinfo.value.reason_code == "grade.raw_evidence_digest_mismatch"
    assert excinfo.value.path == "$.rawEvidenceLocator"
    assert not _grade_path(tmp_path, run, grade).exists()


def test_append_grade_rejects_symlinked_raw_artifact_directory(tmp_path):
    run, _attempt, run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    artifacts_dir = run_path.parent / "artifacts"
    outside_artifacts_dir = tmp_path.with_name(tmp_path.name + "-outside-artifacts")
    artifacts_dir.rename(outside_artifacts_dir)
    artifacts_dir.symlink_to(outside_artifacts_dir, target_is_directory=True)
    grade = _grade(str(run["runId"]), "ef")

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), grade, tmp_path)

    assert excinfo.value.reason_code == "grade.unsafe_identifier_path"
    assert excinfo.value.path == "$.rawEvidenceLocator"
    assert not _grade_path(tmp_path, run, grade).exists()


def test_append_grade_rejects_tampered_raw_content_object(tmp_path):
    run, _attempt, _run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    raw_manifest = json.loads((tmp_path / str(run["rawEvidenceLocator"])).read_bytes())
    entry_index, entry = next((index, entry) for index, entry in enumerate(raw_manifest["entries"]) if entry["present"])
    object_path = tmp_path / str(entry["objectLocator"])
    object_path.chmod(0o600)
    object_path.write_text("tampered raw object\n")
    assert sha256_digest(object_path.read_bytes()) != entry["digest"]
    grade = _grade(str(run["runId"]), "ef")

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), grade, tmp_path)

    assert excinfo.value.reason_code == "grade.raw_evidence_digest_mismatch"
    assert excinfo.value.path == f"$.rawEvidenceLocator.entries[{entry_index}].digest"
    assert not _grade_path(tmp_path, run, grade).exists()
