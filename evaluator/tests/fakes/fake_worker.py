from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any


def _digest(seed: str) -> str:
    return "sha256:" + (seed * 64)[:64]


MATRIX: dict[str, dict[str, object]] = {
    "pre_start_auth_failure": {
        "preStartFailure": "authentication",
        "reasonCode": "pre_start_auth_failure",
        "class": "infrastructure_failure",
        "countsInValidRun": False,
        "retryEligible": True,
        "workerProcessState": "not_started",
    },
    "invalid_controller_input": {
        "reasonCode": "invalid_controller_input",
        "class": "infrastructure_failure",
        "countsInValidRun": False,
        "retryEligible": False,
        "workerProcessState": "not_started",
    },
    "valid_start_timeout": {
        "terminalKind": "product_timeout",
        "reasonCode": "product_timeout",
        "class": "product_failure",
        "countsInValidRun": False,
        "retryEligible": False,
        "workerProcessState": "terminated",
        "controllerExitCode": 124,
        "workerExitCode": "none",
        "timeout": True,
    },
    "soft_denial_exit_zero": {
        "terminalKind": "agent_finished",
        "reasonCode": "needs_input",
        "class": "indeterminate",
        "countsInValidRun": False,
        "retryEligible": False,
        "workerProcessState": "terminated",
        "controllerExitCode": 0,
        "workerExitCode": 0,
        "agentDeclaredState": "needs_input",
        "inputPermissionState": "needs_input",
    },
    "safety_refusal": {
        "terminalKind": "agent_finished",
        "reasonCode": "safety_refusal",
        "class": "safety_refusal",
        "countsInValidRun": False,
        "retryEligible": False,
        "workerProcessState": "terminated",
        "agentDeclaredState": "safety_refusal",
    },
    "malformed_ndjson": {
        "terminalKind": "capture_indeterminate",
        "reasonCode": "malformed_ndjson",
        "class": "indeterminate",
        "countsInValidRun": False,
        "retryEligible": True,
        "workerProcessState": "terminated",
        "infrastructureValidity": "capture_malformed",
    },
    "truncated_ndjson": {
        "terminalKind": "capture_indeterminate",
        "reasonCode": "truncated_ndjson",
        "class": "indeterminate",
        "countsInValidRun": False,
        "retryEligible": True,
        "workerProcessState": "terminated",
        "infrastructureValidity": "capture_truncated",
    },
    "grader_leakage": {
        "terminalKind": "capture_indeterminate",
        "reasonCode": "grader_leakage",
        "class": "indeterminate",
        "countsInValidRun": False,
        "retryEligible": False,
        "workerProcessState": "terminated",
        "infrastructureValidity": "grader_leakage_detected",
    },
    "adapter_failure": {
        "terminalKind": "adapter_failure",
        "reasonCode": "adapter_failure",
        "class": "infrastructure_failure",
        "countsInValidRun": False,
        "retryEligible": True,
        "workerProcessState": "terminated",
        "controllerExitCode": 70,
        "workerExitCode": "none",
        "infrastructureValidity": "adapter_failure",
    },
    "budget_exhaustion": {
        "terminalKind": "agent_finished",
        "reasonCode": "budget_exhaustion",
        "class": "product_failure",
        "countsInValidRun": False,
        "retryEligible": False,
        "workerProcessState": "terminated",
        "consumption": {"toolCalls": 20, "wallTimeMs": 600000},
    },
    "tool_misuse": {
        "terminalKind": "agent_finished",
        "reasonCode": "tool_misuse",
        "class": "product_failure",
        "countsInValidRun": False,
        "retryEligible": False,
        "workerProcessState": "terminated",
        "agentDeclaredState": "tool_misuse",
    },
    "test_flake": {
        "terminalKind": "capture_indeterminate",
        "reasonCode": "test_flake",
        "class": "indeterminate",
        "countsInValidRun": False,
        "retryEligible": True,
        "workerProcessState": "terminated",
        "infrastructureValidity": "test_flake",
    },
    "ordinary_artifact_failure": {
        "terminalKind": "agent_finished",
        "reasonCode": "ordinary_artifact_failure",
        "class": "gradable",
        "countsInValidRun": True,
        "retryEligible": False,
        "workerProcessState": "terminated",
        "agentDeclaredState": "artifact_failed",
    },
    "success": {
        "terminalKind": "agent_finished",
        "reasonCode": "success",
        "class": "gradable",
        "countsInValidRun": True,
        "retryEligible": False,
        "workerProcessState": "terminated",
        "agentDeclaredState": "completed",
    },
}


@dataclass
class FakeWorker:
    case_id: str
    invocations: list[dict[str, object]] = field(default_factory=list)

    @property
    def behavior(self) -> dict[str, object]:
        return MATRIX[self.case_id]

    @property
    def pre_start_failure(self) -> str | None:
        value = self.behavior.get("preStartFailure")
        return str(value) if value is not None else None

    def run(self, invocation: dict[str, object]) -> dict[str, object]:
        self.invocations.append(copy.deepcopy(invocation))
        behavior = self.behavior
        consumption = {
            "schemaVersion": 1,
            "inputTokens": "unavailable",
            "outputTokens": "unavailable",
            "cachedTokens": "unavailable",
            "toolCalls": 3,
            "subagentCalls": 0,
            "wallTimeMs": 125000,
            "quotaOrCost": "unavailable",
            "sourceEvidenceDigest": _digest("ce"),
        }
        consumption.update(behavior.get("consumption", {}))
        return {
            "terminalKind": behavior.get("terminalKind", "agent_finished"),
            "controllerExitCode": behavior.get("controllerExitCode", 0),
            "workerExitCode": behavior.get("workerExitCode", 0),
            "signal": behavior.get("signal", "none"),
            "timeout": behavior.get("timeout", False),
            "agentDeclaredState": behavior.get("agentDeclaredState", "completed"),
            "inputPermissionState": behavior.get("inputPermissionState", "permitted"),
            "infrastructureValidity": behavior.get("infrastructureValidity", "valid"),
            "consumption": consumption,
            "observedModel": {
                "schemaVersion": 1,
                "requestedModel": "gemini-3.7-flash-high",
                "requestedReasoning": "high",
                "servedIdentityEvidence": [
                    {
                        "schemaVersion": 1,
                        "source": "cli-init",
                        "value": "unreported",
                        "digest": _digest("ac"),
                    }
                ],
                "fallbackProbeResult": {
                    "schemaVersion": 1,
                    "result": "pass",
                    "evidenceDigest": _digest("bd"),
                },
                "conclusion": "unobservable",
                "limitations": ["Fake worker does not expose a served model identity."],
            },
            "stagedFiles": {
                "raw-stream.ndjson": "{\"type\":\"result\"}\n",
                "process.json": "{}\n",
            },
        }
