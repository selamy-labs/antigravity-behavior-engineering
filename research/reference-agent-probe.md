# Reference Agent Capability Probe

**Observed**: 2026-08-18

**Status**: Read-only feasibility research; no reference task was run

## Local Automation Surface

- Executable: /opt/homebrew/bin/codex
- Version: codex-cli 0.145.0
- Non-interactive entry point: codex exec

The local CLI command contract supports:

- an explicit model;
- a named configuration profile;
- a selected working root and additional writable roots;
- read-only, workspace-write, and unrestricted sandbox modes;
- ephemeral sessions that do not persist session files;
- an option to ignore user configuration;
- an option to ignore project and user execution-policy rules;
- strict configuration validation;
- JSONL event output;
- a final-response JSON schema;
- a separate last-message artifact;
- session resume and a dedicated review command.

No model inference, repository mutation, or reference score was produced by this
probe.

## Two Different Meanings of “This Codex Harness”

### Repeatable CLI Reference

A versioned CLI adapter can pin the executable, model, profile, authority,
working root, sandbox, output schema, tools, task digest, timeout, and date. It
can run in disposable environments and produce machine-readable evidence.

Advantages:

- repeatable scheduling;
- stronger condition matching;
- randomized repeated trials;
- structured evidence and failure classification;
- no dependence on manually operating this task.

Limitations:

- ignoring user configuration removes the accumulated local skill and plugin
  behavior the user wants Antigravity to rival;
- retaining user configuration introduces private, mutable, and possibly
  machine-specific behavior;
- the CLI may not have exactly the same system instructions, tools, connectors,
  or interaction semantics as the Codex desktop task.

### Current Desktop Harness Calibration

This task reflects the current Codex desktop environment, its available skills,
rules, plugins, tools, and hidden product instructions.

Advantages:

- closest to the behavior the user explicitly described as the target;
- includes the accumulated local agentic engineering solution.

Limitations:

- private system instructions cannot be exported;
- task state and product versions drift;
- manual runs are difficult to randomize and repeat at release scale;
- exact authority, budget, and tool parity with Antigravity may be impossible;
- it cannot grade competitors without creating circularity.

## Approved Reference Contract

The user approved the current Codex harness as a private goal-completion
reference with a two-lane contract:

1. **Automated reference lane**: a frozen Codex CLI adapter runs repeated public
   or synthetic tasks under recorded authority and resource envelopes.
2. **Desktop calibration lane**: the current Codex app performs a smaller,
   pre-registered blinded artifact assessment or selected task sample as an
   opaque maintainer comparison.

The two lanes must never be pooled into one score. The automated lane supports
distributional comparison. The desktop lane supports ecological calibration to
the behavior that motivated the project.

## Binding Semantics

The phrase “rivals Codex” should require:

- both target Gemini models pass their standalone public release gates;
- both reach the frozen reference margin on the automated Codex lane;
- no critical capability or safety dimension is below its absolute floor;
- desktop calibration is reported separately with its opacity and sample limits;
- the reference agent never sees treatment identity and never grades its own
  competitors;
- provider-specific cost is reported separately when budget equivalence cannot
  be established.

Public release can remain possible when the opaque desktop lane is unavailable,
but the durable project goal must not be marked achieved without the approved
reference evidence.

## Qualification Requirements

Before the reference adapter enters a comparison:

- record executable and configuration digests;
- record the strongest observable served model, reasoning setting, and product
  version;
- define whether user config, rules, skills, plugins, and MCP are included;
- enumerate tools and authority;
- use the same task, starting repository, network policy, hidden-grader boundary,
  timeout, and outcome rubric as the Antigravity conditions;
- freeze retry and exclusion policy;
- prove protected grader material is unavailable;
- emit normalized evidence that removes model and condition identity before
  human judgment;
- repeat the reference condition according to the same precision plan.

## Current Disposition

The two-lane Codex reference is required to declare the durable project goal
achieved but is not a public-release gate. A public release without successful
private reference evidence cannot claim that either target model rivals Codex.
