# Implementation Task-Set Adversarial Review

**Reviewed**: 2026-08-18

**Scope**: Approved `spec.md` and `plan.md` against draft `tasks.md`, its
dependency graph, and requirement traceability.

**Reviewer boundary**: The independent reviewer receives the current artifacts,
is instructed to refute executability and coverage, and makes no edits.

## Round 1

**Verdict**: REVISE

| Finding | Severity | Disposition |
|---|---|---|
| README, current-state, artifact manifest, and traceability text inferred that the 46-task set already had downstream execution authority. | Critical | Rewritten to state that only `spec.md` and `plan.md` are approved; `tasks.md` remains a draft pending owner approval before T001. |
| Ralph state could be initialized with all tasks `not_started` without a bound task-set approval gate. | Critical | Added `taskSet` to Ralph state, required an external signed task-set approval record in `init-ralph-state.py`, and made ready state require an approved digest-bound gate. |
| Handoff validation did not fail closed on stale task approval claims or committed approval records. | High | Extended `handoff/validate_handoff.py` to reject stale approval wording, committed approval records, missing pending task gate state, and an initializer that lacks the exact approval requirement. |
| Worker isolation text did not explicitly exclude ambient Gemini/Antigravity state, host credential stores, ordinary workspaces, or Docker socket exposure. | High | Strengthened `plan.md`, `tasks.md`, and `contracts/runner.md` to require disposable non-root workers, dropped capabilities, `no-new-privileges`, no Docker socket, and no ambient `.gemini` or Antigravity state mounts. |
| Local CLI notes overfit stale version observations and could be misread as release evidence. | Medium | Reworded local observations as non-release notes and preserved the `1.1.14`-or-newer hashed authorized artifact requirement for T013. |
| Reviewer-agent production plumbing and optional SMEvals adapter decisions needed reinspection after prior fixes. | Medium | Confirmed T003, T011, T027, T028, `data-model.md`, `contracts/reviewer.md`, and `plan.md` now include closed review package/verdict/join contracts and make SMEvals optional behind a losslessness decision. |

## Round 2

**Verdict**: HANDOFF READY FOR OWNER TASK-SET APPROVAL; NOT APPROVED FOR
IMPLEMENTATION.

The final byte review must still be followed by mechanical validation and a Git
commit. This review does not self-approve `tasks.md`, provenance, candidate
freeze, public release, publication authority, or any implementation task.
