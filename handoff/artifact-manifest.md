# Handoff Artifact Manifest

The checksum authority is `handoff/artifact-manifest.sha256`. It covers every
authoritative handoff/specification artifact needed to stop at the task-set
approval gate and excludes Git internals, the checksum file itself, and
generated/private execution state.

| Artifact family | Authoritative paths | Version/reference |
|---|---|---|
| Agent entry and overview | `README.md`, `AGENTS.md` | Handoff 2026-08-18 |
| Spec Kit scaffold | `.specify/`, `.agents/skills/speckit-*` | Spec Kit 0.16.0; integration `agy` |
| Governance | `.specify/memory/constitution.md` | Constitution 1.0.1 |
| Feature package | `specs/001-improve-antigravity-behavior/` | Spec and plan approved 2026-08-18; 46-task set pending owner approval |
| Architecture decisions | `docs/architecture/`, `docs/decisions/` | ADR-0001 and ADR-0002 accepted |
| Research and review | `research/` | Public sources and adversarial review records |
| Execution handoff | `handoff/` excluding mutable state | Jump-box Codex contract and JSON Schema 2020-12 formats |

The repository commit is intentionally reported by Git rather than embedded in a
file inside that same commit, which would create a circular identity. Verify it
with `git rev-parse HEAD` and verify content with:

```bash
shasum -a 256 -c handoff/artifact-manifest.sha256
```
