from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import parse_contract


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "evals" / "protocols" / "qualification.json"


def test_committed_qualification_protocol_is_parseable():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))

    assert parse_contract("QualificationProtocol", protocol) == protocol
    protocol_body = dict(protocol)
    protocol_body.pop("protocolDigest")
    assert protocol["protocolDigest"] == sha256_digest(canonical_bytes(protocol_body))
    assert [request["modelRequest"] for request in protocol["modelRequests"]] == [
        "gemini-3.7-flash-high",
        "gemini-3.1-pro-high",
    ]
    assert protocol["requiredPreflights"] == [
        "authentication",
        "fixture_provisioning",
        "model_preflight",
        "fallback_probe",
        "plugin_component_discovery",
        "structured_capture_preflight",
        "authority_tool_inventory",
    ]


def test_live_qualification_command_writes_protected_output_when_explicitly_enabled(tmp_path):
    cli_artifact = os.environ.get("ABE_AUTHORIZED_CLI_PATH")
    if not cli_artifact or os.environ.get("ABE_RUN_LIVE_QUALIFICATION") != "1":
        pytest.skip("Set ABE_RUN_LIVE_QUALIFICATION=1 and ABE_AUTHORIZED_CLI_PATH to run the live CLI probe")

    output = tmp_path / "qualification.json"
    completed = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            "evaluator",
            "abe-eval",
            "qualify",
            "--protocol",
            str(PROTOCOL),
            "--scope",
            "cli_core",
            "--cli-artifact",
            cli_artifact,
            "--output",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )

    assert completed.returncode == 0, completed.stderr
    raw = json.loads(output.read_text(encoding="utf-8"))
    assert parse_contract("EnvironmentQualificationRecord", raw["environmentQualification"]) == raw[
        "environmentQualification"
    ]
    assert raw["environmentQualification"]["supportDecision"] == "qualified"
    assert raw["environmentQualification"]["scope"] == "cli_core"
    assert set(raw["environmentQualification"]["modelConfigurationEvidence"]) == {
        "gemini-3.1-pro-high/high",
        "gemini-3.7-flash-high/high",
    }
