import copy
import json
from pathlib import Path

import pytest

from abe_eval.contracts import ContractValidationError, canonical_contract_digest, parse_contract
from abe_eval.schedule import build_schedule, import_scheduled_attempt


FIXTURE = Path("evals/protocols/fake-block.json")


def _fixture_block() -> tuple[dict[str, object], str]:
    payload = json.loads(FIXTURE.read_text())
    return payload["block"], payload["seed"]


def _attempt_digests(attempts: tuple[dict[str, object], ...]) -> tuple[str, ...]:
    return tuple(canonical_contract_digest("ScheduledAttempt", attempt) for attempt in attempts)


def test_build_schedule_preallocates_attempt_and_run_ids_before_preflight():
    block, seed = _fixture_block()

    attempts = build_schedule(block, seed)

    assert isinstance(attempts, tuple)
    assert len(attempts) == len(block["scenarioDigests"]) * block["repetitions"] * len(block["conditionIds"])
    assert len({attempt["attemptId"] for attempt in attempts}) == len(attempts)
    assert len({attempt["runId"] for attempt in attempts}) == len(attempts)
    assert all(attempt["replacementForAttemptId"] == "none" for attempt in attempts)
    assert all(attempt["retryOrdinal"] == 0 for attempt in attempts)
    assert all(attempt["randomizationProof"]["seedCommitmentDigest"] == block["randomizationSeedCommitment"] for attempt in attempts)
    assert all(parse_contract("ScheduledAttempt", attempt) == attempt for attempt in attempts)


def test_build_schedule_is_seed_reproducible_stably_digestible_and_condition_interleaved():
    block, seed = _fixture_block()

    first = build_schedule(block, seed)
    second = build_schedule(copy.deepcopy(block), seed)
    different_seed = build_schedule({**block, "randomizationSeedCommitment": "sha256:6eaa61e983ff61a7961552cb368ae6ab07df654e8b6db63bfcada529a1b9ea35"}, "alternate-seed")

    assert first == second
    assert _attempt_digests(first) == _attempt_digests(second)
    assert _attempt_digests(first) == (
        "sha256:b76faa483e98db5ef5230141f797b5d190569c0dc34a09a9c4a6ea1d11cf43ad",
        "sha256:41f9ccedfb04aee4683d187794a3cc2bfb2d7faf8f0ede2648127c0e16a43844",
        "sha256:2935f27d7c995ebbe68fb87062c833cfc42d564bd3baf59c7fa844dddf52b6cf",
        "sha256:bb696a277aa07cecafa1f84842e5bdb8c25b6a4fd32c1ff2222fc43051bec8ba",
        "sha256:93f7949e7b731a8597616630b9fc593fbc00e93f7df17222e85c50966ce27fa4",
        "sha256:31ba05036561eb93a1503fe58c9120db36af00f21caf40971bd21731470767ce",
        "sha256:9db26768b79b953901fbdcd52cf0dde1b6f9ea681fb441d5da9d86c023581670",
        "sha256:36e32ea69b50c4488fb550065d115af2858a3ec2177cb63f9ab505b2aa7619eb",
    )
    assert _attempt_digests(different_seed) != _attempt_digests(first)

    for pair_start in range(0, len(first), 2):
        pair = first[pair_start : pair_start + 2]
        assert {attempt["conditionId"] for attempt in pair} == set(block["conditionIds"])
        assert len({attempt["scenarioId"] for attempt in pair}) == 1
        assert len({attempt["repetition"] for attempt in pair}) == 1


def test_scheduled_attempt_ids_do_not_leak_condition_names_or_implicit_retries():
    block, seed = _fixture_block()

    attempts = build_schedule(block, seed)

    for attempt in attempts:
        identity_blob = attempt["attemptId"] + " " + attempt["runId"]
        assert "bare" not in identity_blob
        assert "full" not in identity_blob
        assert "retry" not in identity_blob
        assert attempt["replacementForAttemptId"] == "none"


def test_import_scheduled_attempt_rejects_tampering_after_hashing():
    block, seed = _fixture_block()
    attempt = build_schedule(block, seed)[0]
    digest = canonical_contract_digest("ScheduledAttempt", attempt)
    assert import_scheduled_attempt(copy.deepcopy(attempt), digest) == attempt

    tampered = copy.deepcopy(attempt)
    tampered["runId"] = "run-tampered-after-hash"
    with pytest.raises(ContractValidationError) as excinfo:
        import_scheduled_attempt(tampered, digest)

    assert excinfo.value.reason_code == "schedule.attempt_digest_mismatch"
