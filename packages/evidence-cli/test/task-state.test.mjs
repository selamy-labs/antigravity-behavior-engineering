import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { canonicalBytes, sha256Digest } from "../../contracts/src/canonical-json.mjs";
import {
  ContractValidationError,
  ReasonCodes,
  parseCompletionGateEvent,
  parseTaskState,
} from "../../contracts/src/runtime-contracts.mjs";

const repoRoot = path.resolve(new URL("../../..", import.meta.url).pathname);
const packageRoot = path.join(repoRoot, "packages", "evidence-cli");
const packageJsonPath = path.join(packageRoot, "package.json");
const packageBin = path.join(packageRoot, "bin", "abe-evidence.mjs");
const pluginRuntime = path.join(repoRoot, "plugin", "scripts", "runtime-lib.mjs");
const behaviorLockPath = path.join(repoRoot, "plugin", "behavior-lock.json");
const blackBoxEntrypoints = Object.freeze([
  { label: "plugin runtime", path: pluginRuntime },
  { label: "package binary", path: packageBin },
]);
const packedPackageFiles = Object.freeze([
  "package/bin/abe-evidence.mjs",
  "package/package.json",
  "package/src/runtime-lib.mjs",
  "package/src/task-state.mjs",
]);

const TASK_ID = "task-0001";
const WORKSPACE_DIGEST = "sha256:" + "0".repeat(64);
const REQUEST_DIGEST = "sha256:" + "1".repeat(64);
const CHANGE_DIGEST = "sha256:" + "2".repeat(64);
const EVIDENCE_DIGEST = "sha256:" + "3".repeat(64);
const WRONG_DIGEST = "sha256:" + "4".repeat(64);
const INIT_TIME = "1970-01-01T00:00:00Z";
const APPLY_TIME = "2026-08-22T12:00:00Z";

const taskDir = (root, taskId = TASK_ID) => path.join(root, ".agents", "abe", taskId);
const statePath = (root, taskId = TASK_ID) => path.join(taskDir(root, taskId), "state.json");
const ledgerPath = (root, taskId = TASK_ID) => path.join(taskDir(root, taskId), "completion-gate.ndjson");

const readJson = async (file) => JSON.parse(await fs.readFile(file, "utf8"));
const readLedger = async (file) => (await fs.readFile(file, "utf8")).trimEnd().split("\n").map(JSON.parse);
const digestFile = async (file) => sha256Digest(await fs.readFile(file));

const runNode = (entrypoint, args, { cwd, env = {} } = {}) => new Promise((resolve) => {
  const child = spawn(process.execPath, [entrypoint, ...args], {
    cwd,
    env: { ...process.env, ...env },
    stdio: ["ignore", "pipe", "pipe"],
  });
  const stdout = [];
  const stderr = [];
  child.stdout.on("data", (chunk) => stdout.push(chunk));
  child.stderr.on("data", (chunk) => stderr.push(chunk));
  child.on("close", (exitCode) => {
    resolve({
      exitCode,
      stdout: Buffer.concat(stdout).toString("utf8"),
      stderr: Buffer.concat(stderr).toString("utf8"),
    });
  });
});

const runCommand = (command, args, { cwd = repoRoot, env = {} } = {}) => new Promise((resolve) => {
  const child = spawn(command, args, {
    cwd,
    env: { ...process.env, ...env },
    stdio: ["ignore", "pipe", "pipe"],
  });
  const stdout = [];
  const stderr = [];
  child.stdout.on("data", (chunk) => stdout.push(chunk));
  child.stderr.on("data", (chunk) => stderr.push(chunk));
  child.on("close", (exitCode) => {
    resolve({
      exitCode,
      stdout: Buffer.concat(stdout),
      stderr: Buffer.concat(stderr).toString("utf8"),
    });
  });
});

const runPnpm = (args, options = {}) => {
  if (process.env.npm_execpath && process.env.npm_execpath.includes("pnpm")) {
    return runCommand(process.execPath, [process.env.npm_execpath, ...args], options);
  }
  return runCommand("pnpm", args, options);
};

const withTemporaryWorkspace = async (fn) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "abe-evidence-cli-"));
  try {
    return await fn(root);
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
};

const writeJson = async (file, value) => {
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file, JSON.stringify(value, null, 2) + "\n", "utf8");
};

const copyPackageSource = async (root) => {
  const copyRoot = path.join(root, "evidence-cli");
  await fs.cp(packageRoot, copyRoot, {
    recursive: true,
    filter: (sourcePath) => !sourcePath.split(path.sep).includes("node_modules"),
  });
  return copyRoot;
};

const packageArchivePath = async (packDestination) => {
  const archives = (await fs.readdir(packDestination))
    .filter((entry) => entry.endsWith(".tgz"))
    .sort();
  assert.deepEqual(archives, ["antigravity-abe-evidence-cli-0.0.0.tgz"]);
  return path.join(packDestination, archives[0]);
};

const listArchive = async (archive) => {
  const listing = await runCommand("tar", ["-tzf", archive]);
  assert.equal(listing.exitCode, 0, listing.stderr);
  return listing.stdout.toString("utf8").trimEnd().split("\n").sort();
};

const extractArchive = async (archive, destination) => {
  await fs.mkdir(destination, { recursive: true });
  const extracted = await runCommand("tar", ["-xzf", archive, "-C", destination]);
  assert.equal(extracted.exitCode, 0, extracted.stderr);
  return path.join(destination, "package");
};

const buildAndInspectPackageArchive = async (sourceRoot, root) => {
  const packDestination = path.join(root, "packed");
  await fs.mkdir(packDestination, { recursive: true });
  const packed = await runPnpm(["pack", "--pack-destination", packDestination], { cwd: sourceRoot });
  assert.equal(packed.exitCode, 0, packed.stderr);
  const archive = await packageArchivePath(packDestination);
  const files = await listArchive(archive);
  for (const requiredFile of packedPackageFiles) {
    assert.ok(files.includes(requiredFile), "missing required packed file " + requiredFile);
  }
  assert.deepEqual(files, [...packedPackageFiles]);
  const extractRoot = await extractArchive(archive, path.join(root, "extracted"));
  assert.equal(
    await digestFile(path.join(extractRoot, "src", "runtime-lib.mjs")),
    await digestFile(pluginRuntime),
    "package runtime copy must stay byte-identical to the plugin runtime",
  );
  const help = await runNode(path.join(extractRoot, "bin", "abe-evidence.mjs"), ["--help"], { cwd: root });
  assert.equal(help.exitCode, 0, help.stderr);
  assert.match(help.stdout, /No semantic correctness authority/u);
  return {
    archive,
    digest: await digestFile(archive),
    help: help.stdout,
  };
};

const initArgs = () => [
  "init",
  "--task-id", TASK_ID,
  "--workspace-digest", WORKSPACE_DIGEST,
  "--request-digest", REQUEST_DIGEST,
];

const patchFor = (baseStateDigest, overrides = {}) => ({
  schemaVersion: 1,
  taskId: TASK_ID,
  workspaceDigest: WORKSPACE_DIGEST,
  requestDigest: REQUEST_DIGEST,
  baseStateDigest,
  updatedAt: APPLY_TIME,
  operations: [
    { schemaVersion: 1, op: "setWorkflowTier", value: "substantial" },
    { schemaVersion: 1, op: "setIntent", value: "Build a dependency-free durable evidence CLI." },
    {
      schemaVersion: 1,
      op: "appendAssumption",
      value: {
        schemaVersion: 1,
        id: "A-001",
        question: "Which bounded task identity should this state bind?",
        disposition: "user_direction",
        decision: "Use the explicit task, workspace, and request digests supplied to init/apply.",
        evidence: [],
        reversible: true,
        material: true,
      },
    },
    {
      schemaVersion: 1,
      op: "appendObligation",
      value: {
        schemaVersion: 1,
        id: "O-001",
        requirement: "The CLI writes only validated TaskState artifacts under the current workspace.",
        evidenceSeam: "node plugin/scripts/runtime-lib.mjs validate --state-file .agents/abe/task-0001/state.json",
        negativeCases: ["foreign workspace digest", "stale base digest", "terminal inconsistency"],
        authority: "local repository filesystem",
        required: true,
        status: "pending",
        evidence: [],
        lastRelevantChangeDigest: "none",
      },
    },
    {
      schemaVersion: 1,
      op: "appendIteration",
      value: {
        schemaVersion: 1,
        sequence: 1,
        scope: "Initialized state and first proof obligation.",
        changeDigest: CHANGE_DIGEST,
        impactedObligationIds: ["O-001"],
        impactedEvidenceIds: [],
        sentinelEvidenceIds: [],
        result: "indeterminate",
        nextAction: "Run focused CLI tests.",
      },
    },
    {
      schemaVersion: 1,
      op: "setTerminalState",
      value: {
        schemaVersion: 1,
        declared: "incomplete",
        reason: "Required proof obligation O-001 is not passing yet.",
        unresolvedObligationIds: ["O-001"],
        activeWork: true,
      },
    },
  ],
  ...overrides,
});

const initialize = async (root, entrypoint = pluginRuntime) => {
  const result = await runNode(entrypoint, initArgs(), { cwd: root });
  assert.equal(result.exitCode, 0, result.stderr);
  return result;
};

test("package surface is dependency-free and exposes only the evidence CLI API", async () => {
  const manifest = await readJson(packageJsonPath);
  assert.deepEqual(manifest, {
    name: "@antigravity/abe-evidence-cli",
    version: "0.0.0",
    description: "Dependency-free durable evidence CLI for Antigravity behavior engineering",
    private: true,
    license: "Apache-2.0",
    type: "module",
    exports: {
      ".": "./src/task-state.mjs",
    },
    bin: {
      "abe-evidence": "./bin/abe-evidence.mjs",
    },
    files: [
      "bin/abe-evidence.mjs",
      "src/runtime-lib.mjs",
      "src/task-state.mjs",
    ],
    dependencies: {},
    devDependencies: {},
  });
});

test("packed package output is deterministic, runnable, and fails missing-bin packages", async () => {
  await withTemporaryWorkspace(async (root) => {
    const sourceA = await copyPackageSource(path.join(root, "clean-a"));
    const sourceB = await copyPackageSource(path.join(root, "clean-b"));
    const archiveA = await buildAndInspectPackageArchive(sourceA, path.join(root, "build-a"));
    const archiveB = await buildAndInspectPackageArchive(sourceB, path.join(root, "build-b"));
    assert.equal(archiveA.digest, archiveB.digest);
    assert.equal(archiveA.help, archiveB.help);

    const missingBinSource = await copyPackageSource(path.join(root, "missing-bin"));
    await fs.rm(path.join(missingBinSource, "bin", "abe-evidence.mjs"));
    await assert.rejects(
      () => buildAndInspectPackageArchive(missingBinSource, path.join(root, "missing-bin-build")),
      /missing required packed file package\/bin\/abe-evidence\.mjs/u,
    );
  });
});

test("runtime library and package binary share deterministic help output", async () => {
  await withTemporaryWorkspace(async (root) => {
    const pluginHelp = await runNode(pluginRuntime, ["--help"], { cwd: root });
    const packageHelp = await runNode(packageBin, ["--help"], { cwd: root });
    assert.equal(pluginHelp.exitCode, 0, pluginHelp.stderr);
    assert.equal(packageHelp.exitCode, 0, packageHelp.stderr);
    assert.equal(packageHelp.stdout, pluginHelp.stdout);
    assert.match(pluginHelp.stdout, /abe-evidence init --task-id <id> --workspace-digest <sha256> --request-digest <sha256>/u);
    assert.match(pluginHelp.stdout, /No semantic correctness authority/u);
  });
});

test("behavior lock source revision recovers the locked runtime script bytes", async () => {
  const lock = await readJson(behaviorLockPath);
  const component = lock.components.find((item) => item.kind === "script" && item.path === "scripts/runtime-lib.mjs");
  assert.ok(component, "runtime script component must be locked");
  const recovered = await runCommand("git", ["show", lock.sourceRevision + ":plugin/scripts/runtime-lib.mjs"]);
  assert.equal(recovered.exitCode, 0, recovered.stderr);
  assert.equal(sha256Digest(recovered.stdout), component.digest);
});

test("init atomically creates a valid TaskState and ordinal-zero completion ledger", async () => {
  for (const entrypoint of blackBoxEntrypoints) {
    await withTemporaryWorkspace(async (root) => {
    const result = await initialize(root, entrypoint.path);
    assert.match(result.stdout, /"stateDigest":"sha256:[0-9a-f]{64}"/u);
    assert.equal(result.stderr, "", entrypoint.label);

    const state = await readJson(statePath(root));
    const [event] = await readLedger(ledgerPath(root));
    assert.deepEqual(parseTaskState(state, {
      taskId: TASK_ID,
      workspaceDigest: WORKSPACE_DIGEST,
      requestDigest: REQUEST_DIGEST,
    }), state);
    assert.deepEqual(parseCompletionGateEvent(event, {
      taskId: TASK_ID,
      workspaceDigest: WORKSPACE_DIGEST,
      requestDigest: REQUEST_DIGEST,
    }), event);
    assert.deepEqual(state, {
      schemaVersion: 1,
      taskId: TASK_ID,
      workspaceDigest: WORKSPACE_DIGEST,
      requestDigest: REQUEST_DIGEST,
      workflowTier: "trivial",
      intent: "TaskState initialized; apply an approved or bounded substantial-task patch before implementation.",
      assumptions: [],
      obligations: [],
      iterations: [],
      reviewFindings: [],
      terminalState: {
        schemaVersion: 1,
        declared: "needs_input",
        reason: "Approved or bounded intent and proof obligations are not recorded yet.",
        unresolvedObligationIds: [],
        activeWork: false,
      },
      updatedAt: INIT_TIME,
    });
    assert.deepEqual(event, {
      schemaVersion: 1,
      eventId: TASK_ID + ":initialized:0",
      taskId: TASK_ID,
      workspaceDigest: WORKSPACE_DIGEST,
      requestDigest: REQUEST_DIGEST,
      eventKind: "initialized",
      stopSequenceId: "not_applicable",
      continuationOrdinal: 0,
      frozenBound: 1,
      decision: "none",
      reasonCode: "task_state_initialized",
      previousEventDigest: "genesis",
      occurredAt: INIT_TIME,
    });
    assert.deepEqual(await fs.readdir(taskDir(root)).then((entries) => entries.sort()), [
      "completion-gate.ndjson",
      "state.json",
    ]);
    assert.deepEqual(await fs.readFile(statePath(root)), Buffer.from(canonicalBytes(state)));
    assert.equal(await fs.readFile(ledgerPath(root), "utf8"), Buffer.from(canonicalBytes(event)).toString("utf8") + "\n");
    });
  }
});

test("init refuses a symlinked .agents ancestry instead of escaping the workspace", async () => {
  for (const entrypoint of blackBoxEntrypoints) {
    await withTemporaryWorkspace(async (root) => {
    const outside = await fs.mkdtemp(path.join(os.tmpdir(), "abe-init-escape-"));
    try {
      await fs.symlink(outside, path.join(root, ".agents"));
      const result = await runNode(entrypoint.path, initArgs(), { cwd: root });
      assert.notEqual(result.exitCode, 0, entrypoint.label);
      assert.match(result.stderr, /state\.path_escape/u, entrypoint.label);
      await assert.rejects(() => fs.stat(path.join(outside, "abe", TASK_ID, "state.json")), { code: "ENOENT" });
    } finally {
      await fs.rm(outside, { recursive: true, force: true });
    }
    });
  }
});

test("apply accepts closed patch operations, validates T003 invariants, and preserves the append-only ledger", async () => {
  for (const entrypoint of blackBoxEntrypoints) {
    await withTemporaryWorkspace(async (root) => {
    await initialize(root, entrypoint.path);
    const initialLedger = await fs.readFile(ledgerPath(root), "utf8");
    const baseDigest = await digestFile(statePath(root));
    const patchPath = path.join(root, ".agents", "abe", TASK_ID, "patch.json");
    await writeJson(patchPath, patchFor(baseDigest));

    const applyResult = await runNode(entrypoint.path, ["apply", "--patch-file", ".agents/abe/task-0001/patch.json"], { cwd: root });
    assert.equal(applyResult.exitCode, 0, entrypoint.label + ": " + applyResult.stderr);
    assert.match(applyResult.stdout, /"stateDigest":"sha256:[0-9a-f]{64}"/u);
    assert.equal(await fs.readFile(ledgerPath(root), "utf8"), initialLedger);

    const state = await readJson(statePath(root));
    assert.equal(state.workflowTier, "substantial");
    assert.equal(state.intent, "Build a dependency-free durable evidence CLI.");
    assert.deepEqual(state.obligations.map((item) => item.id), ["O-001"]);
    assert.deepEqual(state.iterations.map((item) => item.sequence), [1]);
    assert.deepEqual(parseTaskState(state, {
      taskId: TASK_ID,
      workspaceDigest: WORKSPACE_DIGEST,
      requestDigest: REQUEST_DIGEST,
    }), state);

    const pluginShow = await runNode(pluginRuntime, ["show", "--state-file", ".agents/abe/task-0001/state.json"], { cwd: root });
    const packageShow = await runNode(packageBin, ["show", "--state-file", ".agents/abe/task-0001/state.json"], { cwd: root });
    assert.equal(pluginShow.exitCode, 0, pluginShow.stderr);
    assert.equal(packageShow.exitCode, 0, packageShow.stderr);
    assert.equal(packageShow.stdout, pluginShow.stdout);
    assert.deepEqual(JSON.parse(pluginShow.stdout), state);

    const validate = await runNode(entrypoint.path, [
      "validate",
      "--state-file", ".agents/abe/task-0001/state.json",
      "--task-id", TASK_ID,
      "--workspace-digest", WORKSPACE_DIGEST,
      "--request-digest", REQUEST_DIGEST,
    ], { cwd: root });
    assert.equal(validate.exitCode, 0, validate.stderr);
    assert.deepEqual(JSON.parse(validate.stdout), {
      ok: true,
      reasonCode: "valid",
      stateDigest: await digestFile(statePath(root)),
    });
    });
  }
});

test("concurrent apply from one base acknowledges at most one update and preserves the survivor", async () => {
  for (const entrypoint of blackBoxEntrypoints) {
    await withTemporaryWorkspace(async (root) => {
    await initialize(root, entrypoint.path);
    const baseDigest = await digestFile(statePath(root));
    const patchFiles = [];
    for (let patchIndex = 0; patchIndex < 24; patchIndex += 1) {
      const operations = [
        { schemaVersion: 1, op: "setIntent", value: "concurrent patch " + patchIndex },
      ];
      for (let assumptionIndex = 0; assumptionIndex < 300; assumptionIndex += 1) {
        operations.push({
          schemaVersion: 1,
          op: "appendAssumption",
          value: {
            schemaVersion: 1,
            id: "A-" + String(patchIndex).padStart(2, "0") + "-" + String(assumptionIndex).padStart(3, "0"),
            question: "Concurrent patch " + patchIndex + " assumption " + assumptionIndex + "?",
            disposition: "user_direction",
            decision: "Append-only same-base concurrency probe.",
            evidence: [],
            reversible: true,
            material: true,
          },
        });
      }
      const patchPath = path.join(root, ".agents", "abe", TASK_ID, "patch-" + patchIndex + ".json");
      await writeJson(patchPath, patchFor(baseDigest, { operations, updatedAt: APPLY_TIME }));
      patchFiles.push(".agents/abe/task-0001/patch-" + patchIndex + ".json");
    }

    const results = await Promise.all(
      patchFiles.map((patchFile) => runNode(entrypoint.path, ["apply", "--patch-file", patchFile], { cwd: root })),
    );
    const successes = results.filter((result) => result.exitCode === 0);
    const failures = results.filter((result) => result.exitCode !== 0);
    assert.equal(successes.length, 1, JSON.stringify(results.map((result) => ({
      exitCode: result.exitCode,
      stderr: result.stderr.trim(),
    }))));
    assert.equal(failures.length, patchFiles.length - 1);
    assert.equal(
      failures.every((result) => /state\.(concurrency_conflict|concurrent_update)/u.test(result.stderr)),
      true,
    );
    const state = await readJson(statePath(root));
    assert.equal(state.assumptions.length, 300);
    const survivingPatch = state.intent.match(/^concurrent patch (?<index>\d+)$/u)?.groups?.index;
    assert.notEqual(survivingPatch, undefined);
    assert.equal(
      state.assumptions.every((assumption) => assumption.id.startsWith("A-" + survivingPatch.padStart(2, "0") + "-")),
      true,
    );
    });
  }
});

test("apply fails closed for unknown operations, stale bases, stale evidence, terminal inconsistency, and foreign identity", async () => {
  for (const entrypoint of blackBoxEntrypoints) {
    await withTemporaryWorkspace(async (root) => {
    await initialize(root, entrypoint.path);
    const original = await fs.readFile(statePath(root), "utf8");
    const baseDigest = await digestFile(statePath(root));
    const patchPath = path.join(root, ".agents", "abe", TASK_ID, "patch.json");

    for (const [name, patch, pattern] of [
      [
        "unknown op",
        patchFor(baseDigest, { operations: [{ schemaVersion: 1, op: "replaceObligations", value: [] }] }),
        /state\.patch_unknown_operation/u,
      ],
      [
        "foreign workspace",
        patchFor(baseDigest, { workspaceDigest: WRONG_DIGEST }),
        new RegExp(ReasonCodes.FOREIGN_IDENTITY, "u"),
      ],
      [
        "stale base",
        patchFor(WRONG_DIGEST),
        /state\.concurrency_conflict/u,
      ],
      [
        "stale evidence",
        patchFor(baseDigest, {
          operations: [
            {
              schemaVersion: 1,
              op: "appendObligation",
              value: {
                schemaVersion: 1,
                id: "O-STALE",
                requirement: "Must have fresh evidence.",
                evidenceSeam: "node --test packages/evidence-cli/test/task-state.test.mjs",
                negativeCases: ["afterChangeDigest mismatch"],
                authority: "local repository filesystem",
                required: true,
                status: "passing",
                evidence: [{
                  schemaVersion: 1,
                  kind: "test",
                  locator: "packages/evidence-cli/test/task-state.test.mjs",
                  digest: EVIDENCE_DIGEST,
                  observedAt: APPLY_TIME,
                  afterChangeDigest: WRONG_DIGEST,
                  result: "pass",
                }],
                lastRelevantChangeDigest: CHANGE_DIGEST,
              },
            },
            {
              schemaVersion: 1,
              op: "setTerminalState",
              value: {
                schemaVersion: 1,
                declared: "complete",
                reason: "Incorrectly complete with stale evidence.",
                unresolvedObligationIds: [],
                activeWork: false,
              },
            },
          ],
        }),
        new RegExp(ReasonCodes.STALE_EVIDENCE, "u"),
      ],
      [
        "terminal inconsistency",
        patchFor(baseDigest, {
          operations: [
            { schemaVersion: 1, op: "setWorkflowTier", value: "substantial" },
            {
              schemaVersion: 1,
              op: "appendObligation",
              value: {
                schemaVersion: 1,
                id: "O-OPEN",
                requirement: "Must not declare complete while required work is pending.",
                evidenceSeam: "node plugin/scripts/runtime-lib.mjs validate --state-file .agents/abe/task-0001/state.json",
                negativeCases: ["complete terminal state with required pending obligation"],
                authority: "local repository filesystem",
                required: true,
                status: "pending",
                evidence: [],
                lastRelevantChangeDigest: "none",
              },
            },
            {
              schemaVersion: 1,
              op: "setTerminalState",
              value: {
                schemaVersion: 1,
                declared: "complete",
                reason: "Incorrectly complete while a required proof obligation is pending.",
                unresolvedObligationIds: [],
                activeWork: false,
              },
            },
          ],
        }),
        new RegExp(ReasonCodes.TERMINAL_INCONSISTENT, "u"),
      ],
    ]) {
      await writeJson(patchPath, patch);
      const result = await runNode(entrypoint.path, ["apply", "--patch-file", ".agents/abe/task-0001/patch.json"], { cwd: root });
      assert.notEqual(result.exitCode, 0, entrypoint.label + ": " + name);
      assert.match(result.stderr, pattern, entrypoint.label + ": " + name);
      assert.equal(await fs.readFile(statePath(root), "utf8"), original, entrypoint.label + ": " + name + " must roll back state");
    }
    });
  }
});

test("validate and show reject malformed state, foreign contexts, traversal, and symlink escapes", async () => {
  for (const entrypoint of blackBoxEntrypoints) {
    await withTemporaryWorkspace(async (root) => {
    await initialize(root, entrypoint.path);
    const malformedPath = path.join(root, ".agents", "abe", TASK_ID, "malformed.json");
    await fs.writeFile(malformedPath, "{\"schemaVersion\":", "utf8");

    const malformed = await runNode(entrypoint.path, ["validate", "--state-file", ".agents/abe/task-0001/malformed.json"], { cwd: root });
    assert.notEqual(malformed.exitCode, 0, entrypoint.label);
    assert.match(malformed.stderr, /state\.invalid_json/u, entrypoint.label);

    const foreign = await runNode(entrypoint.path, [
      "validate",
      "--state-file", ".agents/abe/task-0001/state.json",
      "--workspace-digest", WRONG_DIGEST,
    ], { cwd: root });
    assert.notEqual(foreign.exitCode, 0, entrypoint.label);
    assert.match(foreign.stderr, new RegExp(ReasonCodes.FOREIGN_IDENTITY, "u"), entrypoint.label);

    const traversal = await runNode(entrypoint.path, ["show", "--state-file", "../outside.json"], { cwd: root });
    assert.notEqual(traversal.exitCode, 0, entrypoint.label);
    assert.match(traversal.stderr, /state\.path_escape/u, entrypoint.label);

    const outside = await fs.mkdtemp(path.join(os.tmpdir(), "abe-outside-"));
    try {
      await writeJson(path.join(outside, "state.json"), await readJson(statePath(root)));
      await fs.symlink(outside, path.join(taskDir(root), "link"));
      const symlink = await runNode(entrypoint.path, ["show", "--state-file", ".agents/abe/task-0001/link/state.json"], { cwd: root });
      assert.notEqual(symlink.exitCode, 0, entrypoint.label);
      assert.match(symlink.stderr, /state\.path_escape/u, entrypoint.label);
    } finally {
      await fs.rm(outside, { recursive: true, force: true });
    }
    });
  }
});

test("init rejects unsafe identities and cleans temporary initialization residue", async () => {
  for (const entrypoint of blackBoxEntrypoints) {
    await withTemporaryWorkspace(async (root) => {
    const unsafe = await runNode(entrypoint.path, [
      "init",
      "--task-id", "../evil",
      "--workspace-digest", WORKSPACE_DIGEST,
      "--request-digest", REQUEST_DIGEST,
    ], { cwd: root });
    assert.notEqual(unsafe.exitCode, 0, entrypoint.label);
    assert.match(unsafe.stderr, /state\.invalid_task_id/u, entrypoint.label);
    await assert.rejects(() => fs.stat(path.join(root, ".agents")), { code: "ENOENT" });

    await fs.mkdir(path.join(root, ".agents", "abe"), { recursive: true });
    await fs.writeFile(taskDir(root), "not a directory\n", "utf8");
    const existing = await runNode(entrypoint.path, initArgs(), { cwd: root });
    assert.notEqual(existing.exitCode, 0, entrypoint.label);
    assert.match(existing.stderr, /state\.init_exists/u, entrypoint.label);
    const residue = (await fs.readdir(path.join(root, ".agents", "abe"))).filter((entry) => entry.includes(".tmp"));
    assert.deepEqual(residue, []);
    });
  }
});

test("runtime-library exported API reports the same T003 reason codes as the shared contracts", async () => {
  const runtime = await import("../src/task-state.mjs");
  await withTemporaryWorkspace(async (root) => {
    await runtime.initializeTaskState({
      root,
      taskId: TASK_ID,
      workspaceDigest: WORKSPACE_DIGEST,
      requestDigest: REQUEST_DIGEST,
    });
    const state = await readJson(statePath(root));
    const parsed = runtime.parseTaskState(state);
    assert.deepEqual(parsed, state);
    assert.notEqual(parsed, state);
    parsed.intent = "mutated parsed clone";
    assert.equal(state.intent, "TaskState initialized; apply an approved or bounded substantial-task patch before implementation.");
    assert.throws(
      () => parseTaskState({ ...state, workspaceDigest: WRONG_DIGEST }, {
        taskId: TASK_ID,
        workspaceDigest: WORKSPACE_DIGEST,
        requestDigest: REQUEST_DIGEST,
      }),
      (error) => error instanceof ContractValidationError && error.reasonCode === ReasonCodes.FOREIGN_IDENTITY,
    );
    assert.throws(
      () => runtime.parseTaskState(state, { unexpected: true }),
      (error) => error?.reasonCode === ReasonCodes.INVALID_CONTEXT,
    );
    await assert.rejects(
      () => runtime.validateTaskStateFile({
        root,
        stateFile: ".agents/abe/task-0001/state.json",
        taskId: TASK_ID,
        workspaceDigest: WRONG_DIGEST,
        requestDigest: REQUEST_DIGEST,
      }),
      (error) => error?.reasonCode === ReasonCodes.FOREIGN_IDENTITY,
    );
  });
});
