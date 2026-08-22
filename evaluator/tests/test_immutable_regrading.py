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


def _owner_writable(path: Path) -> bool:
    return bool(stat.S_IMODE(path.stat().st_mode) & stat.S_IWUSR)


def _open_artifact_store_for_tamper(run_path: Path) -> None:
    artifacts = run_path.parent / "artifacts"
    artifacts.chmod(0o700)
    (artifacts / "sha256").chmod(0o700)


def _close_artifact_store_after_tamper(run_path: Path) -> None:
    artifacts = run_path.parent / "artifacts"
    (artifacts / "sha256").chmod(0o500)
    artifacts.chmod(0o500)


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
    grades_dir = grade_path.parent.parent
    ledger_path = run_path.parent / "grade-ledger.ndjson"
    assert not _owner_writable(grades_dir)
    assert not _owner_writable(ledger_path)
    assert stat.S_IMODE(grade_path.parent.stat().st_mode) & stat.S_IWUSR == 0
    assert stat.S_IMODE(grade_path.stat().st_mode) & stat.S_IWUSR == 0
    assert json.loads(grade_path.read_bytes()) == grade
    with pytest.raises(PermissionError):
        grade_path.unlink()
    assert grade_path.exists()
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


def test_append_grade_rejects_mutable_raw_artifact_directory(tmp_path):
    run, _attempt, run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    (run_path.parent / "artifacts" / "sha256").chmod(0o700)
    grade = _grade(str(run["runId"]), "ef")

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), grade, tmp_path)

    assert excinfo.value.reason_code == "grade.raw_evidence_mutable"
    assert excinfo.value.path == "$.rawEvidenceLocator.artifacts.sha256"
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
    first_path.parent.chmod(0o700)
    first_path.chmod(0o600)
    first_path.unlink()
    replacement = copy.deepcopy(first)
    replacement["outcome"] = "fail"

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), replacement, tmp_path)

    assert excinfo.value.reason_code == "grade.grade_store_invalid"
    assert not first_path.exists()


def test_repeated_grader_digest_cannot_recreate_removed_grade_directory(tmp_path):
    run, _attempt, _run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    first = _grade(str(run["runId"]), "cb")
    append_grade(str(run["runId"]), first, tmp_path)
    first_path = _grade_path(tmp_path, run, first)
    first_path.parent.chmod(0o700)
    first_path.chmod(0o600)
    first_path.unlink()
    first_path.parent.parent.chmod(0o700)
    first_path.parent.rmdir()
    first_path.parent.parent.chmod(0o500)
    replacement = copy.deepcopy(first)
    replacement["outcome"] = "fail"

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), replacement, tmp_path)

    assert excinfo.value.reason_code == "grade.grade_store_invalid"
    assert not first_path.exists()


def test_repeated_grader_digest_cannot_be_replaced_without_chmod_of_grade_store(tmp_path):
    run, _attempt, run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    first = _grade(str(run["runId"]), "cb")
    append_grade(str(run["runId"]), first, tmp_path)
    first_path = _grade_path(tmp_path, run, first)
    original_grade_bytes = first_path.read_bytes()
    moved_grade_dir = tmp_path / "moved-grade-dir"
    replacement = copy.deepcopy(first)
    replacement["outcome"] = "fail"

    with pytest.raises(PermissionError):
        first_path.parent.rename(moved_grade_dir)
    with pytest.raises(PermissionError):
        (run_path.parent / "grade-ledger.ndjson").write_bytes(b"")
    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), replacement, tmp_path)

    assert excinfo.value.reason_code == "grade.grader_digest_already_exists"
    assert first_path.read_bytes() == original_grade_bytes
    assert not moved_grade_dir.exists()


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
    run_dir.chmod(0o700)
    run_dir.rename(outside_run_dir)
    run_dir.symlink_to(outside_run_dir, target_is_directory=True)
    grade = _grade(str(run["runId"]), "ab")

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), grade, tmp_path)

    assert excinfo.value.reason_code == "grade.run_missing"
    assert not (
        outside_run_dir / "grades" / str(grade["graderDigest"]).removeprefix("sha256:") / "grade.json"
    ).exists()


def test_append_grade_rejects_run_directory_with_mismatched_run_record(tmp_path):
    run, _attempt, _run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    other_run_id = "other-run"
    other_run_dir = tmp_path / "runs" / other_run_id
    other_run_dir.mkdir()
    (other_run_dir / "run.json").write_bytes(canonical_bytes(run) + b"\n")
    (other_run_dir / "run.json").chmod(0o400)
    other_run_dir.chmod(0o500)
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
    assert not _grade_path(tmp_path, run, grade).exists()


def test_append_grade_rejects_self_consistent_run_json_and_finalization_tamper(tmp_path):
    run, attempt, run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    tampered = copy.deepcopy(run)
    tampered["conditionDigest"] = _digest("99")
    tampered = parse_contract("RunRecord", tampered)
    run_path.chmod(0o600)
    run_path.write_bytes(canonical_bytes(tampered) + b"\n")
    run_path.chmod(0o400)
    (run_path.parent / "run.digest").chmod(0o600)
    (run_path.parent / "run.digest").write_text(canonical_contract_digest("RunRecord", tampered) + "\n")
    (run_path.parent / "run.digest").chmod(0o400)
    events = _read_lifecycle(tmp_path, str(attempt["attemptId"]))
    events[-1]["evidenceDigest"] = canonical_contract_digest("RunRecord", tampered)
    _write_lifecycle(tmp_path, str(attempt["attemptId"]), events)
    grade = _grade(str(run["runId"]), "ef")

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), grade, tmp_path)

    assert excinfo.value.reason_code == "grade.raw_evidence_digest_mismatch"
    assert excinfo.value.path == "$.rawEvidenceLocator.conditionDigest"
    assert not _grade_path(tmp_path, run, grade).exists()


def test_append_grade_rejects_self_consistent_run_manifest_digest_lifecycle_tamper(tmp_path):
    run, attempt, run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    raw_manifest_path = tmp_path / str(run["rawEvidenceLocator"])
    raw_manifest = json.loads(raw_manifest_path.read_bytes())
    tampered = copy.deepcopy(run)
    tampered["conditionDigest"] = _digest("99")
    raw_manifest["runRecordBinding"]["conditionDigest"] = tampered["conditionDigest"]
    new_manifest_bytes = canonical_bytes(raw_manifest)
    new_manifest_digest = sha256_digest(new_manifest_bytes)
    new_manifest_locator = "runs/" + str(run["runId"]) + "/artifacts/sha256/" + new_manifest_digest.removeprefix("sha256:")
    _open_artifact_store_for_tamper(run_path)
    new_manifest_path = tmp_path / new_manifest_locator
    new_manifest_path.write_bytes(new_manifest_bytes)
    new_manifest_path.chmod(0o400)
    _close_artifact_store_after_tamper(run_path)
    tampered["artifactManifestDigest"] = new_manifest_digest
    tampered["rawEvidenceLocator"] = new_manifest_locator
    tampered = parse_contract("RunRecord", tampered)
    run_path.chmod(0o600)
    run_path.write_bytes(canonical_bytes(tampered) + b"\n")
    run_path.chmod(0o400)
    (run_path.parent / "run.digest").chmod(0o600)
    (run_path.parent / "run.digest").write_text(canonical_contract_digest("RunRecord", tampered) + "\n")
    (run_path.parent / "run.digest").chmod(0o400)
    events = _read_lifecycle(tmp_path, str(attempt["attemptId"]))
    events[-1]["evidenceDigest"] = canonical_contract_digest("RunRecord", tampered)
    _write_lifecycle(tmp_path, str(attempt["attemptId"]), events)
    grade = _grade(str(run["runId"]), "ef")

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), grade, tmp_path)

    assert excinfo.value.reason_code == "grade.raw_evidence_digest_mismatch"
    assert excinfo.value.path == "$.rawEvidenceLocator.conditionDigest"
    assert not _grade_path(tmp_path, run, grade).exists()


def test_append_grade_rejects_staged_outcome_artifact_tamper_even_when_raw_manifest_and_run_agree(tmp_path):
    run, attempt, run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    raw_manifest_path = tmp_path / str(run["rawEvidenceLocator"])
    raw_manifest = json.loads(raw_manifest_path.read_bytes())
    staged = json.loads((tmp_path / str(raw_manifest["stagedOutcomeLocator"])).read_bytes())
    tampered_agent_state = "completed-after-rewrite"
    staged["agentDeclaredState"] = tampered_agent_state
    staged = parse_contract("StagedAttemptOutcome", staged)
    staged_bytes = canonical_bytes(staged)
    staged_digest = canonical_contract_digest("StagedAttemptOutcome", staged)
    staged_locator = "runs/" + str(run["runId"]) + "/artifacts/sha256/" + staged_digest.removeprefix("sha256:")
    _open_artifact_store_for_tamper(run_path)
    staged_path = tmp_path / staged_locator
    staged_path.write_bytes(staged_bytes)
    staged_path.chmod(0o400)
    raw_manifest["stagedOutcomeDigest"] = staged_digest
    raw_manifest["stagedOutcomeLocator"] = staged_locator
    raw_manifest["runRecordBinding"]["agentDeclaredState"] = tampered_agent_state
    new_manifest_bytes = canonical_bytes(raw_manifest)
    new_manifest_digest = sha256_digest(new_manifest_bytes)
    new_manifest_locator = "runs/" + str(run["runId"]) + "/artifacts/sha256/" + new_manifest_digest.removeprefix("sha256:")
    new_manifest_path = tmp_path / new_manifest_locator
    new_manifest_path.write_bytes(new_manifest_bytes)
    new_manifest_path.chmod(0o400)
    _close_artifact_store_after_tamper(run_path)
    tampered = copy.deepcopy(run)
    tampered["agentDeclaredState"] = tampered_agent_state
    tampered["artifactManifestDigest"] = new_manifest_digest
    tampered["rawEvidenceLocator"] = new_manifest_locator
    tampered = parse_contract("RunRecord", tampered)
    run_path.chmod(0o600)
    run_path.write_bytes(canonical_bytes(tampered) + b"\n")
    run_path.chmod(0o400)
    (run_path.parent / "run.digest").chmod(0o600)
    (run_path.parent / "run.digest").write_text(canonical_contract_digest("RunRecord", tampered) + "\n")
    (run_path.parent / "run.digest").chmod(0o400)
    events = _read_lifecycle(tmp_path, str(attempt["attemptId"]))
    events[-1]["evidenceDigest"] = canonical_contract_digest("RunRecord", tampered)
    _write_lifecycle(tmp_path, str(attempt["attemptId"]), events)
    grade = _grade(str(run["runId"]), "ef")

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), grade, tmp_path)

    assert excinfo.value.reason_code == "grade.run_finalization_digest_mismatch"
    assert excinfo.value.path == "$.lifecycleEventDigests[3].evidenceDigest"
    assert not _grade_path(tmp_path, run, grade).exists()


def test_append_grade_removes_grade_slot_when_grade_chmod_fails(tmp_path, monkeypatch):
    run, _attempt, _run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    grade = _grade(str(run["runId"]), "ab")
    grade_path = _grade_path(tmp_path, run, grade)
    original_chmod = Path.chmod

    def fail_grade_chmod(self, mode, *args, **kwargs):
        if Path(self) == grade_path:
            raise OSError(5, "simulated grade chmod failure")
        return original_chmod(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "chmod", fail_grade_chmod)

    with pytest.raises(OSError):
        append_grade(str(run["runId"]), grade, tmp_path)

    assert not grade_path.exists()
    assert not grade_path.parent.exists()


def test_append_grade_truncates_partial_ledger_append_before_cleanup(tmp_path, monkeypatch):
    run, _attempt, _run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    failed = _grade(str(run["runId"]), "ab")
    failed_grade_path = _grade_path(tmp_path, run, failed)
    ledger_path = tmp_path / "runs" / str(run["runId"]) / "grade-ledger.ndjson"
    original_open = Path.open
    should_fail = True

    class PartialLedgerAppend:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, exc_type, exc, traceback):
            return self.stream.__exit__(exc_type, exc, traceback)

        def write(self, data):
            self.stream.write(data[:1])
            self.stream.flush()
            raise OSError(5, "simulated partial ledger append")

        def __getattr__(self, name):
            return getattr(self.stream, name)

    def partial_ledger_open(self, *args, **kwargs):
        nonlocal should_fail
        stream = original_open(self, *args, **kwargs)
        mode = args[0] if args else kwargs.get("mode", "r")
        if should_fail and Path(self) == ledger_path and mode == "ab":
            should_fail = False
            return PartialLedgerAppend(stream)
        return stream

    monkeypatch.setattr(Path, "open", partial_ledger_open)

    with pytest.raises(OSError):
        append_grade(str(run["runId"]), failed, tmp_path)

    assert ledger_path.read_bytes() == b""
    assert not failed_grade_path.exists()
    assert not failed_grade_path.parent.exists()
    replacement = _grade(str(run["runId"]), "de")

    grade_digest = append_grade(str(run["runId"]), replacement, tmp_path)

    assert grade_digest == canonical_contract_digest("GradeRecord", replacement)
    assert _grade_path(tmp_path, run, replacement).exists()


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
    assert not _grade_path(tmp_path, run, grade).exists()


def test_append_grade_rejects_prior_lifecycle_event_tamper(tmp_path):
    run, attempt, _run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    events = _read_lifecycle(tmp_path, str(attempt["attemptId"]))
    events[0]["evidenceDigest"] = _digest("77")
    _write_lifecycle(tmp_path, str(attempt["attemptId"]), events)
    grade = _grade(str(run["runId"]), "ef")

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), grade, tmp_path)

    assert excinfo.value.reason_code == "grade.run_finalization_digest_mismatch"
    assert excinfo.value.path == "$.lifecycleEventDigests"
    assert not _grade_path(tmp_path, run, grade).exists()


def test_append_grade_rejects_self_consistent_prior_lifecycle_event_tamper(tmp_path):
    run, attempt, run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    run_dir = run_path.parent
    raw_manifest = json.loads((tmp_path / str(run["rawEvidenceLocator"])).read_bytes())
    staged = json.loads((tmp_path / str(raw_manifest["stagedOutcomeLocator"])).read_bytes())
    unclassified = json.loads((tmp_path / str(raw_manifest["unclassifiedOutcomeLocator"])).read_bytes())
    events = _read_lifecycle(tmp_path, str(attempt["attemptId"]))
    events[1]["evidenceDigest"] = _digest("42")
    lifecycle_digests = [canonical_contract_digest("AttemptLifecycleEvent", event) for event in events[:-1]]
    staged["lifecycleEventDigests"] = lifecycle_digests
    unclassified["lifecycleEventDigests"] = lifecycle_digests
    staged = parse_contract("StagedAttemptOutcome", staged)
    unclassified = parse_contract("UnclassifiedStagedAttemptOutcome", unclassified)
    run_dir.chmod(0o700)
    (run_dir / "artifacts").chmod(0o700)
    (run_dir / "artifacts" / "sha256").chmod(0o700)
    staged_bytes = canonical_bytes(staged)
    staged_digest = canonical_contract_digest("StagedAttemptOutcome", staged)
    staged_locator = "runs/" + str(run["runId"]) + "/artifacts/sha256/" + staged_digest.removeprefix("sha256:")
    (tmp_path / staged_locator).write_bytes(staged_bytes)
    (tmp_path / staged_locator).chmod(0o400)
    unclassified_bytes = canonical_bytes(unclassified)
    unclassified_digest = canonical_contract_digest("UnclassifiedStagedAttemptOutcome", unclassified)
    unclassified_locator = "runs/" + str(run["runId"]) + "/artifacts/sha256/" + unclassified_digest.removeprefix("sha256:")
    (tmp_path / unclassified_locator).write_bytes(unclassified_bytes)
    (tmp_path / unclassified_locator).chmod(0o400)
    raw_manifest["lifecycleEventDigests"] = lifecycle_digests
    raw_manifest["stagedOutcomeDigest"] = staged_digest
    raw_manifest["stagedOutcomeLocator"] = staged_locator
    raw_manifest["unclassifiedOutcomeDigest"] = unclassified_digest
    raw_manifest["unclassifiedOutcomeLocator"] = unclassified_locator
    raw_manifest_bytes = canonical_bytes(raw_manifest)
    raw_manifest_digest = sha256_digest(raw_manifest_bytes)
    raw_manifest_locator = "runs/" + str(run["runId"]) + "/artifacts/sha256/" + raw_manifest_digest.removeprefix("sha256:")
    (tmp_path / raw_manifest_locator).write_bytes(raw_manifest_bytes)
    (tmp_path / raw_manifest_locator).chmod(0o400)
    _close_artifact_store_after_tamper(run_path)
    tampered = copy.deepcopy(run)
    tampered["artifactManifestDigest"] = raw_manifest_digest
    tampered["rawEvidenceLocator"] = raw_manifest_locator
    tampered = parse_contract("RunRecord", tampered)
    run_path.chmod(0o600)
    run_path.write_bytes(canonical_bytes(tampered) + b"\n")
    run_path.chmod(0o400)
    (run_dir / "run.digest").chmod(0o600)
    (run_dir / "run.digest").write_text(canonical_contract_digest("RunRecord", tampered) + "\n")
    (run_dir / "run.digest").chmod(0o400)
    events[-1]["evidenceDigest"] = canonical_contract_digest("RunRecord", tampered)
    _write_lifecycle(tmp_path, str(attempt["attemptId"]), events)
    run_dir.chmod(0o500)
    grade = _grade(str(run["runId"]), "ef")

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), grade, tmp_path)

    assert excinfo.value.reason_code == "grade.run_finalization_digest_mismatch"
    assert excinfo.value.path == "$.lifecycleEventDigests[1].evidenceDigest"
    assert not _grade_path(tmp_path, run, grade).exists()


def test_append_grade_rejects_attempt_json_tamper(tmp_path):
    run, attempt, _run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    attempt_path = tmp_path / "attempts" / str(attempt["attemptId"]) / "attempt.json"
    tampered_attempt = copy.deepcopy(attempt)
    tampered_attempt["scheduledAt"] = "2026-08-18T13:13:13Z"
    attempt_path.write_bytes(canonical_bytes(parse_contract("ScheduledAttempt", tampered_attempt)) + b"\n")
    grade = _grade(str(run["runId"]), "ef")

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), grade, tmp_path)

    assert excinfo.value.reason_code == "grade.run_finalization_digest_mismatch"
    assert excinfo.value.path == "$.attemptId"
    assert not _grade_path(tmp_path, run, grade).exists()


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
    assert not _grade_path(tmp_path, run, grade).exists()


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


def test_append_grade_rejects_raw_manifest_locator_digest_segment_mismatch(tmp_path):
    run, attempt, run_path, _raw_manifest_before, _run_digest = _finalized_run(tmp_path)
    raw_manifest_path = tmp_path / str(run["rawEvidenceLocator"])
    wrong_locator = "runs/" + str(run["runId"]) + "/artifacts/sha256/" + ("0" * 64)
    wrong_path = tmp_path / wrong_locator
    _open_artifact_store_for_tamper(run_path)
    wrong_path.write_bytes(raw_manifest_path.read_bytes())
    wrong_path.chmod(0o400)
    _close_artifact_store_after_tamper(run_path)
    tampered = copy.deepcopy(run)
    tampered["rawEvidenceLocator"] = wrong_locator
    tampered = parse_contract("RunRecord", tampered)
    run_path.chmod(0o600)
    run_path.write_bytes(canonical_bytes(tampered) + b"\n")
    run_path.chmod(0o400)
    (run_path.parent / "run.digest").chmod(0o600)
    (run_path.parent / "run.digest").write_text(canonical_contract_digest("RunRecord", tampered) + "\n")
    (run_path.parent / "run.digest").chmod(0o400)
    events = _read_lifecycle(tmp_path, str(attempt["attemptId"]))
    events[-1]["evidenceDigest"] = canonical_contract_digest("RunRecord", tampered)
    _write_lifecycle(tmp_path, str(attempt["attemptId"]), events)
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
    run_path.parent.chmod(0o700)
    artifacts_dir.chmod(0o700)
    artifacts_dir.rename(outside_artifacts_dir)
    artifacts_dir.symlink_to(outside_artifacts_dir, target_is_directory=True)
    run_path.parent.chmod(0o500)
    grade = _grade(str(run["runId"]), "ef")

    with pytest.raises(ContractValidationError) as excinfo:
        append_grade(str(run["runId"]), grade, tmp_path)

    assert excinfo.value.reason_code == "grade.unsafe_identifier_path"
    assert excinfo.value.path == "$.rawEvidenceLocator.artifacts"
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
