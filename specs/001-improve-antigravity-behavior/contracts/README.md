# Contract Index

These plan-phase contracts define boundaries that implementation and evaluation
must preserve.

| Contract | Boundary |
|---|---|
| [runner.md](runner.md) | Protected controller to disposable Antigravity worker |
| [hooks.md](hooks.md) | Antigravity hook process to runtime scripts |
| [reviewer.md](reviewer.md) | Worker to conclusion-free custom reviewer and back |
| [evidence-store.md](evidence-store.md) | Scheduled attempts, immutable raw evidence, grades, and redacted publication |

Normative entity fields and state transitions are in
[data-model.md](../data-model.md). Runtime JSON Schemas generated from these
contracts must reject unknown fields at protected boundaries and retain unknown
Antigravity event payload fields only inside an explicitly versioned raw
envelope.
