from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.condition_pair import validate_pair
from abe_eval.contracts import ContractValidationError, canonical_contract_digest, parse_contract


ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "evals" / "formative" / "superpowers-pilot.matrix.json"
ANALYSIS = ROOT / "evals" / "formative" / "superpowers-pilot.analysis.json"
T020_MATRIX = ROOT / "evals" / "formative" / "bare-pilot.matrix.json"
T020_ANALYSIS = ROOT / "evals" / "formative" / "bare-pilot.analysis.json"
ACTUAL_PROTECTED_BLINDED = ROOT / "evidence" / "raw" / "formative" / "incumbent-baseline" / "blinded-baseline-input.json"
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
            assert isinstance(case["value"], dict)
            return case["value"]
    raise AssertionError(name)


def _qualification(path: Path) -> dict[str, object]:
    qualification = parse_contract("EnvironmentQualificationRecord", _case_value("EnvironmentQualificationRecord"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes({"schemaVersion": 1, "environmentQualification": qualification}) + b"\n")
    return qualification


def _json_blob(value: object) -> str:
    return canonical_bytes(value).decode("utf-8").lower()


def _assert_blinded_and_candidate_free(blinded: dict[str, object]) -> None:
    assert parse_contract("BlindedBaselineInput", blinded) == blinded
    blob = _json_blob(blinded)
    for forbidden in ("bare", "superpowers", "full", "local", "candidate", "sealed"):
        assert forbidden not in blob


def test_superpowers_matrix_is_committed_with_external_pin_and_no_t020_attempt_reuse(tmp_path: Path):
    from abe_eval.bare_condition import load_bare_pilot_matrix, planned_bare_pilot_cells
    from abe_eval.paired_incumbent import load_paired_incumbent_matrix, planned_paired_incumbent_cells

    matrix = load_paired_incumbent_matrix(MATRIX)
    analysis = _load(ANALYSIS)
    qualification = _qualification(tmp_path / "qualification.json")
    cells = planned_paired_incumbent_cells(matrix, qualification)
    t020_cells = planned_bare_pilot_cells(load_bare_pilot_matrix(T020_MATRIX), qualification)

    assert matrix["matrixType"] == "superpowers-paired-incumbent-pilot"
    assert matrix["conditionPair"] == ["bare", "superpowers"]
    assert matrix["superpowersSource"] == {
        "schemaVersion": 1,
        "name": "superpowers",
        "sourceUrl": "https://github.com/obra/superpowers",
        "revision": "b36e0829c6d0140e93cfef2ca599b1b07d4a7797",
        "version": "6.3.0",
        "license": "MIT",
        "rootDigest": "sha256:a89f1095b9170551686c36a85efb811bfffa6f925c6b757d17b4dcd540a6ea00",
    }
    assert analysis["matrixDigest"] == sha256_digest(canonical_bytes(matrix))
    assert analysis["historicalBareMatrixDigest"] == sha256_digest(canonical_bytes(load_bare_pilot_matrix(T020_MATRIX)))
    assert analysis["protectedBlindedBaselineInput"] == {
        "path": "evidence/raw/formative/incumbent-baseline/blinded-baseline-input.json",
        "committed": False,
    }

    assert {cell["modelRequest"] for cell in cells} == TARGET_MODELS
    assert {cell["familyId"] for cell in cells} == set(matrix["familyIds"])
    assert len(cells) == len(matrix["familyIds"]) * len(TARGET_MODELS)

    t020_attempt_ids = {
        str(attempt["attemptId"])
        for cell in t020_cells
        for attempt in cell["attempts"]
    }
    t020_run_ids = {str(attempt["runId"]) for cell in t020_cells for attempt in cell["attempts"]}

    for cell in cells:
        block = parse_contract("BlockSpec", cell["block"])
        baseline = parse_contract("ConditionLock", cell["conditions"]["bare"])
        incumbent = parse_contract("ConditionLock", cell["conditions"]["superpowers"])
        pair_lock = parse_contract("ConditionPairLock", cell["conditionPairLock"])
        result = validate_pair(pair_lock, baseline, incumbent)
        assert result.ok, result
        assert block["conditionIds"] == ["bare", "superpowers"]
        assert block["conditionPairLockDigest"] == canonical_contract_digest("ConditionPairLock", pair_lock)
        assert pair_lock["allowedDifferences"] == ["/enabledComponents"]
        assert baseline["enabledComponents"] == []
        assert incumbent["enabledComponents"] == ["upstream:superpowers"]
        assert baseline["dependencyDigests"] == {
            "superpowers": "sha256:a89f1095b9170551686c36a85efb811bfffa6f925c6b757d17b4dcd540a6ea00"
        }
        assert incumbent["dependencyDigests"] == baseline["dependencyDigests"]
        assert {attempt["conditionId"] for attempt in cell["attempts"]} == {"bare", "superpowers"}
        assert len(cell["attempts"]) == 6
        assert t020_attempt_ids.isdisjoint(str(attempt["attemptId"]) for attempt in cell["attempts"])
        assert t020_run_ids.isdisjoint(str(attempt["runId"]) for attempt in cell["attempts"])


def test_paired_incumbent_cli_writes_contemporaneous_runs_and_blinded_input(tmp_path: Path):
    from abe_eval.paired_incumbent import analyze_paired_incumbent_evidence

    qualification_path = tmp_path / "evidence" / "raw" / "qualification" / "local" / "qualification.json"
    qualification = _qualification(qualification_path)
    raw_root = tmp_path / "evidence" / "raw" / "formative" / "incumbent-baseline"

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            "evaluator",
            "abe-eval",
            "run-matrix",
            "--matrix",
            str(MATRIX),
            "--condition-pair",
            "bare",
            "superpowers",
            "--qualification",
            str(qualification_path),
            "--raw-root",
            str(raw_root),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    command_result = json.loads(completed.stdout)
    assert command_result["command"] == "run-matrix"
    assert command_result["conditionPair"] == ["bare", "superpowers"]
    assert command_result["runsCreated"] == 168
    assert command_result["runsByModel"] == {"gemini-3.1-pro-high": 84, "gemini-3.7-flash-high": 84}
    assert command_result["runsByCondition"] == {"bare": 84, "superpowers": 84}

    grade = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            "evaluator",
            "abe-eval",
            "grade",
            "--analysis",
            str(ANALYSIS),
            "--raw-root",
            str(raw_root),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert grade.returncode == 0, grade.stdout + grade.stderr
    grade_result = json.loads(grade.stdout)
    assert grade_result["command"] == "grade"
    assert grade_result["analysisId"] == "superpowers-incumbent-formative-pilot-2026-08-22"
    assert grade_result["pairsGraded"] == 84
    assert grade_result["blindedBaselineInputPath"] == str(raw_root / "blinded-baseline-input.json")

    runs = [parse_contract("RunRecord", _load(path)) for path in sorted((raw_root / "runs").glob("*/run.json"))]
    assert len(runs) == 168
    assert {run["observedModel"]["requestedModel"] for run in runs} == TARGET_MODELS
    assert {run["classification"]["countsInIntentionToTreat"] for run in runs} == {True}
    assert {run["conditionDigest"] for run in runs}
    assert not list(raw_root.glob("**/*RAW_CANARY*"))

    report = analyze_paired_incumbent_evidence(MATRIX, ANALYSIS, raw_root)
    assert report == _load(ANALYSIS)
    assert report["qualificationDigest"] == canonical_contract_digest("EnvironmentQualificationRecord", qualification)
    assert set(report["modelReports"]) == TARGET_MODELS
    assert report["conditionLabelPolicy"] == "public_analysis_labels_incumbent; protected_power_input_masks_conditions"
    assert report["localTreatmentOutcomeIncluded"] is False
    assert report["sealedOutcomeIncluded"] is False
    assert report["sourceRunDigests"] == sorted(canonical_contract_digest("RunRecord", run) for run in runs)

    blinded = _load(raw_root / "blinded-baseline-input.json")
    _assert_blinded_and_candidate_free(blinded)
    assert grade_result["blindedBaselineInputDigest"] == canonical_contract_digest("BlindedBaselineInput", blinded)

    if ACTUAL_PROTECTED_BLINDED.exists():
        _assert_blinded_and_candidate_free(_load(ACTUAL_PROTECTED_BLINDED))


def test_paired_incumbent_rejects_wrong_pair_and_missing_evidence(tmp_path: Path):
    from abe_eval.paired_incumbent import load_paired_incumbent_matrix

    qualification_path = tmp_path / "qualification.json"
    _qualification(qualification_path)

    wrong_pair = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            "evaluator",
            "abe-eval",
            "run-matrix",
            "--matrix",
            str(MATRIX),
            "--condition-pair",
            "bare",
            "full",
            "--qualification",
            str(qualification_path),
            "--raw-root",
            str(tmp_path / "raw"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    missing_evidence = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            "evaluator",
            "abe-eval",
            "grade",
            "--analysis",
            str(ANALYSIS),
            "--raw-root",
            str(tmp_path / "empty-raw"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert wrong_pair.returncode == 2
    assert "paired_incumbent.condition_pair_mismatch" in wrong_pair.stderr
    assert missing_evidence.returncode == 2
    assert "paired_incumbent.missing_run_evidence" in missing_evidence.stderr

    invalid = _load(MATRIX)
    invalid.pop("superpowersSource")
    with pytest.raises(ContractValidationError) as excinfo:
        load_paired_incumbent_matrix(invalid)  # type: ignore[arg-type]
    assert excinfo.value.reason_code == "paired_incumbent.missing_lock"
    assert excinfo.value.path == "$.superpowersSource"
