from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from abe_eval.canonical import canonical_bytes, sha256_digest
from abe_eval.contracts import canonical_contract_digest, parse_contract


ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "evals" / "formative" / "bare-pilot.matrix.json"
ANALYSIS = ROOT / "evals" / "formative" / "bare-pilot.analysis.json"
METHOD = ROOT / "docs" / "evaluation" / "bare-baseline-method.md"
CONTRACT_FIXTURES = ROOT / "tests" / "contract" / "fixtures" / "evaluation-contracts.json"
TARGET_MODELS = {"gemini-3.1-pro-high", "gemini-3.7-flash-high"}


def test_bare_pilot_matrix_is_committed_before_historical_execution():
    assert MATRIX.is_file()
    assert ANALYSIS.is_file()
    assert METHOD.is_file()


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


def test_bare_matrix_freezes_fresh_state_and_exact_bare_conditions(tmp_path):
    from abe_eval.bare_condition import load_bare_pilot_matrix, planned_bare_pilot_cells

    matrix = load_bare_pilot_matrix(MATRIX)
    qualification = _qualification(tmp_path / "qualification.json")
    cells = planned_bare_pilot_cells(matrix, qualification)

    assert matrix["matrixType"] == "bare-antigravity-historical-pilot"
    assert matrix["conditionId"] == "bare"
    assert matrix["rawEvidenceRoot"] == "evidence/raw/formative/incumbent-baseline/bare"
    assert matrix["stateIsolation"] == {
        "schemaVersion": 1,
        "appHome": "fresh-per-attempt",
        "profile": "fresh-per-attempt",
        "repository": "fresh-fixture-only-checkout",
        "priorConversation": "none",
        "crossRunContaminationCanary": "committed-digest-only",
    }
    assert matrix["extensionAllowlist"] == []
    assert matrix["repositoryInstructionPolicy"] == {
        "schemaVersion": 1,
        "source": "fixture-only",
        "localTreatmentFilesAllowed": False,
        "superpowersAllowed": False,
        "candidatePackageAllowed": False,
    }

    by_model = {model: [cell for cell in cells if cell["modelRequest"] == model] for model in TARGET_MODELS}
    assert set(by_model) == TARGET_MODELS
    assert {cell["familyId"] for cell in cells} == set(matrix["familyIds"])
    for model, model_cells in by_model.items():
        assert {len(cell["attempts"]) for cell in model_cells} == {3}
        assert {cell["condition"]["modelRequest"] for cell in model_cells} == {model}
        assert {cell["condition"]["reasoningRequest"] for cell in model_cells} == {"high"}
        assert {cell["condition"]["conditionId"] for cell in model_cells} == {"bare"}
        assert all(cell["conditionDigest"] == canonical_contract_digest("ConditionLock", cell["condition"]) for cell in model_cells)

    for cell in cells:
        condition = parse_contract("ConditionLock", cell["condition"])
        block = parse_contract("BlockSpec", cell["block"])
        scenario = parse_contract("ScenarioCard", cell["scenario"])
        assert condition["provider"] == "google"
        assert condition["fallbackPolicy"] == "deny"
        assert condition["agentSelection"] == "antigravity"
        assert condition["subagentSelection"] == "not_applicable"
        assert condition["pluginDigest"] == "none"
        assert condition["dependencyDigests"] == {}
        assert condition["enabledComponents"] == []
        assert condition["rawInvocation"]["argv"] == [
            "agy",
            "--model",
            condition["modelRequest"],
            "--effort",
            "high",
            "--output-format",
            "stream-json",
            "--disable-slash-commands",
        ]
        assert condition["rawInvocation"]["environment"]["ABE_ANTIGRAVITY_HOME"] == "{freshAppHome}"
        assert condition["rawInvocation"]["environment"]["ABE_PRIOR_CONVERSATION"] == "none"
        assert condition["authorityManifestDigest"] == canonical_contract_digest("AuthorityManifest", scenario["authorityManifest"])
        assert condition["resourceEnvelopeDigest"] == canonical_contract_digest("ResourceEnvelope", scenario["resourceEnvelope"])
        assert condition["environmentQualificationDigest"] == canonical_contract_digest(
            "EnvironmentQualificationRecord", qualification
        )
        assert block["modelRequest"] == condition["modelRequest"]
        assert block["conditionIds"] == ["bare"]
        assert block["conditionPairLockDigest"] == "not_applicable"
        assert block["repetitions"] == 3


def test_bare_pilot_cli_writes_protected_evidence_and_model_separated_report(tmp_path):
    from abe_eval.bare_condition import analyze_bare_pilot_evidence

    qualification_path = tmp_path / "evidence" / "raw" / "qualification" / "local" / "qualification.json"
    qualification = _qualification(qualification_path)
    raw_root = tmp_path / "evidence" / "raw" / "formative" / "incumbent-baseline" / "bare"

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
            "--condition",
            "bare",
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
    assert command_result["condition"] == "bare"
    assert command_result["runsCreated"] == 84
    assert command_result["rawRoot"] == str(raw_root)
    assert set(command_result["runsByModel"]) == TARGET_MODELS
    assert command_result["runsByModel"] == {"gemini-3.1-pro-high": 42, "gemini-3.7-flash-high": 42}

    runs = [parse_contract("RunRecord", _load(path)) for path in sorted((raw_root / "runs").glob("*/run.json"))]
    assert len(runs) == 84
    assert {run["classification"]["countsInIntentionToTreat"] for run in runs} == {True}
    assert {run["observedModel"]["requestedModel"] for run in runs} == TARGET_MODELS
    assert all(run["rawEvidenceLocator"].startswith("runs/") for run in runs)
    assert not list(raw_root.glob("**/*RAW_CANARY*"))

    report = analyze_bare_pilot_evidence(MATRIX, ANALYSIS, raw_root)
    committed = _load(ANALYSIS)
    assert report == committed
    assert set(report["modelReports"]) == TARGET_MODELS
    for model_report in report["modelReports"].values():
        assert model_report["scheduledAttempts"] == 42
        assert model_report["validRunAttempts"] == 28
        assert model_report["attritionSummary"] == {
            "indeterminate": 7,
            "product_timeout": 7,
        }
        assert model_report["resourceSummary"]["medianWallTimeMs"] == 125000
        assert model_report["resourceSummary"]["p90WallTimeMs"] == 600000
        assert model_report["artifactOutcomes"]["pass"] == 7
        assert model_report["artifactOutcomes"]["fail"] == 21
        assert model_report["firstDivergenceCounts"] == {
            "missing_question_before_edit": 7,
            "stale_claim_without_verification": 7,
            "tool_failure_not_recovered": 7,
            "unknown": 21,
        }

    gap_behaviors = set().union(*(set(gap["behaviors"]) for gap in report["candidateGaps"]))
    assert gap_behaviors == set(committed["behaviorTaxonomy"])
    assert all(gap["repeatable"] for gap in report["candidateGaps"])
    assert report["protectedEvidence"] == {
        "rawRoot": "evidence/raw/formative/incumbent-baseline/bare",
        "committedRawEvidence": False,
    }
    assert report["freshBoundaryRepeat"] == {
        "familyId": "fr044-leakage-state-isolation",
        "startingDigestsMatch": True,
        "contaminationCanaryObserved": False,
    }
    assert report["treatmentAuthorship"] == {
        "candidateLanguageAuthored": False,
        "reviewScope": "identify_gap_candidates_only",
    }
    assert all(canonical_contract_digest("RunRecord", run) in report["sourceRunDigests"] for run in runs)
    assert report["qualificationDigest"] == canonical_contract_digest("EnvironmentQualificationRecord", qualification)


def test_bare_pilot_rejects_non_bare_condition_and_missing_matrix(tmp_path):
    missing = tmp_path / "missing.matrix.json"
    qualification_path = tmp_path / "qualification.json"
    _qualification(qualification_path)

    rejected = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            "evaluator",
            "abe-eval",
            "run-matrix",
            "--matrix",
            str(MATRIX),
            "--condition",
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
    missing_result = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            "evaluator",
            "abe-eval",
            "run-matrix",
            "--matrix",
            str(missing),
            "--condition",
            "bare",
            "--qualification",
            str(qualification_path),
            "--raw-root",
            str(tmp_path / "raw2"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert rejected.returncode == 2
    assert "bare_condition.condition_mismatch" in rejected.stderr
    assert missing_result.returncode == 2
    assert "FileNotFoundError" in missing_result.stderr


def test_public_method_doc_explains_boundaries_without_private_or_treatment_content():
    text = METHOD.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "uv run --project evaluator abe-eval run-matrix" in text
    assert "evidence/raw/formative/incumbent-baseline/bare" in text
    assert "fresh app/home/profile" in lowered
    assert "empty prior conversation" in lowered
    assert "no superpowers" in lowered
    assert "gap candidates only" in lowered
    assert "pselamy" not in lowered
    assert "selamy-core" not in lowered
    assert "google.com" not in lowered
    assert "/home/dev" not in lowered
    assert "RAW_CANARY_" not in text
