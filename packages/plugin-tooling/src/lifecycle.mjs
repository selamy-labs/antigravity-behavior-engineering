import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";

import { canonicalBytes, sha256Digest } from "../../contracts/src/canonical-json.mjs";

const DIGEST_PATTERN = /^sha256:[0-9a-f]{64}$/u;
const PINNED_REVISION_PATTERN = /^[0-9a-f]{40}$/u;
const SEMVER_PATTERN = /^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$/u;
const PACKAGE_LOCK_KEYS = new Set([
  "schemaVersion",
  "packageName",
  "packageVersion",
  "sourceRevision",
  "minimumCliVersion",
  "supportedPlatforms",
  "components",
  "dependencies",
  "files",
  "lifecycle",
  "generatedAt",
]);
const PLATFORM_KEYS = new Set(["schemaVersion", "os", "architecture", "nodeRange"]);
const COMPONENT_KEYS = new Set(["schemaVersion", "kind", "name", "path", "claimId", "defaultEnabled", "digest"]);
const COMPONENT_KINDS = new Set(["skill", "rule", "agent", "hook", "script"]);
const DEPENDENCY_KEYS = new Set(["schemaVersion", "name", "sourceUrl", "revision", "license", "consumption", "required", "qualificationEvidence"]);
const DEPENDENCY_CONSUMPTIONS = new Set(["runtime", "development", "research"]);
const LIFECYCLE_KEYS = new Set(["requiredCommands", "volatilityPolicy"]);
const VOLATILITY_KEYS = new Set(["ignoredPaths"]);

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

const toPosixRelative = (root, absolutePath) => {
  const relativePath = path.relative(root, absolutePath).split(path.sep).join("/");
  if (relativePath === "" || relativePath.startsWith("../") || path.isAbsolute(relativePath)) {
    fail("lifecycle.profile_escape", "$.profileRoot");
  }
  return relativePath;
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

const profileFiles = async (profileRoot, volatilityPolicy) => {
  const canonicalRoot = await fs.realpath(profileRoot).catch((error) => {
    if (error?.code === "ENOENT") {
      fail("lifecycle.profile_not_found", "$.profileRoot");
    }
    throw error;
  });
  const pending = [canonicalRoot];
  const entries = [];
  while (pending.length > 0) {
    const directory = pending.pop();
    const children = await fs.readdir(directory, { withFileTypes: true });
    children.sort((left, right) => left.name.localeCompare(right.name));
    for (const child of children) {
      const absolutePath = path.join(directory, child.name);
      const relativePath = toPosixRelative(canonicalRoot, absolutePath);
      if (ignored(relativePath, volatilityPolicy)) {
        continue;
      }
      if (child.isSymbolicLink()) {
        fail("lifecycle.profile_symlink", relativePath);
      }
      if (child.isDirectory()) {
        pending.push(absolutePath);
      } else if (child.isFile()) {
        const bytes = await fs.readFile(absolutePath);
        entries.push({ path: relativePath, digest: digestBytes(bytes), byteLength: bytes.byteLength });
      }
    }
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

export const diffProfileSnapshots = (before, after) => {
  const beforeEntries = new Map((before.entries || []).map((entry) => [entry.path, entry]));
  const afterEntries = new Map((after.entries || []).map((entry) => [entry.path, entry]));
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

const listInstalledPackageFiles = async (root) => {
  const pending = [root];
  const files = [];
  while (pending.length > 0) {
    const directory = pending.pop();
    const children = await fs.readdir(directory, { withFileTypes: true });
    children.sort((left, right) => left.name.localeCompare(right.name));
    for (const child of children) {
      const absolutePath = path.join(directory, child.name);
      const relativePath = path.relative(root, absolutePath).split(path.sep).join("/");
      if (child.isDirectory()) {
        pending.push(absolutePath);
      } else if (child.isFile()) {
        files.push(relativePath);
      } else if (child.isSymbolicLink()) {
        fail("lifecycle.package_symlink", relativePath);
      }
    }
  }
  files.sort();
  return files;
};

const readDiscovery = async (profileRoot, packageName) => {
  const manifest = await readJsonFile(path.join(profileRoot, ".gemini", "config", "import_manifest.json"), { imports: [] });
  const imports = Array.isArray(manifest.imports) ? manifest.imports : [];
  const names = imports.map((item) => String(item.name || "")).filter((name) => name.length > 0).sort();
  return {
    schemaVersion: 1,
    imported: names.includes(packageName),
    names,
    components: imports.find((item) => item.name === packageName)?.components ?? null,
  };
};

export const inspectInstall = async (profileRoot, expectedLock) => {
  const lock = validateLock(expectedLock);
  const root = installedPluginRoot(profileRoot, lock.packageName);
  const manifest = await readJsonFile(path.join(root, "plugin.json"), null);
  if (!manifest) {
    fail("lifecycle.plugin_not_found", root);
  }
  if (manifest.name !== lock.packageName) {
    fail("lifecycle.plugin_name_mismatch", "plugin.json");
  }

  const packageFiles = [];
  for (const [relativePath, expectedDigest] of Object.entries(lock.files).sort(([left], [right]) => left.localeCompare(right))) {
    const bytes = await fs.readFile(path.join(root, relativePath)).catch((error) => {
      if (error?.code === "ENOENT") {
        fail("lifecycle.package_file_missing", relativePath);
      }
      throw error;
    });
    const digest = digestBytes(bytes);
    if (digest !== expectedDigest) {
      fail("lifecycle.package_file_digest_mismatch", relativePath);
    }
    packageFiles.push({ packagePath: relativePath, digest, byteLength: bytes.byteLength });
  }

  const installedFiles = await listInstalledPackageFiles(root);
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
    packageFiles,
    installedFiles,
    manifestDigest: packageFiles.find((file) => file.packagePath === "plugin.json").digest,
  };
};

const runProcess = (argv, options) => new Promise((resolve) => {
  const child = spawn(argv[0], argv.slice(1), {
    cwd: options.cwd,
    env: options.env,
    shell: false,
    stdio: ["ignore", "pipe", "pipe"],
  });
  let stdout = "";
  let stderr = "";
  child.stdout.setEncoding("utf8");
  child.stderr.setEncoding("utf8");
  child.stdout.on("data", (chunk) => {
    stdout += chunk;
  });
  child.stderr.on("data", (chunk) => {
    stderr += chunk;
  });
  child.on("error", (error) => {
    resolve({ exitCode: 127, stdout, stderr: stderr + String(error.message) + "\n" });
  });
  child.on("close", (code) => {
    resolve({ exitCode: Number.isInteger(code) ? code : 127, stdout, stderr });
  });
});

export const runPluginCommand = async (cliPath, args, { profileRoot, cwd, env = {}, volatilityPolicy } = {}) => {
  if (typeof profileRoot !== "string" || profileRoot.length === 0) {
    fail("lifecycle.profile_not_found", "$.profileRoot");
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
    beforeDigest: before.profileDigest,
    afterDigest: after.profileDigest,
    touchedPaths: diff.changedPaths,
    discovery,
  };
};

export const loadBehaviorLock = async (file) => validateLock(JSON.parse(await fs.readFile(file, "utf8")));
