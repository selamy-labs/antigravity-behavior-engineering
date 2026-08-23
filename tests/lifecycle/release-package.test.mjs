import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  LifecycleValidationError,
  materializeProfileFixture,
  runPluginCommand,
  snapshotProfile,
  verifyProfileDependencies,
} from "../../packages/plugin-tooling/src/lifecycle.mjs";

const repoRoot = path.resolve(new URL("../..", import.meta.url).pathname);
const pluginRoot = path.join(repoRoot, "plugin");
const lifecycleBin = path.join(repoRoot, "packages", "plugin-tooling", "bin", "lifecycle-test.mjs");
const compareBin = path.join(repoRoot, "packages", "plugin-tooling", "bin", "compare-profile.mjs");
const customizedFixture = path.join(repoRoot, "tests", "lifecycle", "fixtures", "customized-profile.json");
const readJson = async (file) => JSON.parse(await fs.readFile(file, "utf8"));

const run = (argv, options = {}) => new Promise((resolve) => {
  const child = spawn(argv[0], argv.slice(1), {
    cwd: options.cwd || repoRoot,
    env: { ...process.env, ...(options.env || {}) },
    stdio: ["ignore", "pipe", "pipe"],
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
});

const withTemporaryRoot = async (prefix, fn) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), prefix));
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

const makeFakeCli = async (root) => {
  const script = path.join(root, "fake-agy.mjs");
  await fs.writeFile(script, `#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
const args = process.argv.slice(2);
if (args[0] === "--version") { process.stdout.write("1.1.19\\n"); process.exit(0); }
if (args[0] !== "plugin") { process.exit(2); }
const profile = process.env.HOME;
const configRoot = path.join(profile, ".gemini", "config");
const pluginsRoot = path.join(configRoot, "plugins");
const configPath = path.join(configRoot, "config.json");
const importsPath = path.join(configRoot, "import_manifest.json");
const readJson = async (file, fallback) => { try { return JSON.parse(await fs.readFile(file, "utf8")); } catch (error) { if (error.code === "ENOENT") return fallback; throw error; } };
const writeJson = async (file, value) => { await fs.mkdir(path.dirname(file), { recursive: true }); await fs.writeFile(file, JSON.stringify(value, null, 2) + "\\n"); };
const command = args[1];
if (command === "validate") { await fs.access(path.join(args[2], "plugin.json")); process.exit(0); }
if (command === "install") {
  const source = args[2];
  const manifest = await readJson(path.join(source, "plugin.json"), null);
  if (!manifest) process.exit(1);
  if (process.env.ABE_FAKE_INTERRUPT_INSTALL === "1") process.exit(12);
  if (process.env.ABE_FAKE_CONFLICT_NAME === manifest.name) process.exit(13);
  if (process.env.ABE_FAKE_PRECEDENCE_CONFLICT_NAME === manifest.name) process.exit(14);
  const destination = path.join(pluginsRoot, manifest.name);
  await fs.rm(destination, { recursive: true, force: true });
  await fs.cp(source, destination, { recursive: true });
  const imports = await readJson(importsPath, { imports: [] });
  imports.imports = (imports.imports || []).filter((entry) => entry.name !== manifest.name);
  imports.imports.push({ name: manifest.name, source: "antigravity", importedAt: "2026-08-23T00:00:00Z", components: ["skills", "hooks"] });
  await writeJson(importsPath, imports);
  process.exit(0);
}
if (command === "list") { process.stdout.write(JSON.stringify(await readJson(importsPath, { imports: [] })) + "\\n"); process.exit(0); }
if (command === "disable" || command === "enable") {
  const config = await readJson(configPath, { plugins: {} });
  config.plugins ||= {};
  config.plugins[args[2]] = { enabled: command === "enable" };
  await writeJson(configPath, config);
  process.exit(0);
}
if (command === "uninstall") {
  await fs.rm(path.join(pluginsRoot, args[2]), { recursive: true, force: true });
  const imports = await readJson(importsPath, { imports: [] });
  imports.imports = (imports.imports || []).filter((entry) => entry.name !== args[2]);
  await writeJson(importsPath, imports);
  process.exit(0);
}
process.exit(2);
`, "utf8");
  await fs.chmod(script, 0o755);
  return script;
};

test("customized fixture is exact, user-owned, and dependency-verifiable", async () => {
  await withTemporaryRoot("abe-release-fixture-", async (root) => {
    const profile = path.join(root, "profile");
    const fixture = await readJson(customizedFixture);
    await materializeProfileFixture(profile, fixture);
    const before = await snapshotProfile(profile);
    const lock = await readJson(path.join(pluginRoot, "behavior-lock.json"));
    const dependencies = await verifyProfileDependencies(profile, lock);

    assert.equal(before.entries.length, Object.keys(fixture.files).length);
    assert.deepEqual(dependencies, [{
      schemaVersion: 1,
      name: "superpowers",
      required: false,
      expectedRevision: "b36e0829c6d0140e93cfef2ca599b1b07d4a7797",
      observedRevision: "b36e0829c6d0140e93cfef2ca599b1b07d4a7797",
      ownership: "user",
      status: "user_owned_verified",
    }]);

    const mismatch = structuredClone(fixture);
    mismatch.files[".abe/dependencies/superpowers.json"].revision = "0".repeat(40);
    const mismatchProfile = path.join(root, "mismatch");
    await materializeProfileFixture(mismatchProfile, mismatch);
    await assert.rejects(
      () => verifyProfileDependencies(mismatchProfile, lock),
      (error) => error instanceof LifecycleValidationError && error.code === "lifecycle.dependency_mismatch",
    );

    const requiredLock = structuredClone(lock);
    requiredLock.dependencies[0].required = true;
    await assert.rejects(
      () => verifyProfileDependencies(path.join(root, "missing"), requiredLock),
      (error) => error instanceof LifecycleValidationError && error.code === "lifecycle.required_dependency_missing",
    );
  });
});

test("compare-profile emits an exact stable diff and fails on changed state", async () => {
  await withTemporaryRoot("abe-release-compare-", async (root) => {
    const beforePath = path.join(root, "before.json");
    const samePath = path.join(root, "same.json");
    const changedPath = path.join(root, "changed.json");
    const profile = path.join(root, "profile");
    await fs.mkdir(profile);
    await fs.writeFile(path.join(profile, "keep.txt"), "keep\n");
    const before = await snapshotProfile(profile);
    await writeJson(beforePath, before);
    await writeJson(samePath, before);
    await fs.writeFile(path.join(profile, "keep.txt"), "changed\n");
    await writeJson(changedPath, await snapshotProfile(profile));

    const same = await run([process.execPath, compareBin, "--before", beforePath, "--after", samePath]);
    assert.equal(same.exitCode, 0, same.stderr);
    assert.deepEqual(JSON.parse(same.stdout).changedPaths, []);

    const changed = await run([process.execPath, compareBin, "--before", beforePath, "--after", changedPath]);
    assert.equal(changed.exitCode, 2);
    assert.deepEqual(JSON.parse(changed.stdout).modifiedPaths, ["keep.txt"]);

    await writeJson(changedPath, {});
    const invalid = await run([process.execPath, compareBin, "--before", beforePath, "--after", changedPath]);
    assert.equal(invalid.exitCode, 2);
    assert.match(invalid.stderr, /lifecycle\.invalid_profile_manifest|lifecycle\.invalid_field/u);
  });
});

test("name, precedence, and interruption controls fail before profile mutation", async () => {
  await withTemporaryRoot("abe-release-controls-", async (root) => {
    const fakeCli = await makeFakeCli(root);
    const lock = await readJson(path.join(pluginRoot, "behavior-lock.json"));
    for (const [variable, exitCode] of [
      ["ABE_FAKE_CONFLICT_NAME", 13],
      ["ABE_FAKE_PRECEDENCE_CONFLICT_NAME", 14],
      ["ABE_FAKE_INTERRUPT_INSTALL", 12],
    ]) {
      const profile = path.join(root, variable.toLowerCase());
      await materializeProfileFixture(profile, { schemaVersion: 1, fixtureId: "clean", files: {} });
      const result = await runPluginCommand(fakeCli, ["install", pluginRoot], {
        profileRoot: profile,
        env: variable === "ABE_FAKE_INTERRUPT_INSTALL"
          ? { [variable]: "1" }
          : { [variable]: lock.packageName },
      });
      assert.equal(result.exitCode, exitCode);
      assert.deepEqual(result.touchedPaths, []);
    }
  });
});

test("release lifecycle is timed, idempotent, reversible, and preserves user-owned dependencies", async () => {
  await withTemporaryRoot("abe-release-lifecycle-", async (root) => {
    const fakeCli = await makeFakeCli(root);
    for (const fixture of ["clean", "customized"]) {
      const profile = path.join(root, fixture + "-profile");
      const recordPath = path.join(root, fixture + "-timing.json");
      const result = await run([
        process.execPath,
        lifecycleBin,
        "--plugin", pluginRoot,
        "--profile-fixture", fixture,
        "--profile-root", profile,
        "--cli", fakeCli,
        "--record-timing", recordPath,
      ]);
      assert.equal(result.exitCode, 0, result.stderr);
      const report = JSON.parse(result.stdout);
      assert.deepEqual(report, await readJson(recordPath));
      assert.equal(report.valid, true);
      assert.equal(report.profileFixture, fixture);
      assert.equal(report.countedInstallVerifyMs < 600_000, true);
      assert.equal(report.totalDurationMs >= report.countedInstallVerifyMs, true);
      assert.equal(report.idempotent, true);
      assert.deepEqual(report.packageOwnedResiduePaths, []);
      assert.deepEqual(report.unintendedUnrelatedChanges, []);
      assert.deepEqual(report.excludedIntervals.map(({ kind, counted }) => ({ kind, counted })), [
        { kind: "authentication", counted: false },
        { kind: "dependency_download", counted: false },
      ]);
      assert.deepEqual(report.operations.map(({ name, exitCode }) => ({ name, exitCode })), [
        { name: "validate", exitCode: 0 },
        { name: "install", exitCode: 0 },
        { name: "verify", exitCode: 0 },
        { name: "repeat_install", exitCode: 0 },
        { name: "disable", exitCode: 0 },
        { name: "enable", exitCode: 0 },
        { name: "upgrade", exitCode: 0 },
        { name: "rollback", exitCode: 0 },
        { name: "uninstall", exitCode: 0 },
      ]);
      assert.equal(report.volatilityReview.rejectedPaths.includes(".gemini/config/config.json"), true);
      assert.equal(report.volatilityReview.rejectedPaths.includes(".gemini/config/import_manifest.json"), true);
      if (fixture === "customized") {
        assert.equal(report.dependencies[0].status, "user_owned_verified");
        assert.equal(report.dependencies[0].preserved, true);
      } else {
        assert.equal(report.dependencies[0].status, "absent_optional");
      }
    }
  });
});

test("installation documentation names the supported surface, dependency ownership, timing exclusions, and removal check", async () => {
  const documentation = await fs.readFile(path.join(repoRoot, "docs", "release", "installation.md"), "utf8");
  for (const required of [
    "Antigravity CLI",
    "1.1.18",
    "Linux x64",
    "agy plugin validate plugin",
    "agy plugin install plugin",
    "Superpowers",
    "user-owned",
    "authentication",
    "dependency download",
    "agy plugin uninstall antigravity-behavior-engineering",
    "compare-profile.mjs",
    "Desktop/IDE is experimental",
    "SDK use is evaluation-only",
  ]) {
    assert.equal(documentation.includes(required), true, required);
  }
});
