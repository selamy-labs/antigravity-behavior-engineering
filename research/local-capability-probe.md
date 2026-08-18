# Local Antigravity Capability Probe

**Observed**: 2026-08-18

**Purpose**: Record non-release local observations and explain why they cannot
produce valid evidence for the v1 CLI and target-model requirements.

## Environment

- Antigravity CLI executable: resolved by `command -v agy`; absolute local path
  intentionally omitted from the public record
- Historical local CLI observation recorded during research: below the current
  qualification floor
- Finalization-session local `agy --version` observation: 1.1.14
- Current public documentation observed during research: CLI 1.1.14
- No plugin or configuration change was requested by this probe.
- Listing models required the CLI to access its normal profile and localhost
  control socket; the first sandboxed attempt failed before listing models.

## Live Model Catalog

The local CLI reported:

- Gemini 3.6 Flash: high, medium, low
- Gemini 3.5 Flash: high, medium, low
- Gemini 3.1 Pro: high, low
- Claude Sonnet 4.6
- Claude Opus 4.6
- GPT-OSS 120B

Gemini 3.7 Flash was not listed.

## Plugin Command Contract

The local CLI exposes:

- plugin list;
- plugin import;
- plugin install;
- plugin uninstall;
- plugin enable and disable;
- plugin validate;
- plugin marketplace linking.

The top-level command also exposes model and effort pinning, accept-edits and
plan modes, JSON and streaming-JSON input and output, structured output schemas,
conversation resume, sandboxing, slash-command disablement, timeouts, and an
explicit log-file path. These are candidate controls for deterministic capture;
their exact semantics still require qualification on the release CLI.

Validating the pinned Superpowers repository root with the local CLI failed:

> missing plugin.json

The pinned upstream repository instead contains a Claude plugin manifest and an
Antigravity marketplace descriptor whose source points at the repository root.
Its README documents direct Antigravity installation from the repository URL.
This probe did not perform that state-changing install.

## Interpretation

1. No local observation in this note is qualification evidence for the required
   dual-model evaluation because it did not run inside the disposable worker
   boundary with the authorized hashed CLI artifact.
2. Historical local validation failures do not establish incompatibility with
   the current remote-install path.
3. A model name in documentation is not enough. Every evaluation worker must
   pass a live model and headless-output preflight before receiving a task.
4. A README install command is not enough. Every upstream plugin or adapter must
   pass install, discovery, activation, disablement, and removal conformance on
   the exact pinned CLI.
5. The work Antigravity environment described by the user is the likely target
   evaluation surface, but its version and live model catalog have not yet been
   captured.

## Candidate CLI Floor

Public release notes identify controls and fixes that the evaluation contract
depends on:

- post-floor research identified stable model slugs and explicit effort
  selection;
- post-floor research identified structured JSON, streaming events, schemas, and detailed tool
  and subagent evidence;
- post-floor research identified headless skill expansion and corrected stop
  and post-tool hooks;
- post-floor research identified stop hooks reachable before built-in
  termination and corrected model and effort flag application;
- post-floor research identified machine-readable model and agent inventories
  and corrected headless execution-mode selection;
- 1.1.14 added one explicit custom-agent control for inheriting skills, rules,
  plugins, subagents, and MCP servers.

This makes 1.1.14 the candidate qualification floor, not yet the frozen release
minimum. Qualification still requires live conformance probes; a version number
alone does not prove the behavior.

## Qualification Gate

An environment may enter baseline or treatment evaluation only when all of the
following evidence is recorded:

- exact authorized CLI executable digest and version, with version at or above
  the `1.1.14` floor;
- exact output of the live model catalog containing the requested model slug;
- a fail-closed unknown-model probe;
- successful JSON and streaming-JSON schema probes;
- recorded execution mode, skill-expansion setting, timeout, and log path;
- explicit authority and permission manifest;
- successful clean plugin validation or installation in disposable state;
- discovery and activation probe for every selected component;
- no unlisted global plugin, skill, rule, hook, MCP server, conversation, or
  permission state;
- task image, fixture, grader, and starting-state digests.

## Current Disposition

- Specification and public research can continue locally.
- Target behavioral baselines cannot be claimed from this environment.
- No CLI upgrade or plugin installation should occur until the specification and
  plan are approved and an isolated qualification method is defined.
