# Feature Specification: Improve Antigravity Engineering Behavior

**Feature Branch**: 001-improve-antigravity-behavior

**Created**: 2026-08-18

**Status**: Approved — 2026-08-18

**Input**: Create a public, installable Antigravity behavior-engineering package
that makes Gemini 3.7 Flash and Gemini 3.1 Pro substantially better at deep
problem understanding, iterative implementation, verification, and adversarial
review. Use Antigravity's full customization surface when evidence justifies it,
compose rather than republish public skill libraries, and prove behavioral lift
through controlled evaluation in isolated task environments.

**Plain-language promise**: A user installs one public package and gets an
Antigravity agent that asks the questions that matter, keeps its work aligned
with the request, makes changes in reviewable steps, tests the real result,
looks for its own mistakes, and reports honestly. It should do this with either
permitted Gemini model without turning small jobs into ceremonies.

The package earns an improvement claim only through repeated, controlled tests
against Antigravity without the package. A public release must work for both
Gemini models, install and uninstall cleanly, preserve user work, and carry safe
licensing and provenance. The stronger claim that the result rivals Codex also
requires the separate private Codex comparisons defined below.

## Scope

### In Scope

- Engineering tasks in unfamiliar existing repositories, especially requests
  whose requirements, constraints, or affected components are initially
  ambiguous.
- Automatic behavior improvement from the first applicable task after a clean
  installation, without a per-session activation ritual.
- Investigation, intent confirmation, specification, planning, incremental
  implementation, verification, adversarial review, repair, and evidence-backed
  completion.
- Standalone operation with Gemini 3.7 Flash and Gemini 3.1 Pro, plus optional
  collaboration retained only when evaluation supports it.
- Skills, rules, hooks, custom agents, scripts, and plugin packaging when each
  selected extension surface has a distinct, measured responsibility.
- Antigravity CLI as the sole release-gating product surface for version one.
- Desktop/IDE compatibility experiments and SDK evaluation adapters that make no
  version-one product compatibility claim.
- Bare-versus-enhanced evaluation, focused module ablations, reference-agent
  comparison, and publication of evidence and limitations.
- Clean install, coexistence, upgrade, rollback, disablement, and removal.
- Public-safe composition of upstream methods and the project owner's existing
  public skill library.

### Out of Scope

- Training, fine-tuning, or modifying the underlying models.
- Republishing third-party skill bodies merely for installation convenience.
- Google-confidential examples, internal identifiers, private infrastructure,
  or organization-specific operating instructions.
- General-purpose personal assistance unrelated to software engineering.
- Claims that remote model inference is deterministic or fully hermetic.
- Model roles inferred only from the Flash or Pro label.
- Version-one desktop/IDE or SDK product compatibility claims.
- Treating Antigravity product or extension surfaces as equivalent without
  separate evidence.
- Imposing this package-development lifecycle on every end-user task.

## Clarifications

### Session 2026-08-18

- Q: Which Antigravity product surfaces must pass release gates in version one?
  → A: Antigravity CLI only; desktop/IDE compatibility is experimental, and SDK
  use is evaluation-only.
- Q: How should version one compose upstream behavior libraries?
  → A: Use a hybrid of verified upstream-native Antigravity packages and
  independently authored Antigravity-native modules; do not republish upstream
  skill bodies.
- Q: Should the current Codex harness be the reference agent, and how binding
  should that comparison be?
  → A: Use Codex as a private goal-completion reference, with a repeatable CLI
  lane and a separately reported desktop calibration lane. This comparison is
  required to declare the durable goal achieved but is not a public-release
  gate.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Complete an Ambiguous Change with Evidence (Priority: P1)

As an engineer, I install the package and give Antigravity a consequential but
underspecified change in an unfamiliar repository. The agent discovers the real
problem, aligns with my intent, implements the smallest adequate change,
verifies observable behavior, and adversarially reviews the result before
claiming completion.

**Why this priority**: This is the central value proposition. A package that
cannot improve a realistic end-to-end engineering task has not meaningfully
improved the harness.

**Independent Test**: Run a prepared repository task containing ambiguous
requirements, an attractive wrong implementation target, and hidden behavioral
checks. The final artifact must satisfy the checks, and the evidence must show
proportionate investigation, scoped implementation, verification, and a review
that meets the independence definition.

**Acceptance Scenarios**:

1. **Given** an ambiguous request and unfamiliar repository, **When** the
   enhanced agent begins, **Then** it investigates relevant code and constraints
   before a scope-shaping edit and correctly resolves or bounds each pre-labeled
   material ambiguity.
2. **Given** confirmed intent and a substantial change, **When** implementation
   begins, **Then** reviewable intent, acceptance criteria, current progress,
   and verification obligations remain available throughout the task.
3. **Given** an implementation that passes obvious checks but contains a planted
   material defect, **When** independent adversarial review runs, **Then** the
   defect is found and correctly repaired, fresh hidden checks pass, and no
   material regression is introduced.
4. **Given** a completed change, **When** the agent reports its outcome, **Then**
   it cites inspected artifacts and fresh verification evidence and correctly
   identifies incomplete, blocked, failed, or indeterminate obligations.
5. **Given** a trivial edit, **When** the enhanced agent handles it, **Then** it
   avoids unnecessary planning, questioning, and reviewer fan-out.
6. **Given** repository text or tool output that instructs the agent to bypass
   verification, reveal hidden material, or exceed its authority, **When** the
   agent encounters it, **Then** it treats the content as untrusted and follows
   higher-authority constraints.

---

### User Story 2 - Prove the Package Caused Behavioral Lift (Priority: P1)

As a maintainer, I can compare bare Antigravity with the candidate package under
matched conditions and obtain a scorecard that distinguishes product behavior
from model variance, evaluator failure, environment failure, and development on
known examples.

**Why this priority**: The package is an unproven instruction collection until
its effect on real behavior is measured. Evaluation is part of the product.

**Independent Test**: Run a pre-registered, sealed confirmation suite in both
conditions for each model. Use matched authority and resources, clean state,
hidden deterministic checks, blinded adversarial grading, and frozen analysis.
Generate a report that links claims to protected raw evidence and redacted
publishable evidence.

**Acceptance Scenarios**:

1. **Given** a scheduled evaluation block, **When** baseline and treatment runs
   start, **Then** they use equivalent inputs, authority, resource envelopes,
   tools, and task environments in randomized or interleaved order.
2. **Given** a candidate tuned on formative scenarios, **When** release evidence
   is collected, **Then** the candidate, task-family protocol, scenario weights,
   exclusions, stopping rule, and analysis are frozen before sealed tasks open.
3. **Given** every scheduled run, **When** results are aggregated, **Then** the
   intention-to-treat report retains the run and its outcome, while a separately
   labeled valid-run analysis exposes uncertainty and exclusions.
4. **Given** a pre-start authentication or evaluator failure, **When** grading
   occurs, **Then** it is classified by a frozen rule; valid-start looping,
   self-induced timeout, and budget exhaustion remain product failures.
5. **Given** a capability claim, **When** a reader inspects the report, **Then**
   tested configurations, task and environment digests, evidence, scoring,
   attrition, confounders, and limitations are discoverable.
6. **Given** a claim that one module caused an improvement, **When** evidence is
   reviewed, **Then** a package-without-module versus package-with-module
   ablation supports it separately from bare-versus-full package lift.

---

### User Story 3 - Work with Either Permitted Model (Priority: P1)

As an engineer, I can select Gemini 3.7 Flash or Gemini 3.1 Pro and receive the
complete workflow without requiring the other model. Optional collaboration
improves a measured outcome within a declared resource profile.

**Why this priority**: Access policy may permit only one model at a time. Both
are capable engineering agents and must be measured rather than stereotyped.

**Independent Test**: Run the entire locked confirmation suite with each model
as the only available model. Verify requested and observed configuration,
standalone workflow coverage, and no fallback. Evaluate collaboration as a
separate, budgeted treatment.

**Acceptance Scenarios**:

1. **Given** only Gemini 3.7 Flash is available, **When** the package executes
   the suite, **Then** all required investigation, implementation, verification,
   and independent-review behaviors remain available.
2. **Given** only Gemini 3.1 Pro is available, **When** the package executes the
   suite, **Then** all required behaviors remain available.
3. **Given** an unavailable or misspelled model, **When** a run starts, **Then**
   it fails before treatment rather than silently falling back or entering the
   analysis under a false identity.
4. **Given** immutable served model identity is not exposed, **When** evidence is
   published, **Then** it records the request and strongest observable provider
   metadata and discloses the limit.
5. **Given** optional collaboration, **When** it is evaluated, **Then** quality
   and resource use are reported separately under the same aggregate budget or
   labeled as a more-expensive profile.

---

### User Story 4 - Install, Coexist, and Leave Cleanly (Priority: P1)

As an Antigravity CLI user with existing customizations, I can install, inspect,
upgrade, disable, roll back, and remove the package without corrupting or
silently overriding unrelated behavior.

**Why this priority**: A behavior package touches instruction and automation
surfaces that can conflict with user state. Safe lifecycle behavior is part of
being useful to the public.

**Independent Test**: Exercise the lifecycle on clean and customized CLI
fixtures. Compare before-and-after state and verify discovery paths, precedence,
conflicts, version identity, idempotence, rollback, and removal.

**Acceptance Scenarios**:

1. **Given** a clean supported CLI environment, **When** installation completes,
   **Then** a deterministic probe identifies the package version, enabled
   modules, dependency versions, and discovered component paths.
2. **Given** global or workspace customizations, **When** installation detects a
   naming or precedence conflict, **Then** it reports the conflict and requires a
   documented resolution rather than silently overwriting.
3. **Given** an installed version, **When** the same installation runs again,
   **Then** it is idempotent and preserves unrelated state.
4. **Given** an upgrade or rollback, **When** activation is verified, **Then** no
   stale component or mismatched dependency remains active.
5. **Given** disablement or removal, **When** state is compared with the captured
   pre-install manifest, **Then** package-owned changes are absent and unrelated
   changes are preserved.

---

### User Story 5 - Evolve and Publish Safely (Priority: P2)

As a maintainer, I add or refine behavior only after observing a current gap,
verify that the smallest change fixes it, run regressions and sealed
confirmation, and release a public-safe package with clear attribution.

**Why this priority**: Durable capability requires a repeatable improvement
loop. Unmeasured additions create bloat, regressions, and false confidence.

**Independent Test**: Introduce a candidate behavior through formative failure,
focused treatment, ablation, frozen regression, sealed confirmation,
public-safety, attribution, and lifecycle checks. An untested, unsafe, or
unattributed change cannot qualify for release.

**Acceptance Scenarios**:

1. **Given** a proposed change, **When** no failing or underperforming formative
   scenario exists, **Then** it is not accepted as a new capability.
2. **Given** a treatment that fixes its focus but regresses supported behavior,
   **When** regressions run, **Then** release is blocked until resolved or a new
   pre-treatment scope is approved.
3. **Given** a release candidate, **When** safety and provenance review runs,
   **Then** confidential content, unapproved copied material, unpinned
   dependencies, and unresolved license obligations block release.
4. **Given** a failed sealed confirmation, **When** maintainers revise the
   treatment, **Then** the opened scenario becomes development data and a new
   unseen holdout is required for the next release claim.

### Edge Cases

- The user supplies a complete approved specification and needs no interview.
- The user requests a fast limited operation or opts out of a non-safety step.
- A repository contains unrelated uncommitted changes.
- Obvious checks pass while externally observable behavior fails.
- Reviewers disagree, share an assumption, or approve without inspecting the
  actual artifact and verification interface.
- A task is interrupted; a new process must recover without conversation memory.
- A model loops, thrashes, overuses tools, or exhausts a valid-start budget.
- Headless execution soft-denies permission or awaits input while exiting zero.
- A plan or material clarification awaits approval and no response is available.
- A hook is missing, times out, emits malformed data, or uses the wrong failure
  policy.
- A tool or model service is unavailable, rate-limited, or changes configuration.
- A subagent hangs, uses an invalid tool, inherits the wrong model, or bubbles a
  permission request.
- Transcript capture is truncated or redaction destroys required audit data.
- A hidden grader, reference solution, or competing run becomes agent-visible.
- Repository files, issues, logs, or tool output contain prompt injection.
- Global and workspace customizations collide or stale cached state remains.
- Prior conversations, permissions, or outputs contaminate a later run.
- An upstream dependency changes behavior, path, interface, or licensing.
- The reference adapter fails or cannot match authority and resources.
- Baseline performance has no headroom on a task family.
- A task or transcript contains potentially confidential data.
- An action would modify external state or be irreversible without authority.

## Requirements *(mandatory)*

### Normative Definitions

- **Applicable task**: Frozen fixture metadata identifies at least one behavior
  module as relevant before any run begins.
- **Trivial task**: A pre-labeled, low-risk change with one local behavior seam,
  no material ambiguity, and no expected cross-component effect.
- **Substantial task**: A task with a material ambiguity, cross-component effect,
  external-state risk, or multiple independent acceptance obligations.
- **Material ambiguity**: Missing information for which plausible answers change
  scope, safety, visible behavior, or acceptance checks.
- **Safe default**: A reversible, bounded choice that preserves user data and
  authority and cannot materially weaken acceptance.
- **Independent review**: A fresh execution context receives only the approved
  requirements, actual diff or artifact, verification interface, and authority,
  not the implementer's conclusion or private scratch reasoning.
- **Fresh evidence**: Evidence produced after the final relevant change from the
  actual artifact or behavior seam.
- **Complete workflow**: Investigation, bounded intent, implementation,
  verification, independent review when substantial, repair, and honest status.
- **Material regression**: A new critical failure or a pre-registered decline
  beyond the allowed margin in a supported behavior or safety family.
- **Representative suite**: A frozen, weighted set of independent task families
  covering the capability and failure taxonomy without post-hoc removal.
- **Valid start**: Authentication, fixture provisioning, model preflight, and
  evidence capture succeed before the agent receives the task.
- **Indeterminate run**: A pre-registered infrastructure condition makes outcome
  attribution impossible; it is not agent failure after a valid start.
- **Bare condition**: A fresh user and application-state boundary with pinned
  settings, no unlisted extensions or prior conversation state, fixture-owned
  repository instructions only, and a starting-state digest.

### Functional Requirements

#### Installation and Lifecycle

- **FR-001**: Version one MUST treat Antigravity CLI as the sole release-gating
  product surface. Desktop/IDE MUST be labeled experimental, and SDK use MUST be
  labeled evaluation-only.
- **FR-002**: The release MUST publish its minimum CLI version, tested operating
  systems, versioned package manifest, one documented installation flow, and a
  deterministic discovery-path conformance probe.
- **FR-003**: Version one MUST use hybrid composition. Public libraries with a
  verified native Antigravity package MUST remain pinned upstream dependencies
  that the installation flow resolves or verifies from their own source.
  Methodologies without a conforming native package MUST inform independently
  authored Antigravity-native modules rather than copied skill bodies. Missing,
  incompatible, or unverifiable required dependencies MUST fail visibly.
- **FR-004**: The installed package MUST affect the first applicable task in a
  new session without requiring an activation phrase.
- **FR-005**: Fixture metadata MUST define applicability independently of agent
  behavior. Evaluation MUST measure outcomes and use separate trace probes for
  discovery or irrelevant instruction-body access.
- **FR-006**: Users MUST be able to inspect package version, enabled modules,
  component paths, precedence, and upstream versions.
- **FR-007**: Installation MUST be idempotent, preserve unrelated state, and
  report naming or precedence conflicts before changing conflicting state.
- **FR-008**: Upgrade, rollback, disablement, and removal MUST cover every path
  touched by the package and leave no stale package-owned behavior.

#### Engineering Behavior

- **FR-009**: The agent MUST apply a proportionate workflow using the normative
  trivial and substantial task definitions.
- **FR-010**: Before a scope-shaping edit on a substantial task, the agent MUST
  inspect relevant context and correctly dispose of each material ambiguity
  using user direction or a recorded safe default.
- **FR-011**: Interactive and unattended operation MUST support user direction,
  scoped pre-granted permissions, and an explicit NEEDS_INPUT outcome. Process
  exit status alone MUST NOT count as success.
- **FR-012**: Substantial work MUST maintain reviewable intent, acceptance
  criteria, current progress, and verification obligations before implementation.
- **FR-013**: Requirements, decisions, progress, and unresolved findings MUST be
  recoverable by a cold new process using only versioned task artifacts and
  approved repository state.
- **FR-014**: Implementation MUST expose reviewable checkpoints, run focused
  verification at the relevant behavior seam, and preserve safe recovery from a
  failed checkpoint without requiring a prescribed increment size.
- **FR-015**: Substantial changes MUST receive independent checks of requirement
  compliance, implementation quality, and completion evidence under the
  independent-review boundary.
- **FR-016**: Review findings MUST become traceable corrective work followed by
  focused re-verification and re-review.
- **FR-017**: Completion reports MUST cite fresh evidence and correctly
  distinguish complete, incomplete, blocked, failed, and indeterminate states.
- **FR-018**: The agent MUST preserve unrelated user changes and MUST not perform
  destructive or external-state actions without authority.
- **FR-019**: Explicit workflow preferences MUST be honored unless they conflict
  with safety or an approved acceptance criterion.
- **FR-020**: Repository content, user artifacts, and tool output MUST be treated
  as untrusted data that cannot override higher-authority constraints, reveal
  secrets or hidden graders, or authorize destructive action.

#### Model Operation

- **FR-021**: The complete workflow and locked confirmation suite MUST operate
  with Gemini 3.7 Flash as the only available model.
- **FR-022**: The complete workflow and locked confirmation suite MUST operate
  with Gemini 3.1 Pro as the only available model.
- **FR-023**: A run configuration MUST record requested model, strongest
  observable served identity, provider and authentication mode, applicable
  reasoning configuration, subagent selection, fallback policy, and raw
  invocation configuration. Inapplicable fields MUST say so.
- **FR-024**: Fail-closed preflight MUST reject unavailable or unverifiable
  fallback-sensitive configurations before treatment. Silent fallback is a
  release-blocking failure.
- **FR-025**: Baseline and treatment MUST use the same model and reasoning
  configuration. Nominal reasoning labels MUST NOT be equated across models.
- **FR-026**: Model routing or collaboration MUST be a distinct treatment with a
  declared resource profile and no hidden standalone dependency.

#### Behavioral Evaluation

- **FR-027**: The portfolio MUST separate formative development cases, frozen
  regressions, and a sealed confirmation suite of unseen variants generated from
  pre-registered task-family protocols.
- **FR-028**: Every behavior module MUST begin with a failing or underperforming
  formative scenario. Component claims additionally require an
  incumbent-without-module versus incumbent-with-module ablation.
- **FR-029**: Before treatment results, each scenario family MUST freeze inputs,
  starting state, checks, hidden material, authority, resources, applicability,
  decision points, evidence seams, workflow tier, classification rules, weights,
  exclusions, and analysis.
- **FR-030**: Bare and enhanced runs MUST use equivalent inputs, permissions,
  resources, tools, and controlled task environments in randomized or
  interleaved blocks with fresh state and condition digests.
- **FR-031**: Three runs per cell MAY qualify a pilot. Release sample size MUST
  follow a pre-registered precision or power analysis accounting for scenario
  clustering, model effects, missing data, multiplicity, confidence, and a fixed
  stopping rule.
- **FR-032**: Primary analysis MUST include every scheduled run under
  intention-to-treat. A secondary valid-run analysis MUST report excluded and
  indeterminate runs, capped retries, and differential attrition.
- **FR-033**: Classification MUST separate process state, agent-declared state,
  permission or input state, infrastructure validity, deterministic grader
  result, and adversarial grader result.
- **FR-034**: Valid-start looping, self-induced timeout, tool misuse, and budget
  exhaustion MUST be product failures. Pre-start infrastructure failure, capture
  truncation, grader leakage, safety refusal, and test flake MUST use frozen
  classifications.
- **FR-035**: Evidence MUST include configuration, transcript, artifacts,
  changes, verification, duration, consumption, tool and subagent activity,
  permissions, errors, classifications, grader outputs, and content digests.
- **FR-036**: Protected raw evidence MUST be separate from redacted publishable
  evidence. Redaction MUST preserve auditability without exposing secrets,
  hidden material, or private reasoning.
- **FR-037**: Hidden checks MUST be combined with condition- and model-blind
  judgment. Presentation MUST be randomized and normalized, with an anchored
  rubric, two calibrated reviewers, adjudication, and reported agreement on a
  pre-registered sample.
- **FR-038**: Agent-visible execution MUST be isolated from hidden checks, grader
  instructions, reference solutions, and competing runs. Hidden checks execute
  outside the agent boundary with canary leakage probes.
- **FR-039**: Evaluation MUST use disposable task environments, fresh user and
  application state, pinned tool and fixture digests, scoped credentials, and
  cross-run contamination checks around remote inference.
- **FR-040**: Goal-completion comparison MUST use two separately reported Codex
  reference lanes: a repeatable CLI adapter on public or synthetic tasks and a
  smaller, pre-registered calibration against the current desktop harness. The
  lanes MUST NOT be pooled. Each lane MUST record its harness, tools, authority,
  resources, date, and score distribution and MUST NOT grade competitors.
- **FR-041**: Public release MUST NOT depend on the private desktop calibration
  or another non-public reference. The durable goal MUST NOT be declared
  achieved, and the release MUST NOT claim that the enhanced models rival
  Codex, unless both target models meet the frozen automated Codex margin and
  the separate desktop calibration is completed and reported with its opacity
  and sample limitations.
- **FR-042**: Quality claims MUST be conditional on pre-registered resource
  envelopes covering quota or cost, tokens, wall time, tool calls, retries, and
  subagent fan-out at central and tail percentiles.
- **FR-043**: Published claims MUST link to per-run evidence, tested versions,
  frozen aggregation, uncertainty, attrition, confounders, and limitations.
- **FR-044**: Regressions MUST cover interrogation, proportionality, durable
  intent, root-cause debugging, verification honesty, defect and defect-free
  review, repair, cold restart, preferences, dirty worktrees, prompt injection,
  permission soft-denial, missing input, hook and tool failure, model and quota
  drift, truncated capture, grader leakage, and state isolation.

#### Public Distribution

- **FR-045**: Third-party libraries MUST be consumed from attributed, pinned
  upstream sources and MUST NOT be silently republished.
- **FR-046**: Automated release checks MUST inventory dependencies and licenses
  and detect secrets, confidential identifiers, private paths, unattributed
  copied content, missing notices, and unexpected package files.
- **FR-047**: Recorded human provenance and license review MUST confirm the
  supported license policy, source digests, adaptations, attribution duties, and
  resolution of every critical automated finding.
- **FR-048**: Public documentation MUST distinguish public prerequisites from
  private maintainer resources and explain controlled task environments and the
  remote-inference reproducibility boundary.
- **FR-049**: The package, fixture, hidden grader, reference adapter, protected
  evidence, and published evidence MUST have explicit trust and access
  boundaries so evaluation cannot become self-grading.
- **FR-050**: The first general release MUST pass frozen gates for both models.
  A later model exclusion requires a pre-treatment spec amendment and separately
  named channel; it cannot be made after observing treatment results.

### Key Entities

- **Behavior Package**: The product with version, modules, policies, roles,
  component paths, supported surface, and dependencies.
- **Behavior Module**: A focused intervention with triggering conditions,
  desired behavior, non-goals, extension responsibility, and evidence.
- **Scenario Portfolio**: Formative, regression, and sealed-confirmation
  partitions with task-family protocols and contamination history.
- **Behavior Scenario**: A controlled task with state, applicability, ambiguity
  labels, authority, resources, checks, and classification rules.
- **Run Configuration**: Model and reasoning configuration, package condition,
  versions, authority, resources, task and environment digests, and time.
- **Resource Envelope**: Quota or cost, tokens, duration, tool calls, retries,
  and subagent fan-out permitted for a task family.
- **Evaluation Run**: A scheduled execution producing process, agent,
  infrastructure, deterministic, and adversarial outcome fields.
- **Evidence Bundle**: Protected raw evidence and its digest-linked publishable
  projection.
- **Behavior Scorecard**: Intention-to-treat and valid-run comparisons retaining
  uncertainty, attrition, regressions, resources, and limitations.
- **Reference Evidence**: Separately reported automated Codex CLI comparison and
  current-desktop calibration; the two lanes have distinct roles and are never
  pooled into one score.
- **Upstream Dependency**: A public library or tool with pinned source, license,
  attribution, dependency mode, and compatibility evidence.
- **Release Candidate**: A frozen package version evaluated against lifecycle,
  regressions, sealed confirmation, public safety, and provenance gates.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For each model on the sealed suite, the enhanced condition either
  improves macro-averaged task success by at least 20 percentage points or
  reaches at least 90% success when bare performance is at least 80%. The
  scenario-stratified confidence interval has a positive lower bound, no family
  crosses its frozen non-inferiority margin, and no material safety regression
  occurs.
- **SC-002**: On the matched, repeated Codex CLI reference lane, each enhanced
  model achieves at least 75% of Codex's normalized score, at least 80 out of
  100 on the absolute rubric, and no critical dimension below 70. The separate
  desktop calibration is completed and reported with its pre-registered limits.
  These are durable-goal criteria, not public-release gates.
- **SC-003**: On substantial tasks, at least 90% of pre-labeled material
  ambiguities are correctly identified and disposed of before the first
  scope-shaping edit, with at least 90% precision and no more than the frozen
  question burden.
- **SC-004**: On mixed planted-defect and defect-free review tasks, material
  defect recall is at least 85%, precision at least 80%, every accepted repair
  passes fresh hidden checks, and no repair introduces a material regression.
- **SC-005**: Critical false completion has zero tolerance. On a dedicated
  honesty suite, the one-sided 95% upper confidence bound for claiming completion
  while a required check fails, is missing, or is indeterminate is below 5%.
  Successful completion recall is also reported.
- **SC-006**: At least 90% of cold-restart scenarios recover every confirmed
  requirement, unresolved finding, completed verification obligation, and next
  action from durable artifacts and reach an equivalent final outcome.
- **SC-007**: At least 95% of clearly non-applicable tasks load no engineering
  instruction body, and each module meets pre-registered activation precision
  and recall. At least 90% of trivial-task runs avoid unnecessary specification,
  interruption, and multi-reviewer fan-out.
- **SC-008**: On supported CLI environments, a new user can install and verify
  the package in under 10 minutes excluding authentication and dependency
  download time. Install is idempotent, and removal leaves zero package-owned
  state and zero unintended change to unrelated state.
- **SC-009**: Every published run records requested and strongest observable
  served model identity, reasoning configuration, Antigravity and package
  versions, task and environment digests, authority, resources, and scoring
  version. No fallback-sensitive run has unverifiable substitution.
- **SC-010**: Public artifacts pass automated safety and provenance checks with
  zero unresolved critical findings and have recorded human license and
  provenance approval.
- **SC-011**: Two condition- and model-blind reviewers rate problem
  understanding, verification, review quality, and completion honesty at least
  4 out of 5 in at least 80% of representative complex runs, with per-dimension
  floors and at least 80% raw agreement before adjudication.
- **SC-012**: Every quality gate is met within its frozen resource envelope.
  Reports show median and 90th-percentile tokens, duration, tool calls, retries,
  and subagent fan-out. Differential timeout or indeterminate rates remain below
  the frozen attrition limit.
- **SC-013**: Every selected extension component has a component-to-scenario
  entry and focused ablation evidence. Removing an unneeded component does not
  reduce a claimed capability.

## Assumptions

- Version one targets software engineering in existing repositories; greenfield
  generation and non-engineering work may be evaluated later.
- CLI is the sole release-gating product surface. Desktop/IDE is experimental,
  and SDK use is evaluation-only until a later approved specification.
- Maintainers have legitimate CLI access to Gemini 3.7 Flash and Gemini 3.1 Pro
  and can request the exact model used.
- The automated Codex reference runs only public or synthetic fixtures. The
  desktop calibration may exercise the current private harness, but its private
  instructions and unrelated context are not copied into this repository.
- Public release may precede successful private Codex comparison, but it carries
  no claim that the package makes either target model rival Codex.
- Controlled task environments can pin repositories, tools, package inputs, and
  graders. Remote inference and sampling remain outside that boundary.
- Superpowers, Prime Radiant, Spec Kit, and the project owner's public skills
  remain independent projects whose interfaces and licenses may change.
- Hybrid composition means upstream-native packages retain their own identity
  and lifecycle, while this repository owns only original Antigravity-specific
  behavior and clearly marked, license-compliant adaptations.
- Thresholds may be amended before treatment evaluation but MUST NOT be weakened
  after results without a new experiment and unseen holdout.

## Dependencies

- A supported Antigravity CLI installation with legitimate model access,
  transcripts or run artifacts, and observable run configuration.
- Public upstream libraries and methods selected during planning under
  compatible licenses and pinned versions.
- A dependency resolver or verifier that preserves upstream identity, records
  source digests, and never silently copies upstream skill bodies.
- A versioned Codex CLI reference adapter capable of running the same public or
  synthetic suite under recorded authority and resources, plus access to the
  current Codex desktop harness for the separate maintainer calibration.
- Disposable execution capacity for randomized baseline, treatment, ablation,
  and reference runs without cross-run state leakage.
- At least two calibrated human reviewers for the pre-registered judgment sample.
