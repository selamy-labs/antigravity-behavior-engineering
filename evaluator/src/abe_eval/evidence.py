"""Immutable content-addressed evidence import for finalized evaluator runs."""

from __future__ import annotations

import errno
import json
import os
import uuid
from pathlib import Path

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import ContractValidationError, canonical_contract_digest, parse_contract


_REQUIRED_OUTPUTS = frozenset({"raw-stream.ndjson", "process.json"})


def _fail(reason_code: str, path: str = "$") -> None:
    raise ContractValidationError(reason_code, path)


def _safe_identifier(value: object, path: str) -> str:
    text = str(value)
    if not text or text in {".", ".."} or "/" in text or "\\" in text or "\x00" in text:
        _fail("evidence.unsafe_identifier_path", path)
    return text


def _safe_staged_output_name(value: object, path: str) -> str:
    if not isinstance(value, str):
        _fail("evidence.invalid_staging_manifest", path)
    if not value or value in {".", ".."} or "/" in value or "\\" in value or "\x00" in value:
        _fail("evidence.unsafe_staged_path", path)
    return value


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


def _read_json(path: Path, reason_code: str, error_path: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        _fail(reason_code, error_path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        _fail(reason_code, error_path)
    if not isinstance(value, dict):
        _fail(reason_code, error_path)
    return value


def _read_lifecycle(root: Path, attempt_id: str) -> list[dict[str, object]]:
    path = root / "attempts" / attempt_id / "lifecycle.ndjson"
    if path.is_symlink() or not path.is_file():
        _fail("evidence.lifecycle_missing", "$.attemptId")
    events: list[dict[str, object]] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if not line:
            continue
        try:
            event = parse_contract("AttemptLifecycleEvent", json.loads(line))
        except (json.JSONDecodeError, ContractValidationError):
            _fail("evidence.invalid_lifecycle", "$.lifecycleEventDigests[" + str(index) + "]")
        events.append(event)
    if not events:
        _fail("evidence.lifecycle_missing", "$.attemptId")
    for index, event in enumerate(events):
        if event["sequence"] != index:
            _fail("evidence.lifecycle_sequence_mismatch", "$.lifecycleEventDigests[" + str(index) + "]")
        if event["phase"] == "run_finalized":
            _fail("evidence.run_already_finalized", "$.runId")
    if events[-1]["phase"] != "execution_terminal":
        _fail("evidence.lifecycle_not_terminal", "$.lifecycleEventDigests")
    return events


def _validate_staging_manifest(staging: Path, manifest: dict[str, object]) -> list[dict[str, object]]:
    if manifest.get("schemaVersion") != 1:
        _fail("evidence.invalid_staging_manifest", "$.schemaVersion")
    entries_value = manifest.get("entries")
    if not isinstance(entries_value, list):
        _fail("evidence.invalid_staging_manifest", "$.entries")
    output_root = staging / "output"
    if output_root.is_symlink() or not output_root.is_dir():
        _fail("evidence.output_directory_missing", "$.output")

    seen: set[str] = set()
    validated: list[dict[str, object]] = []
    for index, entry_value in enumerate(entries_value):
        entry_path = "$.entries[" + str(index) + "]"
        if not isinstance(entry_value, dict):
            _fail("evidence.invalid_staging_manifest", entry_path)
        if set(entry_value) != {"path", "present", "digest", "byteLength"}:
            _fail("evidence.invalid_staging_manifest", entry_path)
        name = _safe_staged_output_name(entry_value["path"], entry_path + ".path")
        if name in seen:
            _fail("evidence.duplicate_staged_path", entry_path + ".path")
        seen.add(name)
        present = entry_value["present"]
        if not isinstance(present, bool):
            _fail("evidence.invalid_staging_manifest", entry_path + ".present")
        digest = entry_value["digest"]
        byte_length = entry_value["byteLength"]
        if not isinstance(digest, str) or not isinstance(byte_length, int) or isinstance(byte_length, bool) or byte_length < 0:
            _fail("evidence.invalid_staging_manifest", entry_path)
        if not present:
            if digest != "none" or byte_length != 0:
                _fail("evidence.invalid_staging_manifest", entry_path)
            if name in _REQUIRED_OUTPUTS:
                _fail("evidence.missing_staged_output", "$.output." + name)
            validated.append({"path": name, "present": False, "digest": "none", "byteLength": 0})
            continue

        source = output_root / name
        if source.is_symlink():
            _fail("evidence.symlink_staged_output", "$.output." + name)
        if not source.is_file():
            if name in _REQUIRED_OUTPUTS:
                _fail("evidence.missing_staged_output", "$.output." + name)
            _fail("evidence.staged_output_missing", "$.output." + name)
        data = source.read_bytes()
        actual_digest = sha256_digest(data)
        if actual_digest != digest or len(data) != byte_length:
            _fail("evidence.staged_output_digest_mismatch", "$.output." + name)
        validated.append({"path": name, "present": True, "digest": digest, "byteLength": byte_length, "data": data})

    missing_required = sorted(name for name in _REQUIRED_OUTPUTS if name not in seen)
    if missing_required:
        _fail("evidence.missing_staged_output", "$.output." + missing_required[0])
    return validated


def _digest_for(entries: list[dict[str, object]], name: str) -> str:
    for entry in entries:
        if entry["path"] == name:
            return str(entry["digest"])
    return "none"


def _object_locator(digest: str) -> str:
    return "objects/sha256/" + digest.removeprefix("sha256:")


def _temporary_sibling(path: Path) -> Path:
    return path.with_name(path.name + ".tmp." + str(os.getpid()) + "." + uuid.uuid4().hex)


def _write_content_object(root: Path, digest: str, data: bytes) -> str:
    if sha256_digest(data) != digest:
        _fail("evidence.content_digest_mismatch", "$.objects")
    objects = root / "objects"
    sha256_dir = objects / "sha256"
    _ensure_plain_dir(objects, "evidence.object_store_invalid", "$.objects")
    _ensure_plain_dir(sha256_dir, "evidence.object_store_invalid", "$.objects.sha256")
    object_path = root / _object_locator(digest)
    if object_path.exists() or object_path.is_symlink():
        if object_path.is_symlink() or not object_path.is_file() or object_path.read_bytes() != data:
            _fail("evidence.object_digest_collision", "$.objects")
        return _object_locator(digest)

    tmp_path = _temporary_sibling(object_path)
    try:
        with tmp_path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(tmp_path, object_path)
    except FileExistsError:
        if not object_path.is_file() or object_path.is_symlink() or object_path.read_bytes() != data:
            _fail("evidence.object_digest_collision", "$.objects")
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
    return _object_locator(digest)


def _write_json_exclusive(path: Path, value: dict[str, object], reason_code: str) -> None:
    data = canonical_bytes(value) + b"\n"
    tmp_path = _temporary_sibling(path)
    try:
        with tmp_path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(tmp_path, path)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            _fail(reason_code, "$.runId")
        raise
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def _append_run_finalized_event(root: Path, attempt_id: str, events: list[dict[str, object]], run: dict[str, object]) -> None:
    event = parse_contract(
        "AttemptLifecycleEvent",
        {
            "schemaVersion": 1,
            "attemptId": attempt_id,
            "sequence": len(events),
            "phase": "run_finalized",
            "terminalKind": "none",
            "occurredAt": str(run["processState"]["endedAt"]),
            "evidenceDigest": canonical_contract_digest("RunRecord", run),
        },
    )
    path = root / "attempts" / attempt_id / "lifecycle.ndjson"
    with path.open("ab") as stream:
        stream.write(canonical_bytes(event) + b"\n")


def import_run(
    staging: Path,
    attempt: object,
    condition: object,
    scenario: object,
    qualification: object,
    root: Path,
) -> dict[str, object]:
    """Import one T007 staged outcome into immutable raw evidence and a finalized RunRecord."""

    root = Path(root)
    staging = Path(staging)
    if staging.is_symlink() or not staging.is_dir():
        _fail("evidence.staging_missing", "$.staging")

    parsed_attempt = parse_contract("ScheduledAttempt", attempt)
    parsed_condition = parse_contract("ConditionLock", condition)
    parsed_scenario = parse_contract("ScenarioCard", scenario)
    parsed_qualification = parse_contract("EnvironmentQualificationRecord", qualification)
    attempt_id = _safe_identifier(parsed_attempt["attemptId"], "$.attemptId")
    run_id = _safe_identifier(parsed_attempt["runId"], "$.runId")
    run_dir = root / "runs" / run_id
    run_json = run_dir / "run.json"
    if run_json.exists() or run_json.is_symlink():
        _fail("evidence.run_already_finalized", "$.runId")

    unclassified = _read_json(staging / "unclassified-outcome.json", "evidence.unclassified_outcome_missing", "$.unclassifiedOutcome")
    staged = _read_json(staging / "staged-outcome.json", "evidence.staged_outcome_missing", "$.stagedOutcome")
    manifest = _read_json(staging / "staging-manifest.json", "evidence.staging_manifest_missing", "$.stagingManifest")
    entries = _validate_staging_manifest(staging, manifest)

    bundle = parse_contract(
        "StagedAttemptOutcomeBundle",
        {"schemaVersion": 1, "unclassifiedOutcome": unclassified, "stagedOutcome": staged},
    )
    staged = bundle["stagedOutcome"]
    unclassified = bundle["unclassifiedOutcome"]
    if staged["stagingManifestDigest"] != sha256_digest(canonical_bytes(manifest)):
        _fail("evidence.binding_mismatch", "$.stagingManifestDigest")
    if staged["runId"] != run_id or staged["attemptId"] != attempt_id:
        _fail("evidence.binding_mismatch", "$.runId")
    if parsed_attempt["conditionId"] != parsed_condition["conditionId"]:
        _fail("evidence.binding_mismatch", "$.conditionDigest")
    if parsed_attempt["scenarioId"] != parsed_scenario["scenarioId"]:
        _fail("evidence.binding_mismatch", "$.scenarioDigest")
    if staged["conditionDigest"] != canonical_contract_digest("ConditionLock", parsed_condition):
        _fail("evidence.binding_mismatch", "$.conditionDigest")
    if staged["scenarioDigest"] != canonical_contract_digest("ScenarioCard", parsed_scenario):
        _fail("evidence.binding_mismatch", "$.scenarioDigest")
    if staged["environmentQualificationDigest"] != canonical_contract_digest("EnvironmentQualificationRecord", parsed_qualification):
        _fail("evidence.binding_mismatch", "$.environmentQualificationDigest")

    events = _read_lifecycle(root, attempt_id)
    event_digests = [canonical_contract_digest("AttemptLifecycleEvent", event) for event in events]
    if event_digests != staged["lifecycleEventDigests"]:
        _fail("evidence.binding_mismatch", "$.lifecycleEventDigests")

    raw_entries: list[dict[str, object]] = []
    for entry in entries:
        raw_entry = {key: entry[key] for key in ("path", "present", "digest", "byteLength")}
        if entry["present"]:
            raw_entry["objectLocator"] = _write_content_object(root, str(entry["digest"]), entry["data"])  # type: ignore[arg-type]
        raw_entries.append(raw_entry)
    raw_manifest = {
        "schemaVersion": 1,
        "runId": run_id,
        "attemptId": attempt_id,
        "stagedOutcomeDigest": canonical_contract_digest("StagedAttemptOutcome", staged),
        "unclassifiedOutcomeDigest": canonical_contract_digest("UnclassifiedStagedAttemptOutcome", unclassified),
        "sourceStagingManifestDigest": staged["stagingManifestDigest"],
        "entries": raw_entries,
    }
    raw_manifest_bytes = canonical_bytes(raw_manifest)
    raw_manifest_digest = sha256_digest(raw_manifest_bytes)
    raw_manifest_locator = _write_content_object(root, raw_manifest_digest, raw_manifest_bytes)

    run = parse_contract(
        "RunRecord",
        {
            "schemaVersion": 1,
            "runId": run_id,
            "attemptId": attempt_id,
            "conditionDigest": staged["conditionDigest"],
            "scenarioDigest": staged["scenarioDigest"],
            "environmentQualificationDigest": staged["environmentQualificationDigest"],
            "attemptQualification": staged["attemptQualification"],
            "observedModel": staged["observedModel"],
            "processState": staged["processState"],
            "agentDeclaredState": staged["agentDeclaredState"],
            "inputPermissionState": staged["inputPermissionState"],
            "infrastructureValidity": staged["infrastructureValidity"],
            "artifactManifestDigest": raw_manifest_digest,
            "transcriptDigest": _digest_for(raw_entries, "raw-stream.ndjson"),
            "eventStreamDigest": _digest_for(raw_entries, "hook-events.ndjson"),
            "consumption": staged["consumption"],
            "classification": staged["classification"],
            "rawEvidenceLocator": raw_manifest_locator,
            "redactedEvidenceLocator": "not_redacted",
        },
    )
    _ensure_plain_dir(root / "runs", "evidence.run_store_invalid", "$.runs")
    _ensure_plain_dir(run_dir, "evidence.run_store_invalid", "$.runId")
    _write_json_exclusive(run_json, run, "evidence.run_already_finalized")
    _append_run_finalized_event(root, attempt_id, events, run)
    return run


__all__ = ["import_run"]
