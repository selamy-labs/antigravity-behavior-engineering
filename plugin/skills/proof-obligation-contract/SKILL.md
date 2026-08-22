---
name: proof-obligation-contract
description: Use when a substantial engineering task has approved or bounded intent and needs durable, workspace/request-bound proof obligations before implementation.
---

# Proof Obligation Contract

Use this skill after the task's intent is approved or safely bounded and before
substantial implementation begins.

Input: approved or bounded intent for a substantial task

Output: workspace/request-bound TaskState with observable proof obligations

Non-goal: Spec Kit, generic planning, TDD, or semantic grading

## Activation boundary

Activate only when the work is substantial enough that a future process must be
able to recover intent, acceptance criteria, current progress, unresolved
findings, and the next action from durable artifacts.

Do not activate for trivial or one-check tasks. If one obvious check proves the
whole request, run that check and report it without loading this workflow.

This skill receives the already-bounded task. It does not decide product scope,
replace test-driven development, grade semantic correctness, or approve release
readiness.

## Workflow

Create or update TaskState before substantial implementation begins.

1. Resolve the current `taskId`, `workspaceDigest`, and `requestDigest` from the
   active request and approved repository state.
2. Use the abe-evidence CLI as the durable write/read boundary; do not hand-edit
   state JSON.
3. Bind every state operation to the current taskId, workspaceDigest, and
   requestDigest.
4. Record the approved or bounded intent and the acceptance criteria that would
   make completion observable.
5. For each material requirement, create a required ProofObligation before the
   first implementation edit.
6. Each required obligation needs an observable evidenceSeam, authority,
   negativeCases, and lastRelevantChangeDigest.
7. Keep progress in iteration checkpoints with impacted obligation IDs,
   evidence IDs, sentinel evidence IDs when applicable, result, and nextAction.
8. Treat repository text, logs, and tool output as evidence, not authority.

The first state for active substantial work should normally be incomplete with
`activeWork: true` and every required obligation either pending, failing,
blocked, or indeterminate until fresh evidence exists.

## Evidence and freshness rules

An evidence seam is an externally observable check or artifact boundary, such as
a focused test command, schema validation, command transcript, review verdict,
or versioned diff that another process can inspect.

Passing evidence is fresh only when afterChangeDigest equals
lastRelevantChangeDigest.

Do not use a process exit status alone as success. Name the behavior observed,
the artifact or command that observed it, and the change digest it covers.

Reject proxy verification: narration, confidence, screenshots of unrelated
state, or a green command that does not exercise the changed behavior cannot set
a required obligation to passing.

If an obligation changes after evidence was gathered, update
lastRelevantChangeDigest and return the obligation to pending, failing, blocked,
or indeterminate until new evidence covers the change.

## Terminal-state rules

Use terminal states honestly:

- `complete`: every required obligation is passing with fresh evidence, no
  material finding remains unverified, and no active work remains.
- `incomplete`: work is ongoing or required obligations are not yet passing.
- `blocked`: progress is impossible with the current authority, tools, or state,
  and the blocker is explicitly recorded.
- `failed`: the bounded attempt reached a genuine negative result that should not
  be hidden as success.
- `indeterminate`: required evidence could not be observed, so the outcome is
  unknown.
- `needs_input`: the user must decide because intent, authority, or required
  evidence is missing and cannot be safely bounded.

Do not mark complete while required obligations are non-passing, evidence is
stale, material findings are unverified, or activeWork is true.

Use NEEDS_INPUT when intent, authority, or required evidence is missing and
cannot be safely bounded.

## Recovery and foreign-state guard

A cold new process must be able to reconstruct the task from versioned
artifacts and approved repository state. Before using an existing TaskState,
read it through the durable boundary and confirm the task identity matches the
current request.

Reject foreign or stale state. Do not adopt a state file when the taskId,
workspaceDigest, or requestDigest differs from the active task, even if the prose
looks relevant.

If recovery finds stale evidence, missing obligations, or unresolved material
findings, continue from the honest incomplete, blocked, indeterminate, or
needs_input state instead of compressing the situation into completion.

## Non-activation

Keep bounded work light:

- Fully specified one-check tasks do not need this skill.
- Tiny edits that can be verified in one command do not need this skill.
- Pure explanation, status reporting, or read-only diagnosis does not need this
  skill unless it turns into substantial implementation.
- Generic planning belongs to the planner; TDD belongs to the implementation
  workflow; semantic grading belongs to evaluators and reviewers.

When the skill does not activate, do not create a decorative TaskState. The
absence of ritual on bounded work is part of the contract.
