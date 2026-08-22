from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import canonical_contract_digest, parse_contract


ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "evals" / "formative" / "proof-obligation-contract.matrix.json"
ANALYSIS = ROOT / "evals" / "formative" / "proof-obligation-contract.analysis.json"
CONTRACT_FIXTURES = ROOT / "tests" / "contract" / "fixtures" / "evaluation-contracts.json"
TARGET_MODELS = {"gemini-3.1-pro-high", "gemini-3.7-flash-high"}


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _case_value(name: str) -> dict[str, object]:
    fixture = _load(CONTRACT_FIXTURES)
    for case in fixture["validCases"]:
        if case["name"] == name:
            value = case["value"]
            assert isinstance(value, dict)
            return value
    raise AssertionError(name)


def _qualification(path: Path) -> dict[str, object]:
    qualification = parse_contract("EnvironmentQualificationRecord", _case_value("EnvironmentQualificationRecord"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes({"schemaVersion": 1, "environmentQualification": qualification}) + b"\n")
    return qualification


def _run_cli(*args: str) -> dict[str, object]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        ["uv", "run", "--project", "evaluator", "--locked", "--offline", "abe-eval", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    output = json.loads(result.stdout)
    assert isinstance(output, dict)
    return output


def _runs(raw_root: Path) -> list[dict[str, object]]:
    runs = []
    for path in sorted((raw_root / "runs").glob("*/run.json")):
        run = _load(path)
        assert run["schemaVersion"] == 1
        assert run["runDigest"] == sha256_digest(canonical_bytes({k: v for k, v in run.items() if k != "runDigest"}))
        runs.append(run)
    return runs


def test_skill_ablation_run_matrix_grades_and_reports_incumbent_before(tmp_path: Path) -> None:
    qualification_path = tmp_path / "qualification.json"
    qualification = _qualification(qualification_path)
    raw_root = tmp_path / "evidence" / "raw" / "formative" / "proof-obligation-contract" / "incumbent-before"
    output = tmp_path / "evidence" / "publishable" / "formative" / "proof-obligation-contract" / "incumbent-before"

    run_result = _run_cli(
        "run-matrix",
        "--matrix",
        str(MATRIX),
        "--condition",
        "incumbent-before",
        "--qualification",
        str(qualification_path),
        "--raw-root",
        str(raw_root),
    )
    grade_result = _run_cli("grade", "--analysis", str(ANALYSIS), "--raw-root", str(raw_root))
    report_result = _run_cli("report", "--analysis", str(ANALYSIS), "--raw-root", str(raw_root), "--output", str(output))

    assert run_result["runsCreated"] == 20
    assert run_result["condition"] == "incumbent-before"
    assert run_result["runsByModel"] == {"gemini-3.1-pro-high": 10, "gemini-3.7-flash-high": 10}
    assert grade_result["runsGraded"] == 20
    assert grade_result["phase"] == "incumbent-before"
    assert report_result["reportPath"] == str(output / "proof-obligation-contract-report.json")

    runs = _runs(raw_root)
    assert {run["modelRequest"] for run in runs} == TARGET_MODELS
    assert {run["conditionId"] for run in runs} == {"incumbent-before"}
    assert all(run["qualificationDigest"] == canonical_contract_digest("EnvironmentQualificationRecord", qualification) for run in runs)
    assert any(run["firstDivergenceCode"] == "stale_claim_without_verification" for run in runs)


def test_skill_ablation_run_matrix_grades_and_reports_matched_after(tmp_path: Path) -> None:
    qualification_path = tmp_path / "qualification.json"
    _qualification(qualification_path)
    raw_root = tmp_path / "evidence" / "raw" / "formative" / "proof-obligation-contract" / "matched-after"
    output = tmp_path / "evidence" / "publishable" / "formative" / "proof-obligation-contract" / "matched-after"

    run_result = _run_cli(
        "run-matrix",
        "--matrix",
        str(MATRIX),
        "--condition-pair",
        "incumbent-minus",
        "incumbent-plus",
        "--qualification",
        str(qualification_path),
        "--raw-root",
        str(raw_root),
    )
    grade_result = _run_cli("grade", "--analysis", str(ANALYSIS), "--raw-root", str(raw_root))
    report_result = _run_cli("report", "--analysis", str(ANALYSIS), "--raw-root", str(raw_root), "--output", str(output))
    report = _load(Path(report_result["reportPath"]))

    assert run_result["runsCreated"] == 40
    assert run_result["conditionPair"] == ["incumbent-minus", "incumbent-plus"]
    assert run_result["runsByCondition"] == {"incumbent-minus": 20, "incumbent-plus": 20}
    assert grade_result["runsGraded"] == 40
    assert grade_result["phase"] == "matched-after"
    assert report["metrics"] == _load(ANALYSIS)["metrics"]
    assert report["decisionOutput"] == _load(ANALYSIS)["decisionOutput"]

    runs = _runs(raw_root)
    plus = [run for run in runs if run["conditionId"] == "incumbent-plus"]
    minus = [run for run in runs if run["conditionId"] == "incumbent-minus"]
    assert len(plus) == len(minus) == 20
    assert all(run["skillBodyLoaded"] is False for run in plus if run["expectedTerminalState"] == "not_applicable")
    assert all(run["skillBodyLoaded"] is True for run in plus if run["expectedTerminalState"] != "not_applicable")
    assert any(run["terminalState"] == "needs_input" for run in plus)
    assert any(run["terminalState"] == "indeterminate" for run in plus)
    assert any(run["terminalState"] == "complete" for run in plus)
    assert {"complete", "incomplete", "not_applicable"}.issubset({run["terminalState"] for run in minus})
    assert any(
        run["firstDivergenceCode"] == "false_completion" and run["terminalState"] == "complete"
        for run in minus
    )
