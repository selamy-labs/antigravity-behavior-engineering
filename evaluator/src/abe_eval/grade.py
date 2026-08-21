"""Append-only immutable grader records for finalized evaluator runs."""

from __future__ import annotations

import errno
import json
import os
import stat
import uuid
from pathlib import Path

from abe_eval.canonical import canonical_bytes, sha256_digest
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


def _resolve_relative_locator(root: Path, value: object, path: str) -> Path:
    text = str(value)
    candidate = Path(text)
    if (
        not text
        or candidate.is_absolute()
        or "\\" in text
        or "\x00" in text
        or any(part in {"", ".", ".."} for part in candidate.parts)
    ):
        _fail("grade.unsafe_identifier_path", path)
    return root / candidate


def _ensure_not_owner_writable(path: Path, error_path: str, reason_code: str = "grade.raw_evidence_mutable") -> None:
    if stat.S_IMODE(path.stat().st_mode) & stat.S_IWUSR:
        _fail(reason_code, error_path)


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
        path.chmod(0o400)
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
    events = _read_lifecycle(root, attempt_id)
    if not events:
        _fail("grade.run_finalization_missing", "$.runId")
    for index, event in enumerate(events):
        event_path = "$.lifecycleEventDigests[" + str(index) + "]"
        if event["attemptId"] != attempt_id:
            _fail("grade.run_finalization_digest_mismatch", event_path + ".attemptId")
        if event["sequence"] != index:
            _fail("grade.run_finalization_digest_mismatch", event_path + ".sequence")
    finalized_indices = [index for index, event in enumerate(events) if event["phase"] == "run_finalized"]
    if finalized_indices != [len(events) - 1]:
        _fail("grade.run_finalization_missing", "$.runId")
    finalized = events[-1]
    if len(events) < 2 or events[-2]["phase"] != "execution_terminal":
        _fail("grade.run_finalization_digest_mismatch", "$.lifecycleEventDigests")
    if finalized["terminalKind"] != "none":
        _fail("grade.run_finalization_digest_mismatch", "$.lifecycleEventDigests[" + str(len(events) - 1) + "].terminalKind")
    if finalized["occurredAt"] != run["processState"]["endedAt"]:
        _fail("grade.run_finalization_digest_mismatch", "$.lifecycleEventDigests[" + str(len(events) - 1) + "].occurredAt")
    if finalized["evidenceDigest"] != canonical_contract_digest("RunRecord", run):
        _fail("grade.run_finalization_digest_mismatch", "$.runId")


def _validate_run_digest_anchor(run_dir: Path, run: dict[str, object]) -> None:
    digest_path = run_dir / "run.digest"
    if digest_path.is_symlink() or not digest_path.is_file():
        _fail("grade.run_finalization_digest_mismatch", "$.runId")
    _ensure_not_owner_writable(digest_path, "$.runId", "grade.run_record_mutable")
    try:
        stored_digest = digest_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        _fail("grade.run_finalization_digest_mismatch", "$.runId")
    if stored_digest != canonical_contract_digest("RunRecord", run) + "\n":
        _fail("grade.run_finalization_digest_mismatch", "$.runId")


def _validate_raw_evidence(root: Path, run: dict[str, object]) -> None:
    manifest_path = _resolve_relative_locator(root, run["rawEvidenceLocator"], "$.rawEvidenceLocator")
    if manifest_path.is_symlink() or not manifest_path.is_file():
        _fail("grade.raw_evidence_missing", "$.rawEvidenceLocator")
    manifest_bytes = manifest_path.read_bytes()
    if sha256_digest(manifest_bytes) != run["artifactManifestDigest"]:
        _fail("grade.raw_evidence_digest_mismatch", "$.rawEvidenceLocator")
    _ensure_not_owner_writable(manifest_path, "$.rawEvidenceLocator")
    try:
        manifest = json.loads(manifest_bytes)
    except json.JSONDecodeError:
        _fail("grade.raw_evidence_digest_mismatch", "$.rawEvidenceLocator")
    if not isinstance(manifest, dict):
        _fail("grade.raw_evidence_digest_mismatch", "$.rawEvidenceLocator")
    if manifest.get("runId") != run["runId"] or manifest.get("attemptId") != run["attemptId"]:
        _fail("grade.raw_evidence_digest_mismatch", "$.rawEvidenceLocator")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        _fail("grade.raw_evidence_digest_mismatch", "$.rawEvidenceLocator.entries")
    for index, entry in enumerate(entries):
        entry_path = "$.rawEvidenceLocator.entries[" + str(index) + "]"
        if not isinstance(entry, dict):
            _fail("grade.raw_evidence_digest_mismatch", entry_path)
        if not entry.get("present"):
            if entry.get("digest") != "none" or entry.get("byteLength") != 0:
                _fail("grade.raw_evidence_digest_mismatch", entry_path)
            continue
        object_path = _resolve_relative_locator(root, entry.get("objectLocator"), entry_path + ".objectLocator")
        if object_path.is_symlink() or not object_path.is_file():
            _fail("grade.raw_evidence_missing", entry_path + ".objectLocator")
        data = object_path.read_bytes()
        if sha256_digest(data) != entry.get("digest") or len(data) != entry.get("byteLength"):
            _fail("grade.raw_evidence_digest_mismatch", entry_path + ".digest")
        _ensure_not_owner_writable(object_path, entry_path + ".objectLocator")


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
    _ensure_not_owner_writable(run_json, "$.runId", "grade.run_record_mutable")
    parsed_run = parse_contract("RunRecord", json.loads(run_json.read_text(encoding="utf-8")))
    if parsed_run["runId"] != safe_run_id:
        _fail("grade.run_record_mismatch", "$.runId")
    _validate_run_digest_anchor(run_dir, parsed_run)
    _validate_run_finalization_digest(root, parsed_run)
    _validate_raw_evidence(root, parsed_run)

    grade_segment = _safe_digest_segment(str(parsed_grade["graderDigest"]), "$.graderDigest")
    grades_dir = run_dir / "grades"
    grader_dir = grades_dir / grade_segment
    _ensure_plain_dir(grades_dir, "grade.grade_store_invalid", "$.grades")
    try:
        grader_dir.mkdir(mode=0o700, exist_ok=False)
    except FileExistsError:
        _fail("grade.grader_digest_already_exists", "$.graderDigest")
    grade_path = grader_dir / "grade.json"
    if grade_path.exists() or grade_path.is_symlink():
        _fail("grade.grader_digest_already_exists", "$.graderDigest")
    _write_grade_exclusive(grade_path, parsed_grade)
    return canonical_contract_digest("GradeRecord", parsed_grade)


__all__ = ["append_grade"]
