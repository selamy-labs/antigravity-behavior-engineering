from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from abe_eval.classify import classify
from abe_eval.contracts import ContractValidationError, canonical_contract_digest, parse_contract
from abe_eval.runner import RunAttemptInputs, run_attempt
from abe_eval.schedule import build_schedule
from fakes.fake_worker import FakeWorker
from abe_eval.canonical import canonical_bytes, sha256_digest
from test_valid_start_classification import _classify, _condition, _digest, _environment, _policy, _scenario


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
        scenario = _scenario(attempt, policy)
        environment = _environment()
        worker = FakeWorker("success" if attempt["conditionId"] == "bare" else "ordinary_artifact_failure")
        unclassified = run_attempt(
            RunAttemptInputs(
                scheduled_attempt=attempt,
                condition=_condition(str(attempt["conditionId"]), environment=environment, scenario=scenario),
                scenario=scenario,
                environment_qualification=environment,
                raw_root=tmp_path,
            ),
            worker,
        )
        staged = _classify(unclassified, policy)
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
    scenario = _scenario(attempt, policy)
    environment = _environment()

    class LifecycleInspectingWorker(FakeWorker):
        def run(self, invocation):
            events = _lifecycle_events(tmp_path, str(attempt["attemptId"]))
            assert [event["phase"] for event in events] == ["scheduled", "preflight", "valid_started"]
            assert events[-1]["occurredAt"] != "none"
            assert "attemptId" not in invocation
            assert "conditionId" not in invocation
            visible_request_digest = sha256_digest(canonical_bytes({"agentInput": scenario["agentInput"]}))
            hidden_scenario_digest = sha256_digest(
                canonical_bytes({"agentInput": scenario["agentInput"], "scenarioId": scenario["scenarioId"]})
            )
            assert invocation["requestDigest"] == visible_request_digest
            assert invocation["requestDigest"] != hidden_scenario_digest
            return super().run(invocation)

    run_attempt(
        RunAttemptInputs(
            scheduled_attempt=attempt,
            condition=_condition(str(attempt["conditionId"]), environment=environment, scenario=scenario),
            scenario=scenario,
            environment_qualification=environment,
            raw_root=tmp_path,
        ),
        LifecycleInspectingWorker("success"),
    )


def test_pre_start_failure_still_stages_unclassified_outcome_and_lifecycle(tmp_path):
    attempt = _attempts()[0]
    policy = _policy()
    scenario = _scenario(attempt, policy)
    environment = _environment()
    worker = FakeWorker("pre_start_auth_failure")

    unclassified = run_attempt(
        RunAttemptInputs(
            scheduled_attempt=attempt,
            condition=_condition(str(attempt["conditionId"]), environment=environment, scenario=scenario),
            scenario=scenario,
            environment_qualification=environment,
            raw_root=tmp_path,
        ),
        worker,
    )
    staged = _classify(unclassified, policy)
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


@pytest.mark.parametrize(
    ("field", "bad_value", "failed_preflight"),
    [
        ("environmentQualificationDigest", _digest("ff"), "fixtureProvisioning"),
        ("cliDigest", _digest("ff"), "modelPreflight"),
    ],
)
def test_condition_environment_bindings_fail_before_valid_start(tmp_path, field, bad_value, failed_preflight):
    attempt = _attempts()[0]
    policy = _policy()
    scenario = _scenario(attempt, policy)
    environment = _environment()
    condition = _condition(str(attempt["conditionId"]), environment=environment, scenario=scenario)
    condition[field] = bad_value
    condition = parse_contract("ConditionLock", condition)
    worker = FakeWorker("success")

    unclassified = run_attempt(
        RunAttemptInputs(
            scheduled_attempt=attempt,
            condition=condition,
            scenario=scenario,
            environment_qualification=environment,
            raw_root=tmp_path,
        ),
        worker,
    )
    staged = _classify(unclassified, policy)

    assert worker.invocations == []
    assert [event["phase"] for event in _lifecycle_events(tmp_path, str(attempt["attemptId"]))] == [
        "scheduled",
        "preflight",
        "execution_terminal",
    ]
    assert unclassified["attemptQualification"]["validStartAt"] == "none"
    assert unclassified["attemptQualification"][failed_preflight]["result"] == "fail"
    assert unclassified["processState"]["workerProcessState"] == "not_started"
    assert staged["classification"]["class"] == "infrastructure_failure"
    assert staged["classification"]["reasonCode"] == "invalid_controller_input"


@pytest.mark.parametrize("field", ["attemptId", "runId"])
def test_runner_rejects_path_shaped_attempt_identities_before_writes(tmp_path, field):
    attempt = copy.deepcopy(_attempts()[0])
    attempt[field] = "../escaped"
    attempt = parse_contract("ScheduledAttempt", attempt)
    policy = _policy()
    scenario = _scenario(attempt, policy)
    environment = _environment()
    raw_root = tmp_path / "raw"

    with pytest.raises(ContractValidationError) as excinfo:
        run_attempt(
            RunAttemptInputs(
                scheduled_attempt=attempt,
                condition=_condition(str(attempt["conditionId"]), environment=environment, scenario=scenario),
                scenario=scenario,
                environment_qualification=environment,
                raw_root=raw_root,
            ),
            FakeWorker("success"),
        )

    assert excinfo.value.reason_code == "runner.unsafe_identifier_path"
    assert excinfo.value.path == f"$.{field}"
    assert not (tmp_path / "escaped").exists()
    assert not any(raw_root.rglob("*"))


def test_replacement_attempt_links_to_original_without_overwriting(tmp_path):
    original = _attempts()[0]
    replacement = copy.deepcopy(original)
    replacement["attemptId"] = "attempt-replacement-001"
    replacement["runId"] = "run-replacement-001"
    replacement["replacementForAttemptId"] = original["attemptId"]
    replacement["retryOrdinal"] = 1
    replacement = parse_contract("ScheduledAttempt", replacement)
    policy = _policy()
    original_scenario = _scenario(original, policy)
    replacement_scenario = _scenario(replacement, policy)
    environment = _environment()

    original_outcome = run_attempt(
        RunAttemptInputs(
            scheduled_attempt=original,
            condition=_condition(str(original["conditionId"]), environment=environment, scenario=original_scenario),
            scenario=original_scenario,
            environment_qualification=environment,
            raw_root=tmp_path,
        ),
        FakeWorker("adapter_failure"),
    )
    original_attempt_bytes = (tmp_path / "attempts" / str(original["attemptId"]) / "attempt.json").read_bytes()
    replacement_outcome = run_attempt(
        RunAttemptInputs(
            scheduled_attempt=replacement,
            condition=_condition(str(replacement["conditionId"]), environment=environment, scenario=replacement_scenario),
            scenario=replacement_scenario,
            environment_qualification=environment,
            raw_root=tmp_path,
        ),
        FakeWorker("success"),
    )

    assert replacement["replacementForAttemptId"] == original["attemptId"]
    assert replacement["retryOrdinal"] == 1
    assert (tmp_path / "attempts" / str(original["attemptId"]) / "attempt.json").read_bytes() == original_attempt_bytes
    assert original_outcome["attemptId"] == original["attemptId"]
    assert replacement_outcome["attemptId"] == replacement["attemptId"]
    assert _classify(original_outcome, policy)["classification"]["retryEligible"] is True
    assert _classify(replacement_outcome, policy)["classification"]["countsInValidRun"] is True
