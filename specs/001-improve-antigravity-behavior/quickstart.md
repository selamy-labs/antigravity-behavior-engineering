# Quickstart: Improve Antigravity Engineering Behavior

**Status**: Proposed operator workflow after implementation; commands are plan
contracts, not evidence that the software exists today.

## Prerequisites

- Node.js 22 or later within the release-tested range;
- Corepack and the repository-pinned pnpm version;
- Python 3.12 and uv for maintainer evaluation commands;
- Docker or another OCI-compatible engine for disposable workers;
- an authorized Antigravity CLI artifact at or above the frozen release floor;
- access to Gemini 3.7 Flash and Gemini 3.1 Pro for target evaluation.

The repository never contains Antigravity credentials, private task material,
or the Antigravity binary.

## Bootstrap Maintainer Tooling

From the repository root:

```bash
corepack enable
pnpm install --frozen-lockfile
uv sync --frozen --project evaluator
pnpm verify
```

`pnpm verify` is the single local gate and runs formatting checks, Markdown and
JSON validation, Node tests, Python tests, provenance checks, public-safety
scans, contract consistency, and fixture determinism. It performs no model call
and changes no Antigravity profile.

## Build a Disposable Worker

Build the public worker without the authorized CLI. The controller mounts the
CLI read-only at runtime and validates its digest; do not copy it into the image
or public source tree:

```bash
docker buildx build \
  --tag antigravity-behavior-worker:local \
  --load \
  environments/worker
```

The build records the toolchain and image digests. Credentials and the approved
CLI path are injected only when a qualification or behavioral run starts.

## Qualify an Environment

```bash
uv run --project evaluator abe-eval qualify \
  --worker-image antigravity-behavior-worker:local \
  --cli-artifact "$ABE_AUTHORIZED_CLI_PATH" \
  --models gemini-3.7-flash-high \
  --models gemini-3.1-pro-high \
  --output evidence/raw/qualification/local
```

Qualification fails closed unless the exact model catalog, unknown-model probe,
structured and streaming output, plugin lifecycle, hook resolution, agent tool
list, permission behavior, clean state, and evidence capture all pass.

## Validate the Plugin Without Installing It Globally

```bash
pnpm plugin:validate
pnpm plugin:test
pnpm lifecycle:test -- --fixture clean-profile
pnpm lifecycle:test -- --fixture customized-profile
```

These commands use disposable fixture profiles. They do not touch the operator's
normal Antigravity state.

## Run Fake Evaluator Conformance

```bash
uv run --project evaluator pytest \
  evaluator/tests/test_attempt_accounting.py \
  evaluator/tests/test_valid_start_classification.py \
  evaluator/tests/test_immutable_regrading.py
```

The fake runner covers pre-start failure, post-start timeout, soft denial,
malformed streams, ordinary task failure, and re-grading. This gate must pass
before any paid or quota-consuming model run.

## Capture a Formative Baseline

```bash
uv run --project evaluator abe-eval run-matrix \
  --matrix evals/formative/framing-wrong-component/matrix.json \
  --condition bare \
  --repetitions 3 \
  --qualification evidence/raw/qualification/local/qualification.json
```

The controller schedules every attempt before execution, randomizes within the
declared block, and preserves failures. Three repetitions are pilot evidence,
not release evidence.

## Run a Focused Component Ablation

Only after a matched baseline underperforms and the corresponding treatment is
implemented:

```bash
uv run --project evaluator abe-eval run-matrix \
  --matrix evals/formative/framing-wrong-component/matrix.json \
  --condition incumbent-minus-evidence-first-framing \
  --condition incumbent-plus-evidence-first-framing \
  --repetitions 3 \
  --qualification evidence/raw/qualification/local/qualification.json
```

Positive and negative applicability scenarios live in the same frozen matrix.

## Generate a Blinded Report

```bash
uv run --project evaluator abe-eval grade \
  --analysis evals/formative/framing-wrong-component/analysis.json \
  --raw-root evidence/raw

uv run --project evaluator abe-eval report \
  --analysis evals/formative/framing-wrong-component/analysis.json \
  --raw-root evidence/raw \
  --output evidence/publishable/reports/framing-pilot
```

The report separates intention-to-treat from valid-run analysis and keeps model
results separate.

## Manual Install Lifecycle After Qualification

Use a disposable profile or approved test account:

```bash
agy plugin validate plugin
agy plugin install plugin
agy plugin list
node packages/plugin-tooling/bin/inspect-install.mjs \
  --expected plugin/behavior-lock.json
agy plugin disable antigravity-behavior-engineering
agy plugin enable antigravity-behavior-engineering
agy plugin uninstall antigravity-behavior-engineering
node packages/plugin-tooling/bin/compare-profile.mjs \
  --before evidence/profile-before.json \
  --after evidence/profile-after.json
```

No command may point at the operator's ordinary profile unless they explicitly
authorize that state change.

## Sealed Confirmation

Sealed tasks are opened only through a release-candidate command after the
candidate digest, analysis, sample size, stopping rule, and approval record are
frozen:

```bash
uv run --project evaluator abe-eval confirm \
  --mode prepare \
  --release-lock docs/release/candidate-lock.json \
  --approval docs/release/candidate-freeze-approval.json \
  --sealed-bundle "$ABE_SEALED_BUNDLE_PATH" \
  --qualification evidence/raw/qualification/release/qualification.json \
  --release-root evidence/raw/releases \
  --schedule-out prepared-schedule.json \
  --journal-out opening-journal.json
uv run --project evaluator abe-eval confirm \
  --mode resume \
  --release-lock docs/release/candidate-lock.json \
  --release-root evidence/raw/releases \
  --journal opening-journal.json
```

The command validates the lock, derives the canonical candidate digest, and
uses `evidence/raw/releases/<candidate-digest>/`; schedule/journal arguments are
safe basenames, not caller-supplied candidate paths.

If a confirmation fails and the treatment changes, the opened bundle becomes
regression data and cannot be reused as unseen evidence.
