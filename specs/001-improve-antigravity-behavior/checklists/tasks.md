# Implementation Task-Set Quality Checklist

**Purpose**: Verify that `tasks.md` is executable, causally ordered, fully
traceable, and ready for project-owner approval without authorizing
implementation implicitly.

**Created**: 2026-08-18

**Task set**: [tasks.md](../tasks.md)

## Gate Discipline

- [x] Specification and implementation-plan approvals are recorded
- [x] Task set records its own unapproved status
- [x] No implementation task has started and no source root exists
- [x] Task-set, provenance, candidate-freeze, and public-release approvals remain
  separate human gates
- [x] Public release does not depend on the private desktop calibration; only the
  stronger durable-goal claim does

## Task Executability

- [x] Task IDs are unique and sequential from T001 through T046
- [x] Every task names exact source and test files, prerequisite tasks,
  interfaces or command contracts, a failing-first check, focused verification,
  sentinels, fresh review, and an acceptance condition
- [x] Setup/configuration is folded into independently testable deliverables
  rather than isolated scaffolding tickets
- [x] Runtime component tasks can end by rejecting and removing an unproven
  candidate
- [x] All named downstream interfaces are created by an earlier task
- [x] No task contains TODO/TBD/FIXME or unresolved prose/command placeholders

## Dependency and Causal Integrity

- [x] Immutable contracts, fake evidence, and raw-to-report reconstruction
  precede target-model work
- [x] Live environment qualification precedes behavioral baselines
- [x] Bare and Superpowers-only baselines precede local treatment bodies
- [x] Rule, skill, reviewer, and hook treatments enter sequentially against a
  stable incumbent
- [x] Integrated leave-one-out ablations remove unneeded components before
  candidate freeze
- [x] Precision/power, provenance, lifecycle, and regression artifacts all bind
  candidate-freeze approval before sealed execution
- [x] The dependency graph is acyclic and every referenced task ID exists

## Scope and Traceability

- [x] All 50 functional requirements map to implementing and proving tasks
- [x] All 13 success criteria map to proving tasks
- [x] Every approved plan phase and planned source subsystem has a task owner
- [x] CLI-only release scope, dual standalone models, zero-or-one rule, three
  original skills, two agents, two hooks, packaging, evaluator, evidence, and
  both Codex reference lanes remain in scope
- [x] Superpowers stays upstream; Prime Radiant and Selamy sources are not copied
- [x] Public-safety, provenance, trust boundaries, redaction, resource envelopes,
  and all FR-044 regressions have explicit tasks and gates

## Validation

- [x] Spec Kit recognizes `tasks.md` and all prerequisite design artifacts
- [x] Placeholder, task-ID, unknown-reference, trace-row, trailing-whitespace,
  and `git diff --check` validations pass
- [x] Task-gate constitution check covers all nine principles without an
  exception
- [ ] Independent adversarial task review finds no blocking omission,
  contradiction, unowned interface, or invalid gate

## Notes

- Task-set approval remains pending.
- No task may begin until that approval is explicit.
