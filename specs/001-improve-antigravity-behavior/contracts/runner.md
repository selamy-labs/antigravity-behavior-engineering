# Runner Contract

## Controller Invocation

The protected controller allocates a future RunRecord identity for every
ScheduledAttempt and invokes at most one worker process for it. `run-attempt`
stages raw output plus an UnclassifiedStagedAttemptOutcome and append-only
lifecycle events through `execution_terminal`; the frozen classifier then
writes a StagedAttemptOutcome. Neither step writes `run.json`:

```text
abe-eval run-attempt \
  --attempt <attempt.json> \
  --condition <condition-lock.json> \
  --pair <condition-pair-lock.json> \
  --scenario <scenario-card.json> \
  --raw-root <protected-run-root>
```

The controller creates `attempt.json`, including `runId`, before preflight or
worker start and appends lifecycle events without rewriting it. It projects a
separate WorkerInvocation for the worker; ScheduledAttempt and `/controller`
are never mounted. The worker may read only WorkerInvocation plus the
agent-visible projection of the scenario card. Hidden checks,
applicability labels, condition names, randomization, competing runs, and grader
configuration are not mounted.

The evidence-store importer is the sole writer of the atomic immutable
`run.json` and the subsequent `run_finalized` lifecycle event. Before either
member of a matched pair receives agent input, the controller
validates the ConditionPairLock. Model, reasoning, authority, tools,
ResourceEnvelope, and environment fields must be identical; only the explicitly
listed treatment component paths may differ. A failed pair exits before valid
start and neither member enters treatment execution. Both preallocated attempts
still stage explicit preflight-failure outcomes with
`workerProcessState: not_started`; the importer finalizes their RunRecords.

## Worker Inputs

The worker receives these immutable mounts or content-addressed references:

- fixture repository at `/workspace/repo`;
- fresh Antigravity profile at `/workspace/profile`;
- sanitized invocation at `/workspace/input/worker-invocation.json`;
- sanitized qualification projection at
  `/workspace/input/qualification-lock.json` for image/CLI digest checks;
- selected plugin condition at `/workspace/plugin-condition` or `none`;
- agent-visible task request at `/workspace/input/request.txt`;
- authority manifest at `/workspace/input/authority.json`;
- authorized CLI mounted read-only at `/opt/antigravity/bin/agy`, with its digest
  validated against the EnvironmentQualificationRecord before every attempt;
- writable evidence staging at `/workspace/output`;
- scoped authentication provided outside the image.

WorkerInvocation contains no attempt/block/condition/comparison identity,
randomization proof, hidden scenario label, or controller path. The entrypoint
accepts only `--invocation /workspace/input/worker-invocation.json`; passing a
ScheduledAttempt or controller-owned path is a contract failure before valid
start.

The worker is disposable and never mounts the operator's ordinary home,
workspace, Antigravity state, Gemini state, `.gemini` tree, rules, skills,
agents, hooks, plugins, caches, conversations, project state, credential stores,
or Docker socket. It runs as non-root with dropped Linux capabilities,
`no-new-privileges`, read-only runtime mounts except for declared workspace
scratch/output paths, and no host control-plane socket. Authentication is a
minimal runtime secret supplied by the controller outside agent-visible evidence
and is never copied into the image, repository, transcripts, or publishable
projection.

The worker network policy permits only endpoints required for authenticated
Antigravity inference and configured dependency installation during a dedicated
qualification phase. Behavioral runs use already pinned images and plugins.

## Antigravity Invocation

The adapter constructs an argument vector without shell interpolation. The
primary capture format is:

```text
/opt/antigravity/bin/agy -p <request> \
  --model <exact-model-slug> \
  --effort <exact-effort> \
  --output-format stream-json \
  --log-file <worker-log-path> \
  --timeout <frozen-seconds>
```

The exact flags are accepted only after live qualification on the pinned CLI.
Permission mode, execution mode, skill expansion, slash-command policy, and
agent selection are explicit arguments or configuration recorded in the
ConditionLock. No runner default may change treatment identity silently.

The stream must contain exactly one `init` event before ordinary steps and one
terminal `result` event. The adapter preserves every line before parsing. It
records malformed, duplicate, missing, or out-of-order terminal events rather
than fabricating success.

## Valid-Start Boundary

AttemptQualificationRecord `validStartAt` and the matching `valid_started`
lifecycle event are written immediately before the request becomes visible to
the agent and only after all of these pass:

1. authentication probe;
2. fixture and starting-state verification;
3. exact model and reasoning preflight;
4. unknown-model fail-closed probe for the environment block;
5. plugin/component discovery verification;
6. structured-stream capture preflight;
7. authority and tool-inventory verification.

Failure before this boundary is classified by the frozen infrastructure policy.
Failure after it is not converted to infrastructure merely because `agy` exits
non-zero.

## Worker Outputs

The worker writes only beneath `/workspace/output`:

```text
output/
├── raw-stream.ndjson
├── stdout.txt
├── stderr.txt
├── process.json
├── observed-config.json
├── artifact-manifest.json
├── repository-before.json
├── repository-after.json
├── plugin-discovery.json
└── hook-events.ndjson
```

The controller hashes and imports the directory into protected content-addressed
storage. Missing output files remain explicit in RunRecord; the controller never
creates plausible empty replacements.

## Exit Semantics

The `run-attempt` adapter uses these exits for controller/worker health only:

| Exit | Meaning |
|---:|---|
| 0 | Attempt record and available raw evidence were finalized; task may have passed or failed |
| 64 | Controller input contract invalid before worker start; the preallocated attempt and RunRecord still finalize with `workerProcessState: not_started` |
| 70 | Adapter internal failure; preserve partial evidence and classify from the valid-start boundary |
| 124 | Frozen timeout reached; preserve process tree and partial evidence |

The controller does not infer task success from exit 0. No exit path erases a
ScheduledAttempt. A retry allocates a new attempt and records
`replacementForAttemptId`; graders append GradeRecords after run finalization
without mutating raw evidence.
