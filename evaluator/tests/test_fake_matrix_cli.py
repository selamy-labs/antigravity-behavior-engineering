from __future__ import annotations

import json
import os
import subprocess
from collections import Counter
from pathlib import Path

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import canonical_contract_digest, parse_contract


REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX = REPO_ROOT / "evals" / "formative" / "evaluator-conformance" / "matrix.json"
ANALYSIS = REPO_ROOT / "evals" / "formative" / "evaluator-conformance" / "analysis.json"
README = REPO_ROOT / "evals" / "public-samples" / "fake-scorecard" / "README.md"

EXPECTED_CASES = {
    "adapter_failure",
    "budget_exhaustion",
    "grader_leakage",
    "invalid_controller_input",
    "malformed_ndjson",
    "needs_input",
    "ordinary_artifact_failure",
    "pre_start_auth_failure",
    "product_timeout",
    "safety_refusal",
    "success",
    "test_flake",
    "tool_misuse",
    "truncated_ndjson",
}


def _run_cli(*args: str) -> dict[str, object]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        ["uv", "run", "--project", "evaluator", "abe-eval", *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _grade_paths(raw_root: Path, run_id: object) -> list[Path]:
    return sorted((raw_root / "runs" / str(run_id) / "grades").glob("*/grade.json"))


def _metric(value: str) -> dict[str, object]:
    return {"schemaVersion": 1, "value": value, "uncertainty": "0"}


def _decimal_ratio(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0"
    if numerator == denominator:
        return "1.0"
    return format(numerator / denominator, ".6f").rstrip("0").rstrip(".")


def _manual_scorecard(
    analysis: dict[str, object], runs: list[dict[str, object]], grades_by_run: dict[str, list[dict[str, object]]]
) -> dict[str, object]:
    model_request = str(runs[0]["observedModel"]["requestedModel"])
    grade_outcomes_by_run = {
        run_id: [str(grade["outcome"]) for grade in grades] for run_id, grades in grades_by_run.items()
    }
    valid_runs = [run for run in runs if run["classification"]["countsInValidRun"]]
    exclusions = Counter(
        "indeterminate" if run["classification"]["class"] == "indeterminate" else str(run["classification"]["reasonCode"])
        for run in runs
        if not run["classification"]["countsInValidRun"]
    )
    valid_passes = sum(
        1
        for run in valid_runs
        if grade_outcomes_by_run[str(run["runId"])] and all(outcome == "pass" for outcome in grade_outcomes_by_run[str(run["runId"])])
    )
    graded_valid_runs = [run for run in valid_runs if grade_outcomes_by_run[str(run["runId"])]]
    agreeing = sum(1 for run in graded_valid_runs if len(set(grade_outcomes_by_run[str(run["runId"])])) <= 1)
    projection = {
        "analysisLockDigest": canonical_contract_digest("AnalysisLock", analysis),
        "attempts": [
            {
                "runDigest": canonical_contract_digest("RunRecord", run),
                "countsInValidRun": run["classification"]["countsInValidRun"],
                "reasonCode": run["classification"]["reasonCode"],
                "gradeOutcomes": grade_outcomes_by_run[str(run["runId"])],
            }
            for run in runs
        ],
    }
    return parse_contract(
        "Scorecard",
        {
            "schemaVersion": 1,
            "scorecardId": "scorecard-" + str(analysis["analysisId"]),
            "candidateDigest": "not_applicable",
            "analysisLockDigest": canonical_contract_digest("AnalysisLock", analysis),
            "modelRequest": model_request,
            "attemptProjectionDigest": sha256_digest(canonical_bytes(projection)),
            "metrics": {
                "intention_to_treat_attempts": _metric(str(len(runs))),
                "valid_run_attempts": _metric(str(len(valid_runs))),
                "valid_run_success_rate": _metric(_decimal_ratio(valid_passes, len(valid_runs))),
            },
            "resourceSummary": {
                "median_wall_time_ms": str(
                    sorted(int(run["consumption"]["wallTimeMs"]) for run in runs)[len(runs) // 2]
                )
            },
            "attritionSummary": {
                "itt_total": str(len(runs)),
                "valid_run_total": str(len(valid_runs)),
                **{"excluded_" + reason: str(count) for reason, count in sorted(exclusions.items())},
            },
            "graderAgreement": {
                "gradable_runs_with_grades": str(len(graded_valid_runs)),
                "raw_agreement": _decimal_ratio(agreeing, len(graded_valid_runs)),
            },
            "limitations": [],
        },
    )


def test_fake_matrix_cli_publishes_scorecard_recomputable_from_raw_evidence(tmp_path):
    raw_root = tmp_path / "evidence" / "raw" / "formative" / "evaluator-conformance"
    output = tmp_path / "evidence" / "publishable" / "reports" / "evaluator-conformance"

    matrix_result = _run_cli("fake-matrix", "--matrix", str(MATRIX), "--raw-root", str(raw_root))
    grade_result = _run_cli("grade", "--analysis", str(ANALYSIS), "--raw-root", str(raw_root))
    report_result = _run_cli(
        "report",
        "--analysis",
        str(ANALYSIS),
        "--raw-root",
        str(raw_root),
        "--output",
        str(output),
    )
    repeat_report_result = _run_cli(
        "report",
        "--analysis",
        str(ANALYSIS),
        "--raw-root",
        str(raw_root),
        "--output",
        str(output),
    )

    assert matrix_result["runsCreated"] == 14
    assert grade_result["gradesCreated"] == 14
    assert set(matrix_result["caseIds"]) == EXPECTED_CASES
    assert report_result["scorecardPath"] == str(output / "scorecard.json")
    assert repeat_report_result["scorecardDigest"] == report_result["scorecardDigest"]
    assert repeat_report_result["redactedRuns"] == 14
    assert repeat_report_result["redactedRunsSkipped"] == 14

    runs = [parse_contract("RunRecord", _json(path)) for path in sorted((raw_root / "runs").glob("*/run.json"))]
    assert len(runs) == 14
    grades_by_run: dict[str, list[dict[str, object]]] = {}
    for run in runs:
        grade_paths = _grade_paths(raw_root, run["runId"])
        assert len(grade_paths) == 1
        grades_by_run[str(run["runId"])] = [parse_contract("GradeRecord", _json(grade_paths[0]))]

    analysis = parse_contract("AnalysisLock", _json(ANALYSIS))
    independent_scorecard = _manual_scorecard(analysis, runs, grades_by_run)
    published_scorecard = parse_contract("Scorecard", _json(output / "scorecard.json"))
    assert published_scorecard == independent_scorecard

    by_reason = {str(run["classification"]["reasonCode"]): run for run in runs}
    assert by_reason["success"]["classification"]["countsInValidRun"] is True
    assert grades_by_run[str(by_reason["success"]["runId"])][0]["outcome"] == "pass"
    assert by_reason["product_timeout"]["classification"] == {
        **by_reason["product_timeout"]["classification"],
        "class": "product_failure",
        "countsInValidRun": False,
        "reasonCode": "product_timeout",
    }
    assert by_reason["product_timeout"]["processState"]["timeout"] is True
    assert by_reason["pre_start_auth_failure"]["processState"]["workerProcessState"] == "not_started"
    assert by_reason["pre_start_auth_failure"]["attemptQualification"]["authentication"]["result"] == "fail"
    assert by_reason["truncated_ndjson"]["classification"]["class"] == "indeterminate"
    assert by_reason["truncated_ndjson"]["infrastructureValidity"] == "capture_truncated"

    assert published_scorecard["metrics"] == {
        "intention_to_treat_attempts": {"schemaVersion": 1, "value": "14", "uncertainty": "0"},
        "valid_run_attempts": {"schemaVersion": 1, "value": "2", "uncertainty": "0"},
        "valid_run_success_rate": {"schemaVersion": 1, "value": "0.5", "uncertainty": "0"},
    }
    assert published_scorecard["attritionSummary"] == {
        "excluded_adapter_failure": "1",
        "excluded_budget_exhaustion": "1",
        "excluded_indeterminate": "5",
        "excluded_invalid_controller_input": "1",
        "excluded_pre_start_auth_failure": "1",
        "excluded_product_timeout": "1",
        "excluded_safety_refusal": "1",
        "excluded_tool_misuse": "1",
        "itt_total": "14",
        "valid_run_total": "2",
    }
    assert published_scorecard["graderAgreement"] == {"gradable_runs_with_grades": "2", "raw_agreement": "1.0"}

    readme = README.read_text(encoding="utf-8").lower()
    for forbidden in (
        "selamy" + "-core",
        "p" + "selamy",
        "google" + ".com",
        "/home" + "/dev",
        "hidden " + "check",
        "private " + "source",
    ):
        assert forbidden not in readme
    assert "fake-matrix" in readme
    assert "no target-model run" in readme
