# Model Capability Implications

**Captured**: 2026-08-18

**Status**: Public-source research; non-normative until the specification is
approved and a plan is approved

## What the Public Evidence Establishes

Gemini 3.7 Flash and Gemini 3.1 Pro are both plausible standalone engineering
agents. They share a documented one-million-token input window and 64K-token
text output. Google describes both as suitable for agentic and coding work.

The [Gemini 3.7 Flash model card][flash-card] reports configurable thinking and
strong results on long-horizon software engineering and terminal-agent tasks,
including 65.3% on DeepSWE v1.1 and 85.8% on Terminal-bench 2.1. It also reports
14.9% on the harder Terminal-bench 3.0, showing substantial capability without
eliminating room for harness improvement.

The [Gemini 3.1 Pro model card][pro-card] reports strong software-engineering
and agentic results, including 80.6% on SWE-bench Verified, 54.2% on SWE-bench
Pro, and 68.5% on Terminal-Bench 2.0 under its stated harness.

These provider-reported benchmarks use different tasks, dates, and scaffolds.
They establish prior capability, not a direct Flash-versus-Pro ordering and not
evidence that this package improves either model.

## Product Implications

### Improve control, not basic competence

The package should concentrate on failures that a capable model still exhibits
inside an engineering harness:

- acting before material ambiguity is resolved;
- losing confirmed intent during a long trajectory or restart;
- treating a plausible implementation as proof of observable behavior;
- accepting superficial test success or self-review;
- failing to turn review findings into verified repairs;
- claiming completion after a soft denial, missing check, or indeterminate run;
- spending excessive time and tokens on trivial work;
- obeying repository or tool content that exceeds its authority.

Generic coding tutorials, exhaustive style rules, and always-on procedural
checklists are unlikely to add enough value to justify their context and latency
cost.

### Start with one common behavior contract

Neither model should be assigned a permanent role from its Flash or Pro label.
The first treatment should expose the same capability contract to both models.
A model-specific profile is justified only when a focused ablation shows a
repeatable failure in one model and a targeted adaptation fixes it without
weakening the common contract.

### Treat reasoning level as part of the treatment identity

The [Antigravity headless guide][headless] exposes separate high and medium
Gemini 3.7 Flash slugs, Gemini 3.1 Pro high, and an effort control. Evaluation
must record the requested slug, requested effort, and strongest observable
served identity. It must fail closed if those controls are unavailable or do
not affect the observed run configuration.

Reasoning level must not drift between baseline and treatment. A lower-cost
profile can be evaluated separately, but it cannot be pooled with the primary
quality condition.

## Evaluation Implications

### Avoid ceiling-only tasks

High-capability baselines can make ordinary repository fixes uninformative.
Each scenario family needs a mix of:

- tasks with enough headroom to reveal improvement;
- tasks where the bare model is already strong and treatment must be
  non-inferior;
- defect-free cases that expose over-review and unnecessary edits;
- planted ambiguities, false seams, and plausible-but-wrong verification paths;
- long trajectories or cold restarts that test durable state;
- controlled prompt injection, permissions, and partial infrastructure failure.

### Score the artifact and the trajectory separately

Correct final code is necessary but cannot prove the intended behavior. The
evaluation should separately measure:

- externally checked task success;
- ambiguity identification and disposition;
- preservation of confirmed requirements;
- quality and freshness of verification evidence;
- independent-review recall and precision;
- repair correctness and regression rate;
- completion honesty;
- resource use and unnecessary ceremony.

Trajectory measures must not reward performative narration. Hidden checks and
artifact outcomes remain the primary evidence whenever they can decide the
question.

### Expect smaller lift than weak-model demonstrations

Because both baselines may already be strong, useful evidence can be a mix of
absolute lift, reduced catastrophic failure, lower variance, and non-inferior
quality at lower resource cost. Sample size and stopping rules must be selected
after blinded baseline variance estimates, then frozen before treatment
confirmation.

## Consequence for the Proposed Extension Surface

The current behavior-architecture hypotheses remain directionally consistent
with the model evidence:

- a compact Model Decision rule may carry authority, proportionality, and
  evidence invariants on applicable engineering work only after body-level lazy
  application is proven;
- focused skills supply decision protocols only when their scenario applies;
- custom agents create fresh-context requirements and quality falsification;
- hooks observe lifecycle state and enforce bounded mechanical gates;
- evaluation authoring remains part of the product so every intervention has a
  causal and regression test.

The full surface is useful because responsibilities differ, not because every
surface must contain equal amounts of content.

[flash-card]: https://deepmind.google/models/model-cards/gemini-3-7-flash/
[pro-card]: https://deepmind.google/models/model-cards/gemini-3-1-pro/
[headless]: https://antigravity.google/docs/cli/headless/
