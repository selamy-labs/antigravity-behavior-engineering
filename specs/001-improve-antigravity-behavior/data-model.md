# Data Model: Improve Antigravity Engineering Behavior

**Date**: 2026-08-18

**Status**: Plan-phase contract model; implementation remains unapproved

## Modeling Principles

- Every persisted object has an explicit `schemaVersion`.
- IDs are stable, opaque strings; display names never become identity.
- Content-addressed objects carry SHA-256 digests over canonical bytes.
- Raw runs and grades are append-only. A correction creates a superseding
  object; it does not rewrite evidence.
- Agent-visible task state and protected evaluator state are separate types and
  paths.
- A process exit, agent declaration, deterministic result, and blind-review
  result are separate fields.
- Optional fields are absent only when the schema makes their inapplicability
  unambiguous; recorded run metadata uses explicit `not_applicable` values.

## Runtime Entities

### PackageLock

Companion metadata for information the official `plugin.json` cannot safely
carry.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `packageName` | string | Must match `plugin.json.name` |
| `packageVersion` | SemVer string | Required |
| `sourceRevision` | 40-character Git SHA | Required for release |
| `minimumCliVersion` | SemVer string | Frozen after qualification |
| `supportedPlatforms` | array of platform records | Each names OS, architecture, and Node range |
| `components` | array of ComponentLock | Unique by kind and name |
| `dependencies` | array of DependencyLock | Exact upstream revision and license |
| `files` | map of relative path to SHA-256 | Covers every package-owned file |
| `generatedAt` | RFC 3339 timestamp | Informational, excluded from reproducible content digest |

### ComponentLock

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `kind` | `skill`, `rule`, `agent`, `hook`, or `script` | Required |
| `name` | string | Unique with `kind` |
| `path` | normalized relative path | Must remain inside plugin root |
| `claimId` | string | Links to an EvaluationClaim |
| `defaultEnabled` | boolean | Required |
| `digest` | SHA-256 string | Required |

### DependencyLock

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `name` | string | Required |
| `sourceUrl` | HTTPS URL | Required |
| `revision` | immutable revision | Required |
| `license` | SPDX identifier | Required |
| `consumption` | `runtime`, `development`, or `research` | Required |
| `required` | boolean | Runtime missing dependencies fail visibly |
| `qualificationEvidence` | relative evidence locator or `not_qualified` | Required |

### TaskState

Agent-visible durable state created only for an applicable substantial task.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `taskId` | opaque string | Must match containing directory |
| `workspaceDigest` | SHA-256 string | Prevents adopting foreign state |
| `requestDigest` | SHA-256 string | Binds state to the initiating task |
| `workflowTier` | `trivial` or `substantial` | Durable state normally exists only for `substantial` |
| `intent` | string | Approved or bounded intent |
| `assumptions` | array of Assumption | May be empty |
| `obligations` | array of ProofObligation | At least one for substantial work |
| `iterations` | array of IterationCheckpoint | Append-only logical order |
| `reviewFindings` | array of ReviewFinding | Findings and repair closure |
| `terminalState` | TerminalState | Must agree with obligation statuses |
| `updatedAt` | RFC 3339 timestamp | Required |

The runtime serializer uses canonical key order for digests, writes a temporary
file in the same directory, fsyncs where supported, and atomically renames it.
The completion hook never edits `TaskState`; it only evaluates mechanical
conditions and emits a reason.

### CompletionGateEvent

Append-only accounting for the bounded completion continuation. The evidence
CLI writes the genesis event atomically with TaskState initialization; the hook
may append only continuation events. The ledger is stored beside, but is not
part of, `TaskState`; it has no semantic authority.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `eventId` | opaque string | Unique within the task ledger |
| `taskId` | opaque string | Must match the validated TaskState and containing directory |
| `workspaceDigest` | SHA-256 | Must match TaskState |
| `requestDigest` | SHA-256 | Must match TaskState |
| `eventKind` | `initialized` or `continued` | Exactly one initialized genesis event |
| `stopSequenceId` | string or `not_applicable` | Required only for `continued`; derived from qualified Stop input |
| `continuationOrdinal` | nonnegative integer | Zero for genesis; strictly increasing for continuations |
| `frozenBound` | nonnegative integer | Must match the selected component lock |
| `decision` | `none` or `continue` | Genesis uses `none`; only `continue` consumes the bound |
| `reasonCode` | registered mechanical reason | No semantic success judgment |
| `previousEventDigest` | SHA-256 or `genesis` | Forms a hash chain |
| `occurredAt` | RFC 3339 timestamp | Required |

TaskState initialization creates a one-line ledger whose event is
`initialized`, ordinal zero, `previousEventDigest: genesis`, and binds the task,
workspace, request, and initial frozen bound. That is the only safe first-create
path. The hook appends `continued` under an exclusive lock before emitting
`continue`. A missing/empty ledger at Stop is evidence loss, not first use, and
fails open. Repeated or concurrent delivery cannot consume beyond the bound.

### Assumption

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `id` | string | Unique within task |
| `question` | string | Scope-shaping unknown |
| `disposition` | `user_direction`, `safe_default`, `bounded_out`, or `needs_input` | Required |
| `decision` | string | Required unless `needs_input` |
| `evidence` | array of EvidenceReference | May be empty only for explicit user direction |
| `reversible` | boolean | A safe default must be reversible |
| `material` | boolean | Controls applicability scoring |

### ProofObligation

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `id` | string | Stable and unique within task |
| `requirement` | string | Observable required behavior |
| `evidenceSeam` | string | Real interface or artifact that can falsify it |
| `negativeCases` | array of strings | At least one for substantial behavioral changes |
| `authority` | string | Actions and resources allowed to discharge it |
| `required` | boolean | Required unresolved obligations block complete |
| `status` | `pending`, `passing`, `failing`, `blocked`, `indeterminate`, or `not_applicable` | Required |
| `evidence` | array of EvidenceReference | Passing requires fresh evidence |
| `lastRelevantChangeDigest` | SHA-256 or `none` | Freshness anchor |

### EvidenceReference

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `kind` | `test`, `command`, `artifact`, `diff`, `review`, or `observation` | Required |
| `locator` | workspace-relative path or run event ID | No hidden path |
| `digest` | SHA-256 string | Required when content exists |
| `observedAt` | RFC 3339 timestamp | Required |
| `afterChangeDigest` | SHA-256 or `none` | Must equal obligation anchor for fresh passing evidence |
| `result` | `pass`, `fail`, or `indeterminate` | Required |

### IterationCheckpoint

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `sequence` | positive integer | Strictly increasing |
| `scope` | string | One reviewable behavior increment |
| `changeDigest` | SHA-256 string | Required |
| `impactedObligationIds` | array of strings | Non-empty |
| `impactedEvidenceIds` | array of strings | Required after verification |
| `sentinelEvidenceIds` | array of strings | May be empty only with recorded reason |
| `result` | `passing`, `failing`, `blocked`, or `indeterminate` | Required |
| `nextAction` | string | Required unless terminal |

### ReviewFinding

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `id` | string | Stable within task |
| `reviewerRole` | `requirements` or `quality` | Required |
| `severity` | `critical`, `important`, or `minor` | Required |
| `claim` | string | Falsifiable defect statement |
| `evidence` | array of EvidenceReference | Non-empty |
| `status` | `open`, `accepted`, `rejected`, `repaired`, or `verified` | Required |
| `dispositionReason` | string | Required for rejection or closure |
| `repairChangeDigest` | SHA-256 or `none` | Required after repair |
| `verificationEvidenceIds` | array of strings | Required for `verified` |

### TerminalState

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `declared` | `complete`, `incomplete`, `blocked`, `failed`, `indeterminate`, or `needs_input` | Required |
| `reason` | string | Required |
| `unresolvedObligationIds` | array of strings | Must match required non-passing obligations |
| `activeWork` | boolean | `complete` requires false |

## Evaluation Entities

### ScenarioCard

Frozen controller-owned definition for one task instance.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `scenarioId` | string | Globally unique |
| `family` | registered TaskFamily ID | Required |
| `partition` | `formative`, `regression`, or `sealed` | Immutable after first run |
| `variantProtocolDigest` | SHA-256 or `not_applicable` | Required |
| `fixtureDigest` | SHA-256 | Required |
| `startingStateDigest` | SHA-256 | Required |
| `agentInput` | protected path reference | Never embedded in public reports for sealed tasks |
| `applicability` | map of component name to boolean | Created before execution |
| `materialAmbiguities` | protected labeled array | Required for framing families |
| `authorityManifest` | AuthorityManifest | Required |
| `resourceEnvelope` | ResourceEnvelope | Required |
| `checks` | protected array of CheckLock | Required |
| `classificationPolicyDigest` | SHA-256 | Required |
| `weight` | positive number | Frozen before confirmation |

### ConditionLock

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `conditionId` | string | E.g. `bare`, `full`, or ablation ID |
| `modelRequest` | exact CLI model slug | Required |
| `reasoningRequest` | exact CLI effort or slug | Required |
| `provider` | string | Required |
| `authenticationMode` | string | Required; never stores credentials |
| `fallbackPolicy` | literal `deny` for release evidence | Required |
| `agentSelection` | exact agent name or `not_applicable` | Required |
| `subagentSelection` | exact policy or `not_applicable` | Required |
| `rawInvocation` | argument-vector and non-secret environment projection | Required |
| `cliDigest` | SHA-256 | Required |
| `pluginDigest` | SHA-256 or `none` | Required |
| `dependencyDigests` | map | Required |
| `enabledComponents` | sorted array | Required |
| `authorityManifestDigest` | SHA-256 | Required; pair-locked before dispatch |
| `resourceEnvelopeDigest` | SHA-256 | Required; pair-locked before dispatch |
| `toolInventoryDigest` | SHA-256 | Required |
| `permissionDigest` | SHA-256 | Required |
| `environmentDigest` | SHA-256 | Required |
| `environmentQualificationDigest` | SHA-256 | Binds the reusable qualified environment |

### ConditionPairLock

Pre-dispatch proof that a baseline and treatment differ only where the frozen
comparison permits.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `pairId` | string | Required |
| `baselineConditionDigest` | SHA-256 | Required |
| `treatmentConditionDigest` | SHA-256 | Required |
| `requiredEqualFields` | array of JSON pointers | Includes model, reasoning, authority, tools, resources, and environment |
| `allowedDifferences` | array of JSON pointers | Exact treatment components only |
| `validatorDigest` | SHA-256 | Required |
| `validatedAt` | RFC 3339 timestamp | Must precede valid start |
| `result` | `pass` or `fail` | Failure prevents both agents from receiving input |

### BlockSpec

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `blockId` | opaque string | Required |
| `modelRequest` | exact model slug | One model per block |
| `scenarioDigests` | non-empty sorted array of SHA-256 | Required |
| `conditionIds` | one condition or exact matched pair | Required |
| `conditionPairLockDigest` | SHA-256 or `not_applicable` | Required for matched pair |
| `repetitions` | positive integer | Frozen |
| `randomizationSeedCommitment` | SHA-256 | Seed remains controller-owned |
| `resourceEnvelopeDigest` | SHA-256 | Required |

### MatrixLock

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `matrixId` | opaque string | Required |
| `partition` | `formative`, `regression`, or `sealed` | Required |
| `blockDigests` | non-empty ordered array of SHA-256 | Covers BlockSpecs |
| `conditionDigests` | non-empty sorted array of SHA-256 | Required |
| `analysisLockDigests` | non-empty sorted array of SHA-256 | Required |
| `environmentQualificationDigest` | SHA-256 | Required for live matrices |
| `protocolDigest` | SHA-256 | Required |
| `matrixDigest` | SHA-256 | Canonical identity excluding itself |

### AnalysisLock

Immutable per-family analysis contract created before treatment results.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `analysisId` | string | Required |
| `familyId` | string | Required |
| `unitOfAnalysis` | registered value | Required |
| `clusterKey` | `scenarioId` or stricter registered key | Required |
| `modelEffects` | `separate` for release model outcomes | Required |
| `weights` | map of scenario strata to positive numbers | Frozen |
| `missingDataPolicy` | registered policy and valid-run projection | Required |
| `multiplicityPolicy` | registered family-wise policy | Required |
| `confidenceLevel` | number | Required |
| `margins` | map of metric to lift or non-inferiority margin | Required |
| `exclusions` | closed list with reason codes | Required |
| `stoppingRule` | fixed sample or sequential rule | Required before sealed treatment |
| `resourceEnvelopeDigest` | SHA-256 | Required |
| `analysisCodeDigest` | SHA-256 | Required |
| `cohortDefinitions` | registered map of disjoint cohort IDs to inclusion rules | Required when metrics use distinct positive and negative cohorts |
| `variantReductionPolicyDigest` | SHA-256 or `not_applicable` | Required for attempt-to-variant analyses |

### PrecisionPowerLock

Immutable derivation of the release sample size, created from blinded baseline
inputs before any sealed treatment result is available.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `lockId` | opaque string | Required |
| `analysisLockDigests` | non-empty sorted array of SHA-256 | Covers every release analysis family |
| `blindedBaselineInputDigest` | SHA-256 | Required; contains no treatment outcomes |
| `estimands` | non-empty array of registered estimand IDs | Required |
| `varianceAssumptions` | registered object | Required, including source and conservative transformations |
| `clusterAssumptions` | registered object | Required, including independent unit and intra-cluster handling |
| `target` | power/minimum-effect or precision/half-width object | Required per estimand |
| `confidenceLevel` | number | Required |
| `perModelSampleSizes` | map of exact model slug to condition and family counts | Required; models remain separate |
| `scenarioAllocation` | map of family and stratum to independent variant and repetition counts | Required |
| `attritionAllowance` | frozen rate and replacement cap by reason code | Required |
| `honestyNegativeCohortDigest` | SHA-256 or `not_applicable` | Failing, missing, and indeterminate-check variants only |
| `honestyPositiveCohortDigest` | SHA-256 or `not_applicable` | Working-evidence variants used only for completion recall |
| `variantReductionPolicyDigest` | SHA-256 or `not_applicable` | Binds original/replacement attempts to one model-condition-variant outcome |
| `multiplicityPolicyDigest` | SHA-256 | Must match covered AnalysisLocks |
| `missingDataPolicyDigest` | SHA-256 | Must match covered AnalysisLocks |
| `computationMethod` | name and immutable implementation version | Required |
| `computationDigest` | SHA-256 | Covers inputs, code, and result |
| `stoppingRuleDigest` | SHA-256 | Fixed before sealed treatment |
| `honestyNegativeVariantMinimumPerModelFullCondition` | positive integer or `not_applicable` | At least 59 distinct evaluable negative variants; excludes bare, positive, repetition, and replacement counts |

### ResourceEnvelope

Frozen quality-and-cost identity for a condition profile.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `envelopeId` | string | Required |
| `quotaOrCost` | normalized cap or `not_observable` with reason | Required |
| `tokens` | per-run cap plus required `median` and `p90` reporting | Required |
| `wallTime` | per-run cap plus required `median` and `p90` reporting | Required |
| `toolCalls` | per-run cap plus required `median` and `p90` reporting | Required |
| `retries` | per-attempt cap plus required `median` and `p90` reporting | Required |
| `subagentFanOut` | per-run cap plus required `median` and `p90` reporting | Required |
| `differentialAttritionLimit` | maximum treatment-minus-baseline timeout or indeterminate rate | Required |
| `overagePolicy` | literal `fail_profile` for release evidence | Required |

### ReleaseCandidateLock

Immutable identity of the integrated package and every pre-sealed decision it
depends on. Candidate-freeze approval binds this object's digest.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `candidateId` | opaque string | Required |
| `packageDigest` | SHA-256 | Digest of the exact plugin archive |
| `packageLockDigest` | SHA-256 | Required |
| `qualificationDigest` | SHA-256 | Exact release CLI/image/model/plugin qualification |
| `conditionLockDigests` | map of model and condition to SHA-256 | Includes bare and full for each model |
| `taskFamilyProtocolDigests` | non-empty sorted array of SHA-256 | Required |
| `analysisLockDigests` | non-empty sorted array of SHA-256 | Required |
| `precisionPowerLockDigest` | SHA-256 | Required |
| `sampleAllocationDigest` | SHA-256 | Required, even when embedded in the precision/power lock |
| `stoppingRuleDigests` | non-empty sorted array of SHA-256 | Required |
| `exclusionPolicyDigests` | non-empty sorted array of SHA-256 | Required |
| `resourceEnvelopeDigests` | non-empty sorted array of SHA-256 | Required |
| `componentRegistryDigest` | SHA-256 | Binds integrated leave-one-out decisions |
| `regressionResultDigest` | SHA-256 | Required for both models |
| `lifecycleResultDigest` | SHA-256 | Required for every supported OS |
| `provenanceApprovalDigest` | SHA-256 | Must identify an approved human record |
| `frozenAt` | RFC 3339 timestamp | Informational; candidate digest excludes this field |

### ScheduledAttempt

Immutable schedule identity created before runner invocation and never mutated or
deleted. Execution progress is recorded as append-only AttemptLifecycleEvents.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `attemptId` | opaque string | Primary identity |
| `blockId` | string | Randomization block |
| `scenarioId` | string | Required |
| `conditionId` | string | Required |
| `repetition` | positive integer | Required |
| `scheduledAt` | RFC 3339 timestamp | Required |
| `randomizationProof` | digest plus ordinal | Required |
| `runId` | opaque string | Allocated with the attempt before any preflight or worker start |
| `replacementForAttemptId` | opaque string or `none` | Required; retry relation never overwrites the original |
| `retryOrdinal` | nonnegative integer | Zero for the original attempt |

### WorkerInvocation

Sanitized worker-visible invocation projected from protected controller state.
It deliberately omits attempt ID, condition ID, block/randomization identity,
comparison role, scenario labels/checks, and competing-run information.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `invocationId` | fresh opaque string | Cannot be joined to condition identity by the worker |
| `runId` | opaque string | Required for output correlation |
| `requestPath` | literal `/workspace/input/request.txt` | Required |
| `requestDigest` | SHA-256 | Agent-visible request only |
| `fixtureDigest` | SHA-256 | Agent-visible starting fixture |
| `authorityManifestDigest` | SHA-256 | Matches mounted authority file |
| `resourceCaps` | worker-enforceable subset of ResourceEnvelope | No aggregate comparison data |
| `toolPermissionProjection` | closed non-secret object | Required |
| `cliPath` | literal `/opt/antigravity/bin/agy` | Read-only runtime mount |
| `cliDigest` | SHA-256 | Validated before worker start |
| `environmentQualificationDigest` | SHA-256 | Required |
| `outputPath` | literal `/workspace/output` | Required |

### AttemptLifecycleEvent

Append-only execution event. Folding events by sequence yields current lifecycle
state without rewriting ScheduledAttempt.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `attemptId` | opaque string | Required |
| `sequence` | nonnegative integer | Starts at zero and increases by one |
| `phase` | `scheduled`, `preflight`, `valid_started`, `execution_terminal`, or `run_finalized` | Must follow the declared transition graph |
| `terminalKind` | `none`, `preflight_failed`, `agent_finished`, `product_timeout`, `capture_indeterminate`, or `adapter_failure` | Non-`none` only for `execution_terminal` |
| `occurredAt` | RFC 3339 timestamp | Required |
| `evidenceDigest` | SHA-256 | Binds the evidence responsible for the transition |

### RunRecord

Immutable record of one scheduled attempt, including failure before an ordinary
agent output exists.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `runId` | opaque string | Required |
| `attemptId` | string | One-to-one with ScheduledAttempt |
| `conditionDigest` | SHA-256 | Required |
| `scenarioDigest` | SHA-256 | Required |
| `environmentQualificationDigest` | SHA-256 | Reusable environment qualification used by the condition |
| `attemptQualification` | AttemptQualificationRecord | Records all seven preflights and valid-start boundary |
| `observedModel` | ObservedModel | Explicit strongest evidence and limitations |
| `processState` | ProcessState | Exit, signal, timeout, and timestamps |
| `agentDeclaredState` | terminal label or `none` | Separate from process |
| `inputPermissionState` | normalized label | Required |
| `infrastructureValidity` | normalized label | Required |
| `artifactManifestDigest` | SHA-256 or `none` | Required |
| `transcriptDigest` | SHA-256 or `none` | Required |
| `eventStreamDigest` | SHA-256 or `none` | Required |
| `consumption` | ConsumptionRecord | Required, with explicit unavailable fields |
| `classification` | frozen Classification | Required |
| `rawEvidenceLocator` | protected content-addressed path | Required |
| `redactedEvidenceLocator` | path or `not_redacted` | Required |

### UnclassifiedStagedAttemptOutcome

Protected runner output after `execution_terminal` and before the frozen
classification decision table is applied.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `attemptId` | opaque string | Must match ScheduledAttempt |
| `runId` | opaque string | Must match ScheduledAttempt |
| `conditionDigest` | SHA-256 | Copied from validated controller input |
| `scenarioDigest` | SHA-256 | Copied from validated controller input |
| `environmentQualificationDigest` | SHA-256 | Copied from validated controller input |
| `lifecycleEventDigests` | non-empty ordered array of SHA-256 | Ends at `execution_terminal` |
| `attemptQualification` | AttemptQualificationRecord | Required |
| `observedModel` | ObservedModel | Required |
| `processState` | ProcessState | Required |
| `agentDeclaredState` | terminal label or `none` | Required |
| `inputPermissionState` | normalized label | Required |
| `infrastructureValidity` | normalized label | Required |
| `consumption` | ConsumptionRecord | Required |
| `stagingManifestDigest` | SHA-256 | Covers every staged path and explicit missing-output marker |

### StagedAttemptOutcome

Protected pre-import object produced by the runner after `execution_terminal`.
It is not a RunRecord and cannot be graded or aggregated. The evidence importer
validates it against the immutable attempt and lifecycle chain, imports raw
bytes, then consumes it exactly once to create `run.json`.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `attemptId` | opaque string | Must match ScheduledAttempt |
| `runId` | opaque string | Must match ScheduledAttempt |
| `conditionDigest` | SHA-256 | Must match the supplied ConditionLock |
| `scenarioDigest` | SHA-256 | Must match the supplied ScenarioCard |
| `environmentQualificationDigest` | SHA-256 | Must match the supplied EnvironmentQualificationRecord |
| `lifecycleEventDigests` | non-empty ordered array of SHA-256 | Ends at `execution_terminal`, never `run_finalized` |
| `attemptQualification` | AttemptQualificationRecord | Required |
| `observedModel` | ObservedModel | Required |
| `processState` | ProcessState | Required |
| `agentDeclaredState` | terminal label or `none` | Required |
| `inputPermissionState` | normalized label | Required |
| `infrastructureValidity` | normalized label | Required |
| `consumption` | ConsumptionRecord | Required |
| `classification` | Classification | Frozen before import |
| `unclassifiedOutcomeDigest` | SHA-256 | Binds the exact input passed to classify |
| `stagingManifestDigest` | SHA-256 | Covers every staged path and explicit missing-output marker |

### ProcessState

Process evidence is descriptive and cannot determine task success by itself.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `workerProcessState` | `not_started`, `started`, or `terminated` | Required |
| `controllerExitCode` | integer | Required |
| `workerExitCode` | integer or `none` | `none` when no worker starts or a signal prevents an exit code |
| `signal` | string or `none` | Required |
| `timeout` | boolean | Required |
| `startedAt` | RFC 3339 timestamp or `none` | Required |
| `endedAt` | RFC 3339 timestamp | Required |
| `stderrDigest` | SHA-256 or `none` | Required |

### EnvironmentQualificationRecord

Reusable qualification for an exact CLI, image, platform, model set, and
customization configuration. It never contains a per-attempt valid-start time.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `qualificationId` | opaque string | Required |
| `scope` | `cli_core` or `release_candidate` | Required |
| `cliVersion` | SemVer | Required |
| `cliDigest` | SHA-256 | Required |
| `imageDigest` | SHA-256 | Required |
| `platform` | OS and architecture record | Required |
| `modelConfigurationEvidence` | map of exact model/effort request to observed evidence | Required |
| `unknownModelFallbackEvidence` | evidence digest | Required |
| `structuredCaptureEvidence` | evidence digest | Required |
| `pluginLifecycleEvidence` | evidence digest or `not_applicable` | `not_applicable` allowed only for `cli_core` |
| `customizationConformanceEvidence` | evidence digest or `not_applicable` | `not_applicable` allowed only for `cli_core` |
| `authorityToolCapabilityEvidence` | evidence digest | Required |
| `supportDecision` | `qualified` or `rejected` | Required |
| `limitations` | array of strings | Required, may be empty |
| `qualifiedAt` | RFC 3339 timestamp | Required |

### QualificationProtocol

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `protocolId` | opaque string | Required |
| `cliVersionConstraint` | exact SemVer or closed range | Required |
| `cliArtifactDigest` | SHA-256 | Required |
| `imageDigest` | SHA-256 | Required |
| `platforms` | non-empty array of OS/architecture records | Required |
| `modelRequests` | exact model/reasoning pairs | Both target models required for release scope |
| `fallbackProbes` | non-empty closed array | Unknown model and altered reasoning included |
| `structuredCaptureContractDigest` | SHA-256 | Required |
| `requiredPreflights` | exact seven registered preflight IDs | Closed set |
| `customizationScope` | `cli_core` or `release_candidate` | Required |
| `protocolDigest` | SHA-256 | Canonical identity excluding itself |

### AttemptQualificationRecord

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `authentication` | pass/fail plus evidence digest | Required |
| `fixtureProvisioning` | pass/fail plus evidence digest | Required |
| `modelPreflight` | pass/fail plus evidence digest | Required |
| `fallbackProbe` | pass/fail plus evidence digest | Required |
| `pluginComponentDiscovery` | pass/fail plus evidence digest | Required |
| `structuredCapturePreflight` | pass/fail plus evidence digest | Required |
| `authorityToolInventory` | pass/fail plus evidence digest | Required |
| `validStartAt` | timestamp or `none` | Set immediately before agent input |

### Classification

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `class` | `product_failure`, `infrastructure_failure`, `safety_refusal`, `indeterminate`, or `gradable` | Frozen vocabulary |
| `reasonCode` | registered enum | Required |
| `policyDigest` | SHA-256 | Required |
| `retryEligible` | boolean | Derived from frozen policy |
| `countsInIntentionToTreat` | literal `true` | Every scheduled attempt counts |
| `countsInValidRun` | boolean | Derived, never hand-edited |

### GradeRecord

Appended beneath a run and identified by grader digest.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `gradeId` | opaque string | Required |
| `runId` | string | Required |
| `graderDigest` | SHA-256 | Allows multiple immutable grades |
| `conditionBlind` | literal `true` for release judgment | Required |
| `modelBlind` | literal `true` for release judgment | Required |
| `deterministicChecks` | array of CheckResult | Required |
| `reviewerGrades` | array of ReviewerGrade | Two for pre-registered release sample |
| `adjudication` | object or `not_required` | Frozen rule |
| `outcome` | `pass`, `fail`, or `indeterminate` | Required |
| `metrics` | map of registered numeric or boolean metrics | No open-ended release metrics |
| `diagnostics` | TrajectoryDiagnostics | Non-primary |

### Scorecard

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `scorecardId` | opaque string | Required |
| `candidateDigest` | SHA-256 or `not_applicable` | Required |
| `analysisLockDigest` | SHA-256 | Required |
| `modelRequest` | exact model slug | One model per release scorecard |
| `attemptProjectionDigest` | SHA-256 | Binds scheduled/ITT/valid-run rows |
| `metrics` | closed map of registered metric to value/uncertainty | Required |
| `resourceSummary` | median/p90 plus envelope result | Required |
| `attritionSummary` | counts/rates by frozen reason | Required |
| `graderAgreement` | registered agreement object | Required |
| `limitations` | array of strings | Required |

### SafetyReport

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `reportId` | opaque string | Required |
| `rootDigest` | SHA-256 | Exact scanned public tree |
| `policyDigest` | SHA-256 | Required |
| `findings` | array of closed finding records | Stable IDs/severity/location/evidence |
| `criticalOpenCount` | nonnegative integer | Derived |
| `scannerDigests` | non-empty sorted array of SHA-256 | Required |

### ProvenanceInventory

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `inventoryId` | opaque string | Required |
| `rootDigest` | SHA-256 | Exact inventoried tree |
| `sources` | closed array of source URL/revision/license/consumption records | Required |
| `adaptations` | closed array of source-to-local classifications | Required |
| `noticeDigest` | SHA-256 | Required |
| `policyDigest` | SHA-256 | Required |

### AuthorityManifest

Closed worker authority supplied before input visibility.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `manifestId` | opaque string | Required |
| `allowedActions` | sorted array of registered actions | Deny by default |
| `allowedResources` | sorted array of normalized resource locators | No wildcard roots |
| `networkPolicyDigest` | SHA-256 | Required |
| `credentialGrantDigests` | sorted array of non-secret grant digests | May be empty |
| `expiresAt` | RFC 3339 timestamp or `not_applicable` | Required |

### CheckLock

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `checkId` | opaque string | Unique within a scenario |
| `kind` | registered deterministic check kind | Required |
| `implementationDigest` | SHA-256 | Required |
| `inputDigest` | SHA-256 | Hidden controller-owned input |
| `expectedResultDigest` | SHA-256 | Hidden controller-owned oracle |
| `timeoutMs` | positive integer | Required |

### ClassificationPolicy

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `policyId` | opaque string | Required |
| `reasonCodes` | closed ordered decision table | Exhaustive and non-overlapping |
| `replacementCaps` | map of eligible reason code to nonnegative integer | Frozen before scheduling |
| `validRunProjection` | registered rule | Required |
| `policyDigest` | SHA-256 | Covers canonical policy bytes |

### ObservedModel

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `requestedModel` | exact CLI slug | Required |
| `requestedReasoning` | exact effort/slug | Required |
| `servedIdentityEvidence` | ordered array of source, value, and digest | Strongest available observations first |
| `fallbackProbeResult` | `pass`, `fail`, or `indeterminate` plus digest | Required |
| `conclusion` | exact observed identity or `unobservable` | Never inferred beyond evidence |
| `limitations` | array of strings | Required |

### ConsumptionRecord

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `inputTokens` | nonnegative integer or `unavailable` | Required |
| `outputTokens` | nonnegative integer or `unavailable` | Required |
| `cachedTokens` | nonnegative integer or `unavailable` | Required |
| `toolCalls` | nonnegative integer or `unavailable` | Required |
| `subagentCalls` | nonnegative integer or `unavailable` | Required |
| `wallTimeMs` | nonnegative integer | Controller-observed |
| `quotaOrCost` | normalized value or `unavailable` | Required |
| `sourceEvidenceDigest` | SHA-256 | Required |

### CheckResult

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `checkId` | opaque string | Matches CheckLock |
| `implementationDigest` | SHA-256 | Must match the lock |
| `outcome` | `pass`, `fail`, or `indeterminate` | Required |
| `reasonCode` | registered code | Required |
| `evidenceDigest` | SHA-256 | Required |
| `durationMs` | nonnegative integer | Diagnostic only |

### ReviewerGrade

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `reviewerId` | opaque pseudonymous ID | Required |
| `rubricDigest` | SHA-256 | Required |
| `calibrationDigest` | SHA-256 | Required |
| `dimensionScores` | closed map of dimension to anchored score | Required |
| `findingIds` | sorted array of finding IDs | May be empty |
| `overall` | anchored score or `indeterminate` | Required |
| `limitations` | array of strings | Required |

### TrajectoryDiagnostics

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `firstDivergenceCode` | registered code or `none` | Diagnostic only |
| `recoveryCount` | nonnegative integer or `unavailable` | Diagnostic only |
| `repeatedWorkCount` | nonnegative integer or `unavailable` | Diagnostic only |
| `permissionEvents` | nonnegative integer or `unavailable` | Diagnostic only |
| `sourceDigest` | SHA-256 | Required |

### EvidenceEvent

Agent-visible, append-only hook observation. It records mechanics, never whether
the task is correct.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `eventId` | opaque string | Required |
| `taskId` | opaque string | Must match containing task state |
| `sequence` | nonnegative integer | Strictly increasing |
| `eventKind` | registered tool/process lifecycle kind | Required |
| `toolName` | string or `not_applicable` | Required |
| `resultClass` | `success`, `error`, or `indeterminate` | Mechanical only |
| `redactedPayloadDigest` | SHA-256 | Payload is redacted before append |
| `previousEventDigest` | SHA-256 or `genesis` | Hash-chain link |
| `occurredAt` | RFC 3339 timestamp | Required |

### BlindedBaselineInput

Protected, pre-release statistical input produced by a contemporaneous
pair-interleaved bare-versus-incumbent block. Condition labels and outcomes are
masked; it contains no local-treatment or sealed-treatment result.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `inputId` | opaque string | Required |
| `sourceAttemptDigests` | non-empty sorted array of SHA-256 | Bare and incumbent pilot attempts only |
| `analysisLockDigests` | non-empty sorted array of SHA-256 | Pre-treatment locks only |
| `maskingProtocolDigest` | SHA-256 | Required |
| `clusterSummaries` | blinded variance/attrition/resource summaries by model and family | No condition labels |
| `honestyCohortSummaries` | blinded disjoint positive/negative counts | Required |
| `createdAt` | RFC 3339 timestamp | Informational |

### ApprovalRecord

Human gate artifact used before a one-use protected suite can open.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `approvalId` | opaque string | Required |
| `gate` | `candidate_freeze` or `public_release` | Required |
| `owner` | recorded project-owner identity or approved pseudonymous key ID | Required |
| `decision` | `approved` or `rejected` | Required |
| `boundDigests` | gate-specific closed map | Candidate freeze binds candidate, qualification, protocol, analysis, power/precision, sample, stopping, exclusion, resource, and provenance approval; public release binds final archive, release report, public-evidence manifest, release decision, provenance approval, and candidate-freeze approval |
| `publicationTargetDigest` | SHA-256 or `not_applicable` | Public release binds exact owner/repository; candidate freeze uses `not_applicable` |
| `publicationChannelAuthorityDigest` | SHA-256 or `not_applicable` | Public release binds authorized channel and actor/grant; candidate freeze uses `not_applicable` |
| `approvedAt` | RFC 3339 timestamp | Required |
| `signature` | signature record or explicitly documented local approval mechanism | Required |
| `supersedes` | approval ID or `none` | Required |

### ProvenanceApprovalRecord

Human judgment that automated safety and inventory checks cannot replace.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `approvalId` | opaque string | Required |
| `reviewer` | approved reviewer identity or key ID | Required |
| `supportedLicensePolicyDigest` | SHA-256 | Required |
| `sourceInventoryDigest` | SHA-256 | Required |
| `adaptationInventoryDigest` | SHA-256 | Required |
| `attributionAndNoticeDigest` | SHA-256 | Required |
| `criticalFindingResolutions` | map of finding ID to signed disposition | All critical findings present |
| `decision` | `approved` or `rejected` | Required |
| `approvedAt` | RFC 3339 timestamp | Required when approved |
| `signature` | signature record or documented local approval mechanism | Required |

### ReleaseGateDecision

Closed public-gate decision produced from the frozen sealed analysis before any
approval or publication. General release passes only if both target models pass
every public criterion. SC-002 reference parity is outside this decision and
affects only the stronger durable-goal claim.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `decisionId` | opaque string | Required |
| `candidateDigest` | SHA-256 | Must match ReleaseCandidateLock |
| `analysisDigest` | SHA-256 | Exact sealed analysis |
| `publicCriteriaDigest` | SHA-256 | Covers SC-001 and SC-003–SC-013 |
| `perModelDecisions` | closed map of both exact model slugs to pass/fail plus criterion results | Both entries required; never pooled |
| `overallDecision` | `pass` or `fail` | Pass iff both per-model decisions pass every public criterion |
| `blockingCriteria` | sorted array of model/criterion IDs | Empty iff pass |
| `limitationsDigest` | SHA-256 | Required |
| `decidedAt` | RFC 3339 timestamp | Informational |

### ReviewerVerdict

Agent-visible reviewer output validated before the worker uses it.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `reviewerRole` | `requirements` or `quality` | Must match invoked agent |
| `artifactDigest` | SHA-256 | Binds review to actual artifact |
| `obligationDigest` | SHA-256 | Binds the approved obligation set |
| `verificationInterfaceDigest` | SHA-256 | Required |
| `authorityDigest` | SHA-256 | Binds the review authority envelope |
| `findings` | array of ReviewerFinding | May be empty on defect-free tasks |
| `verdict` | `pass`, `fail`, or `indeterminate` | Required |
| `inspectedEvidence` | array of EvidenceReference | Non-empty unless indeterminate before access |
| `limitations` | array of strings | Required, may be empty |

### ReviewPackageInput

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `reviewerRole` | `requirements` or `quality` | Required |
| `artifactRoot` | normalized path inside declared workspace | Required |
| `artifactDigest` | SHA-256 | Required |
| `obligations` | non-empty array of ProofObligation | Approved set only |
| `obligationDigest` | SHA-256 | Required |
| `verificationInterface` | closed read-only interface record | Required |
| `verificationInterfaceDigest` | SHA-256 | Required |
| `authorityManifest` | AuthorityManifest | Read-only review authority |
| `authorityDigest` | SHA-256 | Required |

### ReviewRequest

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `requestId` | opaque string | Required |
| `reviewerRole` | `requirements` or `quality` | Required |
| `artifactDigest` | SHA-256 | Required |
| `obligationDigest` | SHA-256 | Required |
| `verificationInterfaceDigest` | SHA-256 | Required |
| `authorityDigest` | SHA-256 | Required |
| `packageManifestDigest` | SHA-256 | Exact minimum review package |
| `reviewRequestDigest` | SHA-256 | Canonical identity excluding itself |

### ReviewerFinding

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `id` | opaque string | Unique within verdict |
| `severity` | `critical`, `important`, or `minor` | Required |
| `claim` | falsifiable defect statement | Required |
| `evidence` | non-empty array of EvidenceReference | Required |
| `affectedObligationIds` | sorted array of IDs | May be empty only for quality/safety finding |
| `suggestedFalsification` | string | Required |

### ReviewJoinRecord

Agent-visible mechanical join of independently validated reviewer verdicts.
It does not merge conclusions or decide whether a finding is accepted.

| Field | Type | Rule |
|---|---|---|
| `schemaVersion` | literal `1` | Required |
| `reviewRequestDigest` | SHA-256 | Both verdicts must bind this request package |
| `requirementsVerdictDigest` | SHA-256 or `indeterminate` | Required |
| `qualityVerdictDigest` | SHA-256 or `indeterminate` | Required |
| `roleSeparationEvidenceDigest` | SHA-256 | Proves separate invocations/no cross-output input |
| `findings` | ordered role-tagged finding references | No semantic deduplication |
| `joinState` | `complete` or `indeterminate` | Any invalid/missing role is indeterminate |
| `limitations` | array of strings | Required |

## State Transitions

### Runtime task

```text
unclassified
  -> trivial -> verified terminal state
  -> substantial -> framed -> obligations_active
       -> iteration_in_progress -> review_pending
       -> repair_in_progress -> review_pending
       -> complete | incomplete | blocked | failed | indeterminate | needs_input
```

`complete` is valid only when every required obligation is `passing`, every
accepted material finding is `verified`, evidence is fresh, and no work is
active. The completion hook can refuse one stop attempt within the frozen bound,
but cannot change semantic statuses. Its authoritative count is the validated
CompletionGateEvent hash chain, never a mutable field in TaskState.

### Scheduled evaluation attempt

```text
immutable ScheduledAttempt(runId allocated)
  + lifecycle event: scheduled
  -> lifecycle event: preflight
       -> lifecycle event: execution_terminal(preflight_failed)
       -> lifecycle event: valid_started(occurredAt = validStartAt)
            -> lifecycle event: execution_terminal(agent_finished)
            -> lifecycle event: execution_terminal(product_timeout)
            -> lifecycle event: execution_terminal(capture_indeterminate)
            -> lifecycle event: execution_terminal(adapter_failure)
  -> runner writes UnclassifiedStagedAttemptOutcome
  -> frozen classifier writes StagedAttemptOutcome
  -> evidence importer atomically writes RunRecord
  -> lifecycle event: run_finalized

finalized RunRecord
  -> zero or more immutable GradeRecords appended by grader digest
```

Every terminal path reaches `run_finalized`, including controller-contract
failure before a worker starts; that path creates a RunRecord whose ProcessState
is `workerProcessState: not_started`. No transition deletes or replaces an
attempt or lifecycle event. A retry is a new ScheduledAttempt linked through
`replacementForAttemptId`. The `valid_started` event time and
AttemptQualificationRecord `validStartAt` must agree. Grading never mutates the
ScheduledAttempt, lifecycle events, or RunRecord.

## Trust Boundaries

- `plugin/` and task-state files are agent-visible.
- Scenario labels, hidden checks, condition locks, randomization, raw competing
  runs, and release rubrics are controller-only.
- Reviewer agents see the minimum conclusion-free package; they do not see
  hidden grader state.
- Redaction reads protected evidence and writes a new publishable tree; it never
  mutates protected evidence.
