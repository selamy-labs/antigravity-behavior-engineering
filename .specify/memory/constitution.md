<!--
Sync Impact Report
- Version change: 1.0.0 -> 1.0.1
- Added principles:
  - I. Behavioral Outcomes Over Artifacts
  - II. Eval-First Behavior Engineering (NON-NEGOTIABLE)
  - III. Evidence Before Completion
  - IV. Full Surface, Clear Responsibilities
  - V. Models Are Measured, Not Stereotyped
  - VI. Progressive Context and Durable State
  - VII. Independent Adversarial Iteration
  - VIII. Public-Safe Composition and Attribution
  - IX. Hermetic Task Environments, Honest Inference Boundary
- Added sections:
  - Product and Safety Boundaries
  - Development and Evaluation Workflow
- Removed sections: none
- Clarifications:
  - Extension surfaces are available tools, not mandatory component quotas.
  - Release evidence is separated from formative behavior development.
  - Model identity and reasoning configuration are recorded per product surface.
  - Spec Kit approval gates govern package development and release, not every
    end-user task executed by the installed package.
- Deferred items: initial supported Antigravity product-surface matrix remains
  a feature-specification decision.
-->

# Antigravity Behavior Engineering Constitution

## Core Principles

### I. Behavioral Outcomes Over Artifacts

Every repository component MUST target an observable Antigravity behavior tied
to a named user need or failure scenario. The number of skills, prompts, rules,
hooks, or agents is not a measure of success. Each behavior-changing proposal
MUST state the baseline behavior, desired behavior, and evidence that would
distinguish them. Components without a demonstrated behavioral purpose MUST NOT
be added.

### II. Eval-First Behavior Engineering (NON-NEGOTIABLE)

Every new or materially changed skill, rule, hook, or custom agent MUST begin
with a behavioral scenario that fails or underperforms without the change. The
same scenario MUST then be run with the treatment under comparable conditions.
The smallest intervention that closes the observed gap is preferred. Newly
discovered evasions, rationalizations, and failure modes MUST become regression
cases. Formative scenarios MAY guide development, but public causal or release
claims MUST come from evaluation evidence whose tasks and analysis rules were
frozen before the candidate treatment was examined. Evaluator scaffolding may
precede the first failing run only when needed to make the scenario executable.

### III. Evidence Before Completion

An agent's narrative, a successful process exit, or a passing proxy check MUST
NOT be accepted as proof by itself. Completion claims MUST point to evidence at
the real behavior seam: independent tests, inspected artifacts, repository
diffs, transcripts, or an adversarial grader as appropriate. Failed and
indeterminate outcomes MUST remain visible. A claim is complete only when a
reviewer can reproduce how the evidence supports it.

### IV. Full Surface, Clear Responsibilities

The project MAY use any Antigravity extension surface when it is the smallest
effective intervention: skills for judgment-heavy methods, rules for stable
invariants, hooks or scripts for mechanically enforceable gates and telemetry,
custom agents for independent roles, and plugin packaging for installation and
discovery. Every used surface MUST have a distinct, evaluated responsibility.
The same policy MUST NOT be redundantly encoded across multiple surfaces without
a documented defense-in-depth reason. Portable methods SHOULD remain portable,
while the installed product MUST optimize Antigravity behavior.

### V. Models Are Measured, Not Stereotyped

Gemini 3.7 Flash and Gemini 3.1 Pro MUST each be treated as capable standalone
engineering agents. Model roles, routing, and collaboration patterns MUST be
earned through evidence rather than inferred from the Flash or Pro label.
Evaluations MUST record the exact model identifier, reasoning effort,
or surface-specific equivalent when applicable; the strongest observable served
model identity; Antigravity and plugin versions; available tools; permissions;
budgets; authentication mode; and date. Unobservable immutable model identity
MUST be disclosed rather than guessed. Silent model fallback is prohibited.
Multi-model collaboration MAY improve performance but MUST NOT become an
undeclared dependency.

### VI. Progressive Context and Durable State

Instructions MUST be focused, discoverable, and progressively disclosed;
large monolithic operating prompts are prohibited. Critical constraints MUST
be available when decisions are made, while heavy references are loaded only
when relevant. Requirements, decisions, progress, review findings, and
verification evidence MUST live in versioned artifacts so work can survive
context compaction, interruption, and resumption without relying on memory.

### VII. Independent Adversarial Iteration

The implementer MUST NOT be the sole authority that its work is correct.
Specification compliance, code quality, and final verification MUST receive an
independent review with fresh context when the harness supports it. Reviewers
MUST attempt to falsify claims and inspect the real artifact. Findings become
traceable corrective work, and the system MUST iterate until the relevant
evidence passes or the result is honestly reported as blocked or indeterminate.

### VIII. Public-Safe Composition and Attribution

The repository MUST contain no Google-confidential information, internal
identifiers, private operating practices, credentials, customer data, or local
machine assumptions. Existing public skill libraries MUST be composed from
their upstream sources, with versions pinned and licenses honored, rather than
silently copied. Any adapted content MUST preserve required attribution and
pass a license review. Organization-specific lessons MUST be generalized and
screened before public inclusion.

### IX. Hermetic Task Environments, Honest Inference Boundary

Evaluation tasks SHOULD run in disposable environments with pinned toolchains,
fixture and grader digests, isolated state, scoped credentials, and captured
artifacts. The remote model service is outside that hermetic boundary. Reports
MUST describe the result as a controlled task environment around remote
inference and MUST disclose service drift, sampling variance, and other limits
on reproducibility. No stronger claim of hermeticity is permitted.

## Product and Safety Boundaries

- The primary product is an installable, public Antigravity behavior plugin.
- The initial user is the project owner in a policy-constrained work setting;
  the public design MUST remain useful without access to private infrastructure.
- The plugin MAY contain skills, rules, hooks, custom agents, scripts, fixtures,
  and evaluation adapters when each has a distinct responsibility.
- Third-party libraries, including Superpowers and Prime Radiant projects, MUST
  be consumed as attributed upstream dependencies or research inputs. They are
  not vendored by default.
- Destructive actions, external publication, credential use, and changes to
  systems outside the evaluation environment remain subject to explicit human
  authority and applicable policy.
- The project does not train or modify base models, promise parity from a
  single benchmark, or embed confidential work examples.

## Development and Evaluation Workflow

1. Use the gated Spec Kit flow to develop this package: constitution,
   specification, clarification, plan, quality checklist, tasks, cross-artifact
   analysis, implementation, and convergence. The installed package MUST apply
   a proportionate workflow to end-user tasks rather than imposing this entire
   package-development lifecycle on each task.
2. Obtain explicit human approval of this package's specification before
   planning and of its plan before implementation. Public release requires a
   separate approval.
3. For each target behavior, capture a bare-Antigravity baseline before writing
   the treatment. Pre-register acceptance criteria and material confounders.
4. Run baseline and treatment contemporaneously with comparable task inputs,
   permissions, budgets, and environments. Use repeated trials where model
   variance can change the conclusion.
5. Combine deterministic hidden checks with model-blind adversarial assessment.
   Manually inspect representative automated scores and every surprising result.
6. Track correctness, problem understanding, verification quality, review
   quality, completion honesty, cost, latency, and unnecessary tool or agent
   fan-out. Capability gains MUST NOT conceal material safety or efficiency
   regressions.
7. Release a behavior change only after its focused scenario and the relevant
   regression suite pass. Publish the method, evidence, limitations, and exact
   tested versions with every capability claim.

## Governance

This constitution supersedes conflicting project conventions. Every feature
specification, plan, task set, review, and release MUST include a constitution
compliance check. Deviations require an explicit rationale, bounded duration,
owner, and removal condition; convenience alone is insufficient.

Amendments require a documented proposal, explicit human approval, an updated
Sync Impact Report, and semantic versioning. MAJOR versions remove or redefine
governing guarantees, MINOR versions add or materially expand principles, and
PATCH versions clarify existing intent. Compliance MUST be reviewed whenever a
Spec Kit artifact crosses a human approval gate and before any public release.

**Version**: 1.0.1 | **Ratified**: 2026-08-18 | **Last Amended**: 2026-08-18
