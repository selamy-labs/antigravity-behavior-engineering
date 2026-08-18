# Specification Adversarial Review Synthesis

**Review date**: 2026-08-18

**Reviewed artifact**:
[spec.md](../specs/001-improve-antigravity-behavior/spec.md)

**Initial verdict**: Request changes

**Current verdict**: Major findings addressed; clarification and human approval
remain required before planning.

## Review Method

Three independent reviews examined different failure surfaces:

1. Antigravity capability and product-contract feasibility;
2. Gemini model capability and standalone-treatment validity;
3. experimental design, causal attribution, and statistical claim strength.

The reviews attempted to falsify the specification rather than improve its
wording cosmetically. A concern counts as resolved only when the revised
specification contains a testable requirement or explicitly narrows the claim.

## Critical Findings and Disposition

### Product surface was undefined

- Risk: CLI, desktop/IDE, and SDK have different installation, authentication,
  model, permission, and evidence contracts.
- Decision: The user selected Antigravity CLI as the only v1 release-gating
  surface. Desktop/IDE is experimental and SDK is evaluation-only.
- Evidence in spec: Scope, Clarifications, FR-001–FR-002, SC-008.
- Status: Resolved.

### Full extension surface was being treated as a component quota

- Risk: Requiring a skill, rule, hook, agent, and plugin regardless of evidence
  would reward artifact count and unnecessary complexity.
- Decision: Every extension surface is available, but each selected component
  must have a distinct responsibility and focused ablation.
- Evidence in constitution: Principle IV, version 1.0.1.
- Evidence in spec: Scope, FR-028, SC-013.
- Status: Resolved.

### Upstream dependency behavior was unspecified

- Risk: Antigravity has no documented cross-plugin dependency resolver, and
  upstream projects differ in native support and licensing.
- Decision: FR-003 defines dependency modes and fail-visible behavior.
  The user approved hybrid composition: verified upstream-native Antigravity
  packages remain pinned upstream dependencies, while unsupported methodology
  informs independently authored Antigravity-native modules.
- Evidence: FR-003, FR-045–FR-047, provenance-inventory.md.
- Status: Resolved.

### Automatic activation was not operationally observable

- Risk: Skill metadata normally appears at discovery while body access and
  behavior selection are model-driven. An activation breadcrumb could change the
  behavior being measured.
- Decision: Applicability is frozen in fixture metadata. Product evaluation
  measures behavior; separate trace probes assess discovery and irrelevant body
  access.
- Evidence in spec: FR-004–FR-005, SC-007.
- Status: Resolved.

### Model identity and reasoning controls differed by surface

- Risk: CLI, SDK, and custom subagents expose different identifiers and controls.
  A report could claim an exact model that was not observable.
- Decision: Run configuration is surface-aware, records requested and strongest
  observable served identity, and says not applicable instead of inventing
  equivalence. Fallback-sensitive preflight fails closed.
- Evidence in spec: FR-023–FR-025, SC-009.
- Status: Resolved for CLI v1; live preflight remains an implementation gate.

### Interaction and successful exit were conflated

- Risk: Headless permission soft-denial can exit zero, and unattended runs can
  legitimately need clarification or approval.
- Decision: Requirements distinguish user-input, permission, process, agent,
  infrastructure, and grader state. NEEDS_INPUT is explicit; exit zero is not
  completion evidence.
- Evidence in spec: FR-011, FR-033–FR-035; Edge Cases.
- Status: Resolved.

### Forced compaction was not a portable CLI control

- Risk: A mandatory forced-compaction test depended on an undocumented control.
- Decision: The release gate is cold new-process recovery from durable artifacts.
  Natural or SDK-specific compaction can be studied separately.
- Evidence in spec: FR-013, SC-006.
- Status: Resolved.

### Independent review was not defined

- Risk: A reviewer could inherit the implementer's conclusion, repeat its
  assumptions, or depend on a product tier unavailable to v1 users.
- Decision: Independence is a fresh context receiving requirements, actual
  artifact, verification interface, and authority—but not conclusions or scratch
  reasoning.
- Evidence in spec: Normative Definitions, FR-015–FR-016.
- Status: Resolved.

### Bare-versus-full could not attribute modules

- Risk: Overall package lift says nothing about whether a particular skill,
  rule, hook, or agent helped.
- Decision: Bare-versus-full estimates product lift. Incumbent-without-module
  versus incumbent-with-module ablation supports component claims.
- Evidence in spec: FR-028, SC-013.
- Status: Resolved.

### Bare Antigravity was contaminated by user state

- Risk: Global plugins, skills, settings, conversations, permissions, caches, and
  repository instructions could leak into baseline.
- Decision: Bare condition has a fresh user and application-state boundary,
  pinned settings, no unlisted extensions, fixture-only repository instructions,
  and a starting digest.
- Evidence in spec: Normative Definitions, FR-030, FR-039.
- Status: Resolved.

### The release sample was underpowered and pseudoreplicated

- Risk: Three repetitions per cell cannot establish a 20-point lift or a
  below-five-percent false-completion rate.
- Decision: Three runs are pilot-only. Release size follows a pre-registered
  precision or power analysis accounting for clustered scenarios, model effects,
  missing data, multiplicity, and fixed stopping.
- Evidence in spec: FR-031, SC-001, SC-005.
- Status: Resolved at requirements level.

### Development and release data were the same

- Risk: Selecting failures and tuning against them before publishing the result
  creates overfit, regression to the mean, and cherry-picking.
- Decision: Formative, frozen regression, and sealed confirmation partitions are
  separate. Candidate, protocols, weights, exclusions, and analysis freeze
  before holdouts open. Opened failed holdouts become development data.
- Evidence in spec: User Stories 2 and 5, FR-027–FR-030.
- Status: Resolved.

### Indeterminate outcomes could hide product failure

- Risk: Selective infrastructure labels and unlimited reruns could erase hard
  treatment failures.
- Decision: Intention-to-treat includes every scheduled run. A secondary
  valid-run analysis reports exclusions and attrition. Valid-start looping,
  self-induced timeout, misuse, and budget exhaustion count as product failures.
- Evidence in spec: FR-032–FR-034, SC-012.
- Status: Resolved.

### Metrics rewarded performative traces

- Risk: Verbose questioning, shotgun review, or always abstaining could game
  ambiguity, defect, and honesty scores.
- Decision: Ambiguity uses pre-labeled recall, precision, decision timing, and
  question burden. Review mixes defect and defect-free tasks and measures recall,
  precision, repair correctness, and regression. Honesty reports both false
  completion and successful completion recall.
- Evidence in spec: SC-003–SC-005.
- Status: Resolved.

### Graders could infer model or treatment

- Risk: Style or metadata could reveal condition, and one reviewer could produce
  unstable judgment scores.
- Decision: Normalize and randomize evidence; blind model and condition; use an
  anchored rubric, two calibrated reviewers, agreement reporting, and
  adjudication.
- Evidence in spec: FR-037, SC-011.
- Status: Resolved.

### Quality could be bought with unbounded cost

- Risk: Fan-out and long runtimes could improve quality while making the package
  unusable.
- Decision: Each task family has a frozen resource envelope. Report central and
  tail tokens, duration, tools, retries, and subagent fan-out. More-expensive
  collaboration is a separately named profile.
- Evidence in spec: FR-026, FR-042, SC-012.
- Status: Resolved.

### Reference-agent comparison was not reproducible

- Risk: An opaque reference, mismatched authority, or low reference score makes
  a percentage ratio meaningless.
- Decision: The reference uses a versioned adapter and matched authority and
  resources, never grades competitors, and is compared against both normalized
  and absolute floors. Codex is the approved private goal-completion reference:
  a repeatable CLI lane and a separately reported current-desktop calibration
  lane that are never pooled. Neither lane gates public release.
- Evidence in spec: FR-040–FR-041, SC-002.
- Status: Resolved.

### Evaluator sandboxing was mistaken for hermeticity

- Risk: Native command sandboxing is not a hidden-grader boundary, and remote
  inference cannot be hermetic.
- Decision: Disposable task environments isolate visible execution from hidden
  checks and competing outputs. Canary probes detect leakage. Reports explicitly
  describe controlled environments around remote inference.
- Evidence in constitution: Principle IX.
- Evidence in spec: FR-038–FR-039, FR-048–FR-049.
- Status: Resolved.

### Prompt injection and lifecycle coexistence were missing

- Risk: Repository or tool content could disable verification, while install or
  uninstall could corrupt user customizations.
- Decision: Untrusted-content authority requirements and adversarial scenarios
  are explicit. Lifecycle covers precedence, conflict reporting, idempotence,
  upgrade, rollback, disablement, and removal with before-and-after manifests.
- Evidence in spec: User Stories 1 and 4, FR-006–FR-008, FR-020, SC-008.
- Status: Resolved.

### Automated provenance was treated as legal certainty

- Risk: Scans cannot establish copied-content status or legal compatibility.
- Decision: Automated inventory and detection are separate from recorded human
  provenance and license approval.
- Evidence in spec: FR-045–FR-047, SC-010.
- Status: Resolved.

### Model scope could be reduced after results

- Risk: A failing model could be excluded post hoc while retaining a dual-model
  claim.
- Decision: The first general release must pass both models. Exclusion requires a
  pre-treatment specification amendment and separately named release channel.
- Evidence in spec: FR-021–FR-022, FR-050.
- Status: Resolved.

## Remaining Approval Sequence

1. Re-evaluate the specification checklist after clarification.
2. Obtain explicit specification approval.
3. Create the Spec Kit plan.
4. Run the formal Spec Kit requirements-quality checklist after plan creation.
5. Obtain explicit plan approval before implementation.

## Current Gate

The specification is not approved, planning has not started, and no behavioral
lift claim exists. The durable goal remains active.
