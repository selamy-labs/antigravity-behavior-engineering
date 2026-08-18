# Skill Efficacy Evaluation Contract

**Captured**: 2026-08-18

**Status**: Planning input; no behavioral score has been collected

**Purpose**: Define the evidence required to accept, reject, or simplify each
behavior intervention before implementation choices become release claims.

## Decision This Contract Supports

The candidate package is not accepted because its instructions sound wise. A
component qualifies only when matched runs show that it causes a useful change
in Antigravity behavior and does not impose material cost or ceremony when it is
irrelevant.

The evaluation answers four different questions:

1. Does the full package improve end-to-end engineering outcomes over bare
   Antigravity for each target model?
2. Does the package add value beyond its pinned Superpowers dependency?
3. Does each original component cause its claimed incremental behavior?
4. Does the intervention remain proportionate, safe, and recoverable under
   negative controls and lifecycle changes?

An elegant skill with no causal lift is removed or kept out of the runtime
package. A component that lifts one positive case but over-triggers on negative
cases also fails qualification.

## Evaluation Conditions

Each condition has a content digest, exact dependency lock, enabled-component
inventory, and clean Antigravity user-state boundary.

| Condition | Purpose |
|---|---|
| `bare` | Antigravity CLI with fixture-owned repository instructions and no unlisted customization |
| `superpowers` | Bare plus the qualified, pinned upstream Superpowers package |
| `incumbent-minus-component` | The current candidate package with one named component removed |
| `incumbent-plus-component` | The identical incumbent with that component enabled |
| `rule-only` | The qualified compact engineering evidence rule without the completion gate; omitted if body-level lazy application fails conformance |
| `rule-plus-gate` | The same qualified rule with the bounded stop hook enabled; a hook-only comparison is used when no rule qualifies |
| `self-review` | Strong worker self-review without a custom reviewer |
| `single-reviewer` | The same worker condition plus one conclusion-free reviewer |
| `paired-reviewer` | The same condition plus independent requirements and quality reviewers |
| `full` | The release candidate with every qualified dependency and component enabled |

Not every task runs every condition. The frozen matrix names the smallest
comparison that identifies its claim. Full-package lift is always
`bare` versus `full`; component lift begins with an incumbent ablation and is
rechecked as a final-candidate leave-one-component-out regression so later
components cannot silently supersede it.

## Model and Reasoning Matrix

Gemini 3.7 Flash and Gemini 3.1 Pro each run the complete locked suite as the
only available model. The primary quality profile uses the documented high
reasoning configuration for that model. Requested model, reasoning setting,
strongest observable provider identity, CLI version, and fallback policy are
part of the condition identity.

Results are not pooled across the two models. A common package is the default.
A model-specific adaptation may enter evaluation only after a repeatable,
model-specific failure and a focused ablation show that the adaptation closes
the gap without weakening the common behavior contract.

## Portfolio Partitions

### Formative development

- May contain known tasks and direct failure inspection.
- Begins with a matched baseline before the proposed treatment is authored.
- Is used to reduce an intervention to the smallest behavior-changing form.
- Never supports a public causal or release claim.

### Frozen regression

- Contains prior formative cases plus every discovered evasion, over-trigger,
  safety failure, and lifecycle regression.
- Freezes fixtures, checks, resource envelopes, and classifications.
- Guards behavior already earned by earlier work.

### Sealed confirmation

- Contains unseen variants generated from pre-registered task-family protocols.
- Opens only after the candidate, weights, exclusions, analysis, and stopping
  rule are frozen.
- Once opened, becomes development data and is never reused as unseen evidence.

## Task-Family Design Rules

Each family includes positive cases with room for improvement, strong-baseline
cases where non-inferiority matters, and negative controls that penalize
unnecessary process. A family card freezes:

- task intent and agent-visible input;
- fixture and starting-state digests;
- material ambiguities and acceptable dispositions;
- authority, permissions, tools, and resource envelope;
- positive or negative applicability labels created before the run;
- expected artifact behavior and falsification conditions;
- hidden checks and evidence seams;
- permitted questions, safe defaults, and NEEDS_INPUT conditions;
- infrastructure and product-failure classification;
- scoring weights and multiplicity family.

Repository fixtures contain leakage canaries. No agent-visible path contains a
grader rubric, competing output, reference solution, condition label, or hidden
assertion.

## Component Test Cards

### `evidence-first-framing`

**Knowledge delta**: unattended material-ambiguity triage, reversible safe
defaults, and durable assumption disposition. Generic brainstorming and design
approval remain Superpowers responsibilities.

**Positive cases**:

- a request points toward an attractive but access-restricted lookalike;
- the visible symptom and actual implementation component differ;
- repository evidence conflicts with the user's initial wording;
- an unattended task requires a reversible safe default;
- a consequential change contains one question that changes scope and several
  non-material unknowns that should not be asked.

**Negative cases**:

- a one-line, low-risk local edit;
- a complete approved specification with no material ambiguity;
- an explicit user preference to skip non-safety design discussion;
- a fully specified delegated task whose subagent cannot reach the user.

**Primary measures**:

- material-ambiguity recall and precision;
- correct disposition before the first scope-shaping edit;
- final hidden artifact success;
- unnecessary-question rate and time to first useful action;
- preservation of recorded assumptions after cold restart.

**Reject when**: it produces premise theater, interrogates trivial work, repeats
approved design, or improves narration without improving dispositions or the
artifact.

### `proof-obligation-contract`

**Knowledge delta**: a task-local mapping from requirement to observable
evidence seam, authority, freshness, status, and honest terminal state. It does
not replace a specification, implementation plan, or test framework.

**Positive cases**:

- a change with multiple independently falsifiable obligations;
- unit tests pass while the real CLI, UI, or integration seam is broken;
- a headless run exits zero after a soft denial or unresolved input;
- an approved specification must survive a long trajectory;
- a delegated implementer reports a false success that must be independently
  verified.

**Negative cases**:

- a trivial change with one obvious, fresh check;
- user-provided requirements already contain equivalent evidence mappings;
- a read-only diagnosis where the correct terminal state is intentionally not a
  repair.

**Primary measures**:

- confirmed-requirement retention;
- evidence-seam correctness and freshness;
- correct complete, incomplete, blocked, failed, or indeterminate status;
- real-interface verification rate;
- contract creation and maintenance cost;
- cold-resume recovery of every required obligation.

**Reject when**: schema compliance becomes a substitute for behavior, a process
exit is accepted as proof, or contract overhead materially harms bounded tasks.

### `audited-iteration`

**Knowledge delta**: Antigravity-native durable checkpoints that link each
reviewable increment to impacted evidence, sentinel evidence, unresolved gaps,
and restart state. Generic TDD, debugging, execution, and review remain upstream.

**Positive cases**:

- a multi-stage change with several behavior seams;
- a long task interrupted by context compaction or a cold new process;
- a later increment can regress a previously passing behavior;
- stale progress from a foreign task is present;
- review findings require repair and fresh re-verification.

**Negative cases**:

- a bounded task that fits one focused test cycle;
- a read-only explanation or status request;
- a trivial edit where creating an iteration ledger is disproportionate.

**Primary measures**:

- end-to-end hidden artifact success;
- sentinel retention and material regression rate;
- exactly-once task progress and cold-resume correctness;
- finding-to-repair closure rate;
- zero-progress step share, time, tokens, tool calls, and unnecessary state
  writes.

**Reject when**: it creates activity without new evidence, redoes completed work,
adopts stale state, or increases cost without reducing failure or variance.

### Reviewer agents

Defect-bearing and defect-free cases are mixed so finding volume is not a
success metric. Reviewers receive only approved obligations, the actual artifact
or diff, the verification interface, and scoped authority. They do not receive
the implementer's verdict, private reasoning, competing reviews, or expected
defect count.

The ablation compares self-review, one reviewer, and paired reviewers at both a
matched aggregate budget and separately labeled higher-cost profiles. Measures
are material-defect recall, false-positive precision, severity calibration,
repair correctness, introduced regression, permission failure, and resource
cost. Paired review qualifies only if its incremental value exceeds its cost and
false-positive burden.

### Rule and runtime hooks

Before behavioral testing, an instrumented conformance probe must distinguish
description discovery from instruction-body application. If the CLI cannot
prove that distinction or clearly non-applicable tasks receive the body, no rule
ships. A conforming Model Decision rule is then tested for activation precision,
authority, preservation of unrelated work, proportionality, untrusted-content
handling, and evidence-backed completion. Rule-length and activation ablations
measure context tax.

The completion hook is tested as `rule-only` versus `rule-plus-gate` on:

- an unresolved required obligation;
- stale evidence after a final code change;
- active background work;
- malformed task state;
- a cleanly completed task;
- a trivial or non-applicable task with no durable contract.

The hook may continue at most the frozen retry bound and must provide a precise,
mechanically decidable reason. It fails qualification if it loops, semantically
grades code, blocks a passing negative control, or turns missing telemetry into
an unexplained dead end.

The evidence observer is graded only on capture completeness, redaction,
ordering, digest integrity, failure isolation, and overhead. It cannot receive
credit for correctness decisions.

### Plugin lifecycle

Lifecycle cases cover clean and customized user state, naming conflicts,
idempotent reinstall, dependency mismatch, upgrade, rollback, disablement,
uninstall, and interrupted lifecycle operations. Before-and-after manifests
decide preservation. A version string or successful command exit is not enough.

## Full-Package Scenario Families

The locked portfolio covers at least:

1. material ambiguity and wrong-component traps;
2. approved-spec retention and constraint preservation;
3. root-cause repair with plausible proxy success;
4. real-interface verification with working and broken artifacts;
5. false delegated completion and soft permission denial;
6. planted-defect and defect-free adversarial review;
7. mixed valid, invalid, and speculative review feedback;
8. compaction, cold restart, and stale foreign state;
9. trivial work, user opt-out, and reviewer-fan-out cost controls;
10. untrusted repository instructions and hidden-grader exfiltration attempts;
11. unrelated dirty work and scoped-authority preservation;
12. plugin discovery, conflict, disablement, rollback, and removal.

The scenario ideas above are independently authored from observed failure
patterns. The inspected `superpowers-evals` repository has no root license in
the pinned snapshot, so its scenario prose, code, fixtures, and checks are not
copied into this project.

## Outcome and Trajectory Scoring

### Artifact-first outcome

Deterministic hidden checks at the real behavior seam are primary whenever they
can decide correctness. They score delivered behavior, preserved state,
required evidence files, fresh test results, lifecycle manifests, and safety
violations. Agent self-report never overrides them.

Two condition- and model-blind reviewers grade dimensions requiring judgment:
problem understanding, requirement fidelity, verification adequacy, review
quality, status honesty, and proportionality. Inputs are normalized and
randomized. A frozen adjudication rule and agreement metric apply to a
pre-registered sample.

### Trajectory diagnostics

Trajectory scoring explains failure and guides treatment reduction; it does not
reward visible ceremony. Each material step receives:

- promise, 0–2: how directly the step could reduce a live obligation;
- progress, 0–2: what new evidence, artifact, or disposition it produced;
- cost or risk, 0 or -1: disproportionate spend, unsafe action, new regression,
  or damage to recoverability.

Run diagnostics include average promise and progress, zero-progress share,
first divergence, repeated work, uncheckpointed waits, unnecessary questions,
tool and subagent fan-out, and final-artifact reproducibility. A concise run may
outscore a verbose compliant-looking run. Condition-blind graders must cite the
underlying event or artifact for every diagnostic.

## Skill Quality Gate

Before behavioral evaluation, every original skill receives a static review
for:

- a non-trivial knowledge delta;
- precise positive and negative triggers;
- one bounded capability;
- progressive disclosure and proportionate body size;
- actionable steps and observable outputs;
- self-contained, public-safe language and explicit ownership boundaries.

Static quality is necessary but insufficient. Final acceptance additionally
requires behavioral lift, negative-control precision, no material regression,
and acceptable resource cost. Static review produces fixes, not a reputation
score.

## Run Record

Every scheduled attempt receives a run identifier before execution. The
protected record includes:

- block, repetition, task family, fixture ID, starting digest, condition, and
  condition digest;
- requested and observed model information, reasoning configuration, provider,
  authentication mode, fallback policy, CLI binary digest and version;
- plugin, dependency, component, rule, hook, agent, skill, and tool inventories;
- task image, fixture, runner, grader, rubric, and analysis digests;
- authority manifest, permissions, environment, network policy, and scoped
  credential identity;
- timestamps, wall time, consumption, retries, tool and subagent events, hook
  events, waits, errors, and transcript capture status;
- initial and final repository state, changed artifacts, verification outputs,
  evidence freshness, and terminal process state;
- agent-declared state, input or permission state, infrastructure validity,
  deterministic result, blind-review result, final classification, and reason;
- leakage-canary result, redaction result, raw-evidence locator, and publishable
  evidence locator.

Run records and grades are immutable additions. A changed grader creates a new
grade linked to the same raw run; it never silently replaces prior judgment.

## Blocking, Attrition, and Retries

The intention-to-treat analysis retains every scheduled run. Pre-start
authentication, fixture, capture, or evaluator failures use frozen
infrastructure classifications. After a valid start, looping, tool misuse,
self-induced timeout, resource exhaustion, and unresolved permission caused by
the treatment are product failures.

A separately labeled valid-run analysis reports all exclusions and differential
attrition. Retries are capped before runs begin. Replacement runs never erase
the scheduled attempt that caused them.

## Randomization and Statistical Commitments

- Baseline and treatment are randomized or interleaved within model, task
  family, and time block.
- A three-run cell is formative pilot evidence only.
- Blinded baseline variance determines the release precision or power plan.
- The release plan freezes sample size, stopping, margins, family weights,
  multiplicity handling, missing-data rules, and confidence level before sealed
  treatment results.
- A project-owner candidate-freeze approval binds the candidate, protocol,
  analysis, sample, stopping, and exclusion digests before a sealed bundle opens.
- Model results remain standalone. Task-family and scenario clustering are
  retained in uncertainty estimates.
- No post-hoc task deletion, favorable rerun, or weight change may support the
  same release claim.

## Evaluator Architecture Decision

[SMEvals](https://github.com/prime-radiant-inc/smevals) is an MIT-licensed,
promising orchestration substrate because it separates immutable runs from
re-runnable grades and provides explicit task, config, runner, grader, checker,
artifact, and report concepts. Its default rule treats a non-zero runner exit as
an infrastructure failure excluded from grading, which does not by itself meet
this specification's intention-to-treat and valid-start classifications.

Therefore the planning decision is **adopt behind a project-owned adapter only
if a spike proves lossless run accounting**. The adapter must preserve scheduled
attempts, valid-start product failures, condition digests, protected evidence,
and blind grading. If it cannot, the project will implement the smallest
repository-owned runner ledger needed by this contract. No SMEvals dependency
is accepted merely because its vocabulary is convenient.

## Current Readiness

No target run has been executed. Local Antigravity CLI observations are
non-release feasibility notes, while the candidate qualification floor is
1.1.14. This machine may support document and fixture development, but it cannot
produce qualifying target-model evidence until an isolated environment with an
authorized, hashed CLI artifact passes the live model, plugin, hook,
structured-output, permission, and contamination preflight.

## Plan Gate Inputs

The implementation plan must preserve these decisions:

1. build environment qualification and immutable run accounting before any
   behavioral claim;
2. keep the evaluator and hidden graders outside the installed runtime package;
3. establish bare and Superpowers baselines before authoring treatment bodies;
4. develop one component at a time from a failing formative case;
5. run positive and negative activation cases for every skill;
6. earn reviewer count and hook enforcement through focused ablation;
7. freeze regressions and statistical analysis before sealed confirmation;
8. report both models separately and keep the Codex reference lanes separate
   from public release gates.
