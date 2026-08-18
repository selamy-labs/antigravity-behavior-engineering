# Implementation Task-Set Adversarial Review

**Reviewed**: 2026-08-18

**Scope**: Approved `spec.md` and `plan.md` against draft `tasks.md`, its
dependency graph, and requirement traceability.

**Reviewer boundary**: The independent reviewer receives the current artifacts,
is instructed to refute executability and coverage, and makes no edits.

## Earlier Candidate Review

**Verdict**: REVISE

| Finding | Severity | Disposition |
|---|---|---|
| README, current-state, artifact manifest, and traceability text inferred that the 46-task set already had downstream execution authority. | Critical | Rewritten to state that only `spec.md` and `plan.md` are approved; `tasks.md` remains a draft pending owner approval before T001. |
| Ralph state could be initialized with all tasks `not_started` without a bound task-set approval gate. | Critical | Added `taskSet` to Ralph state, required an external signed task-set approval record in `init-ralph-state.py`, and made ready state require an approved digest-bound gate. |
| Handoff validation did not fail closed on stale task approval claims or committed approval records. | High | Extended `handoff/validate_handoff.py` to reject stale approval wording, committed approval records, missing pending task-gate state, and an initializer that lacks the exact approval requirement. |
| Worker boundary could be read as allowing ambient user state. | High | Strengthened plan, runner, and task contracts to prohibit ordinary home/workspace, `.gemini`, Antigravity state, caches, conversations, credential stores, and Docker-socket mounts. |
| Local CLI notes overfit stale version observations and could be misread as release evidence. | Medium | Reworded local observations as non-release notes and preserved the `1.1.14`-or-newer hashed authorized-artifact requirement for T013. |
| Reviewer-agent plumbing and the optional SMEvals adapter needed reinspection. | Medium | Confirmed closed reviewer package/verdict/join contracts and retained SMEvals only behind a proved-lossless adapter decision. |

The earlier candidate passed a second byte review, but that verdict was
superseded when a later, stopped task snapshot introduced additional substantive
contract fixes. The earlier verdict was not treated as authority for the later
bytes.

## Post-Stop Reconciliation Review

**Reviewer**: Gemini 3.7 Flash (High), invoked in a fresh read-only OCI
environment with slash-command and skill expansion disabled. The reviewer had
no write lease and received only the two public repository trees.

**Verdict**: `PLAN_COMPLETE`; `implementationAuthorized: false`; no unresolved
contradictions.

The reviewer inspected every differing path and required the reconciliation to:

1. retain the external, commit-and-task-digest-bound approval record and default
   denial of T001;
2. retain the approval schema, pending example state, validator enforcement,
   worker isolation, version normalization, and checksum authority;
3. adopt the role-neutral paired-review envelope and two role-specific requests;
4. adopt the exact two-model scorecard map and per-model release decisions;
5. bind the deterministic package-archive record into the candidate lock;
6. adopt lock-derived sealed `prepare`/`resume` schedule and journal behavior;
7. remove the package-lock self-digest cycle; and
8. remove the obsolete personal repository target without admitting private
   logs, paths, email addresses, credentials, or non-public provenance.

The controller applied that plan, additionally binding public specification
repository text to the owner-selected
`selamy-labs/antigravity-behavior-engineering` target. The merged task graph
still contains exactly T001 through T046 in coherent order, and the structural
validator rejects implementation roots, stale approval claims, committed
approval records, or an unbound Ralph initializer.

Independent verification counted all 33 file decisions as 24
`KEEP_CANDIDATE`, 5 `MERGE`, and 4 `TAKE_INCOMING`. That corrects a
non-normative 23/5/5 count in the reviewer's prose summary; the structured
file-decision list itself was complete and no path was omitted.

## Final Verdict

**HANDOFF READY FOR PROJECT-OWNER TASK-SET REVIEW; NOT APPROVED FOR
IMPLEMENTATION.** Mechanical validation and a clean Git commit are still
required after checksum regeneration. This review does not self-approve
`tasks.md`, T001, provenance, candidate freeze, public release, or publication
authority.
