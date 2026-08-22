from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PINNED_REVISION = "0c28dc6298eb0e6c3b47e296e82a6972a01d76d0"


def _find_optional_adapter() -> object | None:
    try:
        return importlib.util.find_spec("abe_eval.adapters.smevals")
    except ModuleNotFoundError:
        return None


def test_rejected_smevals_dependency_leaves_project_owned_path_authoritative():
    decision = (REPO_ROOT / "research" / "smevals-adapter-decision.md").read_text(encoding="utf-8")
    pyproject_text = (REPO_ROOT / "evaluator" / "pyproject.toml").read_text(encoding="utf-8")
    lock_text = (REPO_ROOT / "evaluator" / "uv.lock").read_text(encoding="utf-8")
    pyproject = tomllib.loads(pyproject_text)

    assert "Decision: REJECT" in decision
    assert PINNED_REVISION in decision
    assert "project-owned immutable ledger remains the evaluator system of record" in decision
    assert _find_optional_adapter() is None
    assert "smevals" not in {dependency.lower().split("[", 1)[0] for dependency in pyproject["project"]["dependencies"]}
    assert "smevals" not in pyproject_text.lower()
    assert "smevals" not in lock_text.lower()


def _write_smevals_run(
    root: Path,
    yaml: object,
    *,
    task_name: str,
    exit_code: int,
    outcome: str,
    extra_task_fields: dict[str, object] | None = None,
) -> None:
    run_dir = root / task_name / "bare" / "gemini-3-7-flash-high" / "2026-08-18T12-00-00Z"
    grade_dir = run_dir / "grades" / "default"
    grade_dir.mkdir(parents=True)
    grader = {"name": "default", "checks": []}
    task = {
        "name": task_name,
        "attemptId": "attempt-" + task_name,
        "runId": "run-" + task_name,
        **(extra_task_fields or {}),
    }
    run = {
        "task": task,
        "config": {"name": "bare", "runner": "fake", "model": "gemini-3.7-flash-high"},
        "started": "2026-08-18T12:00:00+00:00",
        "duration_seconds": 1,
        "exit_code": exit_code,
    }
    grade = {
        "grader": "default",
        "graded": "2026-08-18T12:01:00+00:00",
        "outcome": outcome,
        "score": 1.0 if outcome == "pass" else 0.0,
        "tags": [],
        "checks": [{"checker": "synthetic", "ok": outcome == "pass", "metrics": {"task_name": task_name}}],
    }
    (run_dir / "run.yaml").write_text(yaml.safe_dump(run, sort_keys=False), encoding="utf-8")
    (grade_dir / "grader.yaml").write_text(yaml.safe_dump(grader, sort_keys=False), encoding="utf-8")
    (grade_dir / "grade.yaml").write_text(yaml.safe_dump(grade, sort_keys=False), encoding="utf-8")
    second_grade_dir = run_dir / "grades" / "adjudicator"
    second_grade_dir.mkdir()
    (second_grade_dir / "grader.yaml").write_text(yaml.safe_dump({"name": "adjudicator", "checks": []}), encoding="utf-8")
    (second_grade_dir / "grade.yaml").write_text(
        yaml.safe_dump({**grade, "grader": "adjudicator", "outcome": "fail", "score": 0.0}, sort_keys=False),
        encoding="utf-8",
    )


def test_pinned_smevals_revision_is_lossy_for_required_known_answer_cases(tmp_path):
    smevals_cli = pytest.importorskip("smevals.cli")
    yaml = pytest.importorskip("yaml")
    grader = {"name": "default", "checks": []}
    runs_root = tmp_path / "smevals-runs"

    _write_smevals_run(runs_root, yaml, task_name="success", exit_code=0, outcome="pass")
    _write_smevals_run(runs_root, yaml, task_name="valid_start_timeout", exit_code=124, outcome="fail")
    _write_smevals_run(runs_root, yaml, task_name="pre_start_auth_failure", exit_code=64, outcome="fail")
    _write_smevals_run(
        runs_root,
        yaml,
        task_name="replacement_for_pre_start_auth_failure",
        exit_code=0,
        outcome="fail",
        extra_task_fields={"replacementForAttemptId": "attempt-pre_start_auth_failure", "retryOrdinal": 1},
    )
    _write_smevals_run(
        runs_root,
        yaml,
        task_name="missing_capture",
        exit_code=0,
        outcome="fail",
        extra_task_fields={"expectedCaptureDigest": "sha256:" + "0" * 64, "captureStatus": "missing"},
    )

    rows, ungraded, stale, failed = smevals_cli.collect_grade_rows(runs_root, "default", grader)

    rows_by_task = {row["task"]: row for row in rows}
    assert set(rows_by_task) == {"missing_capture", "replacement_for_pre_start_auth_failure", "success"}
    assert failed == 2
    assert ungraded == 0
    assert stale == 0
    for row in rows:
        assert set(row) == {"task", "config", "model", "outcome", "score", "tags", "metrics", "run_dir"}
        row_text = repr(row)
        assert "run-" not in row_text
        assert "attempt-" not in row_text
        assert "adjudicator" not in row_text
        assert "replacementForAttemptId" not in row_text
        assert "retryOrdinal" not in row_text
        assert "captureStatus" not in row_text
        assert "expectedCaptureDigest" not in row_text
