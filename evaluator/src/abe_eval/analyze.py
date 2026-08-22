"""Frozen attempt aggregation for scorecards."""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import canonical_contract_digest, parse_contract


def _metric(value: str) -> dict[str, object]:
    return {"schemaVersion": 1, "value": value, "uncertainty": "0"}


def _view_run(view: object) -> tuple[dict[str, object], list[str]]:
    if isinstance(view, dict) and "run" in view:
        run_value = view["run"]
        grade_outcomes = view.get("gradeOutcomes", [])
    else:
        run_value = view
        grade_outcomes = []
    if not isinstance(grade_outcomes, list) or any(outcome not in {"pass", "fail"} for outcome in grade_outcomes):
        raise TypeError("analysis.invalid_grade_outcomes")
    return parse_contract("RunRecord", run_value), list(grade_outcomes)


def _decimal_ratio(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0"
    if numerator == denominator:
        return "1.0"
    return format(numerator / denominator, ".6f").rstrip("0").rstrip(".")


def analyze_attempts(analysis: dict[str, object], attempts: Iterable[object]) -> dict[str, object]:
    """Aggregate every scheduled attempt under ITT and report valid-run attrition."""

    parsed_analysis = parse_contract("AnalysisLock", analysis)
    views = [_view_run(view) for view in attempts]
    runs = [run for run, _grades in views]
    if not runs:
        raise TypeError("analysis.empty_attempts")
    model_request = str(runs[0]["observedModel"]["requestedModel"])
    if any(run["observedModel"]["requestedModel"] != model_request for run in runs):
        raise TypeError("analysis.mixed_models")
    valid_runs = [(run, grades) for run, grades in views if run["classification"]["countsInValidRun"]]
    exclusions = Counter(
        "indeterminate" if run["classification"]["class"] == "indeterminate" else str(run["classification"]["reasonCode"])
        for run, _grades in views
        if not run["classification"]["countsInValidRun"]
    )
    valid_passes = sum(1 for _run, grades in valid_runs if grades and all(outcome == "pass" for outcome in grades))
    graded_valid = [(run, grades) for run, grades in valid_runs if grades]
    agreeing = sum(1 for _run, grades in graded_valid if len(set(grades)) <= 1)
    projection = {
        "analysisLockDigest": canonical_contract_digest("AnalysisLock", parsed_analysis),
        "attempts": [
            {
                "runDigest": canonical_contract_digest("RunRecord", run),
                "countsInValidRun": run["classification"]["countsInValidRun"],
                "reasonCode": run["classification"]["reasonCode"],
                "gradeOutcomes": grades,
            }
            for run, grades in views
        ],
    }
    attrition_summary = {
        "itt_total": str(len(views)),
        "valid_run_total": str(len(valid_runs)),
        **{"excluded_" + reason: str(count) for reason, count in sorted(exclusions.items())},
    }
    scorecard = {
        "schemaVersion": 1,
        "scorecardId": "scorecard-" + str(parsed_analysis["analysisId"]),
        "candidateDigest": "not_applicable",
        "analysisLockDigest": canonical_contract_digest("AnalysisLock", parsed_analysis),
        "modelRequest": model_request,
        "attemptProjectionDigest": sha256_digest(canonical_bytes(projection)),
        "metrics": {
            "intention_to_treat_attempts": _metric(str(len(views))),
            "valid_run_attempts": _metric(str(len(valid_runs))),
            "valid_run_success_rate": _metric(_decimal_ratio(valid_passes, len(valid_runs))),
        },
        "resourceSummary": {
            "median_wall_time_ms": str(sorted(int(run["consumption"]["wallTimeMs"]) for run in runs)[len(runs) // 2])
        },
        "attritionSummary": attrition_summary,
        "graderAgreement": {
            "gradable_runs_with_grades": str(len(graded_valid)),
            "raw_agreement": _decimal_ratio(agreeing, len(graded_valid)),
        },
        "limitations": [],
    }
    return parse_contract("Scorecard", scorecard)


__all__ = ["analyze_attempts"]
