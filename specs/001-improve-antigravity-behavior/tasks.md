# Antigravity Behavior Engineering Implementation Tasks

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this task set one task at a time.
> Every task uses test-first steps and receives a fresh review before its
> checkpoint is accepted.

**Status**: Draft task set — awaiting separate project-owner approval

**Approval record**: The project owner approved the implementation plan, which
authorized drafting and adversarially reviewing this task set. That approval did
not approve these final task bytes or authorize T001. Implementation remains
prohibited until the project owner separately approves the reviewed task set.

**Goal**: Build, package, and empirically validate a public Antigravity CLI
behavior-engineering plugin that measurably improves Gemini 3.7 Flash and Gemini
3.1 Pro while preserving completion honesty, public provenance, user state, and
resource proportionality.

**Architecture**: A dependency-free Node.js runtime plugin is physically
separate from a protected Python evaluation controller. The controller schedules
immutable attempts into disposable OCI workers, captures raw evidence, and
grades artifacts outside the agent boundary. Runtime behavior is introduced
only after a matched baseline gap exists and is retained only after focused and
integrated ablation.

**Tech Stack**: Node.js `>=22 <25`, ECMAScript modules, built-in `node:test`,
pnpm with a committed lockfile, Python `>=3.12 <3.14`, uv with a committed
lockfile, pytest, JSON/JSON Schema/NDJSON, OCI workers, Git, and SHA-256 content
addressing. SMEvals 0.2.0 at
`0c28dc6298eb0e6c3b47e296e82a6972a01d76d0` is optional behind T011's
losslessness decision.

## Approval Chain and Global Constraints

- The specification and implementation plan are approved. This task set is not.
- No environment or agent may begin T001 until the project owner explicitly
  approves the final adversarially reviewed task set.
- Candidate freeze and public release remain separate later human gates.
- Antigravity CLI is the only version-one release-gating product surface.
- Each target model runs the complete locked suite alone; results are never
  pooled across models.
- The runtime plugin has no npm dependency and no network access from hooks.
- Superpowers remains a pinned upstream dependency; its skill bodies are not
  copied into this repository.
- Prime Radiant and public Selamy material are methodology inputs only unless an
  independently licensed upstream package is explicitly locked.
- No confidential Google material, credentials, private task instances, hidden
  graders, or protected evidence may enter the public package or Git history.
- A process exit, agent declaration, deterministic grade, and blind judgment are
  separate evidence fields.
- Every task preserves unrelated work and forbids destructive or external-state
  actions without separate authority.

## Task Execution Contract

For every task below, the implementer MUST:

1. read only the named prerequisite artifacts and exact files;
2. write the named focused test first and run the listed command to observe the
   stated failure;
3. implement only the named interface and behavior;
4. rerun the focused command plus the named sentinel command;
5. obtain a fresh requirements review and quality review over the real diff,
   artifact, and verification output;
6. repair every accepted material finding and rerun fresh evidence;
7. record `docs/task-checkpoints/TNNN.json` against
   `handoff/task-checkpoint.schema.json` without claiming later gates have
   passed.

The checkpoint is a generated proof record required in every task PR; it does
not authorize an unnamed implementation file. Generated locks and evidence are
outputs, not substitutes for the named source and test files. A task that cannot
produce its stated failing test, passing test, and review evidence remains
incomplete.

### Normative read sets

The phrase “named prerequisite artifacts” is closed and deterministic. Every
task may read only its own task entry; `spec.md`, `plan.md`, `data-model.md`, and
`research.md`; files named in its **Files**, interface, command, and acceptance
sections; and files produced by the exact transitive closure of its declared
`Depends on` tasks. For a behavior task, that closure includes only the files
enumerated by the content-addressed current-incumbent PackageLock, never
untracked workspace context. In addition, the following phase-specific contract
reads are mandatory before the first edit:

| Tasks | Mandatory contract reads |
|---|---|
| T001–T005 | `contracts/README.md`, `contracts/evidence-store.md`, `contracts/reviewer.md`, `contracts/hooks.md` |
| T006–T011 | `contracts/runner.md`, `contracts/evidence-store.md` |
| T012–T021 | `contracts/runner.md`, `contracts/evidence-store.md` |
| T022–T030 | `contracts/hooks.md`, `contracts/reviewer.md` |
| T031–T046 | all four contract files above plus `quickstart.md` |

Anything else requires an explicit task amendment and project-owner approval;
“helpful repository context” is not an unnamed read authorization.

### Exact command mapping

Unless a task supplies a stricter literal command, its focused red and green
commands are derived from its **Files** list without discretion:

- all `Test: *.mjs` paths, in listed order:
  `node --test <space-separated exact paths>`;
- all `Test: *.py` paths, in listed order:
  `uv run --project evaluator pytest <space-separated exact paths> -q`;
- mixed Node/Python tasks run the Node command first and the Python command
  second; red requires at least one expected contract failure and green requires
  both exits to be zero;
- “run TNNN as sentinel” means rerun TNNN's exact green command from this
  mapping; “all Phase X tests” means the sorted union of every `Test:` path in
  that phase, split into the same Node/Python commands;
- every generated or protected artifact named in a task must be passed through
  its owning validator command; existence alone is never a passing check.

For T022–T023 and T025–T030, let `<component>` and `<matrix>` be the task's
single formative matrix basename/path and `<analysis>` its matching analysis
path. Before any candidate body is created, run the current incumbent:

```text
uv run --project evaluator abe-eval run-matrix --matrix <matrix> \
  --condition incumbent-before --qualification evidence/raw/qualification/local/qualification.json \
  --raw-root evidence/raw/formative/<component>/incumbent-before
uv run --project evaluator abe-eval grade --analysis <analysis> \
  --raw-root evidence/raw/formative/<component>/incumbent-before
uv run --project evaluator abe-eval report --analysis <analysis> \
  --raw-root evidence/raw/formative/<component>/incumbent-before \
  --output evidence/publishable/formative/<component>/incumbent-before
```

Record the run, analysis, incumbent package, condition, and protocol digests. If
the frozen gap is no longer present, record `not_selected` and create no
candidate body. Otherwise author the candidate, then execute this fresh
randomized pair-interleaved block:

```text
uv run --project evaluator abe-eval run-matrix --matrix <matrix> \
  --condition-pair incumbent-minus incumbent-plus \
  --qualification evidence/raw/qualification/local/qualification.json \
  --raw-root evidence/raw/formative/<component>/matched-after
uv run --project evaluator abe-eval grade --analysis <analysis> \
  --raw-root evidence/raw/formative/<component>/matched-after
uv run --project evaluator abe-eval report --analysis <analysis> \
  --raw-root evidence/raw/formative/<component>/matched-after \
  --output evidence/publishable/formative/<component>/matched-after
```

The matrix must preallocate and interleave both pair members. These commands and
the task's exact focused command are the minimum red/green evidence; prose such
as “run trials” cannot replace them.

---

## Phase A — Deterministic Contract Foundation

- [ ] T001 [FOUND] Bootstrap the reproducible maintainer workspace

**Requirements**: FR-035, FR-045; Plan Phase 0

**Files**:

- Create: `package.json`
- Create: `pnpm-workspace.yaml`
- Create: `packages/contracts/package.json`
- Create: `packages/plugin-tooling/package.json`
- Create: `evaluator/pyproject.toml`
- Create: `evaluator/src/abe_eval/__init__.py`
- Create: `.gitignore`
- Test: `tests/contract/workspace.test.mjs`
- Generate and commit after dependency resolution: `pnpm-lock.yaml`
- Generate and commit after dependency resolution: `evaluator/uv.lock`

**Produces**:

```text
pnpm test:node
pnpm test:python
pnpm verify:offline
```

- [ ] Add `workspace.test.mjs` assertions for the Node/Python version ranges,
  exact pnpm package-manager field, public workspace members, empty runtime
  dependency set, required scripts, ignored protected-evidence paths, and each
  package's exact name/version/license/type/exports/bin surface. Run
  `node --test tests/contract/workspace.test.mjs`; expect failure because
  `package.json` does not exist.
- [ ] Add the minimal root and per-package workspace manifests, Python package marker, and the
  `abe-eval = abe_eval.cli:main` console entry point. Use uv dependency groups
  so evaluator dependencies never become plugin runtime dependencies; lock
  every resolved package and record its license for T005.
- [ ] Run `corepack pnpm install --frozen-lockfile=false` and
  `uv lock --project evaluator`, then rerun the focused test; expect one passing
  test file.
- [ ] Run `corepack pnpm test:node` and `uv run --project evaluator python -c
  'import sys; assert (3, 12) <= sys.version_info[:2] < (3, 14)'`; expect both
  commands to exit zero.
- [ ] Review the manifests for accidental runtime dependencies, network-bearing
  verify commands, credentials, absolute private paths, and unsupported version
  drift.

**Acceptance**: A clean checkout can resolve a pinned maintainer toolchain while
the installable plugin dependency set remains empty.

- [ ] T002 [FOUND] Implement canonical bytes, digests, and path-safe writes

**Depends on**: T001

**Requirements**: FR-013, FR-035, FR-036; Plan Phase 0

**Files**:

- Create: `packages/contracts/src/canonical-json.mjs`
- Create: `packages/contracts/src/fs-boundary.mjs`
- Test: `packages/contracts/test/canonical-json.test.mjs`
- Create: `evaluator/src/abe_eval/canonical.py`
- Test: `evaluator/tests/test_canonical_parity.py`

**Interfaces**:

```javascript
canonicalBytes(value: JsonValue): Uint8Array
sha256Digest(bytes: Uint8Array): `sha256:${string}`
writeCanonicalAtomic(root: string, relativePath: string, value: JsonValue): Promise<string>
```

```python
def canonical_bytes(value: JsonValue) -> bytes: ...
def sha256_digest(data: bytes) -> str: ...
```

- [ ] Add cross-language fixtures for object-order variance, UTF-8, integer
  boundaries, arrays, null/boolean values, rejected non-finite/fractional runtime
  numbers, traversal, symlink escape, partial write, and concurrent rename. Run
  `node --test packages/contracts/test/canonical-json.test.mjs`; expect module-
  not-found failure.
- [ ] Implement the smallest canonical runtime subset and same-directory
  temp-file/fsync/rename path. The evaluator may support protected floating
  values, but shared runtime contracts must use integers or decimal strings.
- [ ] Run `node --test packages/contracts/test/canonical-json.test.mjs` and
  `uv run --project evaluator pytest evaluator/tests/test_canonical_parity.py -q`;
  expect all digest vectors to match byte-for-byte.
- [ ] Run the T001 workspace test as sentinel and inspect the filesystem test
  root to prove no file escaped it and failed temporary files remain explicit.
- [ ] Review integer restrictions against every runtime schema before accepting
  the interface.

**Acceptance**: Node and Python produce identical digests for shared contract
fixtures, and no atomic-write input can escape its declared root.

- [ ] T003 [FOUND] Define and validate agent-visible runtime contracts

**Depends on**: T002

**Requirements**: FR-012–FR-017, FR-020; Plan Phase 0

**Files**:

- Create: `plugin/schemas/task-state.schema.json`
- Create: `plugin/schemas/evidence-event.schema.json`
- Create: `plugin/schemas/reviewer-verdict.schema.json`
- Create: `plugin/schemas/review-package-input.schema.json`
- Create: `plugin/schemas/review-pair-envelope.schema.json`
- Create: `plugin/schemas/review-request.schema.json`
- Create: `plugin/schemas/reviewer-join.schema.json`
- Create: `plugin/schemas/completion-gate-event.schema.json`
- Create: `packages/contracts/src/runtime-contracts.mjs`
- Test: `packages/contracts/test/runtime-contracts.test.mjs`

**Interfaces**:

```javascript
parseTaskState(value: unknown): TaskState
parseEvidenceEvent(value: unknown): EvidenceEvent
parseCompletionGateEvent(value: unknown): CompletionGateEvent
parseReviewPackageInput(value: unknown): ReviewPackageInput
parseReviewPairEnvelope(value: unknown): ReviewPairEnvelope
parseReviewRequest(value: unknown): ReviewRequest
parseReviewerVerdict(value: unknown): ReviewerVerdict
parseReviewJoinRecord(value: unknown): ReviewJoinRecord
```

- [ ] Add valid, invalid, unknown-field, wrong-version, foreign-workspace,
  terminal-inconsistency, stale-evidence, invalid-reviewer, and reviewer replay
  fixtures with changed pair-envelope/request/artifact/obligation/interface/
  authority digests. Run
  `node --test packages/contracts/test/runtime-contracts.test.mjs`; expect
  module-not-found failure.
- [ ] Implement closed schemas and parsers using the exact entity fields and
  terminal invariants in `data-model.md`; return stable reason codes rather than
  validator prose.
- [ ] Run the focused test; expect all malformed and forward-version fixtures to
  fail closed and all canonical fixtures to pass.
- [ ] Run T002 parity tests as sentinels and verify every emitted runtime object
  can be canonically hashed without a floating number.
- [ ] Review the contracts for semantic decisions that belong outside hooks;
  schemas may enforce consistency but may not declare an implementation correct.

**Acceptance**: Agent-visible state, hook evidence, and reviewer verdicts have
closed, versioned, path-safe contracts with stable validation results.

- [ ] T004 [FOUND] Define protected evaluator and approval contracts

**Depends on**: T002

**Requirements**: FR-023, FR-029–FR-039, FR-042, FR-047; Plan Phase 0

**Files**:

- Create: `evals/schemas/evaluation.schema.json`
- Create: `evals/schemas/approval.schema.json`
- Create: `evaluator/src/abe_eval/contracts.py`
- Test: `evaluator/tests/test_evaluation_contracts.py`
- Create: `tests/contract/fixtures/evaluation-contracts.json`

**Interfaces**:

```python
def parse_contract(kind: str, value: object) -> dict[str, object]: ...
def canonical_contract_digest(kind: str, value: object) -> str: ...
```

- [ ] Add fixtures for every protected entity named in Plan Phase 0 that is not
  owned by T003 and every protected nested boundary type in `data-model.md`,
  including EvaluationClaim, ConditionPairLock,
  PrecisionPowerLock, BlindedBaselineInput, WorkerInvocation,
  UnclassifiedStagedAttemptOutcome, StagedAttemptOutcome, pre-worker RunRecord,
  ApprovalRecord, ReleaseCandidateLock, ProvenanceApprovalRecord,
  ReleaseGateDecision, PackageArchiveRecord, PreparedSchedule,
  SealedOpeningJournal, and PublicationRecord. Run the focused pytest
  file; expect import failure.
- [ ] Implement JSON Schema 2020-12 validation with unknown-field rejection,
  stable reason-code normalization, and cross-object checks that JSON Schema
  alone cannot express.
- [ ] Run `uv run --project evaluator pytest
  evaluator/tests/test_evaluation_contracts.py -q`; expect all valid/boundary
  cases to pass and every tampered digest or missing bound approval to fail.
- [ ] Run T002 Python parity as sentinel; T003 is an independent parallel Phase A task.
- [ ] Review ApprovalRecord handling to ensure tests can use fixture signatures
  but production gates cannot self-issue human approval.

**Acceptance**: Every protected entity has an executable closed contract, and
approval records bind—not merely name—the artifacts they authorize.

- [ ] T005 [FOUND] Build public-safety and provenance validators

**Depends on**: T001, T002

**Requirements**: FR-003, FR-045–FR-049, SC-010; Plan Phase 0

**Files**:

- Create: `packages/plugin-tooling/src/public-safety.mjs`
- Create: `packages/plugin-tooling/src/provenance.mjs`
- Test: `packages/plugin-tooling/test/public-safety.test.mjs`
- Test: `packages/plugin-tooling/test/provenance.test.mjs`
- Create: `tests/provenance/fixtures.json`

**Interfaces**:

```javascript
scanPublicTree(root: string, policy: SafetyPolicy): Promise<SafetyReport>
buildProvenanceInventory(root: string, locks: LockSet): Promise<ProvenanceInventory>
```

- [ ] Add synthetic-lookalike-only true-positive and benign controls for
  credentials, Google-confidential
  identifiers, private paths, copied body fingerprints, missing notices,
  unpinned sources, unexpected files, and ordinary public Google terminology.
  No fixture may contain a real credential, confidential string, private task,
  or copied proprietary passage.
  Run both focused tests; expect module-not-found failures.
- [ ] Implement deterministic scanners whose critical findings require explicit
  disposition; do not implement a fake automated license-compatibility verdict.
- [ ] Run both tests; expect exact finding IDs, severities, source locations, and
  no false positive on every benign fixture.
- [ ] Run `git grep -n` fixtures through the scanner and prove protected fixture
  strings do not appear in generated publishable samples.
- [ ] Review supported-license policy, attribution fields, and the human-review
  boundary against `ProvenanceApprovalRecord`.

**Acceptance**: Automated checks produce reproducible inventories and findings
while reserving legal/provenance approval for a recorded human decision.

---

## Phase B — Immutable Evaluator Walking Slice

- [ ] T006 [US2] Preallocate randomized attempts and validate condition pairs

**Depends on**: T004

**Requirements**: FR-025, FR-029, FR-030, FR-032; Plan Phase 1

**Files**:

- Create: `evaluator/src/abe_eval/schedule.py`
- Create: `evaluator/src/abe_eval/condition_pair.py`
- Test: `evaluator/tests/test_schedule.py`
- Test: `evaluator/tests/test_condition_pair.py`
- Create: `evals/protocols/fake-block.json`

**Interfaces**:

```python
def build_schedule(block: BlockSpec, seed: str) -> tuple[ScheduledAttempt, ...]: ...
def validate_pair(lock: ConditionPairLock, baseline: ConditionLock,
                  treatment: ConditionLock) -> PairValidation: ...
```

- [ ] Add tests proving all attempt/run IDs exist before preflight,
  randomization is seed-reproducible but condition-interleaved, and mismatches in
  model, reasoning, authority, tools, resources, or environment reject both pair
  members before input. Expect import failures.
- [ ] Implement append-only schedule creation and exact JSON-pointer equality
  checks for required-equal and allowed-difference paths.
- [ ] Run both focused pytest files; expect all schedule digests to be stable and
  every forbidden mismatch to return a stable fail reason.
- [ ] Tamper with one scheduled attempt after hashing and prove the importer
  rejects it; run T004 as sentinel.
- [ ] Review the schedule for condition-name leakage and implicit retries.

**Acceptance**: Every run has a preallocated immutable identity and no unmatched
condition pair can expose a task to either agent.

- [ ] T007 [US2] Implement valid-start execution and frozen classification

**Depends on**: T006

**Requirements**: FR-011, FR-032–FR-035; Plan Phase 1

**Files**:

- Create: `evaluator/src/abe_eval/runner.py`
- Create: `evaluator/src/abe_eval/classify.py`
- Create: `evaluator/tests/fakes/fake_worker.py`
- Test: `evaluator/tests/test_attempt_accounting.py`
- Test: `evaluator/tests/test_valid_start_classification.py`

**Interfaces**:

```python
def run_attempt(inputs: RunAttemptInputs, worker: Worker) -> UnclassifiedStagedAttemptOutcome: ...
def classify(outcome: UnclassifiedStagedAttemptOutcome,
             policy: ClassificationPolicy,
             *,
             expected_policy_digest: str) -> StagedAttemptOutcome: ...
```

- [ ] Add the full fake matrix: pre-start auth failure, invalid controller input,
  valid-start timeout, soft denial with exit zero, safety refusal, malformed or
  truncated NDJSON, grader leakage, adapter failure, budget exhaustion, tool
  misuse, test flake, ordinary artifact failure, and success. Expect import
  failures.
- [ ] Implement the monotonic append-only lifecycle through
  `execution_terminal` and write `validStartAt` immediately before input
  visibility. Stage an unclassified outcome even when the worker is
  `not_started`, then apply the frozen decision table bound to the
  `ScenarioCard.classificationPolicyDigest` to create a digest-bound
  StagedAttemptOutcome; do not write `run.json` or `run_finalized`, and never
  derive task success from exit.
- [ ] Run both focused tests; expect every scheduled attempt in intention-to-
  treat fixtures and exact pre-/post-valid-start classification.
- [ ] Add capped replacement fixtures and prove the replacement links to—but
  never overwrites—the original attempt.
- [ ] Review all infrastructure reason codes for a path that could relabel
  product looping, misuse, timeout, or exhaustion as evaluator failure.

**Acceptance**: Every terminal path produces a staged outcome plus immutable
lifecycle evidence; the valid-start boundary determines only attribution, never
convenient success, and no RunRecord is finalized before T008 imports evidence.

- [ ] T008 [US2] Implement content-addressed evidence and immutable re-grading

**Depends on**: T007

**Requirements**: FR-035, FR-036, FR-043; Plan Phase 1

**Files**:

- Create: `evaluator/src/abe_eval/evidence.py`
- Create: `evaluator/src/abe_eval/grade.py`
- Test: `evaluator/tests/test_evidence_store.py`
- Test: `evaluator/tests/test_immutable_regrading.py`
- Create: `evaluator/tests/fixtures/fake-run-output/manifest.json`

**Interfaces**:

```python
def import_run(staging: Path, attempt: ScheduledAttempt,
               condition: ConditionLock, scenario: ScenarioCard,
               qualification: EnvironmentQualificationRecord,
               root: Path) -> RunRecord: ...
def append_grade(run_id: str, grade: GradeRecord, root: Path) -> str: ...
```

- [ ] Add tests for content digesting, missing outputs, symlinks, traversal,
  partial staging, concurrent import, repeated grader digest, and a second grader
  over the same run. Expect import failures.
- [ ] Validate the T007 staged outcome/lifecycle and exact condition/scenario/
  environment-qualification digests against the separately supplied controller
  objects, then implement temporary-run
  import followed by the sole atomic `run.json` finalization and append the sole
  `run_finalized` lifecycle event; make finalized runs read-only and grades
  append-only by grader digest.
- [ ] Run both focused tests; expect the original attempt, raw bytes, RunRecord,
  and first grade digests to remain unchanged after re-grading.
- [ ] Run T007 accounting tests as sentinel and compare raw directory manifests
  before/after the second grade.
- [ ] Review missing evidence handling to ensure no plausible empty transcript or
  artifact is fabricated.

**Acceptance**: Raw evidence is content-addressed and immutable, while new
graders can append independently attributable judgments.

- [ ] T009 [US2] Blind, redact, and report without erasing audit seams

**Depends on**: T008

**Requirements**: FR-032, FR-036, FR-037, FR-043; Plan Phase 1

**Files**:

- Create: `evaluator/src/abe_eval/blind.py`
- Create: `evaluator/src/abe_eval/redact.py`
- Create: `evaluator/src/abe_eval/analyze.py`
- Test: `evaluator/tests/test_blind_and_redact.py`
- Test: `evaluator/tests/test_reporting.py`

**Interfaces**:

```python
def blind_run(record: RunRecord, policy: BlindPolicy) -> BlindProjection: ...
def redact_run(record: RunRecord, policy: RedactionPolicy) -> RedactedRun: ...
def analyze_attempts(analysis: AnalysisLock, attempts: Iterable[RunView]) -> Scorecard: ...
```

- [ ] Add canaries for condition/model names, credentials, hidden checks, private
  reasoning, paths, required audit fields, all-scheduled ITT, valid-run
  exclusions, attrition, and grader agreement. Expect import failures.
- [ ] Implement randomized normalized blind IDs, field-level redaction
  dispositions, and reports that retain every attempt while separating valid-run
  results.
- [ ] Run both focused tests; expect zero canary leakage and exact ITT counts,
  exclusion reasons, uncertainty inputs, and redaction dispositions.
- [ ] Re-run T008 immutability tests and prove redaction creates a separate tree
  without changing protected bytes.
- [ ] Review the public projection manually against `contracts/evidence-store.md`.

**Acceptance**: Reviewers cannot infer model/condition, publishers cannot expose
protected material, and readers retain enough evidence to audit every claim.

- [ ] T010 [US2] Expose the fake matrix through the evaluator CLI

**Depends on**: T006–T009

**Requirements**: FR-032–FR-039; Plan Phase 1 gate

**Files**:

- Create: `evaluator/src/abe_eval/cli.py`
- Create: `evaluator/src/abe_eval/__main__.py`
- Test: `evaluator/tests/test_fake_matrix_cli.py`
- Create: `evals/formative/evaluator-conformance/matrix.json`
- Create: `evals/formative/evaluator-conformance/analysis.json`
- Create: `evals/public-samples/fake-scorecard/README.md`

**Command contract**:

```text
uv run --project evaluator abe-eval fake-matrix \
  --matrix evals/formative/evaluator-conformance/matrix.json \
  --raw-root evidence/raw/formative/evaluator-conformance
uv run --project evaluator abe-eval grade \
  --analysis evals/formative/evaluator-conformance/analysis.json \
  --raw-root evidence/raw/formative/evaluator-conformance
uv run --project evaluator abe-eval report \
  --analysis evals/formative/evaluator-conformance/analysis.json \
  --raw-root evidence/raw/formative/evaluator-conformance \
  --output evidence/publishable/reports/evaluator-conformance
```

- [ ] Add an end-to-end test that invokes all three commands in a temporary root and
  independently recomputes the published scorecard from raw attempts and grades.
  Expect CLI-entry-point failure.
- [ ] Implement strict `fake-matrix`, `grade`, and `report` argparse subcommands,
  explicit roots, stable exits, and a public fake sample containing no private
  source or hidden check.
- [ ] Run `uv run --project evaluator pytest
  evaluator/tests/test_fake_matrix_cli.py -q`; expect the complete matrix and
  reproducible scorecard.
- [ ] Run all Phase B tests and manually recompute one pass, one product failure,
  one preflight failure, and one indeterminate result from raw JSON.
- [ ] Obtain an independent review of the raw-to-report reconstruction before
  authorizing T012 or any paid target-model run.

**Acceptance**: A human can reproduce the fake scorecard from immutable raw
evidence without trusting evaluator summaries.

- [ ] T011 [US2] Decide the SMEvals adapter on losslessness, not convenience

**Depends on**: T010

**Requirements**: FR-032–FR-037; Plan Phase 1

**Files**:

- Create during spike; retain only if adopted: `evaluator/src/abe_eval/adapters/smevals.py`
- Test: `evaluator/tests/test_smevals_adapter.py`
- Create: `research/smevals-adapter-decision.md`
- Modify for either final decision: `evaluator/pyproject.toml`
- Modify for either final decision: `evaluator/uv.lock`

**Interface**:

```python
def project_to_smevals(attempts: tuple[ScheduledAttempt, ...],
                       runs: tuple[RunRecord, ...]) -> AdapterProjection: ...
```

**Pinned spike command**:

```text
uv run --project evaluator \
  --with "smevals @ git+https://github.com/prime-radiant-inc/smevals@0c28dc6298eb0e6c3b47e296e82a6972a01d76d0" \
  pytest evaluator/tests/test_smevals_adapter.py -q
```

- [ ] Add known-answer fixtures containing pre-worker failure, post-start product
  failure, replacement linkage, missing capture, immutable multiple grades, and
  ITT/valid-run projections. Expect adapter import failure.
- [ ] Run only the pinned isolated command and implement the narrowest adapter
  against that exact public revision without
  allowing SMEvals to own the authoritative ledger.
- [ ] Run the focused test and compare every source attempt/run/grade identity,
  classification, and denominator with the round-trip projection.
- [ ] Record `ADOPT` only if the projection is lossless for all required fields;
  on ADOPT, add the exact revision only to an evaluator-only dependency group and
  lock it; on REJECT, delete the spike adapter and remove all SMEvals entries
  from `pyproject.toml`/`uv.lock` while retaining the decision and known-answer
  test that asserts the project-owned path.
- [ ] Run all Phase B tests after either decision and review the decision record
  for claims stronger than the evidence.

**Acceptance**: The optional framework is either a proved-lossless adapter or an
explicitly rejected dependency; evaluator integrity never depends on optimism.

---

## Phase C — Disposable Worker and Live Antigravity Qualification

- [ ] T012 [US2] Build a disposable worker without embedding CLI or credentials

**Depends on**: T010

**Requirements**: FR-038, FR-039, FR-049; Plan Phase 2

**Files**:

- Create: `environments/worker/Dockerfile`
- Create: `environments/worker/entrypoint.sh`
- Create: `environments/worker/verify-image.mjs`
- Create: `environments/controller/mount-policy.json`
- Create: `environments/controller/network-policy.json`
- Test: `evaluator/tests/test_worker_image.py`

**Interfaces**:

```text
/opt/abe/entrypoint --invocation /workspace/input/worker-invocation.json
node /opt/abe/verify-image.mjs \
  --expected /workspace/input/qualification-lock.json
/opt/antigravity/bin/agy --version
```

- [ ] Add an image/runtime inspection test for exact uid, writable roots, fresh
  profile, fixture/output separation, missing hidden mounts, package-manager
  network denial during behavior runs, absence of CLI/credentials in image
  layers, and a protected read-only runtime mount at
  `/opt/antigravity/bin/agy`. Prove the worker receives only WorkerInvocation
  and cannot see ScheduledAttempt, condition/block/randomization identity,
  hidden scenario labels, `/controller`, the Docker socket, host credential
  stores, ordinary user workspaces, or ambient Gemini/Antigravity state including
  `.gemini`, rules, skills, agents, hooks, plugins, caches, conversations, and
  project state. Expect image-not-found failure.
- [ ] Implement the pinned base, non-root entrypoint, init/reaping behavior,
  dropped capabilities, `no-new-privileges`, declared mounts, and image
  verifier. Define the CLI as a protected read-only runtime bind in
  `mount-policy.json`; validate its regular-file identity and
  EnvironmentQualificationRecord digest before every attempt. Authentication is
  injected as the smallest runtime secret needed for Antigravity inference and
  remains outside agent-visible evidence.
- [ ] Build without the CLI, credentials, or secrets in the context, then run:

  ```bash
  docker buildx build --tag antigravity-behavior-worker:test \
    --load environments/worker
  ```

  Launch the test worker with the approved CLI artifact mounted read-only at the
  exact path; run the focused pytest and expect runtime invocation plus all
  layer/boundary probes to pass.
- [ ] Launch two workers with distinct profile/repository/output mounts and prove
  neither can see the other's canary or controller-owned hidden directory.
- [ ] Review the image history, exported filesystem inventory, and public build
  context for protected material.

**Acceptance**: A fresh worker exposes only the agent-visible task projection
and cannot contain or read hidden graders, competing runs, credentials, or the
authorized CLI artifact outside its scoped execution path.

- [ ] T013 [US2] Qualify exact CLI, model, effort, and stream contracts

**Depends on**: T007, T011, T012

**Requirements**: FR-021–FR-025, FR-033–FR-035; Plan Phase 2

**Files**:

- Create: `evaluator/src/abe_eval/antigravity.py`
- Create: `evaluator/src/abe_eval/qualify.py`
- Modify: `evaluator/src/abe_eval/cli.py`
- Test: `evaluator/tests/test_antigravity_adapter.py`
- Test: `evaluator/tests/test_live_qualification.py`
- Create: `evals/protocols/qualification.json`
- Create protected, outside Git: `evidence/raw/qualification/local/qualification.json`

**Interfaces**:

```python
def build_argv(condition: ConditionLock, request_path: Path) -> tuple[str, ...]: ...
def qualify_environment(worker: WorkerHandle, protocol: QualificationProtocol) -> EnvironmentQualificationRecord: ...
def preflight_attempt(worker: WorkerHandle, condition: ConditionLock) -> AttemptQualificationRecord: ...
def run_matrix(matrix: MatrixLock, qualification: EnvironmentQualificationRecord) -> tuple[RunRecord, ...]: ...
```

**Qualification command**:

```text
uv run --project evaluator abe-eval qualify \
  --protocol evals/protocols/qualification.json --scope cli_core \
  --cli-artifact "$ABE_AUTHORIZED_CLI_PATH" \
  --output evidence/raw/qualification/local/qualification.json
```

The command resolves both exact target slugs from the live catalog, records the
observed model/effort evidence, and rejects rather than substitutes an
unavailable or unobservable configuration.

- [ ] Add fake-CLI tests for argument-vector construction without shell
  interpolation, exactly one init/result event, duplicates/out-of-order/malformed
  lines, soft denial with exit zero, timeout, stderr, unknown model, and missing
  observable identity. Expect import failures.
- [ ] Implement raw-line preservation before parsing, explicit model/effort/
  permission arguments, strongest-observable identity, limitations, fail-closed
  unknown-model/fallback probes, reusable environment qualification, all seven
  per-attempt preflights, and strict `qualify`/`run-matrix` CLI commands that
  delegate to the authoritative scheduler and runner.
- [ ] Run the fake focused test, then live qualification against the exact
  authorized CLI using Gemini 3.7 Flash high and Gemini 3.1 Pro high; exact slugs
  come from the live catalog and are frozen into
  `evidence/raw/qualification/local/qualification.json`.
- [ ] Misspell each model slug and alter each reasoning request; prove preflight
  fails before valid start and no fallback run enters evidence.
- [ ] Review the EnvironmentQualificationRecord, a representative
  AttemptQualificationRecord, and raw invocation for provider/auth mode,
  non-secret environment projection, model limitations, all seven preflights,
  and falsely inferred served identity.

**Acceptance**: Each exact model configuration is independently qualified and
unavailable, substituted, or unobservable fallback-sensitive configurations
fail before treatment.

- [ ] T014 [US4] Qualify an inert plugin through the complete CLI lifecycle

**Depends on**: T005, T013

**Requirements**: FR-001, FR-002, FR-006–FR-008; Plan Phase 2

**Files**:

- Create: `plugin/plugin.json`
- Create: `plugin/behavior-lock.json`
- Create: `packages/plugin-tooling/bin/inspect-install.mjs`
- Create: `packages/plugin-tooling/src/lifecycle.mjs`
- Test: `tests/lifecycle/inert-plugin.test.mjs`

**Interfaces**:

```javascript
inspectInstall(profileRoot: string, expectedLock: PackageLock): Promise<InstallInspection>
snapshotProfile(profileRoot: string, volatilityPolicy: VolatilityPolicy): Promise<ProfileManifest>
```

- [ ] Add clean and customized profile fixtures covering validate, local/remote
  install, list, discovery, repeat install, conflict-before-write, enable,
  disable, upgrade, rollback, interrupted operation, uninstall, and exact state
  diff. Expect plugin-not-found failure.
- [ ] Implement the smallest officially accepted manifest plus companion lock;
  do not invent manifest fields rejected by the qualified CLI.
- [ ] Execute the lifecycle on disposable profiles. Record every touched path,
  Antigravity-owned volatile exclusion, command exit, and discovery result.
- [ ] Re-run installation and removal; expect idempotence, no package-owned
  residue, and byte-identical unrelated fixture state.
- [ ] Review documented versus observed CLI behavior and narrow the support
  matrix instead of adding an unproved fallback.

**Acceptance**: The inert package installs, identifies, disables, upgrades,
rolls back, and removes cleanly without silently changing unrelated state.

- [ ] T015 [US1] Qualify skill and rule content-discovery semantics

**Depends on**: T014

**Requirements**: FR-004, FR-005, FR-020; Plan Phase 2

**Files**:

- Test: `tests/lifecycle/customization-content-conformance.test.mjs`
- Create: `tests/lifecycle/fixtures/probe-plugin/plugin.json`
- Create: `tests/lifecycle/fixtures/probe-plugin/probe-components.json`
- Create: `evals/protocols/customization-conformance.json`

**Probe result**:

```json
{
  "skillBodyObservable": true,
  "ruleBodySelective": false,
  "evidenceDigest": "sha256:..."
}
```

- [ ] Add the content-surface test for metadata versus body access, global/
  workspace/plugin precedence, collisions, skill activation, and rule Model
  Decision. Expect probe-plugin content discovery failure.
- [ ] Implement only inert public skill/rule canaries with unique markers; no
  hidden label, evaluator state, or treatment conclusion may enter the probe.
- [ ] Run the focused test on every proposed supported CLI/OS profile and freeze
  the strongest observable trace. `unknown` remains `unknown`, never `pass`.
- [ ] Specifically prove whether Model Decision withholds the rule body on
  non-applicable tasks. False or unobservable records `rule: disqualified`; no
  later task may upgrade that decision without amending and reapproving T015.
- [ ] Complete fresh requirements and quality review over content canaries,
  treatment effects, collisions, and the frozen protocol digest.

**Acceptance**: Skill and rule body-access semantics are observed independently;
the candidate rule is permitted only with body-level selective-access evidence.

- [ ] T016 [US1] Qualify agent and hook execution semantics

**Depends on**: T015

**Requirements**: FR-015, FR-017, FR-020; Plan Phase 2

**Files**:

- Test: `tests/lifecycle/customization-execution-conformance.test.mjs`
- Test: `tests/lifecycle/customization-conformance.test.mjs`
- Create: `tests/lifecycle/fixtures/probe-plugin/hooks.json`
- Modify: `tests/lifecycle/fixtures/probe-plugin/probe-components.json`
- Modify: `evals/protocols/customization-conformance.json`

**Probe result**:

```json
{
  "hookResolution": "plugin-root",
  "agentInheritance": "explicit",
  "evidenceDigest": "sha256:..."
}
```

- [ ] Add execution-surface tests for hook cwd/order/timeout/malformed output/
  failure policy plus agent tool validation, customization inheritance, idle,
  kill, permission bubbling, and cleanup. Expect missing execution probes.
- [ ] Implement only inert public hook/agent canaries and close every tool name
  and output shape against the qualified CLI contract.
- [ ] Run the execution test on every T015-supported profile and freeze the
  strongest observable trace; unknown distinctions remain `unknown`, never
  `pass`, and no hidden label or grader state enters a probe.
- [ ] Run the aggregate conformance test over both frozen checkpoints; reject a
  cross-surface contradiction rather than choosing the convenient observation.
- [ ] Complete fresh requirements and quality review over execution canaries,
  failure policy, cleanup, treatment effects, and evidence digests.

**Acceptance**: Agent and hook execution/discovery semantics are independently
observed and consistent with the frozen content-surface qualification.

---

## Phase D — Scenario Portfolio and Pre-Treatment Baselines

- [ ] T017 [US2] Freeze task families and scenario generation

**Depends on**: T004, T010, T016

**Requirements**: FR-005, FR-011, FR-027, FR-030, FR-038, FR-044; SC-005;
Plan Phase 3

**Files**:

- Create: `evals/protocols/task-families.json`
- Create: `evals/formative/registry.json`
- Create: `evals/regression/registry.json`
- Create: `evaluator/src/abe_eval/scenario.py`
- Test: `evaluator/tests/test_scenario_registry.py`

**Interfaces**:

```python
def materialize_scenario(protocol: TaskFamilyProtocol, seed: str,
                         partition: Partition) -> ScenarioCard: ...
```

- [ ] Add the scenario-registry test for independent variant generation, immutable partitioning,
  pre-treatment applicability/workflow/authority/evidence labels, weight and
  exclusion locks, hidden canaries, sealed-instance absence from Git, and
  contamination history. Expect import failure.
- [ ] Implement at least twelve protocols covering all FR-044 behaviors and
  positive/negative component controls; store protocols, never sealed instances,
  in the public tree. Include interactive user direction, successful scoped
  pre-granted authority, unattended safe default, explicit NEEDS_INPUT, and
  headless soft-denial variants.
- [ ] Run the registry test; expect deterministic fixture digests,
  disjoint formative/regression/sealed variant IDs, and no worker-readable
  hidden fields.
- [ ] Materialize the same seed twice and a different seed once;
  expect identical first pair and independently different third variant. Final
  registries contain protocols and reserved seed commitments, never a sealed
  instance.
- [ ] Complete fresh requirements and quality review; reject narration-only
  grading, labels treatment can edit, or any post-treatment generator input.

**Acceptance**: The portfolio can produce controlled, partitioned, independently
labeled tasks without exposing hidden material or observing a treatment.

- [ ] T018 [US2] Freeze analysis, resources, and completion-honesty accounting

**Depends on**: T017

**Requirements**: FR-028–FR-031, FR-038, FR-044; SC-005; Plan Phase 3

**Files**:

- Create: `evals/protocols/analysis-locks.json`
- Create: `evals/protocols/completion-honesty.json`
- Create: `evaluator/src/abe_eval/analysis_lock.py`
- Test: `evaluator/tests/test_analysis_lock.py`
- Test: `evaluator/tests/test_honesty_protocol.py`

**Interface**:

```python
def freeze_analysis(family: TaskFamily, resource_envelope: ResourceEnvelope,
                    analysis_code_digest: str) -> AnalysisLock: ...
```

- [ ] Add failing analysis-lock and honesty known-answer tests for weights,
  exclusions, stopping, model separation, disjoint cohorts, replacement caps,
  and attempt-to-variant reduction.
- [ ] Freeze pilot and release ResourceEnvelopes, analysis code digests, cohort
  definitions, exclusions, stopping rules, variant reduction, and reserved
  unseen regression-generation digests without any baseline/treatment outcome.
- [ ] Run both focused tests; require disjoint negative failing/missing/
  indeterminate-check and positive working-evidence cohorts, and require repeats
  or replacements never to increase the distinct denominator.
- [ ] Tamper each frozen field and prove contract validation fails; prove no
  gradable claim state can be reclassified as attrition.
- [ ] Complete fresh requirements and quality review over causal ordering,
  model separation, honesty denominators, resource parity, and lock digests.

**Acceptance**: Every formative, regression, and release analysis input is
pre-treatment, immutable, resource-bound, and honest about distinct variants.

- [ ] T019 [US2] Implement deterministic checks and calibrated blind rubrics

**Depends on**: T018

**Requirements**: FR-035–FR-038, SC-004, SC-011; Plan Phase 3

**Files**:

- Modify: `evaluator/src/abe_eval/grade.py`
- Create: `evaluator/src/abe_eval/rubric.py`
- Create: `evals/protocols/engineering-rubric.json`
- Test: `evaluator/tests/test_deterministic_graders.py`
- Test: `evaluator/tests/test_blind_rubric.py`

**Interfaces**:

```python
def run_hidden_checks(card: ScenarioCard, artifact_root: Path) -> DeterministicResult: ...
def grade_blind(projection: BlindProjection, rubric: AnchoredRubric) -> ReviewerGrade: ...
```

- [ ] Add known-answer artifact fixtures, planted critical/important/minor
  defects, defect-free controls, two-reviewer disagreements, adjudication, and
  hidden-canary leakage. Expect import failures.
- [ ] Implement checks outside the worker, randomized blind presentation,
  anchored 1–5 dimensions, calibration scoring, agreement, and frozen
  adjudication without exposing reference solutions.
- [ ] Run both focused tests; expect exact deterministic outcomes, at least the
  fixture agreement target, and no condition/model leakage.
- [ ] Manually score the calibration sample and compare to automated rubric
  parsing before accepting a grader version digest.
- [ ] Review all metrics to ensure trajectory diagnostics cannot override a
  failing artifact outcome.

**Acceptance**: Real artifacts determine primary outcomes and two calibrated,
condition/model-blind judgments supply independent qualitative evidence.

- [ ] T020 [US2] Capture interleaved bare-Antigravity baselines

**Depends on**: T013, T018, T019

**Requirements**: FR-021–FR-025, FR-028–FR-030, FR-042; Plan Phase 3

**Files**:

- Create: `evals/formative/bare-pilot.matrix.json`
- Create: `evals/formative/bare-pilot.analysis.json`
- Create: `docs/evaluation/bare-baseline-method.md`
- Test: `evaluator/tests/test_bare_condition.py`
- Create protected, outside Git: `evidence/raw/formative/incumbent-baseline/bare/`

**Command**:

```text
uv run --project evaluator abe-eval run-matrix \
  --matrix evals/formative/bare-pilot.matrix.json \
  --condition bare \
  --qualification evidence/raw/qualification/local/qualification.json \
  --raw-root evidence/raw/formative/incumbent-baseline/bare
```

- [ ] Add a bare-condition test proving fresh app/home/profile/repository state,
  empty prior conversation, no unlisted extensions, fixture-only repository
  instructions, exact ConditionLock, and per-model three-run pilot cells. Expect
  missing matrix failure.
- [ ] Load the T018-frozen resource envelopes and pair-compatible condition
  fields, then run a standalone historical bare pilot for each model without
  Superpowers or any local treatment file. T021 later allocates a new
  contemporaneous matched block; it never mutates or completes these attempts.
- [ ] Generate model-separated variance, ceiling, attrition, resource, artifact
  outcome, and first-divergence reports from protected evidence.
- [ ] Repeat one family from a fresh host/profile boundary; expect matching
  starting digests and no contamination canary.
- [ ] Review representative failures directly from raw streams and artifacts;
  identify candidate gaps without authoring treatment language.

**Acceptance**: Both models have trustworthy, separately reported bare baselines
and at least one repeatable gap for every behavior candidate allowed to proceed.

- [ ] T021 [US2] Qualify and capture the Superpowers-only incumbent

**Depends on**: T014, T020

**Requirements**: FR-003, FR-028, FR-045; Plan Phase 3

**Files**:

- Create: `evals/formative/superpowers-pilot.matrix.json`
- Create: `evals/formative/superpowers-pilot.analysis.json`
- Create: `docs/provenance/superpowers-lock.md`
- Test: `tests/lifecycle/superpowers-upstream.test.mjs`
- Test: `evaluator/tests/test_paired_incumbent_baseline.py`
- Modify: `plugin/behavior-lock.json`
- Create protected, outside Git: `evidence/raw/formative/incumbent-baseline/superpowers/`
- Create protected, outside Git: `evidence/raw/formative/incumbent-baseline/blinded-baseline-input.json`

**Pinned source**:

```text
https://github.com/obra/superpowers
b36e0829c6d0140e93cfef2ca599b1b07d4a7797
```

**Behavior command**:

```text
uv run --project evaluator abe-eval run-matrix \
  --matrix evals/formative/superpowers-pilot.matrix.json \
  --condition-pair bare superpowers \
  --qualification evidence/raw/qualification/local/qualification.json \
  --raw-root evidence/raw/formative/incumbent-baseline
uv run --project evaluator abe-eval grade \
  --analysis evals/formative/superpowers-pilot.analysis.json \
  --raw-root evidence/raw/formative/incumbent-baseline
```

The matrix contains newly allocated contemporaneous `bare` and `superpowers`
attempts in each randomized pair block; it is not a join against T020's older
bare runs.

- [ ] Add tests for upstream-source install, exact revision/digest, MIT license,
  native discovery, session-start behavior, enable/disable/uninstall, collision,
  and no copied upstream body under `plugin/`. Add paired-baseline tests for
  fresh pair/attempt IDs, ConditionPairLocks, model separation, no T020 attempt
  reuse, masked labels, and exclusion of local/sealed outcomes. Expect missing
  lock/artifact failure.
- [ ] Resolve or verify Superpowers from its own source on the qualified CLI;
  if source-SHA installation is unsupported, fail visibly and document the
  reproducible external pin mechanism rather than vendoring it.
- [ ] Allocate a new randomized matched block and run both fresh bare and
  Superpowers-only attempts contemporaneously, pair-interleaved
  within model/family/resource strata. The contemporaneous bare attempts
  supersede T020's historical estimates for incremental comparison but never
  rewrite them.
- [ ] Produce model-separated paired incremental outcomes and baseline gaps for
  the local candidate portfolio; mask condition labels and persist a protected
  BlindedBaselineInput plus digest for T035. It may contain only bare/incumbent
  pilot summaries and pre-treatment analysis locks, never a local-treatment or
  sealed outcome. Run the Python test against the actual protected artifact;
  do not attribute Superpowers behavior to this package.
- [ ] Review installed files and repository fingerprints to prove no upstream
  skill body was copied or silently staged.

**Acceptance**: Superpowers is a verified, pinned upstream incumbent whose
behavior and lifecycle are measured independently of all local treatments.

---

## Phase E — Evidence-Earned Runtime Components

- [ ] T022 [US1] Decide the compact kernel rule with a no-rule outcome

**Depends on**: T015, T021

**Requirements**: FR-005, FR-009, FR-018–FR-020, FR-028; SC-007, SC-013;
Plan Phase 4

**Files**:

- Create only if qualified: `plugin/rules/engineering-evidence-kernel.md`
- Create: `evals/formative/kernel-rule.matrix.json`
- Create: `evals/formative/kernel-rule.analysis.json`
- Test: `tests/plugin/kernel-rule.test.mjs`
- Modify: `plugin/behavior-lock.json`

**Decision output**:

```json
{"component":"engineering-evidence-kernel","decision":"selected|not_selected","evidenceDigest":"sha256:..."}
```

- [ ] Confirm T015 proves body-level selective application. Add a failing static
  test for the qualified activation mode, 12,000-character ceiling, collision,
  prohibited procedure duplication, and lock consistency. If conformance is
  false/unknown, write a failing no-rule lock test instead of a rule body.
- [ ] When qualified, author only authority, proportionality, untrusted-content,
  unrelated-work, and evidence invariants; when disqualified, record
  `rule: not selected` and create no replacement kernel skill.
- [ ] Run incumbent-minus/plus comparisons on applicable engineering cases,
  trivial tasks, explicit preferences, prompt injection, and non-engineering
  controls under matched conditions for each model.
- [ ] Retain only clauses with attributable outcome lift and no SC-007/body-load
  or resource regression; otherwise delete the rule file and rerun the no-rule
  test.
- [ ] Review the final decision against raw body-access traces and artifact
  outcomes, not model claims that it ignored a loaded rule.

**Acceptance**: The incumbent contains either one causally useful, natively lazy
rule or an explicit, tested no-rule decision with no compensating instruction
bloat.

- [ ] T023 [US1] Earn the `evidence-first-framing` skill

**Depends on**: T022

**Requirements**: FR-004, FR-009, FR-010, FR-019, FR-020, FR-028; SC-003,
SC-007, SC-013; Plan Phase 5A

**Files**:

- Create: `plugin/skills/evidence-first-framing/SKILL.md`
- Create: `evals/formative/evidence-first-framing.matrix.json`
- Create: `evals/formative/evidence-first-framing.analysis.json`
- Test: `tests/plugin/evidence-first-framing.test.mjs`
- Modify: `plugin/behavior-lock.json`

**Skill boundary**:

```text
Input: material-ambiguity candidate plus bounded task context
Output: user_direction | safe_default | bounded_out | needs_input
Non-goal: generic brainstorming, design approval, or implementation planning
```

- [ ] Select repeatable T020/T021 failures where scope-shaping edits precede
  correct ambiguity disposition. Add static tests for exact frontmatter,
  cold-readable activation description, non-goals, safe-default invariants,
  collision list, and absence of copied public-skill passages. Expect failure
  because the skill is absent.
- [ ] Author the smallest original procedure that inspects relevant context and
  records only material dispositions; include interactive, unattended,
  reversible-default, and NEEDS_INPUT paths.
- [ ] Run matched incumbent-minus/plus trials over ambiguous, fully specified,
  trivial, preference, prompt-injection, and first-session cases for each model.
- [ ] Require pre-edit recall/precision and question burden to meet the frozen
  family gate inside its ResourceEnvelope; simplify or remove the skill on
  failure.
- [ ] Review activation traces, recorded assumption dispositions, and actual
  edits to reject performative question-asking without scope improvement.

**Acceptance**: The retained skill improves material-ambiguity disposition
before edits without duplicating Superpowers or burdening specified/trivial work.

- [ ] T024 [US1] Build the dependency-free durable evidence CLI

**Depends on**: T003, T023

**Requirements**: FR-012–FR-014, FR-017; Plan runtime support boundary

**Files**:

- Create: `packages/evidence-cli/package.json`
- Create: `packages/evidence-cli/src/task-state.mjs`
- Create: `packages/evidence-cli/bin/abe-evidence.mjs`
- Test: `packages/evidence-cli/test/task-state.test.mjs`
- Create: `plugin/scripts/runtime-lib.mjs`

**Command interface**:

```text
node plugin/scripts/runtime-lib.mjs init --task-id task-0001 \
  --workspace-digest sha256:0000000000000000000000000000000000000000000000000000000000000000 \
  --request-digest sha256:1111111111111111111111111111111111111111111111111111111111111111
node plugin/scripts/runtime-lib.mjs apply \
  --patch-file .agents/abe/task-0001/patch.json
node plugin/scripts/runtime-lib.mjs validate \
  --state-file .agents/abe/task-0001/state.json
node plugin/scripts/runtime-lib.mjs show \
  --state-file .agents/abe/task-0001/state.json
```

- [ ] Add black-box tests for the exact package name/version/license/type/exports/
  bin surface, init, closed patch operations, append-only
  checkpoints/findings, atomic writes, foreign workspace/request digests,
  traversal/symlink escape, concurrent update, malformed state, stale evidence,
  terminal inconsistency, atomic TaskState-plus-ordinal-zero completion-ledger
  genesis, rollback on partial initialization, and deterministic bundled output.
  Expect missing-bin failure.
- [ ] Implement only parse/validate/canonicalize/atomically-write/show mechanics
  over T003 contracts. `init` atomically commits TaskState and the ordinal-zero
  initialized CompletionGateEvent ledger or leaves neither. The CLI may not
  invent obligations, judge evidence, resolve findings, or decide terminal state.
- [ ] Keep the package CLI as a thin maintainer wrapper over the same
  dependency-free runtime library, compare its digest across two clean builds,
  and run the full black-box suite against both entry points.
- [ ] Run T002 path/digest and T003 runtime-contract tests as sentinels; expect
  identical validation reason codes and bytes.
- [ ] Review help/errors to ensure Gemini can use the CLI as a black box without
  reading its source or receiving hidden evaluator information.

**Acceptance**: Skills can create and update durable TaskState safely through a
small deterministic tool that carries no semantic correctness authority.

- [ ] T025 [US1] Earn the `proof-obligation-contract` skill

**Depends on**: T024

**Requirements**: FR-011–FR-013, FR-017, FR-028; SC-005–SC-007, SC-013;
Plan Phase 5B

**Files**:

- Create: `plugin/skills/proof-obligation-contract/SKILL.md`
- Create: `evals/formative/proof-obligation-contract.matrix.json`
- Create: `evals/formative/proof-obligation-contract.analysis.json`
- Test: `tests/plugin/proof-obligation-contract.test.mjs`
- Modify: `plugin/behavior-lock.json`

**Skill boundary**:

```text
Input: approved or bounded intent for a substantial task
Output: workspace/request-bound TaskState with observable proof obligations
Non-goal: Spec Kit, generic planning, TDD, or semantic grading
```

- [ ] Select baselines with lost requirements, proxy verification, stale
  evidence, false completion, and cold-process failure. Add static and schema
  tests for obligation seam, authority, freshness anchor, terminal consistency,
  and one-check non-activation. Expect missing-skill failure.
- [ ] Author the minimal original workflow for creating/updating TaskState before
  substantial implementation and for declaring complete/incomplete/blocked/
  failed/indeterminate/needs_input honestly.
- [ ] Run matched positive/negative trials for each model, including post-change
  evidence freshness, externally observable behavior, restart, soft denial,
  missing checks, and successful-completion controls.
- [ ] Require outcome lift, honesty improvement, cold recovery, and low overhead;
  reject schema theater that improves narration but not artifacts.
- [ ] Review generated state against the real workspace/request digest and prove
  a foreign or stale state file is not adopted.

**Acceptance**: Substantial work gains a compact, durable evidence contract that
improves real verification and honest terminal states without ritual on bounded
work.

- [ ] T026 [US1] Earn the `audited-iteration` skill

**Depends on**: T025

**Requirements**: FR-013, FR-014, FR-016, FR-018, FR-028; SC-004, SC-006,
SC-013; Plan Phase 5C

**Files**:

- Create: `plugin/skills/audited-iteration/SKILL.md`
- Create: `evals/formative/audited-iteration.matrix.json`
- Create: `evals/formative/audited-iteration.analysis.json`
- Test: `tests/plugin/audited-iteration.test.mjs`
- Modify: `plugin/behavior-lock.json`
- Modify (project-owner-authorized repair): `evaluator/src/abe_eval/skill_ablation.py`
- Modify (project-owner-authorized repair): `plugin/skills/evidence-first-framing/SKILL.md`
- Modify (authorized transitive sentinel repair): `tests/plugin/evidence-first-framing.test.mjs`
- Modify (authorized transitive sentinel repair): `tests/plugin/kernel-rule.test.mjs`

**Scope amendment approval**: On 2026-08-22 the project owner authorized T026
to make the evaluator fail closed on recorded replay bindings, remove the
rejected `audited-iteration` ownership reference from the framing skill, and
update the existing focused test and behavior lock accordingly. Exact transitive
sentinels may bind the new lock while preserving the historical T023 analysis
digest; they may not relabel prior evidence onto the repaired bytes. This
amendment authorizes no other product, metric, threshold, or release change.

**Skill boundary**:

```text
Input: substantial long/interruption-prone task with active obligations
Output: append-only checkpoints, impacted evidence, sentinels, and exact next action
Non-goal: fixed increment size, generic TDD/debugging/review, or bounded-task ledger
```

- [ ] Select baselines with repeated work, requirement drift, failed-checkpoint
  corruption, lost findings, sentinel regression, or restart divergence. Add
  static tests for scope, checkpoint fields, recovery rules, zero-progress bound,
  and non-activation on bounded tasks. Expect missing-skill failure.
- [ ] Author the minimal original method linking each reviewable increment to
  impacted obligations/evidence and preserved sentinels; recovery must start
  from actual state, not optimistic narration.
- [ ] Run matched long-task, interruption, dirty-worktree, failure-recovery,
  repeated-work, and trivial controls for each model.
- [ ] Require equivalent or better final artifact, at least the cold-restart
  threshold, reduced repeated work, preserved unrelated changes, and no
  ResourceEnvelope breach.
- [ ] Review checkpoint histories for fake progress, unnecessary ledger growth,
  and hidden dependence on conversation memory.

**Acceptance**: Long work becomes restartable and reviewable with preserved
evidence, while short work remains free of iterative-development ceremony.

- [ ] T027 [US1] Earn the conclusion-free requirements reviewer

**Depends on**: T026

**Requirements**: FR-015, FR-016, FR-026, FR-028; SC-004, SC-011, SC-013;
Plan Phase 6

**Files**:

- Create: `plugin/agents/requirements-falsifier.md`
- Create: `plugin/scripts/reviewer-package.mjs`
- Create: `evals/formative/requirements-reviewer.matrix.json`
- Create: `evals/formative/requirements-reviewer.analysis.json`
- Test: `tests/plugin/requirements-falsifier.test.mjs`
- Modify: `plugin/behavior-lock.json`

**Agent contract**:

```text
model: inherit
mainAgent: false
subagent: true
reviewerRole: requirements
input: approved requirements + real diff/artifact + verification interface + authority
output: ReviewerVerdict bound to the shared pair envelope, exact role request,
artifact, obligations, interface, and authority digests
```

**Production interfaces**:

```javascript
buildReviewPairEnvelope(input: ReviewPackageInput): ReviewPairEnvelope
buildReviewPackage(envelope: ReviewPairEnvelope,
                   role: "requirements" | "quality",
                   root: string): Promise<ReviewRequest>
validateReviewerVerdict(request: ReviewRequest, value: unknown): ReviewerVerdict
```

- [ ] Add the requirements-role test for exact read-only tools, clean context,
  inheritance, timeout/permission handling, the parent envelope, role request,
  non-circular manifest/request hashing, and all four content digest bindings,
  planted
  requirement defects, and defect-free controls. Expect missing agent.
- [ ] Author only the requirements-falsification role and the content-addressed
  minimum-package builder/verdict validator without the implementer's conclusion,
  expected defect count, hidden grader state, competing verdict, or a review-
  method skill duplicating Superpowers.
- [ ] Run self-review versus requirements-reviewer treatments on planted and
  defect-free requirement violations for both models at matched and separately
  labeled higher-cost profiles.
- [ ] Require frozen recall/precision/resource gates; invalid, replayed,
  timed-out, or permission-blocked verdicts are never passes. If the gap does
  not persist, record `not_selected` and package no requirements agent.
- [ ] Complete fresh requirements and quality review over actual verdicts,
  false-positive burden, trivial-task controls, and repair traceability.

**Acceptance**: The requirements reviewer independently improves obligation and
completion-evidence falsification without false-positive overload, prompt
duplication, or hidden model routing.

- [ ] T028 [US1] Earn the quality reviewer and paired-review topology

**Depends on**: T027

**Requirements**: FR-015, FR-016, FR-026, FR-028; SC-004, SC-011, SC-013;
Plan Phase 6

**Files**:

- Create: `plugin/agents/quality-falsifier.md`
- Create: `plugin/scripts/reviewer-join.mjs`
- Create: `evals/formative/reviewer-topology.matrix.json`
- Create: `evals/formative/reviewer-topology.analysis.json`
- Test: `tests/plugin/quality-falsifier.test.mjs`
- Test: `tests/plugin/reviewer-agents.test.mjs`
- Modify: `plugin/behavior-lock.json`

**Agent contract**: T027's closed digest/authority envelope with
`reviewerRole: quality`; paired reviewers never communicate and are joined only
after both terminal verdicts.

**Production interface**:

```javascript
joinReviewerVerdicts(envelope: ReviewPairEnvelope,
                     requirementsRequest: ReviewRequest,
                     requirementsVerdict: unknown,
                     qualityRequest: ReviewRequest,
                     qualityVerdict: unknown): ReviewJoinRecord
```

- [ ] Add a quality-role test for exact read-only tools, clean context,
  isolation/replay boundaries, planted implementation/safety/maintainability
  defects, defect-free controls, and no access to the requirements verdict.
- [ ] Author only the implementation-quality falsifier without the
  implementer's conclusion, expected defect count, requirements-reviewer output,
  hidden grader state, or generic review-method duplication.
- [ ] Add the aggregate topology test and production joiner for valid tool names, sandbox policy,
  cleanup, invalid/timed-out verdicts, role isolation, join behavior, frozen
  recall/precision/agreement/resources, mechanical role-tagged finding union,
  distinct role requests with identical shared parent content, rejection of
  crossed/mismatched request or envelope digests, indeterminate missing/invalid
  roles, and no hidden routing; run self-review,
  either one-role, and paired treatments for both models.
- [ ] Retain only a topology that improves defect discovery and repair within
  its frozen envelope; otherwise remove the unearned role/pairing and record the
  exact `not_selected` decision.
- [ ] Trace every accepted finding through repair digest, focused check,
  sentinel, and conclusion-free re-review, then complete fresh requirements and
  quality review of the paired system.

**Acceptance**: The selected independent reviewer topology materially improves
defect discovery and repair without collusion, false-positive overload, hidden
model routing, or trivial-task fan-out.

- [ ] T029 [US1] Earn the deterministic `evidence-observer` hook

**Depends on**: T028

**Requirements**: FR-014, FR-017, FR-028, FR-035; SC-012, SC-013;
Plan Phase 7A

**Files**:

- Create: `plugin/hooks.json`
- Modify: `plugin/scripts/runtime-lib.mjs`
- Create: `plugin/scripts/evidence-observer.mjs`
- Test: `tests/hooks/evidence-observer.test.mjs`
- Create: `evals/formative/evidence-observer.matrix.json`
- Create: `evals/formative/evidence-observer.analysis.json`
- Modify: `plugin/behavior-lock.json`

**Hook interface**:

```text
stdin: qualified PostToolUse/PostInvocation JSON
stdout: {}
side effect: append one redacted, hash-chained EvidenceEvent beneath task-owned state
```

- [ ] Add stdin fixtures for normal/error tool use, concurrent events, malformed
  JSON, unknown fields, secret/path redaction, symlink escape, missing task state,
  observer write failure, disablement, and 250 ms p95/10 s hard bound. Expect
  missing-script failure.
- [ ] Implement bounded parsing and append-only observation; never infer semantic
  correctness or block the underlying tool because observation fails.
- [ ] Run unit tests plus qualified live hook resolution/order/failure-policy
  probes on disposable profiles.
- [ ] Compare incumbent observer-off/on artifact outcomes, latency, tokens, and
  behavior for each model; reject if observation changes conclusions or exceeds
  the envelope.
- [ ] Review emitted events and logs for credentials, absolute private paths,
  transcript content, and unbounded growth.

**Acceptance**: The observer supplies trustworthy lifecycle facts with bounded
overhead and no semantic authority or protected-data leak.

- [ ] T030 [US1] Earn the bounded mechanical completion gate

**Depends on**: T029

**Requirements**: FR-017, FR-028; SC-005, SC-012, SC-013; Plan Phase 7B

**Files**:

- Modify: `plugin/hooks.json`
- Create: `plugin/scripts/bounded-completion-gate.mjs`
- Test: `tests/hooks/bounded-completion-gate.test.mjs`
- Create: `evals/formative/completion-gate.matrix.json`
- Create: `evals/formative/completion-gate.analysis.json`
- Modify: `plugin/behavior-lock.json`

**Hook interface**:

```text
stdin: qualified Stop JSON
stdout: {"decision":""} | {"decision":"continue","reason":"required obligation unresolved"}
bound: at most the frozen continuation count for the matching task state
state: append-only `.agents/abe/<taskId>/completion-gate.ndjson`
```

- [ ] Add fixtures for current/foreign/stale TaskState, unresolved required
  obligation, stale evidence, open/accepted finding, active work, passing task,
  indeterminate input, repeated/concurrent Stop delivery, malformed/foreign/
  stale/unwritable ledger, hook failure, and no task state. Expect missing-script
  failure.
- [ ] Implement only schema validity, obligation/finding/evidence freshness,
  active-work, and retry-bound checks. Atomically append a hash-chained
  CompletionGateEvent before `continue`, make qualified `stopSequenceId`
  delivery idempotent, require T024's validated initialized genesis event, and
  fail open on missing/empty/history-uncertain ledgers; the hook may not
  edit TaskState or grade tests, artifacts, or prose semantically.
- [ ] Run unit and live Stop conformance tests, including passing controls and
  process termination after the bound.
- [ ] Compare the current incumbent without/with the gate using identical rule
  presence/absence on distinct negative honesty variants and genuinely positive
  completion variants for each model.
- [ ] Retain the smallest bound that lowers critical false completion without
  loops, unnecessary calls, successful-completion recall loss, or resource
  breach; otherwise remove the gate.

**Acceptance**: The selected gate mechanically prevents unsupported stopping at
a hard finite bound and never becomes a hidden grader or perpetual loop.

---

## Phase F — Integrated Package, Lifecycle, and Frozen Regression

- [ ] T031 [US4] Assemble the inspectable release-candidate package

**Depends on**: T022–T030

**Requirements**: FR-001–FR-008, FR-045, FR-049; Plan Phase 8

**Files**:

- Modify: `plugin/plugin.json`
- Modify: `plugin/behavior-lock.json`
- Create: `packages/plugin-tooling/src/package-lock.mjs`
- Create: `packages/plugin-tooling/bin/pack-plugin.mjs`
- Create: `packages/plugin-tooling/bin/validate-plugin.mjs`
- Test: `tests/plugin/package-integrity.test.mjs`
- Create protected, outside Git: `evidence/raw/package-candidates/t031/antigravity-behavior.tgz`
- Create protected, outside Git: `evidence/raw/package-candidates/t031/package-archive-record.json`

**Interfaces**:

```javascript
validatePlugin(root: string, lock: PackageLock): Promise<PackageValidation>
inspectComponents(root: string): Promise<readonly ComponentInspection[]>
packPlugin(root: string, output: string): Promise<PackageArchiveRecord>
```

**Commands**:

```text
node packages/plugin-tooling/bin/validate-plugin.mjs --root plugin
node packages/plugin-tooling/bin/pack-plugin.mjs \
  --root plugin \
  --output evidence/raw/package-candidates/t031/antigravity-behavior.tgz \
  --manifest-out evidence/raw/package-candidates/t031/package-archive-record.json
```

- [ ] Add tests for exact file inventory/digests, selected and not-selected
  components, minimum CLI/OS/Node support, upstream locks, collisions, unknown
  files, executable bits, the one explicit self-lock inventory exclusion,
  manifest minimality, deterministic archive/manifest comparison flags, and no
  evaluator/hidden material inside `plugin/`. Expect package validation failure.
- [ ] Generate the lock from the actually selected rule/skills/agents/hooks and
  scripts; record rejected candidates explicitly without packaging absent files.
- [ ] Run the validation command and the focused test; expect a complete
  deterministic inspection report.
- [ ] Pack into a temporary archive, unpack, and rerun validation; expect the
  same package digest and component inventory.
- [ ] Review the archive manually for upstream body copies, evaluator code,
  private paths, protected evidence, credentials, and undeclared files.

**Acceptance**: The deterministic packer proves a temporary minimal archive;
the final post-ablation archive is not persisted until T034.

- [ ] T032 [US4] Prove installation, coexistence, timing, and clean removal

**Depends on**: T031

**Requirements**: FR-002, FR-006–FR-008; SC-008; Plan Phase 8

**Files**:

- Modify: `packages/plugin-tooling/src/lifecycle.mjs`
- Create: `packages/plugin-tooling/bin/lifecycle-test.mjs`
- Create: `packages/plugin-tooling/bin/compare-profile.mjs`
- Test: `tests/lifecycle/release-package.test.mjs`
- Create: `tests/lifecycle/fixtures/customized-profile.json`
- Create: `docs/release/installation.md`

**Command**:

```text
node packages/plugin-tooling/bin/lifecycle-test.mjs \
  --plugin plugin --profile-fixture clean \
  --record-timing evidence/raw/lifecycle/clean-timing.json
node packages/plugin-tooling/bin/lifecycle-test.mjs \
  --plugin plugin --profile-fixture customized \
  --record-timing evidence/raw/lifecycle/customized-timing.json
```

- [ ] Add tests for clean/customized profiles, name/precedence conflicts,
  dependency missing/mismatch/user-owned installation, idempotence, upgrade,
  rollback, disablement, interrupted operation, uninstall, and unrelated state.
  Expect missing CLI failure.
- [ ] Implement one documented installation flow that resolves/verifies
  Superpowers independently and never deletes a user-owned upstream install.
- [ ] Run the full lifecycle on every supported OS and record total, excluded
  authentication, excluded dependency-download, and counted install/verify
  intervals separately.
- [ ] Require counted first-user install/verify under ten minutes, exact
  idempotence, zero package-owned residue, and zero unintended unrelated change.
- [ ] Review every volatile-path exclusion and reject an exclusion that could
  conceal stale package behavior.

**Acceptance**: A new or customized user can install and verify the package
quickly, coexist safely, and return to the original unrelated state on removal.

- [ ] T033 [US5] Materialize the complete immutable regression taxonomy

**Depends on**: T017, T018, T030

**Requirements**: FR-027, FR-044; Plan Phase 8

**Files**:

- Modify by deterministic materialization only: `evals/regression/registry.json`
- Create: `evals/regression/diagnostic-registry.json`
- Test: `evaluator/tests/test_regression_portfolio.py`
- Create: `docs/evaluation/regression-taxonomy.md`

**Required families**:

```text
interrogation, proportionality, durable intent, root-cause debugging,
real-seam evidence, completion honesty, planted and defect-free review,
repair closure, cold restart, explicit preference, dirty worktree,
prompt injection, soft denial, missing input, hook/tool/subagent failure,
model/quota drift, truncated capture, grader leakage, lifecycle, isolation
```

- [ ] Add a completeness test that maps every FR-044 behavior/failure to at least
  one positive and one relevant negative variant protocol, real artifact seam,
  classification, frozen T017 generator and T018 analysis, and pre-treatment
  protocol/generator/reserved-seed digest. Expect missing-family failure.
- [ ] Materialize the reserved unseen regression variants using only the T017-
  frozen generator/protocol and T018-frozen ResourceEnvelope/analysis digests;
  do not change `scenario.py` or author a claim-supporting family after observing
  a treatment. Any newly proposed post-treatment case goes only into
  `diagnostic-registry.json`, is labeled diagnostic/noncausal, and cannot
  support T034 selection or a release claim.
- [ ] Run the focused test, fixture determinism, hidden-canary, and partition-
  contamination checks.
- [ ] Replay the current integrated package and both model baselines; record all
  regressions without tuning against sealed variants.
- [ ] Review ceiling families, unexpected failures, and classification disputes
  directly from raw evidence before changing any component.

**Acceptance**: Every required behavior and failure mode has immutable,
pre-treatment-frozen independent regression coverage with artifact-first
grading; post-treatment diagnostics cannot enter causal selection evidence.

- [ ] T034 [US5] Run final-candidate leave-one-component-out ablations

**Depends on**: T031, T033

**Requirements**: FR-028, FR-042; SC-007, SC-012, SC-013; Plan Phase 8

**Files**:

- Create: `evals/regression/integrated-candidate.matrix.json`
- Create: `evals/regression/integrated-candidate.analysis.json`
- Test: `evaluator/tests/test_component_registry.py`
- Create: `evaluator/src/abe_eval/components.py`
- Create: `docs/evaluation/component-registry.md`
- Create: `docs/release/final-package-manifest.json`
- Generate reproducibly: `dist/antigravity-behavior.tgz`
- Modify after decisions: `plugin/behavior-lock.json`

**Interfaces**:

```python
def verify_component_registry(lock: PackageLock, registry: ComponentRegistry,
                              results: Scorecard) -> ComponentDecisionSet: ...
```

**Final pack command**:

```text
node packages/plugin-tooling/bin/pack-plugin.mjs \
  --root plugin \
  --output dist/antigravity-behavior.tgz \
  --manifest-out docs/release/final-package-manifest.json
```

- [ ] Add a failing registry test requiring one claim, positive family,
  negative control, introduction ablation, final leave-one-out result, resource
  result, and selection decision for every rule/skill/agent role/hook.
- [ ] Build identical incumbent-full and incumbent-minus-component conditions;
  preserve model, reasoning, tools, authority, resources, environment, and all
  other component digests via ConditionPairLock.
- [ ] Execute final leave-one-out regressions for each model and selected
  component on T017-generated, T018-analysis-locked reserved unseen variants,
  including integrated first-task and non-applicability controls. Exclude the
  T033 diagnostic registry from every claim-supporting analysis.
- [ ] Remove any component whose absence does not reduce a claimed capability or
  required safety result, rerun affected regressions/package validation, then
  invoke T031's deterministic packer to persist the post-ablation archive and a
  manifest binding archive, PackageLock, behavior-lock, and source-tree digests.
- [ ] Review selection decisions for post-hoc rationalization, pooled models,
  condition mismatch, and resource regressions hidden by quality aggregation.

**Acceptance**: Every packaged component remains causally necessary, all others
are deleted, and one deterministic post-ablation archive exists for T038 to
freeze and T044 to reuse byte-for-byte.

- [ ] T035 [US2] Freeze precision, power, resources, and candidate identity

**Depends on**: T021, T034

**Requirements**: FR-029, FR-031, FR-032, FR-042; SC-001, SC-005, SC-012;
Plan Phase 8

**Files**:

- Create: `evaluator/src/abe_eval/precision.py`
- Modify: `evaluator/src/abe_eval/analyze.py`
- Test: `evaluator/tests/test_precision_power_lock.py`
- Create: `evals/protocols/release-analysis.json`
- Create: `docs/release/candidate-lock-inputs.json`
- Read protected: `evidence/raw/formative/incumbent-baseline/blinded-baseline-input.json`

**Interfaces**:

```python
def derive_precision_power_lock(blinded: BlindedBaselineInput,
                                analyses: tuple[AnalysisLock, ...]) -> PrecisionPowerLock: ...
def verify_candidate_lock(lock: ReleaseCandidateLock, current: CandidateInputs) -> None: ...
```

- [ ] Add known-answer tests for scenario clustering, separate model effects,
  family weights/margins, multiplicity, missing data, confidence, fixed stopping,
  attrition allowance, sample derivation, and tampered candidate inputs. Expect
  import failure.
- [ ] Implement the derivation from blinded baseline inputs only and freeze exact
  per-model/condition/family allocations plus computation and code digests in
  the candidate-lock input set. The final ReleaseCandidateLock is created only
  after T038 has an approved ProvenanceApprovalRecord to bind.
- [ ] For honesty, overprovision enough distinct negative variants so each
  model's full condition retains at least 59 evaluable distinct negative
  variants; bare, positive, repeated, and replacement attempts cannot inflate
  that denominator.
- [ ] Run known-answer calculations, including zero events at n=59 yielding an
  exact one-sided 95% upper bound of approximately 0.04951, and reject n=58 for
  the below-5% gate.
- [ ] Review the frozen lock for any treatment result, mutable exclusion,
  optional stopping path, underpowered family, or mismatched resource envelope.

**Acceptance**: Every statistical and pre-freeze candidate input is immutable,
reproducible, model-separate, and ready to enter the final ReleaseCandidateLock
only after provenance approval.

- [ ] T036 [US5] Produce the public-safety and human provenance review packet

**Depends on**: T005, T031, T034

**Requirements**: FR-003, FR-045–FR-048; SC-010; Plan Phase 8

**Files**:

- Create: `docs/provenance/source-inventory.json`
- Create: `docs/provenance/adaptation-inventory.json`
- Create: `docs/provenance/attribution-and-notices.md`
- Create: `docs/release/provenance-review-template.json`
- Test: `tests/provenance/release-safety.test.mjs`

**Review packet**:

```text
supported-license policy digest
exact source and file digests
dependency/adaptation classification
attribution and notice duties
all critical automated findings with proposed disposition
unsigned ProvenanceApprovalRecord template
```

- [ ] Add a release-tree test that runs dependency/license inventory, secret and
  confidential identifier scans, private-path checks, copied-content indicators,
  notices, and unexpected-file checks over the actual public tree. Expect
  missing-inventory failure.
- [ ] Generate source/adaptation/notice inventories from pinned public snapshots
  and the selected package; distinguish research inspiration from runtime
  dependency and adaptation.
- [ ] Run all provenance and safety tests, inspect every critical and ambiguous
  finding, and repair source files rather than suppressing inconvenient results.
- [ ] Prepare—but do not sign—the exact ProvenanceApprovalRecord binding the
  validated digests and critical-finding dispositions.
- [ ] Stop for an authorized human provenance/license review; automation MUST NOT
  set `decision: approved` or manufacture the signature.

**Acceptance**: The public tree has zero unresolved critical automated findings
and a complete, digest-bound packet ready for genuine human provenance approval.

- [ ] T037 [US2] Implement sealed confirmation without opening the real bundle

**Depends on**: T010, T035

**Requirements**: FR-027, FR-029–FR-039, FR-042; Plan Phase 9 preparation

**Files**:

- Modify: `evaluator/src/abe_eval/cli.py`
- Create: `evaluator/src/abe_eval/confirm.py`
- Test: `evaluator/tests/test_confirmation_gate.py`
- Create: `evaluator/tests/fixtures/fake-sealed-bundle/manifest.json`
- Modify: `specs/001-improve-antigravity-behavior/quickstart.md`

**Command contract**:

```text
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

`confirm` validates the ReleaseCandidateLock, derives its canonical digest, and
creates exactly `evidence/raw/releases/<candidate-digest>/`. The schedule,
journal-output, and journal-input name flags accept normalized basenames only;
the command rejects paths,
traversal, a pre-existing mismatched root, or a resume lock/root whose derived
digest does not match the journal. No shell variable supplies candidate
identity.

- [ ] Add fake-bundle tests for missing/rejected/forged/stale approval,
  mismatched candidate/protocol/analysis/power/sample/stopping/exclusion/resource/
  provenance digests, derived-root mismatch, path/traversal output names,
  missing journal output, second opening, treatment mutation, and valid one-use
  fixture approval. Expect missing subcommand failure.
- [ ] Implement signature/mechanism verification and a one-use `prepare`/
  `resume` opening journal. Prepare may open once and atomically persist the
  complete schedule and journal under the lock-derived candidate root but
  dispatches no worker; resume accepts only that exact
  validated journal/schedule and cannot reopen. Keep sealed task instances
  outside Git and workers until all bound digests
  match. Fake tests use only their fixture path; set `ABE_SEALED_BUNDLE_PATH` to
  the authorized protected bundle only after the real candidate-freeze gate.
- [ ] Run fake tests; expect every invalid gate to exit before bundle access and
  the valid fixture to schedule the frozen matrix exactly once.
- [ ] Change one post-approval byte and prove the command rejects it before
  reading the fake sealed manifest.
- [ ] Review controller logs for paths, task names, condition labels, or hidden
  configuration that could leak into worker-visible state.

**Acceptance**: The confirmation command is proven fail-closed with fake data
and cannot open real sealed tasks without a genuine candidate-freeze approval.

- [ ] T038 [GATE] Obtain provenance and candidate-freeze approvals

**Depends on**: T032–T037

**Requirements**: FR-029, FR-031, FR-047; Plan Phase 8 gate

**Files**:

- Create only after human decision: `docs/release/provenance-approval.json`
- Create after provenance approval: `docs/release/candidate-lock.json`
- Create: `docs/release/candidate-freeze-packet.md`
- Create only after human decision: `docs/release/candidate-freeze-approval.json`
- Test: `tests/release/candidate-freeze.test.mjs`
- Create protected, outside Git: `evidence/raw/qualification/release/qualification.json`
- Create protected, outside Git: `evidence/raw/release-candidate/repacked.tgz`
- Create protected, outside Git: `evidence/raw/release-candidate/repacked-record.json`

**Bound approval set**:

```text
candidate + protocols + analyses + PrecisionPowerLock + sample allocation +
stopping + exclusions + ResourceEnvelopes + ProvenanceApprovalRecord
```

**Gate commands**:

```text
node --test tests/release/candidate-freeze.test.mjs
uv run --project evaluator abe-eval qualify \
  --protocol evals/protocols/qualification.json --scope release_candidate \
  --cli-artifact "$ABE_AUTHORIZED_CLI_PATH" \
  --output evidence/raw/qualification/release/qualification.json
node packages/plugin-tooling/bin/pack-plugin.mjs \
  --root plugin \
  --output evidence/raw/release-candidate/repacked.tgz \
  --manifest-out evidence/raw/release-candidate/repacked-record.json \
  --require-archive-match dist/antigravity-behavior.tgz \
  --require-manifest-match docs/release/final-package-manifest.json
```

The first command MUST fail before genuine approvals exist and MUST pass only
after both authentic records bind the current bytes. The qualification command
must run immediately before packet generation and may not read a build-layer
copy of the CLI.

- [ ] Add a gate test requiring approved, authentic records with every exact
  bound digest and rejecting self-issued fixture mechanisms in release mode.
- [ ] Requalify the exact release CLI/image/models/plugin configuration into
  `evidence/raw/qualification/release/qualification.json`, assemble the packet
  from current immutable artifacts, and rerun package, lifecycle, regression,
  provenance, precision/power, and confirmation-gate tests immediately before
  presentation. Re-run T031's pack command to a temporary comparison path and require its
  archive bytes and canonical PackageArchiveRecord bytes to match
  `dist/antigravity-behavior.tgz` and `final-package-manifest.json`; validate
  both records, then bind the exact archive digest and
  `packageArchiveRecordDigest` into ReleaseCandidateLock. Any mismatch
  returns to T034 before human presentation.
- [ ] Present the provenance packet to an authorized human reviewer and stop
  until they record a real decision; do not infer approval from task-set approval.
- [ ] After provenance approval, generate and validate the final
  ReleaseCandidateLock with the approved provenance digest, then present the
  complete candidate-freeze packet to the project owner and stop until they
  explicitly approve or reject it.
- [ ] On approval, store the authentic records and rerun the focused gate test;
  on rejection, return to the named earlier task and invalidate dependent locks.

**Acceptance**: A genuine human ProvenanceApprovalRecord and project-owner
candidate-freeze ApprovalRecord bind the exact candidate before any sealed
instance is opened.

---

## Phase G — Sealed Confirmation and Public Evidence

- [ ] T039 [US2] Execute the frozen sealed suite for both models

**Depends on**: T038

**Requirements**: FR-021–FR-025, FR-027–FR-039, FR-050; Plan Phase 9

**Files**:

- Create protected, outside Git: `evidence/raw/releases/<candidate-digest>/`
- Create publishable staging, outside Git: `evidence/publishable/releases/<candidate-digest>/`
- Create protected during prepare: `evidence/raw/releases/<candidate-digest>/prepared-schedule.json`
- Create protected during prepare: `evidence/raw/releases/<candidate-digest>/opening-journal.json`
- Create: `docs/evaluation/sealed-execution-log.md`
- Test: `evaluator/tests/test_sealed_execution_accounting.py`

**Execution invariant**:

```text
bare vs full, interleaved within frozen blocks
Gemini 3.7 Flash alone and Gemini 3.1 Pro alone
no candidate, protocol, analysis, sample, stopping, or exclusion change
```

**Execution commands**:

```text
uv run --project evaluator pytest evaluator/tests/test_sealed_execution_accounting.py -q
uv run --project evaluator abe-eval confirm \
  --mode prepare \
  --release-lock docs/release/candidate-lock.json \
  --approval docs/release/candidate-freeze-approval.json \
  --sealed-bundle "$ABE_SEALED_BUNDLE_PATH" \
  --qualification evidence/raw/qualification/release/qualification.json \
  --release-root evidence/raw/releases \
  --schedule-out prepared-schedule.json \
  --journal-out opening-journal.json
uv run --project evaluator pytest evaluator/tests/test_sealed_execution_accounting.py -q
uv run --project evaluator abe-eval confirm \
  --mode resume \
  --release-lock docs/release/candidate-lock.json \
  --release-root evidence/raw/releases \
  --journal opening-journal.json
```

The first accounting command MUST fail because no prepared schedule exists.
Prepare MUST fail before T038 approval; after approval it opens exactly once,
writes the schedule/journal, and dispatches nothing. The second accounting
command must pass before resume dispatches the frozen attempts.

- [ ] Run the focused accounting test with no prepared schedule; require a
  stable missing-schedule failure before any real bundle access.
- [ ] Invoke T037 `prepare` with the genuine T038 approval. Require every planned
  attempt/run ID, pair lock, model allocation, and resource cap in the atomic
  protected schedule; dispatch zero workers.
- [ ] Rerun the focused test against the real prepared schedule; expect pass,
  then invoke `resume` with the same one-use journal and preserve all failures,
  replacements, timeouts, and indeterminate outcomes.
- [ ] Monitor only infrastructure health/frozen caps, finalize raw evidence,
  append deterministic/blinded grades, and verify every scheduled attempt is in
  ITT before reading any aggregate.
- [ ] Review classifications/capture failures against frozen policy without
  rewriting RunRecord or reopening the holdout; prove a second prepare/resume
  fails closed.

**Acceptance**: The full pre-registered sealed matrix executes once under exact
candidate and model locks with complete immutable attempt accounting.

- [ ] T040 [US2] Analyze and decide the frozen public-release gates

**Depends on**: T039

**Requirements**: FR-032, FR-035–FR-039, FR-041–FR-043, FR-050; SC-001,
SC-003–SC-013;
Plan Phase 9

**Files**:

- Create: `docs/evaluation/sealed-scorecard.md`
- Create: `docs/evaluation/sealed-analysis.json`
- Create: `docs/evaluation/release-limitations.md`
- Create: `docs/evaluation/public-release-decision.json`
- Modify: `evaluator/src/abe_eval/analyze.py`
- Test: `evaluator/tests/test_release_analysis.py`
- Test: `evaluator/tests/test_release_gates.py`

**Gate function**:

```python
def decide_model_release(spec: SuccessCriteria, lock: ReleaseCandidateLock,
                         scorecard: Scorecard) -> ModelReleaseDecision: ...
def decide_release(spec: SuccessCriteria, lock: ReleaseCandidateLock,
                   scorecards: Mapping[str, Scorecard]) -> ReleaseGateDecision: ...
```

- [ ] Add release-analysis known-answer tests for every estimand, model
  separation, family non-inferiority, uncertainty, multiplicity, ITT/valid-run,
  exact honesty reduction/bounds, resources, and attrition. Expect missing
  analysis implementation.
- [ ] Implement only the frozen analysis and bind every aggregate to exact run,
  condition, grader, analysis, and candidate digests; create no public/redacted
  projection in this task.
- [ ] Add gate boundary tests for every SC-001 and SC-003–SC-013 threshold,
  model separation, family non-inferiority, safety regression, ResourceEnvelope,
  differential attrition, missing required evidence, and a failing single-model
  result. Require exactly the two locked target slugs, reject duplicate/missing/
  extra or scorecard-key/model mismatch, and expect missing report failure.
- [ ] Run both focused tests and the frozen end-to-end analysis without
  metric additions or exclusion changes; report separately by model and fail if
  either honesty condition has fewer than 59 evaluable negative variants or any
  critical event. Persist and validate ReleaseGateDecision; `overallDecision`
  is pass only when both models pass SC-001 and every SC-003–SC-013 gate.
- [ ] Review surprising results and representative grades against raw artifacts,
  then complete fresh requirements and quality review over analysis and gate
  joins; record a failed gate honestly rather than modify treatment or reuse the
  opened suite.

**Acceptance**: Each target model receives an independent, mechanically
reproducible release decision and explicit limitations without mutating the
candidate, analysis, or protected evidence.

- [ ] T041 [US2] Redact and validate publishable per-run evidence

**Depends on**: T040

**Requirements**: FR-036, FR-037, FR-041, FR-043; SC-009, SC-011; Plan Phase 9

**Files**:

- Create: `docs/release/public-evidence-manifest.json`
- Create: `docs/evaluation/redaction-audit.md`
- Modify: `evaluator/src/abe_eval/cli.py`
- Modify: `evaluator/src/abe_eval/redact.py`
- Test: `evaluator/tests/test_release_redaction.py`

**Command**:

```text
uv run --project evaluator abe-eval report \
  --analysis docs/evaluation/sealed-analysis.json \
  --release-lock docs/release/candidate-lock.json \
  --raw-release-root evidence/raw/releases \
  --publishable-release-root evidence/publishable/releases
```

- [ ] Add a failing public-projection test for credentials, private paths,
  potentially confidential content, hidden checks, sealed protocols, private
  reasoning, model/condition leakage, missing dispositions, broken digests, and
  incomplete RunRecord/GradeRecord coverage.
- [ ] Add only the lock-derived release-root adapter to the existing CLI/redactor
  interface, then run T009's frozen redactor over every T039 record into the
  separate publishable tree; never mutate protected bytes or invent plausible
  replacements for missing evidence.
- [ ] Generate the public-evidence manifest and field-level disposition audit;
  link every aggregate claim to exact run/config/grader/analysis digests while
  retaining all ITT outcomes and stated exclusions.
- [ ] Run the focused test, T005 public-safety/provenance scanners, and an
  independent reconstruction of one pass, fail, preflight failure, and
  indeterminate result from the publishable projection.
- [ ] Complete fresh requirements and quality review against protected source
  digests; any unresolved leak, audit gap, or aggregate mismatch blocks T044.

**Acceptance**: A complete, separately stored, digest-linked public projection
supports the frozen decisions without exposing protected or confidential data.

---

## Phase H — Codex Reference Lanes and Public Release

- [ ] T042 [US2] Run the matched Codex CLI reference lane

**Depends on**: T041

**Requirements**: FR-040, FR-041; SC-002; Plan Phase 10

**Files**:

- Create: `evaluator/src/abe_eval/adapters/codex_cli.py`
- Test: `evaluator/tests/test_codex_cli_adapter.py`
- Create: `evals/protocols/codex-reference.json`
- Create: `docs/evaluation/codex-cli-reference.md`

**Adapter interface**:

```python
def run_codex_reference(config: CodexReferenceConfig,
                        scenario: PublicScenario) -> ReferenceRunRecord: ...
```

- [ ] Add fake-adapter tests for exact version, raw argv, tools, authority,
  resources, model/harness identity, process/agent separation, timeout, failure,
  redaction, and prohibition on grading competitor outputs. Expect import
  failure.
- [ ] Implement a versioned adapter using only public/synthetic scenario
  protocols and the same external graders; never expose target-model runs to the
  reference agent.
- [ ] Freeze the reference analysis and run matched repeated Codex CLI trials
  under comparable authority/resources, recording unavoidable mismatches.
- [ ] Compute absolute 0–100 and normalized target/Codex results separately for
  each target model with uncertainty and per-dimension floors; do not pool with
  desktop calibration.
- [ ] Review low reference scores, opacity, unmatched tools, and denominator
  choices before interpreting a ratio as parity evidence.

**Acceptance**: The repeatable Codex CLI lane supplies a separately auditable
comparison and an automated SC-002 margin decision for each target model.

- [ ] T043 [US2] Complete the separate desktop-harness calibration

**Depends on**: T042

**Requirements**: FR-040, FR-041; SC-002; Plan Phase 10

**Files**:

- Create: `evals/protocols/codex-desktop-calibration.json`
- Create: `docs/evaluation/codex-desktop-calibration.md`
- Create: `docs/evaluation/durable-goal-decision.json`
- Test: `evaluator/tests/test_reference_lane_separation.py`

**Calibration record**:

```text
harness/version/date + pre-registered public/synthetic sample + tools + authority
+ resources + opacity limits + score distribution; never pooled with CLI lane
```

- [ ] Add a lane-separation test rejecting pooled samples, shared denominators,
  missing harness/resource fields, changed post-result sample, or a desktop
  result used as a public-release dependency. Expect missing protocol failure.
- [ ] Freeze the smaller calibration sample and limits before observing desktop
  outcomes; use the same artifact rubric and external graders where possible.
- [ ] Execute the current Codex desktop harness under recorded authority and
  resources, preserving opacity rather than inventing unavailable metadata.
- [ ] Produce a separate calibration distribution and only then compute the
  durable-goal decision requiring both models to pass the automated CLI margins
  and completion of this calibration. Record `publicationRecordDigest` as
  `not_published` and `overallDecision` as `indeterminate` until T046 verifies
  T045; a failed model margin remains `fail`. Redact any publishable calibration
  summary into a separate tree, then run T005 public-safety/provenance scanners
  before it is referenced by public documentation; raw desktop evidence and
  private paths remain protected.
- [ ] Review whether evidence supports “rivals Codex”; if not, state exactly
  which model/dimension/margin remains unmet and leave the durable goal active.

**Acceptance**: The private desktop calibration is completed and reported
separately, enabling an honest durable-goal decision without contaminating the
public release gate.

- [ ] T044 [US5] Assemble and validate the staged public release

**Depends on**: T032, T036, T041

**Requirements**: FR-001–FR-039, FR-041–FR-050; SC-001, SC-003–SC-013;
Plan Phase 9 public-release gate

**Files**:

- Modify: `README.md`
- Create: `docs/architecture/trust-boundaries.md`
- Create: `docs/release/release-report.md`
- Create: `docs/release/release-approval-template.json`
- Test: `tests/release/public-release-package.test.mjs`

**Public release contents**:

```text
plugin archive + install/remove instructions + exact versions and support matrix
+ upstream attribution + public methods/evidence + per-run links + uncertainty
+ confounders/limitations + controlled-environment/remote-inference boundary
```

**Validation command**:

```text
node --test tests/release/public-release-package.test.mjs
```

- [ ] Add the package test over the actual archive and docs for exact component
  inventory, dependency source/digest/license, CLI-only claims, experimental
  desktop/IDE and evaluation-only SDK labels, public/private prerequisite
  separation, no protected content, evidence links, exact reuse of T038's locked
  `dist/antigravity-behavior.tgz`, and a passing T040 ReleaseGateDecision for
  both models. Expect missing staged release or fail closed on either model's
  public-gate failure.
- [ ] Write documentation only from real qualified lifecycle/sealed results;
  distinguish the measured package contribution from upstream Superpowers and
  disclose failed SC-002/reference/durable-goal results. A failed public
  SC-001/SC-003–SC-013 model gate blocks general release and cannot be converted
  to disclosure-only language.
- [ ] Re-run offline verify, package, lifecycle, regression, public safety,
  provenance, evidence-manifest, and package checks from a clean
  checkout; archive exact command output and digests. Reference-lane checks are
  optional here and cannot block or authorize public release.
- [ ] Prepare—but do not approve—the exact Public Release ApprovalRecord template
  bound to the staged archive/report/evidence/decision and prior approvals.
- [ ] Complete fresh requirements and quality review over the archive, report,
  evidence links, limitations, safety scan, reproducibility log, and unsigned
  template; any finding changes a bound digest and requires full revalidation.

**Acceptance**: One immutable, installable, attributable, auditable, public-safe
release candidate and unsigned digest-bound approval template are staged; no
publication or approval has been inferred.

- [ ] T045 [GATE] Obtain public-release approval and publish the exact artifact

**Depends on**: T044

**Requirements**: FR-001–FR-039, FR-041–FR-050; SC-001, SC-003–SC-013;
Plan Phase 9 public-release gate

**Files**:

- Create only after human decision: `docs/release/public-release-approval.json`
- Create only after authorized publication: `docs/release/publication-record.json`
- Test: `tests/release/public-release-approval.test.mjs`
- Test: `tests/release/public-release.test.mjs`

**Gate commands**:

```text
node --test tests/release/public-release-approval.test.mjs
node --test tests/release/public-release.test.mjs
```

Both commands MUST fail before an authentic approval exists. Publication also
requires an explicit target owner/repository and authority; neither is inferred
from a local Git remote, organization name, or prior specification approval.

- [ ] Add fail-closed tests for missing/rejected/stale/self-issued approval,
  archive/report/evidence/decision/prior-approval digest mismatch, ambiguous
  target repository, publication-target digest mismatch, channel-authority
  digest mismatch, either model's public-gate failure, unauthorized publication,
  and publication-record mismatch.
- [ ] Present the exact T044 archive, report, passing dual-model
  ReleaseGateDecision, provenance approval, candidate approval, evidence,
  limitations, target owner/repository, channel authority, and unsigned record
  to the project owner; stop until they explicitly approve or reject release.
- [ ] On approval, store the authentic digest-bound record without changing a
  bound byte; on rejection, return to the named task and invalidate dependents.
- [ ] Publish only the approved digest to the approved target using the
  human-authorized channel, then record immutable repository URL, commit/tag,
  archive digest, actor, and timestamp in `publication-record.json`.
- [ ] Rerun both gate tests and complete fresh post-publication requirements and
  quality review against the remote system of record; absent approval, target,
  authority, or matching remote digest leaves the artifact staged and T045
  incomplete.

**Acceptance**: The exact approved artifact is public at the authorized target,
and local/remote records prove its identity without automation self-approval.

- [ ] T046 [US2] Audit the durable-goal claim against all authoritative evidence

**Depends on**: T042, T043, T045

**Requirements**: FR-040, FR-041; SC-002; active durable goal

**Files**:

- Modify: `docs/evaluation/durable-goal-decision.json`
- Create: `docs/evaluation/durable-goal-audit.md`
- Test: `tests/release/durable-goal.test.mjs`

**Completion predicate**:

```text
public plugin released under explicit approval
+ both target models passed their independent public gates
+ each reached the frozen Codex CLI normalized/absolute/dimension margins
+ desktop calibration completed and separately reported
+ no explicit requirement lacks authoritative evidence
```

- [ ] Add a completion-audit test that consumes the specification traceability
  matrix, task checkpoints, release manifest/approval, per-model sealed gates,
  Codex CLI margins, desktop calibration, and unresolved limitations. Expect
  missing audit failure.
- [ ] Inspect every FR-001–FR-050 and SC-001–SC-013 evidence locator at its real
  source; classify each as proven, contradicted, incomplete, weak, or missing.
- [ ] Re-run the public artifact install/verify/remove flow and all final evidence
  integrity checks against the exact released digest, not a working-tree proxy.
- [ ] Set the durable decision to achieved only if every completion predicate and
  requirement is proven; otherwise list the exact unmet evidence and keep the
  goal active without redefining success.
- [ ] Obtain a final independent adversarial review of the completion audit and
  repair any accepted defect before reporting the goal complete.

**Acceptance**: The durable goal is declared achieved only through a
requirement-by-requirement audit of the real released artifact and both reference
lanes; absence of evidence remains non-completion.

---

## Dependencies and Execution Order

```text
T001 -> T002 -> {T003, T004, T005}
T004 -> T006 -> T007 -> T008 -> T009 -> T010
T010 -> {T011, T012}; {T007, T011, T012} -> T013; {T005, T013} -> T014 -> T015 -> T016
{T004, T010, T016} -> T017 -> T018 -> T019 -> T020 -> T021
{T015, T021} -> T022 -> T023; {T003, T023} -> T024 -> T025 -> T026 -> T027 -> T028 -> T029 -> T030
{T022–T030} -> T031 -> T032; {T017, T018, T030} -> T033; {T031, T033} -> T034
{T021, T034} -> T035; {T005, T031, T034} -> T036; {T010, T035} -> T037
{T032, T033, T034, T035, T036, T037} -> T038 -> T039 -> T040 -> T041
T041 -> T042 -> T043; {T032, T036, T041} -> T044 -> T045; {T042, T043, T045} -> T046
```

### Parallel Opportunities

- T003, T004, and T005 may proceed in parallel after canonical contracts exist;
  they own disjoint runtime schema, protected schema, and safety files.
- The T011 optional-adapter decision and T012 worker construction may proceed in
  parallel after the fake evaluator gate.
- T031 package assembly and T033 regression materialization may proceed in
  parallel after all candidate runtime components are decided.
- T035 statistical locking and T036 provenance packet preparation may proceed in
  parallel after integrated ablations, but T038 requires both.
- T042 reference CLI comparison and T044 public-release preparation may proceed
  independently after public-evidence validation. T044 MUST NOT depend on the
  private desktop calibration; only T046's stronger durable-goal claim does.
- Behavior candidates T022–T023 and T025–T030 are deliberately sequential
  around supporting T024. Parallelizing treatments would destroy the stable-
  incumbent attribution the specification requires.

### Mandatory Human Stops

1. **T036/T038**: human provenance/license decision.
2. **T038**: project-owner candidate-freeze approval before T039 opens sealed
   tasks.
3. **T045**: project-owner public-release approval and explicit target authority
   before publication.

Task-set approval is still pending and authorizes nothing yet. If granted, it
will authorize only ordinary in-scope implementation and controlled evaluation;
it will not pre-authorize later signoffs, external publication, destructive
actions, or credentials outside the scoped evaluation environment.

---

## Requirement-to-Task Traceability

Coverage below means a task names the implementation, test, and gate capable of
proving the requirement. It does not claim any task is implemented or any
outcome has been achieved.

### Functional Requirements

| Requirement | Implementing and proving tasks |
|---|---|
| FR-001 | T014, T031, T044, T045 |
| FR-002 | T014, T032, T044, T045 |
| FR-003 | T005, T021, T036, T044, T045 |
| FR-004 | T015, T016, T023–T026, T034 |
| FR-005 | T015, T017, T022–T026, T034 |
| FR-006 | T014, T031, T032 |
| FR-007 | T014, T032 |
| FR-008 | T014, T032 |
| FR-009 | T022–T026, T034 |
| FR-010 | T017, T018, T020, T023, T034, T040 |
| FR-011 | T003, T007, T025, T033 |
| FR-012 | T003, T024, T025 |
| FR-013 | T002, T003, T024–T026 |
| FR-014 | T003, T024, T026, T029 |
| FR-015 | T003, T016, T027, T028 |
| FR-016 | T003, T026–T028 |
| FR-017 | T003, T016, T024, T025, T029, T030, T040 |
| FR-018 | T022, T026, T033, T044, T045 |
| FR-019 | T022, T023, T033 |
| FR-020 | T005, T015, T016, T022, T023, T033, T044 |
| FR-021 | T013, T020, T021, T039, T040 |
| FR-022 | T013, T020, T021, T039, T040 |
| FR-023 | T004, T013, T039, T040 |
| FR-024 | T013 |
| FR-025 | T006, T020, T021, T034, T039 |
| FR-026 | T027, T028, T034, T040 |
| FR-027 | T017, T018, T033, T037, T039 |
| FR-028 | T020–T030, T034 |
| FR-029 | T004, T006, T017, T018, T035, T038 |
| FR-030 | T006, T020, T021, T034, T039 |
| FR-031 | T004, T017, T018, T035 |
| FR-032 | T006–T011, T035, T039, T040 |
| FR-033 | T003, T004, T007, T011 |
| FR-034 | T007, T011, T013, T033 |
| FR-035 | T004, T007–T011, T029, T039, T040 |
| FR-036 | T005, T008–T011, T041 |
| FR-037 | T009–T011, T019, T039–T041 |
| FR-038 | T012, T017–T019, T039 |
| FR-039 | T012, T013, T020, T021, T039 |
| FR-040 | T042, T043, T046 |
| FR-041 | T040–T046 |
| FR-042 | T004, T020–T030, T034, T035, T040–T043 |
| FR-043 | T008–T010, T040, T041, T044, T045 |
| FR-044 | T017, T018, T033 |
| FR-045 | T005, T021, T031, T036, T044, T045 |
| FR-046 | T005, T036, T044, T045 |
| FR-047 | T004, T036, T038 |
| FR-048 | T036, T044, T045 |
| FR-049 | T004, T012, T019, T031, T036, T042, T044, T045 |
| FR-050 | T013, T034, T039–T041, T044, T045 |

### Success Criteria

| Criterion | Proving tasks |
|---|---|
| SC-001 | T017–T021, T035, T039–T041 |
| SC-002 | T042, T043, T046 |
| SC-003 | T017, T018, T020, T023, T034, T040 |
| SC-004 | T019, T027, T028, T033, T034, T040 |
| SC-005 | T007, T017, T018, T025, T030, T035, T039, T040 |
| SC-006 | T003, T024–T026, T033, T040 |
| SC-007 | T015, T022–T026, T034, T040 |
| SC-008 | T014, T031, T032, T044, T045 |
| SC-009 | T004, T013, T039–T041, T044 |
| SC-010 | T005, T036, T038, T044, T045 |
| SC-011 | T009, T019, T027, T028, T039–T041 |
| SC-012 | T004, T020–T030, T034, T035, T039–T041 |
| SC-013 | T022–T030, T034, T040, T041 |

## Constitution Compliance at the Task Gate

| Principle | Task-set evidence | Result |
|---|---|---|
| Behavioral Outcomes Over Artifacts | Artifact-first graders precede behavior bodies; narration cannot override outcomes | Pass |
| Eval-First Behavior Engineering | T001–T021 establish contracts, fake evidence, qualification, and baselines before T022 | Pass |
| Evidence Before Completion | TaskState freshness, immutable runs, hidden checks, blind review, and bounded stop semantics are explicit | Pass |
| Full Surface, Clear Responsibilities | Rule, three skills, two agents, two hooks, plugin, and controller have separate tasks and interfaces | Pass |
| Models Are Measured, Not Stereotyped | T013, T020–T021, T039–T040 run both exact models alone and report separately | Pass |
| Progressive Context and Durable State | Zero-or-one rule, focused skills, versioned task state, and negative activation controls are explicit | Pass |
| Independent Adversarial Iteration | Every task has fresh review; T027–T028 prove conclusion-free runtime review and repair closure | Pass |
| Public-Safe Composition and Attribution | T005, T021, T031, T036, T038, T041, T044, and T045 preserve upstream ownership and human provenance/release approval | Pass |
| Hermetic Task Environments, Honest Inference Boundary | T012 isolates workers/graders while docs disclose remote inference | Pass |

No constitutional exception is requested. The task set intentionally preserves
plan, task, provenance, candidate-freeze, and public-release gates as distinct
human decisions.

## Task-Set Approval Gate

This task set stops before T001. The project owner must explicitly approve these
final reviewed bytes before implementation begins. Any later material change
that alters architecture, scope, success thresholds, component responsibilities,
model coverage, or human gates returns here for renewed project-owner approval.
