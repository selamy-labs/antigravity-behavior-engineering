import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { constants as fsConstants } from "node:fs";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  appendEvidenceObservation,
  applyTaskStatePatch,
  canonicalBytes,
  initializeTaskState,
  parseEvidenceEvent,
  sha256Digest,
  writeCanonicalAtomic,
} from "../../plugin/scripts/runtime-lib.mjs";

const repoRoot = path.resolve(new URL("../..", import.meta.url).pathname);
const pluginRoot = path.join(repoRoot, "plugin");
const hooksPath = path.join(pluginRoot, "hooks.json");
const observerPath = path.join(pluginRoot, "scripts", "evidence-observer.mjs");
const matrixPath = path.join(repoRoot, "evals", "formative", "evidence-observer.matrix.json");
const repairMatrixPath = path.join(repoRoot, "evals", "formative", "evidence-observer.repair-matrix.json");
const liveHookRepairMatrixPath = path.join(repoRoot, "evals", "formative", "evidence-observer.live-hook-repair-matrix.json");
const analysisPath = path.join(repoRoot, "evals", "formative", "evidence-observer.analysis.json");
const lockPath = path.join(pluginRoot, "behavior-lock.json");
const taskId = "T029-fixture";
const workspaceDigest = "sha256:" + "0".repeat(64);
const requestDigest = "sha256:" + "1".repeat(64);
const changeDigest = "sha256:" + "2".repeat(64);

const readJson = async (file) => JSON.parse(await fs.readFile(file, "utf8"));
const taskRoot = (root) => path.join(root, ".agents", "abe", taskId);
const statePath = (root) => path.join(taskRoot(root), "state.json");
const ledgerPath = (root) => path.join(taskRoot(root), "evidence-events.ndjson");
const readLedger = async (root) => (await fs.readFile(ledgerPath(root), "utf8"))
  .trimEnd()
  .split("\n")
  .map(JSON.parse);

const withWorkspace = async (fn) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "abe-evidence-observer-"));
  try {
    return await fn(root);
  } finally {
    await fs.chmod(taskRoot(root), 0o700).catch(() => {});
    await fs.rm(root, { recursive: true, force: true });
  }
};

const prepareTask = async (root) => {
  const initialized = await initializeTaskState({ root, taskId, workspaceDigest, requestDigest });
  const patch = {
    schemaVersion: 1,
    taskId,
    workspaceDigest,
    requestDigest,
    baseStateDigest: initialized.stateDigest,
    updatedAt: "2026-08-23T00:00:00Z",
    operations: [
      { schemaVersion: 1, op: "setWorkflowTier", value: "substantial" },
      { schemaVersion: 1, op: "setIntent", value: "Exercise deterministic observation." },
      {
        schemaVersion: 1,
        op: "appendObligation",
        value: {
          schemaVersion: 1,
          id: "O-001",
          requirement: "Record lifecycle mechanics without semantic authority.",
          evidenceSeam: ".agents/abe/T029-fixture/evidence-events.ndjson",
          negativeCases: ["secret retention", "path escape", "semantic grading"],
          authority: "fixture workspace only",
          required: true,
          status: "pending",
          evidence: [],
          lastRelevantChangeDigest: changeDigest,
        },
      },
      {
        schemaVersion: 1,
        op: "setTerminalState",
        value: {
          schemaVersion: 1,
          declared: "incomplete",
          reason: "Focused verification is pending.",
          unresolvedObligationIds: ["O-001"],
          activeWork: true,
        },
      },
    ],
  };
  await writeCanonicalAtomic(root, "observer-patch.json", patch);
  await applyTaskStatePatch({ root, patchFile: "observer-patch.json" });
};

const commonInput = (root) => ({
  conversationId: "00000000-0000-4000-8000-000000000029",
  workspacePaths: [root],
  transcriptPath: "/private/brain/session/transcript.jsonl",
  artifactDirectoryPath: "/private/brain/session/artifacts",
  modelName: "gemini-3.7-flash-high",
});

const postToolInput = (root, overrides = {}) => ({
  ...commonInput(root),
  toolCall: { name: "run_command", args: { CommandLine: "node --test" } },
  stepIdx: 3,
  error: "",
  ...overrides,
});

const postInvocationInput = (root, overrides = {}) => ({
  ...commonInput(root),
  invocationNum: 2,
  initialNumSteps: 7,
  ...overrides,
});

const runObserver = (stdin, { cwd = pluginRoot } = {}) => new Promise((resolve) => {
  const child = spawn(process.execPath, [observerPath], {
    cwd,
    stdio: ["pipe", "pipe", "pipe"],
  });
  const stdout = [];
  const stderr = [];
  child.stdout.on("data", (chunk) => stdout.push(chunk));
  child.stderr.on("data", (chunk) => stderr.push(chunk));
  child.on("close", (exitCode) => resolve({
    exitCode,
    stdout: Buffer.concat(stdout).toString("utf8"),
    stderr: Buffer.concat(stderr).toString("utf8"),
  }));
  child.stdin.end(typeof stdin === "string" ? stdin : JSON.stringify(stdin));
});

test("hook manifest binds both qualified observation events to the shipped script", async () => {
  const hooks = await readJson(hooksPath);
  const handler = {
    type: "command",
    command: "node scripts/evidence-observer.mjs",
    timeout: 10,
  };

  assert.deepEqual(hooks, {
    "evidence-observer": {
      enabled: true,
      PostToolUse: [{ matcher: "*", hooks: [handler] }],
      PostInvocation: [handler],
    },
  });
  assert.equal((await fs.stat(observerPath)).isFile(), true, "missing observer script must fail closed in packaging");
});

test("normal and error tool use plus post invocation append schema-valid chained events", async () => {
  await withWorkspace(async (root) => {
    await prepareTask(root);
    const normal = await runObserver(postToolInput(root));
    const failed = await runObserver(postToolInput(root, {
      toolCall: { name: "write_to_file", args: { TargetFile: "/private/repo/key.txt" } },
      stepIdx: 4,
      error: "permission denied",
    }));
    const invoked = await runObserver(postInvocationInput(root));

    for (const result of [normal, failed, invoked]) {
      assert.equal(result.exitCode, 0, result.stderr);
      assert.equal(result.stdout, "{}\n");
      assert.equal(result.stderr, "");
    }

    const events = await readLedger(root);
    assert.equal(events.length, 3);
    assert.deepEqual(events.map(({ sequence, eventKind, toolName, resultClass }) => ({ sequence, eventKind, toolName, resultClass })), [
      { sequence: 0, eventKind: "post_tool_use", toolName: "run_command", resultClass: "success" },
      { sequence: 1, eventKind: "post_tool_use", toolName: "write_to_file", resultClass: "error" },
      { sequence: 2, eventKind: "post_invocation", toolName: "not_applicable", resultClass: "success" },
    ]);
    for (const event of events) {
      assert.deepEqual(parseEvidenceEvent(event, { taskId }), event);
    }
    assert.equal(events[0].previousEventDigest, "genesis");
    assert.equal(events[1].previousEventDigest, sha256Digest(canonicalBytes(events[0])));
    assert.equal(events[2].previousEventDigest, sha256Digest(canonicalBytes(events[1])));
  });
});

test("concurrent deliveries serialize without loss or duplicate sequence numbers", async () => {
  await withWorkspace(async (root) => {
    await prepareTask(root);
    const results = await Promise.all(Array.from({ length: 8 }, (_, index) => runObserver(postToolInput(root, { stepIdx: index }))));
    assert.equal(
      results.every(({ exitCode, stdout, stderr }) => exitCode === 0 && stdout === "{}\n" && stderr === ""),
      true,
      JSON.stringify(results.filter(({ exitCode, stdout, stderr }) => exitCode !== 0 || stdout !== "{}\n" || stderr !== "")),
    );

    const events = await readLedger(root);
    assert.equal(events.length, 8);
    assert.deepEqual(events.map(({ sequence }) => sequence), Array.from({ length: 8 }, (_, index) => index));
    for (let index = 1; index < events.length; index += 1) {
      assert.equal(events[index].previousEventDigest, sha256Digest(canonicalBytes(events[index - 1])));
    }
  });
});

test("malformed JSON exits nonzero without partial stdout or echoed input", async () => {
  const secret = "TOKEN-super-secret-value";
  const result = await runObserver(`{"secret":"${secret}"`);
  assert.notEqual(result.exitCode, 0);
  assert.equal(result.stdout, "");
  assert.match(result.stderr, /^observer\.invalid_json\n$/u);
  assert.equal(result.stderr.includes(secret), false);
});

test("unknown fields, secrets, paths, and transcript content are retained only through redacted digests", async () => {
  await withWorkspace(async (root) => {
    await prepareTask(root);
    const secret = "TOKEN-super-secret-value";
    const privatePath = "/home/private-user/confidential/repository.txt";
    const transcriptContent = "the transcript says do not retain me";
    const result = await runObserver(postToolInput(root, {
      toolCall: {
        name: `TOKEN-${secret}`,
        args: {
          Authorization: `Bearer ${secret}`,
          CommandLine: `cat ${privatePath}`,
          transcriptContent,
        },
      },
      error: `failed with ${secret} at ${privatePath}`,
      futureField: { raw: transcriptContent, apiKey: secret },
    }));
    assert.equal(result.exitCode, 0, result.stderr);
    assert.equal(result.stdout, "{}\n");
    const bytes = await fs.readFile(ledgerPath(root), "utf8");
    for (const forbidden of [secret, privatePath, transcriptContent, "Authorization", "futureField", "CommandLine"]) {
      assert.equal(bytes.includes(forbidden), false, `ledger retained ${forbidden}`);
      assert.equal(result.stderr.includes(forbidden), false, `diagnostic retained ${forbidden}`);
    }
    const [event] = await readLedger(root);
    assert.equal(event.toolName, "unrecognized_tool");
    assert.match(event.redactedPayloadDigest, /^sha256:[0-9a-f]{64}$/u);
    assert.deepEqual(Object.keys(event).sort(), [
      "eventId",
      "eventKind",
      "occurredAt",
      "previousEventDigest",
      "redactedPayloadDigest",
      "resultClass",
      "schemaVersion",
      "sequence",
      "taskId",
      "toolName",
    ]);
  });
});

test("symlink escape, missing task state, and write failure fail open with visible bounded diagnostics", async () => {
  await withWorkspace(async (root) => {
    const missing = await runObserver(postToolInput(root));
    assert.equal(missing.exitCode, 0);
    assert.equal(missing.stdout, "{}\n");
    assert.match(missing.stderr, /^observer\.not_recorded observer\.task_state_missing\n$/u);

    await prepareTask(root);
    const outside = path.join(root, "outside.ndjson");
    await fs.writeFile(outside, "outside\n", "utf8");
    await fs.symlink(outside, ledgerPath(root));
    const escaped = await runObserver(postToolInput(root));
    assert.equal(escaped.exitCode, 0);
    assert.equal(escaped.stdout, "{}\n");
    assert.match(escaped.stderr, /^observer\.not_recorded state\.path_escape\n$/u);
    assert.equal(await fs.readFile(outside, "utf8"), "outside\n");
    await fs.unlink(ledgerPath(root));

    await fs.chmod(taskRoot(root), 0o500);
    const unwritable = await runObserver(postToolInput(root));
    assert.equal(unwritable.exitCode, 0);
    assert.equal(unwritable.stdout, "{}\n");
    assert.match(unwritable.stderr, /^observer\.not_recorded observer\.write_failed\n$/u);
  });
});

test("task-directory replacement cannot redirect observer writes outside the selected evidence directory", async () => {
  await withWorkspace(async (root) => {
    await prepareTask(root);
    const selectedTaskRoot = taskRoot(root);
    const displacedTaskRoot = path.join(root, "selected-task-displaced");
    const outside = path.join(root, "outside-task");
    await fs.mkdir(outside);

    const originalOpen = fs.open;
    let releaseDirectoryOpen;
    const directoryOpenReleased = new Promise((resolve) => {
      releaseDirectoryOpen = resolve;
    });
    let observedDirectoryOpen;
    const directoryOpened = new Promise((resolve) => {
      observedDirectoryOpen = resolve;
    });
    fs.open = async (target, flags, ...rest) => {
      const handle = await originalOpen(target, flags, ...rest);
      if (path.basename(String(target)) === taskId && (flags & fsConstants.O_DIRECTORY) !== 0) {
        observedDirectoryOpen();
        await directoryOpenReleased;
      }
      return handle;
    };

    try {
      const append = appendEvidenceObservation({ input: postToolInput(root) });
      const first = await Promise.race([
        directoryOpened.then(() => "directory-opened"),
        append.then(() => "append-completed"),
      ]);
      assert.equal(first, "directory-opened", "observer must anchor the selected task directory before writing");

      await fs.rename(selectedTaskRoot, displacedTaskRoot);
      await fs.symlink(outside, selectedTaskRoot);
      releaseDirectoryOpen();
      await append;

      assert.equal((await fs.readFile(path.join(displacedTaskRoot, "evidence-events.ndjson"), "utf8")).trim().length > 0, true);
      await assert.rejects(fs.stat(path.join(outside, ".evidence-observer.lock")), { code: "ENOENT" });
      await assert.rejects(fs.stat(path.join(outside, "evidence-events.ndjson")), { code: "ENOENT" });
    } finally {
      releaseDirectoryOpen();
      fs.open = originalOpen;
      await fs.unlink(selectedTaskRoot).catch(() => {});
      await fs.rename(displacedTaskRoot, selectedTaskRoot).catch(() => {});
    }
  });
});

test("task-directory replacement before the first state read cannot expose external state", async () => {
  await withWorkspace(async (root) => {
    await prepareTask(root);
    const selectedTaskRoot = taskRoot(root);
    const displacedTaskRoot = path.join(root, "selected-task-before-read");
    const outside = path.join(root, "outside-state-source");
    await fs.mkdir(outside);
    await fs.writeFile(path.join(outside, "state.json"), await fs.readFile(statePath(root)));

    const originalLstat = fs.lstat;
    const originalReadFile = fs.readFile;
    let releaseStateInspection;
    const stateInspectionReleased = new Promise((resolve) => {
      releaseStateInspection = resolve;
    });
    let observedStateInspection;
    const stateInspected = new Promise((resolve) => {
      observedStateInspection = resolve;
    });
    let swapped = false;
    let externalStateReads = 0;
    fs.lstat = async (target, ...rest) => {
      const status = await originalLstat(target, ...rest);
      if (!swapped && path.basename(String(target)) === "state.json") {
        observedStateInspection();
        await stateInspectionReleased;
      }
      return status;
    };
    fs.readFile = async (target, ...rest) => {
      if (swapped && target === statePath(root)) {
        externalStateReads += 1;
      }
      return originalReadFile(target, ...rest);
    };

    try {
      const append = appendEvidenceObservation({ input: postToolInput(root) }).then(
        (event) => ({ event }),
        (error) => ({ error }),
      );
      await stateInspected;
      await fs.rename(selectedTaskRoot, displacedTaskRoot);
      await fs.symlink(outside, selectedTaskRoot);
      swapped = true;
      releaseStateInspection();
      const result = await append;

      assert.equal(externalStateReads, 0, "observer read state through a replaced parent directory");
      assert.equal(result.error, undefined, result.error?.message);
      assert.equal((await fs.readFile(path.join(displacedTaskRoot, "evidence-events.ndjson"), "utf8")).trim().length > 0, true);
      await assert.rejects(fs.stat(path.join(outside, "evidence-events.ndjson")), { code: "ENOENT" });
    } finally {
      swapped = true;
      releaseStateInspection();
      fs.lstat = originalLstat;
      fs.readFile = originalReadFile;
      await fs.unlink(selectedTaskRoot).catch(() => {});
      await fs.rename(displacedTaskRoot, selectedTaskRoot).catch(() => {});
    }
  });
});

test("state and ledger leaf replacement races never follow external symlinks", async () => {
  for (const leafName of ["state.json", "evidence-events.ndjson"]) {
    await withWorkspace(async (root) => {
      await prepareTask(root);
      if (leafName === "evidence-events.ndjson") {
        await appendEvidenceObservation({ input: postToolInput(root) });
      }
      const selectedLeaf = path.join(taskRoot(root), leafName);
      const displacedLeaf = selectedLeaf + ".displaced";
      const outsideLeaf = path.join(root, "outside-" + leafName);
      await fs.writeFile(outsideLeaf, await fs.readFile(selectedLeaf));

      const originalLstat = fs.lstat;
      let releaseLeafInspection;
      const leafInspectionReleased = new Promise((resolve) => {
        releaseLeafInspection = resolve;
      });
      let observedLeafInspection;
      const leafInspected = new Promise((resolve) => {
        observedLeafInspection = resolve;
      });
      let intercepted = false;
      fs.lstat = async (target, ...rest) => {
        const status = await originalLstat(target, ...rest);
        if (!intercepted && path.basename(String(target)) === leafName) {
          intercepted = true;
          observedLeafInspection();
          await leafInspectionReleased;
        }
        return status;
      };

      try {
        const append = appendEvidenceObservation({ input: postToolInput(root) }).then(
          () => null,
          (error) => error,
        );
        await leafInspected;
        await fs.rename(selectedLeaf, displacedLeaf);
        await fs.symlink(outsideLeaf, selectedLeaf);
        releaseLeafInspection();
        const error = await append;

        assert.equal(error?.reasonCode, "state.path_escape");
        assert.deepEqual(await fs.readFile(outsideLeaf), await fs.readFile(displacedLeaf));
      } finally {
        releaseLeafInspection();
        fs.lstat = originalLstat;
        await fs.unlink(selectedLeaf).catch(() => {});
        await fs.rename(displacedLeaf, selectedLeaf).catch(() => {});
      }
    });
  }
});

test("bounded direct appends stay below the frozen p95 envelope and reject ledger growth beyond the cap", async (context) => {
  await withWorkspace(async (root) => {
    await prepareTask(root);
    const durations = [];
    for (let index = 0; index < 40; index += 1) {
      const started = performance.now();
      await appendEvidenceObservation({
        input: postToolInput(root, { stepIdx: index }),
        occurredAt: `2026-08-23T00:00:${String(index).padStart(2, "0")}Z`,
      });
      durations.push(performance.now() - started);
    }
    durations.sort((left, right) => left - right);
    const p95 = durations[Math.ceil(durations.length * 0.95) - 1];
    assert.ok(p95 < 250, `observer p95 ${p95.toFixed(3)} ms exceeds 250 ms`);
    context.diagnostic(`observer direct-append p95=${p95.toFixed(3)}ms n=${durations.length}`);
  });

  await withWorkspace(async (root) => {
    await prepareTask(root);
    await fs.writeFile(ledgerPath(root), "x".repeat(4 * 1024 * 1024 + 1), "utf8");
    await assert.rejects(
      appendEvidenceObservation({ input: postToolInput(root) }),
      (error) => error?.reasonCode === "observer.ledger_limit",
    );
  });
});

test("formative matrix freezes ablation, disablement, failure isolation, and resource decisions", async () => {
  const matrix = await readJson(matrixPath);
  const repairMatrix = await readJson(repairMatrixPath);
  const liveHookRepairMatrix = await readJson(liveHookRepairMatrixPath);
  const analysis = await readJson(analysisPath);
  assert.equal(matrix.frozenBeforeTreatment, true);
  assert.deepEqual(matrix.models, ["gemini-3.1-pro-high", "gemini-3.7-flash-high"]);
  assert.deepEqual(matrix.conditions.map(({ conditionId }) => conditionId), [
    "incumbent-observer-off",
    "incumbent-observer-on",
  ]);
  assert.equal(matrix.deterministicCases.includes("disablement"), true);
  assert.equal(matrix.deterministicCases.includes("missing_script"), true);
  assert.equal(matrix.evidencePolicy.semanticAuthority, false);
  assert.equal(matrix.evidencePolicy.failurePolicy.startsWith("fail_open"), true);
  assert.equal(matrix.resourceEnvelope.p95Milliseconds, 250);
  assert.equal(matrix.resourceEnvelope.hardTimeoutSeconds, 10);
  assert.equal(matrix.resourceEnvelope.maxLedgerBytes, 4 * 1024 * 1024);
  assert.equal(repairMatrix.frozenBeforeTreatment, true);
  assert.equal(repairMatrix.candidateRuntimeDigest, sha256Digest(await fs.readFile(path.join(pluginRoot, "scripts", "runtime-lib.mjs"))));
  assert.deepEqual(repairMatrix.conditions.map(({ conditionId }) => conditionId), [
    "repaired-runtime-observer-off",
    "repaired-runtime-observer-on",
  ]);
  assert.equal(liveHookRepairMatrix.frozenBeforeTreatment, true);
  assert.equal(liveHookRepairMatrix.candidateRuntimeDigest, sha256Digest(await fs.readFile(path.join(pluginRoot, "scripts", "runtime-lib.mjs"))));
  assert.deepEqual(liveHookRepairMatrix.conditions.map(({ conditionId }) => conditionId), [
    "installed-live-observer-off",
    "installed-live-observer-on",
  ]);
  assert.equal(liveHookRepairMatrix.liveHookQualification.observerOff.pluginImported, true);
  assert.equal(liveHookRepairMatrix.liveHookQualification.observerOff.namedHooksLoaded, 0);
  assert.equal(liveHookRepairMatrix.liveHookQualification.observerOff.hookFilesLoaded, 0);
  assert.equal(liveHookRepairMatrix.liveHookQualification.observerOn.namedHooksLoaded, 1);
  assert.equal(liveHookRepairMatrix.liveHookQualification.observerOn.hookFilesLoaded, 1);
  assert.equal(liveHookRepairMatrix.liveHookQualification.profileIsolation, "mount_namespace_config_bind");
  assert.equal(analysis.matrixDigest, sha256Digest(await fs.readFile(matrixPath)));
  assert.equal(analysis.currentRuntimeControl.matrixDigest, sha256Digest(await fs.readFile(liveHookRepairMatrixPath)));
  assert.equal(analysis.matchedTreatment.matrixDigest, sha256Digest(await fs.readFile(liveHookRepairMatrixPath)));
  assert.equal(analysis.currentRuntimeControl.hookResolution.namedHooksLoaded, 1);
  assert.equal(analysis.currentRuntimeControl.hookResolution.hookFilesLoaded, 1);
  assert.equal(analysis.matchedTreatment.hookResolution.namedHooksLoaded, 1);
  assert.equal(analysis.matchedTreatment.hookResolution.hookFilesLoaded, 1);
  assert.equal(analysis.implementation.hooksDigest, sha256Digest(await fs.readFile(hooksPath)));
  assert.equal(analysis.implementation.observerScriptDigest, sha256Digest(await fs.readFile(observerPath)));
  assert.equal(analysis.implementation.runtimeDigest, sha256Digest(await fs.readFile(path.join(pluginRoot, "scripts", "runtime-lib.mjs"))));
  assert.equal(analysis.incumbentReplay.candidateBodyPresent, false);
  assert.equal(analysis.incumbentReplay.models.every(({ observerEvents }) => observerEvents === 0), true);
  assert.equal(analysis.matchedTreatment.models.every(({ artifactMatches, completionConclusion }) => artifactMatches && completionConclusion === "complete"), true);
  assert.equal(analysis.resourceReport.envelopeResult, "pass");
  assert.deepEqual(analysis.privacyReview, {
    liveEventCount: 8,
    liveLedgerBytes: 3251,
    maximumCanonicalEventBytes: 424,
    credentialPatternsFound: 0,
    absolutePrivatePathsFound: 0,
    transcriptContentFound: 0,
    rawArgumentsFound: 0,
    rawErrorsFound: 0,
    unboundedGrowth: false,
  });
  assert.deepEqual(analysis.selectionDecision, {
    decision: "selected",
    retained: true,
    claimId: "T029.evidence-observer.redacted-hash-chained-lifecycle-facts",
    reason: "The current repaired-runtime ablation closes the lifecycle-evidence gap for both models while preserving exact artifacts, completion conclusions, tool-call counts, failure isolation, privacy, and the frozen resource envelope.",
  });
  const analysisBytes = await fs.readFile(analysisPath, "utf8");
  for (const forbidden of ["/home/", "/tmp/", "codex-dispatch", "conversationId"]) {
    assert.equal(analysisBytes.includes(forbidden), false, `public analysis retained ${forbidden}`);
  }
});

test("behavior lock selects only the earned observer and covers every plugin file", async () => {
  const lock = await readJson(lockPath);
  const files = [];
  const walk = async (directory, prefix = "") => {
    for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
      const relative = prefix ? `${prefix}/${entry.name}` : entry.name;
      if (entry.isDirectory()) {
        await walk(path.join(directory, entry.name), relative);
      } else if (entry.isFile() && relative !== "behavior-lock.json") {
        files.push(relative);
      }
    }
  };
  await walk(pluginRoot);
  files.sort();
  assert.deepEqual(Object.keys(lock.files).sort(), files);
  for (const relative of files) {
    assert.equal(lock.files[relative], sha256Digest(await fs.readFile(path.join(pluginRoot, relative))));
  }
  assert.deepEqual(lock.components.filter(({ name }) => name === "evidence-observer"), [
    {
      schemaVersion: 1,
      kind: "hook",
      name: "evidence-observer",
      path: "hooks.json",
      claimId: "T029.evidence-observer.redacted-hash-chained-lifecycle-facts",
      defaultEnabled: true,
      digest: lock.files["hooks.json"],
    },
  ]);
});
