from __future__ import annotations

import copy

from abe_eval.analyze import analyze_attempts
from abe_eval.contracts import canonical_contract_digest, parse_contract
from test_evidence_store import _case_value


def _run(run_id: str, *, classification_class: str, reason_code: str, counts_valid: bool, outcome: str | None) -> dict[str, object]:
    run = _case_value("RunRecordPreWorker")
    run["runId"] = run_id
    run["attemptId"] = "attempt-" + run_id
    run["observedModel"]["requestedModel"] = "gemini-3.7-flash-high"
    run["classification"] = {
        "schemaVersion": 1,
        "class": classification_class,
        "reasonCode": reason_code,
        "policyDigest": "sha256:" + "df" * 32,
        "retryEligible": False,
        "countsInIntentionToTreat": True,
        "countsInValidRun": counts_valid,
    }
    if counts_valid:
        run["attemptQualification"] = _case_value("StagedAttemptOutcome")["attemptQualification"]
        run["processState"] = _case_value("StagedAttemptOutcome")["processState"]
        run["agentDeclaredState"] = "completed"
        run["inputPermissionState"] = "permitted"
        run["infrastructureValidity"] = "valid"
    parsed = parse_contract("RunRecord", run)
    view: dict[str, object] = {"run": parsed, "gradeOutcomes": [] if outcome is None else [outcome]}
    return view


def test_analyze_attempts_keeps_all_scheduled_itt_and_separates_valid_run_exclusions_and_agreement():
    analysis = _case_value("AnalysisLock")
    attempts = [
        _run("run-valid-pass", classification_class="gradable", reason_code="success", counts_valid=True, outcome="pass"),
        _run("run-pre-start", classification_class="infrastructure_failure", reason_code="pre_start_auth_failure", counts_valid=False, outcome=None),
        _run("run-capture", classification_class="indeterminate", reason_code="capture_truncated", counts_valid=False, outcome="fail"),
    ]

    scorecard = analyze_attempts(analysis, attempts)

    parse_contract("Scorecard", scorecard)
    assert scorecard["scorecardId"] == "scorecard-analysis-001"
    assert scorecard["candidateDigest"] == "not_applicable"
    assert scorecard["analysisLockDigest"] == canonical_contract_digest("AnalysisLock", analysis)
    assert scorecard["modelRequest"] == "gemini-3.7-flash-high"
    assert scorecard["metrics"] == {
        "intention_to_treat_attempts": {"schemaVersion": 1, "value": "3", "uncertainty": "0"},
        "valid_run_attempts": {"schemaVersion": 1, "value": "1", "uncertainty": "0"},
        "valid_run_success_rate": {"schemaVersion": 1, "value": "1.0", "uncertainty": "0"},
    }
    assert scorecard["attritionSummary"] == {
        "excluded_indeterminate": "1",
        "excluded_pre_start_auth_failure": "1",
        "itt_total": "3",
        "valid_run_total": "1",
    }
    assert scorecard["graderAgreement"] == {"gradable_runs_with_grades": "1", "raw_agreement": "1.0"}
    assert scorecard == analyze_attempts(copy.deepcopy(analysis), copy.deepcopy(attempts))
