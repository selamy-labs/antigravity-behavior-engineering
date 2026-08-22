# SMEvals adapter decision

Decision: REJECT

Pinned revision evaluated: `0c28dc6298eb0e6c3b47e296e82a6972a01d76d0` from `https://github.com/prime-radiant-inc/smevals`.

## Evidence

The T011 spike used the pinned isolated command shape required by the task:

```text
uv run --project evaluator --with "smevals @ git+https://github.com/prime-radiant-inc/smevals@0c28dc6298eb0e6c3b47e296e82a6972a01d76d0" pytest evaluator/tests/test_smevals_adapter.py -q
```

At that revision, SMEvals treats any non-zero runner exit as a failed harness run. Its `collect_grade_rows` path skips those runs before returning report rows and reports them only as an excluded failed-run count. The retained known-answer fixture includes a pre-worker authentication failure and a post-valid-start timeout; SMEvals excludes both from rows. That loses the required distinction between pre-start infrastructure failure and post-valid-start product failure, and it cannot preserve intention-to-treat denominators or valid-run attrition by frozen classification reason.

The same retained fixture includes replacement linkage, a missing-capture marker, and two immutable grader directories. The report row surface does not carry our immutable `runId`, `attemptId`, replacement linkage, capture status or digest, canonical run digest, grade digest, or multiple-grade identities. It returns one row for one selected grader, while this evaluator must preserve grader outputs and reported agreement without letting an optional framework own or rewrite the authoritative ledger.

## Consequence

The project-owned immutable ledger remains the evaluator system of record. SMEvals is not added to `evaluator/pyproject.toml` or `evaluator/uv.lock`, and no `abe_eval.adapters.smevals` module is retained. The T011 regression test keeps a known-answer SMEvals fixture under the pinned isolated command and asserts that the public revision is lossy for the required cases.

This rejection does not block later use of compatible task/checker ideas, but any future adoption requires a new losslessness proof before the dependency can enter the evaluator lock.
