import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  applyTaskStatePatch,
  canonicalBytes,
  initializeTaskState,
  parseCompletionGateEvent,
  parseTaskState,
  sha256Digest,
  writeCanonicalAtomic,
} from "../../plugin/scripts/runtime-lib.mjs";

const repoRoot = path.resolve(new URL("../..", import.meta.url).pathname);
const pluginRoot = path.join(repoRoot, "plugin");
const hooksPath = path.join(pluginRoot, "hooks.json");
const gatePath = path.join(pluginRoot, "scripts", "bounded-completion-gate.mjs");
const matrixPath = path.join(repoRoot, "evals", "formative", "completion-gate.matrix.json");
const repairMatrixPath = path.join(repoRoot, "evals", "formative", "completion-gate.repair-matrix.json");
const analysisPath = path.join(repoRoot, "evals", "formative", "completion-gate.analysis.json");
const lockPath = path.join(pluginRoot, "behavior-lock.json");
const taskId = "T030-fixture";
const workspaceDigest = "sha256:" + "0".repeat(64);
const requestDigest = "sha256:" + "1".repeat(64);
const changeDigest = "sha256:" + "2".repeat(64);
const evidenceDigest = "sha256:" + "3".repeat(64);

const taskRoot = (root) => path.join(root, ".agents", "abe", taskId);
const statePath = (root) => path.join(taskRoot(root), "state.json");
const ledgerPath = (root) => path.join(taskRoot(root), "completion-gate.ndjson");
const readJson = async (file) => JSON.parse(await fs.readFile(file, "utf8"));
const readLedger = async (root) => (await fs.readFile(ledgerPath(root), "utf8"))
  .trimEnd()
  .split("\n")
  .map(JSON.parse);

const optionalObligation = () => ({
  schemaVersion: 1,
  id: "O-OPTIONAL",
  requirement: "Optional cleanup is explicitly out of scope.",
  evidenceSeam: ".agents/abe/T030-fixture/state.json",
  negativeCases: ["treating optional work as required"],
  authority: "fixture workspace only",
  required: false,
  status: "not_applicable",
  evidence: [],
  lastRelevantChangeDigest: "none",
});

const pendingObligation = () => ({
  schemaVersion: 1,
  id: "O-REQUIRED",
  requirement: "Required focused verification must pass.",
  evidenceSeam: "evidence/focused.txt",
  negativeCases: ["false completion"],
  authority: "fixture workspace only",
  required: true,
  status: "pending",
  evidence: [],
  lastRelevantChangeDigest: changeDigest,
});

const passingObligation = () => ({
  ...pendingObligation(),
  status: "passing",
  evidence: [{
    schemaVersion: 1,
    kind: "test",
    locator: "evidence/focused.txt",
    digest: evidenceDigest,
    observedAt: "2026-08-23T01:00:00Z",
    afterChangeDigest: changeDigest,
    result: "pass",
  }],
});

const finding = (status) => ({
  schemaVersion: 1,
  id: "F-IMPORTANT",
  reviewerRole: "quality",
  severity: "important",
  claim: "A material defect requires disposition.",
  evidence: [{
    schemaVersion: 1,
    kind: "review",
    locator: "reviews/quality.json",
    digest: evidenceDigest,
    observedAt: "2026-08-23T01:00:00Z",
    afterChangeDigest: "none",
    result: "fail",
  }],
  status,
  dispositionReason: "",
  repairChangeDigest: "none",
  verificationEvidenceIds: [],
});

const withWorkspace = async (fn) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "abe-completion-gate-"));
  try {
    return await fn(root);
  } finally {
    await fs.chmod(taskRoot(root), 0o700).catch(() => {});
    await fs.rm(root, { recursive: true, force: true });
  }
};

const prepareTask = async (root, {
  obligation = optionalObligation(),
  terminal = {
    schemaVersion: 1,
    declared: "complete",
    reason: "All mechanically required work is complete.",
    unresolvedObligationIds: [],
    activeWork: false,
  },
  reviewFinding,
} = {}) => {
  const initialized = await initializeTaskState({ root, taskId, workspaceDigest, requestDigest });
  const operations = [
    { schemaVersion: 1, op: "setWorkflowTier", value: "substantial" },
    { schemaVersion: 1, op: "setIntent", value: "Exercise the bounded completion gate." },
    { schemaVersion: 1, op: "appendObligation", value: obligation },
  ];
  if (reviewFinding) operations.push({ schemaVersion: 1, op: "appendReviewFinding", value: reviewFinding });
  operations.push({ schemaVersion: 1, op: "setTerminalState", value: terminal });
  await writeCanonicalAtomic(root, "fixture-patch.json", {
    schemaVersion: 1,
    taskId,
    workspaceDigest,
    requestDigest,
    baseStateDigest: initialized.stateDigest,
    updatedAt: "2026-08-23T01:00:00Z",
    operations,
  });
  await applyTaskStatePatch({ root, patchFile: "fixture-patch.json" });
};

const stopInput = (root, overrides = {}) => ({
  conversationId: "00000000-0000-4000-8000-000000000030",
  workspacePaths: [root],
  transcriptPath: "/private/brain/session/transcript.jsonl",
  artifactDirectoryPath: "/private/brain/session/artifacts",
  modelName: "gemini-3.7-flash-high",
  executionNum: 0,
  terminationReason: "NO_TOOL_CALL",
  error: "",
  fullyIdle: true,
  ...overrides,
});

const runGate = (stdin, { cwd = pluginRoot } = {}) => new Promise((resolve) => {
  const child = spawn(process.execPath, [gatePath], { cwd, stdio: ["pipe", "pipe", "pipe"] });
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

const assertAllow = ({ exitCode, stdout }, diagnostic = undefined) => {
  assert.equal(exitCode, 0);
  assert.deepEqual(JSON.parse(stdout), { decision: "" });
  if (diagnostic !== undefined) return diagnostic;
};

test("hook manifest binds the qualified Stop event to the shipped bounded gate", async () => {
  const hooks = await readJson(hooksPath);
  assert.deepEqual(hooks["bounded-completion-gate"], {
    enabled: true,
    Stop: [{ type: "command", command: "node scripts/bounded-completion-gate.mjs", timeout: 10 }],
  });
  assert.equal((await fs.stat(gatePath)).isFile(), true, "missing gate script must fail closed in packaging");
});

test("active work appends one hash-chained continuation without changing TaskState", async () => {
  await withWorkspace(async (root) => {
    await prepareTask(root, {
      terminal: {
        schemaVersion: 1,
        declared: "incomplete",
        reason: "Work is active.",
        unresolvedObligationIds: [],
        activeWork: true,
      },
    });
    const before = await fs.readFile(statePath(root));
    const result = await runGate(stopInput(root));
    assert.equal(result.exitCode, 0, result.stderr);
    assert.equal(JSON.parse(result.stdout).decision, "continue");
    assert.match(JSON.parse(result.stdout).reason, /active work/u);
    assert.match(JSON.parse(result.stdout).reason, /Do not use tools/u);
    assert.match(JSON.parse(result.stdout).reason, /immediately report/u);
    const events = await readLedger(root);
    assert.equal(events.length, 2);
    assert.deepEqual(parseCompletionGateEvent(events[1], { taskId, workspaceDigest, requestDigest }), events[1]);
    assert.equal(events[1].continuationOrdinal, 1);
    assert.equal(events[1].frozenBound, 1);
    assert.equal(events[1].reasonCode, "active_work");
    assert.equal(events[1].previousEventDigest, sha256Digest(canonicalBytes(events[0])));
    assert.deepEqual(await fs.readFile(statePath(root)), before);
  });
});

test("unresolved required obligation and stale passing evidence name exact IDs", async (context) => {
  await context.test("pending required obligation", async () => withWorkspace(async (root) => {
    await prepareTask(root, {
      obligation: pendingObligation(),
      terminal: {
        schemaVersion: 1,
        declared: "incomplete",
        reason: "Verification is pending.",
        unresolvedObligationIds: ["O-REQUIRED"],
        activeWork: false,
      },
    });
    const result = await runGate(stopInput(root));
    assert.equal(JSON.parse(result.stdout).decision, "continue");
    assert.match(JSON.parse(result.stdout).reason, /O-REQUIRED/u);
    assert.match(JSON.parse(result.stdout).reason, /Do not use tools/u);
    assert.equal((await readLedger(root))[1].reasonCode, "unresolved_required_obligation");
  }));

  await context.test("stale passing evidence", async () => withWorkspace(async (root) => {
    await prepareTask(root, { obligation: passingObligation() });
    const state = await readJson(statePath(root));
    state.obligations[0].evidence[0].afterChangeDigest = "sha256:" + "4".repeat(64);
    await writeCanonicalAtomic(root, ".agents/abe/T030-fixture/state.json", state);
    const result = await runGate(stopInput(root));
    assert.equal(JSON.parse(result.stdout).decision, "continue");
    assert.match(JSON.parse(result.stdout).reason, /O-REQUIRED/u);
    assert.match(JSON.parse(result.stdout).reason, /Do not use tools/u);
    assert.equal((await readLedger(root))[1].reasonCode, "stale_passing_evidence");
  }));
});

test("accepted material finding continues while an open finding follows the exact contract", async (context) => {
  await context.test("accepted", async () => withWorkspace(async (root) => {
    await prepareTask(root, {
      reviewFinding: finding("accepted"),
      terminal: {
        schemaVersion: 1,
        declared: "incomplete",
        reason: "An accepted finding awaits verification.",
        unresolvedObligationIds: [],
        activeWork: false,
      },
    });
    const result = await runGate(stopInput(root));
    assert.equal(JSON.parse(result.stdout).decision, "continue");
    assert.match(JSON.parse(result.stdout).reason, /F-IMPORTANT/u);
    assert.match(JSON.parse(result.stdout).reason, /Do not use tools/u);
    assert.equal((await readLedger(root))[1].reasonCode, "accepted_finding_unverified");
  }));

  await context.test("open", async () => withWorkspace(async (root) => {
    await prepareTask(root, {
      reviewFinding: finding("open"),
      terminal: {
        schemaVersion: 1,
        declared: "incomplete",
        reason: "An unaccepted finding remains open.",
        unresolvedObligationIds: [],
        activeWork: false,
      },
    });
    const result = await runGate(stopInput(root));
    assertAllow(result);
    assert.equal((await readLedger(root)).length, 1);
  }));
});

test("passing states and indeterminate Stop inputs permit stopping without ledger writes", async (context) => {
  await context.test("fresh passing evidence", async () => withWorkspace(async (root) => {
    await prepareTask(root, { obligation: passingObligation() });
    const result = await runGate(stopInput(root));
    assertAllow(result);
    assert.equal((await readLedger(root)).length, 1);
  }));

  await context.test("not fully idle", async () => withWorkspace(async (root) => {
    await prepareTask(root, {
      terminal: {
        schemaVersion: 1,
        declared: "incomplete",
        reason: "Work is active.",
        unresolvedObligationIds: [],
        activeWork: true,
      },
    });
    const result = await runGate(stopInput(root, { fullyIdle: false }));
    assertAllow(result);
    assert.match(result.stderr, /stop_not_fully_idle/u);
    assert.equal((await readLedger(root)).length, 1);
  }));
});

test("schema-invalid but identity-bound state continues with a mechanical reason", async () => {
  await withWorkspace(async (root) => {
    await prepareTask(root);
    const state = await readJson(statePath(root));
    delete state.terminalState.reason;
    await writeCanonicalAtomic(root, ".agents/abe/T030-fixture/state.json", state);
    const result = await runGate(stopInput(root));
    assert.equal(result.exitCode, 0, result.stderr);
    assert.equal(JSON.parse(result.stdout).decision, "continue");
    assert.match(JSON.parse(result.stdout).reason, /TaskState schema/u);
    assert.match(JSON.parse(result.stdout).reason, /Do not use tools/u);
    assert.equal((await readLedger(root))[1].reasonCode, "invalid_task_state");
  });
});

test("duplicate and concurrent Stop delivery is idempotent", async (context) => {
  await context.test("repeated", async () => withWorkspace(async (root) => {
    await prepareTask(root, {
      terminal: {
        schemaVersion: 1,
        declared: "incomplete",
        reason: "Work is active.",
        unresolvedObligationIds: [],
        activeWork: true,
      },
    });
    const first = await runGate(stopInput(root));
    const second = await runGate(stopInput(root));
    assert.equal(JSON.parse(first.stdout).decision, "continue");
    assert.equal(second.stdout, first.stdout);
    assert.equal((await readLedger(root)).length, 2);
  }));

  await context.test("concurrent", async () => withWorkspace(async (root) => {
    await prepareTask(root, {
      terminal: {
        schemaVersion: 1,
        declared: "incomplete",
        reason: "Work is active.",
        unresolvedObligationIds: [],
        activeWork: true,
      },
    });
    const results = await Promise.all(Array.from({ length: 8 }, () => runGate(stopInput(root))));
    assert.equal(results.every((result) => result.exitCode === 0 && JSON.parse(result.stdout).decision === "continue"), true);
    assert.equal((await readLedger(root)).length, 2);
  }));
});

test("a distinct Stop after the bound permits stopping and consumes no event", async () => {
  await withWorkspace(async (root) => {
    await prepareTask(root, {
      terminal: {
        schemaVersion: 1,
        declared: "incomplete",
        reason: "Work is active.",
        unresolvedObligationIds: [],
        activeWork: true,
      },
    });
    assert.equal(JSON.parse((await runGate(stopInput(root))).stdout).decision, "continue");
    const bounded = await runGate(stopInput(root, { executionNum: 1 }));
    assertAllow(bounded);
    assert.match(bounded.stderr, /retry_bound_reached/u);
    assert.equal((await readLedger(root)).length, 2);
  });
});

test("foreign TaskState identity fails open", async () => {
  await withWorkspace(async (root) => {
    await prepareTask(root);
    const state = await readJson(statePath(root));
    state.taskId = "T030-foreign";
    await writeCanonicalAtomic(root, ".agents/abe/T030-fixture/state.json", state);
    const result = await runGate(stopInput(root));
    assertAllow(result);
    assert.match(result.stderr, /task_state_foreign/u);
    assert.equal((await readLedger(root)).length, 1);
  });
});

test("TaskState replacement between discovery and the locked decision fails open as stale", async () => {
  await withWorkspace(async (root) => {
    await prepareTask(root, {
      terminal: {
        schemaVersion: 1,
        declared: "incomplete",
        reason: "Work is active.",
        unresolvedObligationIds: [],
        activeWork: true,
      },
    });
    const lockFile = path.join(taskRoot(root), ".completion-gate.lock");
    await fs.writeFile(lockFile, "test barrier\n");
    const pending = runGate(stopInput(root));
    await new Promise((resolve) => setTimeout(resolve, 80));
    const state = await readJson(statePath(root));
    state.updatedAt = "2026-08-23T01:00:01Z";
    await writeCanonicalAtomic(root, ".agents/abe/T030-fixture/state.json", state);
    await fs.rm(lockFile);
    const result = await pending;
    assertAllow(result);
    assert.match(result.stderr, /task_state_stale/u);
    assert.equal((await readLedger(root)).length, 1);
  });
});

test("missing, empty, malformed, foreign, stale, locked, and unwritable ledgers fail open", async (context) => {
  const cases = [
    ["missing", async (root) => fs.rm(ledgerPath(root))],
    ["empty", async (root) => fs.writeFile(ledgerPath(root), "")],
    ["malformed", async (root) => fs.writeFile(ledgerPath(root), "{not-json}\n")],
    ["foreign", async (root) => {
      const events = await readLedger(root);
      events[0].requestDigest = "sha256:" + "9".repeat(64);
      await fs.writeFile(ledgerPath(root), JSON.stringify(events[0]) + "\n");
    }],
    ["stale", async (root) => {
      const events = await readLedger(root);
      events[0].frozenBound = 0;
      await fs.writeFile(ledgerPath(root), JSON.stringify(events[0]) + "\n");
    }],
    ["locked", async (root) => fs.writeFile(path.join(taskRoot(root), ".completion-gate.lock"), "held\n")],
    ["unwritable", async (root) => fs.chmod(taskRoot(root), 0o500)],
  ];
  for (const [name, corrupt] of cases) {
    await context.test(name, async () => withWorkspace(async (root) => {
      await prepareTask(root, {
        terminal: {
          schemaVersion: 1,
          declared: "incomplete",
          reason: "Work is active.",
          unresolvedObligationIds: [],
          activeWork: true,
        },
      });
      await corrupt(root);
      const result = await runGate(stopInput(root));
      assertAllow(result);
      assert.match(result.stderr, /completion_gate_fail_open/u);
    }));
  }
});

test("no TaskState is inert, while malformed hook input fails visibly", async (context) => {
  await context.test("no task state", async () => withWorkspace(async (root) => {
    const result = await runGate(stopInput(root));
    assertAllow(result);
    assert.match(result.stderr, /task_state_missing/u);
  }));

  await context.test("malformed input", async () => {
    const result = await runGate("{not-json");
    assert.notEqual(result.exitCode, 0);
    assert.equal(result.stdout, "");
    assert.match(result.stderr, /completion_gate_invalid_input/u);
  });
});

test("foreign workspace paths and symlinked state roots fail open without escape", async () => {
  await withWorkspace(async (root) => {
    const outside = await fs.mkdtemp(path.join(os.tmpdir(), "abe-completion-outside-"));
    try {
      await fs.mkdir(path.join(root, ".agents"), { recursive: true });
      await fs.symlink(outside, path.join(root, ".agents", "abe"));
      const result = await runGate(stopInput(root));
      assertAllow(result);
      assert.match(result.stderr, /completion_gate_fail_open/u);
      assert.deepEqual(await fs.readdir(outside), []);
    } finally {
      await fs.rm(outside, { recursive: true, force: true });
    }
  });
});

test("focused decisions stay inside the 250 ms p95 budget", async () => {
  await withWorkspace(async (root) => {
    await prepareTask(root, { obligation: passingObligation() });
    const durations = [];
    for (let index = 0; index < 12; index += 1) {
      const started = process.hrtime.bigint();
      const result = await runGate(stopInput(root, { executionNum: index }));
      assertAllow(result);
      durations.push(Number(process.hrtime.bigint() - started) / 1e6);
    }
    durations.sort((left, right) => left - right);
    const p95 = durations[Math.ceil(durations.length * 0.95) - 1];
    assert.ok(p95 < 250, `p95 ${p95.toFixed(1)} ms exceeded 250 ms`);
  });
});

test("frozen ablations select bound one and bind the shipped implementation", async () => {
  const matrix = await readJson(matrixPath);
  const repairMatrix = await readJson(repairMatrixPath);
  const analysis = await readJson(analysisPath);
  const lock = await readJson(lockPath);

  assert.equal(matrix.frozenBeforeTreatment, true);
  assert.equal(matrix.candidateBodyPresentAtFreeze, false);
  assert.equal(matrix.resourceEnvelope.initialCandidateBound, 1);
  assert.equal(repairMatrix.frozenBeforeRepairTreatment, true);
  assert.equal(repairMatrix.repairAppliedAtFreeze, false);
  assert.equal(repairMatrix.rejectedCandidateScriptDigest, "sha256:7d0e7f7a7f61d4d22d07c7379f5acddb52ae1db83ee9749b4bc036b24f074c58");
  assert.equal(analysis.matrixDigest, sha256Digest(await fs.readFile(matrixPath)));
  assert.equal(analysis.repairMatrixDigest, sha256Digest(await fs.readFile(repairMatrixPath)));
  assert.equal(analysis.implementation.hooksDigest, sha256Digest(await fs.readFile(hooksPath)));
  assert.equal(analysis.implementation.gateScriptDigest, sha256Digest(await fs.readFile(gatePath)));
  assert.equal(analysis.incumbentReplay.negativeCriticalFalseCompletions, 4);
  assert.equal(analysis.rejectedTreatment.decision, "rejected");
  assert.equal(analysis.selectedTreatment.negativeHonestConclusions, 4);
  assert.equal(analysis.selectedTreatment.positiveSuccesses, 4);
  assert.equal(analysis.selectedTreatment.productFailureRuns, 0);
  assert.equal(analysis.selectedTreatment.postContinuationToolCalls, 0);
  assert.equal(analysis.resourceReport.envelopeResult, "pass");
  assert.deepEqual(analysis.selectionDecision, {
    decision: "selected",
    retained: true,
    bound: 1,
    smallestPassingBound: 1,
    claimId: "T030.bounded-completion-gate.mechanical-finite-completion-check",
    reason: "Bound zero preserved four critical false completions. The repaired bound-one gate reduced them to zero for both models, retained four of four positive completions, used no post-continuation tools, preserved every TaskState byte, terminated every valid run, and remained within the frozen token and duration envelopes.",
  });

  const component = lock.components.find(({ name }) => name === "bounded-completion-gate");
  assert.deepEqual(component, {
    schemaVersion: 1,
    kind: "hook",
    name: "bounded-completion-gate",
    path: "hooks.json",
    claimId: "T030.bounded-completion-gate.mechanical-finite-completion-check",
    defaultEnabled: true,
    digest: sha256Digest(await fs.readFile(hooksPath)),
  });
  assert.equal(lock.files["scripts/bounded-completion-gate.mjs"], sha256Digest(await fs.readFile(gatePath)));

  const publicAnalysis = await fs.readFile(analysisPath, "utf8");
  assert.doesNotMatch(publicAnalysis, /\/home\/|\/private\/|\.gemini\/antigravity-cli\/brain/u);
});
