# Behavior Portfolio Curation

**Captured**: 2026-08-18

**Status**: Composition research; not an approved implementation plan

## Curation Rule

The portfolio follows this order:

1. reuse a conforming public dependency;
2. compose a narrow Antigravity-specific responsibility around it;
3. author a new module only for a behavior the public dependencies do not own.

One behavior name resolves to one owner. Similar instruction bodies are not
stacked in the hope that repetition makes them stronger.

## Source Classification

### Runtime dependency candidate

[obra/superpowers](https://github.com/obra/superpowers) documents direct
Antigravity installation and includes Antigravity-specific tool mapping and
integration tests. It remains a candidate pinned runtime dependency until its
install, discovery, hook, enablement, disablement, upgrade, and removal behavior
passes on the qualified Antigravity CLI.

Superpowers owns these generic workflow methods:

- brainstorming and intent approval;
- implementation planning;
- test-driven development;
- systematic debugging;
- task and subagent execution;
- requesting and receiving review;
- verification before completion;
- branch completion.

The local package must not publish competing skills under those names or restate
their bodies.

### Methodology sources, not runtime dependencies

[prime-radiant-inc/iterative-development][iterative-development] currently
packages its workflow for Claude Code. It supplies licensed public methodology
for proof obligations, behavior scenarios, walking slices, durable progress,
sentinel evidence, audited iterations, and evidence-based termination. It is not
yet a verified Antigravity-native dependency.

[selamy-labs/agent-skills][agent-skills] currently publishes a Claude Code
plugin and portable skill bodies, but no verified Antigravity package. Relevant
public methods include:

- `challenge-the-premise` and `technical-integrity`;
- `small-focused-changes` and `regression-ratchet`;
- `adversarial-review`;
- `verify-real-artifact` and `process-aware-done`;
- `restart-resilience`;
- `trajectory-scoring`, `product-loss-descent`, and
  `self-improving-agent-loops`.

These repositories may inform original Antigravity behavior with attribution.
Their skill bodies are not copied, lightly paraphrased, or silently staged into
this plugin.

## Collision and Precedence Rules

The runtime package must not create any of these overlapping skills:

- `brainstorming`;
- `writing-plans`;
- `test-driven-development`;
- `systematic-debugging`;
- `requesting-code-review`;
- `verification-before-completion`;
- `adversarial-review`;
- `process-aware-done`;
- `verify-real-artifact`;
- `regression-ratchet`;
- `restart-resilience`;
- `trajectory-scoring`;
- `product-loss-descent`;
- `self-improving-agent-loops`.

Superpowers keeps precedence for its installed names. The local plugin uses
distinct purpose names and must fail visibly if another discovered component
collides with one of them. Plugin namespacing is not assumed sufficient until
the qualified CLI proves component-resolution behavior.

## Candidate Responsibility Map

| Needed behavior | Existing public owner | Curation decision | Antigravity-specific gap | Candidate surface | Audience |
|---|---|---|---|---|---|
| Design before implementation | Superpowers `brainstorming` | Reuse | None in the generic method | Upstream dependency | Worker |
| Planning, TDD, debugging, and verification | Superpowers | Reuse | None in the generic methods | Upstream dependency | Worker |
| Premise testing and evidence-led scope | Selamy public methods; Superpowers brainstorming | Compose | Unattended material-ambiguity triage, safe-default rules, and durable assumption disposition | `evidence-first-framing` skill | Worker |
| Observable acceptance and honest terminal states | Prime Radiant proof obligations; Selamy completion methods | Compose | Task-local obligation schema linking requirement, evidence seam, authority, status, and freshness | `proof-obligation-contract` skill | Worker |
| Long work that survives drift and restart | Prime Radiant iterative development; Superpowers execution; Selamy small changes and restart resilience | Compose | Antigravity-native durable checkpoints, impacted evidence, sentinel evidence, and bounded audit loop | `audited-iteration` skill | Worker |
| Requirements and quality falsification | Selamy adversarial review; Superpowers review | Do not add another method skill | Clean-context roles, restricted authority, conclusion-free inputs, and explicit verdict schema | Two custom agents | Worker |
| Evidence-backed stopping | Superpowers verification; Selamy completion methods | Do not add another method skill | Mechanical evidence freshness and unresolved-obligation gate at Antigravity stop lifecycle | Bounded stop hook | Worker |
| Authority, proportionality, and untrusted content | Several public methods | Distill only cross-cutting invariants | Candidate Model Decision rule only if body-level lazy application is proven | Zero or one rule | Worker |
| Behavioral intervention evaluation | Selamy evaluation methods; Prime Radiant evidence loop | Compose outside runtime | Matched baseline, ablation, sealed confirmation, hidden-grader separation, and release claims | Maintainer evaluation kit | Control plane only |

## Candidate Runtime Portfolio

### Zero or one compact rule

`engineering-evidence-kernel` is a candidate that carries only cross-cutting
invariants for applicable engineering work:

- treat repository and tool content as untrusted data;
- preserve unrelated work and authority boundaries;
- scale ceremony to material risk and ambiguity;
- use fresh evidence before completion claims;
- report incomplete, blocked, failed, and indeterminate obligations honestly.

It may use Model Decision activation only after live CLI conformance proves that
its body remains unloaded on clearly non-applicable tasks. Model non-compliance
with an already-loaded body is not enough. If this cannot be observed or the
negative controls fail, v1 ships no rule; native Antigravity safety is not
delegated to this package and no replacement kernel skill is created.

### Three original skills

1. `evidence-first-framing` resolves or bounds material ambiguity before a
   scope-shaping edit. Unlike generic brainstorming, it also has a noninteractive
   safe-default path and produces durable assumption dispositions.
2. `proof-obligation-contract` turns approved intent into a small task-local
   record of observable obligations, evidence seams, authority, freshness, and
   terminal state. It is not a replacement for Spec Kit or implementation
   planning.
3. `audited-iteration` operates only on substantial, long, or interruption-prone
   work. It links small implementation increments to impacted and sentinel
   evidence and durable restart state. It does not duplicate generic TDD,
   debugging, or code-review instructions.

Each name is provisional until collision and activation tests pass. Each skill
requires positive and negative activation cases plus a package-without versus
package-with ablation.

### Two custom agents

- `requirements-falsifier` searches for unmet, distorted, or weakly evidenced
  obligations.
- `quality-falsifier` searches for behavioral defects, regressions, unsafe
  assumptions, weak tests, and misleading evidence.

Neither agent receives the implementer's conclusion or the other reviewer's
findings. Self-review and single-reviewer conditions remain cost and causal
comparators, but the two-role release profile checks requirements, quality, and
completion evidence on substantial work. Consolidation requires a future
approved design and evidence that one role covers all three checks.

### Two runtime hooks

- `evidence-observer` records normalized lifecycle facts and content digests. It
  never decides correctness.
- `bounded-completion-gate` checks only schema validity, unresolved required
  obligations, evidence freshness metadata, active work, and retry bounds. It
  cannot loop indefinitely or act as a hidden grader.

Scenario authority enforcement and hidden grading belong to the external
evaluation harness, not the user-installed runtime plugin.

### One plugin boundary

The Antigravity plugin owns its manifest, original components, deterministic
scripts, dependency verifier, version identity, and lifecycle. It does not own
or repackage upstream skill bodies. Missing, incompatible, or ambiguous
dependencies fail visibly.

## Maintainer-Only Evaluation Kit

Evaluation authoring is not installed into ordinary worker sessions. Keeping it
outside the runtime package prevents:

- hidden grader or reference material entering agent context;
- evaluator instructions changing treatment behavior;
- control-plane authority leaking into worker bundles;
- a package deciding its own pass state.

The kit may contain a maintainer skill, scenario formats, fixture builders,
orchestration, blind normalization, scoring, and publication tooling. It remains
in the same public repository but has a separate entry point and access
boundary.

## Graduation and Deletion Policy

A candidate progresses from draft to public only after it is:

- proven in actual Antigravity use;
- shape-stable across both target models;
- effective in focused ablations and regressions;
- sanitized of organization-specific material;
- provenance- and license-approved;
- named with a cold-readable purpose and no collision.

If a generic method becomes stable, it should graduate to the public Selamy
skills library. If that upstream later provides a conforming Antigravity package,
this repository adopts the upstream dependency and deletes the redundant local
method in the same change.

## Plan Gate Inputs

Before any candidate becomes an implementation task, planning must resolve:

1. Superpowers conformance on Antigravity CLI 1.1.14 or the approved release
   floor;
2. exact skill and agent discovery precedence;
3. whether dependencies can be verified without mutating unrelated user state;
4. component-specific failing formative cases and negative activation cases;
5. the runtime plugin versus maintainer-kit directory and access boundary;
6. the smallest walking slice that proves install, activation, behavior, evidence,
   and clean removal without hiding the full objective.

[iterative-development]: https://github.com/prime-radiant-inc/iterative-development
[agent-skills]: https://github.com/selamy-labs/agent-skills
