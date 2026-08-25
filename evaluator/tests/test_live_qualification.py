from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import parse_contract
from abe_eval.antigravity import (
    release_candidate_capture_boundary_digest,
    release_candidate_invocation_boundary_digest,
)


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "evals" / "protocols" / "qualification.json"
RELEASE_PROTOCOL = ROOT / "evals" / "protocols" / "qualification-release-candidate.json"
RELEASE_INPUTS = ROOT / "evals" / "protocols" / "release-candidate-qualification-inputs.json"


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


def test_release_candidate_qualification_protocol_binds_current_cli_worker_and_candidate_without_rewriting_history():
    historical_bytes = PROTOCOL.read_bytes()
    protocol = json.loads(RELEASE_PROTOCOL.read_text(encoding="utf-8"))
    inputs = json.loads(RELEASE_INPUTS.read_text(encoding="utf-8"))

    assert sha256_digest(historical_bytes) == "sha256:a5b5a2693716108f2110372ec2c467298ae24f0d544238fc4f5ba24fd6e8ac6a"
    assert parse_contract("QualificationProtocol", protocol) == protocol
    protocol_body = dict(protocol)
    protocol_body.pop("protocolDigest")
    assert protocol["protocolDigest"] == sha256_digest(canonical_bytes(protocol_body))
    assert protocol["protocolId"] == "qualification-protocol-release-candidate-1.1.19-capture-replacement-2026-08-25"
    assert protocol["cliVersionConstraint"] == "1.1.19"
    assert protocol["cliArtifactDigest"] == "sha256:68d229d37aeabde76d15af0003d4c1ce07b211414e7452fb0309be9714ae7dd4"
    assert protocol["customizationScope"] == "release_candidate"
    assert protocol["releaseCandidateInputsDigest"] == sha256_digest(canonical_bytes(inputs))
    assert parse_contract("ReleaseCandidateQualificationInputs", inputs) == inputs
    assert inputs == {
        "schemaVersion": 1,
        "kind": "ReleaseCandidateQualificationInputs",
        "workerImageDigest": protocol["imageDigest"],
        "candidateArchiveDigest": "sha256:233366d1fd5c2fe513b533fabc106a8683635d95ca6faaf63bd36fb4a8f99d86",
        "packageArchiveRecordDigest": "sha256:6a60aaf430a7e67ac4a178ea5a02199f197b2bdae6e337ea730022ff9b241aa3",
        "packageLockDigest": "sha256:49eed42bf00056e3185bc7f5be0711e9efea7bf1d5297a706260a4e2b5982a3d",
        "behaviorLockDigest": "sha256:697c2556ca922dbda8d81737dc873d8c9261765e44cec99e51ad3c6866c4d624",
        "pluginManifestDigest": "sha256:e860e2f88747c8272e295f2e8e4718e40bd414f4a85a786eb3c94997be7df37e",
        "t032CheckpointDigest": "sha256:68dc66d9ae7fffabaeec3f05143efa7ad1af4335d83ff374164ec0f103433f72",
        "candidateCausalityFreezeDigest": "sha256:eaabda91aea0f2555205bc98ac2337e6c3c6871fc35ba2b4bb1c56d71dd695fa",
        "authorizedCliDigest": protocol["cliArtifactDigest"],
        "invocationBoundaryDigest": release_candidate_invocation_boundary_digest(),
        "captureBoundaryDigest": release_candidate_capture_boundary_digest(),
        "pluginLifecycleSourceEvidenceDigest": "sha256:5ba6c26cdc6165bbc4630fa626104cea85bfaae115b1f436b129f2bc129c49a1",
        "customizationConformanceSourceEvidenceDigest": "sha256:03d9ed7c955178ce32fa77c804236a2f8927285038b04210af36078e62705fc5",
    }


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
