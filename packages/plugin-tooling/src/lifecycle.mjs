import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { constants as fsConstants } from "node:fs";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { canonicalBytes, sha256Digest } from "../../contracts/src/canonical-json.mjs";

const DIGEST_PATTERN = /^sha256:[0-9a-f]{64}$/u;
const PINNED_REVISION_PATTERN = /^[0-9a-f]{40}$/u;
const SEMVER_PATTERN = /^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$/u;
const DEFAULT_MAXIMUM_COUNTED_MS = 600_000;
const DEFAULT_MAXIMUM_COMMAND_OUTPUT_BYTES = 1_048_576;
const PACKAGE_LOCK_KEYS = new Set([
  "schemaVersion",
  "packageName",
  "packageVersion",
  "sourceRevision",
  "minimumCliVersion",
  "supportedPlatforms",
  "components",
  "rejectedComponents",
  "dependencies",
  "files",
  "lifecycle",
  "generatedAt",
]);
const PLATFORM_KEYS = new Set(["schemaVersion", "os", "architecture", "nodeRange"]);
const COMPONENT_KEYS = new Set(["schemaVersion", "kind", "name", "path", "claimId", "defaultEnabled", "digest"]);
const REJECTED_COMPONENT_KEYS = new Set(["schemaVersion", "taskId", "kind", "name", "decision", "evidencePath", "evidenceDigest"]);
const COMPONENT_KINDS = new Set(["skill", "rule", "agent", "hook", "script"]);
const DEPENDENCY_KEYS = new Set(["schemaVersion", "name", "sourceUrl", "revision", "license", "consumption", "required", "qualificationEvidence"]);
const DEPENDENCY_CONSUMPTIONS = new Set(["runtime", "development", "research"]);
const LIFECYCLE_KEYS = new Set(["requiredCommands", "volatilityPolicy"]);
const VOLATILITY_KEYS = new Set(["ignoredPaths"]);
const PROFILE_KEYS = new Set(["schemaVersion", "profileDigest", "entries"]);
const PROFILE_ENTRY_KEYS = new Set(["path", "digest", "byteLength"]);

export class LifecycleValidationError extends TypeError {
  constructor(code, fieldPath = "$") {
    super(code + " at " + fieldPath);
    this.name = "LifecycleValidationError";
    this.code = code;
    this.path = fieldPath;
  }
}

const fail = (code, fieldPath = "$") => {
  throw new LifecycleValidationError(code, fieldPath);
};

const digestBytes = (bytes) => "sha256:" + createHash("sha256").update(bytes).digest("hex");

const digestObject = (value) => sha256Digest(canonicalBytes(value));

const assertObject = (value, fieldPath) => {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    fail("lifecycle.invalid_field", fieldPath);
  }
  return value;
};

const assertKnownKeys = (record, allowedKeys, fieldPath) => {
  for (const key of Object.keys(record)) {
    if (!allowedKeys.has(key)) {
      fail("lifecycle.invalid_field", fieldPath + "." + key);
    }
  }
  for (const key of allowedKeys) {
    if (!Object.hasOwn(record, key)) {
      fail("lifecycle.invalid_field", fieldPath + "." + key);
    }
  }
};

const assertNonEmptyString = (value, fieldPath) => {
  if (typeof value !== "string" || value.length === 0 || value.includes("\u0000")) {
    fail("lifecycle.invalid_field", fieldPath);
  }
};

const assertRelativePath = (relativePath, fieldPath) => {
  if (
    typeof relativePath !== "string"
    || relativePath.length === 0
    || path.isAbsolute(relativePath)
    || relativePath.includes("\\")
    || relativePath.includes("\u0000")
  ) {
    fail("lifecycle.invalid_path", fieldPath);
  }
  const segments = relativePath.split("/");
  if (segments.some((segment) => segment === "" || segment === "." || segment === "..")) {
    fail("lifecycle.invalid_path", fieldPath);
  }
};

const assertDigest = (value, fieldPath) => {
  if (typeof value !== "string" || !DIGEST_PATTERN.test(value)) {
    fail("lifecycle.invalid_digest", fieldPath);
  }
};

const assertSemver = (value, fieldPath) => {
  if (typeof value !== "string" || !SEMVER_PATTERN.test(value)) {
    fail("lifecycle.invalid_field", fieldPath);
  }
};

const validatePlatform = (platform, index) => {
  assertObject(platform, "$.supportedPlatforms[" + index + "]");
  assertKnownKeys(platform, PLATFORM_KEYS, "$.supportedPlatforms[" + index + "]");
  if (platform.schemaVersion !== 1) {
    fail("lifecycle.invalid_field", "$.supportedPlatforms[" + index + "].schemaVersion");
  }
  assertNonEmptyString(platform.os, "$.supportedPlatforms[" + index + "].os");
  assertNonEmptyString(platform.architecture, "$.supportedPlatforms[" + index + "].architecture");
  assertNonEmptyString(platform.nodeRange, "$.supportedPlatforms[" + index + "].nodeRange");
};

const validateComponent = (component, index) => {
  assertObject(component, "$.components[" + index + "]");
  assertKnownKeys(component, COMPONENT_KEYS, "$.components[" + index + "]");
  if (component.schemaVersion !== 1 || !COMPONENT_KINDS.has(component.kind)) {
    fail("lifecycle.invalid_field", "$.components[" + index + "].kind");
  }
  assertNonEmptyString(component.name, "$.components[" + index + "].name");
  assertRelativePath(component.path, "$.components[" + index + "].path");
  assertNonEmptyString(component.claimId, "$.components[" + index + "].claimId");
  if (typeof component.defaultEnabled !== "boolean") {
    fail("lifecycle.invalid_field", "$.components[" + index + "].defaultEnabled");
  }
  assertDigest(component.digest, "$.components[" + index + "].digest");
};

const validateRejectedComponent = (component, index) => {
  const fieldPath = "$.rejectedComponents[" + index + "]";
  assertObject(component, fieldPath);
  assertKnownKeys(component, REJECTED_COMPONENT_KEYS, fieldPath);
  if (component.schemaVersion !== 1 || !/^T[0-9]{3}$/u.test(component.taskId) || !COMPONENT_KINDS.has(component.kind)) {
    fail("lifecycle.invalid_field", fieldPath);
  }
  assertNonEmptyString(component.name, fieldPath + ".name");
  if (component.decision !== "not_selected") {
    fail("lifecycle.invalid_field", fieldPath + ".decision");
  }
  assertRelativePath(component.evidencePath, fieldPath + ".evidencePath");
  assertDigest(component.evidenceDigest, fieldPath + ".evidenceDigest");
};

const validateDependency = (dependency, index) => {
  assertObject(dependency, "$.dependencies[" + index + "]");
  assertKnownKeys(dependency, DEPENDENCY_KEYS, "$.dependencies[" + index + "]");
  if (dependency.schemaVersion !== 1) {
    fail("lifecycle.invalid_field", "$.dependencies[" + index + "].schemaVersion");
  }
  assertNonEmptyString(dependency.name, "$.dependencies[" + index + "].name");
  if (typeof dependency.sourceUrl !== "string" || !dependency.sourceUrl.startsWith("https://") || dependency.sourceUrl.includes("\u0000")) {
    fail("lifecycle.invalid_field", "$.dependencies[" + index + "].sourceUrl");
  }
  if (typeof dependency.revision !== "string" || !PINNED_REVISION_PATTERN.test(dependency.revision)) {
    fail("lifecycle.invalid_field", "$.dependencies[" + index + "].revision");
  }
  assertNonEmptyString(dependency.license, "$.dependencies[" + index + "].license");
  if (!DEPENDENCY_CONSUMPTIONS.has(dependency.consumption)) {
    fail("lifecycle.invalid_field", "$.dependencies[" + index + "].consumption");
  }
  if (typeof dependency.required !== "boolean") {
    fail("lifecycle.invalid_field", "$.dependencies[" + index + "].required");
  }
  if (dependency.qualificationEvidence !== "not_qualified") {
    assertRelativePath(dependency.qualificationEvidence, "$.dependencies[" + index + "].qualificationEvidence");
  }
  if (dependency.required && dependency.qualificationEvidence === "not_qualified") {
    fail("lifecycle.unqualified_required_dependency", "$.dependencies[" + index + "].qualificationEvidence");
  }
};

const validateLifecycle = (lifecycle) => {
  assertObject(lifecycle, "$.lifecycle");
  assertKnownKeys(lifecycle, LIFECYCLE_KEYS, "$.lifecycle");
  if (!Array.isArray(lifecycle.requiredCommands) || lifecycle.requiredCommands.length === 0) {
    fail("lifecycle.invalid_field", "$.lifecycle.requiredCommands");
  }
  for (const [index, command] of lifecycle.requiredCommands.entries()) {
    assertNonEmptyString(command, "$.lifecycle.requiredCommands[" + index + "]");
  }
  assertObject(lifecycle.volatilityPolicy, "$.lifecycle.volatilityPolicy");
  assertKnownKeys(lifecycle.volatilityPolicy, VOLATILITY_KEYS, "$.lifecycle.volatilityPolicy");
  if (!Array.isArray(lifecycle.volatilityPolicy.ignoredPaths)) {
    fail("lifecycle.invalid_field", "$.lifecycle.volatilityPolicy.ignoredPaths");
  }
  for (const [index, ignoredPath] of lifecycle.volatilityPolicy.ignoredPaths.entries()) {
    if (typeof ignoredPath !== "string" || ignoredPath.length === 0 || path.isAbsolute(ignoredPath) || ignoredPath.includes("\u0000")) {
      fail("lifecycle.invalid_path", "$.lifecycle.volatilityPolicy.ignoredPaths[" + index + "]");
    }
  }
};

const validateLock = (lock) => {
  assertObject(lock, "$");
  assertKnownKeys(lock, PACKAGE_LOCK_KEYS, "$");
  if (lock.schemaVersion !== 1) {
    fail("lifecycle.invalid_field", "$.schemaVersion");
  }
  assertNonEmptyString(lock.packageName, "$.packageName");
  assertSemver(lock.packageVersion, "$.packageVersion");
  if (typeof lock.sourceRevision !== "string" || !PINNED_REVISION_PATTERN.test(lock.sourceRevision)) {
    fail("lifecycle.invalid_field", "$.sourceRevision");
  }
  assertSemver(lock.minimumCliVersion, "$.minimumCliVersion");
  if (!Array.isArray(lock.supportedPlatforms) || lock.supportedPlatforms.length === 0) {
    fail("lifecycle.invalid_field", "$.supportedPlatforms");
  }
  lock.supportedPlatforms.forEach(validatePlatform);
  if (!Array.isArray(lock.components)) {
    fail("lifecycle.invalid_field", "$.components");
  }
  const components = new Set();
  lock.components.forEach((component, index) => {
    validateComponent(component, index);
    const key = component.kind + "\n" + component.name;
    if (components.has(key)) {
      fail("lifecycle.invalid_field", "$.components");
    }
    components.add(key);
  });
  if (!Array.isArray(lock.rejectedComponents)) {
    fail("lifecycle.invalid_field", "$.rejectedComponents");
  }
  const rejectedComponents = new Set();
  lock.rejectedComponents.forEach((component, index) => {
    validateRejectedComponent(component, index);
    const key = component.kind + "\n" + component.name;
    if (components.has(key) || rejectedComponents.has(key)) {
      fail("lifecycle.invalid_field", "$.rejectedComponents");
    }
    rejectedComponents.add(key);
  });
  if (!Array.isArray(lock.dependencies)) {
    fail("lifecycle.invalid_field", "$.dependencies");
  }
  const dependencies = new Set();
  lock.dependencies.forEach((dependency, index) => {
    validateDependency(dependency, index);
    if (dependencies.has(dependency.name)) {
      fail("lifecycle.invalid_field", "$.dependencies");
    }
    dependencies.add(dependency.name);
  });
  assertObject(lock.files, "$.files");
  for (const [relativePath, digest] of Object.entries(lock.files)) {
    assertRelativePath(relativePath, "$.files");
    assertDigest(digest, "$.files." + relativePath);
  }
  validateLifecycle(lock.lifecycle);
  assertNonEmptyString(lock.generatedAt, "$.generatedAt");
  return lock;
};

const ignored = (relativePath, volatilityPolicy = {}) => {
  const ignoredPaths = Array.isArray(volatilityPolicy.ignoredPaths) ? volatilityPolicy.ignoredPaths : [];
  return ignoredPaths.some((pattern) => {
    if (pattern.endsWith("/**")) {
      const prefix = pattern.slice(0, -3);
      return relativePath === prefix || relativePath.startsWith(prefix + "/");
    }
    return relativePath === pattern;
  });
};

const readJsonFile = async (file, fallback) => {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch (error) {
    if (error?.code === "ENOENT") {
      return fallback;
    }
    fail("lifecycle.invalid_json", file);
  }
};

const parseCapturedJson = (bytes, fieldPath) => {
  try {
    return JSON.parse(Buffer.from(bytes).toString("utf8"));
  } catch {
    fail("lifecycle.invalid_json", fieldPath);
  }
};

const profileFiles = async (profileRoot, volatilityPolicy, { includeBytes = false } = {}) => {
  const resolvedRoot = path.resolve(profileRoot);
  const canonicalRoot = await fs.realpath(resolvedRoot).catch((error) => {
    if (error?.code === "ENOENT") {
      fail("lifecycle.profile_not_found", "$.profileRoot");
    }
    throw error;
  });
  if (canonicalRoot !== resolvedRoot) fail("lifecycle.profile_symlink", "$.profileRoot");
  const entries = [];
  const scanDirectory = async (directoryHandle, prefix) => {
    const descriptorRoot = `/proc/self/fd/${directoryHandle.fd}`;
    const children = await fs.readdir(descriptorRoot, { withFileTypes: true });
    children.sort((left, right) => left.name.localeCompare(right.name));
    for (const child of children) {
      const relativePath = prefix.length === 0 ? child.name : prefix + "/" + child.name;
      const descriptorPath = descriptorRoot + "/" + child.name;
      if (ignored(relativePath, volatilityPolicy)) {
        continue;
      }
      if (child.isSymbolicLink()) {
        fail("lifecycle.profile_symlink", relativePath);
      }
      if (child.isDirectory()) {
        const childHandle = await fs.open(
          descriptorPath,
          fsConstants.O_RDONLY | fsConstants.O_DIRECTORY | fsConstants.O_NOFOLLOW,
        ).catch(() => fail("lifecycle.profile_symlink", relativePath));
        try {
          await scanDirectory(childHandle, relativePath);
        } finally {
          await childHandle.close();
        }
      } else if (child.isFile()) {
        const fileHandle = await fs.open(
          descriptorPath,
          fsConstants.O_RDONLY | fsConstants.O_NOFOLLOW,
        ).catch(() => fail("lifecycle.profile_symlink", relativePath));
        try {
          const status = await fileHandle.stat();
          if (!status.isFile()) fail("lifecycle.invalid_profile_file", relativePath);
          const bytes = await fileHandle.readFile();
          entries.push({
            path: relativePath,
            digest: digestBytes(bytes),
            byteLength: bytes.byteLength,
            ...(includeBytes ? { bytes } : {}),
          });
        } finally {
          await fileHandle.close();
        }
      } else {
        fail("lifecycle.invalid_profile_file", relativePath);
      }
    }
  };

  const rootHandle = await fs.open(
    canonicalRoot,
    fsConstants.O_RDONLY | fsConstants.O_DIRECTORY | fsConstants.O_NOFOLLOW,
  ).catch(() => fail("lifecycle.profile_symlink", "$.profileRoot"));
  try {
    await scanDirectory(rootHandle, "");
  } finally {
    await rootHandle.close();
  }
  entries.sort((left, right) => left.path.localeCompare(right.path));
  return entries;
};

export const snapshotProfile = async (profileRoot, volatilityPolicy = {}) => {
  const entries = await profileFiles(profileRoot, volatilityPolicy);
  return {
    schemaVersion: 1,
    profileDigest: digestObject(entries),
    entries,
  };
};

export const validateProfileSnapshot = (snapshot, fieldPath = "$") => {
  assertObject(snapshot, fieldPath);
  assertKnownKeys(snapshot, PROFILE_KEYS, fieldPath);
  if (snapshot.schemaVersion !== 1 || !Array.isArray(snapshot.entries)) fail("lifecycle.invalid_profile_manifest", fieldPath);
  assertDigest(snapshot.profileDigest, fieldPath + ".profileDigest");
  let previous = null;
  for (const [index, entry] of snapshot.entries.entries()) {
    const entryPath = fieldPath + `.entries[${index}]`;
    assertObject(entry, entryPath);
    assertKnownKeys(entry, PROFILE_ENTRY_KEYS, entryPath);
    assertRelativePath(entry.path, entryPath + ".path");
    assertDigest(entry.digest, entryPath + ".digest");
    if (!Number.isSafeInteger(entry.byteLength) || entry.byteLength < 0) fail("lifecycle.invalid_profile_manifest", entryPath + ".byteLength");
    if (previous !== null && previous.localeCompare(entry.path) >= 0) fail("lifecycle.invalid_profile_manifest", entryPath + ".path");
    previous = entry.path;
  }
  if (digestObject(snapshot.entries) !== snapshot.profileDigest) fail("lifecycle.profile_digest_mismatch", fieldPath + ".profileDigest");
  return snapshot;
};

export const diffProfileSnapshots = (beforeInput, afterInput) => {
  const before = validateProfileSnapshot(beforeInput, "$.before");
  const after = validateProfileSnapshot(afterInput, "$.after");
  const beforeEntries = new Map(before.entries.map((entry) => [entry.path, entry]));
  const afterEntries = new Map(after.entries.map((entry) => [entry.path, entry]));
  const addedPaths = [...afterEntries.keys()].filter((entryPath) => !beforeEntries.has(entryPath)).sort();
  const removedPaths = [...beforeEntries.keys()].filter((entryPath) => !afterEntries.has(entryPath)).sort();
  const modifiedPaths = [...afterEntries.keys()]
    .filter((entryPath) => beforeEntries.has(entryPath) && beforeEntries.get(entryPath).digest !== afterEntries.get(entryPath).digest)
    .sort();
  return {
    schemaVersion: 1,
    beforeDigest: before.profileDigest,
    afterDigest: after.profileDigest,
    addedPaths,
    removedPaths,
    modifiedPaths,
    changedPaths: [...addedPaths, ...modifiedPaths, ...removedPaths].sort(),
  };
};

const installedPluginRoot = (profileRoot, packageName) => path.join(profileRoot, ".gemini", "config", "plugins", packageName);

const readDiscovery = async (profileRoot, packageName) => {
  const manifest = await readJsonFile(path.join(profileRoot, ".gemini", "config", "import_manifest.json"), { imports: [] });
  const imports = Array.isArray(manifest.imports) ? manifest.imports : [];
  const names = imports.map((item) => String(item.name || "")).filter((name) => name.length > 0).sort();
  const imported = imports.find((item) => item.name === packageName);
  return {
    schemaVersion: 1,
    imported: names.includes(packageName),
    names,
    components: imported?.components ?? null,
    source: typeof imported?.source === "string" ? imported.source : null,
  };
};

export const inspectInstall = async (profileRoot, expectedLock) => {
  const lock = validateLock(expectedLock);
  const root = installedPluginRoot(profileRoot, lock.packageName);
  const capturedFiles = await profileFiles(root, {}, { includeBytes: true }).catch((error) => {
    if (error instanceof LifecycleValidationError && error.code === "lifecycle.profile_not_found") fail("lifecycle.plugin_not_found", root);
    throw error;
  });
  const byPath = new Map(capturedFiles.map((entry) => [entry.path, entry]));
  const manifestFile = byPath.get("plugin.json");
  const behaviorLockFile = byPath.get("behavior-lock.json");
  if (!manifestFile || !behaviorLockFile) fail("lifecycle.package_file_missing", !manifestFile ? "plugin.json" : "behavior-lock.json");
  const manifest = parseCapturedJson(manifestFile.bytes, "plugin.json");
  if (manifest.name !== lock.packageName) {
    fail("lifecycle.plugin_name_mismatch", "plugin.json");
  }
  if (manifest.version !== lock.packageVersion) {
    fail("lifecycle.plugin_version_mismatch", "plugin.json");
  }
  const installedLock = parseCapturedJson(behaviorLockFile.bytes, "behavior-lock.json");
  if (!Buffer.from(canonicalBytes(installedLock)).equals(Buffer.from(canonicalBytes(lock)))) {
    fail("lifecycle.package_file_digest_mismatch", "behavior-lock.json");
  }

  const packageFiles = [];
  for (const [relativePath, expectedDigest] of Object.entries(lock.files).sort(([left], [right]) => left.localeCompare(right))) {
    const captured = byPath.get(relativePath);
    if (!captured) fail("lifecycle.package_file_missing", relativePath);
    if (captured.digest !== expectedDigest) {
      fail("lifecycle.package_file_digest_mismatch", relativePath);
    }
    packageFiles.push({ packagePath: relativePath, digest: captured.digest, byteLength: captured.byteLength });
  }

  const installedFiles = capturedFiles.map((entry) => entry.path);
  const unexpectedFiles = installedFiles.filter((relativePath) => relativePath !== "behavior-lock.json" && !Object.hasOwn(lock.files, relativePath));
  if (unexpectedFiles.length > 0) {
    fail("lifecycle.package_unexpected_file", unexpectedFiles[0]);
  }

  const config = await readJsonFile(path.join(profileRoot, ".gemini", "config", "config.json"), { plugins: {} });
  const enabledValue = config?.plugins?.[lock.packageName]?.enabled;
  const discovery = await readDiscovery(profileRoot, lock.packageName);
  return {
    schemaVersion: 1,
    pluginName: lock.packageName,
    installed: true,
    enabled: typeof enabledValue === "boolean" ? enabledValue : true,
    discovery,
    components: [...lock.components],
    rejectedComponents: [...lock.rejectedComponents],
    packageFiles,
    installedFiles,
    manifestDigest: packageFiles.find((file) => file.packagePath === "plugin.json").digest,
  };
};

const runProcess = (argv, options) => new Promise((resolve) => {
  const child = spawn(argv[0], argv.slice(1), {
    cwd: options.cwd,
    env: options.env,
    detached: process.platform !== "win32",
    shell: false,
    stdio: ["ignore", "pipe", "pipe"],
  });
  let stdout = "";
  let stderr = "";
  let capturedBytes = 0;
  let terminationReason = null;
  let settled = false;
  let forceKillTimer;
  const maximumOutputBytes = options.maximumOutputBytes;
  const signalChild = (signal) => {
    try {
      if (process.platform !== "win32" && Number.isInteger(child.pid)) process.kill(-child.pid, signal);
      else child.kill(signal);
    } catch {
      try {
        child.kill(signal);
      } catch {
        // The process or process group has already exited.
      }
    }
  };
  const terminate = (reason) => {
    if (terminationReason !== null) return;
    terminationReason = reason;
    signalChild("SIGTERM");
    forceKillTimer = setTimeout(() => {
      signalChild("SIGKILL");
    }, 100);
    forceKillTimer.unref();
  };
  const capture = (current, chunk) => {
    const remaining = Math.max(0, maximumOutputBytes - capturedBytes);
    const bytes = Buffer.from(chunk);
    capturedBytes += bytes.byteLength;
    if (remaining > 0) current += bytes.subarray(0, remaining).toString("utf8");
    if (capturedBytes > maximumOutputBytes) terminate("output_limit");
    return current;
  };
  const timeout = setTimeout(() => terminate("timeout"), options.timeoutMs);
  timeout.unref();
  child.stdout.setEncoding("utf8");
  child.stderr.setEncoding("utf8");
  child.stdout.on("data", (chunk) => {
    stdout = capture(stdout, chunk);
  });
  child.stderr.on("data", (chunk) => {
    stderr = capture(stderr, chunk);
  });
  child.on("error", (error) => {
    if (settled) return;
    settled = true;
    clearTimeout(timeout);
    if (forceKillTimer) clearTimeout(forceKillTimer);
    resolve({ exitCode: 127, stdout, stderr: stderr + String(error.message) + "\n", terminationReason });
  });
  child.on("close", (code) => {
    if (settled) return;
    settled = true;
    clearTimeout(timeout);
    if (forceKillTimer) clearTimeout(forceKillTimer);
    const forcedExitCode = terminationReason === "timeout" ? 124 : 125;
    resolve({
      exitCode: terminationReason === null && Number.isInteger(code) ? code : forcedExitCode,
      stdout,
      stderr,
      terminationReason,
    });
  });
});

export const runPluginCommand = async (cliPath, args, {
  profileRoot,
  cwd,
  env = {},
  volatilityPolicy,
  timeoutMs = DEFAULT_MAXIMUM_COUNTED_MS,
  maximumOutputBytes = DEFAULT_MAXIMUM_COMMAND_OUTPUT_BYTES,
} = {}) => {
  if (typeof profileRoot !== "string" || profileRoot.length === 0) {
    fail("lifecycle.profile_not_found", "$.profileRoot");
  }
  if (!Number.isSafeInteger(timeoutMs) || timeoutMs <= 0 || timeoutMs > DEFAULT_MAXIMUM_COUNTED_MS) {
    fail("lifecycle.invalid_field", "$.timeoutMs");
  }
  if (
    !Number.isSafeInteger(maximumOutputBytes)
    || maximumOutputBytes <= 0
    || maximumOutputBytes > DEFAULT_MAXIMUM_COMMAND_OUTPUT_BYTES
  ) {
    fail("lifecycle.invalid_field", "$.maximumOutputBytes");
  }
  await fs.mkdir(profileRoot, { recursive: true });
  const policy = volatilityPolicy || {};
  const before = await snapshotProfile(profileRoot, policy);
  const argv = [String(cliPath), "plugin", ...args.map(String)];
  const processResult = await runProcess(argv, {
    cwd,
    env: {
      PATH: process.env.PATH || "/usr/bin:/bin:/usr/sbin:/sbin",
      LANG: process.env.LANG || "C.UTF-8",
      HOME: profileRoot,
      ...Object.fromEntries(Object.entries(env).map(([key, value]) => [String(key), String(value)])),
    },
    timeoutMs,
    maximumOutputBytes,
  });
  const after = await snapshotProfile(profileRoot, policy);
  const diff = diffProfileSnapshots(before, after);
  const command = String(args[0] || "");
  const packageName = command === "install" && args[1] && !String(args[1]).includes(path.sep) ? String(args[1]).split("@")[0] : "";
  const discovery = await readDiscovery(profileRoot, packageName || "").catch(() => ({
    schemaVersion: 1,
    imported: false,
    names: [],
    components: null,
  }));
  return {
    schemaVersion: 1,
    command,
    argv,
    exitCode: processResult.exitCode,
    stdout: processResult.stdout,
    stderr: processResult.stderr,
    terminationReason: processResult.terminationReason,
    beforeDigest: before.profileDigest,
    afterDigest: after.profileDigest,
    touchedPaths: diff.changedPaths,
    discovery,
  };
};

export const loadBehaviorLock = async (file) => validateLock(JSON.parse(await fs.readFile(file, "utf8")));

const FIXTURE_KEYS = new Set(["schemaVersion", "fixtureId", "files"]);
const DEPENDENCY_STATE_KEYS = new Set(["schemaVersion", "name", "sourceUrl", "revision", "ownership", "artifactDigest"]);
const PROFILE_METADATA_PATHS = [
  ".gemini/config/config.json",
  ".gemini/config/import_manifest.json",
];

const canonicalJsonLine = (value) => Buffer.concat([Buffer.from(canonicalBytes(value)), Buffer.from("\n")]);

const readOptionalBytes = async (file) => fs.readFile(file).catch((error) => {
  if (error?.code === "ENOENT") return null;
  throw error;
});

const writeFixtureFile = async (root, relativePath, value) => {
  assertRelativePath(relativePath, "$.files." + relativePath);
  const target = path.join(root, ...relativePath.split("/"));
  const parent = path.dirname(target);
  await fs.mkdir(parent, { recursive: true });
  const canonicalParent = await fs.realpath(parent);
  if (canonicalParent !== parent || !canonicalParent.startsWith(root + path.sep)) {
    fail("lifecycle.profile_escape", relativePath);
  }
  await fs.writeFile(target, canonicalJsonLine(value), { flag: "wx", mode: 0o600 });
};

export const materializeProfileFixture = async (profileRoot, fixture) => {
  assertObject(fixture, "$");
  assertKnownKeys(fixture, FIXTURE_KEYS, "$");
  if (fixture.schemaVersion !== 1 || !["clean", "customized"].includes(fixture.fixtureId)) {
    fail("lifecycle.invalid_fixture", "$.fixtureId");
  }
  assertObject(fixture.files, "$.files");
  const absoluteRoot = path.resolve(profileRoot);
  await fs.mkdir(absoluteRoot, { recursive: true });
  if (await fs.realpath(absoluteRoot) !== absoluteRoot) fail("lifecycle.profile_symlink", absoluteRoot);
  if ((await fs.readdir(absoluteRoot)).length > 0) fail("lifecycle.profile_not_empty", absoluteRoot);
  for (const [relativePath, value] of Object.entries(fixture.files).sort(([left], [right]) => left.localeCompare(right))) {
    assertObject(value, "$.files." + relativePath);
    await writeFixtureFile(absoluteRoot, relativePath, value);
  }
  return snapshotProfile(absoluteRoot);
};

export const verifyProfileDependencies = async (profileRoot, lockInput) => {
  const lock = validateLock(lockInput);
  const records = [];
  for (const dependency of lock.dependencies) {
    if (!/^[0-9A-Za-z][0-9A-Za-z._-]*$/u.test(dependency.name)) {
      fail("lifecycle.invalid_field", "$.dependencies.name");
    }
    const statePath = path.join(path.resolve(profileRoot), ".abe", "dependencies", dependency.name + ".json");
    const state = await readJsonFile(statePath, null);
    if (state === null) {
      if (dependency.required) fail("lifecycle.required_dependency_missing", dependency.name);
      records.push({
        schemaVersion: 1,
        name: dependency.name,
        required: false,
        expectedRevision: dependency.revision,
        observedRevision: null,
        ownership: "none",
        status: "absent_optional",
      });
      continue;
    }
    assertObject(state, dependency.name);
    assertKnownKeys(state, DEPENDENCY_STATE_KEYS, dependency.name);
    if (state.schemaVersion !== 1 || state.name !== dependency.name || !["user", "release"].includes(state.ownership)) {
      fail("lifecycle.invalid_dependency_state", dependency.name);
    }
    if (state.sourceUrl !== dependency.sourceUrl) fail("lifecycle.dependency_source_mismatch", dependency.name);
    if (state.revision !== dependency.revision) fail("lifecycle.dependency_mismatch", dependency.name);
    assertDigest(state.artifactDigest, dependency.name + ".artifactDigest");
    const artifactRoot = installedPluginRoot(profileRoot, dependency.name);
    const artifactFiles = await profileFiles(artifactRoot, {}, { includeBytes: true }).catch((error) => {
      if (error instanceof LifecycleValidationError && error.code === "lifecycle.profile_not_found") {
        fail("lifecycle.dependency_artifact_missing", dependency.name);
      }
      throw error;
    });
    const artifactEntries = artifactFiles.map(({ path: artifactPath, digest, byteLength }) => ({ path: artifactPath, digest, byteLength }));
    const artifactDigest = digestObject(artifactEntries);
    if (artifactDigest !== state.artifactDigest) fail("lifecycle.dependency_artifact_mismatch", dependency.name);
    const artifactByPath = new Map(artifactFiles.map((file) => [file.path, file]));
    const pluginManifest = artifactByPath.get("plugin.json");
    const revisionRecord = artifactByPath.get("revision.json");
    if (!pluginManifest || parseCapturedJson(pluginManifest.bytes, dependency.name + "/plugin.json").name !== dependency.name) {
      fail("lifecycle.dependency_artifact_mismatch", dependency.name);
    }
    if (!revisionRecord) fail("lifecycle.dependency_revision_missing", dependency.name);
    const pinnedArtifact = parseCapturedJson(revisionRecord.bytes, dependency.name + "/revision.json");
    if (pinnedArtifact.revision !== dependency.revision || pinnedArtifact.sourceUrl !== dependency.sourceUrl) {
      fail("lifecycle.dependency_mismatch", dependency.name);
    }
    const discovery = await readDiscovery(profileRoot, dependency.name);
    if (!discovery.imported) fail("lifecycle.dependency_discovery_missing", dependency.name);
    if (discovery.source !== state.ownership) fail("lifecycle.dependency_ownership_mismatch", dependency.name);
    records.push({
      schemaVersion: 1,
      name: dependency.name,
      required: dependency.required,
      expectedRevision: dependency.revision,
      observedRevision: state.revision,
      ownership: state.ownership,
      sourceUrl: state.sourceUrl,
      artifactDigest,
      status: state.ownership === "user" ? "user_owned_verified" : "release_owned_verified",
    });
  }
  return records;
};

const normalizedLifecycleSnapshot = async (profileRoot, volatilityPolicy) => {
  const snapshot = await snapshotProfile(profileRoot, volatilityPolicy);
  const entries = [];
  for (const entry of snapshot.entries) {
    if (entry.path !== ".gemini/config/import_manifest.json") {
      entries.push(entry);
      continue;
    }
    const manifest = await readJsonFile(path.join(profileRoot, ...entry.path.split("/")), { imports: [] });
    const normalized = structuredClone(manifest);
    if (Array.isArray(normalized.imports)) {
      for (const imported of normalized.imports) {
        if (imported && typeof imported === "object" && Object.hasOwn(imported, "importedAt")) imported.importedAt = "<volatile>";
      }
    }
    const bytes = canonicalJsonLine(normalized);
    entries.push({ path: entry.path, digest: digestBytes(bytes), byteLength: bytes.byteLength });
  }
  entries.sort((left, right) => left.path.localeCompare(right.path));
  return { schemaVersion: 1, profileDigest: digestObject(entries), entries };
};

const parseVersion = (value, fieldPath) => {
  const match = /(?:^|\s)([0-9]+)\.([0-9]+)\.([0-9]+)(?:\s|$)/u.exec(value);
  if (!match) fail("lifecycle.invalid_cli_version", fieldPath);
  return match.slice(1).map(Number);
};

const versionAtLeast = (observed, minimum) => {
  for (let index = 0; index < 3; index += 1) {
    if (observed[index] !== minimum[index]) return observed[index] > minimum[index];
  }
  return true;
};

const commandEnvironment = (profileRoot, extra = {}) => ({
  PATH: process.env.PATH || "/usr/bin:/bin:/usr/sbin:/sbin",
  LANG: process.env.LANG || "C.UTF-8",
  HOME: profileRoot,
  ...extra,
});

const createUpgradeVariant = async (pluginRoot) => {
  const temporaryRoot = await fs.mkdtemp(path.join(os.tmpdir(), "abe-lifecycle-upgrade-"));
  const variantRoot = path.join(temporaryRoot, "plugin");
  await fs.cp(pluginRoot, variantRoot, { recursive: true, dereference: false, verbatimSymlinks: true });
  const manifestPath = path.join(variantRoot, "plugin.json");
  const lockPath = path.join(variantRoot, "behavior-lock.json");
  const manifest = await readJsonFile(manifestPath, null);
  const lock = await loadBehaviorLock(lockPath);
  const versionParts = manifest.version.split(".").map(Number);
  manifest.version = [versionParts[0], versionParts[1], versionParts[2] + 1].join(".");
  const manifestBytes = canonicalJsonLine(manifest);
  lock.packageVersion = manifest.version;
  lock.files = { ...lock.files, "plugin.json": digestBytes(manifestBytes) };
  await fs.writeFile(manifestPath, manifestBytes);
  await fs.writeFile(lockPath, canonicalJsonLine(lock));
  return { temporaryRoot, variantRoot, lock };
};

const restoreMetadata = async (profileRoot, baseline) => {
  for (const relativePath of PROFILE_METADATA_PATHS) {
    const target = path.join(profileRoot, ...relativePath.split("/"));
    const bytes = baseline.get(relativePath);
    if (bytes === null) {
      await fs.unlink(target).catch((error) => {
        if (error?.code !== "ENOENT") throw error;
      });
    } else {
      await fs.mkdir(path.dirname(target), { recursive: true });
      await fs.writeFile(target, bytes);
    }
  }
  for (const relativePath of [
    ".gemini/config/plugins",
    ".gemini/config",
    ".gemini",
  ]) {
    await fs.rmdir(path.join(profileRoot, ...relativePath.split("/"))).catch((error) => {
      if (!["ENOENT", "ENOTEMPTY"].includes(error?.code)) throw error;
    });
  }
};

const packageResidue = async (profileRoot, packageName) => {
  const residue = [];
  const installedRoot = installedPluginRoot(profileRoot, packageName);
  if (await fs.lstat(installedRoot).then(() => true, (error) => (error?.code === "ENOENT" ? false : Promise.reject(error)))) residue.push("installed-package-root");
  const discovery = await readDiscovery(profileRoot, packageName);
  if (discovery.imported) residue.push("import-manifest-entry");
  const config = await readJsonFile(path.join(profileRoot, ".gemini", "config", "config.json"), {});
  if (config?.plugins && Object.hasOwn(config.plugins, packageName)) residue.push("plugin-config-entry");
  return residue;
};

const restoreReleaseBaseline = async (profileRoot, packageName, baselineMetadata, before, volatilityPolicy) => {
  await fs.rm(installedPluginRoot(profileRoot, packageName), { recursive: true, force: true });
  await restoreMetadata(profileRoot, baselineMetadata);
  const after = await normalizedLifecycleSnapshot(profileRoot, volatilityPolicy);
  const diff = diffProfileSnapshots(before, after);
  const packageOwnedResiduePaths = await packageResidue(profileRoot, packageName);
  if (packageOwnedResiduePaths.length > 0 || diff.changedPaths.length > 0) {
    fail("lifecycle.cleanup_failed", packageName);
  }
  return { after, diff, packageOwnedResiduePaths };
};

const preflightPackageConflict = async (profileRoot, packageName) => {
  const discovery = await readDiscovery(profileRoot, packageName);
  const installedRoot = installedPluginRoot(profileRoot, packageName);
  const installed = await fs.lstat(installedRoot).then(() => true, (error) => (error?.code === "ENOENT" ? false : Promise.reject(error)));
  if (installed || discovery.imported) fail("lifecycle.name_conflict", packageName);
  const config = await readJsonFile(path.join(profileRoot, ".gemini", "config", "config.json"), {});
  if (config?.plugins && Object.hasOwn(config.plugins, packageName)) fail("lifecycle.precedence_conflict", packageName);
};

export const runReleaseLifecycle = async ({
  cliPath,
  pluginRoot,
  profileRoot,
  profileFixture,
  maximumCountedMs = DEFAULT_MAXIMUM_COUNTED_MS,
  maximumCommandOutputBytes = DEFAULT_MAXIMUM_COMMAND_OUTPUT_BYTES,
}) => {
  if (!Number.isSafeInteger(maximumCountedMs) || maximumCountedMs <= 0 || maximumCountedMs > DEFAULT_MAXIMUM_COUNTED_MS) {
    fail("lifecycle.invalid_field", "$.maximumCountedMs");
  }
  if (
    !Number.isSafeInteger(maximumCommandOutputBytes)
    || maximumCommandOutputBytes <= 0
    || maximumCommandOutputBytes > DEFAULT_MAXIMUM_COMMAND_OUTPUT_BYTES
  ) {
    fail("lifecycle.invalid_field", "$.maximumCommandOutputBytes");
  }
  const totalStarted = process.hrtime.bigint();
  const lock = await loadBehaviorLock(path.join(pluginRoot, "behavior-lock.json"));
  if (!lock.supportedPlatforms.some((platform) => platform.os === process.platform && platform.architecture === process.arch)) {
    fail("lifecycle.unsupported_platform", process.platform + "/" + process.arch);
  }
  const versionResult = await runProcess([cliPath, "--version"], {
    cwd: pluginRoot,
    env: commandEnvironment(profileRoot),
    timeoutMs: maximumCountedMs,
    maximumOutputBytes: maximumCommandOutputBytes,
  });
  if (versionResult.terminationReason === "timeout") fail("lifecycle.command_timeout", "cli_version");
  if (versionResult.terminationReason === "output_limit") fail("lifecycle.command_output_limit", "cli_version");
  if (versionResult.exitCode !== 0) fail("lifecycle.cli_version_failed", "$.cliPath");
  const observedVersion = parseVersion(versionResult.stdout, "$.cliVersion");
  if (!versionAtLeast(observedVersion, parseVersion(lock.minimumCliVersion, "$.minimumCliVersion"))) {
    fail("lifecycle.cli_version_mismatch", "$.cliVersion");
  }

  const rejectedPaths = lock.lifecycle.volatilityPolicy.ignoredPaths.filter((entry) => PROFILE_METADATA_PATHS.includes(entry));
  const acceptedPaths = lock.lifecycle.volatilityPolicy.ignoredPaths.filter((entry) => !PROFILE_METADATA_PATHS.includes(entry));
  const effectivePolicy = { ignoredPaths: acceptedPaths };
  const baselineMetadata = new Map(await Promise.all(PROFILE_METADATA_PATHS.map(async (relativePath) => [
    relativePath,
    await readOptionalBytes(path.join(profileRoot, ...relativePath.split("/"))),
  ])));
  const before = await normalizedLifecycleSnapshot(profileRoot, effectivePolicy);
  const dependenciesBefore = await verifyProfileDependencies(profileRoot, lock);
  await preflightPackageConflict(profileRoot, lock.packageName);
  const dependencyDigests = new Map();
  for (const dependency of dependenciesBefore) {
    dependencyDigests.set(dependency.name, digestObject(dependency));
  }

  const operations = [];
  const countedStarted = process.hrtime.bigint();
  const elapsedCountedMs = () => Number((process.hrtime.bigint() - countedStarted) / 1_000_000n);
  const timedCommand = async (name, args, { counted = false } = {}) => {
    const start = process.hrtime.bigint();
    const remainingMs = counted ? maximumCountedMs - elapsedCountedMs() : maximumCountedMs;
    if (remainingMs <= 0) fail("lifecycle.command_timeout", name);
    const result = await runPluginCommand(cliPath, args, {
      profileRoot,
      cwd: pluginRoot,
      volatilityPolicy: effectivePolicy,
      timeoutMs: remainingMs,
      maximumOutputBytes: maximumCommandOutputBytes,
    });
    const durationMs = Number((process.hrtime.bigint() - start) / 1_000_000n);
    operations.push({ schemaVersion: 1, name, command: String(args[0]), exitCode: result.exitCode, durationMs, touchedPaths: result.touchedPaths });
    if (result.terminationReason === "timeout") fail("lifecycle.command_timeout", name);
    if (result.terminationReason === "output_limit") fail("lifecycle.command_output_limit", name);
    if (result.exitCode !== 0) fail("lifecycle.command_failed", name);
    return { result, durationMs };
  };
  const timedInspection = async (name, expectedLock) => {
    const start = process.hrtime.bigint();
    await inspectInstall(profileRoot, expectedLock);
    const durationMs = Number((process.hrtime.bigint() - start) / 1_000_000n);
    if (elapsedCountedMs() >= maximumCountedMs) fail("lifecycle.command_timeout", name);
    operations.push({ schemaVersion: 1, name, command: "inspect-install", exitCode: 0, durationMs, touchedPaths: [] });
    return durationMs;
  };

  let upgrade;
  try {
    const validation = await timedCommand("validate", ["validate", pluginRoot], { counted: true });
    const installation = await timedCommand("install", ["install", pluginRoot], { counted: true });
    const verificationMs = await timedInspection("verify", lock);
    const installed = await normalizedLifecycleSnapshot(profileRoot, effectivePolicy);
    await timedCommand("repeat_install", ["install", pluginRoot]);
    const repeated = await normalizedLifecycleSnapshot(profileRoot, effectivePolicy);
    if (diffProfileSnapshots(installed, repeated).changedPaths.length > 0) fail("lifecycle.non_idempotent", "repeat_install");
    await timedCommand("disable", ["disable", lock.packageName]);
    if ((await inspectInstall(profileRoot, lock)).enabled !== false) fail("lifecycle.disable_failed", lock.packageName);
    await timedCommand("enable", ["enable", lock.packageName]);
    if ((await inspectInstall(profileRoot, lock)).enabled !== true) fail("lifecycle.enable_failed", lock.packageName);
    upgrade = await createUpgradeVariant(pluginRoot);
    await timedCommand("upgrade", ["install", upgrade.variantRoot]);
    await inspectInstall(profileRoot, upgrade.lock);
    await timedCommand("rollback", ["install", pluginRoot]);
    await inspectInstall(profileRoot, lock);
    await timedCommand("uninstall", ["uninstall", lock.packageName]);
    const cliResidueBeforeCleanup = await packageResidue(profileRoot, lock.packageName);
    const { after, diff, packageOwnedResiduePaths } = await restoreReleaseBaseline(
      profileRoot,
      lock.packageName,
      baselineMetadata,
      before,
      effectivePolicy,
    );
    const dependenciesAfter = await verifyProfileDependencies(profileRoot, lock);
    const dependencies = [];
    for (const dependency of dependenciesAfter) {
      dependencies.push({ ...dependency, preserved: dependencyDigests.get(dependency.name) === digestObject(dependency) });
    }
    const countedInstallVerifyMs = validation.durationMs + installation.durationMs + verificationMs;
    const totalDurationMs = Number((process.hrtime.bigint() - totalStarted) / 1_000_000n);
    return {
      schemaVersion: 1,
      valid: packageOwnedResiduePaths.length === 0 && diff.changedPaths.length === 0 && countedInstallVerifyMs < maximumCountedMs,
      profileFixture,
      packageName: lock.packageName,
      packageVersion: lock.packageVersion,
      cliVersion: observedVersion.join("."),
      platform: { schemaVersion: 1, os: process.platform, architecture: process.arch, nodeVersion: process.version },
      dependencies,
      operations,
      totalDurationMs,
      countedInstallVerifyMs,
      maximumCountedMs,
      excludedIntervals: [
        { schemaVersion: 1, kind: "authentication", counted: false, durationMs: 0, reason: "prequalified local CLI" },
        { schemaVersion: 1, kind: "dependency_download", counted: false, durationMs: 0, reason: "local package; no dependency download" },
      ],
      idempotent: true,
      cliResidueBeforeCleanup,
      cleanupApplied: cliResidueBeforeCleanup.length > 0,
      packageOwnedResiduePaths,
      unintendedUnrelatedChanges: diff.changedPaths,
      beforeProfileDigest: before.profileDigest,
      afterProfileDigest: after.profileDigest,
      volatilityReview: { schemaVersion: 1, acceptedPaths, rejectedPaths },
    };
  } catch (error) {
    await restoreReleaseBaseline(profileRoot, lock.packageName, baselineMetadata, before, effectivePolicy);
    throw error;
  } finally {
    if (upgrade) await fs.rm(upgrade.temporaryRoot, { recursive: true, force: true });
  }
};
