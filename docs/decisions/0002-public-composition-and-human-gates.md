# ADR-0002: Compose Upstream Work and Preserve Human Release Gates

## Status

Accepted — 2026-08-18

## Context

The project draws on public methods from multiple repositories while targeting a
public artifact. Automated scanning can detect many provenance and safety
problems, but it cannot make the final legal/provenance judgment or authorize an
external publication.

## Decision

Keep Superpowers as a pinned, separately identified upstream dependency and use
Prime Radiant and Selamy sources as attributed research inputs unless a specific
adaptation later receives human license approval. Author only the missing
Antigravity-specific responsibilities locally. Require separate authentic human
records for provenance, candidate freeze, and public release. Require an exact
target repository and publication authority in addition to release approval.

Every behavior component is selected sequentially against the current incumbent,
then tested by integrated leave-one-out ablation. A component with no persistent
gap or no attributable gain is absent from the package and recorded
`not_selected`.

## Alternatives Rejected

- Vendoring public skill bodies: rejected because it obscures ownership,
  lifecycle, updates, and license duties.
- Automated license approval: rejected because scanner output is evidence, not
  human judgment.
- One blanket project approval: rejected because provenance, opening a sealed
  suite, and public publication authorize materially different actions.
- Publishing to a guessed organization: rejected because an organization name
  is not an unambiguous GitHub target or publication authority.

## Consequences

The staged release may wait at a human gate even when all automated checks pass.
That wait is a correct state, not a failure. The public package can remain small
because evidence, not a component quota, controls what ships.
