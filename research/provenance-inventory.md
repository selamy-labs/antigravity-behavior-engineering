# Upstream Provenance Inventory

**Captured**: 2026-08-18

**Status**: Research-stage inventory; human legal and provenance approval is
still required before distribution.

## Policy

- Consume an upstream package from its own public source when it already supports
  Antigravity.
- Do not copy upstream skill bodies merely to simplify installation.
- Derive original Antigravity-specific behavior from public ideas and observed
  failure modes; preserve attribution when an adaptation is substantial.
- Pin and verify the exact source used for evaluation.
- Treat a missing or ambiguous repository-wide license as no redistribution
  permission until the owner clarifies it.
- Keep license text, notices, source digests, modifications, and install state in
  the release evidence.

## Inventory

### obra/superpowers

- Source: https://github.com/obra/superpowers
- Research snapshot: b36e0829c6d0140e93cfef2ca599b1b07d4a7797
- Observed version: 6.3.0
- License: MIT, copyright Jesse Vincent.
- Native support: The upstream README documents direct Antigravity installation
  with agy plugin install from the upstream repository.
- Local conformance caveat: a historical local CLI plugin validation of the
  repository root failed because no root plugin.json was present. The repository
  contains an Antigravity marketplace descriptor. Remote-install compatibility
  must be proven on the qualified CLI rather than inferred from local ambient
  state.
- Distribution posture: Prefer a declared, pinned upstream dependency installed
  from its own source. Do not republish its skills in this repository.
- Verification obligation: Record the installed upstream digest and confirm its
  session-start hook, skills, and lifecycle work on the pinned CLI version.

### prime-radiant-inc/iterative-development

- Source: https://github.com/prime-radiant-inc/iterative-development
- Research snapshot: c05889aeb28f1f2c93f88232236e6ed906d32a6f
- License: Apache-2.0.
- Native support: The README documents a Claude Code marketplace package and a
  conceptual dependency on Superpowers, not an Antigravity package.
- Distribution posture: Use it as a methodology and research source. Prefer
  original Antigravity-native modules over copying its skill bodies. Any actual
  adaptation must retain the license, carry modification notices, and satisfy
  Apache-2.0 attribution requirements.
- Verification obligation: Demonstrate independently that any distilled
  iteration behavior changes Antigravity outcomes rather than assuming the
  Claude Code workflow transfers.

### selamy-labs/agent-skills

- Source: https://github.com/selamy-labs/agent-skills
- Research snapshot: 22ac23247b99aee2235478cd9bea5f4e6fee1848
- License: MIT, copyright Selamy Labs.
- Local-state warning: The available local checkout contains unrelated
  uncommitted work and must not be modified or treated as identical to the
  public snapshot.
- Distribution posture: Consume stable public skills from upstream and consider
  graduating newly proven portable skills there later. Keep Antigravity-specific
  packaging in this incubator.
- Verification obligation: Record each consumed skill digest and avoid depending
  on unpublished local changes.

### prime-radiant-inc/smevals

- Source: https://github.com/prime-radiant-inc/smevals
- Research snapshot: 0c28dc6298eb0e6c3b47e296e82a6972a01d76d0
- Observed version: 0.2.0
- License: MIT, copyright Prime Radiant, Inc.
- Distribution posture: Candidate evaluation dependency, subject to planning,
  focused interface review, and version pinning.
- Verification obligation: Prove that any adopted evaluator covers the required
  Antigravity evidence and classification schema.

### prime-radiant-inc/superpowers-evals

- Source: https://github.com/prime-radiant-inc/superpowers-evals
- Research snapshot: ba3f22e6f205565d8ce1dc037ddee7d12eb179d5
- License: No repository-wide license file found in the captured snapshot.
- Distribution posture: Research reference only. Do not copy, modify, or
  redistribute scenarios, code, documentation, or fixtures without explicit
  permission or a later verified license.
- Permitted project use: Record high-level public observations and create
  independently authored scenarios that test the same general failure classes.

### prime-radiant-inc/stockyard

- Source: https://github.com/prime-radiant-inc/stockyard
- Research snapshot: da59a23d1a5122b4d9ab721638b9840d78dd942b
- License: No repository-wide license file found in the captured snapshot.
- Distribution posture: Research reference only. Do not copy or redistribute.
- Permitted project use: Independently design disposable task-environment
  boundaries informed by public industry practice.

### prime-radiant-inc/serf

- Source: https://github.com/prime-radiant-inc/serf
- Research snapshot: 37228494f8850bb1ffd33476ffd31b47f2b495bc
- License: A file named LICENSE-kilroy contains MIT terms for Dan Shapiro. A
  repository-wide license was not established by this audit.
- Distribution posture: No v1 dependency or redistribution. Require explicit
  scope clarification before any future use.

### prime-radiant-inc/greenfield

- Source: https://github.com/prime-radiant-inc/greenfield
- Research snapshot: 6e6d4b425fe9082d469493d64a5b8e12b15dc9da
- License: Apache-2.0.
- Distribution posture: Research reference for later greenfield scenarios.
  Greenfield behavior is outside v1 product scope.

## Approved Composition Shape

The evidence currently favors a hybrid that still presents one documented user
flow:

1. Install this project's original Antigravity-native plugin.
2. Resolve Superpowers from its own repository as a pinned external plugin.
3. Consume selected public Selamy skills from their upstream source rather than
   copying them.
4. Implement original Antigravity-native iteration and adversarial-review
   modules informed by Prime Radiant's licensed methodology.
5. Keep unlicensed evaluation repositories outside the distributed dependency
   graph.
6. Emit a lock and provenance report containing every source digest and license.

The user approved this hybrid as a specification clarification on 2026-08-18.

## Release Gate

Before release, a human reviewer must confirm:

- the license applies to the exact files and snapshot consumed;
- the install or adaptation mode matches the license obligations;
- all required notices and modification markings are present;
- no unlicensed or confidential content entered the artifact;
- removal deletes package-managed dependency state without deleting user-owned
  upstream installations;
- published claims distinguish upstream behavior from this project's measured
  incremental contribution.
