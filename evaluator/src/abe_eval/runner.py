"""T007 protected runner staging for evaluator attempts."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import ContractValidationError, canonical_contract_digest, parse_contract


_PREFLIGHT_AT = "2026-08-18T12:09:00Z"
_VALID_START_AT = "2026-08-18T12:10:00Z"
_ENDED_AT = "2026-08-18T12:12:00Z"
_OUTPUT_NAMES = (
    "raw-stream.ndjson",
    "stdout.txt",
    "stderr.txt",
    "process.json",
    "observed-config.json",
    "artifact-manifest.json",
    "repository-before.json",
    "repository-after.json",
    "plugin-discovery.json",
    "hook-events.ndjson",
)


class Worker(Protocol):
    """Small protected runner worker seam used by tests and later adapters."""

    pre_start_failure: str | None

    def run(self, invocation: dict[str, object]) -> dict[str, object]: ...


@dataclass(frozen=True)
class RunAttemptInputs:
    scheduled_attempt: object
    condition: object
    scenario: object
    environment_qualification: object
    raw_root: Path | str


def _fail(reason_code: str, path: str) -> None:
    raise ContractValidationError(reason_code, path)


def _digest_payload(payload: object) -> str:
    return sha256_digest(canonical_bytes(payload))


def _seed_digest(seed: str) -> str:
    return "sha256:" + (seed * 64)[:64]


def _safe_path_segment(value: str, path: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value or "\x00" in value:
        _fail("runner.unsafe_identifier_path", path)
    return value


def _write_json(path: Path, value: object, *, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_bytes(value) + b"\n"
    if path.exists() and not overwrite:
        if path.read_bytes() == data:
            return
        _fail("runner.path_already_exists", "$rawRoot")
    path.write_bytes(data)


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        _fail("runner.path_already_exists", "$rawRoot")
    path.write_text(value)


def _preflight_result(result: str, seed: str) -> dict[str, object]:
    return {"schemaVersion": 1, "result": result, "evidenceDigest": _seed_digest(seed)}


def _attempt_qualification(failed_preflight: str | None, valid_start_at: str) -> dict[str, object]:
    fields = {
        "authentication": "35",
        "fixtureProvisioning": "46",
        "modelPreflight": "57",
        "fallbackProbe": "68",
        "pluginComponentDiscovery": "79",
        "structuredCapturePreflight": "8a",
        "authorityToolInventory": "9b",
    }
    qualification: dict[str, object] = {"schemaVersion": 1}
    for field, seed in fields.items():
        qualification[field] = _preflight_result("fail" if field == failed_preflight else "pass", seed)
    qualification["validStartAt"] = valid_start_at
    return parse_contract("AttemptQualificationRecord", qualification)


def _observed_model(condition: dict[str, object], result: dict[str, object] | None) -> dict[str, object]:
    if result and "observedModel" in result:
        observed = copy.deepcopy(result["observedModel"])
        observed["requestedModel"] = condition["modelRequest"]
        observed["requestedReasoning"] = condition["reasoningRequest"]
        return parse_contract("ObservedModel", observed)
    return parse_contract(
        "ObservedModel",
        {
            "schemaVersion": 1,
            "requestedModel": condition["modelRequest"],
            "requestedReasoning": condition["reasoningRequest"],
            "servedIdentityEvidence": [
                {"schemaVersion": 1, "source": "pre-start", "value": "unreported", "digest": _seed_digest("ac")}
            ],
            "fallbackProbeResult": {"schemaVersion": 1, "result": "indeterminate", "evidenceDigest": _seed_digest("bd")},
            "conclusion": "unobservable",
            "limitations": ["Worker did not reach valid start."],
        },
    )


def _consumption(result: dict[str, object] | None) -> dict[str, object]:
    if result and "consumption" in result:
        return parse_contract("ConsumptionRecord", result["consumption"])
    return parse_contract(
        "ConsumptionRecord",
        {
            "schemaVersion": 1,
            "inputTokens": "unavailable",
            "outputTokens": "unavailable",
            "cachedTokens": "unavailable",
            "toolCalls": "unavailable",
            "subagentCalls": "unavailable",
            "wallTimeMs": 0,
            "quotaOrCost": "unavailable",
            "sourceEvidenceDigest": _seed_digest("ce"),
        },
    )


def _process_state(result: dict[str, object] | None, worker_started: bool) -> dict[str, object]:
    if not worker_started:
        return parse_contract(
            "ProcessState",
            {
                "schemaVersion": 1,
                "workerProcessState": "not_started",
                "controllerExitCode": 64,
                "workerExitCode": "none",
                "signal": "none",
                "timeout": False,
                "startedAt": "none",
                "endedAt": _PREFLIGHT_AT,
                "stderrDigest": _seed_digest("ee"),
            },
        )
    assert result is not None
    return parse_contract(
        "ProcessState",
        {
            "schemaVersion": 1,
            "workerProcessState": result.get("workerProcessState", "terminated"),
            "controllerExitCode": result.get("controllerExitCode", 0),
            "workerExitCode": result.get("workerExitCode", 0),
            "signal": result.get("signal", "none"),
            "timeout": result.get("timeout", False),
            "startedAt": _VALID_START_AT,
            "endedAt": _ENDED_AT,
            "stderrDigest": result.get("stderrDigest", "none"),
        },
    )


def _event(attempt_id: str, sequence: int, phase: str, terminal_kind: str, occurred_at: str, evidence: object) -> dict[str, object]:
    return parse_contract(
        "AttemptLifecycleEvent",
        {
            "schemaVersion": 1,
            "attemptId": attempt_id,
            "sequence": sequence,
            "phase": phase,
            "terminalKind": terminal_kind,
            "occurredAt": occurred_at,
            "evidenceDigest": _digest_payload(evidence),
        },
    )


def _append_lifecycle_event(root: Path, attempt_id: str, event: dict[str, object]) -> None:
    path = root / "attempts" / attempt_id / "lifecycle.ndjson"
    path.parent.mkdir(parents=True, exist_ok=True)
    sequence = int(event["sequence"])
    if sequence == 0 and path.exists():
        _fail("runner.lifecycle_already_exists", "$.attemptId")
    if sequence != 0 and not path.exists():
        _fail("runner.lifecycle_missing", "$.attemptId")
    with path.open("ab") as stream:
        stream.write(canonical_bytes(event) + b"\n")


def _record_lifecycle_event(
    root: Path,
    attempt_id: str,
    events: list[dict[str, object]],
    event: dict[str, object],
) -> None:
    _append_lifecycle_event(root, attempt_id, event)
    events.append(event)


def _resource_caps(scenario: dict[str, Any]) -> dict[str, object]:
    envelope = scenario["resourceEnvelope"]
    return {
        "schemaVersion": 1,
        "wallTimeMs": int(envelope["wallTime"]["cap"]),
        "toolCalls": int(envelope["toolCalls"]["cap"]),
        "subagentCalls": int(envelope["subagentFanOut"]["cap"]),
        "tokens": int(envelope["tokens"]["cap"]),
    }


def _worker_invocation(
    attempt: dict[str, object],
    condition: dict[str, object],
    scenario: dict[str, object],
    environment_digest: str,
) -> dict[str, object]:
    authority = scenario["authorityManifest"]
    return parse_contract(
        "WorkerInvocation",
        {
            "schemaVersion": 1,
            "invocationId": "invocation-" + _digest_payload({"runId": attempt["runId"]}).removeprefix("sha256:")[:32],
            "runId": attempt["runId"],
            "requestPath": "/workspace/input/request.txt",
            "requestDigest": _digest_payload({"agentInput": scenario["agentInput"], "scenarioId": scenario["scenarioId"]}),
            "fixtureDigest": scenario["fixtureDigest"],
            "authorityManifestDigest": canonical_contract_digest("AuthorityManifest", authority),
            "resourceCaps": _resource_caps(scenario),
            "toolPermissionProjection": {
                "schemaVersion": 1,
                "allowedTools": list(authority["allowedActions"]),
                "network": "deny_except_inference",
            },
            "cliPath": "/opt/antigravity/bin/agy",
            "cliDigest": condition["cliDigest"],
            "environmentQualificationDigest": environment_digest,
            "outputPath": "/workspace/output",
        },
    )


def _staging_manifest(root: Path, run_id: str, result: dict[str, object] | None) -> str:
    output_root = root / "staged" / run_id / "output"
    staged_files = dict(result.get("stagedFiles", {})) if result else {}
    entries: list[dict[str, object]] = []
    for name in _OUTPUT_NAMES:
        content = staged_files.get(name)
        if content is None:
            entries.append({"path": name, "present": False, "digest": "none", "byteLength": 0})
            continue
        _write_text(output_root / name, str(content))
        data = str(content).encode("utf-8")
        entries.append({"path": name, "present": True, "digest": sha256_digest(data), "byteLength": len(data)})
    manifest = {"schemaVersion": 1, "runId": run_id, "entries": entries}
    _write_json(root / "staged" / run_id / "staging-manifest.json", manifest)
    return _digest_payload(manifest)


def _controller_input_failure(attempt: dict[str, object], condition: dict[str, object], scenario: dict[str, object]) -> str | None:
    if attempt["conditionId"] != condition["conditionId"]:
        return "fixtureProvisioning"
    if attempt["scenarioId"] != scenario["scenarioId"]:
        return "fixtureProvisioning"
    return None


def run_attempt(inputs: RunAttemptInputs, worker: Worker) -> dict[str, object]:
    """Stage one scheduled attempt through execution_terminal without finalizing a RunRecord."""

    attempt = parse_contract("ScheduledAttempt", inputs.scheduled_attempt)
    condition = parse_contract("ConditionLock", inputs.condition)
    scenario = parse_contract("ScenarioCard", inputs.scenario)
    environment = parse_contract("EnvironmentQualificationRecord", inputs.environment_qualification)
    root = Path(inputs.raw_root)
    attempt_id = _safe_path_segment(str(attempt["attemptId"]), "$.attemptId")
    run_id = _safe_path_segment(str(attempt["runId"]), "$.runId")
    environment_digest = canonical_contract_digest("EnvironmentQualificationRecord", environment)

    attempt_root = root / "attempts" / attempt_id
    _write_json(attempt_root / "attempt.json", attempt)

    failed_preflight = _controller_input_failure(attempt, condition, scenario)
    pre_start_failure = worker.pre_start_failure if failed_preflight is None else None
    if pre_start_failure == "authentication":
        failed_preflight = "authentication"

    events: list[dict[str, object]] = []
    _record_lifecycle_event(root, attempt_id, events, _event(attempt_id, 0, "scheduled", "none", str(attempt["scheduledAt"]), attempt))
    _record_lifecycle_event(
        root,
        attempt_id,
        events,
        _event(attempt_id, 1, "preflight", "none", _PREFLIGHT_AT, {"condition": condition, "scenario": scenario}),
    )
    worker_result: dict[str, object] | None = None
    worker_started = failed_preflight is None
    valid_start_at = "none"
    if worker_started:
        valid_start_at = _VALID_START_AT
        invocation = _worker_invocation(attempt, condition, scenario, environment_digest)
        _record_lifecycle_event(
            root,
            attempt_id,
            events,
            _event(attempt_id, 2, "valid_started", "none", valid_start_at, invocation),
        )
        worker_result = worker.run(invocation)
        terminal_kind = str(worker_result.get("terminalKind", "agent_finished"))
        _record_lifecycle_event(
            root,
            attempt_id,
            events,
            _event(attempt_id, 3, "execution_terminal", terminal_kind, _ENDED_AT, worker_result),
        )
    else:
        _record_lifecycle_event(
            root,
            attempt_id,
            events,
            _event(
                attempt_id,
                2,
                "execution_terminal",
                "preflight_failed",
                _PREFLIGHT_AT,
                {"failedPreflight": failed_preflight or "fixtureProvisioning"},
            ),
        )

    lifecycle_digests = [canonical_contract_digest("AttemptLifecycleEvent", event) for event in events]
    qualification = _attempt_qualification(failed_preflight, valid_start_at)
    process_state = _process_state(worker_result, worker_started)
    infrastructure = "valid"
    if not worker_started:
        infrastructure = "pre_start_auth_failure" if failed_preflight == "authentication" else "invalid_controller_input"
    elif worker_result:
        infrastructure = str(worker_result.get("infrastructureValidity", "valid"))

    outcome = parse_contract(
        "UnclassifiedStagedAttemptOutcome",
        {
            "schemaVersion": 1,
            "attemptId": attempt_id,
            "runId": run_id,
            "conditionDigest": canonical_contract_digest("ConditionLock", condition),
            "scenarioDigest": canonical_contract_digest("ScenarioCard", scenario),
            "environmentQualificationDigest": environment_digest,
            "lifecycleEventDigests": lifecycle_digests,
            "attemptQualification": qualification,
            "observedModel": _observed_model(condition, worker_result),
            "processState": process_state,
            "agentDeclaredState": str(worker_result.get("agentDeclaredState", "none")) if worker_result else "none",
            "inputPermissionState": str(worker_result.get("inputPermissionState", "not_requested")) if worker_result else "not_requested",
            "infrastructureValidity": infrastructure,
            "consumption": _consumption(worker_result),
            "stagingManifestDigest": _staging_manifest(root, run_id, worker_result),
        },
    )
    _write_json(root / "staged" / run_id / "unclassified-outcome.json", outcome)
    return outcome


__all__ = ["RunAttemptInputs", "Worker", "run_attempt"]
