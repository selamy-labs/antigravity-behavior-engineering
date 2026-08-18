# Implementation Plan Adversarial Review

**Reviewed**: 2026-08-18

**Reviewer boundary**: Independent agent received only the approved `spec.md`
and draft `plan.md`, was instructed to refute readiness, and made no edits.

## Round 1 Verdict: REVISE

### 1. Pre-registration was too late

**Finding**: The plan first froze weights, classifications, exclusions, sample,
and analysis after component treatment results, and listed the precision or
power plan as a sealed-confirmation output.

**Resolution**:

- Phase 3 now creates an immutable per-family intervention and analysis lock
  before any treatment in that family.
- Baseline variance informs the release precision or power design.
- Phase 8 freezes that design, sample, and stopping rule before sealed treatment.
- Phase 9 may execute but cannot change the pre-registered plan.

### 2. The universal rule violated non-applicability

**Finding**: An always-loaded rule could not satisfy SC-007's requirement that
clearly non-applicable tasks load no engineering instruction body.

**Resolution**:

- The kernel is now a model-decided rule eligible only for applicable software
  engineering work.
- Native Antigravity safety remains responsible outside package activation.
- Phase 4 gates rule activation precision and Phase 8 repeats integrated
  first-task and non-applicability evidence.

### 3. Sequential ablations did not prove final composition

**Finding**: A later component could supersede an earlier component even though
the earlier one had passed when it was introduced.

**Resolution**:

- Phase 8 now runs final-candidate leave-one-component-out regressions for every
  selected rule, skill, agent role, and hook.
- A component with no remaining claimed contribution is removed before candidate
  freeze.

### 4. One reviewer could miss a required lens

**Finding**: The plan allowed one reviewer as the default even though FR-015
requires independent checks of requirements, implementation quality, and
completion evidence.

**Resolution**:

- The current release profile uses both conclusion-free roles for substantial
  work and neither for trivial work.
- A future single-role consolidation requires an approved plan change and proof
  that one independent role covers all three checks.

### 5. Sealed confirmation lacked an explicit freeze approval artifact

**Finding**: The plan named candidate freeze as a human gate but did not require
proof before opening the one-use sealed bundle.

**Resolution**:

- `ApprovalRecord` binds candidate, protocol, analysis, precision or power,
  sample, stopping, and exclusion digests.
- Phase 8 requires project-owner candidate-freeze approval.
- Phase 9 and the quickstart confirmation command require that approval.

## Round 2 Verdict: REVISE

The reviewer confirmed findings 1, 3, 4, and 5 closed. One blocker remained:
the plan asserted that Rule `Model Decision` withheld the instruction body, but
had not defined evidence that distinguished lazy application from a model merely
ignoring an already-loaded rule.

**Resolution**:

- Phase 2 now requires an instrumented live conformance probe using the strongest
  observable customization trace.
- The rule is a zero-or-one candidate, not an assumed architecture component.
- If body-level selective application is unobservable or any non-applicable
  control receives the body, v1 ships no rule and creates no replacement kernel
  skill.
- The focused skills keep distinct framing, evidence, and recovery ownership;
  native Antigravity retains baseline safety.

## Round 3 Verdict: REVISE

The reviewer confirmed the SC-007 blocker closed and found one new contradiction:
Phase 7 still required `rule-only` versus `rule-plus-gate`, which cannot execute
when rule conformance selects the no-rule path.

**Resolution**: The completion-gate ablation now compares the current incumbent
without the gate against the identical incumbent with the gate. Both condition
locks record the same qualified-rule presence or absence.

## Round 4 Verdict: SHIP_FOR_OWNER_REVIEW

The independent reviewer confirmed that the completion-gate ablation works with
either qualified-rule presence or the no-rule path and that all prior blockers
remain closed. No additional blocking contradiction was found.

## Requirement Traceability Review Round 1: REVISE

After the one-row-per-requirement matrix was added, the independent reviewer
found five rows whose promised proof was stronger than the plan:

1. FR-025 lacked a defined ConditionPairLock validator before agent input.
2. FR-031 did not enumerate clustering, model effects, missing data,
   multiplicity, confidence, and margins inside AnalysisLock.
3. FR-047 lacked a recorded human ProvenanceApprovalRecord bound into candidate
   freeze.
4. SC-008 lacked timed first-user installation tests on every supported OS with
   authentication and download intervals separated.
5. SC-012 lacked required median/p90 reporting and a frozen differential
   attrition limit.

**Resolution**: Phase 0, Phase 1, Phase 3, Phase 8, Phase 9, the data model, and
the runner contract now define each artifact, measurement, and blocking gate.

## Requirement Traceability Review Round 2: REVISE

The reviewer confirmed the five Round 1 repairs and found three remaining gaps:

1. FR-031 named a precision or power plan but lacked a typed derivation artifact
   connecting blinded inputs and assumptions to per-model sample sizes.
2. FR-032's ScheduledAttempt schema, state diagram, retry link, and pre-worker
   exit semantics contradicted one another and could leave a failure without a
   stable RunRecord identity.
3. SC-005 had no fully specified independent unit, exact confidence procedure,
   minimum effective sample, or separate successful-completion recall measure.

**Resolution**:

- `PrecisionPowerLock` now freezes blinded inputs, estimands, variance and
  cluster assumptions, targets, per-model allocations, attrition, computation,
  multiplicity, missing-data, and stopping-rule digests.
- Every ScheduledAttempt now receives `runId` at scheduling, uses one declared
  monotonic lifecycle, retains explicit replacement links, and finalizes a
  RunRecord even when the worker never starts.
- The completion-honesty family now uses independent scenario variants as its
  unit, zero-tolerance critical events, an exact one-sided 95% Clopper-Pearson
  upper bound, at least 59 effective variants per model on the zero-event path,
  intention-to-treat reporting, attrition, and separate recall on genuinely
  successful completions.

## Requirement Traceability Review Round 3: REVISE

The reviewer confirmed the FR-031 and FR-032 repairs, then found that SC-005's
59-variant denominator could still pool positive controls, bare-condition runs,
repetitions, or replacements.

**Resolution**:

- The critical gate is now separate for each model under the `full`
  release-candidate condition and uses only distinct negative variants whose
  required check fails, is missing, or is indeterminate.
- A frozen reduction policy maps every original/replacement attempt to one
  model-condition-variant outcome; replacements and repetitions cannot increase
  the distinct denominator, and a variant without a gradable claim state is
  reported as attrition.
- Each model's full condition must retain at least 59 evaluable distinct negative
  variants or fail the gate. Bare results are comparator-only.
- Working-evidence variants form a disjoint positive cohort used only for the
  separately reported successful-completion recall.

## Requirement Traceability Review Round 4: SHIP_TRACEABILITY

The independent reviewer confirmed that the release gate is now isolated per
exact model and full-candidate condition, uses at least 59 distinct evaluable
negative variants, cannot be inflated by positive controls, bare runs,
repetitions, or replacements, and reports attrition and positive-cohort recall
separately. The reviewer found no contradiction introduced by the repair.
