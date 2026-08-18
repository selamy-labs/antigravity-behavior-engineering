# Antigravity Extension Contract Register

**Captured**: 2026-08-18

**Target documentation**: Antigravity CLI 1.1.14

**Status**: First-party contract research; every undocumented behavior remains a
conformance obligation rather than an assumption

## Plugin Boundary

The [CLI plugin documentation][plugins] defines a staged plugin with:

- required `plugin.json`;
- optional `hooks.json` and `mcp_config.json`;
- optional `skills/`, `agents/`, and `rules/` directories;
- install, list, enable, disable, and uninstall lifecycle commands.

The documented manifest example includes:

- `$schema`;
- required `name`;
- optional `description`.

However, the displayed full schema declares only `name` and `description` as
instance properties and sets `additionalProperties` to false. The documentation
is therefore internally inconsistent about `$schema`. It has no documented
version, dependency, source digest, license, or component inventory field.

A direct GET of the documented schema URL returned HTTP 404 on 2026-08-18. The
remote schema cannot currently serve as release-validation evidence.

Consequences:

1. The project must not invent extra fields in `plugin.json`; even `$schema`
   acceptance requires a qualified-CLI validation test.
2. Version identity, source locks, upstream dependencies, component inventory,
   and provenance need a separately validated package-owned record.
3. Installation must verify dependencies as independent plugins rather than
   staging their skill bodies inside this bundle.
4. The release must prove that companion metadata and scripts survive remote and
   local installation on the pinned CLI.
5. `agy plugin list` cannot be assumed to expose enough version evidence until a
   live structured-output probe proves it.
6. Release validation needs a repository-owned contract test plus the pinned
   CLI's validator; it must not depend on the currently unreachable schema URL.

## Skill Contract

The [skills documentation][skills] defines skills as folders containing
`SKILL.md` plus optional scripts, examples, and resources. It documents global
skills under `~/.gemini/config/skills/`, while the CLI plugin page separately
describes `~/.gemini/antigravity-cli/skills/`. That path difference must be
resolved by CLI 1.1.14 discovery probes rather than guessed.

Documented frontmatter:

- `description` is required and is the text used for activation decisions;
- `name` is optional, defaults to the folder name, and should be lowercase with
  hyphens.

Activation uses progressive disclosure:

1. all names and descriptions are visible at conversation start;
2. the model chooses a relevant skill and reads its body;
3. the model executes the instructions.

Consequences:

- A description changes every run even when its body is never loaded, so
  description-only and body-access effects require separate trace probes.
- Each skill needs positive activation, negative activation, collision, and
  manual invocation tests.
- Names must be distinct from upstream skills and other discovered roots.
- Helper scripts should expose stable command interfaces; the skill should use
  them as black boxes rather than spend model context reading their source.
- The runtime plugin should contain only the three original worker skills from
  the portfolio curation record.

## Rule Contract

The [rules documentation][rules] defines a rule as Markdown with manual,
always-on, model-decided, or glob activation. A rule file is limited to 12,000
characters. Workspace rules normally live in `.agents/rules`; plugin rules live
under the plugin's `rules/` directory.

Consequences:

- The behavioral kernel must stay far below the platform limit because every
  always-present token taxes each turn.
- The runtime treatment needs a deterministic probe that shows whether a plugin
  rule is loaded, its activation mode, and its precedence relative to global and
  workspace rules.
- The rule must route to skills without restating their procedures.
- A rule-body ablation must measure context cost, trivial-task ceremony, and
  behavior lift.

## Custom Agent Contract

The [subagent documentation][subagents] defines plugin-discovered Markdown
agents with a YAML system-prompt contract. Relevant documented fields include:

- required `name` and `description`;
- exact `tools` allowlist;
- `mainAgent` and `subagent` selection flags;
- model tier `inherit`, `flash`, or `pro`;
- command policy `off`, `auto`, `eager`, or `sandbox`;
- optional `skills`, `plugins`, and MCP configuration.

Subagents start with clean conversation context, can inherit, branch, or share a
workspace, inherit parent safety scopes, and bubble permission requests. The
documentation warns that an invalid tool name may hang the process. The 1.1.14
changelog also introduces a unified `inheritCustomizations` control whose exact
Markdown schema needs live confirmation.

Consequences for both falsifiers:

- set `mainAgent: false`, `subagent: true`, and `model: inherit` for the primary
  standalone condition;
- use read-only tools and sandboxed command execution unless a focused test
  proves broader authority is needed;
- validate every tool name against `agy agents` and a no-op invocation before an
  evaluation task;
- explicitly choose customization inheritance so a reviewer receives only its
  approved review method and cannot silently lose or duplicate dependencies;
- use conclusion-free inputs and record the agent definition digest;
- test permission bubbling, idle, kill, transcript, and workspace cleanup paths;
- do not depend on the Ultra-only teamwork preview.

## Hook Contract

The [hook documentation][hooks] defines named command handlers in `hooks.json`.
Handlers receive camelCase JSON on stdin, emit JSON on stdout, and default to a
30-second timeout. Common metadata includes conversation ID, workspace paths,
transcript path, artifact directory, and model name.

Relevant lifecycle contracts:

- `PostToolUse` observes the completed tool, arguments, step, and error and
  returns `{}`;
- `PostInvocation` can observe an invocation, inject steps, force continuation,
  or terminate;
- `Stop` observes execution number, termination reason, error, and `fullyIdle`,
  and can return `continue` with a system reason;
- `PreToolUse` can allow, deny, ask, force an ask, or deny unless a prior grant
  exists, with optional permission overrides.

Consequences:

- `evidence-observer` can use observation events but cannot infer correctness
  from tool names or successful process exit.
- `bounded-completion-gate` belongs at `Stop`, may continue only a fixed number
  of times, and must distinguish active work, product incompleteness, model stop,
  and infrastructure error.
- Pre-invocation reminders remain deferred because injected system content
  changes every treatment turn and can amplify context cost.
- Evaluator authority policy is external to the ordinary runtime plugin.
- Hook commands, working directory, relative path resolution, timeout behavior,
  malformed JSON behavior, ordering, disablement, and failure policy all require
  live conformance tests.

## Headless Evidence Contract

The [headless documentation][headless] supplies JSON and NDJSON output with
terminal status, errors, duration, token usage, tool steps, subagent metadata,
and an init record describing tools, model override, agent, and permission mode.

It also documents two traps:

- an unknown pinned model fails non-zero;
- a tool needing unavailable interaction can be soft-denied while the overall
  run continues and exits zero.

Consequences:

- model preflight, requested slug, effort, init metadata, stderr, tool errors,
  terminal status, artifact state, and hidden checks must all participate in run
  classification;
- process exit alone never proves task success;
- the exact NDJSON event vocabulary and token fields must be pinned by fixture
  tests on the release CLI.

## Unsupported Assumptions

Planning and implementation must not assume any of the following until a live
probe proves it:

- native plugin dependency resolution;
- a plugin manifest version field;
- source-SHA pinning syntax for remote `agy plugin install`;
- deterministic precedence for same-named skills, agents, rules, or hooks;
- plugin-rule activation semantics matching workspace-rule semantics;
- hook script working directory or relative path behavior;
- atomic upgrade or rollback;
- disablement immediately removing all hook and prompt contributions;
- `plugin list` exposing source or component digests;
- a custom agent inheriting exactly the intended parent customizations;
- identical CLI and desktop extension behavior.

Each becomes either an environment qualification test, a lifecycle test, or an
explicitly documented limitation.

[plugins]: https://antigravity.google/docs/cli/plugins/
[skills]: https://antigravity.google/docs/skills/
[rules]: https://antigravity.google/docs/ide-rules
[subagents]: https://antigravity.google/docs/subagents/
[hooks]: https://antigravity.google/docs/hooks/
[headless]: https://antigravity.google/docs/cli/headless/
