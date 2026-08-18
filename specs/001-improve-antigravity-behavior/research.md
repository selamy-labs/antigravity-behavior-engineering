# Technical Research: Improve Antigravity Engineering Behavior

**Date**: 2026-08-18

**Status**: Plan-phase decisions; implementation remains unapproved

## Decision Summary

| Topic | Decision | Reason |
|---|---|---|
| Release surface | Antigravity CLI only | The specification explicitly gates v1 on CLI; desktop is experimental and SDK is evaluation-only |
| CLI floor | Qualify 1.1.14 first; freeze the release minimum only after conformance | Required model/effort, structured-output, headless-skill, hook-ordering, model-list, and agent-inheritance behavior accumulated through 1.1.14 |
| Runtime package | Antigravity-native plugin containing Markdown, JSON, and dependency-free ECMAScript modules | Matches the documented plugin surface while keeping hook execution inspectable and portable |
| Runtime language | Node.js 22+, ECMAScript modules, standard library only | Reliable JSON, hashing, file locking, and process behavior without a package install in the user's plugin directory |
| Maintainer toolchain | pnpm workspace plus Node's built-in test runner | One deterministic validation entry point for plugin contracts, scripts, lifecycle fixtures, and public-safety checks |
| Evaluation control plane | Python 3.12 managed by uv, with a pinned SMEvals adapter spike | SMEvals supplies useful immutable-run and re-grading concepts; the adapter must close its intention-to-treat gap before adoption |
| Isolation | Protected controller outside a disposable OCI worker, with fresh profile and repository state per run | Prevents grader leakage and cross-run state while acknowledging remote inference is not hermetic |
| Upstream behavior | Install and pin Superpowers from upstream; do not vendor its skill bodies | It is the candidate native owner of generic planning, TDD, debugging, execution, review, and completion verification |
| Original runtime behavior | Three focused skills, two candidate reviewers, two bounded hooks, and zero or one qualified rule | Each selected surface has a distinct claim and focused ablation; the rule requires proven body-level lazy application |
| Hidden grading | Controller-only deterministic checks plus blinded human/model judgment | Agent-visible runtime cannot grade itself or inspect competing conditions |
| Evidence | Append-only raw run records with immutable re-grades and a separately redacted publication tree | Supports auditability, re-analysis, privacy, and provenance |

## Antigravity Contract Findings

The current official CLI documentation identifies version 1.1.14, a plugin
root marked by `plugin.json`, and optional `skills/`, `agents/`, `rules/`,
`hooks.json`, and `mcp_config.json`. The displayed manifest schema permits only
`name` and `description`, although its example also includes `$schema`; the
documented schema URL returned 404 during research. The plan therefore keeps
version and dependency identity in a companion lock file and treats
`agy plugin validate` plus live install/discovery probes as authoritative.

Hooks are shell commands that consume JSON on standard input and emit JSON on
standard output. Their relative working directory and plugin path resolution
are not documented strongly enough to assume. The environment qualification
suite must prove command resolution before runtime hook bodies are enabled.

Skill discovery uses progressive disclosure. Evaluation must distinguish
metadata discovery from relevant body loading and must include negative
activation cases. Custom agents run in clean context, can restrict tools, and
inherit permissions; every tool name and inheritance setting must pass a no-op
probe because invalid tools can hang.

## Runtime Choice

Shipped executable scripts use `.mjs` files and only these Node capabilities:

- standard input and output for hook JSON;
- `node:crypto` for SHA-256 digests;
- `node:fs` and atomic rename for append-only, task-owned evidence;
- `node:path` for boundary-safe path resolution;
- `node:process` for explicit exit and error behavior.

The runtime package has no npm install step and no network call. A qualification
probe verifies that the hook command resolves an acceptable Node executable in
each supported CLI environment. If that cannot be guaranteed, the first release
must narrow its supported environments; it must not silently add a shell or jq
fallback with different semantics.

## Evaluator Choice

The evaluator is maintainer-only and may use a different toolchain. SMEvals
0.2.0 at public commit `0c28dc6298eb0e6c3b47e296e82a6972a01d76d0`
is MIT licensed. It separates tasks, configs, runners, graders, checks, runs,
grades, and artifacts and permits re-grading immutable runs.

Its default classification excludes every non-zero runner exit as
infrastructure failure and tops up replacements. That is incompatible with the
specification when a valid-start model loops, misuses tools, exhausts budget, or
causes a permission dead end. The first evaluator slice is therefore a
losslessness spike:

1. schedule an attempt in a project-owned append-only ledger;
2. record qualification and the exact valid-start boundary;
3. invoke a fake Antigravity runner through SMEvals;
4. force pre-start infrastructure, post-start timeout, soft denial, malformed
   stream, and ordinary task-failure cases;
5. prove every scheduled attempt survives and is classified correctly;
6. prove a new grader adds a grade without rewriting the raw run.

If all cases pass, SMEvals remains behind the adapter. If any required case
cannot be represented losslessly, the plan uses the same runner and grader
contracts with a small project-owned ledger instead. The spike has a binary
decision and does not affect the runtime plugin.

## Isolation Architecture

The evaluation has three trust zones:

1. **Protected controller**: schedules conditions, owns hidden tasks and
   graders, injects scoped credentials, and stores raw evidence.
2. **Disposable worker**: contains the pinned Antigravity CLI, target plugin
   condition, fixture repository, allowed tools, and a fresh Antigravity profile.
3. **Remote inference service**: receives model traffic through the allowed
   network path and remains outside reproducible task-state control.

The public repository supplies an OCI build context that never contains the
Antigravity binary, credentials, hidden graders, or sealed tasks. An authorized
operator supplies the CLI artifact or documented installer at build time and
injects authentication at run time through a scoped mount or credential proxy.
Image, toolchain, fixture, plugin, and starting-state digests are recorded.

A host-profile runner may exist only as a separately labeled diagnostic adapter
when authentication prevents container execution. It cannot supply release
evidence until it demonstrates equivalent fresh state and contamination checks.

## Repository Architecture

```text
plugin/                         installable, agent-visible runtime package
├── plugin.json
├── behavior-lock.json
├── skills/
├── rules/
├── agents/
├── hooks.json
├── scripts/
└── schemas/

packages/
├── contracts/                 shared schema sources and validators
├── plugin-tooling/            manifest, discovery, lifecycle, and safety probes
└── evidence-cli/              local inspection and redaction commands

evaluator/                     protected control-plane source, never installed
├── src/
├── adapters/
├── graders/
├── analysis/
└── tests/

evals/
├── formative/                 known development scenarios
├── regression/                frozen known failures
├── protocols/                 generators for sealed unseen variants
└── public-samples/             non-secret examples only

environments/
├── worker/                    public OCI build context
└── controller/                orchestration and policy manifests

tests/
├── contract/
├── plugin/
├── hooks/
├── lifecycle/
├── evaluator/
└── safety/

evidence/                      ignored protected runs; redacted reports separate
docs/
├── architecture/
├── evaluation/
├── provenance/
└── release/
```

## Composition Decisions

Superpowers remains the candidate runtime dependency for generic workflow
methods, subject to conformance on the exact CLI floor. Prime Radiant's
iterative-development project and the user's public Selamy skills are licensed
methodology inputs, not runtime dependencies in v1. Their bodies are not copied
or lightly paraphrased.

The original candidate portfolio is deliberately narrow:

- candidate rule: `engineering-evidence-kernel`, omitted if Model Decision does
  not prove body-level lazy application;
- skills: `evidence-first-framing`, `proof-obligation-contract`,
  `audited-iteration`;
- agents: `requirements-falsifier`, `quality-falsifier`;
- hooks: `evidence-observer`, `bounded-completion-gate`.

Names remain candidate names until collision tests pass. No v1 MCP server is
planned because the behavior layer needs no new external typed operation.

## Delivery Sequence Decision

Evaluation infrastructure and bare baselines precede treatment bodies. The
runtime plugin shell may be built early for lifecycle conformance, but its
behavior rule, skills, agents, and hooks are authored one at a time only after a
matched formative failure exists. Each component is retained only after its
positive case, negative activation controls, focused ablation, and regression
gate pass.

## Rejected Alternatives

| Alternative | Rejection reason |
|---|---|
| One monolithic system prompt | Taxes every turn, duplicates upstream methods, and prevents component attribution |
| Vendor Superpowers or public Selamy skill bodies | Creates ownership, update, and provenance problems without new behavior |
| Put hidden grading in runtime hooks | Lets the treatment grade itself and leaks control-plane authority |
| Dispatch reviewers on trivial work | Trivial controls must use neither reviewer; substantial release work uses both conclusion-free roles to cover requirements, quality, and completion evidence |
| Treat Flash as executor and Pro as planner | Model labels do not establish role; both must pass standalone |
| Use any local unqualified CLI observation for target evidence | A version string or ambient profile observation does not prove Gemini 3.7 Flash, isolation, headless, hook, model, or evidence-capture conformance |
| Use SMEvals without an adapter | Its default non-zero-exit classification can erase valid-start product failures |
| Ship shell plus jq hooks | Adds undocumented prerequisites and divergent platform behavior |
| Add an MCP server in v1 | No missing external operation justifies its security and availability surface |

## Open Items Resolved by Qualification, Not Guessing

These are test gates with predetermined consequences rather than product
ambiguities:

- If CLI 1.1.14 cannot resolve plugin-relative hook commands, the hook command
  packaging must change before any hook experiment.
- If Superpowers cannot install, activate, disable, and remove cleanly, it cannot
  be a release dependency; the specification must return for scope approval
  before replacing its responsibilities.
- If the target model or reasoning configuration cannot be verified strongly
  enough to prevent silent fallback, that environment cannot enter evaluation.
- If OCI execution cannot satisfy authorized authentication without exposing
  secrets, an approved ephemeral VM worker must replace it; a contaminated host
  run cannot be relabeled as hermetic evidence.
- If the SMEvals adapter loses a scheduled attempt or misclassifies a valid-start
  failure, the project-owned ledger becomes the evaluator system of record.
