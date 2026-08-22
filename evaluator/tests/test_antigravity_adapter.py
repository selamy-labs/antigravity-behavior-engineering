from __future__ import annotations

import copy
import json
import os
import stat
import subprocess
import textwrap
from pathlib import Path

import pytest

from abe_eval.antigravity import (
    AntigravityWorkerHandle,
    build_argv,
    preflight_attempt,
    probe_fail_closed,
    qualify_environment,
    run_antigravity,
)
from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.cli import main
from abe_eval.contracts import canonical_contract_digest, parse_contract


FIXTURES = Path("tests/contract/fixtures/evaluation-contracts.json")
TARGETS = (
    ("gemini-3.7-flash-high", "high"),
    ("gemini-3.1-pro-high", "high"),
)


def _digest(seed: str) -> str:
    return "sha256:" + (seed * 64)[:64]


def _case_value(name: str) -> dict[str, object]:
    cases = json.loads(FIXTURES.read_text(encoding="utf-8"))["validCases"]
    return copy.deepcopy(next(case["value"] for case in cases if case["name"] == name))


def _condition(cli_path: Path, *, model: str = "gemini-3.7-flash-high", effort: str = "high") -> dict[str, object]:
    condition = _case_value("ConditionLock")
    condition["modelRequest"] = model
    condition["reasoningRequest"] = effort
    condition["authenticationMode"] = "headless-yolo-disposable-worker"
    condition["rawInvocation"] = {
        "schemaVersion": 1,
        "argv": [
            str(cli_path),
            "--dangerously-skip-permissions",
            "--sandbox",
            "--disable-slash-commands",
            "--output-format",
            "stream-json",
            "--print-timeout",
            "30s",
        ],
        "environment": {
            "AGY_LOG_FILE": "/workspace/output/agy.log",
            "AGY_PERMISSION_MODE": "always-proceed",
        },
    }
    return parse_contract("ConditionLock", condition)


def _protocol(cli_digest: str = "sha256:" + "a" * 64, image_digest: str = "sha256:" + "b" * 64) -> dict[str, object]:
    protocol = _case_value("QualificationProtocol")
    protocol["protocolId"] = "qualification-protocol-t013-test"
    protocol["customizationScope"] = "cli_core"
    protocol["cliVersionConstraint"] = "1.1.18"
    protocol["cliArtifactDigest"] = cli_digest
    protocol["imageDigest"] = image_digest
    protocol["modelRequests"] = [
        {"schemaVersion": 1, "modelRequest": model, "reasoningRequest": effort}
        for model, effort in TARGETS
    ]
    protocol["fallbackProbes"] = [
        {
            "schemaVersion": 1,
            "probeId": "unknown-model-gemini-3.7-flash-high",
            "request": "gemini-3.7-flash-high-misspelled/high",
            "evidenceDigest": _digest("1"),
        },
        {
            "schemaVersion": 1,
            "probeId": "altered-reasoning-gemini-3.7-flash-high",
            "request": "gemini-3.7-flash-high/medium",
            "evidenceDigest": _digest("2"),
        },
        {
            "schemaVersion": 1,
            "probeId": "unknown-model-gemini-3.1-pro-high",
            "request": "gemini-3.1-pro-high-misspelled/high",
            "evidenceDigest": _digest("3"),
        },
        {
            "schemaVersion": 1,
            "probeId": "altered-reasoning-gemini-3.1-pro-high",
            "request": "gemini-3.1-pro-high/low",
            "evidenceDigest": _digest("4"),
        },
    ]
    body = copy.deepcopy(protocol)
    body["protocolDigest"] = "sha256:" + "0" * 64
    body.pop("protocolDigest")
    protocol["protocolDigest"] = sha256_digest(canonical_bytes(body))
    return parse_contract("QualificationProtocol", protocol)


def _fake_agy(tmp_path: Path) -> Path:
    script = tmp_path / "fake-agy.py"
    script.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json
            import os
            import sys
            import time

            TARGETS = [
                ("gemini-3.7-flash-high", "Gemini 3.7 Flash (High)"),
                ("gemini-3.1-pro-high", "Gemini 3.1 Pro (High)"),
            ]
            TARGET_LABELS = dict(TARGETS)

            def arg(name, default=""):
                if name not in sys.argv:
                    return default
                index = sys.argv.index(name)
                if index + 1 >= len(sys.argv):
                    return default
                return sys.argv[index + 1]

            def emit(value):
                print(json.dumps(value, separators=(",", ":")), flush=True)

            if "--version" in sys.argv:
                print("1.1.18")
                raise SystemExit(0)

            if "models" in sys.argv:
                targets = TARGETS
                if os.environ.get("ABE_FAKE_AGY_CATALOG") == "flash-only":
                    targets = TARGETS[:1]
                for slug, label in targets:
                    print(f"{slug}\\t{label}")
                raise SystemExit(0)

            if "plugin" in sys.argv and "list" in sys.argv:
                print("no plugins installed")
                raise SystemExit(0)

            if "agent" in sys.argv or "agents" in sys.argv:
                print("default\\tDefault agent")
                raise SystemExit(0)

            mode = os.environ.get("ABE_FAKE_AGY_MODE", "success")
            model = arg("--model")
            effort = arg("--effort")
            log_file = arg("--log-file")
            if log_file:
                with open(log_file, "w", encoding="utf-8") as stream:
                    stream.write(f"fake log model={model} effort={effort} mode={mode}\\n")
                    if mode in {"default_model", "default_model_with_override"}:
                        stream.write(f"Model ID {model} not in local config, defaulting to CCPA\\n")
                        stream.write("Model resolved via default\\n")
                    if mode == "default_model_with_override":
                        label = TARGET_LABELS.get(model, "unknown")
                        stream.write(f"Resolving model {model}\\n")
                        stream.write(f"Propagating selected model override to backend: label=\\"{label}\\"\\n")

            if mode == "init_then_malformed_failure":
                emit({"event":"init","conversation_id":"fake-conversation","init":{"model":model,"cwd":os.getcwd(),"tools":["finish"],"permission_mode":"always-proceed"}})
                print("{not-json", flush=True)
                raise SystemExit(1)

            if model not in {slug for slug, _ in TARGETS}:
                emit({"event":"result","result":{"conversation_id":"","status":"ERROR","response":"","error":"invalid model selection","duration_seconds":0,"num_turns":0,"usage":{"input_tokens":0,"output_tokens":0,"thinking_tokens":0,"cache_read_tokens":0,"total_tokens":0}}})
                raise SystemExit(1)
            if (model.endswith("-high") and effort != "high") or (model == "gemini-3.1-pro-high" and effort != "high"):
                emit({"event":"result","result":{"conversation_id":"","status":"ERROR","response":"","error":"model effort conflict","duration_seconds":0,"num_turns":0,"usage":{"input_tokens":0,"output_tokens":0,"thinking_tokens":0,"cache_read_tokens":0,"total_tokens":0}}})
                raise SystemExit(1)

            init = {"event":"init","conversation_id":"fake-conversation","init":{"model":model,"cwd":os.getcwd(),"tools":["finish","run_command","read_resource"],"permission_mode":"always-proceed"}}
            if mode == "missing_identity":
                init["init"].pop("model")
            result = {"event":"result","result":{"conversation_id":"fake-conversation","status":"SUCCESS","response":"OK\\n","duration_seconds":1,"num_turns":1,"usage":{"input_tokens":11,"output_tokens":2,"thinking_tokens":1,"cache_read_tokens":3,"total_tokens":13}}}

            if mode == "stderr":
                print("diagnostic on stderr", file=sys.stderr, flush=True)
            if mode == "dump_env":
                emit(init)
                env_result = dict(result)
                env_result["result"] = dict(result["result"])
                env_result["result"]["response"] = json.dumps(dict(os.environ), sort_keys=True)
                emit(env_result)
                raise SystemExit(0)
            if mode == "malformed":
                emit(init)
                print("{not-json", flush=True)
                emit(result)
                raise SystemExit(0)
            if mode == "duplicate_init":
                emit(init)
                emit(init)
                emit(result)
                raise SystemExit(0)
            if mode == "duplicate_result":
                emit(init)
                emit(result)
                emit(result)
                raise SystemExit(0)
            if mode == "out_of_order":
                emit(result)
                emit(init)
                raise SystemExit(0)
            if mode == "soft_denial":
                emit(init)
                denied = dict(result)
                denied["result"] = dict(result["result"])
                denied["result"]["response"] = "Permission denied: command approval required.\\n"
                emit(denied)
                raise SystemExit(0)
            if mode == "timeout":
                emit(init)
                time.sleep(10)
                raise SystemExit(0)

            emit(init)
            emit({"event":"step_update","step_update":{"conversation_id":"fake-conversation","step_index":0,"state":"DONE","step_type":"user_input"}})
            emit(result)
            raise SystemExit(0)
            """
        ),
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def _request(tmp_path: Path, text: str = "Reply with OK.") -> Path:
    request = tmp_path / "request.txt"
    request.write_text(text, encoding="utf-8")
    return request


def _run_fake(
    tmp_path: Path,
    *,
    mode: str = "success",
    model: str = "gemini-3.7-flash-high",
    effort: str = "high",
    timeout_seconds: float = 2,
) -> dict[str, object]:
    fake = _fake_agy(tmp_path)
    env = {"ABE_FAKE_AGY_MODE": mode}
    return run_antigravity(
        _condition(fake, model=model, effort=effort),
        _request(tmp_path),
        tmp_path / "output",
        timeout_seconds=timeout_seconds,
        env=env,
        cwd=tmp_path,
    )


def test_build_argv_uses_one_prompt_argument_and_explicit_headless_permissions(tmp_path):
    fake = _fake_agy(tmp_path)
    request = _request(tmp_path, "hello; touch /tmp/pwned && $(whoami)")

    argv = build_argv(_condition(fake), request)

    assert isinstance(argv, tuple)
    assert argv[0] == str(fake)
    assert argv[argv.index("-p") + 1] == "hello; touch /tmp/pwned && $(whoami)"
    assert "--dangerously-skip-permissions" in argv
    assert "--sandbox" in argv
    assert "--disable-slash-commands" in argv
    assert argv[argv.index("--model") + 1] == "gemini-3.7-flash-high"
    assert argv[argv.index("--effort") + 1] == "high"
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert argv[argv.index("--print-timeout") + 1] == "30s"
    assert ";" not in argv[: argv.index("-p")]


def test_successful_stream_preserves_raw_lines_and_returns_runner_worker_result(tmp_path):
    result = _run_fake(tmp_path)

    assert result["terminalKind"] == "agent_finished"
    assert result["agentDeclaredState"] == "completed"
    assert result["inputPermissionState"] == "permitted"
    assert result["infrastructureValidity"] == "valid"
    assert result["process"]["workerExitCode"] == 0
    assert result["consumption"]["inputTokens"] == 11
    assert result["consumption"]["outputTokens"] == 2
    assert result["observedModel"]["requestedModel"] == "gemini-3.7-flash-high"
    assert result["observedModel"]["requestedReasoning"] == "high"
    assert result["observedModel"]["servedIdentityEvidence"][0]["source"] == "cli-init.model"
    assert result["observedModel"]["servedIdentityEvidence"][0]["value"] == "gemini-3.7-flash-high"
    assert result["observedModel"]["conclusion"] == "gemini-3.7-flash-high"
    raw_lines = result["stagedFiles"]["raw-stream.ndjson"].splitlines()
    assert [json.loads(line)["event"] for line in raw_lines] == ["init", "step_update", "result"]
    assert (tmp_path / "output" / "raw-stream.ndjson").read_text(encoding="utf-8") == result["stagedFiles"][
        "raw-stream.ndjson"
    ]


@pytest.mark.parametrize("mode", ["malformed", "duplicate_init", "duplicate_result", "out_of_order", "missing_identity"])
def test_stream_contract_failures_are_preserved_as_capture_malformed(tmp_path, mode):
    result = _run_fake(tmp_path, mode=mode)

    assert result["terminalKind"] == "capture_indeterminate"
    assert result["agentDeclaredState"] == "unknown"
    assert result["inputPermissionState"] == "unknown"
    assert result["infrastructureValidity"] == "capture_malformed"
    assert result["observedModel"]["conclusion"] == "unobservable"
    assert result["stagedFiles"]["raw-stream.ndjson"]


def test_exit_zero_soft_denial_is_not_reported_as_agent_finished(tmp_path):
    result = _run_fake(tmp_path, mode="soft_denial")

    assert result["process"]["workerExitCode"] == 0
    assert result["terminalKind"] == "permission_soft_denial"
    assert result["agentDeclaredState"] == "needs_input"
    assert result["inputPermissionState"] == "denied"
    assert result["infrastructureValidity"] == "valid"


def test_timeout_after_init_is_capture_truncated_with_raw_init_preserved(tmp_path):
    result = _run_fake(tmp_path, mode="timeout", timeout_seconds=0.25)

    assert result["process"]["timeout"] is True
    assert result["process"]["workerExitCode"] == "none"
    assert result["terminalKind"] == "product_timeout"
    assert result["infrastructureValidity"] == "capture_truncated"
    assert json.loads(result["stagedFiles"]["raw-stream.ndjson"].splitlines()[0])["event"] == "init"


def test_stderr_is_preserved_and_digested_without_turning_success_into_failure(tmp_path):
    result = _run_fake(tmp_path, mode="stderr")

    assert result["terminalKind"] == "agent_finished"
    assert result["process"]["stderrDigest"] == sha256_digest(b"diagnostic on stderr\n")
    assert result["stagedFiles"]["stderr.txt"] == "diagnostic on stderr\n"
    assert result["process"]["logDigest"] == sha256_digest(
        b"fake log model=gemini-3.7-flash-high effort=high mode=stderr\n"
    )
    assert result["stagedFiles"]["agy.log"] == "fake log model=gemini-3.7-flash-high effort=high mode=stderr\n"
    assert result["process"]["environmentProjection"] == {
        "AGY_LOG_FILE": "/workspace/output/agy.log",
        "AGY_PERMISSION_MODE": "always-proceed",
    }


def test_child_process_environment_is_allowlisted_not_parent_inherited(tmp_path, monkeypatch):
    monkeypatch.setenv("ABE_REVIEW_SENTINEL_SECRET", "must-not-leak")

    result = _run_fake(tmp_path, mode="dump_env")

    assert "ABE_REVIEW_SENTINEL_SECRET" not in result["stagedFiles"]["raw-stream.ndjson"]


def test_fallback_probe_fails_if_valid_start_precedes_malformed_failure(tmp_path):
    fake = _fake_agy(tmp_path)
    evidence = probe_fail_closed(
        fake,
        model="gemini-3.7-flash-high-misspelled",
        effort="high",
        cwd=tmp_path,
        env={"ABE_FAKE_AGY_MODE": "init_then_malformed_failure"},
    )

    assert evidence["result"] == "fail"
    assert evidence["validStartObserved"] is True


@pytest.mark.parametrize(
    ("model", "effort"),
    [
        ("gemini-3.7-flash-high-misspelled", "high"),
        ("gemini-3.7-flash-high", "medium"),
        ("gemini-3.1-pro-high-misspelled", "high"),
        ("gemini-3.1-pro-high", "low"),
    ],
)
def test_fallback_probes_fail_before_valid_start_for_unknown_model_and_reasoning_mismatch(tmp_path, model, effort):
    fake = _fake_agy(tmp_path)
    evidence = probe_fail_closed(fake, model=model, effort=effort, cwd=tmp_path)

    assert evidence["result"] == "pass"
    assert evidence["validStartObserved"] is False
    assert evidence["workerExitCode"] == 1
    assert "invalid model selection" in evidence["rawStream"] or "model effort conflict" in evidence["rawStream"]


def test_preflight_attempt_records_all_seven_checks_before_valid_start(tmp_path):
    fake = _fake_agy(tmp_path)
    condition = _condition(fake)
    handle = AntigravityWorkerHandle(
        cli_path=fake,
        request_path=_request(tmp_path),
        output_root=tmp_path / "output",
        cwd=tmp_path,
        env={},
    )

    qualification = preflight_attempt(handle, condition)

    assert parse_contract("AttemptQualificationRecord", qualification) == qualification
    assert qualification["validStartAt"] == "none"
    assert {
        "authentication",
        "fixtureProvisioning",
        "modelPreflight",
        "fallbackProbe",
        "pluginComponentDiscovery",
        "structuredCapturePreflight",
        "authorityToolInventory",
    } == {key for key in qualification if key not in {"schemaVersion", "validStartAt"}}
    assert all(qualification[key]["result"] == "pass" for key in qualification if key not in {"schemaVersion", "validStartAt"})


def test_qualify_environment_freezes_model_evidence_and_reusable_environment_record(tmp_path):
    fake = _fake_agy(tmp_path)
    cli_digest = sha256_digest(fake.read_bytes())
    protocol = _protocol(cli_digest=cli_digest)
    handle = AntigravityWorkerHandle(
        cli_path=fake,
        request_path=_request(tmp_path),
        output_root=tmp_path / "qualification-output",
        cwd=tmp_path,
        env={},
    )

    qualification = qualify_environment(handle, protocol)

    assert parse_contract("EnvironmentQualificationRecord", qualification.environment) == qualification.environment
    assert qualification.environment["scope"] == "cli_core"
    assert qualification.environment["cliVersion"] == "1.1.18"
    assert qualification.environment["cliDigest"] == cli_digest
    assert qualification.environment["imageDigest"] == protocol["imageDigest"]
    assert qualification.environment["supportDecision"] == "qualified"
    assert set(qualification.environment["modelConfigurationEvidence"]) == {
        "gemini-3.1-pro-high/high",
        "gemini-3.7-flash-high/high",
    }
    assert qualification.raw["environmentQualificationDigest"] == canonical_contract_digest(
        "EnvironmentQualificationRecord", qualification.environment
    )
    assert qualification.raw["protocolDigest"] == protocol["protocolDigest"]
    assert qualification.raw["modelRuns"]["gemini-3.7-flash-high/high"]["stream"]["events"] == [
        "init",
        "step_update",
        "result",
    ]


def test_qualify_environment_rejects_protocol_model_missing_from_live_catalog(tmp_path):
    fake = _fake_agy(tmp_path)
    cli_digest = sha256_digest(fake.read_bytes())
    protocol = _protocol(cli_digest=cli_digest)
    handle = AntigravityWorkerHandle(
        cli_path=fake,
        request_path=_request(tmp_path),
        output_root=tmp_path / "qualification-output",
        cwd=tmp_path,
        env={"ABE_FAKE_AGY_CATALOG": "flash-only"},
    )

    qualification = qualify_environment(handle, protocol)

    assert qualification.environment["supportDecision"] == "rejected"
    assert qualification.raw["catalog"]["missingModelRequests"] == ["gemini-3.1-pro-high"]


def test_qualify_environment_rejects_successful_stream_with_model_default_log(tmp_path):
    fake = _fake_agy(tmp_path)
    cli_digest = sha256_digest(fake.read_bytes())
    protocol = _protocol(cli_digest=cli_digest)
    handle = AntigravityWorkerHandle(
        cli_path=fake,
        request_path=_request(tmp_path),
        output_root=tmp_path / "qualification-output",
        cwd=tmp_path,
        env={"ABE_FAKE_AGY_MODE": "default_model"},
    )

    qualification = qualify_environment(handle, protocol)

    assert qualification.environment["supportDecision"] == "rejected"
    for run in qualification.raw["modelRuns"].values():
        assert run["terminalKind"] == "agent_finished"
        assert run["infrastructureValidity"] == "valid"
        assert "model_resolved_via_default" in run["process"]["logFindings"]


def test_qualify_environment_accepts_provider_default_with_exact_selected_model_override(tmp_path):
    fake = _fake_agy(tmp_path)
    cli_digest = sha256_digest(fake.read_bytes())
    protocol = _protocol(cli_digest=cli_digest)
    handle = AntigravityWorkerHandle(
        cli_path=fake,
        request_path=_request(tmp_path),
        output_root=tmp_path / "qualification-output",
        cwd=tmp_path,
        env={"ABE_FAKE_AGY_MODE": "default_model_with_override"},
    )

    qualification = qualify_environment(handle, protocol)

    assert qualification.environment["supportDecision"] == "qualified"
    for run in qualification.raw["modelRuns"].values():
        assert run["modelResolution"]["modelResolvedViaDefault"] is True
        assert run["modelResolution"]["selectedModelOverridePropagated"] is True
        assert run["modelResolution"]["expectedLabel"].startswith("Gemini ")


def test_qualify_cli_writes_protected_raw_output_with_fake_cli(tmp_path):
    fake = _fake_agy(tmp_path)
    protocol = _protocol(cli_digest=sha256_digest(fake.read_bytes()))
    protocol_path = tmp_path / "qualification-protocol.json"
    protocol_path.write_bytes(canonical_bytes(protocol) + b"\n")
    output = tmp_path / "evidence" / "raw" / "qualification" / "local" / "qualification.json"

    status = main(
        [
            "qualify",
            "--protocol",
            str(protocol_path),
            "--scope",
            "cli_core",
            "--cli-artifact",
            str(fake),
            "--output",
            str(output),
        ]
    )

    assert status == 0
    raw = json.loads(output.read_text(encoding="utf-8"))
    assert raw["environmentQualificationDigest"] == canonical_contract_digest(
        "EnvironmentQualificationRecord", raw["environmentQualification"]
    )
    assert raw["supportDecision"] == "qualified"


def test_run_matrix_cli_fails_closed_until_materialized_runner_inputs_exist(tmp_path):
    matrix = _case_value("MatrixLock")
    qualification = _case_value("EnvironmentQualificationRecord")
    matrix_path = tmp_path / "matrix.json"
    qualification_path = tmp_path / "qualification.json"
    matrix_path.write_bytes(canonical_bytes(matrix) + b"\n")
    qualification_path.write_bytes(canonical_bytes({"environmentQualification": qualification}) + b"\n")

    assert main(["run-matrix", "--matrix", str(matrix_path), "--qualification", str(qualification_path)]) == 2
