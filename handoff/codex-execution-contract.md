# Jump-Box Codex Execution Contract

## Purpose

After explicit task-set approval, jump-box Codex is the sole implementation
writer and runs the 46-task plan one task per PR, with durable state and no
architecture invention. Antigravity is not an implementation or failover writer:
it runs only as the hermetic system under test inside the repository-defined
disposable OCI boundary when a task explicitly requires it. This is a
human-supervised execution protocol, not a Ralph or autonomous-resumption loop.

## Sources of Truth

Use the authority order in `AGENTS.md`. The executor may resolve transcription or
formatting errors only when every authoritative artifact has one unambiguous
meaning. Any architectural, product, metric, model, schema, or gate ambiguity is
`needs_human`, not an invitation to improvise.

## State

- Store the single authoritative mutable file at
  `$CODEX_EXECUTION_STATE_DIR/state.json`, outside Git.
- Validate it against `handoff/execution-state.schema.json` on every load and before
  every atomic replacement.
- Write `state.json.tmp`, fsync where available, then rename atomically. Never
  repair malformed state heuristically.
- Each PR commits `docs/task-checkpoints/TNNN.json`, validated against
  `handoff/task-checkpoint.schema.json`. This is the durable public reconstruction
  seam; private execution state may be lost without losing merged-task evidence.
- State and checkpoints contain no credentials, protected evidence, private
  paths, or hidden evaluation labels.
- A ready state must include `humanGates.taskSet.status: approved` bound to the
  current commit and `tasks.md` digest before T001 can be selected.

## Deterministic Task Selection

1. Parse top-level task IDs and direct dependencies from `tasks.md`.
2. Verify IDs are exactly T001 through T046 with no duplicate or unknown edge.
3. If `humanGates.taskSet.status` is not `approved`, stop before T001 with the
   required owner approval sentence and do not create a branch.
4. Select the numerically smallest task whose status is `not_started`, all direct
   dependencies are `merged` or `not_selected` as permitted by their acceptance,
   and no human gate is pending.
5. T038 and T045 are never auto-selected past their presentation step without
   authentic human records. If no task is eligible, stop with the exact unmet
   dependency or gate.
6. Never start a second task while one is active or has an unmerged PR.

## Single-Task PR Protocol

For selected TNNN:

1. Fetch the base branch and require a clean worktree. Record base commit and
   task-entry digest. Do not use destructive reset to obtain cleanliness.
2. Create `codex/TNNN-<exact-title-kebab-case>` from the recorded base.
3. Read only the task's normative read set. Verify every named prerequisite and
   human-supplied input before editing.
4. Write the named focused test first. Run the exact red command and record its
   expected failure. An unexpected pass or unrelated failure stops the task.
5. Implement only the named files/interfaces. For behavior tasks, first execute
   the current-incumbent replay required by `tasks.md`; a vanished gap yields
   `not_selected`, not a rewritten treatment.
6. Run the focused green command, every named sentinel, and artifact validator.
   Record exact argv, exit, output digest, and relevant artifact digests.
7. Freeze the implementation commit. Give a conclusion-free package to a fresh
   requirements reviewer and a fresh quality reviewer. The implementation
   process cannot review itself.
8. Repair accepted material findings, rerun focused/sentinel evidence, create a
   new implementation commit, and re-review. Rejected findings require a
   falsifiable evidence-backed disposition.
9. Commit the final checkpoint as the last PR commit. Open one PR titled
   `[TNNN] <exact task title>` and include red, green, sentinel, reviewer, safety,
   rollback, and checkpoint evidence.
10. Merge only if all required checks pass and the environment explicitly grants
    ordinary merge authority. Otherwise set `awaiting_merge` and stop for the
    authorized merger.
11. After the system-of-record merge is observed, update private state to
    `merged`, record the merge commit, delete/retain the branch per repository
    policy, and select again.

## Failure Budget

The budget applies to unexpected failures, not the required initial red test.

| Failure class | Budget | Required action at exhaustion |
|---|---:|---|
| Same deterministic implementation/test failure with no new evidence | 3 repair cycles | `needs_human`; report signature, attempts, artifacts, and smallest unresolved decision |
| Infrastructure/tool process failure | 2 fresh-process retries | `needs_human`; do not reclassify it as product failure or silently change tools |
| Suspected flake | 1 confirmation rerun only when a frozen flake policy permits | Preserve both outcomes; otherwise treat as deterministic failure |
| Accepted material-review repair cycles | 3 | `needs_human`; likely task/architecture mismatch, no threshold weakening |
| No-progress cycles | 2 consecutive cycles | Stop; no busy looping or cosmetic changes |
| Human gate | 0 automated approvals | Stage packet and stop immediately |

Any new evidence resets only the relevant same-failure counter; it does not reset
total attempts or erase prior failures.

## Escalation Conditions

Stop in `needs_human` when any of these is true:

- authoritative artifacts conflict or omit a load-bearing decision;
- final task-set approval is absent, rejected, unsigned, or bound to different
  bytes;
- a named path, command, dependency, schema, test seam, or approval mechanism is
  absent and cannot be derived from an earlier approved task;
- an exact CLI/model/tool surface differs from qualification assumptions;
- the task would need an unapproved dependency, architecture change, public API,
  metric, threshold, denominator, fallback, or protected-data exposure;
- the worktree contains overlapping unrelated changes;
- required repository access, Git identity, credentials, protected inputs,
  reviewer independence, merge authority, or publication authority is absent;
- a public-boundary scan reports a possible secret, confidential identifier,
  private path, internal terminology, copied body, or license ambiguity;
- any failure budget is exhausted.

The escalation message contains one exact question/action, not several speculative
options. Continue unrelated eligible work only when there is no active PR and the
blocked task is not a dependency of that work.

## Recovery and Rollback

- On process restart, validate state, compare recorded base/head/PR commits with
  Git and the remote system of record, then resume the recorded phase. Never
  trust prose memory.
- If state disagrees with Git, preserve both and stop. Do not rewrite evidence.
- Before PR merge, recover by adding commits or abandon the branch through the
  repository's approved non-destructive workflow.
- After merge, rollback is a new revert PR tied to the same task checkpoint; do
  not rewrite public history.
- A behavior treatment that fails selection is deleted in the same PR and its
  `not_selected` checkpoint is preserved.
- Any candidate change after freeze invalidates the freeze approval and sealed
  eligibility. Any release-byte change after approval invalidates release
  approval and publication eligibility.

## Stop Conditions

Execution stops when:

- a human input/gate or failure budget requires `needs_human`;
- a PR is awaiting review, checks, or merge without authority to continue;
- no dependency-ready task exists;
- T045 lacks explicit target/publication authority;
- T046 proves any completion predicate missing, contradicted, weak, or
  unverified; or
- T046 is merged with every predicate proven and the final independent review
  records a ship verdict.

Only the last condition permits reporting the durable goal achieved.
