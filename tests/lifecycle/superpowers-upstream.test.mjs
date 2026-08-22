import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  loadBehaviorLock,
  runPluginCommand,
} from "../../packages/plugin-tooling/src/lifecycle.mjs";

const repoRoot = path.resolve(new URL("../..", import.meta.url).pathname);
const pluginRoot = path.join(repoRoot, "plugin");
const lockPath = path.join(pluginRoot, "behavior-lock.json");
const provenanceDoc = path.join(repoRoot, "docs", "provenance", "superpowers-lock.md");

const SUPERPOWERS = Object.freeze({
  name: "superpowers",
  version: "6.3.0",
  sourceUrl: "https://github.com/obra/superpowers",
  revision: "b36e0829c6d0140e93cfef2ca599b1b07d4a7797",
  rootDigest: "sha256:a89f1095b9170551686c36a85efb811bfffa6f925c6b757d17b4dcd540a6ea00",
  licenseDigest: "sha256:a37e0e9697144819e1d965176ac4ae5bc3fa02d11e7812036bbcadf6dafe2400",
  pluginManifestDigest: "sha256:d7ac84a700062e865715f75626945a2a3324778c68dba1a543c7ed41e48def10",
  geminiExtensionDigest: "sha256:3200d324e4ce3c47edf5cf4b251878febb9c32f64ec33bb9eb58c06d96c8e3b9",
  geminiContextDigest: "sha256:0823da8b7277f8b623746d57c0bee75fda02e4c832fe57843e644d0fe633abbc",
  sessionStartDigest: "sha256:88a060272ca8047e0d1cd73a016e1cebba8396807a44be1e296d7c02dcbb9934",
});

const digestBytes = (bytes) => "sha256:" + createHash("sha256").update(bytes).digest("hex");

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

const writeSyntheticSuperpowersSource = async (root) => {
  await writeJson(path.join(root, "plugin.json"), {
    name: SUPERPOWERS.name,
    version: SUPERPOWERS.version,
    license: "MIT",
    repository: SUPERPOWERS.sourceUrl,
  });
  await writeJson(path.join(root, "gemini-extension.json"), {
    name: SUPERPOWERS.name,
    version: SUPERPOWERS.version,
    description: "Synthetic descriptor for upstream lifecycle conformance only.",
    contextFileName: "GEMINI.md",
  });
  await fs.mkdir(path.join(root, "hooks"), { recursive: true });
  await fs.writeFile(
    path.join(root, "GEMINI.md"),
    "Synthetic upstream context fixture; the real Superpowers body is resolved from the pinned source.\n",
    "utf8",
  );
  await fs.writeFile(path.join(root, "hooks", "session-start"), "#!/bin/sh\nprintf 'superpowers-session-start\\n'\n", "utf8");
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
  await readPluginName(pluginArgs[2]);
  process.stdout.write("[ok] validate\\n");
  process.exit(0);
}
if (command === "install") {
  const source = pluginArgs[2];
  const name = await readPluginName(source);
  const destination = path.join(pluginsRoot, name);
  try {
    await fs.access(destination);
    await fail("plugin-name-collision", 13);
  } catch (error) {
    if (error?.code !== "ENOENT") {
      throw error;
    }
  }
  await copyTree(source, destination);
  const manifest = await readJson(importManifestPath, { imports: [] });
  manifest.imports = (manifest.imports || []).filter((item) => item.name !== name);
  manifest.imports.push({ name, source: "local-pinned-checkout", importedAt: "2026-08-22T00:00:00Z", components: null });
  await writeJson(importManifestPath, manifest);
  process.stdout.write("[ok] install " + name + "\\n");
  process.exit(0);
}
if (command === "list") {
  process.stdout.write(JSON.stringify(await readJson(importManifestPath, { imports: [] }), null, 2) + "\\n");
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
if (command === "session-start") {
  const name = pluginArgs[2];
  const config = await readJson(configPath, { plugins: {} });
  const enabled = config.plugins?.[name]?.enabled !== false;
  if (enabled) {
    await fs.access(path.join(pluginsRoot, name, "hooks", "session-start"));
    process.stdout.write("session-start:" + name + "\\n");
  }
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

const collectPluginFiles = async (root) => {
  const pending = [root];
  const files = [];
  while (pending.length > 0) {
    const directory = pending.pop();
    for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
      const absolutePath = path.join(directory, entry.name);
      const relativePath = path.relative(root, absolutePath).split(path.sep).join("/");
      if (entry.isDirectory()) {
        pending.push(absolutePath);
      } else if (entry.isFile()) {
        files.push(relativePath);
      }
    }
  }
  return files.sort();
};

test("behavior lock pins Superpowers as an upstream research dependency and provenance doc records exact evidence", async () => {
  const lock = await loadBehaviorLock(lockPath);
  const superpowers = lock.dependencies.find((dependency) => dependency.name === SUPERPOWERS.name);
  assert.deepEqual(superpowers, {
    schemaVersion: 1,
    name: SUPERPOWERS.name,
    sourceUrl: SUPERPOWERS.sourceUrl,
    revision: SUPERPOWERS.revision,
    license: "MIT",
    consumption: "research",
    required: false,
    qualificationEvidence: "docs/provenance/superpowers-lock.md",
  });

  const doc = await fs.readFile(provenanceDoc, "utf8");
  for (const expected of [
    SUPERPOWERS.sourceUrl,
    SUPERPOWERS.revision,
    SUPERPOWERS.rootDigest,
    SUPERPOWERS.licenseDigest,
    SUPERPOWERS.pluginManifestDigest,
    SUPERPOWERS.geminiExtensionDigest,
    SUPERPOWERS.geminiContextDigest,
    SUPERPOWERS.sessionStartDigest,
    "MIT",
    "not vendored",
    "external pin",
  ]) {
    assert.match(doc, new RegExp(expected.replaceAll(".", "\\.")), expected);
  }
});

test("plugin tree does not copy upstream Superpowers skill bodies or context bodies", async () => {
  const files = await collectPluginFiles(pluginRoot);
  assert.equal(files.includes("skills/evidence-first-framing/SKILL.md"), true);
  assert.equal(files.some((file) => file.includes("using-superpowers")), false);
  assert.equal(files.some((file) => file === "GEMINI.md" || file === "gemini-extension.json"), false);
  assert.equal(files.some((file) => file.includes("session-start")), false);

  const corpus = (
    await Promise.all(files.map((file) => fs.readFile(path.join(pluginRoot, file), "utf8")))
  ).join("\n---file---\n");
  assert.doesNotMatch(corpus, /@\.\/skills\/using-superpowers\/SKILL\.md/u);
  assert.doesNotMatch(corpus, /Core skills library: TDD, debugging, collaboration patterns/u);
  assert.doesNotMatch(corpus, /Copyright \(c\) 2025 Jesse Vincent/u);
});

test("Superpowers upstream source can be installed, discovered, toggled, session-started, collision-blocked, and uninstalled", async () => {
  await withTemporaryRoot("abe-superpowers-lifecycle-", async (root) => {
    const source = path.join(root, "source");
    const profile = path.join(root, "profile");
    await writeSyntheticSuperpowersSource(source);
    const cli = await fakeAgy(root);

    assert.equal((await runPluginCommand(cli, ["validate", source], { profileRoot: profile, cwd: root })).exitCode, 0);

    const installed = await runPluginCommand(cli, ["install", source], { profileRoot: profile, cwd: root });
    assert.equal(installed.exitCode, 0, installed.stderr);
    assert.match(installed.stdout, /install superpowers/u);

    const pluginJson = await fs.readFile(
      path.join(profile, ".gemini", "config", "plugins", SUPERPOWERS.name, "plugin.json"),
    );
    assert.equal(digestBytes(pluginJson), digestBytes(await fs.readFile(path.join(source, "plugin.json"))));

    const listed = await runPluginCommand(cli, ["list"], { profileRoot: profile, cwd: root });
    assert.equal(listed.exitCode, 0);
    assert.match(listed.stdout, /superpowers/u);
    assert.deepEqual(JSON.parse(listed.stdout).imports.map((item) => item.name), [SUPERPOWERS.name]);

    const disabled = await runPluginCommand(cli, ["disable", SUPERPOWERS.name], { profileRoot: profile, cwd: root });
    assert.equal(disabled.exitCode, 0);
    const disabledStart = await runPluginCommand(cli, ["session-start", SUPERPOWERS.name], { profileRoot: profile, cwd: root });
    assert.equal(disabledStart.exitCode, 0);
    assert.equal(disabledStart.stdout, "");

    const enabled = await runPluginCommand(cli, ["enable", SUPERPOWERS.name], { profileRoot: profile, cwd: root });
    assert.equal(enabled.exitCode, 0);
    const enabledStart = await runPluginCommand(cli, ["session-start", SUPERPOWERS.name], { profileRoot: profile, cwd: root });
    assert.equal(enabledStart.exitCode, 0);
    assert.match(enabledStart.stdout, /session-start:superpowers/u);

    const collision = await runPluginCommand(cli, ["install", source], { profileRoot: profile, cwd: root });
    assert.equal(collision.exitCode, 13);
    assert.match(collision.stderr, /plugin-name-collision/u);

    const uninstalled = await runPluginCommand(cli, ["uninstall", SUPERPOWERS.name], { profileRoot: profile, cwd: root });
    assert.equal(uninstalled.exitCode, 0);
    await assert.rejects(
      () => fs.access(path.join(profile, ".gemini", "config", "plugins", SUPERPOWERS.name, "plugin.json")),
      /ENOENT/u,
    );
  });
});
