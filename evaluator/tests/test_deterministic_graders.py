from __future__ import annotations

import copy
import json
from pathlib import Path

from abe_eval.contracts import parse_contract
from abe_eval.grade import run_hidden_checks


FIXTURES = Path("tests/contract/fixtures/evaluation-contracts.json")
CONTROLLER_CANARY = "T019_CONTROLLER_CANARY_DO_NOT_EXPOSE"
REQUIRED_RESULT = "T019_REQUIRED_RESULT"


def _case_value(name: str) -> dict[str, object]:
    for case in json.loads(FIXTURES.read_text(encoding="utf-8"))["validCases"]:
        if case["name"] == name:
            return copy.deepcopy(case["value"])
    raise AssertionError(name)


def _check(check_id: str) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "checkId": check_id,
        "kind": "artifact_hidden_check",
        "implementationDigest": "sha256:" + "19" * 32,
        "inputDigest": "sha256:" + "29" * 32,
        "expectedResultDigest": "sha256:" + "39" * 32,
        "timeoutMs": 1000,
    }


def _card() -> dict[str, object]:
    card = _case_value("ScenarioCard")
    card["scenarioId"] = "scenario-t019-known-answer"
    card["checks"] = [
        _check("required-output-present"),
        _check("required-result-token"),
        _check("controller-canary-absent"),
        _check("no-placeholder-or-long-line"),
    ]
    return parse_contract("ScenarioCard", card)


def test_hidden_checks_find_planted_critical_important_and_minor_artifact_defects(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    (artifact_root / "answer.txt").write_text("wrong result with " + CONTROLLER_CANARY + "\n", encoding="utf-8")
    (artifact_root / "notes.md").write_text("TODO: finish this line\n" + ("x" * 90) + "\n", encoding="utf-8")

    result = run_hidden_checks(_card(), artifact_root)

    assert result["schemaVersion"] == 1
    assert result["outcome"] == "fail"
    assert result["artifactOutcome"] == "fail"
    assert result["severityCounts"] == {"critical": 1, "important": 2, "minor": 1}
    assert result["diagnostics"]["firstDivergenceCode"] == "none"
    assert [check["reasonCode"] for check in result["checkResults"]] == [
        "passed",
        "required_token_missing",
        "controller_canary_leaked",
        "placeholder_or_long_line",
    ]
    assert all(parse_contract("CheckResult", check) == check for check in result["checkResults"])


def test_defect_free_artifact_control_passes_all_hidden_checks(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    (artifact_root / "answer.txt").write_text(REQUIRED_RESULT + "\n", encoding="utf-8")
    (artifact_root / "notes.md").write_text("Evidence is complete.\n", encoding="utf-8")

    result = run_hidden_checks(_card(), artifact_root)

    assert result["outcome"] == "pass"
    assert result["artifactOutcome"] == "pass"
    assert result["severityCounts"] == {"critical": 0, "important": 0, "minor": 0}
    assert [check["outcome"] for check in result["checkResults"]] == ["pass", "pass", "pass", "pass"]


def test_diagnostics_cannot_override_a_failing_artifact_outcome(tmp_path):
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    (artifact_root / "answer.txt").write_text("wrong result\n", encoding="utf-8")

    result = run_hidden_checks(_card(), artifact_root)

    assert result["diagnostics"]["firstDivergenceCode"] == "none"
    assert result["outcome"] == "fail"
    assert result["artifactOutcome"] == "fail"
