"""Command-line entry points for deterministic evaluator conformance samples."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from abe_eval.analyze import analyze_attempts
from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.classify import classify
from abe_eval.contracts import ContractValidationError, canonical_contract_digest, parse_contract
from abe_eval.evidence import import_run
from abe_eval.grade import append_grade
from abe_eval.qualify import command_qualify, command_run_matrix
from abe_eval.redact import redact_run
from abe_eval.runner import RunAttemptInputs, run_attempt
from abe_eval.schedule import build_schedule


_BASE_ENVIRONMENT: dict[str, object] = {
    "schemaVersion": 1,
    "qualificationId": "env-qual-evaluator-conformance-001",
    "scope": "release_candidate",
    "platform": {"schemaVersion": 1, "os": "linux", "architecture": "x64"},
    "imageDigest": "sha256:6105d6cc76af400325e94d588ce511be5bfdbb73b437dc51eca43917d7a43e3d",
    "cliVersion": "1.0.0",
    "cliDigest": "sha256:" + "a" * 64,
    "pluginLifecycleEvidence": "sha256:b1e3de3b4c3a15de9e60630eb7531ad0df2397cf7d477504545ad96cb9fdddba",
    "customizationConformanceEvidence": "sha256:412dac876f03f5f5d04de645fbeaf55dc4a0f335f026ed4b209ad232e4a9582a",
    "modelConfigurationEvidence": {
        "gemini-3.1-pro-high/high": "sha256:af30308345d789145d9087a8d6e5037a089e92239bc312bcaba0099bb8e20ba7",
        "gemini-3.7-flash-high/high": "sha256:73f95cf180a19624e4be9a711fd53a90dadfffa410cc9cd2ba1999454a5b99b8",
    },
    "unknownModelFallbackEvidence": "sha256:5c7ee2074b65853f71fc5a01ce194ff26deedf6daacdb715c6beefdfd3f31b35",
    "structuredCaptureEvidence": "sha256:460ee6aa3a80359181b794cc31a7185addba77626e9f719c10e3c8efb8668a1d",
    "authorityToolCapabilityEvidence": "sha256:9c89b182fbab8a63ba3bb24d5101415c2d117c2a861f75c088e5f7e246cf6125",
    "qualifiedAt": "2026-08-18T11:00:00Z",
    "supportDecision": "qualified",
    "limitations": [],
}

_BASE_SCENARIO: dict[str, object] = {
    "schemaVersion": 1,
    "scenarioId": "scenario-evaluator-conformance",
    "family": "evaluator-conformance",
    "partition": "formative",
    "weight": 1,
    "agentInput": "protected/input.txt",
    "fixtureDigest": "sha256:f16d05ec6b29248d2c61adb1e9263f78e4f7bace1b955014a2d17872cfe4064d",
    "startingStateDigest": "sha256:59dbf36d9930a99bfc1e13a10518cd5cf42d29ef9b21993c424b4146a81aa30e",
    "checks": [
        {
            "schemaVersion": 1,
            "checkId": "check-001",
            "kind": "file_exists",
            "inputDigest": "sha256:18119a956a4552ac75990d4c1570266b210ce06c4155071be0bd8f1f724bb9cb",
            "expectedResultDigest": "sha256:039563441c466042eb1c8ce088e316a06287667937be57e4861e749f52daf080",
            "implementationDigest": "sha256:e36d0798938f4d1c92a668d29f6002e87737a0e0a1de316f9c3198327b4111af",
            "timeoutMs": 1000,
        }
    ],
    "materialAmbiguities": ["Synthetic evaluator conformance scenario; no live task ambiguity."],
    "resourceEnvelope": {
        "schemaVersion": 1,
        "envelopeId": "resource-envelope-001",
        "wallTime": {"schemaVersion": 1, "cap": 600000, "median": "not_observable", "p90": "not_observable"},
        "toolCalls": {"schemaVersion": 1, "cap": 20, "median": "not_observable", "p90": "not_observable"},
        "subagentFanOut": {"schemaVersion": 1, "cap": 0, "median": "not_observable", "p90": "not_observable"},
        "tokens": {"schemaVersion": 1, "cap": 100, "median": "not_observable", "p90": "not_observable"},
        "retries": {"schemaVersion": 1, "cap": 1, "median": "not_observable", "p90": "not_observable"},
        "quotaOrCost": "not_observable",
        "overagePolicy": "fail_profile",
        "differentialAttritionLimit": "0.05",
    },
    "authorityManifest": {
        "schemaVersion": 1,
        "manifestId": "authority-001",
        "allowedActions": ["read_fixture", "write_output"],
        "allowedResources": ["/workspace/input", "/workspace/output"],
        "credentialGrantDigests": [],
        "networkPolicyDigest": "sha256:51ca343f4cd77272a62f79d907b06b96a91745503f8c445823cb58f1c88d2628",
        "expiresAt": "not_applicable",
    },
    "classificationPolicyDigest": "sha256:e37d8012ffe55956d37837d66475fe9362591a6f23a70b63cd6d60ce49db054a",
    "applicability": {"verification-before-completion": True},
    "variantProtocolDigest": "not_applicable",
}


def _digest(seed: str) -> str:
    return "sha256:" + (seed * 64)[:64]


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("cli.expected_json_object")
    return value


def _write_json(path: Path, value: dict[str, object]) -> str:
    data = canonical_bytes(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError(str(path))
        return sha256_digest(data[:-1])
    path.write_bytes(data)
    return sha256_digest(data[:-1])


def _emit(value: dict[str, object], *, stream: Any = sys.stdout) -> None:
    stream.write(canonical_bytes(value).decode("utf-8") + "\n")


def _matrix(path: Path) -> dict[str, object]:
    matrix = _load_json(path)
    if matrix.get("schemaVersion") != 1:
        raise TypeError("cli.unsupported_matrix_schema")
    if not isinstance(matrix.get("matrixId"), str) or not matrix["matrixId"]:
        raise TypeError("cli.invalid_matrix_id")
    if not isinstance(matrix.get("seed"), str) or not matrix["seed"]:
        raise TypeError("cli.invalid_matrix_seed")
    if not isinstance(matrix.get("caseOrder"), list) or not all(isinstance(case, str) for case in matrix["caseOrder"]):
        raise TypeError("cli.invalid_case_order")
    if len(matrix["caseOrder"]) != len(set(matrix["caseOrder"])):
        raise TypeError("cli.duplicate_case_id")
    if not isinstance(matrix.get("behaviors"), dict):
        raise TypeError("cli.invalid_behaviors")
    if set(matrix["caseOrder"]) != set(matrix["behaviors"]):
        raise TypeError("cli.case_behavior_mismatch")
    matrix["block"] = parse_contract("BlockSpec", matrix.get("block"))
    matrix["classificationPolicy"] = parse_contract("ClassificationPolicy", matrix.get("classificationPolicy"))
    return matrix


def _scenario(attempt: dict[str, object], policy: dict[str, object]) -> dict[str, object]:
    scenario = copy.deepcopy(_BASE_SCENARIO)
    scenario["scenarioId"] = attempt["scenarioId"]
    scenario["classificationPolicyDigest"] = policy["policyDigest"]
    return parse_contract("ScenarioCard", scenario)


def _environment() -> dict[str, object]:
    return parse_contract("EnvironmentQualificationRecord", copy.deepcopy(_BASE_ENVIRONMENT))


def _condition(condition_id: str, *, environment: dict[str, object], scenario: dict[str, object]) -> dict[str, object]:
    return parse_contract(
        "ConditionLock",
        {
            "schemaVersion": 1,
            "conditionId": condition_id,
            "modelRequest": "gemini-3.7-flash-high",
            "reasoningRequest": "high",
            "provider": "google",
            "authenticationMode": "scoped",
            "fallbackPolicy": "deny",
            "agentSelection": "antigravity",
            "subagentSelection": "not_applicable",
            "rawInvocation": {
                "schemaVersion": 1,
                "argv": ["agy", "--model", "gemini-3.7-flash-high", "--effort", "high"],
                "environment": {"AGY_PROFILE": "fresh"},
            },
            "cliDigest": environment["cliDigest"],
            "pluginDigest": _digest("b"),
            "dependencyDigests": {"superpowers": _digest("c")},
            "enabledComponents": [] if condition_id == "bare" else ["verification-before-completion"],
            "authorityManifestDigest": canonical_contract_digest("AuthorityManifest", scenario["authorityManifest"]),
            "resourceEnvelopeDigest": canonical_contract_digest("ResourceEnvelope", scenario["resourceEnvelope"]),
            "toolInventoryDigest": _digest("f"),
            "permissionDigest": _digest("1"),
            "environmentDigest": _digest("2"),
            "environmentQualificationDigest": canonical_contract_digest("EnvironmentQualificationRecord", environment),
        },
    )


@dataclass
class _MatrixWorker:
    case_id: str
    behavior: dict[str, object]
    invocations: list[dict[str, object]] = field(default_factory=list)

    @property
    def pre_start_failure(self) -> str | None:
        value = self.behavior.get("preStartFailure")
        return str(value) if value is not None else None

    def run(self, invocation: dict[str, object]) -> dict[str, object]:
        self.invocations.append(copy.deepcopy(invocation))
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
        behavior_consumption = self.behavior.get("consumption", {})
        if not isinstance(behavior_consumption, dict):
            raise TypeError("cli.invalid_consumption")
        consumption.update(behavior_consumption)
        return {
            "terminalKind": self.behavior.get("terminalKind", "agent_finished"),
            "controllerExitCode": self.behavior.get("controllerExitCode", 0),
            "workerExitCode": self.behavior.get("workerExitCode", 0),
            "signal": self.behavior.get("signal", "none"),
            "timeout": self.behavior.get("timeout", False),
            "agentDeclaredState": self.behavior.get("agentDeclaredState", "completed"),
            "inputPermissionState": self.behavior.get("inputPermissionState", "permitted"),
            "infrastructureValidity": self.behavior.get("infrastructureValidity", "valid"),
            "consumption": consumption,
            "observedModel": {
                "schemaVersion": 1,
                "requestedModel": "gemini-3.7-flash-high",
                "requestedReasoning": "high",
                "servedIdentityEvidence": [
                    {"schemaVersion": 1, "source": "cli-init", "value": "unreported", "digest": _digest("ac")}
                ],
                "fallbackProbeResult": {"schemaVersion": 1, "result": "pass", "evidenceDigest": _digest("bd")},
                "conclusion": "unobservable",
                "limitations": ["Fake worker does not expose a served model identity."],
            },
            "stagedFiles": {
                "raw-stream.ndjson": "{\"type\":\"result\",\"caseId\":\"" + self.case_id + "\"}\n",
                "process.json": "{}\n",
            },
        }


def _effective_condition_id(attempt_condition_id: object, behavior: dict[str, object]) -> str:
    condition_id = str(attempt_condition_id)
    if behavior.get("controllerInputMismatch") == "condition":
        return "full" if condition_id == "bare" else "bare"
    return condition_id


def _attempts_for(matrix: dict[str, object]) -> list[dict[str, object]]:
    attempts = [parse_contract("ScheduledAttempt", attempt) for attempt in build_schedule(matrix["block"], str(matrix["seed"]))]
    if len(attempts) != len(matrix["caseOrder"]):
        raise TypeError("cli.matrix_attempt_count_mismatch")
    return attempts


def _cmd_fake_matrix(args: argparse.Namespace) -> int:
    matrix = _matrix(Path(args.matrix))
    policy = parse_contract("ClassificationPolicy", matrix["classificationPolicy"])
    raw_root = Path(args.raw_root)
    environment = _environment()
    created: list[dict[str, object]] = []
    attempts = _attempts_for(matrix)
    case_order = list(matrix["caseOrder"])
    behaviors = matrix["behaviors"]
    assert isinstance(behaviors, dict)

    for index, attempt in enumerate(attempts):
        case_id = str(case_order[index])
        behavior_value = behaviors[case_id]
        if not isinstance(behavior_value, dict):
            raise TypeError("cli.invalid_behavior")
        behavior = copy.deepcopy(behavior_value)
        scenario = _scenario(attempt, policy)
        condition = _condition(_effective_condition_id(attempt["conditionId"], behavior), environment=environment, scenario=scenario)
        unclassified = run_attempt(
            RunAttemptInputs(
                scheduled_attempt=attempt,
                condition=condition,
                scenario=scenario,
                environment_qualification=environment,
                raw_root=raw_root,
            ),
            _MatrixWorker(case_id, behavior),
        )
        staged = classify(unclassified, policy, expected_policy_digest=str(policy["policyDigest"]))
        staging = raw_root / "staged" / str(attempt["runId"])
        _write_json(staging / "staged-outcome.json", staged)
        run = import_run(staging, attempt, condition, scenario, environment, raw_root)
        created.append(
            {
                "caseId": case_id,
                "runId": run["runId"],
                "reasonCode": run["classification"]["reasonCode"],
                "classificationClass": run["classification"]["class"],
            }
        )

    _emit(
        {
            "schemaVersion": 1,
            "command": "fake-matrix",
            "matrixId": matrix["matrixId"],
            "runsCreated": len(created),
            "caseIds": [item["caseId"] for item in created],
            "runs": created,
        }
    )
    return 0


def _run_records(raw_root: Path) -> list[dict[str, object]]:
    runs_dir = raw_root / "runs"
    if not runs_dir.is_dir():
        raise FileNotFoundError(str(runs_dir))
    return [parse_contract("RunRecord", _load_json(path)) for path in sorted(runs_dir.glob("*/run.json"))]


def _analysis(path: Path) -> dict[str, object]:
    return parse_contract("AnalysisLock", _load_json(path))


def _fake_grade(run: dict[str, object], analysis: dict[str, object]) -> dict[str, object]:
    passed = run["classification"]["reasonCode"] == "success"
    outcome = "pass" if passed else "fail"
    score = "1.0" if passed else "0.0"
    run_digest = canonical_contract_digest("RunRecord", run)
    grader_digest = sha256_digest(
        canonical_bytes(
            {
                "grader": "fake-matrix-deterministic-grader",
                "analysisLockDigest": canonical_contract_digest("AnalysisLock", analysis),
            }
        )
    )
    return parse_contract(
        "GradeRecord",
        {
            "schemaVersion": 1,
            "gradeId": "grade-" + str(run["runId"]),
            "runId": run["runId"],
            "graderDigest": grader_digest,
            "conditionBlind": True,
            "modelBlind": True,
            "deterministicChecks": [
                {
                    "schemaVersion": 1,
                    "checkId": "fake-matrix-outcome",
                    "implementationDigest": sha256_digest(b"fake-matrix-deterministic-grader-v1"),
                    "outcome": outcome,
                    "reasonCode": str(run["classification"]["reasonCode"]),
                    "evidenceDigest": run_digest,
                    "durationMs": 0,
                }
            ],
            "reviewerGrades": [
                {
                    "schemaVersion": 1,
                    "reviewerId": "fake-matrix-reviewer",
                    "rubricDigest": sha256_digest(b"fake-matrix-rubric-v1"),
                    "calibrationDigest": sha256_digest(b"fake-matrix-calibration-v1"),
                    "dimensionScores": {"task_success": score},
                    "overall": score,
                    "findingIds": [],
                    "limitations": [],
                }
            ],
            "adjudication": "not_required",
            "outcome": outcome,
            "metrics": {"task_success": score},
            "diagnostics": {
                "schemaVersion": 1,
                "repeatedWorkCount": 0,
                "recoveryCount": 0,
                "permissionEvents": 0,
                "firstDivergenceCode": "none",
                "sourceDigest": run_digest,
            },
        },
    )


def _grade_path(raw_root: Path, run: dict[str, object], grade: dict[str, object]) -> Path:
    digest_segment = str(grade["graderDigest"]).removeprefix("sha256:")
    return raw_root / "runs" / str(run["runId"]) / "grades" / digest_segment / "grade.json"


def _cmd_grade(args: argparse.Namespace) -> int:
    raw_root = Path(args.raw_root)
    analysis = _analysis(Path(args.analysis))
    created: list[str] = []
    skipped: list[str] = []
    for run in _run_records(raw_root):
        grade = _fake_grade(run, analysis)
        existing = _grade_path(raw_root, run, grade)
        if existing.exists():
            if parse_contract("GradeRecord", _load_json(existing)) != grade:
                raise FileExistsError(str(existing))
            skipped.append(str(run["runId"]))
            continue
        append_grade(str(run["runId"]), grade, raw_root)
        created.append(str(run["runId"]))
    _emit(
        {
            "schemaVersion": 1,
            "command": "grade",
            "analysisLockDigest": canonical_contract_digest("AnalysisLock", analysis),
            "gradesCreated": len(created),
            "gradesSkipped": len(skipped),
            "runIds": created,
        }
    )
    return 0


def _grades_for(raw_root: Path, run: dict[str, object]) -> list[dict[str, object]]:
    grade_root = raw_root / "runs" / str(run["runId"]) / "grades"
    grades = [parse_contract("GradeRecord", _load_json(path)) for path in sorted(grade_root.glob("*/grade.json"))]
    if not grades:
        raise FileNotFoundError(str(grade_root))
    return grades


def _views(raw_root: Path, runs: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    views: list[dict[str, object]] = []
    for run in runs:
        grades = _grades_for(raw_root, run)
        views.append({"run": run, "gradeOutcomes": [str(grade["outcome"]) for grade in grades]})
    return views


def _public_run_id(policy_id: str, raw_run_id: object) -> str:
    digest = sha256_digest(canonical_bytes({"seed": policy_id, "value": raw_run_id}))
    return "public-run-" + digest.removeprefix("sha256:")[:16]


def _existing_redacted_run(
    public_root: Path, policy: dict[str, object], run: dict[str, object]
) -> dict[str, object] | None:
    policy_id = str(policy["policyId"])
    public_run_id = _public_run_id(policy_id, run["runId"])
    run_path = public_root / "runs" / public_run_id / "run.json"
    manifest_path = public_root / "runs" / public_run_id / "artifacts" / "artifact-manifest.json"
    report_path = public_root / "reports" / policy_id / (public_run_id + "-redaction-report.json")
    paths = (run_path, manifest_path, report_path)
    if not any(path.exists() or path.is_symlink() for path in paths):
        return None
    if not all(path.is_file() and not path.is_symlink() for path in paths):
        raise FileExistsError(str(run_path))

    redacted = parse_contract("RedactedRun", _load_json(run_path))
    manifest = _load_json(manifest_path)
    report = _load_json(report_path)
    if redacted["publicRunId"] != public_run_id:
        raise FileExistsError(str(run_path))
    if redacted["publicConfigurationDigest"] != policy["publicConfigurationDigest"]:
        raise FileExistsError(str(run_path))
    if redacted["scenarioFamilyId"] != policy["scenarioFamilyId"]:
        raise FileExistsError(str(run_path))
    if redacted["processState"] != run["processState"]:
        raise FileExistsError(str(run_path))
    if redacted["classification"] != run["classification"]:
        raise FileExistsError(str(run_path))
    if redacted["consumption"] != run["consumption"]:
        raise FileExistsError(str(run_path))
    if redacted["gradeDigests"] != policy["gradeDigests"]:
        raise FileExistsError(str(run_path))
    if redacted["artifactManifestDigest"] != sha256_digest(canonical_bytes(manifest)):
        raise FileExistsError(str(manifest_path))
    if redacted["redactionReportDigest"] != sha256_digest(canonical_bytes(report)):
        raise FileExistsError(str(report_path))
    return redacted


def _redact_runs(
    output: Path, analysis: dict[str, object], raw_root: Path, runs: list[dict[str, object]]
) -> tuple[list[dict[str, object]], int]:
    public_root = output / "redacted-evidence"
    redacted: list[dict[str, object]] = []
    skipped = 0
    for run in runs:
        grades = _grades_for(raw_root, run)
        policy = {
            "policyId": "fake-scorecard-redaction-" + str(run["runId"]),
            "publicRoot": str(public_root),
            "scenarioFamilyId": str(analysis["familyId"]),
            "publicConfigurationDigest": canonical_contract_digest("AnalysisLock", analysis),
            "gradeDigests": sorted(canonical_contract_digest("GradeRecord", grade) for grade in grades),
            "canaries": [],
        }
        existing = _existing_redacted_run(public_root, policy, run)
        if existing is not None:
            redacted.append(existing)
            skipped += 1
            continue
        redacted.append(redact_run(run, policy))
    return redacted, skipped


def _cmd_report(args: argparse.Namespace) -> int:
    raw_root = Path(args.raw_root)
    output = Path(args.output)
    analysis = _analysis(Path(args.analysis))
    runs = _run_records(raw_root)
    scorecard = analyze_attempts(analysis, _views(raw_root, runs))
    output.mkdir(parents=True, exist_ok=True)
    scorecard_path = output / "scorecard.json"
    scorecard_digest = _write_json(scorecard_path, scorecard)
    redacted, skipped = _redact_runs(output, analysis, raw_root, runs)
    _emit(
        {
            "schemaVersion": 1,
            "command": "report",
            "analysisLockDigest": canonical_contract_digest("AnalysisLock", analysis),
            "scorecardPath": str(scorecard_path),
            "scorecardDigest": scorecard_digest,
            "redactedRuns": len(redacted),
            "redactedRunsSkipped": skipped,
        }
    )
    return 0


def _cmd_qualify(args: argparse.Namespace) -> int:
    raw = command_qualify(
        protocol_path=Path(args.protocol),
        scope=str(args.scope),
        cli_artifact=Path(args.cli_artifact),
        output_path=Path(args.output),
    )
    _emit(
        {
            "schemaVersion": 1,
            "command": "qualify",
            "output": str(args.output),
            "environmentQualificationDigest": raw["environmentQualificationDigest"],
            "supportDecision": raw["supportDecision"],
        }
    )
    return 0


def _cmd_run_matrix(args: argparse.Namespace) -> int:
    runs = command_run_matrix(matrix_path=Path(args.matrix), qualification_path=Path(args.qualification))
    _emit({"schemaVersion": 1, "command": "run-matrix", "runs": len(runs)})
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="abe-eval")
    subcommands = parser.add_subparsers(dest="command", required=True)

    fake_matrix = subcommands.add_parser("fake-matrix")
    fake_matrix.add_argument("--matrix", required=True)
    fake_matrix.add_argument("--raw-root", required=True)
    fake_matrix.set_defaults(func=_cmd_fake_matrix)

    grade = subcommands.add_parser("grade")
    grade.add_argument("--analysis", required=True)
    grade.add_argument("--raw-root", required=True)
    grade.set_defaults(func=_cmd_grade)

    report = subcommands.add_parser("report")
    report.add_argument("--analysis", required=True)
    report.add_argument("--raw-root", required=True)
    report.add_argument("--output", required=True)
    report.set_defaults(func=_cmd_report)

    qualify = subcommands.add_parser("qualify")
    qualify.add_argument("--protocol", required=True)
    qualify.add_argument("--scope", required=True, choices=["cli_core", "release_candidate"])
    qualify.add_argument("--cli-artifact", required=True)
    qualify.add_argument("--output", required=True)
    qualify.set_defaults(func=_cmd_qualify)

    run_matrix_parser = subcommands.add_parser("run-matrix")
    run_matrix_parser.add_argument("--matrix", required=True)
    run_matrix_parser.add_argument("--qualification", required=True)
    run_matrix_parser.set_defaults(func=_cmd_run_matrix)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (ContractValidationError, FileExistsError, FileNotFoundError, json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
        _emit(
            {
                "schemaVersion": 1,
                "command": getattr(args, "command", "unknown"),
                "error": getattr(exc, "reason_code", exc.__class__.__name__),
                "message": str(exc),
            },
            stream=sys.stderr,
        )
        return 2


__all__ = ["main"]
