"""Antigravity CLI adapter and live qualification seams."""

from __future__ import annotations

import copy
import json
import os
import platform
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import canonical_contract_digest, parse_contract


_PREFLIGHT_FIELDS = (
    ("authentication", "authentication"),
    ("fixtureProvisioning", "fixture_provisioning"),
    ("modelPreflight", "model_preflight"),
    ("fallbackProbe", "fallback_probe"),
    ("pluginComponentDiscovery", "plugin_component_discovery"),
    ("structuredCapturePreflight", "structured_capture_preflight"),
    ("authorityToolInventory", "authority_tool_inventory"),
)
_TARGET_EFFORTS = {
    "gemini-3.7-flash-high": "high",
    "gemini-3.1-pro-high": "high",
}
_FALLBACK_EFFORTS = {
    "gemini-3.7-flash-high": "medium",
    "gemini-3.1-pro-high": "low",
}


@dataclass(frozen=True)
class AntigravityWorkerHandle:
    """Runtime handle for a single Antigravity CLI qualification context."""

    cli_path: Path | str
    request_path: Path | str
    output_root: Path | str
    cwd: Path | str | None = None
    env: Mapping[str, str] = field(default_factory=dict)
    timeout_seconds: float = 45


@dataclass(frozen=True)
class QualificationResult:
    """Reusable environment qualification plus the protected raw evidence body."""

    environment: dict[str, object]
    raw: dict[str, object]


@dataclass(frozen=True)
class _ProcessOutput:
    argv: tuple[str, ...]
    returncode: int | str
    stdout: str
    stderr: str
    timed_out: bool


class _StreamContractError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    digest = __import__("hashlib").sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _digest_payload(value: object) -> str:
    return sha256_digest(canonical_bytes(value))


def _evidence(result: str, value: object) -> dict[str, object]:
    return {"schemaVersion": 1, "result": result, "evidenceDigest": _digest_payload(value)}


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value) + b"\n")


def _completed(
    argv: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    cwd: Path | str | None = None,
    timeout_seconds: float = 30,
) -> _ProcessOutput:
    if env is None:
        process_env = os.environ.copy()
    else:
        process_env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
        }
        process_env.update({str(key): str(value) for key, value in env.items()})
    try:
        completed = subprocess.run(
            list(argv),
            cwd=str(cwd) if cwd is not None else None,
            env=process_env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
        return _ProcessOutput(tuple(str(part) for part in argv), completed.returncode, completed.stdout, completed.stderr, False)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", "replace")
        stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", "replace")
        return _ProcessOutput(tuple(str(part) for part in argv), "none", stdout, stderr, True)


def _base_argv_from_condition(condition: dict[str, object]) -> tuple[str, ...]:
    raw_invocation = condition["rawInvocation"]
    assert isinstance(raw_invocation, dict)
    raw_argv = raw_invocation["argv"]
    assert isinstance(raw_argv, list)
    if not raw_argv:
        raise ValueError("antigravity.missing_cli_path")
    return tuple(str(part) for part in raw_argv)


def _raw_environment(condition: dict[str, object]) -> dict[str, str]:
    raw_invocation = condition["rawInvocation"]
    assert isinstance(raw_invocation, dict)
    environment = raw_invocation.get("environment", {})
    if not isinstance(environment, dict):
        raise ValueError("antigravity.invalid_raw_environment")
    return {str(key): str(value) for key, value in environment.items()}


def _replace_option(argv: list[str], option: str, value: str) -> None:
    if option in argv:
        index = argv.index(option)
        if index + 1 >= len(argv):
            raise ValueError("antigravity.option_missing_value:" + option)
        argv[index + 1] = value
        return
    argv.extend([option, value])


def _ensure_flag(argv: list[str], flag: str) -> None:
    if flag not in argv:
        argv.append(flag)


def build_argv(condition: object, request_path: Path) -> tuple[str, ...]:
    """Build the Antigravity print-mode argv without shell interpolation."""

    parsed = parse_contract("ConditionLock", condition)
    request = Path(request_path).read_text(encoding="utf-8")
    raw_environment = _raw_environment(parsed)
    argv = list(_base_argv_from_condition(parsed))
    if not argv:
        raise ValueError("antigravity.missing_cli_path")

    _ensure_flag(argv, "--dangerously-skip-permissions")
    _ensure_flag(argv, "--sandbox")
    _ensure_flag(argv, "--disable-slash-commands")
    _replace_option(argv, "-p", request)
    _replace_option(argv, "--model", str(parsed["modelRequest"]))
    _replace_option(argv, "--effort", str(parsed["reasoningRequest"]))
    _replace_option(argv, "--output-format", "stream-json")
    _replace_option(argv, "--log-file", raw_environment.get("AGY_LOG_FILE", "/workspace/output/agy.log"))
    _replace_option(argv, "--print-timeout", raw_environment.get("AGY_PRINT_TIMEOUT", "30s"))
    if "--timeout" in argv:
        raise ValueError("antigravity.actual_cli_uses_print_timeout")
    return tuple(argv)


def _host_log_argv(argv: tuple[str, ...], output_root: Path) -> tuple[str, ...]:
    patched = list(argv)
    _replace_option(patched, "--log-file", str(output_root / "agy.log"))
    return tuple(patched)


def _parse_json_lines(raw_stream: str) -> tuple[list[dict[str, Any]], list[str]]:
    raw_lines = raw_stream.splitlines()
    events: list[dict[str, Any]] = []
    for index, line in enumerate(raw_lines, start=1):
        if not line.strip():
            raise _StreamContractError(f"blank line at {index}")
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise _StreamContractError(f"malformed line at {index}") from exc
        if not isinstance(event, dict) or not isinstance(event.get("event"), str):
            raise _StreamContractError(f"invalid event at {index}")
        events.append(event)
    return events, raw_lines


def _usage(result_event: dict[str, Any]) -> dict[str, int | str]:
    usage = result_event.get("result", {}).get("usage", {}) if isinstance(result_event.get("result"), dict) else {}
    if not isinstance(usage, dict):
        usage = {}
    return {
        "inputTokens": int(usage["input_tokens"]) if isinstance(usage.get("input_tokens"), int) else "unavailable",
        "outputTokens": int(usage["output_tokens"]) if isinstance(usage.get("output_tokens"), int) else "unavailable",
        "cachedTokens": int(usage["cache_read_tokens"]) if isinstance(usage.get("cache_read_tokens"), int) else "unavailable",
        "toolCalls": "unavailable",
        "subagentCalls": "unavailable",
        "wallTimeMs": int(float(result_event.get("result", {}).get("duration_seconds", 0)) * 1000)
        if isinstance(result_event.get("result"), dict)
        else 0,
        "quotaOrCost": "unavailable",
    }


def _stream_summary(
    raw_stream: str,
    *,
    expected_model: str,
    expected_effort: str,
    process: _ProcessOutput,
) -> dict[str, Any]:
    events, _raw_lines = _parse_json_lines(raw_stream)
    init_events = [event for event in events if event["event"] == "init"]
    result_events = [event for event in events if event["event"] == "result"]
    if not init_events:
        raise _StreamContractError("missing init event")
    if len(init_events) != 1:
        raise _StreamContractError("duplicate init event")
    if len(result_events) != 1:
        raise _StreamContractError("missing or duplicate result event")
    init_index = events.index(init_events[0])
    result_index = events.index(result_events[0])
    if result_index < init_index:
        raise _StreamContractError("result before init")

    init = init_events[0].get("init")
    if not isinstance(init, dict):
        raise _StreamContractError("invalid init payload")
    observed_model = init.get("model")
    if observed_model != expected_model:
        raise _StreamContractError("missing or mismatched observable model identity")
    permission_mode = init.get("permission_mode")
    if permission_mode != "always-proceed":
        raise _StreamContractError("missing explicit permission mode")
    result = result_events[0].get("result")
    if not isinstance(result, dict):
        raise _StreamContractError("invalid result payload")
    return {
        "events": [str(event["event"]) for event in events],
        "init": copy.deepcopy(init),
        "result": copy.deepcopy(result),
        "observedModel": str(observed_model),
        "observedEffort": expected_effort,
        "permissionMode": str(permission_mode),
        "tools": [str(tool) for tool in init.get("tools", [])] if isinstance(init.get("tools"), list) else [],
        "processTimedOut": process.timed_out,
    }


def _observed_model_record(
    condition: dict[str, object],
    *,
    identity_value: str,
    source: str,
    fallback_result: str = "indeterminate",
    limitations: list[str] | None = None,
) -> dict[str, object]:
    identity = {"schemaVersion": 1, "source": source, "value": identity_value, "digest": _digest_payload({"source": source, "value": identity_value})}
    return parse_contract(
        "ObservedModel",
        {
            "schemaVersion": 1,
            "requestedModel": condition["modelRequest"],
            "requestedReasoning": condition["reasoningRequest"],
            "servedIdentityEvidence": [identity],
            "fallbackProbeResult": _evidence(fallback_result, {"fallback": fallback_result, "model": condition["modelRequest"]}),
            "conclusion": identity_value,
            "limitations": limitations
            or ["Antigravity stream exposes init.model but no independent provider-served identity field."],
        },
    )


def _unobservable_model_record(condition: dict[str, object], reason: str) -> dict[str, object]:
    return parse_contract(
        "ObservedModel",
        {
            "schemaVersion": 1,
            "requestedModel": condition["modelRequest"],
            "requestedReasoning": condition["reasoningRequest"],
            "servedIdentityEvidence": [
                {"schemaVersion": 1, "source": "stream-contract", "value": "unreported", "digest": _digest_payload(reason)}
            ],
            "fallbackProbeResult": _evidence("indeterminate", {"reason": reason}),
            "conclusion": "unobservable",
            "limitations": [reason],
        },
    )


def _result_from_process(
    condition: dict[str, object],
    process: _ProcessOutput,
    raw_stream: str,
    stderr: str,
    output_root: Path,
    child_env: Mapping[str, str] | None,
) -> dict[str, object]:
    stdout_digest = sha256_digest(raw_stream.encode("utf-8"))
    stderr_digest = sha256_digest(stderr.encode("utf-8")) if stderr else "none"
    log_path = output_root / "agy.log"
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
    log_digest = sha256_digest(log_text.encode("utf-8")) if log_text else "none"
    environment_projection = {
        key: value
        for key, value in _raw_environment(condition).items()
        if key in {"AGY_LOG_FILE", "AGY_PERMISSION_MODE", "AGY_PRINT_TIMEOUT"}
    }
    if child_env:
        environment_projection.update(
            {
                key: str(value)
                for key, value in child_env.items()
                if key in {"HOME", "XDG_CACHE_HOME", "XDG_CONFIG_HOME"}
            }
        )
    log_findings: list[str] = []
    if "not logged into Antigravity" in log_text:
        log_findings.append("antigravity_account_metadata_unavailable")
    if "Model resolved via default" in log_text:
        log_findings.append("model_resolved_via_default")
    process_record = {
        "argv": list(process.argv),
        "workerExitCode": process.returncode,
        "timeout": process.timed_out,
        "stdoutDigest": stdout_digest,
        "stderrDigest": stderr_digest,
        "logDigest": log_digest,
        "logFindings": sorted(log_findings),
        "environmentProjection": environment_projection,
    }
    base: dict[str, object] = {
        "controllerExitCode": 0 if not process.timed_out else 124,
        "workerExitCode": process.returncode,
        "signal": "timeout" if process.timed_out else "none",
        "timeout": process.timed_out,
        "stderrDigest": stderr_digest,
        "workerProcessState": "terminated",
    }

    try:
        summary = _stream_summary(
            raw_stream,
            expected_model=str(condition["modelRequest"]),
            expected_effort=str(condition["reasoningRequest"]),
            process=process,
        )
    except _StreamContractError as exc:
        parsed_events: list[dict[str, Any]] = []
        try:
            parsed_events, _ = _parse_json_lines(raw_stream)
        except _StreamContractError:
            parsed_events = []
        saw_init = any(event.get("event") == "init" for event in parsed_events)
        terminal_kind = "product_timeout" if process.timed_out and saw_init else "capture_indeterminate"
        infrastructure = "capture_truncated" if process.timed_out else "capture_malformed"
        observed = _unobservable_model_record(condition, exc.reason)
        consumption = parse_contract(
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
                "sourceEvidenceDigest": stdout_digest,
            },
        )
        result = {
            **base,
            "terminalKind": terminal_kind,
            "agentDeclaredState": "unknown",
            "inputPermissionState": "unknown",
            "infrastructureValidity": infrastructure,
            "observedModel": observed,
            "consumption": consumption,
            "process": {**base, **process_record},
        }
    else:
        result_payload = summary["result"]
        response = str(result_payload.get("response", ""))
        success = process.returncode == 0 and result_payload.get("status") == "SUCCESS"
        soft_denial = success and any(marker in response.lower() for marker in ("permission denied", "approval required"))
        terminal_kind = "permission_soft_denial" if soft_denial else ("agent_finished" if success else "adapter_failure")
        observed = _observed_model_record(
            condition,
            identity_value=str(summary["observedModel"]),
            source="cli-init.model",
            fallback_result="indeterminate",
        )
        usage = _usage({"result": result_payload})
        consumption = parse_contract(
            "ConsumptionRecord",
            {
                "schemaVersion": 1,
                **usage,
                "sourceEvidenceDigest": stdout_digest,
            },
        )
        result = {
            **base,
            "terminalKind": terminal_kind,
            "agentDeclaredState": "needs_input" if soft_denial else ("completed" if success else "errored"),
            "inputPermissionState": "denied" if soft_denial else "permitted",
            "infrastructureValidity": "valid",
            "observedModel": observed,
            "consumption": consumption,
            "process": {**base, **process_record},
            "streamSummary": summary,
        }

    staged_files = {
        "raw-stream.ndjson": raw_stream,
        "stdout.txt": raw_stream,
        "stderr.txt": stderr,
        "agy.log": log_text,
        "process.json": json.dumps(result["process"], sort_keys=True, separators=(",", ":")) + "\n",
        "observed-config.json": canonical_bytes(result["observedModel"]).decode("utf-8") + "\n",
    }
    manifest = {
        "schemaVersion": 1,
        "entries": [
            {"path": name, "digest": sha256_digest(value.encode("utf-8")), "byteLength": len(value.encode("utf-8"))}
            for name, value in sorted(staged_files.items())
        ],
    }
    staged_files["artifact-manifest.json"] = canonical_bytes(manifest).decode("utf-8") + "\n"
    for name, content in staged_files.items():
        _write_text(output_root / name, content)
    result["stagedFiles"] = staged_files
    return result


def run_antigravity(
    condition: object,
    request_path: Path,
    output_root: Path,
    *,
    timeout_seconds: float = 45,
    env: Mapping[str, str] | None = None,
    cwd: Path | str | None = None,
) -> dict[str, object]:
    """Run one Antigravity print-mode attempt and return the runner worker result."""

    parsed = parse_contract("ConditionLock", condition)
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    argv = _host_log_argv(build_argv(parsed, Path(request_path)), output_root)
    process = _completed(argv, env=env, cwd=cwd, timeout_seconds=timeout_seconds)
    return _result_from_process(parsed, process, process.stdout, process.stderr, output_root, env)


def _probe_argv(cli_path: Path | str, model: str, effort: str, log_file: Path) -> tuple[str, ...]:
    return (
        str(cli_path),
        "--dangerously-skip-permissions",
        "--sandbox",
        "-p",
        "Reply with exactly OK and no extra prose.",
        "--model",
        model,
        "--effort",
        effort,
        "--output-format",
        "stream-json",
        "--log-file",
        str(log_file),
        "--print-timeout",
        "15s",
        "--disable-slash-commands",
    )


def probe_fail_closed(
    cli_path: Path | str,
    *,
    model: str,
    effort: str,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    timeout_seconds: float = 45,
) -> dict[str, object]:
    """Probe a model/effort pair that should fail before a valid start."""

    with tempfile.TemporaryDirectory(prefix="abe-fallback-probe-") as raw_tmp:
        log_file = Path(raw_tmp) / "agy.log"
        process = _completed(_probe_argv(cli_path, model, effort, log_file), env=env, cwd=cwd, timeout_seconds=timeout_seconds)
    valid_start_observed = False
    terminal_status = "missing"
    malformed = False
    events: list[dict[str, Any]] = []
    for line in process.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            malformed = True
            break
        if not isinstance(event, dict) or not isinstance(event.get("event"), str):
            malformed = True
            break
        events.append(event)
    valid_start_observed = any(event.get("event") == "init" for event in events)
    result_events = [event for event in events if event.get("event") == "result"]
    if result_events and isinstance(result_events[0].get("result"), dict):
        terminal_status = str(result_events[0]["result"].get("status", "missing"))
    if malformed:
        terminal_status = "malformed"
    passed = process.returncode != 0 and not valid_start_observed and terminal_status != "SUCCESS"
    return {
        "schemaVersion": 1,
        "probe": model + "/" + effort,
        "result": "pass" if passed else "fail",
        "validStartObserved": valid_start_observed,
        "workerExitCode": process.returncode,
        "timeout": process.timed_out,
        "terminalStatus": terminal_status,
        "rawStream": process.stdout,
        "stderrDigest": sha256_digest(process.stderr.encode("utf-8")) if process.stderr else "none",
        "evidenceDigest": _digest_payload(
            {
                "probe": model + "/" + effort,
                "returncode": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr,
                "timeout": process.timed_out,
            }
        ),
    }


def _command_output(
    cli_path: Path | str,
    argv_tail: Sequence[str],
    *,
    env: Mapping[str, str] | None,
    cwd: Path | str | None,
    timeout_seconds: float = 30,
) -> _ProcessOutput:
    return _completed((str(cli_path), "--dangerously-skip-permissions", *argv_tail), env=env, cwd=cwd, timeout_seconds=timeout_seconds)


def _available_models(handle: AntigravityWorkerHandle) -> dict[str, object]:
    process = _command_output(handle.cli_path, ("models",), env=handle.env, cwd=handle.cwd, timeout_seconds=30)
    models: dict[str, str] = {}
    for line in process.stdout.splitlines():
        if not line.strip() or line.startswith("Fetching "):
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            models[parts[0]] = parts[1]
    return {
        "schemaVersion": 1,
        "returncode": process.returncode,
        "models": models,
        "stdoutDigest": sha256_digest(process.stdout.encode("utf-8")),
        "stderrDigest": sha256_digest(process.stderr.encode("utf-8")) if process.stderr else "none",
    }


def _version(cli_path: Path | str, *, env: Mapping[str, str] | None = None, cwd: Path | str | None = None) -> str:
    process = _completed((str(cli_path), "--version"), env=env, cwd=cwd, timeout_seconds=15)
    if process.returncode != 0:
        raise ValueError("antigravity.version_failed")
    return process.stdout.strip()


def _semver_platform() -> dict[str, object]:
    system = platform.system().lower()
    machine = platform.machine().lower()
    os_name = "macos" if system == "darwin" else ("linux" if system == "linux" else system)
    architecture = "x64" if machine in {"x86_64", "amd64"} else ("arm64" if machine in {"arm64", "aarch64"} else machine)
    return {"schemaVersion": 1, "os": os_name, "architecture": architecture}


def _attempt_record(results: dict[str, str], evidence: Mapping[str, object] | None = None) -> dict[str, object]:
    evidence = evidence or {}
    record: dict[str, object] = {"schemaVersion": 1}
    for field, preflight_id in _PREFLIGHT_FIELDS:
        payload = evidence.get(field, {"preflight": preflight_id, "result": results.get(field, "fail")})
        record[field] = {"schemaVersion": 1, "result": results.get(field, "fail"), "evidenceDigest": _digest_payload(payload)}
    record["validStartAt"] = "none"
    return parse_contract("AttemptQualificationRecord", record)


def preflight_attempt(worker: AntigravityWorkerHandle, condition: object) -> dict[str, object]:
    """Run the seven fail-closed preflights before the valid-start boundary."""

    parsed = parse_contract("ConditionLock", condition)
    evidence: dict[str, object] = {}
    results: dict[str, str] = {}

    try:
        version = _version(worker.cli_path, env=worker.env, cwd=worker.cwd)
        results["authentication"] = "pass" if version else "fail"
        evidence["authentication"] = {"version": version, "source": "binary-version-precheck"}
    except (OSError, ValueError):
        results["authentication"] = "fail"
        evidence["authentication"] = {"error": "version_failed"}

    request_path = Path(worker.request_path)
    results["fixtureProvisioning"] = "pass" if request_path.is_file() else "fail"
    evidence["fixtureProvisioning"] = {"requestPath": str(request_path), "exists": request_path.is_file()}

    catalog = _available_models(worker)
    models = catalog.get("models", {})
    model_available = isinstance(models, dict) and parsed["modelRequest"] in models
    results["modelPreflight"] = "pass" if model_available else "fail"
    evidence["modelPreflight"] = catalog

    bad_model = str(parsed["modelRequest"]) + "-misspelled"
    bad_effort = _FALLBACK_EFFORTS.get(str(parsed["modelRequest"]), "medium")
    fallback_evidence = [
        probe_fail_closed(worker.cli_path, model=bad_model, effort=str(parsed["reasoningRequest"]), cwd=worker.cwd, env=worker.env),
        probe_fail_closed(worker.cli_path, model=str(parsed["modelRequest"]), effort=bad_effort, cwd=worker.cwd, env=worker.env),
    ]
    results["fallbackProbe"] = "pass" if all(item["result"] == "pass" for item in fallback_evidence) else "fail"
    evidence["fallbackProbe"] = fallback_evidence

    plugin = _command_output(worker.cli_path, ("plugin", "list"), env=worker.env, cwd=worker.cwd, timeout_seconds=30)
    results["pluginComponentDiscovery"] = "pass" if plugin.returncode == 0 else "fail"
    evidence["pluginComponentDiscovery"] = {"stdoutDigest": sha256_digest(plugin.stdout.encode("utf-8")), "returncode": plugin.returncode}

    stream = run_antigravity(
        parsed,
        request_path,
        Path(worker.output_root) / "preflight-stream",
        timeout_seconds=worker.timeout_seconds,
        env=worker.env,
        cwd=worker.cwd,
    )
    results["structuredCapturePreflight"] = "pass" if stream["infrastructureValidity"] == "valid" else "fail"
    evidence["structuredCapturePreflight"] = {
        "terminalKind": stream["terminalKind"],
        "infrastructureValidity": stream["infrastructureValidity"],
        "rawStreamDigest": sha256_digest(str(stream["stagedFiles"]["raw-stream.ndjson"]).encode("utf-8")),
    }
    authenticated_inference = stream["terminalKind"] == "agent_finished" and stream["infrastructureValidity"] == "valid"
    results["authentication"] = "pass" if results["authentication"] == "pass" and authenticated_inference else "fail"
    evidence["authentication"] = {
        "version": evidence["authentication"].get("version", "unavailable") if isinstance(evidence.get("authentication"), dict) else "unavailable",
        "source": "bounded-live-inference-preflight",
        "terminalKind": stream["terminalKind"],
        "infrastructureValidity": stream["infrastructureValidity"],
        "logFindings": stream["process"].get("logFindings", []) if isinstance(stream.get("process"), dict) else [],
    }

    agent = _command_output(worker.cli_path, ("agent",), env=worker.env, cwd=worker.cwd, timeout_seconds=30)
    tools = stream.get("streamSummary", {}).get("tools", []) if isinstance(stream.get("streamSummary"), dict) else []
    results["authorityToolInventory"] = "pass" if agent.returncode == 0 and tools else "fail"
    evidence["authorityToolInventory"] = {
        "agentListReturncode": agent.returncode,
        "agentListDigest": sha256_digest(agent.stdout.encode("utf-8")),
        "tools": tools,
    }

    return _attempt_record(results, evidence)


def _condition_for(handle: AntigravityWorkerHandle, model: str, effort: str, cli_digest: str, env_qual_digest: str) -> dict[str, object]:
    fixture = {
        "schemaVersion": 1,
        "conditionId": "qualification-" + model,
        "modelRequest": model,
        "reasoningRequest": effort,
        "provider": "google",
        "authenticationMode": "headless-yolo-disposable-worker",
        "fallbackPolicy": "deny",
        "agentSelection": "antigravity",
        "subagentSelection": "not_applicable",
        "rawInvocation": {
            "schemaVersion": 1,
            "argv": [
                str(handle.cli_path),
                "--dangerously-skip-permissions",
                "--sandbox",
                "--disable-slash-commands",
                "--output-format",
                "stream-json",
                "--print-timeout",
                "30s",
            ],
            "environment": {"AGY_LOG_FILE": "/workspace/output/agy.log", "AGY_PERMISSION_MODE": "always-proceed"},
        },
        "cliDigest": cli_digest,
        "pluginDigest": "none",
        "dependencyDigests": {},
        "enabledComponents": [],
        "authorityManifestDigest": _digest_payload({"authority": "qualification"}),
        "resourceEnvelopeDigest": _digest_payload({"resource": "qualification"}),
        "toolInventoryDigest": _digest_payload({"tools": "qualification"}),
        "permissionDigest": _digest_payload({"permissions": "always-proceed+sandbox"}),
        "environmentDigest": _digest_payload({"environment": "fresh-worker-profile"}),
        "environmentQualificationDigest": env_qual_digest,
    }
    return parse_contract("ConditionLock", fixture)


def _model_key(model: str, effort: str) -> str:
    return model + "/" + effort


def _selected_model_override_present(log_text: str, *, model: str, expected_label: str) -> bool:
    return (
        bool(expected_label)
        and f"Resolving model {model}" in log_text
        and f'Propagating selected model override to backend: label="{expected_label}"' in log_text
    )


def qualify_environment(worker: AntigravityWorkerHandle, protocol: object) -> QualificationResult:
    """Qualify an exact CLI artifact and target model/effort set."""

    parsed_protocol = parse_contract("QualificationProtocol", protocol)
    cli_path = Path(worker.cli_path)
    cli_digest = _sha256_file(cli_path)
    if cli_digest != parsed_protocol["cliArtifactDigest"]:
        raise ValueError("antigravity.cli_digest_mismatch")
    cli_version = _version(cli_path, env=worker.env, cwd=worker.cwd)
    constraint = str(parsed_protocol["cliVersionConstraint"])
    if constraint and constraint[0].isdigit() and cli_version != constraint:
        raise ValueError("antigravity.cli_version_mismatch")

    catalog = _available_models(worker)
    catalog_models = catalog.get("models", {})
    missing_models = [
        str(request["modelRequest"])
        for request in parsed_protocol["modelRequests"]
        if not isinstance(catalog_models, dict) or str(request["modelRequest"]) not in catalog_models
    ]
    catalog["missingModelRequests"] = missing_models

    model_evidence: dict[str, str] = {}
    raw_model_runs: dict[str, object] = {}
    env_qual_seed = _digest_payload({"protocol": parsed_protocol["protocolDigest"], "cliDigest": cli_digest})
    for request in parsed_protocol["modelRequests"]:
        model = str(request["modelRequest"])
        effort = str(request["reasoningRequest"])
        key = _model_key(model, effort)
        condition = _condition_for(worker, model, effort, cli_digest, env_qual_seed)
        run = run_antigravity(
            condition,
            Path(worker.request_path),
            Path(worker.output_root) / "models" / key.replace("/", "_"),
            timeout_seconds=worker.timeout_seconds,
            env=worker.env,
            cwd=worker.cwd,
        )
        stream_summary = run.get("streamSummary", {})
        process_record = run["process"] if isinstance(run.get("process"), dict) else {}
        log_findings = process_record.get("logFindings", [])
        log_text = str(run["stagedFiles"].get("agy.log", "")) if isinstance(run.get("stagedFiles"), dict) else ""
        expected_label = str(catalog_models.get(model, "")) if isinstance(catalog_models, dict) else ""
        model_resolution = {
            "schemaVersion": 1,
            "modelResolvedViaDefault": "model_resolved_via_default" in log_findings,
            "selectedModelOverridePropagated": _selected_model_override_present(
                log_text,
                model=model,
                expected_label=expected_label,
            ),
            "expectedLabel": expected_label,
        }
        raw_record = {
            "schemaVersion": 1,
            "model": model,
            "effort": effort,
            "terminalKind": run["terminalKind"],
            "infrastructureValidity": run["infrastructureValidity"],
            "observedModel": run["observedModel"],
            "modelResolution": model_resolution,
            "stream": {
                "events": stream_summary.get("events", []) if isinstance(stream_summary, dict) else [],
                "rawStream": run["stagedFiles"]["raw-stream.ndjson"],
                "rawStreamDigest": sha256_digest(str(run["stagedFiles"]["raw-stream.ndjson"]).encode("utf-8")),
            },
            "process": run["process"],
            "limitations": run["observedModel"]["limitations"],
        }
        raw_model_runs[key] = raw_record
        model_evidence[key] = _digest_payload(raw_record)

    fallback_results: dict[str, object] = {}
    for probe in parsed_protocol["fallbackProbes"]:
        request = str(probe["request"])
        if "/" not in request:
            raise ValueError("antigravity.invalid_fallback_probe_request")
        model, effort = request.rsplit("/", 1)
        fallback_results[str(probe["probeId"])] = probe_fail_closed(
            cli_path,
            model=model,
            effort=effort,
            cwd=worker.cwd,
            env=worker.env,
            timeout_seconds=worker.timeout_seconds,
        )

    first_request = parsed_protocol["modelRequests"][0]
    representative = _condition_for(
        worker,
        str(first_request["modelRequest"]),
        str(first_request["reasoningRequest"]),
        cli_digest,
        env_qual_seed,
    )
    attempt_qualification = preflight_attempt(worker, representative)
    unverified_model_default = any(
        isinstance(record.get("modelResolution"), dict)
        and record["modelResolution"]["modelResolvedViaDefault"]
        and not record["modelResolution"]["selectedModelOverridePropagated"]
        for record in raw_model_runs.values()
    )
    support_qualified = (
        not missing_models
        and not unverified_model_default
        and
        all(record["terminalKind"] == "agent_finished" and record["infrastructureValidity"] == "valid" for record in raw_model_runs.values())
        and all(result["result"] == "pass" for result in fallback_results.values())
        and all(
            attempt_qualification[field]["result"] == "pass"
            for field, _ in _PREFLIGHT_FIELDS
        )
    )
    limitations = [
        "Antigravity CLI stream exposes init.model but no independent provider-served identity field.",
        "Antigravity CLI 1.1.18 exposes --print-timeout; the runner contract's provisional --timeout spelling is not accepted.",
    ]
    platform_record = parsed_protocol["platforms"][0] if parsed_protocol["platforms"] else _semver_platform()
    environment = parse_contract(
        "EnvironmentQualificationRecord",
        {
            "schemaVersion": 1,
            "qualificationId": "env-qual-" + str(parsed_protocol["protocolId"]),
            "scope": parsed_protocol["customizationScope"],
            "cliVersion": cli_version,
            "cliDigest": cli_digest,
            "imageDigest": parsed_protocol["imageDigest"],
            "platform": platform_record,
            "modelConfigurationEvidence": dict(sorted(model_evidence.items())),
            "unknownModelFallbackEvidence": _digest_payload(fallback_results),
            "structuredCaptureEvidence": _digest_payload(raw_model_runs),
            "pluginLifecycleEvidence": "not_applicable",
            "customizationConformanceEvidence": "not_applicable",
            "authorityToolCapabilityEvidence": _digest_payload(
                {
                    "catalog": catalog,
                    "attemptQualification": attempt_qualification,
                    "tools": [
                        raw_model_runs[key]["stream"]["events"]  # type: ignore[index]
                        for key in sorted(raw_model_runs)
                    ],
                }
            ),
            "supportDecision": "qualified" if support_qualified else "rejected",
            "limitations": limitations,
            "qualifiedAt": _now(),
        },
    )
    raw = {
        "schemaVersion": 1,
        "kind": "AntigravityQualificationEvidence",
        "protocolDigest": parsed_protocol["protocolDigest"],
        "environmentQualification": environment,
        "environmentQualificationDigest": canonical_contract_digest("EnvironmentQualificationRecord", environment),
        "cli": {"path": str(cli_path), "version": cli_version, "digest": cli_digest},
        "catalog": catalog,
        "modelRuns": raw_model_runs,
        "fallbackProbes": fallback_results,
        "representativeAttemptQualification": attempt_qualification,
        "supportDecision": environment["supportDecision"],
        "limitations": limitations,
    }
    return QualificationResult(environment=environment, raw=raw)


def run_matrix(matrix: object, qualification: object) -> tuple[dict[str, object], ...]:
    """Fail closed until materialized scheduler/runner inputs are supplied.

    MatrixLock intentionally contains digests rather than the hidden scenario and
    condition bodies needed to invoke workers. Returning an empty tuple would be
    a false success, so T013 exposes the command surface but refuses to dispatch
    until the later sealed-suite tasks provide those materialized inputs.
    """

    parse_contract("MatrixLock", matrix)
    parse_contract("EnvironmentQualificationRecord", qualification)
    raise ValueError("antigravity.run_matrix_requires_materialized_scheduler_and_runner_inputs")


__all__ = [
    "AntigravityWorkerHandle",
    "QualificationResult",
    "build_argv",
    "preflight_attempt",
    "probe_fail_closed",
    "qualify_environment",
    "run_antigravity",
    "run_matrix",
]
