import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  PackageValidationError,
  inspectComponents,
  packPlugin,
  validatePlugin,
} from "../../packages/plugin-tooling/src/package-lock.mjs";

const repoRoot = path.resolve(new URL("../..", import.meta.url).pathname);
const pluginRoot = path.join(repoRoot, "plugin");
const validateBin = path.join(repoRoot, "packages", "plugin-tooling", "bin", "validate-plugin.mjs");
const packBin = path.join(repoRoot, "packages", "plugin-tooling", "bin", "pack-plugin.mjs");
const digest = (bytes) => "sha256:" + createHash("sha256").update(bytes).digest("hex");
const readJson = async (file) => JSON.parse(await fs.readFile(file, "utf8"));

const run = (argv, cwd = repoRoot) => new Promise((resolve) => {
  const child = spawn(argv[0], argv.slice(1), { cwd, stdio: ["ignore", "pipe", "pipe"] });
  const stdout = [];
  const stderr = [];
  child.stdout.on("data", (chunk) => stdout.push(chunk));
  child.stderr.on("data", (chunk) => stderr.push(chunk));
  child.on("close", (exitCode) => resolve({
    exitCode,
    stdout: Buffer.concat(stdout).toString("utf8"),
    stderr: Buffer.concat(stderr).toString("utf8"),
  }));
});

const withTemporaryRoot = async (prefix, fn) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), prefix));
  try {
    return await fn(root);
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
};

const copyTree = async (source, destination) => {
  await fs.cp(source, destination, { recursive: true, dereference: false, verbatimSymlinks: true });
};

const writeJson = async (file, value) => {
  await fs.writeFile(file, JSON.stringify(value, null, 2) + "\n", "utf8");
};

const expectPackageError = async (code, fn) => {
  await assert.rejects(fn, (error) => error instanceof PackageValidationError && error.code === code);
};

test("release-candidate manifest and lock expose selected and rejected components exactly", async () => {
  const manifest = await readJson(path.join(pluginRoot, "plugin.json"));
  const lock = await readJson(path.join(pluginRoot, "behavior-lock.json"));
  const report = await validatePlugin(pluginRoot, lock);
  const components = await inspectComponents(pluginRoot);

  assert.deepEqual(manifest, { name: "antigravity-behavior-engineering", version: "0.0.0" });
  assert.equal(report.valid, true);
  assert.equal(report.packageName, manifest.name);
  assert.equal(report.packageVersion, manifest.version);
  assert.equal(report.minimumCliVersion, "1.1.18");
  assert.deepEqual(report.supportedPlatforms, [
    { schemaVersion: 1, os: "linux", architecture: "x64", nodeRange: ">=22 <25" },
  ]);
  assert.deepEqual(report.dependencies, [{
    schemaVersion: 1,
    name: "superpowers",
    sourceUrl: "https://github.com/obra/superpowers",
    revision: "b36e0829c6d0140e93cfef2ca599b1b07d4a7797",
    license: "MIT",
    consumption: "research",
    required: false,
    qualificationEvidence: "docs/provenance/superpowers-lock.md",
  }]);
  assert.deepEqual(components.map(({ kind, name }) => ({ kind, name })), [
    { kind: "skill", name: "evidence-first-framing" },
    { kind: "skill", name: "proof-obligation-contract" },
    { kind: "script", name: "abe-evidence-runtime" },
    { kind: "hook", name: "evidence-observer" },
  ]);
  assert.deepEqual(report.rejectedComponents.map(({ taskId, kind, name, decision }) => ({ taskId, kind, name, decision })), [
    { taskId: "T022", kind: "rule", name: "engineering-evidence-kernel", decision: "not_selected" },
    { taskId: "T026", kind: "skill", name: "audited-iteration", decision: "not_selected" },
    { taskId: "T027", kind: "agent", name: "requirements-falsifier", decision: "not_selected" },
    { taskId: "T028", kind: "agent", name: "quality-falsifier-and-paired-review", decision: "not_selected" },
    { taskId: "T030", kind: "hook", name: "bounded-completion-gate", decision: "not_selected" },
  ]);
  assert.equal(report.rejectedComponents.every(({ evidencePath }) => !evidencePath.startsWith("plugin/")), true);
  assert.equal(report.rejectedComponents.every(({ evidenceDigest }) => /^sha256:[0-9a-f]{64}$/u.test(evidenceDigest)), true);
  for (const rejected of report.rejectedComponents) {
    assert.equal(digest(await fs.readFile(path.join(repoRoot, rejected.evidencePath))), rejected.evidenceDigest);
  }
});

test("validation binds exact file bytes, modes, self-lock exclusion, and trust boundaries", async () => {
  const lock = await readJson(path.join(pluginRoot, "behavior-lock.json"));
  const report = await validatePlugin(pluginRoot, lock);
  const lockedPaths = Object.keys(lock.files);

  assert.deepEqual(lockedPaths, [...lockedPaths].sort());
  assert.equal(lockedPaths.includes("behavior-lock.json"), false);
  assert.deepEqual(report.files.map(({ path: filePath }) => filePath), lockedPaths);
  assert.equal(report.files.find(({ path: filePath }) => filePath === "scripts/runtime-lib.mjs").mode, "0755");
  assert.equal(report.files.filter(({ path: filePath }) => filePath !== "scripts/runtime-lib.mjs").every(({ mode }) => mode === "0644"), true);
  assert.equal(report.files.every(({ path: filePath, digest: fileDigest }) => lock.files[filePath] === fileDigest), true);
  for (const filePath of lockedPaths) {
    const recovered = await run(["git", "show", `${lock.sourceRevision}:plugin/${filePath}`]);
    assert.equal(recovered.exitCode, 0, recovered.stderr);
    assert.equal(digest(Buffer.from(recovered.stdout)), lock.files[filePath]);
  }
  assert.equal(report.forbiddenPackageZonesPresent.length, 0);
  assert.match(report.packageLockDigest, /^sha256:[0-9a-f]{64}$/u);
  assert.match(report.behaviorLockDigest, /^sha256:[0-9a-f]{64}$/u);
  assert.match(report.sourceTreeDigest, /^sha256:[0-9a-f]{64}$/u);
});

test("validation fails closed for drift, unknown files, collisions, bad platforms, and symlinks", async () => {
  await withTemporaryRoot("abe-package-integrity-", async (root) => {
    const drifted = path.join(root, "drifted");
    await copyTree(pluginRoot, drifted);
    await fs.appendFile(path.join(drifted, "hooks.json"), "\n");
    await expectPackageError("package.digest_mismatch", () => validatePlugin(drifted, readJson(path.join(drifted, "behavior-lock.json"))));

    const unknown = path.join(root, "unknown");
    await copyTree(pluginRoot, unknown);
    await fs.writeFile(path.join(unknown, "undeclared.txt"), "unexpected\n");
    await expectPackageError("package.inventory_mismatch", () => validatePlugin(unknown, readJson(path.join(unknown, "behavior-lock.json"))));

    const collision = path.join(root, "collision");
    await copyTree(pluginRoot, collision);
    const collisionLock = await readJson(path.join(collision, "behavior-lock.json"));
    collisionLock.components.push({ ...collisionLock.components[0] });
    await expectPackageError("package.component_collision", () => validatePlugin(collision, collisionLock));

    const badPlatform = path.join(root, "bad-platform");
    await copyTree(pluginRoot, badPlatform);
    const platformLock = await readJson(path.join(badPlatform, "behavior-lock.json"));
    platformLock.supportedPlatforms[0].nodeRange = "latest";
    await expectPackageError("package.invalid_lock", () => validatePlugin(badPlatform, platformLock));

    const symlinked = path.join(root, "symlinked");
    await copyTree(pluginRoot, symlinked);
    await fs.symlink("hooks.json", path.join(symlinked, "hook-link.json"));
    await expectPackageError("package.symlink", () => validatePlugin(symlinked, readJson(path.join(symlinked, "behavior-lock.json"))));
  });
});

test("deterministic pack writes identical tgz bytes and a canonical PackageArchiveRecord", async () => {
  await withTemporaryRoot("abe-package-pack-", async (root) => {
    const firstArchive = path.join(root, "first.tgz");
    const secondArchive = path.join(root, "second.tgz");
    const first = await packPlugin(pluginRoot, firstArchive);
    const second = await packPlugin(pluginRoot, secondArchive);
    const firstBytes = await fs.readFile(firstArchive);
    const secondBytes = await fs.readFile(secondArchive);

    assert.deepEqual(firstBytes, secondBytes);
    assert.deepEqual(first, second);
    assert.deepEqual(first.archiveFormat, { schemaVersion: 1, format: "tgz", version: "1" });
    assert.equal(first.archiveDigest, digest(firstBytes));
    assert.equal(first.byteSize, firstBytes.byteLength);
    assert.match(first.packageLockDigest, /^sha256:[0-9a-f]{64}$/u);
    assert.equal(first.behaviorLockDigest, digest(await fs.readFile(path.join(pluginRoot, "behavior-lock.json"))));
    assert.match(first.sourceTreeDigest, /^sha256:[0-9a-f]{64}$/u);
    assert.match(first.fileManifestDigest, /^sha256:[0-9a-f]{64}$/u);
    assert.match(first.createdByDigest, /^sha256:[0-9a-f]{64}$/u);

    const listed = await run(["tar", "-tzf", firstArchive]);
    assert.equal(listed.exitCode, 0, listed.stderr);
    const archivePaths = listed.stdout.trimEnd().split("\n");
    assert.deepEqual(archivePaths, [...Object.keys((await readJson(path.join(pluginRoot, "behavior-lock.json"))).files), "behavior-lock.json"].sort());

    const unpacked = path.join(root, "unpacked");
    await fs.mkdir(unpacked);
    const extracted = await run(["tar", "-xzf", firstArchive, "-C", unpacked]);
    assert.equal(extracted.exitCode, 0, extracted.stderr);
    const unpackedReport = await validatePlugin(unpacked, await readJson(path.join(unpacked, "behavior-lock.json")));
    assert.equal(unpackedReport.sourceTreeDigest, first.sourceTreeDigest);
  });
});

test("CLI wrappers emit canonical reports and enforce archive and manifest comparison flags", async () => {
  await withTemporaryRoot("abe-package-cli-", async (root) => {
    const archive = path.join(root, "candidate.tgz");
    const recordPath = path.join(root, "candidate-record.json");
    const validation = await run([process.execPath, validateBin, "--root", pluginRoot]);
    assert.equal(validation.exitCode, 0, validation.stderr);
    assert.equal(JSON.parse(validation.stdout).valid, true);

    const packed = await run([
      process.execPath,
      packBin,
      "--root", pluginRoot,
      "--output", archive,
      "--manifest-out", recordPath,
    ]);
    assert.equal(packed.exitCode, 0, packed.stderr);
    assert.deepEqual(JSON.parse(packed.stdout), await readJson(recordPath));

    const comparisonArchive = path.join(root, "comparison.tgz");
    const comparisonRecord = path.join(root, "comparison-record.json");
    const compared = await run([
      process.execPath,
      packBin,
      "--root", pluginRoot,
      "--output", comparisonArchive,
      "--manifest-out", comparisonRecord,
      "--require-archive-match", archive,
      "--require-manifest-match", recordPath,
    ]);
    assert.equal(compared.exitCode, 0, compared.stderr);
    assert.deepEqual(await fs.readFile(comparisonArchive), await fs.readFile(archive));
    assert.deepEqual(await readJson(comparisonRecord), await readJson(recordPath));

    const mismatch = path.join(root, "mismatch.tgz");
    await fs.writeFile(mismatch, "not the archive\n");
    const rejected = await run([
      process.execPath,
      packBin,
      "--root", pluginRoot,
      "--output", path.join(root, "rejected.tgz"),
      "--manifest-out", path.join(root, "rejected-record.json"),
      "--require-archive-match", mismatch,
    ]);
    assert.equal(rejected.exitCode, 2);
    assert.match(rejected.stderr, /package\.archive_mismatch/u);
  });
});
