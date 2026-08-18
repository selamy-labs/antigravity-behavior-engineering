# ADR-0001: Separate the Runtime Plugin from the Protected Evaluator

## Status

Accepted — 2026-08-18

## Context

The product must change agent behavior while also measuring that change without
leaking condition labels, hidden checks, competing outcomes, or sealed tasks to
the agent. It must preserve every scheduled attempt, distinguish process state
from task success, and support reproducible public claims around remote inference.

## Decision

Use a dependency-free Node.js plugin for agent-visible runtime behavior and a
separate Python controller for scheduling, disposable OCI workers, evidence
capture, deterministic checks, blinded grading, analysis, and redaction. Mount
the authorized CLI read-only at worker runtime; never put it in source or image
layers. Keep immutable attempt identity, append-only lifecycle events, atomic
RunRecord finalization, immutable grades, and publishable redaction projections
as distinct objects.

## Alternatives Rejected

- A monolithic operating prompt: rejected because it defeats progressive
  disclosure, makes attribution weak, and burdens non-applicable tasks.
- Evaluator code inside the plugin: rejected because the agent could observe or
  influence labels and graders.
- CLI copied into the worker image: rejected because it contaminates a public
  image and weakens exact-artifact control.
- Process exit as success: rejected because soft denial, malformed capture, and
  ordinary artifact failure are distinct outcomes.

## Consequences

The system has more explicit contracts and protected storage, but public claims
can be reconstructed from immutable evidence. Remote inference remains outside
the hermetic boundary and must be reported as such.
