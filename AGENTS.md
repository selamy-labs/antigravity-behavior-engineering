# Agent Entry Point

This repository is specification-first. The committed artifacts below are
authoritative in this order:

1. `.specify/memory/constitution.md`
2. `specs/001-improve-antigravity-behavior/spec.md`
3. `specs/001-improve-antigravity-behavior/plan.md`
4. `specs/001-improve-antigravity-behavior/data-model.md` and `contracts/`
5. `specs/001-improve-antigravity-behavior/tasks.md` after explicit
   project-owner task-set approval only
6. `docs/decisions/` and `handoff/codex-execution-contract.md`

If two authoritative artifacts conflict, stop before editing implementation,
record the exact paths and clauses, and request a spec amendment. Do not choose
the convenient interpretation or invent architecture, product behavior, model
routing, a schema field, a fallback, a metric, or a gate. Before task-set
approval, `tasks.md` is a draft handoff artifact for review and no task may be
selected or executed.

## Execution Rules

- After explicit project-owner task-set approval, begin with T001. Select only
  the smallest numbered uncompleted task whose declared dependencies are merged.
- One task equals one branch and one PR. Branch:
  `codex/TNNN-<task-title-kebab-case>`. PR title:
  `[TNNN] <exact task title>`.
- Jump-box Codex is the sole implementation writer. Antigravity receives no
  repository write lease and runs only as the hermetic system under test inside
  the disposable OCI boundary required by the owning task.
- Use only the task's normative read set. Write the named failing test first,
  run the exact red command, implement the named boundary, run green and
  sentinels, then obtain fresh requirements and quality reviews.
- Record `docs/task-checkpoints/TNNN.json` using
  `handoff/task-checkpoint.schema.json` before requesting merge.
- Preserve unrelated work. Never remove or weaken a failing test, frozen
  protocol, denominator, resource envelope, evidence record, or human gate to
  make a task pass.
- Behavior tasks T022–T023 and T025–T030 must replay the current incumbent before
  creating a treatment. If the frozen gap disappeared, record `not_selected` and
  create no component body.
- Do not bulk-run Spec Kit implementation. The Codex execution contract selects
  and executes one task at a time.

## Public Boundary

- Never commit credentials, private task data, protected evidence, sealed task
  instances, confidential identifiers, private paths, or organization-only
  terminology.
- Do not copy upstream skill bodies. Superpowers remains a pinned upstream
  dependency; Prime Radiant and Selamy sources remain attributed research inputs
  unless a later human-approved license record authorizes a specific adaptation.
- The authorized Antigravity CLI is a human-supplied read-only runtime artifact.
  It never enters the repository or worker image.

## Human Stops

Automation may satisfy ordinary tests and independent reviews. It may not create
task-set approval, an approved provenance record, candidate-freeze approval,
public-release approval, target-publication authority, or signature. Before
T001, and again at T038 or T045, stage the packet, mark the external execution
state as `needs_human`, and surface the exact requested action.

Git identity, repository access, model credentials, protected evaluation inputs,
and merge/publication authority are environment-supplied prerequisites. If any
is absent, do not search for or fabricate it.
