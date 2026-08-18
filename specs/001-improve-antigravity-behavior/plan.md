# Antigravity Behavior Engineering Implementation Plan

> **For agentic workers:** After this plan and the generated `tasks.md` are
> approved, use `superpowers:subagent-driven-development` or
> `superpowers:executing-plans` to execute one independently verifiable task at
> a time. No implementation skill is authorized by this document alone.

**Branch**: `001-improve-antigravity-behavior`

**Date**: 2026-08-18

**Spec**: [spec.md](spec.md)

**Status**: Approved — 2026-08-18

**Approval evidence**: The project owner explicitly stated “I approve the
implementation plan.” in the controlling project conversation on 2026-08-18.

**Goal**: Build a public Antigravity CLI plugin and protected evaluation system
that measurably improve Gemini 3.7 Flash and Gemini 3.1 Pro on deep problem
framing, durable iterative implementation, real verification, and adversarial
repair without imposing disproportionate ceremony.

**Architecture**: The installed plugin is a small agent-visible package with
three original skills, candidate reviewer agents, bounded runtime hooks, and at
most one rule whose body ships only if live CLI conformance proves native lazy
application compatible with SC-007. A separate protected controller schedules
clean disposable workers, captures immutable evidence, and grades real artifacts
without exposing hidden material to the plugin. Treatment bodies are authored
only after matched baseline failures exist.

**Tech Stack**: Antigravity CLI 1.1.14 as the initial qualification floor;
Node.js 22+ ECMAScript modules with no runtime dependencies; pnpm for maintainer
tooling; Python 3.12 and uv for the evaluation control plane; pinned SMEvals
0.2.0 behind a losslessness adapter decision; OCI workers; JSON, JSON Schema,
Markdown, NDJSON, Git, and SHA-256 content addressing.

## Global Constraints

- Antigravity CLI is the only v1 release-gating product surface.
- Gemini 3.7 Flash and Gemini 3.1 Pro each run the entire locked suite alone;
  results remain separate.
- No Google-confidential material, credentials, hidden graders, private
  infrastructure assumptions, or unapproved copied content enters public files.
- Upstream-native public skills remain pinned upstream dependencies; their skill
  bodies are not republished.
- Evaluator and hidden-grader code never ships in the agent-visible plugin.
- Runtime hooks are deterministic, network-free, bounded, and mechanically
  scoped; they never decide semantic correctness.
- Every behavior component begins with a failing or underperforming matched
  baseline and needs positive, negative, ablation, and regression evidence.
- Bare and treatment runs use matched models, reasoning settings, authority,
  tools, resource envelopes, and fresh state.
- A process exit, agent declaration, deterministic grade, and blind judgment are
  separate evidence fields.
- Specification approval, plan approval, task approval, candidate freeze, and
  public release are separate human gates.

---

## Summary

The implementation proceeds as an evidence system before it becomes an
instruction system. The first walking slice schedules a fake attempt, crosses a
precise valid-start boundary, captures an immutable run, classifies both
pre-start and post-start failure correctly, re-grades without rewriting raw
evidence, and publishes a redacted sample. The second slice qualifies the real
Antigravity CLI and plugin lifecycle in a disposable worker. Only then are bare
and Superpowers baselines captured.

The runtime portfolio is developed one component at a time:

1. candidate `engineering-evidence-kernel` rule, retained only after native
   body-loading conformance and behavioral ablation;
2. `evidence-first-framing` skill;
3. `proof-obligation-contract` skill;
4. `audited-iteration` skill;
5. one then two conclusion-free reviewer agents;
6. `evidence-observer` hook;
7. `bounded-completion-gate` hook.

Each step compares the incumbent without and with the component. A component
that fails to cause lift, over-triggers, duplicates Superpowers, or exceeds its
resource envelope is simplified or deleted before the next component enters the
incumbent.

## Technical Context

**Language/Version**: Node.js `>=22 <25` for runtime and maintainer JavaScript;
Python `>=3.12 <3.14` for the protected evaluator

**Primary Dependencies**: no runtime npm dependency; pnpm workspace tooling;
uv; SMEvals 0.2.0 at commit
`0c28dc6298eb0e6c3b47e296e82a6972a01d76d0` only if the adapter spike passes

**Storage**: local append-only content-addressed files for protected evidence;
workspace-local JSON/NDJSON for applicable substantial task state

**Testing**: `node --test`, `pytest`, JSON contract tests, fake-runner integration,
OCI qualification, plugin lifecycle tests, hidden deterministic checks, blinded
review, and controlled repeated behavioral evaluation

**Target Platform**: Antigravity CLI on release-qualified macOS and Linux
environments; OCI Linux workers for primary automated evidence; desktop/IDE
experimental; SDK evaluation-only

**Project Type**: installable CLI plugin plus maintainer-only evaluation system

**Performance Goals**: runtime hook p95 below 250 ms on contract fixtures, 10 s
hard hook timeout, no runtime network access, no unbounded completion
continuation, and all behavioral quality within frozen per-family resource
envelopes

**Constraints**: remote inference is outside hermeticity; exact model identity may
be only partly observable; no silent fallback; no modification of ordinary user
profiles during automated tests; protected evidence and sealed tasks remain
outside workers

**Scale/Scope**: one plugin, zero or one qualified rule, three original skills,
two candidate reviewers, two runtime hooks, at least twelve scenario families,
two standalone models, focused ablations, full-package confirmation, and two
separately reported Codex reference lanes

## Constitution Check

*Gate result after project-owner plan approval: PASS, conditional on executing
the plan in the stated order. Re-check after task-set approval, after the
evaluator contracts, and again before candidate freeze.*

| Principle | Plan evidence | Result |
|---|---|---|
| Behavioral Outcomes Over Artifacts | Every component has one claim, task family, negative control, and removal rule | Pass |
| Eval-First Behavior Engineering | Evaluator and matched baselines precede treatment bodies | Pass |
| Evidence Before Completion | Real-interface checks and immutable raw evidence outrank self-report | Pass |
| Full Surface, Clear Responsibilities | Rule, skill, agent, hook, plugin, and control plane have distinct boundaries | Pass |
| Models Are Measured, Not Stereotyped | Both models run the full suite alone under a common contract | Pass |
| Progressive Context and Durable State | One compact rule, focused skills, and task-local versioned state | Pass |
| Independent Adversarial Iteration | Conclusion-free reviewers and repair closure are explicit ablations | Pass |
| Public-Safe Composition and Attribution | Upstream pinning, no body copying, safety scan, and human provenance gate | Pass |
| Hermetic Task Environments, Honest Inference Boundary | Disposable workers and protected graders; remote inference disclosed | Pass |

No constitutional violation requires a complexity exception.

## Project Structure

### Documentation for this feature

```text
specs/001-improve-antigravity-behavior/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── README.md
│   ├── runner.md
│   ├── hooks.md
│   ├── reviewer.md
│   └── evidence-store.md
├── checklists/
│   ├── requirements.md
│   └── plan.md
└── tasks.md                      created only after plan approval
```

### Source code at repository root

```text
plugin/
├── plugin.json                   official minimal Antigravity manifest
├── behavior-lock.json            version, dependency, component, and file lock
├── skills/
│   ├── evidence-first-framing/SKILL.md
│   ├── proof-obligation-contract/SKILL.md
│   └── audited-iteration/SKILL.md
├── rules/engineering-evidence-kernel.md  present only after rule qualification
├── agents/
│   ├── requirements-falsifier.md
│   └── quality-falsifier.md
├── hooks.json
├── scripts/
│   ├── evidence-observer.mjs
│   ├── bounded-completion-gate.mjs
│   └── runtime-lib.mjs
└── schemas/
    ├── task-state.schema.json
    ├── evidence-event.schema.json
    └── reviewer-verdict.schema.json

packages/
├── contracts/
│   ├── src/
│   └── test/
├── plugin-tooling/
│   ├── bin/
│   ├── src/
│   └── test/
└── evidence-cli/
    ├── bin/
    ├── src/
    └── test/

evaluator/
├── pyproject.toml
├── uv.lock
├── src/abe_eval/
│   ├── cli.py
│   ├── schedule.py
│   ├── qualify.py
│   ├── runner.py
│   ├── classify.py
│   ├── evidence.py
│   ├── blind.py
│   ├── grade.py
│   ├── analyze.py
│   ├── redact.py
│   └── adapters/smevals.py
└── tests/

evals/
├── formative/
├── regression/
├── protocols/
├── public-samples/
└── schemas/

environments/
├── worker/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   └── verify-image.mjs
└── controller/
    ├── network-policy.json
    └── mount-policy.json

tests/
├── contract/
├── plugin/
├── hooks/
├── lifecycle/
├── evaluator/
├── provenance/
└── safety/

docs/
├── architecture/
├── evaluation/
├── provenance/
└── release/
```

**Structure Decision**: Keep the installed plugin physically separate from
maintainer tooling and protected evaluation source. Use a small pnpm workspace
for JavaScript contracts and lifecycle tooling and an independent uv project for
the evaluator. Store only public formative/regression examples and sealed-task
protocols in the repository; sealed instances and raw evidence live outside Git.

## Component Boundaries

```text
protected controller
  -> schedules attempt and mounts agent-visible projection
  -> disposable worker
       -> pinned Antigravity CLI
       -> selected plugin condition
       -> fixture repository and fresh profile
       -> remote Gemini inference
       -> raw worker evidence
  -> imports immutable evidence
  -> deterministic hidden grading
  -> blinded judgment and adjudication
  -> redacted publishable report
```

The runtime plugin never calls the controller. The controller never inserts
grader output into a worker. Review agents are worker-side, conclusion-free
quality roles and are not the release graders.

## Implementation Phases and Gates

### Phase 0 — Repository and contract foundation

**Purpose**: Create deterministic validation without shipping behavior.

**Outputs**:

- root `package.json`, pinned `pnpm-workspace.yaml`, lockfile, formatting and
  verification commands;
- evaluator `pyproject.toml` and `uv.lock`;
- JSON Schemas for PackageLock, TaskState, CompletionGateEvent, EvidenceEvent,
  ReviewPackageInput, ReviewRequest, ReviewerFinding, ReviewJoinRecord,
  ScenarioCard, ConditionLock, ConditionPairLock, BlockSpec, MatrixLock,
  AnalysisLock, ResourceEnvelope, ScheduledAttempt, WorkerInvocation,
  AttemptLifecycleEvent, EnvironmentQualificationRecord,
  QualificationProtocol, AttemptQualificationRecord,
  UnclassifiedStagedAttemptOutcome,
  StagedAttemptOutcome, RunRecord, GradeRecord, PrecisionPowerLock,
  Scorecard, SafetyReport, ProvenanceInventory, BlindedBaselineInput,
  ReleaseCandidateLock, ApprovalRecord, ProvenanceApprovalRecord,
  ReleaseGateDecision, and ReviewerVerdict;
- canonical JSON, digest, path-boundary, atomic-write, and manifest libraries;
- public-safety, license, provenance, placeholder, collision, and manifest
  validators;
- contract fixtures for valid, invalid, boundary, and forward-version cases.

**Verification**:

- `pnpm verify` passes from a clean checkout without network or model access;
- malformed or unknown contract fields fail with stable reason codes;
- canonicalization produces identical digests across Node and Python;
- safety fixtures prove both detection and non-detection on benign public text.

**Gate**: No plugin behavior file exists beyond an inert manifest fixture.

### Phase 1 — Immutable evaluator walking slice

**Purpose**: Prove the measurement system cannot erase or relabel failure.

**Outputs**:

- preallocated ScheduledAttempt ledger and randomized block scheduler;
- allocation of `runId` with every schedule, a monotonic attempt lifecycle, and
  explicit replacement links for capped retries;
- runner-owned StagedAttemptOutcome through `execution_terminal`, followed by
  evidence-importer-only atomic RunRecord finalization and `run_finalized` event;
- fake worker covering pre-start auth failure, valid-start timeout, soft denial,
  malformed NDJSON, safety refusal, capture truncation, grader leakage, test
  flake, ordinary artifact failure, and success;
- protected evidence importer, immutable re-grading, blind projection, redactor,
  and intention-to-treat plus valid-run report;
- SMEvals adapter losslessness spike with a recorded adopt-or-reject decision.

**Verification**:

- every scheduled fake attempt appears in intention-to-treat output;
- an invalid pre-worker controller input still finalizes its preallocated
  RunRecord with `workerProcessState: not_started`, and a replacement retains a
  link to that original attempt;
- the condition-pair validator rejects a model, reasoning, authority, tool,
  resource, or environment mismatch before either agent receives input;
- valid-start failures remain product failures even with non-zero process exits;
- capped replacements retain the original failed attempt;
- a new grader adds a grade and leaves prior bytes unchanged;
- condition/model names are absent from blind projections;
- redaction canaries are withheld while required audit fields remain.

**Gate**: An independent manual inspection reproduces the fake scorecard from
raw evidence before paid target-model work is authorized.

### Phase 2 — Disposable worker and Antigravity qualification

**Purpose**: Establish that the real harness obeys the runner, extension, and
capture contracts.

**Outputs**:

- OCI worker that receives the authorized CLI as a protected read-only runtime
  mount, validates its digest, never embeds it in an image layer, never mounts
  ambient Gemini/Antigravity user state or a Docker socket, and runs non-root
  with dropped capabilities and `no-new-privileges`;
- fresh Antigravity profile and repository provisioning;
- live CLI/version/model/effort/unknown-model preflight;
- JSON and NDJSON stream contract probes;
- inert plugin install, validate, list, discovery, enable, disable, uninstall,
  rollback, and state-diff fixtures;
- hook command-resolution and failure-policy probes;
- instrumented Rule `Model Decision` conformance that distinguishes description
  discovery from body application using the strongest observable customization
  trace; if body-level selective application is unobservable or non-applicable
  tasks receive the body, the rule surface is disqualified for v1;
- custom-agent tool-list, inheritance, permission, idle, timeout, and cleanup
  probes;
- reusable EnvironmentQualificationRecord and support-matrix evidence; every
  behavioral run separately records its AttemptQualificationRecord.

**Verification**:

- Gemini 3.7 Flash high and Gemini 3.1 Pro high are live and fail closed when
  misspelled;
- requested model and effort appear in the strongest observable run metadata;
- exactly one init and result event are captured per ordinary run;
- disablement removes prompt and hook contributions immediately;
- uninstall restores the pre-install fixture manifest byte-for-byte except for
  declared Antigravity-owned volatile files;
- no credential or CLI binary appears in the public image context or evidence.

**Gate**: The exact CLI, image, model, and extension configuration earns a
qualification digest. A local, unqualified CLI observation cannot substitute.

### Phase 3 — Scenario portfolio and incumbent baselines

**Purpose**: Create measured problems before creating treatments.

**Outputs**:

- frozen TaskFamily registry and ScenarioCard generator protocols;
- immutable per-family intervention and analysis locks covering inputs, starting
  state, checks, hidden material, authority, resources, applicability, decision
  points, evidence seams, workflow tier, classifications, weights, exclusions,
  metrics, unit of analysis, scenario clustering, model effects, missing-data
  rules, multiplicity, confidence level, margins, and analysis before any
  treatment run in that family;
- ConditionPairLocks binding baseline and treatment model, reasoning, authority,
  tools, ResourceEnvelope, environment, and allowed condition difference before
  randomized dispatch;
- formative positive and negative scenarios for framing, obligations,
  iteration, review, hooks, lifecycle, safety, and proportionality;
- dedicated completion-honesty family with a critical-negative cohort of
  distinct failing, missing, and indeterminate-check variants and a disjoint
  positive cohort of working-evidence variants; its frozen AnalysisLock uses
  the scenario variant as the unit, evaluates the critical gate separately for
  each model under the `full` release-candidate condition, applies a one-sided
  95% Clopper-Pearson upper bound and zero-tolerance failure to the negative
  cohort only, and measures successful-completion recall on the positive cohort
  only;
- frozen honesty reduction policy: all original and replacement attempts for
  one model-condition-variant key reduce to one outcome; any critical false
  completion is an event, a variant is evaluable only when at least one attempt
  yields a gradable terminal claim state, otherwise it is attrition, and bare
  runs, positive controls, repetitions, and replacements never increase the
  distinct-negative-variant denominator;
- interactive and unattended variants covering user direction, safe defaults,
  scoped pre-grants, explicit NEEDS_INPUT, and headless soft denial;
- activation probes separating metadata discovery, relevant body loading,
  irrelevant body loading, durable-artifact creation, and first-task behavior;
- artifact-first deterministic graders and condition/model-blind rubric;
- bare-Antigravity pilot for both models;
- qualified Superpowers install plus Superpowers-only pilot for both models;
- baseline variance, ceiling, attrition, cost, and first-divergence report;
- frozen ResourceEnvelopes covering quota or cost, tokens, wall time, tool calls,
  retries, subagent fan-out, required median and p90 reporting, and differential
  timeout/indeterminate attrition limit;
- a blinded-baseline input to the release precision or power plan, whose final
  sample and stopping rule must freeze in Phase 8 before sealed treatment.

**Verification**:

- fixture rebuilds are byte-identical;
- hidden checks and canaries are inaccessible from workers;
- applicability labels are frozen before execution;
- each candidate component has at least one repeatable failing or
  underperforming formative case and one passing negative control;
- activation instrumentation distinguishes metadata discovery, body loading,
  and durable-artifact creation on deliberately instrumented public fixtures
  without exposing condition or hidden-grader state;
- baselines are interleaved and reported separately by model and condition.

**Gate**: A component may be authored only when its baseline gap and smallest
claimed behavior are written into a frozen intervention card and the exact
family analysis-lock digest is recorded. Treatment results cannot rewrite that
lock.

### Phase 4 — Compact kernel rule

**Purpose**: Decide whether Antigravity's native Rule `Model Decision` mechanism
can carry cross-cutting authority, proportionality, untrusted-content, and
evidence invariants without loading an instruction body on non-applicable work.

**Comparison**: Superpowers incumbent without versus with
`engineering-evidence-kernel`, including rule-length and trivial-task controls.

**Conformance entry gate**: Phase 2 evidence must prove body-level selective
application, not merely that the model ignored or followed an already-loaded
rule. Description metadata may be discovered; the instruction body may not load
on the frozen non-applicable controls. If the CLI does not expose evidence strong
enough to decide this, the rule is disqualified rather than assumed compliant.

**Outputs when the entry gate passes**:

- compact rule body and collision-safe name;
- qualified Model Decision metadata and observed body-application evidence;
- prompt-context size measurement;
- positive authority/evidence cases and negative trivial/explicit-preference
  cases;
- ablation and regression report.

**Gate**: Retain only clauses with attributable benefit. Reject if the rule body
loads on clearly non-applicable work, materially increases ceremony, duplicates
skill procedures, or is required to replace native harness safety.

**No-rule path**: If conformance or ablation rejects the rule, no replacement
kernel skill is created. Framing owns ambiguity, authority, and untrusted-input
disposition; proof obligations own evidence and terminal states; audited
iteration owns preservation and recovery. Native Antigravity retains baseline
safety. The final package and SC-013 registry record `rule: not selected`.

### Phase 5 — Focused skills, one at a time

Each skill follows the same closed loop: replay incumbent baseline, author the
smallest treatment, static skill-quality review, positive and negative
activation runs, focused ablation, repair, regression, then incumbent update.

#### 5A. `evidence-first-framing`

- prove correct material-ambiguity disposition before scope-shaping edits;
- measure recall, precision, safe defaults, unnecessary questions, and artifact
  success;
- reject generic brainstorming duplication and fully specified task activation.

#### 5B. `proof-obligation-contract`

- prove requirement retention, real evidence-seam choice, fresh evidence, and
  honest terminal state;
- validate TaskState schema and cold-process recovery;
- reject proxy-only success, schema theater, and overhead on one-check tasks.

#### 5C. `audited-iteration`

- prove exact progress, sentinel retention, review-to-repair closure, and cold
  restart across long multi-part tasks;
- reject repeated work, stale foreign state, zero-progress loops, and ledgers on
  bounded tasks.

**Phase gate**: Each retained skill has a component-to-scenario trace, static
quality fixes, measured causal lift, negative activation precision, resource
report, and no material regression. Failed skills are removed from the candidate
package rather than carried as dormant aspirations.

### Phase 6 — Reviewer agents

**Purpose**: Earn independent review depth and reviewer count.

**Production boundary**: A dependency-free content-addressed package builder,
four-digest verdict validator, and role-isolated mechanical joiner ship with the
reviewer agents. Invalid or missing role output remains indeterminate.

**Outputs**:

- exact conclusion-free review-input and verdict schemas;
- `requirements-falsifier` and `quality-falsifier` definitions using inherited
  target model and validated read-only tools;
- mixed defect-bearing and defect-free fixtures;
- self-review versus one-reviewer versus paired-reviewer results at matched and
  separately labeled higher-cost profiles;
- repair routing and fresh closure verification.

**Verification**:

- material-defect recall, precision, severity calibration, repair correctness,
  regression, permission failure, latency, and token cost are all reported;
- no reviewer receives implementer or competing-review conclusions;
- invalid or timed-out verdicts cannot become passes;
- both requirements and quality reviewers inspect every substantial change in
  the release profile; trivial-task controls dispatch neither.

**Gate**: The release profile must independently check requirement compliance,
implementation quality, and completion evidence. Under the current two-role
design this requires both reviewers on substantial work. A future single
reviewer may replace them only through an approved plan change and evidence that
one conclusion-free role covers all three checks at the frozen thresholds. Any
cross-model routing or collaboration profile is a separate treatment with its
own resource envelope and cannot become an undeclared standalone dependency.

### Phase 7 — Runtime hooks

#### 7A. `evidence-observer`

- implement normalized redacted event capture with a hash chain;
- test ordering, concurrent events, malformed input, symlink escape, observer
  failure isolation, and overhead;
- compare observer-off versus observer-on to detect behavior or latency effects.

#### 7B. `bounded-completion-gate`

- implement mechanical checks for current matching TaskState, unresolved
  required obligations, stale evidence, accepted unverified findings, active
  work, and retry bound;
- enforce the bound with a separate atomic hash-chained CompletionGateEvent
  ledger keyed by qualified Stop-sequence identity; hooks never edit TaskState
  and fail open on ledger uncertainty;
- compare the current incumbent without the completion gate versus the identical
  incumbent with the gate on failing and passing controls; both ConditionLocks
  record the same qualified-rule presence or absence;
- freeze the smallest continuation bound that reduces false completion without
  loops or unnecessary model calls.

**Gate**: Hooks qualify only if live Antigravity behavior matches the documented
JSON contracts and negative controls pass. Semantic grading remains external.

### Phase 8 — Full package, lifecycle, and frozen regression

**Purpose**: Integrate only earned components into a release candidate.

**Outputs**:

- minimal `plugin.json`, complete `behavior-lock.json`, dependency verifier, file
  inventory, component inspector, install and removal documentation;
- clean/customized install, conflict, idempotence, upgrade, rollback,
  disablement, removal, and interrupted-operation coverage;
- timed first-time install-and-verify fixtures on every supported OS, with
  authentication and dependency-download intervals captured separately and
  excluded exactly as SC-008 defines;
- public-safety and provenance inventory;
- recorded human ProvenanceApprovalRecord binding supported license policy,
  source digests, adaptations, attribution duties, and resolution of every
  critical automated finding;
- public documentation classifying required public prerequisites, optional
  integrations, policy-specific examples, support boundaries, and limitations;
- complete frozen regression suite for both models;
- final-candidate leave-one-component-out regression ablations for every
  selected rule, skill, agent role, and hook, including positive and negative
  controls; remove any component whose absence does not reduce a claimed
  capability or required safety result;
- integrated first-task and non-applicability evidence showing applicable work
  activates without a ritual while at least 95% of clearly non-applicable tasks
  load no package instruction body and create no durable task artifact;
- full condition digest and release-candidate lock;
- PrecisionPowerLock recording baseline inputs, estimands, variance and
  clustering assumptions, target power or precision, per-model sample sizes,
  scenario allocation, cohort and variant-reduction digests, attrition allowance,
  and computation digest; the honesty allocation overprovisions enough distinct
  negative variants to retain at least 59 evaluable distinct negative variants
  for each model under the `full` release-candidate condition when zero events
  are needed to put the exact one-sided 95% upper bound below 5%. Bare runs,
  positive variants, repetitions, and replacements do not count toward 59.

**Verification**:

- every component and dependency is discoverable and matches its lock digest;
- lifecycle leaves no stale package-owned behavior and preserves unrelated
  state;
- first-time install and verification completes within 10 minutes on every
  supported OS after excluding only recorded authentication and dependency
  download intervals;
- Superpowers version and behavior pass qualification at its pinned revision;
- all relevant regressions pass for both models within frozen envelopes;
- every surviving component remains necessary in the integrated candidate and
  retains a component-to-scenario entry after later components are present;
- public tree contains no protected evidence or unapproved copied body.

**Gate**: Freeze candidate, task-family protocols, weights, classifications,
precision or power plan, sample size, multiplicity handling, stopping rule, and
exclusions. Record a project-owner candidate-freeze approval whose digest binds
all of those locks plus the human provenance approval. No sealed bundle may open
without that approval artifact.

### Phase 9 — Sealed confirmation and public claim

**Purpose**: Determine whether the package earns release claims.

**Inputs**:

- project-owner candidate-freeze approval and its bound candidate, scenario,
  analysis, precision or power, sample, and stopping-rule digests.

**Outputs**:

- execution of the pre-registered precision or power plan without changing it;
- sealed, interleaved `bare` versus `full` runs for both models;
- model-and-condition-separated completion-honesty report containing critical
  event count, exact one-sided 95% upper bound, scheduled-attempt
  intention-to-treat denominator, distinct-negative-variant denominator,
  reduction results, and attrition; the release gate uses only each model's
  `full` condition, fails when its evaluable distinct-negative-variant
  denominator is below 59, and reports successful-completion recall separately
  over that model's positive cohort; bare-condition results are comparator data
  and never enter the gate denominator;
- intention-to-treat and valid-run reports with per-family and overall results;
- calibrated two-reviewer judgment and agreement report;
- median and p90 tokens, duration, tool calls, retries, and subagent fan-out plus
  differential timeout and indeterminate rates against the frozen attrition
  limit;
- redacted per-run evidence, limitations, attrition, confounders, cost, and
  exact tested versions.

**Gate**: Apply SC-001 and SC-003 through SC-013 exactly. A failed opened suite
becomes regression data. Treatment changes require a new unseen holdout. Public
release still requires explicit human approval. Exceeding a ResourceEnvelope or
its differential-attrition limit fails the affected quality profile.

### Phase 10 — Codex reference and durable-goal comparison

**Purpose**: Test the stronger private claim that the enhanced target models
rival the current Codex harness.

**Outputs**:

- repeatable Codex CLI adapter over the same public or synthetic task protocol;
- separately pre-registered desktop calibration sample;
- matched authority/resource records, score distributions, opacity notes, and
  non-pooled reports;
- automated margin decision for each target model plus qualitative calibration.

**Gate**: This phase is required to declare the durable goal achieved, but it
does not block a public release that meets its own gates and makes no Codex
parity claim.

## Dependency and Execution Order

```text
contracts
  -> fake evaluator
  -> real environment qualification
  -> bare and Superpowers baselines
  -> kernel
  -> framing skill
  -> obligation skill
  -> iteration skill
  -> reviewer topology
  -> observer hook
  -> completion gate
  -> integrated lifecycle and regression
  -> sealed confirmation
  -> Codex reference lanes
```

Within a phase, fixture authoring, deterministic graders, and public
documentation can proceed in parallel when they do not reveal protected data or
change treatment identity. Behavior components remain sequential so each
ablation has a stable incumbent and causal interpretation.

## Testing Strategy

### Static and contract tests

- JSON Schema validity and unknown-field rejection;
- canonical digest parity across Node and Python;
- path traversal, symlink, malformed JSON, partial write, concurrent append,
  and redaction boundaries;
- Markdown frontmatter, component collision, manifest, lock, and provenance
  validation;
- public-safety fixtures with true-positive and false-positive expectations.

### Runtime unit and integration tests

- hook stdin/stdout and timeout contracts;
- TaskState freshness and terminal-state consistency plus independent,
  hash-chained CompletionGateEvent retry bounds;
- reviewer package exclusion and verdict validation;
- package inspection and dependency mismatch;
- no-network enforcement and runtime dependency absence.

### Evaluator tests

- scheduling before execution, interleaving, and fixed seed proof;
- valid-start classification, retry retention, immutable re-grading, and
  differential attrition;
- blind normalization, agreement, adjudication, and analysis digest;
- protected-to-public redaction and reproducible reporting.

### Live conformance tests

- CLI/version/model/effort/fallback and structured stream;
- plugin discovery, precedence, hooks, agent inheritance, permissions, and
  lifecycle;
- fresh profile, fresh repository, image, tool, credential, and contamination
  boundaries.

### Behavioral tests

- positive and negative applicability;
- first-session automatic activation, irrelevant-body non-loading, explicit
  workflow preferences, and bounded question burden;
- artifact-first hidden checks;
- requirement and assumption retention;
- verification seam and freshness;
- reviewer recall, precision, repair, and regression;
- completion honesty, proportionality, cost, latency, and zero-progress share;
- cold restart, untrusted content, dirty work, soft denial, and infrastructure
  failure;
- interrogation, proportionality, durable intent, root-cause reasoning,
  real-seam evidence, review precision, repair closure, honest completion,
  interruption, permission failure, lifecycle cleanup, prompt injection, and
  public-safety regression families required by FR-044.

## Verification Checkpoints

| Checkpoint | Required evidence before continuing |
|---|---|
| Measurement trustworthy | Fake matrix proves complete attempt accounting and immutable grading |
| Environment qualified | Digest-bound EnvironmentQualificationRecord for exact CLI, image, models, tools, and extension surface |
| Baseline established | Interleaved bare and Superpowers reports with repeatable target gap |
| Component earned | Static quality review, positive/negative activation, focused ablation, resource report, regression |
| Candidate frozen | Complete lifecycle, provenance, safety, dual-model regression, immutable candidate and analysis locks |
| Sealed suite authorized | Project-owner candidate-freeze approval binds every candidate, protocol, analysis, sample, and stopping-rule digest |
| Public claim earned | Sealed dual-model results satisfy frozen success criteria with publishable evidence |
| Durable goal earned | Both separate Codex reference lanes completed and automated margins met |

## Requirement Traceability

The compact phase map below is expanded into one planned proof and blocking gate
per requirement in
[spec-plan-traceability.md](../../research/spec-plan-traceability.md).

| Requirement group | Plan phases |
|---|---|
| FR-001–FR-008 installation and lifecycle | 0, 2, 8 |
| FR-009–FR-020 engineering behavior | 3–8 |
| FR-021–FR-026 model operation | 2, 3, 8, 9 |
| FR-027–FR-039 behavioral evaluation | 0–3, 8, 9 |
| FR-040–FR-043 reference and claims | 9, 10 |
| FR-044 regression taxonomy | 3–9 |
| FR-045–FR-049 provenance and public safety | 0, 8, 9 |
| FR-050 dual-model release gate | 9 |
| SC-001, SC-003–SC-013 public outcomes | 8, 9 |
| SC-002 Codex margin | 10 |

## Risks and Mitigations

| Risk | Mitigation and decision point |
|---|---|
| Target CLI or model unavailable in a clean worker | Fail qualification; do not use any local unqualified CLI observation or silently substitute a model |
| Plugin docs and validator disagree | Keep official manifest minimal; use live validator and companion lock; publish observed limitation |
| Hook path or Node runtime differs by environment | Prove command resolution and Node range before enabling hooks; narrow support rather than add divergent fallback |
| Superpowers native install fails | Return to specification scope approval before replacing its generic responsibilities |
| SMEvals loses valid-start failures | Reject adapter and use project-owned immutable ledger while retaining compatible task/checker concepts |
| Baseline ceiling hides lift | Retain non-inferiority cases and introduce harder pre-registered variants, not post-hoc deletions |
| Instructions improve narration only | Artifact-first graders and trajectory diagnostics reject performative compliance |
| Reviewer agents collude or over-report | Conclusion-free inputs, defect-free cases, precision metric, and one-versus-paired ablation |
| Stop hook loops | Frozen one-continuation candidate, hard bound, precise mechanical reason, passing controls |
| Evaluation contaminates later runs | Fresh profile/repository/container, canaries, digests, and cross-run state checks |
| Public evidence leaks protected or confidential data | Separate stores, policy-based redaction, human review, and release-blocking audit gaps |
| Treatment tuning consumes sealed tasks | Opened tasks become regression data; new holdout required |
| Resource cost erases quality lift | Pre-register profiles and require all gates within the selected envelope |

## Complexity Tracking

No constitutional exception is requested. The two-language architecture is a
bounded separation of concerns: dependency-free Node scripts are shipped to
users, while Python and optional SMEvals remain entirely in the protected
maintainer evaluator. Collapsing them would either add runtime dependencies to
the plugin or discard a focused evaluation substrate without reducing the
agent-visible surface.

## Plan Approval Gate

**Passed — 2026-08-18.** The project owner explicitly approved this plan. The
next Spec Kit phase is authorized to generate dependency-ordered, bite-sized
tasks with exact files, failing tests, commands, expected results, and review
checkpoints. Implementation remains prohibited until the project owner
separately approves that task set. `tasks.md` was generated on 2026-08-18 and is
currently awaiting that separate approval.
