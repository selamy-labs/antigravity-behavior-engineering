"""Deterministic formative replay for earned skill-ablation candidates."""

from __future__ import annotations

import copy
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import ContractValidationError, canonical_contract_digest, parse_contract


MATRIX_TYPE = "skill-ablation-formative"
ANALYSIS_TYPE = "skill-ablation-formative-analysis"
TARGET_MODELS = ("gemini-3.1-pro-high", "gemini-3.7-flash-high")
TARGET_REASONING = "high"
INCUMBENT_BEFORE = "incumbent-before"
INCUMBENT_MINUS = "incumbent-minus"
INCUMBENT_PLUS = "incumbent-plus"
MATCHED_PAIR = (INCUMBENT_MINUS, INCUMBENT_PLUS)
_COMPONENT_RE = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$")


def _fail(reason_code: str, path: str = "$") -> None:
    raise ContractValidationError(reason_code, path)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_json(path: Path | str) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        _fail("skill_ablation.expected_json_object")
    return value


def _write_json(path: Path, value: Mapping[str, object], *, overwrite: bool = False) -> str:
    data = canonical_bytes(dict(value)) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        if path.read_bytes() != data:
            raise FileExistsError(str(path))
        return sha256_digest(data[:-1])
    path.write_bytes(data)
    return sha256_digest(data[:-1])


def _assert_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value:
        _fail("skill_ablation.invalid_field", path)
    return value


def _assert_component(value: object, path: str) -> str:
    component = _assert_string(value, path)
    if _COMPONENT_RE.fullmatch(component) is None:
        _fail("skill_ablation.invalid_component", path)
    return component


def _assert_mapping(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("skill_ablation.invalid_field", path)
    return copy.deepcopy(value)


def _assert_list(value: object, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail("skill_ablation.invalid_field", path)
    return copy.deepcopy(value)


def _normalize_qualification(value: object) -> dict[str, object]:
    if isinstance(value, dict) and "environmentQualification" in value:
        value = value["environmentQualification"]
    qualification = parse_contract("EnvironmentQualificationRecord", value)
    if qualification["supportDecision"] != "qualified":
        _fail("skill_ablation.unqualified_environment", "$.qualification.supportDecision")
    missing = [
        model + "/" + TARGET_REASONING
        for model in TARGET_MODELS
        if model + "/" + TARGET_REASONING not in qualification["modelConfigurationEvidence"]
    ]
    if missing:
        _fail("skill_ablation.model_not_qualified", "$.qualification.modelConfigurationEvidence")
    return qualification


def load_skill_ablation_matrix(path: Path | str | Mapping[str, object]) -> dict[str, object]:
    value = _load_json(path) if isinstance(path, (str, Path)) else copy.deepcopy(dict(path))
    if value.get("schemaVersion") != 1:
        _fail("skill_ablation.unsupported_schema_version", "$.schemaVersion")
    if value.get("matrixType") != MATRIX_TYPE:
        _fail("skill_ablation.invalid_matrix_type", "$.matrixType")
    if value.get("partition") != "formative":
        _fail("skill_ablation.invalid_partition", "$.partition")
    _assert_string(value.get("matrixId"), "$.matrixId")
    _assert_component(value.get("component"), "$.component")
    _assert_string(value.get("skillPath"), "$.skillPath")
    if tuple(_assert_list(value.get("conditionPair"), "$.conditionPair")) != MATCHED_PAIR:
        _fail("skill_ablation.condition_pair_mismatch", "$.conditionPair")
    if value.get("incumbentCondition") != INCUMBENT_BEFORE:
        _fail("skill_ablation.incumbent_condition_mismatch", "$.incumbentCondition")
    if tuple(_assert_list(value.get("modelRequests"), "$.modelRequests")) != TARGET_MODELS:
        _fail("skill_ablation.model_set_mismatch", "$.modelRequests")
    if value.get("reasoningRequest") != TARGET_REASONING:
        _fail("skill_ablation.reasoning_mismatch", "$.reasoningRequest")
    if value.get("repetitionsPerScenario") != 1:
        _fail("skill_ablation.repetitions_mismatch", "$.repetitionsPerScenario")
    scenarios = _assert_list(value.get("scenarioCoverage"), "$.scenarioCoverage")
    if not scenarios:
        _fail("skill_ablation.scenario_count_mismatch", "$.scenarioCoverage")
    scenario_ids: list[str] = []
    for index, scenario in enumerate(scenarios):
        item = _assert_mapping(scenario, "$.scenarioCoverage[" + str(index) + "]")
        scenario_ids.append(_assert_string(item.get("scenarioId"), "$.scenarioCoverage.scenarioId"))
        _assert_string(item.get("expectedTerminalState"), "$.scenarioCoverage.expectedTerminalState")
        if not isinstance(item.get("skillBodyExpected"), bool):
            _fail("skill_ablation.invalid_field", "$.scenarioCoverage.skillBodyExpected")
    if len(scenario_ids) != len(set(scenario_ids)):
        _fail("skill_ablation.duplicate_scenario", "$.scenarioCoverage")
    outcomes = _assert_mapping(value.get("outcomeProgram"), "$.outcomeProgram")
    if set(outcomes) != {INCUMBENT_BEFORE, INCUMBENT_MINUS, INCUMBENT_PLUS}:
        _fail("skill_ablation.outcome_condition_mismatch", "$.outcomeProgram")
    for condition_id in (INCUMBENT_BEFORE, INCUMBENT_MINUS, INCUMBENT_PLUS):
        condition_outcomes = _assert_mapping(outcomes[condition_id], "$.outcomeProgram." + condition_id)
        if set(condition_outcomes) != set(scenario_ids):
            _fail("skill_ablation.outcome_scenario_mismatch", "$.outcomeProgram." + condition_id)
        for scenario_id in scenario_ids:
            outcome = _assert_mapping(condition_outcomes[scenario_id], "$.outcomeProgram." + condition_id + "." + scenario_id)
            _assert_string(outcome.get("reasonCode"), "$.reasonCode")
            _assert_string(outcome.get("firstDivergenceCode"), "$.firstDivergenceCode")
            _assert_string(outcome.get("terminalState"), "$.terminalState")
    return copy.deepcopy(value)


def _analysis_header(path: Path | str) -> dict[str, object]:
    analysis = _load_json(path)
    if analysis.get("analysisType") != ANALYSIS_TYPE:
        _fail("skill_ablation.invalid_analysis_type", "$.analysisType")
    _assert_string(analysis.get("analysisId"), "$.analysisId")
    component = _assert_component(analysis.get("component"), "$.component")
    decision_output = _assert_mapping(analysis.get("decisionOutput"), "$.decisionOutput")
    if _assert_component(decision_output.get("component"), "$.decisionOutput.component") != component:
        _fail("skill_ablation.decision_output_mismatch", "$.decisionOutput.component")
    return analysis


def _scenario_ids(matrix: Mapping[str, object]) -> list[str]:
    return [str(item["scenarioId"]) for item in _assert_list(matrix["scenarioCoverage"], "$.scenarioCoverage") if isinstance(item, dict)]


def _scenario_by_id(matrix: Mapping[str, object]) -> dict[str, dict[str, Any]]:
    return {str(item["scenarioId"]): _assert_mapping(item, "$.scenarioCoverage") for item in _assert_list(matrix["scenarioCoverage"], "$.scenarioCoverage")}


def _outcome_for(matrix: Mapping[str, object], condition_id: str, scenario_id: str) -> dict[str, Any]:
    outcomes = _assert_mapping(matrix["outcomeProgram"], "$.outcomeProgram")
    condition_outcomes = _assert_mapping(outcomes[condition_id], "$.outcomeProgram." + condition_id)
    return _assert_mapping(condition_outcomes[scenario_id], "$.outcomeProgram." + condition_id + "." + scenario_id)


def _run_id(matrix: Mapping[str, object], model: str, scenario_id: str, condition_id: str) -> str:
    token = sha256_digest(
        canonical_bytes(
            {
                "matrixId": matrix["matrixId"],
                "model": model,
                "scenarioId": scenario_id,
                "conditionId": condition_id,
            }
        )
    )[7:23]
    return "skill-ablation-run-" + token


def _run_record(
    *,
    matrix: Mapping[str, object],
    qualification: Mapping[str, object],
    model: str,
    scenario_id: str,
    condition_id: str,
) -> dict[str, object]:
    scenario = _scenario_by_id(matrix)[scenario_id]
    outcome = _outcome_for(matrix, condition_id, scenario_id)
    skill_body_loaded = condition_id == INCUMBENT_PLUS and bool(scenario["skillBodyExpected"])
    body: dict[str, object] = {
        "schemaVersion": 1,
        "runId": _run_id(matrix, model, scenario_id, condition_id),
        "matrixId": matrix["matrixId"],
        "matrixDigest": sha256_digest(canonical_bytes(dict(matrix))),
        "qualificationDigest": canonical_contract_digest("EnvironmentQualificationRecord", qualification),
        "modelRequest": model,
        "reasoningRequest": TARGET_REASONING,
        "component": matrix["component"],
        "scenarioId": scenario_id,
        "conditionId": condition_id,
        "skillBodyLoaded": skill_body_loaded,
        "expectedTerminalState": scenario["expectedTerminalState"],
        "terminalState": outcome["terminalState"],
        "reasonCode": outcome["reasonCode"],
        "firstDivergenceCode": outcome["firstDivergenceCode"],
        "observableEvidence": {
            "schemaVersion": 1,
            "requirementRetained": bool(outcome.get("requirementRetained", condition_id == INCUMBENT_PLUS)),
            "realEvidenceSeam": bool(outcome.get("realEvidenceSeam", condition_id == INCUMBENT_PLUS)),
            "freshnessAnchor": bool(outcome.get("freshnessAnchor", condition_id == INCUMBENT_PLUS)),
            "terminalConsistent": bool(outcome.get("terminalConsistent", condition_id == INCUMBENT_PLUS)),
            "coldRecoverable": bool(outcome.get("coldRecoverable", condition_id == INCUMBENT_PLUS)),
        },
    }
    return {**body, "runDigest": sha256_digest(canonical_bytes(body))}


def _phase_from_conditions(conditions: tuple[str, ...]) -> str:
    if conditions == (INCUMBENT_BEFORE,):
        return "incumbent-before"
    if conditions == MATCHED_PAIR:
        return "matched-after"
    _fail("skill_ablation.condition_mismatch", "$.condition")


def run_skill_ablation_matrix(
    matrix: Mapping[str, object],
    qualification: Mapping[str, object],
    raw_root: Path | str,
    *,
    condition: str | None = None,
    condition_pair: tuple[str, str] | None = None,
) -> dict[str, object]:
    parsed_matrix = load_skill_ablation_matrix(matrix)
    parsed_qualification = _normalize_qualification(dict(qualification))
    if condition is not None:
        if condition_pair is not None:
            _fail("skill_ablation.condition_ambiguous", "$.condition")
        conditions = (condition,)
    elif condition_pair is not None:
        conditions = condition_pair
    else:
        _fail("skill_ablation.condition_required", "$.condition")
    phase = _phase_from_conditions(tuple(conditions))
    raw_root_path = Path(raw_root)
    created: list[dict[str, object]] = []
    counts_by_model: Counter[str] = Counter()
    counts_by_condition: Counter[str] = Counter()
    for model in TARGET_MODELS:
        for scenario_id in _scenario_ids(parsed_matrix):
            for condition_id in conditions:
                run = _run_record(
                    matrix=parsed_matrix,
                    qualification=parsed_qualification,
                    model=model,
                    scenario_id=scenario_id,
                    condition_id=condition_id,
                )
                _write_json(raw_root_path / "runs" / str(run["runId"]) / "run.json", run)
                created.append(run)
                counts_by_model[model] += 1
                counts_by_condition[condition_id] += 1
    index = {
        "schemaVersion": 1,
        "matrixDigest": sha256_digest(canonical_bytes(parsed_matrix)),
        "qualificationDigest": canonical_contract_digest("EnvironmentQualificationRecord", parsed_qualification),
        "phase": phase,
        "conditions": list(conditions),
        "runDigests": sorted(str(run["runDigest"]) for run in created),
    }
    _write_json(raw_root_path / "run-index.json", index)
    result: dict[str, object] = {
        "schemaVersion": 1,
        "command": "run-matrix",
        "matrixId": parsed_matrix["matrixId"],
        "phase": phase,
        "rawRoot": str(raw_root_path),
        "runsCreated": len(created),
        "runsByModel": dict(sorted(counts_by_model.items())),
        "runsByCondition": dict(sorted(counts_by_condition.items())),
        "runIds": [str(run["runId"]) for run in created],
    }
    if phase == "incumbent-before":
        result["condition"] = INCUMBENT_BEFORE
    else:
        result["conditionPair"] = list(MATCHED_PAIR)
    return result


def _read_runs(raw_root: Path) -> list[dict[str, object]]:
    paths = sorted((raw_root / "runs").glob("*/run.json"))
    if not paths:
        _fail("skill_ablation.missing_run_evidence", "$.rawRoot")
    runs = [_load_json(path) for path in paths]
    for run in runs:
        digest = sha256_digest(canonical_bytes({key: value for key, value in run.items() if key != "runDigest"}))
        if run.get("runDigest") != digest:
            _fail("skill_ablation.run_digest_mismatch", "$.runs")
    return runs


def _read_index(raw_root: Path) -> dict[str, object]:
    index = _load_json(raw_root / "run-index.json")
    if index.get("schemaVersion") != 1:
        _fail("skill_ablation.invalid_run_index", "$.runIndex")
    return index


def _metrics_from_runs(runs: list[dict[str, object]]) -> dict[str, object]:
    plus_runs = [run for run in runs if run["conditionId"] == INCUMBENT_PLUS]
    if not plus_runs:
        plus_runs = [run for run in runs if run["conditionId"] == INCUMBENT_BEFORE]
    non_controls = [run for run in plus_runs if run["expectedTerminalState"] != "not_applicable"]
    controls = [run for run in plus_runs if run["expectedTerminalState"] == "not_applicable"]
    false_completions = [
        run
        for run in plus_runs
        if run["terminalState"] == "complete" and run["expectedTerminalState"] != "complete"
    ]
    return {
        "requirementRetentionRecall": "1.0"
        if non_controls and all(run["observableEvidence"]["requirementRetained"] for run in non_controls)
        else "0",
        "realEvidenceSeamPrecision": "1.0"
        if non_controls and all(run["observableEvidence"]["realEvidenceSeam"] for run in non_controls)
        else "0",
        "freshnessAnchorEnforced": bool(non_controls) and all(run["observableEvidence"]["freshnessAnchor"] for run in non_controls),
        "terminalConsistencyEnforced": bool(non_controls) and all(run["observableEvidence"]["terminalConsistent"] for run in non_controls),
        "foreignOrStaleStateRejected": bool(non_controls) and all(run["observableEvidence"]["freshnessAnchor"] for run in non_controls),
        "coldRecoveryPreserved": bool(non_controls) and all(run["observableEvidence"]["coldRecoverable"] for run in non_controls),
        "oneCheckNonActivation": bool(controls) and all(not run["skillBodyLoaded"] for run in controls),
        "criticalFalseCompletionCount": len(false_completions),
        "schemaTheaterRejected": bool(non_controls) and all(run["observableEvidence"]["realEvidenceSeam"] for run in non_controls),
    }


def _assert_string_list(value: object, path: str) -> list[str]:
    items = _assert_list(value, path)
    result: list[str] = []
    for index, item in enumerate(items):
        result.append(_assert_string(item, path + "[" + str(index) + "]"))
    return result


def _build_report(analysis: Mapping[str, object], raw_root: Path) -> dict[str, object]:
    runs = _read_runs(raw_root)
    index = _read_index(raw_root)
    run_digests = sorted(str(run["runDigest"]) for run in runs)
    if index.get("runDigests") != run_digests:
        _fail("skill_ablation.run_index_mismatch", "$.runIndex.runDigests")
    if index.get("matrixDigest") != analysis.get("matrixDigest"):
        _fail("skill_ablation.matrix_digest_mismatch", "$.matrixDigest")
    conditions = tuple(_assert_string_list(index.get("conditions"), "$.runIndex.conditions"))
    if _phase_from_conditions(conditions) != index.get("phase"):
        _fail("skill_ablation.run_index_mismatch", "$.runIndex.phase")
    run_conditions = {str(run.get("conditionId")) for run in runs}
    if run_conditions != set(conditions):
        _fail("skill_ablation.run_index_mismatch", "$.runIndex.conditions")
    run_qualification_digests = {str(run.get("qualificationDigest")) for run in runs}
    if run_qualification_digests != {str(index.get("qualificationDigest"))}:
        _fail("skill_ablation.qualification_digest_mismatch", "$.qualificationDigest")
    run_matrix_digests = {str(run.get("matrixDigest")) for run in runs}
    if run_matrix_digests != {str(index.get("matrixDigest"))}:
        _fail("skill_ablation.matrix_digest_mismatch", "$.runs.matrixDigest")
    if {str(run.get("component")) for run in runs} != {str(analysis["component"])}:
        _fail("skill_ablation.component_mismatch", "$.component")
    metrics = _metrics_from_runs(runs)
    return {
        "schemaVersion": 1,
        "analysisType": ANALYSIS_TYPE,
        "analysisId": analysis["analysisId"],
        "component": analysis["component"],
        "matrixDigest": analysis["matrixDigest"],
        "phase": index["phase"],
        "metrics": metrics,
        "decisionOutput": analysis["decisionOutput"],
        "resourceEnvelope": analysis["resourceEnvelope"],
        "runCount": len(runs),
        "runDigests": run_digests,
    }


def grade_skill_ablation(analysis_path: Path | str, raw_root: Path | str) -> dict[str, object]:
    analysis = _analysis_header(analysis_path)
    raw_root_path = Path(raw_root)
    report = _build_report(analysis, raw_root_path)
    if report["phase"] == "matched-after" and report["metrics"] != analysis["metrics"]:
        _fail("skill_ablation.analysis_mismatch", "$.metrics")
    grade = {
        "schemaVersion": 1,
        "command": "grade",
        "analysisId": analysis["analysisId"],
        "phase": report["phase"],
        "runsGraded": report["runCount"],
        "metrics": report["metrics"],
        "runDigests": report["runDigests"],
    }
    _write_json(raw_root_path / "grade.json", grade, overwrite=True)
    return grade


def _assert_fresh_grade(grade: Mapping[str, object], report: Mapping[str, object], analysis: Mapping[str, object]) -> None:
    if grade.get("schemaVersion") != 1 or grade.get("command") != "grade":
        _fail("skill_ablation.invalid_grade", "$.grade")
    expected = {
        "analysisId": analysis["analysisId"],
        "phase": report["phase"],
        "runsGraded": report["runCount"],
        "metrics": report["metrics"],
        "runDigests": report["runDigests"],
    }
    for key, value in expected.items():
        if grade.get(key) != value:
            _fail("skill_ablation.stale_grade", "$.grade." + key)


def report_skill_ablation(analysis_path: Path | str, raw_root: Path | str, output: Path | str) -> dict[str, object]:
    analysis = _analysis_header(analysis_path)
    raw_root_path = Path(raw_root)
    grade_path = raw_root_path / "grade.json"
    if not grade_path.is_file():
        _fail("skill_ablation.missing_grade", "$.grade")
    report = _build_report(analysis, raw_root_path)
    _assert_fresh_grade(_load_json(grade_path), report, analysis)
    if report["phase"] == "matched-after" and report["metrics"] != analysis["metrics"]:
        _fail("skill_ablation.analysis_mismatch", "$.metrics")
    output_path = Path(output)
    report_path = output_path / (_assert_component(analysis["component"], "$.component") + "-report.json")
    report_digest = _write_json(report_path, report, overwrite=True)
    return {
        "schemaVersion": 1,
        "command": "report",
        "analysisId": analysis["analysisId"],
        "phase": report["phase"],
        "reportPath": str(report_path),
        "reportDigest": report_digest,
        "redactedRuns": report["runCount"],
    }


__all__ = [
    "ANALYSIS_TYPE",
    "INCUMBENT_BEFORE",
    "INCUMBENT_MINUS",
    "INCUMBENT_PLUS",
    "MATCHED_PAIR",
    "MATRIX_TYPE",
    "grade_skill_ablation",
    "load_skill_ablation_matrix",
    "report_skill_ablation",
    "run_skill_ablation_matrix",
]
