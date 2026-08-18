# Fresh-Clone Bootstrap and Validation

Commands in this document are handoff commands, not product commands. Planned
commands under `specs/.../quickstart.md` do not exist until their owning tasks
implement them.

## Human-Supplied Inputs

Set these outside the repository:

```bash
export ABE_HANDOFF_REPOSITORY_URL='https://github.com/selamy-labs/antigravity-behavior-engineering.git'
export RALPH_STATE_DIR='/durable/private/path/antigravity-behavior-engineering'
export RALPH_TASK_SET_APPROVAL_RECORD='/durable/private/path/task-set-approval.json'
```

`RALPH_STATE_DIR` must already be an authorized, durable, non-public directory.
`RALPH_TASK_SET_APPROVAL_RECORD` must name the external human approval record
created only after the owner approval sentence is given. Do not commit the
state-directory or approval-record values.

Git credentials, commit identity, model authentication, the authorized CLI,
protected evaluations, and merge authority are also human/environment supplied.

## Required Handoff Tools

The handoff validator requires Git, Bash, `awk`, `sed`, `rg`, `shasum`, and Spec
Kit 0.16.0. Confirm rather than infer:

```bash
git --version
bash --version
rg --version
specify --version
specify check
git config --get user.name
git config --get user.email
```

An absent Git identity is a human-input stop. An Antigravity CLI is not needed
for T001, but the committed plan sets 1.1.14 as the initial qualification floor;
T013 validates the exact authorized artifact and model catalog.

## Clone and Validate

After the repository target exists:

```bash
git clone "$ABE_HANDOFF_REPOSITORY_URL" antigravity-behavior-engineering
cd antigravity-behavior-engineering
git checkout main
./.specify/scripts/bash/check-prerequisites.sh \
  --json --require-tasks --include-tasks
./handoff/validate-handoff.sh
```

Before publication, transfer the local repository through an authorized channel,
then run the same two validation commands at its root. Do not substitute an
untracked directory copy for the committed repository during implementation.

## Spec Kit Initialization Contract

A fresh empty repository can reproduce the scaffold with:

```bash
specify init --here --integration agy --script sh --force
```

An ordinary clone must not run that command because `.specify/` and `.agents/`
are already committed at version 0.16.0. Reinitialization could overwrite
reviewed files. Validate the clone instead:

```bash
test "$(specify --version)" = 'specify 0.16.0'
test "$(git status --short)" = ''
./.specify/scripts/bash/check-prerequisites.sh --json \
  --require-tasks --include-tasks
```

If the installed Spec Kit differs, install 0.16.0 using the environment's
approved package channel or stop for the operator; the public handoff does not
dictate private package-distribution policy.

## Task-Set Approval Gate

This handoff stops here until the project owner records this exact sentence in
an approval record outside Git:

```text
I approve the final reviewed 46-task set in specs/001-improve-antigravity-behavior/tasks.md and authorize Ralph to begin T001 only under AGENTS.md and handoff/ralph-execution-contract.md.
```

The approval record must bind the current `git rev-parse HEAD` value and the
SHA-256 of `specs/001-improve-antigravity-behavior/tasks.md`. Do not create a
branch or run T001 before that record exists.

## Initialize Ralph State

```bash
mkdir -p "$RALPH_STATE_DIR"
python3 handoff/init-ralph-state.py \
  --state-dir "$RALPH_STATE_DIR" \
  --task-set-approval-record "$RALPH_TASK_SET_APPROVAL_RECORD"
```

The initializer refuses to overwrite state, requires a clean Git checkout,
records `git rev-parse HEAD`, computes the task-set SHA-256, verifies the
external approval record, creates all 46 `not_started` records, writes
atomically, and prints the state path. Verify its anchors with:

```bash
git rev-parse HEAD
shasum -a 256 specs/001-improve-antigravity-behavior/tasks.md
```

Validate `state.json` against `handoff/ralph-state.schema.json` using a
standards-compliant JSON Schema 2020-12 validator approved in the downstream
environment. No validator dependency is added before T001; absence of one is an
environment bootstrap stop, not permission to skip validation.

## Begin After Approval

Read `AGENTS.md` and `handoff/ralph-execution-contract.md`, then create only:

```text
branch: ralph/T001-bootstrap-the-reproducible-maintainer-workspace
PR title: [T001] Bootstrap the reproducible maintainer workspace
```

T001's first command is:

```bash
node --test tests/contract/workspace.test.mjs
```

It must fail for the reason stated by T001 before implementation begins.
