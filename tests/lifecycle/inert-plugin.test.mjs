import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  LifecycleValidationError,
  diffProfileSnapshots,
  inspectInstall,
  runPluginCommand,
  snapshotProfile,
} from "../../packages/plugin-tooling/src/lifecycle.mjs";

const repoRoot = path.resolve(new URL("../..", import.meta.url).pathname);
const pluginRoot = path.join(repoRoot, "plugin");
const lockPath = path.join(pluginRoot, "behavior-lock.json");
const manifestPath = path.join(pluginRoot, "plugin.json");

const rawDigest = (bytes) => "sha256:" + createHash("sha256").update(bytes).digest("hex");

const readJson = async (file) => JSON.parse(await fs.readFile(file, "utf8"));

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

const copyTree = async (source, destination) => {
  await fs.mkdir(destination, { recursive: true });
  for (const entry of await fs.readdir(source, { withFileTypes: true })) {
    const from = path.join(source, entry.name);
    const to = path.join(destination, entry.name);
    if (entry.isDirectory()) {
      await copyTree(from, to);
    } else if (entry.isFile()) {
      await fs.copyFile(from, to);
    }
  }
};

const fakeAgy = async (root) => {
  const script = path.join(root, "fake-agy.mjs");
  await fs.writeFile(script, `#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";

const fail = async (message, code = 1) => {
  process.stderr.write(message + "\\n");
  process.exit(code);
};

const profileRoot = process.env.HOME;
if (!profileRoot) {
  await fail("HOME required", 2);
}

const configRoot = path.join(profileRoot, ".gemini", "config");
const pluginsRoot = path.join(configRoot, "plugins");
const configPath = path.join(configRoot, "config.json");
const importManifestPath = path.join(configRoot, "import_manifest.json");

const readJson = async (file, fallback) => {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch (error) {
    if (error?.code === "ENOENT") {
      return fallback;
    }
    throw error;
  }
};

const writeJson = async (file, value) => {
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file, JSON.stringify(value, null, 2) + "\\n", "utf8");
};

const readPluginName = async (source) => {
  const manifest = await readJson(path.join(source, "plugin.json"), null);
  if (!manifest || typeof manifest.name !== "string" || manifest.name.length === 0) {
    await fail("plugin-not-found", 1);
  }
  return manifest.name;
};

const copyTree = async (source, destination) => {
  await fs.rm(destination, { recursive: true, force: true });
  await fs.mkdir(destination, { recursive: true });
  for (const entry of await fs.readdir(source, { withFileTypes: true })) {
    const from = path.join(source, entry.name);
    const to = path.join(destination, entry.name);
    if (entry.isDirectory()) {
      await copyTree(from, to);
    } else if (entry.isFile()) {
      await fs.copyFile(from, to);
    }
  }
};

const pluginArgs = process.argv.slice(2);
if (pluginArgs[0] !== "plugin") {
  await fail("unsupported command", 2);
}

const command = pluginArgs[1];
if (command === "validate") {
  const source = pluginArgs[2];
  await readPluginName(source);
  process.stdout.write("[ok] " + source + "\\n");
  process.exit(0);
}

if (command === "install") {
  let source = pluginArgs[2];
  if (source === "antigravity-behavior-engineering@local") {
    source = process.env.ABE_FAKE_REMOTE_PLUGIN_ROOT;
  }
  if (process.env.ABE_FAKE_INTERRUPT_INSTALL === "1") {
    await fail("interrupted-before-write", 12);
  }
  const name = await readPluginName(source);
  if (process.env.ABE_FAKE_CONFLICT_NAME === name) {
    await fail("conflict-before-write", 13);
  }
  await copyTree(source, path.join(pluginsRoot, name));
  const manifest = await readJson(importManifestPath, { imports: [] });
  manifest.imports = (manifest.imports || []).filter((item) => item.name !== name);
  manifest.imports.push({ name, source: "antigravity", importedAt: "2026-08-22T00:00:00Z", components: null });
  await writeJson(importManifestPath, manifest);
  process.stdout.write("[ok] " + name + "\\n");
  process.exit(0);
}

if (command === "list") {
  const manifest = await readJson(importManifestPath, { imports: [] });
  if (!manifest.imports.length) {
    process.stdout.write("No imported plugins.\\n");
  } else {
    process.stdout.write(JSON.stringify(manifest, null, 2) + "\\n");
  }
  process.exit(0);
}

if (command === "enable" || command === "disable") {
  const name = pluginArgs[2];
  try {
    await fs.access(path.join(pluginsRoot, name, "plugin.json"));
  } catch {
    await fail('Error: plugin "' + name + '" not found or invalid', 1);
  }
  const config = await readJson(configPath, { plugins: {} });
  config.plugins ||= {};
  config.plugins[name] = { enabled: command === "enable" };
  await writeJson(configPath, config);
  process.exit(0);
}

if (command === "uninstall") {
  const name = pluginArgs[2];
  await fs.rm(path.join(pluginsRoot, name), { recursive: true, force: true });
  const config = await readJson(configPath, { plugins: {} });
  if (config.plugins) {
    delete config.plugins[name];
  }
  await writeJson(configPath, config);
  await writeJson(importManifestPath, { imports: [] });
  process.stdout.write('Uninstalled plugin "' + name + '"\\n');
  process.exit(0);
}

await fail("unsupported plugin command", 2);
`, "utf8");
  await fs.chmod(script, 0o755);
  return script;
};

const loadLock = async () => readJson(lockPath);

test("inert manifest is the minimal CLI-accepted package and behavior lock covers every package file", async () => {
  const manifest = await readJson(manifestPath);
  const lock = await loadLock();

  assert.deepEqual(Object.keys(manifest).sort(), ["name"]);
  assert.equal(manifest.name, "antigravity-behavior-engineering");
  assert.equal(lock.schemaVersion, 1);
  assert.equal(lock.packageName, manifest.name);
  assert.equal(lock.packageVersion, "0.0.0");
  assert.equal(lock.minimumCliVersion, "1.1.18");
  assert.deepEqual(lock.components, []);
  assert.deepEqual(lock.dependencies, [
    {
      schemaVersion: 1,
      name: "superpowers",
      sourceUrl: "https://github.com/obra/superpowers",
      revision: "b36e0829c6d0140e93cfef2ca599b1b07d4a7797",
      license: "MIT",
      consumption: "research",
      required: false,
      qualificationEvidence: "docs/provenance/superpowers-lock.md",
    },
  ]);
  assert.deepEqual(lock.lifecycle.requiredCommands, [
    "validate",
    "install",
    "list",
    "disable",
    "enable",
    "uninstall",
  ]);

  const actualFiles = [];
  const pending = [pluginRoot];
  while (pending.length > 0) {
    const directory = pending.pop();
    for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
      const absolutePath = path.join(directory, entry.name);
      const relativePath = path.relative(pluginRoot, absolutePath).split(path.sep).join("/");
      if (entry.isDirectory()) {
        pending.push(absolutePath);
      } else if (entry.isFile() && relativePath !== "behavior-lock.json") {
        actualFiles.push(relativePath);
      }
    }
  }
  actualFiles.sort();
  assert.deepEqual(Object.keys(lock.files).sort(), actualFiles);
  for (const relativePath of actualFiles) {
    assert.equal(lock.files[relativePath], rawDigest(await fs.readFile(path.join(pluginRoot, relativePath))));
  }
});

test("snapshotProfile excludes declared Antigravity volatility while preserving unrelated state", async () => {
  await withTemporaryRoot("abe-profile-", async (profileRoot) => {
    await writeJson(path.join(profileRoot, ".gemini", "config", "config.json"), { user: { theme: "dark" } });
    await writeJson(path.join(profileRoot, ".gemini", "config", "import_manifest.json"), { imports: [] });
    await fs.mkdir(path.join(profileRoot, ".gemini", "cache"), { recursive: true });
    await fs.writeFile(path.join(profileRoot, ".gemini", "cache", "last_conversations.json"), "{}\n", "utf8");

    const snapshot = await snapshotProfile(profileRoot, {
      ignoredPaths: [".gemini/config/import_manifest.json", ".gemini/cache/**"],
    });

    assert.deepEqual(snapshot.entries.map((entry) => entry.path), [".gemini/config/config.json"]);
    assert.equal(snapshot.entries[0].digest, rawDigest(Buffer.from(JSON.stringify({ user: { theme: "dark" } }, null, 2) + "\n")));
    assert.match(snapshot.profileDigest, /^sha256:[0-9a-f]{64}$/u);
  });
});

test("inspectInstall reports installed, enabled, disabled, and missing-plugin states from profile files", async () => {
  await withTemporaryRoot("abe-profile-", async (profileRoot) => {
    const lock = await loadLock();
    const installedRoot = path.join(profileRoot, ".gemini", "config", "plugins", lock.packageName);
    await copyTree(pluginRoot, installedRoot);
    await writeJson(path.join(profileRoot, ".gemini", "config", "import_manifest.json"), {
      imports: [{ name: lock.packageName, source: "antigravity", importedAt: "2026-08-22T00:00:00Z", components: null }],
    });
    await writeJson(path.join(profileRoot, ".gemini", "config", "config.json"), {
      plugins: { [lock.packageName]: { enabled: false } },
    });

    const disabled = await inspectInstall(profileRoot, lock);
    assert.equal(disabled.installed, true);
    assert.equal(disabled.enabled, false);
    assert.equal(disabled.discovery.imported, true);
    assert.deepEqual(disabled.components, []);
    assert.equal(disabled.packageFiles.every((file) => file.digest === lock.files[file.packagePath]), true);
    assert.equal(disabled.manifestDigest, lock.files["plugin.json"]);

    await writeJson(path.join(profileRoot, ".gemini", "config", "config.json"), {
      plugins: { [lock.packageName]: { enabled: true } },
    });
    assert.equal((await inspectInstall(profileRoot, lock)).enabled, true);

    await fs.rm(installedRoot, { recursive: true, force: true });
    await assert.rejects(
      () => inspectInstall(profileRoot, lock),
      (error) => error instanceof LifecycleValidationError && error.code === "lifecycle.plugin_not_found",
    );
  });
});

test("fake CLI lifecycle covers validate, local and remote install, list, repeat install, conflict, enable, disable, upgrade, rollback, interrupted install, uninstall, and exact state diff", async () => {
  await withTemporaryRoot("abe-lifecycle-", async (root) => {
    const profileRoot = path.join(root, "profile");
    const customizedProfileRoot = path.join(root, "customized-profile");
    const fakeCli = await fakeAgy(root);
    const lock = await loadLock();
    await fs.mkdir(path.join(profileRoot, ".gemini", "config"), { recursive: true });
    await writeJson(path.join(profileRoot, ".gemini", "config", "user-settings.json"), { keep: "byte-identical" });
    await copyTree(profileRoot, customizedProfileRoot);
    const before = await snapshotProfile(profileRoot, lock.lifecycle.volatilityPolicy);

    const missing = await runPluginCommand(fakeCli, ["validate", path.join(root, "missing-plugin")], { profileRoot });
    assert.equal(missing.exitCode, 1);
    assert.match(missing.stderr, /plugin-not-found/u);
    assert.deepEqual(diffProfileSnapshots(before, await snapshotProfile(profileRoot, lock.lifecycle.volatilityPolicy)).changedPaths, []);

    assert.equal((await runPluginCommand(fakeCli, ["validate", pluginRoot], { profileRoot })).exitCode, 0);
    const localInstall = await runPluginCommand(fakeCli, ["install", pluginRoot], { profileRoot });
    assert.equal(localInstall.exitCode, 0);
    assert.deepEqual(localInstall.discovery.names, [lock.packageName]);
    assert.equal((await inspectInstall(profileRoot, lock)).installed, true);

    const repeat = await runPluginCommand(fakeCli, ["install", pluginRoot], { profileRoot });
    assert.equal(repeat.exitCode, 0);
    assert.deepEqual(repeat.discovery.names, [lock.packageName]);

    const conflict = await runPluginCommand(fakeCli, ["install", pluginRoot], {
      profileRoot,
      env: { ABE_FAKE_CONFLICT_NAME: lock.packageName },
    });
    assert.equal(conflict.exitCode, 13);
    assert.deepEqual(conflict.touchedPaths, []);

    assert.equal((await runPluginCommand(fakeCli, ["disable", lock.packageName], { profileRoot })).exitCode, 0);
    assert.equal((await inspectInstall(profileRoot, lock)).enabled, false);
    assert.equal((await runPluginCommand(fakeCli, ["enable", lock.packageName], { profileRoot })).exitCode, 0);
    assert.equal((await inspectInstall(profileRoot, lock)).enabled, true);

    const upgradeRoot = path.join(root, "upgrade-plugin");
    await copyTree(pluginRoot, upgradeRoot);
    const upgradedManifest = await readJson(path.join(upgradeRoot, "plugin.json"));
    upgradedManifest.name = lock.packageName;
    await writeJson(path.join(upgradeRoot, "plugin.json"), upgradedManifest);
    await fs.writeFile(path.join(upgradeRoot, "UPGRADE-MARKER.txt"), "upgrade\n", "utf8");
    assert.equal((await runPluginCommand(fakeCli, ["install", upgradeRoot], { profileRoot })).exitCode, 0);
    assert.equal((await snapshotProfile(profileRoot, lock.lifecycle.volatilityPolicy)).entries.some((entry) => entry.path.endsWith("UPGRADE-MARKER.txt")), true);
    assert.equal((await runPluginCommand(fakeCli, ["install", pluginRoot], { profileRoot })).exitCode, 0);
    assert.equal((await snapshotProfile(profileRoot, lock.lifecycle.volatilityPolicy)).entries.some((entry) => entry.path.endsWith("UPGRADE-MARKER.txt")), false);

    const interrupted = await runPluginCommand(fakeCli, ["install", pluginRoot], {
      profileRoot,
      env: { ABE_FAKE_INTERRUPT_INSTALL: "1" },
    });
    assert.equal(interrupted.exitCode, 12);
    assert.deepEqual(interrupted.touchedPaths, []);

    const remoteInstall = await runPluginCommand(fakeCli, ["install", "antigravity-behavior-engineering@local"], {
      profileRoot: customizedProfileRoot,
      env: { ABE_FAKE_REMOTE_PLUGIN_ROOT: pluginRoot },
    });
    assert.equal(remoteInstall.exitCode, 0);
    assert.equal((await inspectInstall(customizedProfileRoot, lock)).installed, true);

    const list = await runPluginCommand(fakeCli, ["list"], { profileRoot });
    assert.equal(list.exitCode, 0);
    assert.deepEqual(list.discovery.names, [lock.packageName]);

    assert.equal((await runPluginCommand(fakeCli, ["uninstall", lock.packageName], { profileRoot })).exitCode, 0);
    await assert.rejects(
      () => inspectInstall(profileRoot, lock),
      (error) => error instanceof LifecycleValidationError && error.code === "lifecycle.plugin_not_found",
    );
    const after = await snapshotProfile(profileRoot, lock.lifecycle.volatilityPolicy);
    assert.deepEqual(diffProfileSnapshots(before, after).changedPaths, []);
  });
});
