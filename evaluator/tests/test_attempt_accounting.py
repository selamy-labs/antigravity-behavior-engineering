from __future__ import annotations

import copy
import json
from pathlib import Path

from abe_eval.classify import classify
from abe_eval.contracts import canonical_contract_digest, parse_contract
from abe_eval.runner import RunAttemptInputs, run_attempt
from abe_eval.schedule import build_schedule
from fakes.fake_worker import FakeWorker
from test_valid_start_classification import _condition, _environment, _policy, _scenario


FIXTURE = Path("evals/protocols/fake-block.json")


def _attempts() -> tuple[dict[str, object], ...]:
    payload = json.loads(FIXTURE.read_text())
    return tuple(parse_contract("ScheduledAttempt", attempt) for attempt in build_schedule(payload["block"], payload["seed"]))


def _lifecycle_events(root: Path, attempt_id: str) -> list[dict[str, object]]:
    path = root / "attempts" / attempt_id / "lifecycle.ndjson"
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_runner_accounts_for_every_scheduled_attempt_without_finalizing_runs(tmp_path):
    attempts = _attempts()
    policy = _policy()
    staged_by_attempt: dict[str, dict[str, object]] = {}

    for attempt in attempts:
        worker = FakeWorker("success" if attempt["conditionId"] == "bare" else "ordinary_artifact_failure")
        unclassified = run_attempt(
            RunAttemptInputs(
                scheduled_attempt=attempt,
                condition=_condition(str(attempt["conditionId"])),
                scenario=_scenario(attempt, policy),
                environment_qualification=_environment(),
                raw_root=tmp_path,
            ),
            worker,
        )
        staged = classify(unclassified, policy)
        staged_by_attempt[str(attempt["attemptId"])] = staged

        events = _lifecycle_events(tmp_path, str(attempt["attemptId"]))
        assert [event["sequence"] for event in events] == list(range(len(events)))
        assert [event["phase"] for event in events] == ["scheduled", "preflight", "valid_started", "execution_terminal"]
        assert events[-1]["terminalKind"] == "agent_finished"
        assert unclassified["lifecycleEventDigests"] == [
            canonical_contract_digest("AttemptLifecycleEvent", event) for event in events
        ]
        assert unclassified["attemptQualification"]["validStartAt"] == events[2]["occurredAt"]
        assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()
        assert all(event["phase"] != "run_finalized" for event in events)
        assert staged["classification"]["countsInIntentionToTreat"] is True

    assert set(staged_by_attempt) == {str(attempt["attemptId"]) for attempt in attempts}
    assert all(staged["classification"]["countsInValidRun"] for staged in staged_by_attempt.values())


def test_valid_started_event_is_durable_before_worker_input_visibility(tmp_path):
    attempt = _attempts()[0]
    policy = _policy()

    class LifecycleInspectingWorker(FakeWorker):
        def run(self, invocation):
            events = _lifecycle_events(tmp_path, str(attempt["attemptId"]))
            assert [event["phase"] for event in events] == ["scheduled", "preflight", "valid_started"]
            assert events[-1]["occurredAt"] != "none"
            assert "attemptId" not in invocation
            assert "conditionId" not in invocation
            return super().run(invocation)

    run_attempt(
        RunAttemptInputs(
            scheduled_attempt=attempt,
            condition=_condition(str(attempt["conditionId"])),
            scenario=_scenario(attempt, policy),
            environment_qualification=_environment(),
            raw_root=tmp_path,
        ),
        LifecycleInspectingWorker("success"),
    )


def test_pre_start_failure_still_stages_unclassified_outcome_and_lifecycle(tmp_path):
    attempt = _attempts()[0]
    policy = _policy()
    worker = FakeWorker("pre_start_auth_failure")

    unclassified = run_attempt(
        RunAttemptInputs(
            scheduled_attempt=attempt,
            condition=_condition(str(attempt["conditionId"])),
            scenario=_scenario(attempt, policy),
            environment_qualification=_environment(),
            raw_root=tmp_path,
        ),
        worker,
    )
    staged = classify(unclassified, policy)
    events = _lifecycle_events(tmp_path, str(attempt["attemptId"]))

    assert worker.invocations == []
    assert [event["phase"] for event in events] == ["scheduled", "preflight", "execution_terminal"]
    assert events[-1]["terminalKind"] == "preflight_failed"
    assert unclassified["processState"]["workerProcessState"] == "not_started"
    assert unclassified["attemptQualification"]["validStartAt"] == "none"
    assert staged["classification"]["class"] == "infrastructure_failure"
    assert staged["classification"]["countsInIntentionToTreat"] is True
    assert staged["classification"]["countsInValidRun"] is False
    assert (tmp_path / "staged" / str(attempt["runId"]) / "unclassified-outcome.json").exists()
    assert not (tmp_path / "runs" / str(attempt["runId"]) / "run.json").exists()


def test_replacement_attempt_links_to_original_without_overwriting(tmp_path):
    original = _attempts()[0]
    replacement = copy.deepcopy(original)
    replacement["attemptId"] = "attempt-replacement-001"
    replacement["runId"] = "run-replacement-001"
    replacement["replacementForAttemptId"] = original["attemptId"]
    replacement["retryOrdinal"] = 1
    replacement = parse_contract("ScheduledAttempt", replacement)
    policy = _policy()

    original_outcome = run_attempt(
        RunAttemptInputs(
            scheduled_attempt=original,
            condition=_condition(str(original["conditionId"])),
            scenario=_scenario(original, policy),
            environment_qualification=_environment(),
            raw_root=tmp_path,
        ),
        FakeWorker("adapter_failure"),
    )
    original_attempt_bytes = (tmp_path / "attempts" / str(original["attemptId"]) / "attempt.json").read_bytes()
    replacement_outcome = run_attempt(
        RunAttemptInputs(
            scheduled_attempt=replacement,
            condition=_condition(str(replacement["conditionId"])),
            scenario=_scenario(replacement, policy),
            environment_qualification=_environment(),
            raw_root=tmp_path,
        ),
        FakeWorker("success"),
    )

    assert replacement["replacementForAttemptId"] == original["attemptId"]
    assert replacement["retryOrdinal"] == 1
    assert (tmp_path / "attempts" / str(original["attemptId"]) / "attempt.json").read_bytes() == original_attempt_bytes
    assert original_outcome["attemptId"] == original["attemptId"]
    assert replacement_outcome["attemptId"] == replacement["attemptId"]
    assert classify(original_outcome, policy)["classification"]["retryEligible"] is True
    assert classify(replacement_outcome, policy)["classification"]["countsInValidRun"] is True
