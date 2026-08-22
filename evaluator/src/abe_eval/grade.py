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
from abe_eval.runner import _worker_invocation

_RUN_RECORD_BINDING_FIELDS = (
    "conditionDigest",
    "scenarioDigest",
    "environmentQualificationDigest",
    "attemptQualification",
    "observedModel",
    "processState",
    "agentDeclaredState",
    "inputPermissionState",
    "infrastructureValidity",
    "transcriptDigest",
    "eventStreamDigest",
    "consumption",
    "classification",
    "redactedEvidenceLocator",
)
_STAGED_RUN_RECORD_BINDING_FIELDS = (
    "conditionDigest",
    "scenarioDigest",
    "environmentQualificationDigest",
    "attemptQualification",
    "observedModel",
    "processState",
    "agentDeclaredState",
    "inputPermissionState",
    "infrastructureValidity",
    "consumption",
    "classification",
)
_PREFLIGHT_FIELDS = (
    ("authentication", "authentication"),
    ("fixtureProvisioning", "fixtureProvisioning"),
    ("modelPreflight", "modelPreflight"),
    ("fallbackProbe", "fallbackProbe"),
    ("pluginComponentDiscovery", "pluginComponentDiscovery"),
    ("structuredCapturePreflight", "structuredCapturePreflight"),
    ("authorityToolInventory", "authorityToolInventory"),
)
_GRADE_STORE_REST_MODE = 0o500
_GRADE_STORE_WRITE_MODE = 0o700
_GRADE_LEDGER_REST_MODE = 0o400
_GRADE_LEDGER_WRITE_MODE = 0o600


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


def _relative_locator(value: object, path: str) -> Path:
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
    return candidate


def _ensure_plain_ancestors(root: Path, relative: Path, path: str) -> None:
    current = root
    for part in relative.parts[:-1]:
        current = current / part
        if current.is_symlink() or not current.is_dir():
            _fail("grade.unsafe_identifier_path", path)


def _resolve_run_artifact_locator(root: Path, run_id: str, value: object, path: str, expected_digest: object) -> Path:
    relative = _relative_locator(value, path)
    expected_prefix = ("runs", run_id, "artifacts", "sha256")
    if len(relative.parts) != 5 or relative.parts[:4] != expected_prefix:
        _fail("grade.unsafe_identifier_path", path)
    digest_segment = relative.parts[4]
    if len(digest_segment) != 64 or any(character not in "0123456789abcdef" for character in digest_segment):
        _fail("grade.unsafe_identifier_path", path)
    if not isinstance(expected_digest, str) or digest_segment != expected_digest.removeprefix("sha256:"):
        _fail("grade.raw_evidence_digest_mismatch", path)
    _ensure_plain_ancestors(root, relative, path)
    return root / relative


def _ensure_not_owner_writable(path: Path, error_path: str, reason_code: str = "grade.raw_evidence_mutable") -> None:
    if stat.S_IMODE(path.stat().st_mode) & stat.S_IWUSR:
        _fail(reason_code, error_path)


def _preflight_failures(qualification: dict[str, object]) -> list[tuple[str, str]]:
    failures: list[tuple[str, str]] = []
    for field, reason_code in _PREFLIGHT_FIELDS:
        result = qualification[field]
        if isinstance(result, dict) and result["result"] == "fail":
            failures.append((field, reason_code))
    return failures


def _failed_preflight(qualification: dict[str, object]) -> str:
    failures = _preflight_failures(qualification)
    if not failures:
        _fail("grade.run_finalization_digest_mismatch", "$.attemptQualification")
    return failures[0][1]


def _expected_terminal_kind(staged: dict[str, object]) -> str:
    process = staged["processState"]
    infrastructure = staged["infrastructureValidity"]
    if process["workerProcessState"] == "not_started":
        return "preflight_failed"
    if process["timeout"] or process["controllerExitCode"] == 124:
        return "product_timeout"
    if infrastructure == "adapter_failure":
        return "adapter_failure"
    if infrastructure in {"capture_malformed", "capture_truncated", "grader_leakage_detected", "test_flake"}:
        return "capture_indeterminate"
    return "agent_finished"


def _terminal_evidence_digest(staged: dict[str, object], staged_files: dict[str, str]) -> str:
    process = staged["processState"]
    if process["workerProcessState"] == "not_started":
        terminal_evidence = {"failedPreflight": _failed_preflight(staged["attemptQualification"])}
    else:
        terminal_evidence = {
            "terminalKind": _expected_terminal_kind(staged),
            "controllerExitCode": process["controllerExitCode"],
            "workerExitCode": process["workerExitCode"],
            "signal": process["signal"],
            "timeout": process["timeout"],
            "agentDeclaredState": staged["agentDeclaredState"],
            "inputPermissionState": staged["inputPermissionState"],
            "infrastructureValidity": staged["infrastructureValidity"],
            "consumption": staged["consumption"],
            "observedModel": staged["observedModel"],
            "stagedFiles": staged_files,
        }
    return sha256_digest(canonical_bytes(terminal_evidence))


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


def _ensure_existing_plain_dir(path: Path, reason_code: str, error_path: str) -> None:
    if path.is_symlink() or not path.is_dir():
        _fail(reason_code, error_path)


def _ensure_existing_plain_artifact_dir(path: Path, error_path: str) -> None:
    if path.is_symlink():
        _fail("grade.unsafe_identifier_path", error_path)
    if not path.is_dir():
        _fail("grade.raw_evidence_missing", error_path)


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
        try:
            path.chmod(0o400)
        except OSError:
            try:
                path.unlink()
            except OSError:
                pass
            raise
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            _fail("grade.grader_digest_already_exists", "$.graderDigest")
        raise
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def _ensure_existing_grade_store(run_dir: Path) -> tuple[Path, Path]:
    grades_dir = run_dir / "grades"
    ledger_path = run_dir / "grade-ledger.ndjson"
    _ensure_existing_plain_dir(grades_dir, "grade.grade_store_invalid", "$.grades")
    if ledger_path.is_symlink() or not ledger_path.is_file():
        _fail("grade.grade_store_invalid", "$.graderDigest")
    _ensure_not_owner_writable(grades_dir, "$.grades", "grade.grade_store_invalid")
    _ensure_not_owner_writable(ledger_path, "$.graderDigest", "grade.grade_store_invalid")
    return grades_dir, ledger_path


def _restore_grade_store_modes(grades_dir: Path, ledger_path: Path) -> OSError | None:
    restore_error = None
    if ledger_path.exists() and not ledger_path.is_symlink():
        try:
            ledger_path.chmod(_GRADE_LEDGER_REST_MODE)
        except OSError as exc:
            restore_error = restore_error or exc
    if grades_dir.exists() and not grades_dir.is_symlink():
        try:
            grades_dir.chmod(_GRADE_STORE_REST_MODE)
        except OSError as exc:
            restore_error = restore_error or exc
    return restore_error


def _read_json_file(path: Path, reason_code: str, error_path: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        _fail(reason_code, error_path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail(reason_code, error_path)
    if not isinstance(value, dict):
        _fail(reason_code, error_path)
    return value


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


def _validate_run_finalization_digest(
    root: Path,
    run: dict[str, object],
    manifest: dict[str, object],
    attempt: dict[str, object],
    condition: dict[str, object],
    scenario: dict[str, object],
    environment: dict[str, object],
    staged: dict[str, object],
    terminal_evidence_digest: str,
) -> None:
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
    expected_lifecycle_digests = manifest.get("lifecycleEventDigests")
    actual_lifecycle_digests = [canonical_contract_digest("AttemptLifecycleEvent", event) for event in events[:-1]]
    if expected_lifecycle_digests != actual_lifecycle_digests:
        _fail("grade.run_finalization_digest_mismatch", "$.lifecycleEventDigests")
    if events[0]["occurredAt"] != attempt["scheduledAt"]:
        _fail("grade.run_finalization_digest_mismatch", "$.lifecycleEventDigests[0].occurredAt")
    if events[0]["evidenceDigest"] != manifest.get("attemptDigest"):
        _fail("grade.run_finalization_digest_mismatch", "$.lifecycleEventDigests[0].evidenceDigest")
    expected_preflight_digest = sha256_digest(canonical_bytes({"condition": condition, "scenario": scenario}))
    if events[1]["evidenceDigest"] != expected_preflight_digest:
        _fail("grade.run_finalization_digest_mismatch", "$.lifecycleEventDigests[1].evidenceDigest")
    valid_start_at = str(staged["attemptQualification"]["validStartAt"])
    if valid_start_at != "none":
        valid_started = events[2]
        if valid_started["occurredAt"] != valid_start_at:
            _fail("grade.run_finalization_digest_mismatch", "$.lifecycleEventDigests[2].occurredAt")
        qualification_digest = canonical_contract_digest("EnvironmentQualificationRecord", environment)
        expected_valid_started_digest = sha256_digest(canonical_bytes(_worker_invocation(attempt, condition, scenario, qualification_digest)))
        if valid_started["evidenceDigest"] != expected_valid_started_digest:
            _fail("grade.run_finalization_digest_mismatch", "$.lifecycleEventDigests[2].evidenceDigest")
    finalized = events[-1]
    if len(events) < 2 or events[-2]["phase"] != "execution_terminal":
        _fail("grade.run_finalization_digest_mismatch", "$.lifecycleEventDigests")
    terminal_index = len(events) - 2
    if events[terminal_index]["terminalKind"] != _expected_terminal_kind(staged):
        _fail("grade.run_finalization_digest_mismatch", "$.lifecycleEventDigests[" + str(terminal_index) + "].terminalKind")
    if events[terminal_index]["evidenceDigest"] != terminal_evidence_digest:
        _fail("grade.run_finalization_digest_mismatch", "$.lifecycleEventDigests[" + str(terminal_index) + "].evidenceDigest")
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


def _validate_attempt_anchor(root: Path, manifest: dict[str, object], run: dict[str, object]) -> dict[str, object]:
    attempt_id = _safe_identifier(run["attemptId"], "$.attemptId", "grade.unsafe_identifier_path")
    attempt = parse_contract(
        "ScheduledAttempt",
        _read_json_file(root / "attempts" / attempt_id / "attempt.json", "grade.run_finalization_digest_mismatch", "$.attemptId"),
    )
    if attempt["runId"] != run["runId"] or canonical_contract_digest("ScheduledAttempt", attempt) != manifest.get("attemptDigest"):
        _fail("grade.run_finalization_digest_mismatch", "$.attemptId")
    return attempt


def _read_manifest_artifact(
    root: Path,
    run_id: str,
    manifest: dict[str, object],
    locator_field: str,
    digest_field: str,
    contract_name: str,
) -> dict[str, object]:
    locator_path = "$.rawEvidenceLocator." + locator_field
    digest = manifest.get(digest_field)
    artifact_path = _resolve_run_artifact_locator(root, run_id, manifest.get(locator_field), locator_path, digest)
    if artifact_path.is_symlink() or not artifact_path.is_file():
        _fail("grade.raw_evidence_missing", locator_path)
    artifact_bytes = artifact_path.read_bytes()
    if sha256_digest(artifact_bytes) != digest:
        _fail("grade.raw_evidence_digest_mismatch", locator_path)
    _ensure_not_owner_writable(artifact_path, locator_path)
    try:
        value = json.loads(artifact_bytes)
        return parse_contract(contract_name, value)
    except (json.JSONDecodeError, ContractValidationError):
        _fail("grade.raw_evidence_digest_mismatch", locator_path)


def _parse_controller_artifacts(
    root: Path, run_id: str, manifest: dict[str, object], run: dict[str, object]
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    if manifest.get("conditionDigest") != run["conditionDigest"]:
        _fail("grade.raw_evidence_digest_mismatch", "$.rawEvidenceLocator.conditionDigest")
    if manifest.get("scenarioDigest") != run["scenarioDigest"]:
        _fail("grade.raw_evidence_digest_mismatch", "$.rawEvidenceLocator.scenarioDigest")
    if manifest.get("environmentQualificationDigest") != run["environmentQualificationDigest"]:
        _fail("grade.raw_evidence_digest_mismatch", "$.rawEvidenceLocator.environmentQualificationDigest")
    condition = _read_manifest_artifact(root, run_id, manifest, "conditionLocator", "conditionDigest", "ConditionLock")
    scenario = _read_manifest_artifact(root, run_id, manifest, "scenarioLocator", "scenarioDigest", "ScenarioCard")
    environment = _read_manifest_artifact(
        root,
        run_id,
        manifest,
        "environmentQualificationLocator",
        "environmentQualificationDigest",
        "EnvironmentQualificationRecord",
    )
    return condition, scenario, environment


def _validate_run_record_binding(manifest: dict[str, object], run: dict[str, object], staged: dict[str, object]) -> None:
    binding = manifest.get("runRecordBinding")
    if not isinstance(binding, dict) or set(binding) != set(_RUN_RECORD_BINDING_FIELDS):
        _fail("grade.raw_evidence_digest_mismatch", "$.rawEvidenceLocator.runRecordBinding")
    for field in _RUN_RECORD_BINDING_FIELDS:
        if binding[field] != run[field]:
            _fail("grade.run_finalization_digest_mismatch", "$.runId")
    for field in _STAGED_RUN_RECORD_BINDING_FIELDS:
        if staged[field] != run[field] or staged[field] != binding[field]:
            _fail("grade.run_finalization_digest_mismatch", "$.runId")


def _validate_raw_evidence(
    root: Path, run: dict[str, object]
) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object], dict[str, object], str]:
    run_id = _safe_identifier(run["runId"], "$.runId", "grade.unsafe_identifier_path")
    artifacts_dir = root / "runs" / run_id / "artifacts"
    sha256_dir = artifacts_dir / "sha256"
    _ensure_existing_plain_artifact_dir(artifacts_dir, "$.rawEvidenceLocator.artifacts")
    _ensure_existing_plain_artifact_dir(sha256_dir, "$.rawEvidenceLocator.artifacts.sha256")
    _ensure_not_owner_writable(artifacts_dir, "$.rawEvidenceLocator.artifacts")
    _ensure_not_owner_writable(sha256_dir, "$.rawEvidenceLocator.artifacts.sha256")
    manifest_path = _resolve_run_artifact_locator(
        root, run_id, run["rawEvidenceLocator"], "$.rawEvidenceLocator", run["artifactManifestDigest"]
    )
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
    condition, scenario, environment = _parse_controller_artifacts(root, run_id, manifest, run)
    staged = _read_manifest_artifact(
        root, run_id, manifest, "stagedOutcomeLocator", "stagedOutcomeDigest", "StagedAttemptOutcome"
    )
    _read_manifest_artifact(
        root, run_id, manifest, "unclassifiedOutcomeLocator", "unclassifiedOutcomeDigest", "UnclassifiedStagedAttemptOutcome"
    )
    _validate_run_record_binding(manifest, run, staged)
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        _fail("grade.raw_evidence_digest_mismatch", "$.rawEvidenceLocator.entries")
    staged_files: dict[str, str] = {}
    for index, entry in enumerate(entries):
        entry_path = "$.rawEvidenceLocator.entries[" + str(index) + "]"
        if not isinstance(entry, dict):
            _fail("grade.raw_evidence_digest_mismatch", entry_path)
        if not entry.get("present"):
            if entry.get("digest") != "none" or entry.get("byteLength") != 0:
                _fail("grade.raw_evidence_digest_mismatch", entry_path)
            continue
        object_path = _resolve_run_artifact_locator(
            root, run_id, entry.get("objectLocator"), entry_path + ".objectLocator", entry.get("digest")
        )
        if object_path.is_symlink() or not object_path.is_file():
            _fail("grade.raw_evidence_missing", entry_path + ".objectLocator")
        data = object_path.read_bytes()
        if sha256_digest(data) != entry.get("digest") or len(data) != entry.get("byteLength"):
            _fail("grade.raw_evidence_digest_mismatch", entry_path + ".digest")
        _ensure_not_owner_writable(object_path, entry_path + ".objectLocator")
        try:
            staged_files[str(entry["path"])] = data.decode("utf-8")
        except UnicodeDecodeError:
            _fail("grade.raw_evidence_digest_mismatch", entry_path + ".objectLocator")
    return manifest, condition, scenario, environment, staged, _terminal_evidence_digest(staged, staged_files)


def _validate_ledger_grade_slot(run_dir: Path, run_id: str, grader_digest: str, grade_digest: str) -> None:
    try:
        grade_segment = _safe_digest_segment(grader_digest, "$.graderDigest")
        _safe_digest_segment(grade_digest, "$.graderDigest")
    except ContractValidationError:
        _fail("grade.grade_store_invalid", "$.graderDigest")
    grader_dir = run_dir / "grades" / grade_segment
    grade_path = grader_dir / "grade.json"
    if grader_dir.is_symlink() or not grader_dir.is_dir():
        _fail("grade.grade_store_invalid", "$.graderDigest")
    _ensure_not_owner_writable(grader_dir, "$.graderDigest", "grade.grade_store_invalid")
    if grade_path.is_symlink() or not grade_path.is_file():
        _fail("grade.grade_store_invalid", "$.graderDigest")
    _ensure_not_owner_writable(grade_path, "$.graderDigest", "grade.grade_store_invalid")
    try:
        parsed_grade = parse_contract("GradeRecord", json.loads(grade_path.read_text(encoding="utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError, ContractValidationError):
        _fail("grade.grade_store_invalid", "$.graderDigest")
    if parsed_grade["runId"] != run_id or parsed_grade["graderDigest"] != grader_digest:
        _fail("grade.grade_store_invalid", "$.graderDigest")
    if canonical_contract_digest("GradeRecord", parsed_grade) != grade_digest:
        _fail("grade.grade_store_invalid", "$.graderDigest")


def _read_grade_ledger(run_dir: Path, run_id: str) -> set[str]:
    ledger_path = run_dir / "grade-ledger.ndjson"
    if ledger_path.is_symlink() or not ledger_path.is_file():
        _fail("grade.grade_store_invalid", "$.graderDigest")
    _ensure_not_owner_writable(ledger_path, "$.graderDigest", "grade.grade_store_invalid")
    digests: set[str] = set()
    for index, line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines()):
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            _fail("grade.grade_store_invalid", "$.graderDigest")
        if not isinstance(event, dict) or set(event) != {"schemaVersion", "graderDigest", "gradeDigest"}:
            _fail("grade.grade_store_invalid", "$.graderDigest")
        if event["schemaVersion"] != 1:
            _fail("grade.grade_store_invalid", "$.graderDigest")
        grader_digest = str(event["graderDigest"])
        grade_digest = str(event["gradeDigest"])
        _validate_ledger_grade_slot(run_dir, run_id, grader_digest, grade_digest)
        if grader_digest in digests:
            _fail("grade.grade_store_invalid", "$.graderDigest")
        digests.add(grader_digest)
    return digests


def _append_grade_ledger(run_dir: Path, grader_digest: str, grade_digest: str) -> None:
    ledger_path = run_dir / "grade-ledger.ndjson"
    event = {"schemaVersion": 1, "graderDigest": grader_digest, "gradeDigest": grade_digest}
    with ledger_path.open("ab") as stream:
        start = stream.tell()
        try:
            stream.write(canonical_bytes(event) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        except Exception:
            try:
                stream.truncate(start)
                stream.flush()
                os.fsync(stream.fileno())
            except OSError:
                pass
            raise


def append_grade(run_id: str, grade: object, root: Path) -> str:
    """Append one grader's immutable GradeRecord under a finalized run."""

    parsed_grade = parse_contract("GradeRecord", grade)
    safe_run_id = _safe_identifier(run_id, "$.runId", "grade.unsafe_identifier_path")
    if parsed_grade["runId"] != safe_run_id:
        _fail("grade.run_id_mismatch", "$.runId")
    root = Path(root)
    runs_dir = root / "runs"
    _ensure_existing_plain_dir(runs_dir, "grade.run_missing", "$.runId")
    run_dir = runs_dir / safe_run_id
    _ensure_existing_plain_dir(run_dir, "grade.run_missing", "$.runId")
    _ensure_not_owner_writable(run_dir, "$.runId", "grade.run_record_mutable")
    run_json = run_dir / "run.json"
    if run_json.is_symlink() or not run_json.is_file():
        _fail("grade.run_missing", "$.runId")
    _ensure_not_owner_writable(run_json, "$.runId", "grade.run_record_mutable")
    parsed_run = parse_contract("RunRecord", json.loads(run_json.read_text(encoding="utf-8")))
    if parsed_run["runId"] != safe_run_id:
        _fail("grade.run_record_mismatch", "$.runId")
    _validate_run_digest_anchor(run_dir, parsed_run)
    manifest, condition, scenario, environment, staged, terminal_evidence_digest = _validate_raw_evidence(root, parsed_run)
    attempt = _validate_attempt_anchor(root, manifest, parsed_run)
    _validate_run_finalization_digest(
        root,
        parsed_run,
        manifest,
        attempt,
        condition,
        scenario,
        environment,
        staged,
        terminal_evidence_digest,
    )

    grade_segment = _safe_digest_segment(str(parsed_grade["graderDigest"]), "$.graderDigest")
    grades_dir, ledger_path = _ensure_existing_grade_store(run_dir)
    grader_dir = grades_dir / grade_segment
    if parsed_grade["graderDigest"] in _read_grade_ledger(run_dir, safe_run_id):
        _fail("grade.grader_digest_already_exists", "$.graderDigest")
    succeeded = False
    try:
        grades_dir.chmod(_GRADE_STORE_WRITE_MODE)
        ledger_path.chmod(_GRADE_LEDGER_WRITE_MODE)
        grader_dir.mkdir(mode=0o700, exist_ok=False)
        grade_path = grader_dir / "grade.json"
        if grade_path.exists() or grade_path.is_symlink():
            _fail("grade.grader_digest_already_exists", "$.graderDigest")
        grade_digest = canonical_contract_digest("GradeRecord", parsed_grade)
        _write_grade_exclusive(grade_path, parsed_grade)
        grader_dir.chmod(0o500)
        _append_grade_ledger(run_dir, str(parsed_grade["graderDigest"]), grade_digest)
        succeeded = True
    except FileExistsError:
        _fail("grade.grader_digest_already_exists", "$.graderDigest")
    except Exception:
        try:
            grader_dir.chmod(0o700)
        except OSError:
            pass
        grade_path = grader_dir / "grade.json"
        if grade_path.exists() and not grade_path.is_symlink():
            try:
                grade_path.unlink()
            except OSError:
                pass
        try:
            grader_dir.rmdir()
        except OSError:
            pass
        raise
    finally:
        restore_error = _restore_grade_store_modes(grades_dir, ledger_path)
        if succeeded and restore_error is not None:
            raise restore_error
    return grade_digest


__all__ = ["append_grade"]
