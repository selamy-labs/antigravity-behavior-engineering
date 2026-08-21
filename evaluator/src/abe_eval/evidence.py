"""Immutable content-addressed evidence import for finalized evaluator runs."""

from __future__ import annotations

import errno
import json
import os
import uuid
from pathlib import Path

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.classify import _REASON_CLASS, _reason_code
from abe_eval.contracts import ContractValidationError, canonical_contract_digest, parse_contract
from abe_eval.runner import _OUTPUT_NAMES, _worker_invocation


_REQUIRED_OUTPUTS = frozenset({"raw-stream.ndjson", "process.json"})
_ALL_OUTPUTS = frozenset(_OUTPUT_NAMES)
_T007_POLICY_DIGEST = "sha256:e37d8012ffe55956d37837d66475fe9362591a6f23a70b63cd6d60ce49db054a"


def _t007_seed_digest(seed: str) -> str:
    return "sha256:" + (seed * 64)[:64]


_T007_PRE_WORKER_STDERR_DIGEST = _t007_seed_digest("ee")
_RETRY_ELIGIBLE_REASONS_BY_POLICY = {
    _T007_POLICY_DIGEST: frozenset(
        {
            "adapter_failure",
            "malformed_ndjson",
            "pre_start_auth_failure",
            "test_flake",
            "truncated_ndjson",
        }
    )
}
_PREFLIGHT_FIELDS = (
    ("authentication", "authentication"),
    ("fixtureProvisioning", "fixtureProvisioning"),
    ("modelPreflight", "modelPreflight"),
    ("fallbackProbe", "fallbackProbe"),
    ("pluginComponentDiscovery", "pluginComponentDiscovery"),
    ("structuredCapturePreflight", "structuredCapturePreflight"),
    ("authorityToolInventory", "authorityToolInventory"),
)
_PREFLIGHT_EVIDENCE_DIGESTS = {
    "authentication": _t007_seed_digest("35"),
    "fixtureProvisioning": _t007_seed_digest("46"),
    "modelPreflight": _t007_seed_digest("57"),
    "fallbackProbe": _t007_seed_digest("68"),
    "pluginComponentDiscovery": _t007_seed_digest("79"),
    "structuredCapturePreflight": _t007_seed_digest("8a"),
    "authorityToolInventory": _t007_seed_digest("9b"),
}
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


def _media_type(name: str) -> str:
    if name.endswith(".ndjson"):
        return "application/x-ndjson"
    if name.endswith(".json"):
        return "application/json"
    if name.endswith(".txt"):
        return "text/plain; charset=utf-8"
    return "application/octet-stream"


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


def _digest_payload(payload: object) -> str:
    return sha256_digest(canonical_bytes(payload))


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
        if event["attemptId"] != attempt_id:
            _fail("evidence.binding_mismatch", "$.lifecycleEventDigests[" + str(index) + "].attemptId")
        if event["sequence"] != index:
            _fail("evidence.lifecycle_sequence_mismatch", "$.lifecycleEventDigests[" + str(index) + "]")
        if event["phase"] == "run_finalized":
            _fail("evidence.run_already_finalized", "$.runId")
    if events[-1]["phase"] != "execution_terminal":
        _fail("evidence.lifecycle_not_terminal", "$.lifecycleEventDigests")
    return events


def _validate_staging_manifest(
    staging: Path, manifest: dict[str, object], run_id: str, required_outputs: frozenset[str]
) -> list[dict[str, object]]:
    if set(manifest) != {"schemaVersion", "runId", "entries"}:
        _fail("evidence.invalid_staging_manifest", "$.stagingManifest")
    if manifest.get("schemaVersion") != 1:
        _fail("evidence.invalid_staging_manifest", "$.schemaVersion")
    if manifest.get("runId") != run_id:
        _fail("evidence.binding_mismatch", "$.stagingManifest.runId")
    entries_value = manifest.get("entries")
    if not isinstance(entries_value, list):
        _fail("evidence.invalid_staging_manifest", "$.entries")
    output_root = staging / "output"
    if output_root.is_symlink():
        _fail("evidence.symlink_staged_output", "$.output")
    output_root_exists = output_root.exists()
    if output_root_exists and not output_root.is_dir():
        _fail("evidence.output_directory_missing", "$.output")

    seen: set[str] = set()
    present_by_name: dict[str, bool] = {}
    validated: list[dict[str, object]] = []
    for index, entry_value in enumerate(entries_value):
        entry_path = "$.entries[" + str(index) + "]"
        if not isinstance(entry_value, dict):
            _fail("evidence.invalid_staging_manifest", entry_path)
        if set(entry_value) != {"path", "present", "digest", "byteLength"}:
            _fail("evidence.invalid_staging_manifest", entry_path)
        name = _safe_staged_output_name(entry_value["path"], entry_path + ".path")
        if name not in _ALL_OUTPUTS:
            _fail("evidence.unexpected_staged_output", entry_path + ".path")
        if name in seen:
            _fail("evidence.duplicate_staged_path", entry_path + ".path")
        seen.add(name)
        present = entry_value["present"]
        if not isinstance(present, bool):
            _fail("evidence.invalid_staging_manifest", entry_path + ".present")
        present_by_name[name] = present
        digest = entry_value["digest"]
        byte_length = entry_value["byteLength"]
        if not isinstance(digest, str) or not isinstance(byte_length, int) or isinstance(byte_length, bool) or byte_length < 0:
            _fail("evidence.invalid_staging_manifest", entry_path)
        if not present:
            if digest != "none" or byte_length != 0:
                _fail("evidence.invalid_staging_manifest", entry_path)
            if name in required_outputs:
                _fail("evidence.missing_staged_output", "$.output." + name)
            validated.append({"path": name, "present": False, "digest": "none", "byteLength": 0})
            continue

        source = output_root / name
        if not output_root_exists:
            if name in required_outputs:
                _fail("evidence.missing_staged_output", "$.output." + name)
            _fail("evidence.staged_output_missing", "$.output." + name)
        if source.is_symlink():
            _fail("evidence.symlink_staged_output", "$.output." + name)
        if not source.is_file():
            if name in required_outputs:
                _fail("evidence.missing_staged_output", "$.output." + name)
            _fail("evidence.staged_output_missing", "$.output." + name)
        data = source.read_bytes()
        actual_digest = sha256_digest(data)
        if actual_digest != digest or len(data) != byte_length:
            _fail("evidence.staged_output_digest_mismatch", "$.output." + name)
        validated.append({"path": name, "present": True, "digest": digest, "byteLength": byte_length, "data": data})

    if output_root_exists:
        for child in output_root.iterdir():
            name = _safe_staged_output_name(child.name, "$.output")
            if child.is_symlink():
                _fail("evidence.symlink_staged_output", "$.output." + name)
            if name not in seen or not present_by_name[name]:
                _fail("evidence.unmanifested_staged_output", "$.output." + name)

    missing_required = sorted(name for name in required_outputs if name not in seen)
    if missing_required:
        _fail("evidence.missing_staged_output", "$.output." + missing_required[0])
    missing_markers = sorted(name for name in _ALL_OUTPUTS if name not in seen)
    if missing_markers:
        _fail("evidence.missing_staged_output_marker", "$.output." + missing_markers[0])
    return validated


def _digest_for(entries: list[dict[str, object]], name: str) -> str:
    for entry in entries:
        if entry["path"] == name:
            return str(entry["digest"])
    return "none"


def _artifact_locator(run_id: str, digest: str) -> str:
    return "runs/" + run_id + "/artifacts/sha256/" + digest.removeprefix("sha256:")


def _temporary_sibling(path: Path) -> Path:
    return path.with_name(path.name + ".tmp." + str(os.getpid()) + "." + uuid.uuid4().hex)


def _write_content_object(temporary_run_dir: Path, digest: str, data: bytes) -> None:
    if sha256_digest(data) != digest:
        _fail("evidence.content_digest_mismatch", "$.artifacts")
    artifacts = temporary_run_dir / "artifacts"
    sha256_dir = artifacts / "sha256"
    _ensure_plain_dir(artifacts, "evidence.object_store_invalid", "$.artifacts")
    _ensure_plain_dir(sha256_dir, "evidence.object_store_invalid", "$.artifacts.sha256")
    object_path = sha256_dir / digest.removeprefix("sha256:")
    if object_path.exists() or object_path.is_symlink():
        if object_path.is_symlink() or not object_path.is_file() or object_path.read_bytes() != data:
            _fail("evidence.object_digest_collision", "$.artifacts")
        object_path.chmod(0o400)
        return

    tmp_path = _temporary_sibling(object_path)
    try:
        with tmp_path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(tmp_path, object_path)
        object_path.chmod(0o400)
    except FileExistsError:
        if not object_path.is_file() or object_path.is_symlink() or object_path.read_bytes() != data:
            _fail("evidence.object_digest_collision", "$.artifacts")
        object_path.chmod(0o400)
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def _remove_run_directory_contents(run_dir: Path) -> None:
    if run_dir.is_symlink() or not run_dir.is_dir():
        return
    try:
        run_dir.chmod(0o700)
    except OSError:
        pass
    for name in ("run.json", "run.digest", "grade-ledger.ndjson"):
        child = run_dir / name
        if child.is_symlink() or not child.is_file():
            continue
        try:
            child.unlink()
        except OSError:
            pass
    sha256_dir = run_dir / "artifacts" / "sha256"
    if not sha256_dir.is_symlink() and sha256_dir.is_dir():
        for child in sha256_dir.iterdir():
            if child.is_symlink() or not child.is_file():
                continue
            try:
                child.unlink()
            except OSError:
                pass
        try:
            sha256_dir.rmdir()
        except OSError:
            pass
    artifacts_dir = run_dir / "artifacts"
    if not artifacts_dir.is_symlink() and artifacts_dir.is_dir():
        try:
            artifacts_dir.rmdir()
        except OSError:
            pass
    grades_dir = run_dir / "grades"
    if not grades_dir.is_symlink() and grades_dir.is_dir():
        try:
            grades_dir.rmdir()
        except OSError:
            pass
    try:
        run_dir.rmdir()
    except OSError:
        pass


def _write_json_file(path: Path, value: dict[str, object]) -> None:
    data = canonical_bytes(value) + b"\n"
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _write_text_file(path: Path, value: str) -> None:
    with path.open("x", encoding="utf-8") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


def _finalize_run_directory(root: Path, run_id: str, run: dict[str, object], artifacts: list[tuple[str, bytes]]) -> None:
    runs_dir = root / "runs"
    _ensure_plain_dir(runs_dir, "evidence.run_store_invalid", "$.runs")
    run_dir = runs_dir / run_id
    if run_dir.exists() or run_dir.is_symlink():
        _fail("evidence.run_already_finalized", "$.runId")
    temporary_run_dir = runs_dir / (".tmp-" + run_id + "." + str(os.getpid()) + "." + uuid.uuid4().hex)
    temporary_run_dir.mkdir(mode=0o700)
    try:
        for digest, data in artifacts:
            _write_content_object(temporary_run_dir, digest, data)
        (temporary_run_dir / "grades").mkdir(mode=0o700)
        _write_text_file(temporary_run_dir / "grade-ledger.ndjson", "")
        _write_json_file(temporary_run_dir / "run.json", run)
        _write_text_file(temporary_run_dir / "run.digest", canonical_contract_digest("RunRecord", run) + "\n")
        os.rename(temporary_run_dir, run_dir)
        try:
            (run_dir / "run.json").chmod(0o400)
            (run_dir / "run.digest").chmod(0o400)
            (run_dir / "grade-ledger.ndjson").chmod(0o600)
            (run_dir / "grades").chmod(0o700)
            run_dir.chmod(0o500)
        except OSError:
            _rollback_finalized_run_directory(root, run_id)
            raise
    except OSError as exc:
        if exc.errno in {errno.EEXIST, errno.ENOTEMPTY}:
            _fail("evidence.run_already_finalized", "$.runId")
        raise
    finally:
        if temporary_run_dir.exists() and not temporary_run_dir.is_symlink():
            _remove_run_directory_contents(temporary_run_dir)


def _rollback_finalized_run_directory(root: Path, run_id: str) -> None:
    run_dir = root / "runs" / run_id
    _remove_run_directory_contents(run_dir)


def _run_finalized_event(attempt_id: str, events: list[dict[str, object]], run: dict[str, object]) -> dict[str, object]:
    return parse_contract(
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


def _open_lifecycle_append_stream(root: Path, attempt_id: str):
    path = root / "attempts" / attempt_id / "lifecycle.ndjson"
    try:
        return path.open("ab")
    except OSError:
        _fail("evidence.lifecycle_not_appendable", "$.attemptId")


def _append_run_finalized_event(stream, event: dict[str, object]) -> None:
    try:
        stream.write(canonical_bytes(event) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    except OSError:
        _fail("evidence.lifecycle_not_appendable", "$.attemptId")


def _truncate_lifecycle_stream(stream, position: int) -> None:
    try:
        stream.truncate(position)
        stream.flush()
        os.fsync(stream.fileno())
    except OSError:
        pass


def _lifecycle_ends_with_event(root: Path, attempt_id: str, expected: dict[str, object]) -> bool:
    path = root / "attempts" / attempt_id / "lifecycle.ndjson"
    try:
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
        if not lines:
            return False
        actual = parse_contract("AttemptLifecycleEvent", json.loads(lines[-1]))
    except (OSError, json.JSONDecodeError, ContractValidationError):
        return False
    return canonical_contract_digest("AttemptLifecycleEvent", actual) == canonical_contract_digest(
        "AttemptLifecycleEvent", expected
    )


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
        _fail("evidence.binding_mismatch", "$.attemptQualification")
    return failures[0][1]


def _staged_files_from_entries(entries: list[dict[str, object]]) -> dict[str, str]:
    staged_files: dict[str, str] = {}
    for entry in entries:
        if not entry["present"]:
            continue
        data = entry.get("data")
        if not isinstance(data, bytes):
            _fail("evidence.staged_output_missing", "$.output." + str(entry["path"]))
        try:
            staged_files[str(entry["path"])] = data.decode("utf-8")
        except UnicodeDecodeError:
            _fail("evidence.staged_output_not_utf8", "$.output." + str(entry["path"]))
    return staged_files


def _terminal_evidence(staged: dict[str, object], terminal: dict[str, object], entries: list[dict[str, object]]) -> dict[str, object]:
    process = staged["processState"]
    if process["workerProcessState"] == "not_started":
        return {"failedPreflight": _failed_preflight(staged["attemptQualification"])}
    return {
        "terminalKind": terminal["terminalKind"],
        "controllerExitCode": process["controllerExitCode"],
        "workerExitCode": process["workerExitCode"],
        "signal": process["signal"],
        "timeout": process["timeout"],
        "agentDeclaredState": staged["agentDeclaredState"],
        "inputPermissionState": staged["inputPermissionState"],
        "infrastructureValidity": staged["infrastructureValidity"],
        "consumption": staged["consumption"],
        "observedModel": staged["observedModel"],
        "stagedFiles": _staged_files_from_entries(entries),
    }


def _read_stored_attempt(root: Path, attempt_id: str, supplied_attempt: dict[str, object]) -> dict[str, object]:
    stored_attempt = parse_contract(
        "ScheduledAttempt",
        _read_json(root / "attempts" / attempt_id / "attempt.json", "evidence.attempt_missing", "$.attemptId"),
    )
    if canonical_contract_digest("ScheduledAttempt", stored_attempt) != canonical_contract_digest(
        "ScheduledAttempt", supplied_attempt
    ):
        _fail("evidence.binding_mismatch", "$.attemptDigest")
    return stored_attempt


def _validate_controller_bindings(
    condition: dict[str, object], scenario: dict[str, object], qualification: dict[str, object]
) -> str:
    qualification_digest = canonical_contract_digest("EnvironmentQualificationRecord", qualification)
    if condition["environmentQualificationDigest"] != qualification_digest:
        _fail("evidence.binding_mismatch", "$.environmentQualificationDigest")
    if condition["cliDigest"] != qualification["cliDigest"]:
        _fail("evidence.binding_mismatch", "$.environmentQualificationDigest")
    if condition["authorityManifestDigest"] != canonical_contract_digest("AuthorityManifest", scenario["authorityManifest"]):
        _fail("evidence.binding_mismatch", "$.conditionDigest")
    if condition["resourceEnvelopeDigest"] != canonical_contract_digest("ResourceEnvelope", scenario["resourceEnvelope"]):
        _fail("evidence.binding_mismatch", "$.conditionDigest")
    return qualification_digest


def _validate_classification(staged: dict[str, object], scenario: dict[str, object]) -> None:
    classification = staged["classification"]
    if classification["policyDigest"] != scenario["classificationPolicyDigest"]:
        _fail("evidence.binding_mismatch", "$.classification.policyDigest")
    retry_eligible_reasons = _RETRY_ELIGIBLE_REASONS_BY_POLICY.get(str(classification["policyDigest"]))
    if retry_eligible_reasons is None:
        _fail("evidence.unknown_classification_policy", "$.classification.policyDigest")
    expected_reason = _reason_code(staged)
    if classification["reasonCode"] != expected_reason:
        _fail("evidence.binding_mismatch", "$.classification.reasonCode")
    expected_class = _REASON_CLASS[expected_reason]
    if classification["class"] != expected_class:
        _fail("evidence.binding_mismatch", "$.classification.class")
    if classification["countsInIntentionToTreat"] is not True:
        _fail("evidence.binding_mismatch", "$.classification.countsInIntentionToTreat")
    if classification["countsInValidRun"] != (expected_class == "gradable"):
        _fail("evidence.binding_mismatch", "$.classification.countsInValidRun")
    if classification["retryEligible"] != (expected_reason in retry_eligible_reasons):
        _fail("evidence.binding_mismatch", "$.classification.retryEligible")


def _validate_preflight_state(staged: dict[str, object]) -> None:
    valid_start_at = staged["attemptQualification"]["validStartAt"]
    for field, expected_digest in _PREFLIGHT_EVIDENCE_DIGESTS.items():
        if staged["attemptQualification"][field]["evidenceDigest"] != expected_digest:
            _fail("evidence.binding_mismatch", "$.attemptQualification." + field + ".evidenceDigest")
    failures = _preflight_failures(staged["attemptQualification"])
    if valid_start_at == "none":
        if not failures:
            _fail("evidence.binding_mismatch", "$.attemptQualification")
        return
    if failures:
        _fail("evidence.binding_mismatch", "$.attemptQualification." + failures[0][0] + ".result")


def _validate_observed_model_binding(staged: dict[str, object], condition: dict[str, object]) -> None:
    observed = staged["observedModel"]
    if observed["requestedModel"] != condition["modelRequest"]:
        _fail("evidence.binding_mismatch", "$.observedModel.requestedModel")
    if observed["requestedReasoning"] != condition["reasoningRequest"]:
        _fail("evidence.binding_mismatch", "$.observedModel.requestedReasoning")


def _validate_pre_worker_state(staged: dict[str, object], entries: list[dict[str, object]]) -> None:
    process = staged["processState"]
    if process["workerProcessState"] != "not_started":
        return
    if process["controllerExitCode"] != 64:
        _fail("evidence.binding_mismatch", "$.processState.controllerExitCode")
    if process["workerExitCode"] != "none":
        _fail("evidence.binding_mismatch", "$.processState.workerExitCode")
    if process["signal"] != "none":
        _fail("evidence.binding_mismatch", "$.processState.signal")
    if process["timeout"] is not False:
        _fail("evidence.binding_mismatch", "$.processState.timeout")
    if process["startedAt"] != "none":
        _fail("evidence.binding_mismatch", "$.processState.startedAt")
    if staged["agentDeclaredState"] != "none":
        _fail("evidence.binding_mismatch", "$.agentDeclaredState")
    if staged["inputPermissionState"] != "not_requested":
        _fail("evidence.binding_mismatch", "$.inputPermissionState")
    failed_preflight = _failed_preflight(staged["attemptQualification"])
    expected_infrastructure = "pre_start_auth_failure" if failed_preflight == "authentication" else "invalid_controller_input"
    if staged["infrastructureValidity"] != expected_infrastructure:
        _fail("evidence.binding_mismatch", "$.infrastructureValidity")
    expected_stderr_digest = _digest_for(entries, "stderr.txt")
    if expected_stderr_digest == "none":
        expected_stderr_digest = _T007_PRE_WORKER_STDERR_DIGEST
    if process["stderrDigest"] != expected_stderr_digest:
        _fail("evidence.binding_mismatch", "$.processState.stderrDigest")
    observed = staged["observedModel"]
    if observed["servedIdentityEvidence"] != [
        {"schemaVersion": 1, "source": "pre-start", "value": "unreported", "digest": _t007_seed_digest("ac")}
    ]:
        _fail("evidence.binding_mismatch", "$.observedModel.servedIdentityEvidence")
    if observed["fallbackProbeResult"] != {
        "schemaVersion": 1,
        "result": "indeterminate",
        "evidenceDigest": _t007_seed_digest("bd"),
    }:
        _fail("evidence.binding_mismatch", "$.observedModel.fallbackProbeResult")
    if observed["conclusion"] != "unobservable" or observed["limitations"] != ["Worker did not reach valid start."]:
        _fail("evidence.binding_mismatch", "$.observedModel")
    if staged["consumption"] != {
        "schemaVersion": 1,
        "inputTokens": "unavailable",
        "outputTokens": "unavailable",
        "cachedTokens": "unavailable",
        "toolCalls": "unavailable",
        "subagentCalls": "unavailable",
        "wallTimeMs": 0,
        "quotaOrCost": "unavailable",
        "sourceEvidenceDigest": _t007_seed_digest("ce"),
    }:
        _fail("evidence.binding_mismatch", "$.consumption")


def _validate_started_process_state(staged: dict[str, object], entries: list[dict[str, object]]) -> None:
    process = staged["processState"]
    if process["workerProcessState"] == "not_started":
        return
    if staged["infrastructureValidity"] in {"invalid_controller_input", "pre_start_auth_failure"}:
        _fail("evidence.binding_mismatch", "$.infrastructureValidity")
    if process["workerProcessState"] != "terminated":
        _fail("evidence.binding_mismatch", "$.processState.workerProcessState")
    valid_start_at = staged["attemptQualification"]["validStartAt"]
    if process["startedAt"] != valid_start_at:
        _fail("evidence.binding_mismatch", "$.processState.startedAt")
    if process["stderrDigest"] != _digest_for(entries, "stderr.txt"):
        _fail("evidence.binding_mismatch", "$.processState.stderrDigest")


def _validate_attempt_controller_identity(
    attempt: dict[str, object], condition: dict[str, object], scenario: dict[str, object], staged: dict[str, object]
) -> None:
    controller_failure = (
        staged["processState"]["workerProcessState"] == "not_started"
        and staged["classification"]["reasonCode"] == "invalid_controller_input"
    )
    if attempt["conditionId"] != condition["conditionId"] and not controller_failure:
        _fail("evidence.binding_mismatch", "$.conditionDigest")
    if attempt["scenarioId"] != scenario["scenarioId"] and not controller_failure:
        _fail("evidence.binding_mismatch", "$.scenarioDigest")


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


def _validate_lifecycle_bindings(
    events: list[dict[str, object]],
    attempt: dict[str, object],
    condition: dict[str, object],
    scenario: dict[str, object],
    qualification_digest: str,
    staged: dict[str, object],
    entries: list[dict[str, object]],
) -> None:
    valid_start_at = str(staged["attemptQualification"]["validStartAt"])
    expected_phases = ["scheduled", "preflight"]
    if valid_start_at != "none":
        expected_phases.append("valid_started")
    expected_phases.append("execution_terminal")
    if [event["phase"] for event in events] != expected_phases:
        _fail("evidence.binding_mismatch", "$.lifecycleEventDigests")

    if events[0]["occurredAt"] != attempt["scheduledAt"]:
        _fail("evidence.binding_mismatch", "$.lifecycleEventDigests[0].occurredAt")
    if events[0]["evidenceDigest"] != canonical_contract_digest("ScheduledAttempt", attempt):
        _fail("evidence.binding_mismatch", "$.lifecycleEventDigests[0].evidenceDigest")

    preflight_evidence = {"condition": condition, "scenario": scenario}
    if events[1]["evidenceDigest"] != _digest_payload(preflight_evidence):
        _fail("evidence.binding_mismatch", "$.lifecycleEventDigests[1].evidenceDigest")

    if valid_start_at == "none":
        if staged["processState"]["workerProcessState"] != "not_started":
            _fail("evidence.binding_mismatch", "$.attemptQualification.validStartAt")
    else:
        valid_started = events[2]
        if valid_started["occurredAt"] != valid_start_at:
            _fail("evidence.binding_mismatch", "$.attemptQualification.validStartAt")
        invocation = _worker_invocation(attempt, condition, scenario, qualification_digest)
        if valid_started["evidenceDigest"] != _digest_payload(invocation):
            _fail("evidence.binding_mismatch", "$.lifecycleEventDigests[2].evidenceDigest")

    if events[-1]["occurredAt"] != staged["processState"]["endedAt"]:
        _fail("evidence.binding_mismatch", "$.processState.endedAt")
    if events[-1]["terminalKind"] != _expected_terminal_kind(staged):
        _fail("evidence.binding_mismatch", "$.lifecycleEventDigests[" + str(len(events) - 1) + "].terminalKind")
    terminal_evidence = _terminal_evidence(staged, events[-1], entries)
    if events[-1]["evidenceDigest"] != _digest_payload(terminal_evidence):
        _fail("evidence.binding_mismatch", "$.lifecycleEventDigests[" + str(len(events) - 1) + "].evidenceDigest")


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
    stored_attempt = _read_stored_attempt(root, attempt_id, parsed_attempt)
    qualification_digest = _validate_controller_bindings(parsed_condition, parsed_scenario, parsed_qualification)

    unclassified = _read_json(staging / "unclassified-outcome.json", "evidence.unclassified_outcome_missing", "$.unclassifiedOutcome")
    staged = _read_json(staging / "staged-outcome.json", "evidence.staged_outcome_missing", "$.stagedOutcome")
    manifest = _read_json(staging / "staging-manifest.json", "evidence.staging_manifest_missing", "$.stagingManifest")
    bundle = parse_contract(
        "StagedAttemptOutcomeBundle",
        {"schemaVersion": 1, "unclassifiedOutcome": unclassified, "stagedOutcome": staged},
    )
    staged = bundle["stagedOutcome"]
    unclassified = bundle["unclassifiedOutcome"]
    required_outputs = frozenset() if staged["processState"]["workerProcessState"] == "not_started" else _REQUIRED_OUTPUTS
    entries = _validate_staging_manifest(staging, manifest, run_id, required_outputs)
    if staged["stagingManifestDigest"] != sha256_digest(canonical_bytes(manifest)):
        _fail("evidence.binding_mismatch", "$.stagingManifestDigest")
    if staged["runId"] != run_id or staged["attemptId"] != attempt_id:
        _fail("evidence.binding_mismatch", "$.runId")
    if staged["conditionDigest"] != canonical_contract_digest("ConditionLock", parsed_condition):
        _fail("evidence.binding_mismatch", "$.conditionDigest")
    if staged["scenarioDigest"] != canonical_contract_digest("ScenarioCard", parsed_scenario):
        _fail("evidence.binding_mismatch", "$.scenarioDigest")
    if staged["environmentQualificationDigest"] != qualification_digest:
        _fail("evidence.binding_mismatch", "$.environmentQualificationDigest")
    _validate_preflight_state(staged)
    _validate_observed_model_binding(staged, parsed_condition)
    _validate_classification(staged, parsed_scenario)
    _validate_pre_worker_state(staged, entries)
    _validate_attempt_controller_identity(stored_attempt, parsed_condition, parsed_scenario, staged)

    events = _read_lifecycle(root, attempt_id)
    event_digests = [canonical_contract_digest("AttemptLifecycleEvent", event) for event in events]
    if event_digests != staged["lifecycleEventDigests"]:
        _fail("evidence.binding_mismatch", "$.lifecycleEventDigests")
    _validate_lifecycle_bindings(events, stored_attempt, parsed_condition, parsed_scenario, qualification_digest, staged, entries)
    _validate_started_process_state(staged, entries)

    raw_entries: list[dict[str, object]] = []
    artifact_payloads: list[tuple[str, bytes]] = []
    condition_digest = canonical_contract_digest("ConditionLock", parsed_condition)
    scenario_digest = canonical_contract_digest("ScenarioCard", parsed_scenario)
    environment_qualification_digest = canonical_contract_digest("EnvironmentQualificationRecord", parsed_qualification)
    staged_outcome_digest = canonical_contract_digest("StagedAttemptOutcome", staged)
    unclassified_outcome_digest = canonical_contract_digest("UnclassifiedStagedAttemptOutcome", unclassified)
    artifact_payloads.append((condition_digest, canonical_bytes(parsed_condition)))
    artifact_payloads.append((scenario_digest, canonical_bytes(parsed_scenario)))
    artifact_payloads.append((environment_qualification_digest, canonical_bytes(parsed_qualification)))
    artifact_payloads.append((staged_outcome_digest, canonical_bytes(staged)))
    artifact_payloads.append((unclassified_outcome_digest, canonical_bytes(unclassified)))
    for entry in entries:
        raw_entry = {key: entry[key] for key in ("path", "present", "digest", "byteLength")}
        raw_entry["mediaType"] = _media_type(str(entry["path"]))
        raw_entry["sourceZone"] = "protected_raw_staging"
        raw_entry["redactionDisposition"] = "protected_only_pending_redaction"
        if entry["present"]:
            raw_entry["objectLocator"] = _artifact_locator(run_id, str(entry["digest"]))
            artifact_payloads.append((str(entry["digest"]), entry["data"]))  # type: ignore[arg-type]
        raw_entries.append(raw_entry)
    run_record_binding = {
        "conditionDigest": staged["conditionDigest"],
        "scenarioDigest": staged["scenarioDigest"],
        "environmentQualificationDigest": staged["environmentQualificationDigest"],
        "attemptQualification": staged["attemptQualification"],
        "observedModel": staged["observedModel"],
        "processState": staged["processState"],
        "agentDeclaredState": staged["agentDeclaredState"],
        "inputPermissionState": staged["inputPermissionState"],
        "infrastructureValidity": staged["infrastructureValidity"],
        "transcriptDigest": _digest_for(raw_entries, "raw-stream.ndjson"),
        "eventStreamDigest": _digest_for(raw_entries, "hook-events.ndjson"),
        "consumption": staged["consumption"],
        "classification": staged["classification"],
        "redactedEvidenceLocator": "not_redacted",
    }
    if set(run_record_binding) != set(_RUN_RECORD_BINDING_FIELDS):
        _fail("evidence.invalid_raw_manifest", "$.rawEvidenceLocator.runRecordBinding")
    raw_manifest = {
        "schemaVersion": 1,
        "runId": run_id,
        "attemptId": attempt_id,
        "attemptDigest": canonical_contract_digest("ScheduledAttempt", stored_attempt),
        "lifecycleEventDigests": event_digests,
        "conditionDigest": condition_digest,
        "conditionLocator": _artifact_locator(run_id, condition_digest),
        "scenarioDigest": scenario_digest,
        "scenarioLocator": _artifact_locator(run_id, scenario_digest),
        "environmentQualificationDigest": environment_qualification_digest,
        "environmentQualificationLocator": _artifact_locator(run_id, environment_qualification_digest),
        "stagedOutcomeDigest": staged_outcome_digest,
        "stagedOutcomeLocator": _artifact_locator(run_id, staged_outcome_digest),
        "unclassifiedOutcomeDigest": unclassified_outcome_digest,
        "unclassifiedOutcomeLocator": _artifact_locator(run_id, unclassified_outcome_digest),
        "sourceStagingManifestDigest": staged["stagingManifestDigest"],
        "runRecordBinding": run_record_binding,
        "entries": raw_entries,
    }
    raw_manifest_bytes = canonical_bytes(raw_manifest)
    raw_manifest_digest = sha256_digest(raw_manifest_bytes)
    raw_manifest_locator = _artifact_locator(run_id, raw_manifest_digest)
    artifact_payloads.append((raw_manifest_digest, raw_manifest_bytes))

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
    finalized_event = _run_finalized_event(attempt_id, events, run)
    with _open_lifecycle_append_stream(root, attempt_id) as lifecycle_stream:
        _finalize_run_directory(root, run_id, run, artifact_payloads)
        lifecycle_position = lifecycle_stream.tell()
        try:
            _append_run_finalized_event(lifecycle_stream, finalized_event)
        except ContractValidationError as exc:
            if exc.reason_code == "evidence.lifecycle_not_appendable" and _lifecycle_ends_with_event(
                root, attempt_id, finalized_event
            ):
                return run
            _truncate_lifecycle_stream(lifecycle_stream, lifecycle_position)
            _rollback_finalized_run_directory(root, run_id)
            raise
        except Exception:
            _truncate_lifecycle_stream(lifecycle_stream, lifecycle_position)
            _rollback_finalized_run_directory(root, run_id)
            raise
    return run


__all__ = ["import_run"]
