# Research Evidence Register

**Captured**: 2026-08-18

**Purpose**: Record the public evidence behind the feature specification,
separate source facts from project inferences, and define what must be refreshed
before implementation or evaluation.

## Evidence Standard

- **Documented fact** is stated by a primary, public source.
- **Repository observation** is tied to a public repository and commit digest.
- **Inference** is a project conclusion drawn from facts and must be tested.
- **Open evidence** is too weak or unstable to support a product claim.
- Model benchmarks establish prior capability, not package lift. Only this
  project's controlled baseline and treatment runs can establish package lift.

## Antigravity Product Evidence

The current workstation's live results and qualification limits are recorded in
[local-capability-probe.md](local-capability-probe.md). The consolidated
first-party packaging and lifecycle contracts are recorded in
[antigravity-extension-contract.md](antigravity-extension-contract.md).

| Evidence | Classification | Specification consequence |
|---|---|---|
| The [Antigravity changelog](https://antigravity.google/changelog) lists CLI 1.1.14 on 2026-08-18. Releases 1.1.5–1.1.14 added stable model slugs and effort selection, structured headless events, headless skill expansion, functional stop-hook ordering, correct model and effort flag application, machine-readable model inventory, and unified custom-agent customization inheritance. | Documented fact | Treat 1.1.14 as the candidate qualification floor. Prove the exact required controls before freezing the release minimum; do not evaluate on any local unqualified CLI observation. |
| [Headless mode](https://antigravity.google/docs/cli/headless/) lists Gemini 3.7 Flash high and medium and Gemini 3.1 Pro high model slugs. Unknown pinned models fail non-zero rather than silently falling back. | Documented fact | Pin the exact requested slug, run fail-closed preflight, and record the strongest observable served identity. |
| The same headless guide exposes text, JSON, and streaming JSON. Streaming JSON carries progress, tools, and token usage; terminal results carry status and errors. | Documented fact | CLI can be the v1 automation and evidence-capture surface. Validate actual event schemas at the pinned CLI version. |
| Headless runs are stateless by default but can resume a named conversation. | Documented fact | Test both conversation resume and stronger cold-process recovery from durable repository artifacts. |
| A permission requiring interaction can be soft-denied while the run continues and exits zero. | Documented fact | Process exit is never sufficient evidence. Capture permission state, agent state, artifact state, and grader results separately. |
| The headless guide recommends scoped permission rules and warns that skipping all permission checks approves writes and command execution. | Documented fact | Evaluation uses scenario-specific authority manifests. Broad permission bypass is not the default. |
| [CLI plugins and skills](https://antigravity.google/docs/cli/plugins/) documents plugin manifests, skills, rules, agents, MCP, hooks, install, enable, disable, and uninstall commands. | Documented fact | A CLI plugin can package the behavior layer, but lifecycle and discovery still require conformance tests. |
| [General plugins](https://antigravity.google/docs/plugins/) describes plugins as namespaced bundles of skills, rules, MCP servers, and hooks. | Documented fact | Extension components are available mechanisms, not mandatory quotas. Each selected component needs distinct evidence. |
| [Skills](https://antigravity.google/docs/skills/) uses progressive disclosure: names and descriptions are discovered first, then relevant skill bodies are read. | Documented fact | Measure relevant body access and behavior, not whether all skill metadata appeared in context. Include negative activation trials. |
| General and CLI plugin documentation describe different locations and partially different component layouts. | Documented fact | V1 is CLI-only. Pin its manifest schema and paths, and run discovery-path conformance rather than assuming desktop parity. |
| [SDK overview](https://antigravity.google/docs/sdk/overview/) says SDK, CLI, and Antigravity 2.0 share the core harness while exposing programmatic tools, policies, hooks, and skills. | Documented fact | SDK is an evaluation adapter in v1, not evidence that CLI and desktop contracts are interchangeable. |

## Gemini Model Evidence

The behavioral implications of these model capabilities are synthesized in
[model-capability-implications.md](model-capability-implications.md).

| Evidence | Classification | Specification consequence |
|---|---|---|
| The [Gemini 3.7 Flash model card](https://deepmind.google/models/model-cards/gemini-3-7-flash/) describes configurable thinking, a 1M-token input window, 64K output, and distribution through Antigravity. | Documented fact | Treat Flash as a capable standalone engineering agent and measure behavior under pinned high and medium reasoning settings instead of assuming a simple executor role. |
| The model card reports 65.3% on DeepSWE v1.1, 85.8% on Terminal-bench 2.1, 14.9% on Terminal-bench 3.0, and 43.6% on FrontierCode 1.1. | Documented fact with provider-reported benchmark caveat | The model has substantial long-horizon and terminal capability but uneven headroom across harder suites. Use these only to shape scenario difficulty; this project still needs its own matched baseline and treatment evidence. |
| [Gemini 3.1 Pro model card](https://deepmind.google/models/model-cards/gemini-3-1-pro/) describes a 1M-token input window, 64K output, agentic performance, advanced coding, and long-context use. | Documented fact | Treat Pro as a capable standalone engineering model, not merely a planner or reviewer. |
| The model card reports 68.5% Terminal-Bench 2.0 under Terminus-2, 80.6% SWE-bench Verified, 54.2% SWE-bench Pro, 69.2% MCP Atlas, and 85.9% BrowseComp. | Documented fact with provider-reported benchmark caveat | Use these only to reject a weak-model stereotype. Do not compare them directly with this project's results or infer package lift. |
| [Gemini 3.1 Pro API documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-pro-preview) lists preview endpoints and an endpoint optimized for bash plus custom tools. | Documented fact | CLI and API identities differ. Record surface, requested model, authentication, and provider metadata instead of inventing equivalence. |
| [Google's prompt design strategies](https://ai.google.dev/gemini-api/docs/prompting-strategies) says direct, structured instructions are effective for Gemini 3 and provides a researcher-evaluated agentic system-instruction template. | Documented fact | Behavior instructions can materially improve agentic performance, but interventions must remain focused and empirically ablated. |
| The same guide distinguishes diagnosis, adaptability, persistence, risk assessment, ambiguity handling, precision, and completeness as steerable agent behaviors. | Documented fact | These become scenario families and rubric dimensions rather than one monolithic “better agent” score. |
| Current CLI documentation lists Gemini 3.7 Flash high and medium as selectable models. | Documented fact | Run the complete standalone suite for both 3.7 Flash and 3.1 Pro; do not cast Flash as a low-capability executor. |

## Public Methodology Repositories

Research snapshots are observations, not vendored dependencies.
License scope and proposed consumption modes are recorded separately in
[provenance-inventory.md](provenance-inventory.md). Behavioral ownership,
deduplication, and audience decisions are recorded in
[behavior-portfolio-curation.md](behavior-portfolio-curation.md).
The causal comparisons, negative controls, run record, and grading boundaries
are defined in
[skill-efficacy-evaluation-contract.md](skill-efficacy-evaluation-contract.md).

| Project | Public snapshot | Observed contribution |
|---|---|---|
| [obra/superpowers](https://github.com/obra/superpowers) | b36e0829c6d0140e93cfef2ca599b1b07d4a7797 | Progressive skill discovery, mandatory workflow routing, brainstorming before plans, isolated work, test-first execution, two-stage review, and verification before completion. |
| [prime-radiant-inc/iterative-development](https://github.com/prime-radiant-inc/iterative-development) | c05889aeb28f1f2c93f88232236e6ed906d32a6f | Proof obligations, behavioral scenarios, walking skeletons, repeated audited iterations, evidence corpora, and evidence-based termination. |
| [prime-radiant-inc/superpowers-evals](https://github.com/prime-radiant-inc/superpowers-evals) | ba3f22e6f205565d8ce1dc037ddee7d12eb179d5 | Existing Antigravity behavior scenarios, transcript capture, baseline taxonomy, and concrete failure cases such as overtriggering and unnecessary reviewer fan-out. |
| [prime-radiant-inc/smevals](https://github.com/prime-radiant-inc/smevals) | 0c28dc6298eb0e6c3b47e296e82a6972a01d76d0 | Evaluation orchestration research inputs. Adoption requires focused review during planning. |
| [prime-radiant-inc/stockyard](https://github.com/prime-radiant-inc/stockyard) | da59a23d1a5122b4d9ab721638b9840d78dd942b | Disposable task-environment direction and a reminder that remote inference remains outside hermeticity. |
| [prime-radiant-inc/serf](https://github.com/prime-radiant-inc/serf) | 37228494f8850bb1ffd33476ffd31b47f2b495bc | Research input for agent execution. No v1 dependency decision has been made. |
| [prime-radiant-inc/greenfield](https://github.com/prime-radiant-inc/greenfield) | 6e6d4b425fe9082d469493d64a5b8e12b15dc9da | Research input for task construction. Greenfield product behavior remains out of v1 scope. |
| [selamy-labs/agent-skills](https://github.com/selamy-labs/agent-skills) | 22ac23247b99aee2235478cd9bea5f4e6fee1848 | Public generic skills, upstream composition policy, and a graduation target for stable portable methods. The local checkout contains unrelated uncommitted work and is not modified by this project. |

## Distilled Design Hypotheses

These are inferences to test, not accepted facts:

1. A small Model Decision rule may reinforce authority, evidence, and honest
   completion on applicable engineering work, but it is selectable only if live
   evidence proves its body remains unloaded on clearly non-applicable tasks.
2. Focused skills can improve ambiguity disposition, root-cause diagnosis,
   incremental implementation, verification, and adversarial repair when their
   descriptions trigger precisely.
3. Hooks can provide deterministic lifecycle checks and evidence capture, but
   must not become a hidden grader or encode judgment-heavy policy.
4. A fresh custom review agent can improve defect detection if it receives the
   requirements and real artifact but not the implementer's conclusions.
5. Upstream methods can be composed without copying their bodies. The approved
   hybrid strategy keeps verified native packages upstream and independently
   authors only Antigravity-specific behavior for uncovered responsibilities.
6. The same common package can improve both target models, while model-specific
   profiles should exist only if ablation shows they are necessary.
7. A controlled task environment plus sealed grading can support causal claims
   about the package even though remote inference is not hermetic.

## Specification Traceability

| Evidence theme | Primary requirements |
|---|---|
| CLI model pinning, structured output, and soft denial | FR-011, FR-023–FR-025, FR-033–FR-035, SC-009 |
| Progressive disclosure and focused skills | FR-004–FR-005, FR-009, SC-007, SC-013 |
| Plugin packaging and lifecycle | FR-001–FR-008, SC-008 |
| Gemini models as capable standalone agents | FR-021–FR-026, FR-050, SC-001–SC-002 |
| Research-evaluated agentic instruction structure | FR-027–FR-031, SC-001, SC-013 |
| Superpowers workflow evidence | FR-009–FR-020, FR-028, FR-044 |
| Iterative-development proof obligations | FR-012–FR-017, FR-027–FR-044 |
| Controlled but non-hermetic evaluation | FR-038–FR-043, FR-048–FR-049 |
| Public composition and attribution | FR-003, FR-045–FR-048, SC-010 |

## Refresh Triggers

Refresh this register before planning and again before opening the sealed suite
when any of the following changes:

- Antigravity CLI, plugin schema, documented paths, or headless event schema;
- the live output of the CLI model list;
- target model availability or reasoning settings;
- an upstream source digest, interface, or license;
- evaluator authority, container boundary, or evidence schema;
- a public capability claim or numerical benchmark used in release materials.
