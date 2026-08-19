# Public-Boundary Review

**Reviewed**: 2026-08-18

**Scope**: Every committed handoff, Spec Kit, specification, contract, research,
architecture, and agent-entry artifact; no implementation or protected evidence
exists.

## Review Procedure

1. Enumerated every repository file, including dot-directories and executable
   modes.
2. Parsed every JSON document and ran the Spec Kit prerequisite check.
3. Scanned text for absolute user-home paths, private-key material, unresolved
   placeholders, credentials, private test data, organization-only terminology,
   and explicitly prohibited internal terminology supplied by the project owner.
4. Reviewed all research inputs for public URLs, immutable public commit refs,
   attribution, and claims marked as documented fact, observation, inference, or
   proposed contract.
5. Confirmed the repository contains no `plugin/`, `packages/`, `evaluator/`,
   `evals/`, `environments/`, or `tests/` implementation root before T001.
6. Confirmed `.agents/` contains only the public Spec Kit integration skills
   listed in `.specify/integrations/agy.manifest.json`.
7. Checked that no task-set approval record is committed, the execution-state
   task-set gate is pending in the example state, and initialization requires an
   external signed approval record bound to the current commit and `tasks.md`
   digest.

The protected terminology denylist is intentionally not committed. A downstream
reviewer can supply it through `PUBLIC_BOUNDARY_DENYLIST_FILE` when running
`./handoff/validate-handoff.sh`.

## Findings and Dispositions

| Finding | Disposition |
|---|---|
| One research note recorded an absolute local CLI path | Replaced with `command -v agy`; no private path remains |
| Handoff needed mutable execution state | State moved outside Git under human-supplied `CODEX_EXECUTION_STATE_DIR`; committed example is synthetic and null-initialized |
| Public specification-repository target changed during handoff | Bound clone and status text to `selamy-labs/antigravity-behavior-engineering`; repository publication remains separate from implementation authority |
| Stale text inferred final task-set approval | Replaced with an unsigned task-set gate and validator checks that reject approval inference before T001 |
| Worker boundary could be read as allowing ambient user state | Strengthened runner and task contracts to prohibit mounting ordinary home/workspace, `.gemini`, Antigravity state, caches, conversations, credential stores, and Docker socket |
| Historical local CLI observations were too specific for release evidence | Reclassified all local CLI observations as non-release notes; T013 still requires an authorized, hashed CLI artifact at or above `1.1.14` |
| Product and protected-evidence files do not exist | Correct for the controlled handoff; later tasks carry their own release-blocking scans |
| Policy documents necessarily mention classes such as confidential data and credentials | These are public safety requirements, not confidential content or secret values |

## Result

**PASS for specification handoff publication readiness after task-set-gate
corrections.** No Google-confidential
material, secret, private task/test data, private absolute path, protected
evidence, copied upstream skill body, or prohibited internal terminology was
found in the handoff tree.

This is not the later human provenance/license approval and does not authorize a
plugin release or T001. T005, T036, T041, T044, and T045 must rerun the
applicable scans over implementation and release artifacts.
