# Handoff Current State

**As of**: 2026-08-18

## Terminal State of This Handoff

- Constitution, specification, plan, data model, contracts, research, and the
  46-task dependency graph are complete enough for owner review.
- The specification and implementation plan are approved. The 46-task set is
  deliberately not approved and does not authorize T001.
- No plugin, evaluator, worker, evaluation portfolio, or release-pipeline source
  has been implemented.
- The first implementation task after task-set approval is T001, “Bootstrap the
  reproducible maintainer workspace.”
- The authorized public target is `pselamy/antigravity-behavior-engineering`.
  Publication is waiting for a validated local commit plus working GitHub
  credentials/access for that exact target.
- Human gates remain unsigned: task-set approval before T001,
  provenance/license at T038, candidate freeze at T038, and public
  release/publication at T045.

## Authoritative Versions and Public Revisions

| Item | Locked or observed value | Authority |
|---|---|---|
| Spec Kit | `0.16.0` | `.specify/init-options.json`, `specify --version` validation |
| Spec Kit integration | `agy`, shell scripts, committed agent skills | `.specify/integration.json` and `.specify/integrations/agy.manifest.json` |
| Initial Antigravity qualification floor | CLI `1.1.14` | approved `plan.md`; T013 must qualify the actual downstream artifact |
| Target models | Gemini 3.7 Flash high; Gemini 3.1 Pro high | approved spec/plan; T013 freezes exact live slugs |
| Superpowers | `obra/superpowers` at `b36e0829c6d0140e93cfef2ca599b1b07d4a7797` | T021 pinned-source contract |
| Optional SMEvals adapter | `0c28dc6298eb0e6c3b47e296e82a6972a01d76d0` | T011 losslessness decision; not a required dependency |

Observed local versions are feasibility evidence, not release qualification.
The downstream environment must rerun every named preflight and may narrow the
support matrix rather than inventing a compatibility fallback.

This finalization session observed `agy --version` reporting `1.1.14` on the
local machine. Earlier below-floor local observations remain non-release
research notes. No local version observation substitutes for T013's authorized,
hashed, read-only CLI artifact qualification.

## Human-Supplied Prerequisites

These values cannot safely be inferred from the public repository:

1. Git repository access and a configured commit identity.
2. A durable directory for Ralph state (`RALPH_STATE_DIR`) outside the public
   checkout.
3. An authorized Antigravity CLI artifact and legitimate authentication/model
   access, required beginning at T013.
4. An OCI-capable disposable execution substrate, required beginning at T012.
5. Protected formative/sealed task stores and calibrated reviewers at the tasks
   that name them.
6. Normal PR merge authority for ordinary tasks, if automation is expected to
   merge rather than stop after opening a PR.
7. Human approvers for provenance, candidate freeze, and public release.
8. For publication only: working GitHub credentials/access for the authorized
   public target `pselamy/antigravity-behavior-engineering` and explicit
   publication authority at T045.

No secret value, private path, approver identity, or repository target belongs in
the public handoff until its owning gate explicitly requires a public record.

## Known Bootstrap Observation

`specify init --here --integration agy --script sh --force` was exercised in an
empty temporary directory using Spec Kit 0.16.0 and completed successfully. It
emitted an integration compatibility warning whose version notation does not
match the CLI release notation used by this plan. The committed `.specify/` and
`.agents/` trees are therefore authoritative for a clone: do not reinitialize or
change product versions merely to silence the warning. Validate the committed
skills and defer exact runtime qualification to T013.
