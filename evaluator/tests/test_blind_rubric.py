from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from abe_eval.contracts import ContractValidationError, parse_contract
from abe_eval.rubric import adjudicate_reviewer_grades, grade_blind, rubric_digest


RUBRIC_PATH = Path("evals/protocols/engineering-rubric.json")


def _rubric() -> dict[str, object]:
    return json.loads(RUBRIC_PATH.read_text(encoding="utf-8"))


def _projection(*, reviewer_id: str = "reviewer-a", findings: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "projectionId": "blind-projection-t019",
        "reviewerId": reviewer_id,
        "blindConditionId": "condition-8d5fd1b5f0df252a",
        "blindModelId": "model-d7f1b5acd7f7d5a4",
        "artifactDigest": "sha256:" + "ab" * 32,
        "taskText": "Public synthetic task projection with normalized labels only.",
        "findings": [] if findings is None else findings,
        "calibrationSampleId": "calibration-critical-important-minor",
    }


def _finding(finding_id: str, severity: str) -> dict[str, object]:
    return {"schemaVersion": 1, "findingId": finding_id, "severity": severity, "status": "open"}


def test_grade_blind_matches_manual_calibration_sample_without_model_or_condition_leakage():
    rubric = _rubric()
    projection = _projection(
        findings=[
            _finding("critical-missing-required-output", "critical"),
            _finding("important-unverified-claim", "important"),
            _finding("minor-style-issue", "minor"),
        ]
    )

    grade = grade_blind(projection, rubric)

    assert parse_contract("ReviewerGrade", grade) == grade
    assert grade["reviewerId"] == "reviewer-a"
    assert grade["rubricDigest"] == rubric_digest(rubric)
    assert grade["calibrationDigest"] == rubric["calibrationDigest"]
    assert grade["dimensionScores"] == {
        "correctness": "1.0",
        "evidence_honesty": "2.0",
        "safety": "1.0",
    }
    assert grade["overall"] == rubric["calibrationSamples"][0]["manualOverall"]
    assert grade["findingIds"] == [
        "critical-missing-required-output",
        "important-unverified-claim",
        "minor-style-issue",
    ]
    rendered = json.dumps(grade, sort_keys=True)
    assert "gemini-3.7-flash-high" not in rendered
    assert "full" not in rendered


def test_defect_free_control_receives_top_anchored_scores():
    grade = grade_blind(_projection(findings=[]), _rubric())

    assert grade["dimensionScores"] == {
        "correctness": "5.0",
        "evidence_honesty": "5.0",
        "safety": "5.0",
    }
    assert grade["overall"] == "5.0"
    assert grade["findingIds"] == []


def test_two_reviewer_disagreement_requires_frozen_adjudication():
    rubric = _rubric()
    severe = grade_blind(_projection(reviewer_id="reviewer-a", findings=[_finding("critical-a", "critical")]), rubric)
    clean = grade_blind(_projection(reviewer_id="reviewer-b", findings=[]), rubric)

    adjudication = adjudicate_reviewer_grades([severe, clean], rubric)

    assert adjudication == {
        "schemaVersion": 1,
        "decision": "adjudication_required",
        "reason": "reviewer_disagreement",
        "reviewerIds": "reviewer-a,reviewer-b",
        "overallRange": "4.0",
    }


def test_blind_rubric_rejects_raw_condition_model_and_reference_solution_leakage():
    projection = _projection()
    projection["taskText"] = "gemini-3.7-flash-high full REFERENCE_SOLUTION: do not show"

    with pytest.raises(ContractValidationError) as excinfo:
        grade_blind(projection, _rubric())

    assert excinfo.value.reason_code == "rubric.blind_projection_leakage"
    assert excinfo.value.path == "$.taskText"


def test_rubric_digest_is_frozen_and_changes_on_anchor_tamper():
    rubric = _rubric()
    tampered = copy.deepcopy(rubric)
    tampered["dimensions"][0]["anchors"]["5"] = "Tampered top anchor"

    assert rubric["rubricDigest"] == rubric_digest(rubric)
    assert rubric_digest(tampered) != rubric["rubricDigest"]
