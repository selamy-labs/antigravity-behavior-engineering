# Requirement → Task → Proof Traceability

This handoff uses stable IDs instead of duplicating a 63-row matrix into a fourth
place that can drift.

## Canonical Join

| Join key | Requirement authority | Task authority | Planned proof and blocking gate |
|---|---|---|---|
| FR-001…FR-050 | `specs/001-improve-antigravity-behavior/spec.md` | Functional-requirement table in `tasks.md` | Matching FR row in `research/spec-plan-traceability.md` plus the listed task checkpoints |
| SC-001…SC-013 | `specs/001-improve-antigravity-behavior/spec.md` | Success-criterion table in `tasks.md` | Matching SC row in `research/spec-plan-traceability.md` plus the listed task checkpoints |
| T001…T046 | Exact task entry in `tasks.md` after owner task-set approval | Same task entry | `docs/task-checkpoints/TNNN.json`, validated by `handoff/task-checkpoint.schema.json` |

For a requirement ID, proof exists only when every task listed in the task table
has a valid merged checkpoint and the planned proof's blocking gate passes. A
test name, implementation diff, or narrative alone is insufficient. If a task is
legitimately `not_selected`, its checkpoint must prove that outcome is permitted
by the task acceptance and must not leave a requirement without another proving
task.

## Proof Authority by Workstream

| Tasks | Workstream | Authoritative proof seam |
|---|---|---|
| T001–T005 | Reproducibility, schemas, public safety | Locked manifests; canonical-contract known answers; closed-schema fixtures; safety/provenance scan reports |
| T006–T011 | Immutable fake evaluator | Schedule/pair digests; lifecycle and RunRecord fixtures; immutable evidence; blind/redacted reconstruction; optional-adapter losslessness decision |
| T012–T016 | Worker and live surface qualification | Image/layer inventory; runtime CLI-mount digest; environment/attempt qualifications; lifecycle state diff; content and execution conformance traces |
| T017–T021 | Pre-treatment portfolio and incumbents | Frozen generator/analysis/resource/cohort digests; calibrated graders; contemporaneous bare/Superpowers pair blocks; blinded baseline input |
| T022–T030 | Sequential behavior components | Current-incumbent replay digest; matched minus/plus analysis; component decision; negative controls; reviewer/hook contract evidence |
| T031–T038 | Candidate assembly and freeze | Package/lifecycle/regression/leave-one-out results; PrecisionPowerLock; provenance packet; fake sealed gate; authentic provenance and freeze approvals |
| T039–T041 | Sealed release evidence | One-use execution journal; complete ITT ledger; frozen model-separated decision; separate redaction tree and manifest |
| T042–T043 | Reference evidence | Versioned matched CLI lane; separate desktop calibration; explicit mismatch/opacity limits |
| T044–T045 | Staged and public release | Exact archive/report/evidence digests; clean-checkout validation; authentic release approval; remote publication record |
| T046 | Durable completion audit | Requirement-by-requirement classification against released digest and both reference lanes; independent ship-or-revise verdict |

## Human-Gate Join

| Gate | Task | Required authentic proof | Automation behavior |
|---|---:|---|---|
| Task set | Before T001 | Approved external task-set approval record bound to the current commit and `tasks.md` digest | Do not create a branch or run T001 before pass |
| Provenance/license | T038 | Approved ProvenanceApprovalRecord bound to source/adaptation/notice and finding digests | Stage packet, then stop |
| Candidate freeze | T038 | Approved ApprovalRecord bound to candidate, qualification, protocols, analyses, power/sample/stopping/exclusions/resources/provenance | Do not open sealed bundle before pass |
| Public release | T045 | Approved ApprovalRecord bound to archive, report, public evidence, decision, and prior approvals | Do not self-issue or infer |
| Publication authority | T045 | Exact GitHub target plus authorized publication action | Do not guess target or push |

## Mechanical Coverage Checks

`./handoff/validate-handoff.sh` proves that:

- task IDs are exactly T001–T046 and dependencies point backward;
- every task has exactly five execution steps, Files, and Acceptance;
- FR rows are exactly FR-001–FR-050 and SC rows exactly SC-001–SC-013;
- no implementation root exists before T001; and
- JSON and public-boundary structural checks pass.

These checks prove join integrity, not implementation or empirical success.
