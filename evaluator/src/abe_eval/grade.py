"""Append-only immutable grader records for finalized evaluator runs."""

from __future__ import annotations

import errno
import json
import os
import uuid
from pathlib import Path

from abe_eval.canonical import canonical_bytes
from abe_eval.contracts import ContractValidationError, canonical_contract_digest, parse_contract


def _fail(reason_code: str, path: str = "$") -> None:
    raise ContractValidationError(reason_code, path)


def _safe_identifier(value: object, path: str, reason_code: str) -> str:
    text = str(value)
    if not text or text in {".", ".."} or "/" in text or "\\" in text or "\x00" in text:
        _fail(reason_code, path)
    return text


def _safe_digest_segment(value: str, path: str) -> str:
    prefix = "sha256:"
    if not value.startswith(prefix):
        _fail("grade.invalid_grader_digest", path)
    hex_digest = value.removeprefix(prefix)
    if len(hex_digest) != 64 or any(character not in "0123456789abcdef" for character in hex_digest):
        _fail("grade.invalid_grader_digest", path)
    return hex_digest


def _ensure_plain_dir(path: Path, reason_code: str, error_path: str) -> None:
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_dir():
            _fail(reason_code, error_path)
        return
    try:
        path.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        if path.is_symlink() or not path.is_dir():
            _fail(reason_code, error_path)


def _temporary_sibling(path: Path) -> Path:
    return path.with_name(path.name + ".tmp." + str(os.getpid()) + "." + uuid.uuid4().hex)


def _write_grade_exclusive(path: Path, grade: dict[str, object]) -> None:
    data = canonical_bytes(grade) + b"\n"
    tmp_path = _temporary_sibling(path)
    try:
        with tmp_path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(tmp_path, path)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            _fail("grade.grader_digest_already_exists", "$.graderDigest")
        raise
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def _read_lifecycle(root: Path, attempt_id: str) -> list[dict[str, object]]:
    path = root / "attempts" / attempt_id / "lifecycle.ndjson"
    if path.is_symlink() or not path.is_file():
        _fail("grade.run_finalization_missing", "$.runId")
    events: list[dict[str, object]] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line:
            continue
        try:
            events.append(parse_contract("AttemptLifecycleEvent", json.loads(line)))
        except (json.JSONDecodeError, ContractValidationError):
            _fail("grade.invalid_lifecycle", "$.lifecycleEventDigests[" + str(index) + "]")
    return events


def _validate_run_finalization_digest(root: Path, run: dict[str, object]) -> None:
    attempt_id = _safe_identifier(run["attemptId"], "$.attemptId", "grade.unsafe_identifier_path")
    finalized = [event for event in _read_lifecycle(root, attempt_id) if event["phase"] == "run_finalized"]
    if len(finalized) != 1:
        _fail("grade.run_finalization_missing", "$.runId")
    if finalized[0]["evidenceDigest"] != canonical_contract_digest("RunRecord", run):
        _fail("grade.run_finalization_digest_mismatch", "$.runId")


def append_grade(run_id: str, grade: object, root: Path) -> str:
    """Append one grader's immutable GradeRecord under a finalized run."""

    parsed_grade = parse_contract("GradeRecord", grade)
    safe_run_id = _safe_identifier(run_id, "$.runId", "grade.unsafe_identifier_path")
    if parsed_grade["runId"] != safe_run_id:
        _fail("grade.run_id_mismatch", "$.runId")
    root = Path(root)
    run_dir = root / "runs" / safe_run_id
    run_json = run_dir / "run.json"
    if run_json.is_symlink() or not run_json.is_file():
        _fail("grade.run_missing", "$.runId")
    parsed_run = parse_contract("RunRecord", json.loads(run_json.read_text(encoding="utf-8")))
    if parsed_run["runId"] != safe_run_id:
        _fail("grade.run_record_mismatch", "$.runId")
    _validate_run_finalization_digest(root, parsed_run)

    grade_segment = _safe_digest_segment(str(parsed_grade["graderDigest"]), "$.graderDigest")
    grades_dir = run_dir / "grades"
    grader_dir = grades_dir / grade_segment
    _ensure_plain_dir(grades_dir, "grade.grade_store_invalid", "$.grades")
    _ensure_plain_dir(grader_dir, "grade.grader_digest_already_exists", "$.graderDigest")
    grade_path = grader_dir / "grade.json"
    if grade_path.exists() or grade_path.is_symlink():
        _fail("grade.grader_digest_already_exists", "$.graderDigest")
    _write_grade_exclusive(grade_path, parsed_grade)
    return canonical_contract_digest("GradeRecord", parsed_grade)


__all__ = ["append_grade"]
