# Runtime Hook Contract

## Shared Process Rules

- Read exactly one JSON object from standard input.
- Write exactly one JSON object to standard output and diagnostics to standard
  error.
- Complete within the configured timeout; the candidate timeout is 10 seconds,
  below Antigravity's documented 30-second default.
- Make no network calls and invoke no shell.
- Resolve every workspace write beneath a validated workspace root.
- Refuse symlink traversal outside the selected evidence directory.
- Never read hidden grader or controller paths.

## Evidence Observer

The `evidence-observer` runs on `PostToolUse` and `PostInvocation` after live
conformance proves both events. It accepts Antigravity's documented common
fields plus event-specific fields. Unknown source fields are stored only inside
a redacted raw-field digest; they do not become trusted normalized fields.

For `PostToolUse`, it records:

- conversation, workspace, model, and step identity;
- tool name and a policy-redacted argument digest;
- error presence and digest;
- transcript and artifact locators after boundary validation;
- timestamp, observer version, and previous-event digest.

It appends one canonical NDJSON event and outputs:

```json
{}
```

For `PostInvocation`, it records invocation number, starting step count, model,
and content locators, then outputs an empty object. It does not inject steps or
set termination behavior.

Malformed input produces a non-zero hook exit with no partial JSON on standard
output. Qualification determines whether Antigravity isolates this failure; the
release policy must state whether observer failure is fail-open with visible
diagnostics or release-blocking. It never silently claims evidence was recorded.

## Bounded Completion Gate

The `bounded-completion-gate` runs on `Stop`. It consumes Antigravity's common
fields plus `executionNum`, `terminationReason`, `error`, and `fullyIdle`.

It is inert and permits stopping when no current workspace contains a validated,
applicable substantial TaskState. Permitting stop outputs:

```json
{
  "decision": ""
}
```

It outputs `continue` only when all of these hold:

1. a TaskState matches the current workspace and request identity;
2. the retry bound has not been reached;
3. one mechanically decidable condition is true: active work, invalid task-state
   schema, unresolved required obligation, stale passing evidence, or accepted
   material finding not freshly verified;
4. the reason names the exact IDs and condition without asserting semantic
   correctness.

Example:

```json
{
  "decision": "continue",
  "reason": "Completion evidence is stale for required obligation O-3 after change digest 8f2c…; run or record fresh evidence, or report an honest non-complete terminal state."
}
```

The initial candidate bound is one continuation for the matching task/request.
The actual frozen bound is earned by ablation. Before emitting `continue`, the
hook atomically appends a hash-chained CompletionGateEvent to the task-owned
`completion-gate.ndjson` ledger under an exclusive lock. This ledger—not
TaskState and not an inferred model counter—is the authoritative continuation
count. Duplicate/concurrent Stop delivery is idempotent by qualified
`stopSequenceId`. The evidence CLI, never the hook, atomically creates the
validated ordinal-zero `initialized` genesis event beside a new TaskState. If a
Stop sees a missing/empty ledger, that is missing history—not first use—and the
hook fails open. Malformed, foreign, stale, locked, or unwritable ledgers also
fail open. At the bound, the hook
permits stop and logs `retry_bound_reached` without consuming another count; it
cannot loop.

The hook never runs tests, changes an obligation status, evaluates source code,
or upgrades an incomplete task to complete.
