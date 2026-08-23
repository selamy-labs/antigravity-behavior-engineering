import { createHash, randomBytes } from "node:crypto";
import { constants as fsConstants } from "node:fs";
import fs from "node:fs/promises";
import path from "node:path";
import { gzipSync } from "node:zlib";

import { canonicalBytes, sha256Digest } from "../../contracts/src/canonical-json.mjs";

const DIGEST_PATTERN = /^sha256:[0-9a-f]{64}$/u;
const GIT_SHA_PATTERN = /^[0-9a-f]{40}$/u;
const SEMVER_PATTERN = /^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$/u;
const NODE_RANGE_PATTERN = /^(?:(?:>=|>|<=|<|=|\^|~)?[0-9]+(?:\.[0-9]+){0,2})(?:\s+(?:(?:>=|>|<=|<|=|\^|~)?[0-9]+(?:\.[0-9]+){0,2}))*$/u;
const TIMESTAMP_PATTERN = /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$/u;
const COMPONENT_KINDS = new Set(["skill", "rule", "agent", "hook", "script"]);
const DEPENDENCY_CONSUMPTIONS = new Set(["runtime", "development", "research"]);
const LOCK_KEYS = new Set([
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
const COMPONENT_KEYS = new Set(["schemaVersion", "kind", "name", "path", "claimId", "defaultEnabled", "digest"]);
const REJECTED_COMPONENT_KEYS = new Set(["schemaVersion", "taskId", "kind", "name", "decision", "evidencePath", "evidenceDigest"]);
const DEPENDENCY_KEYS = new Set(["schemaVersion", "name", "sourceUrl", "revision", "license", "consumption", "required", "qualificationEvidence"]);
const PLATFORM_KEYS = new Set(["schemaVersion", "os", "architecture", "nodeRange"]);
const LIFECYCLE_KEYS = new Set(["requiredCommands", "volatilityPolicy"]);
const VOLATILITY_KEYS = new Set(["ignoredPaths"]);
const FORBIDDEN_TOP_LEVEL = new Set([".agents", ".git", "evaluator", "evidence"]);
const EXECUTABLE_PACKAGE_PATHS = new Set(["scripts/runtime-lib.mjs"]);
const compareText = (left, right) => (left < right ? -1 : left > right ? 1 : 0);

export class PackageValidationError extends TypeError {
  constructor(code, fieldPath = "$") {
    super(code + " at " + fieldPath);
    this.name = "PackageValidationError";
    this.code = code;
    this.path = fieldPath;
  }
}

const fail = (code, fieldPath = "$") => {
  throw new PackageValidationError(code, fieldPath);
};

const digestBytes = (bytes) => "sha256:" + createHash("sha256").update(bytes).digest("hex");

const assertObject = (value, fieldPath) => {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    fail("package.invalid_lock", fieldPath);
  }
  return value;
};

const assertExactKeys = (value, keys, fieldPath, code = "package.invalid_lock") => {
  assertObject(value, fieldPath);
  const actual = Object.keys(value);
  if (actual.length !== keys.size || actual.some((key) => !keys.has(key))) {
    fail(code, fieldPath);
  }
};

const assertString = (value, fieldPath) => {
  if (typeof value !== "string" || value.length === 0 || value.includes("\u0000")) {
    fail("package.invalid_lock", fieldPath);
  }
};

const assertDigest = (value, fieldPath) => {
  if (typeof value !== "string" || !DIGEST_PATTERN.test(value)) {
    fail("package.invalid_lock", fieldPath);
  }
};

const assertRelativePath = (value, fieldPath) => {
  if (typeof value !== "string" || value.length === 0 || path.isAbsolute(value) || value.includes("\\") || value.includes("\u0000")) {
    fail("package.invalid_lock", fieldPath);
  }
  if (value.split("/").some((segment) => segment === "" || segment === "." || segment === "..")) {
    fail("package.invalid_lock", fieldPath);
  }
};

const parseJson = (bytes, fieldPath, code = "package.invalid_lock") => {
  try {
    return JSON.parse(Buffer.from(bytes).toString("utf8"));
  } catch {
    fail(code, fieldPath);
  }
};

const canonicalRoot = async (root) => {
  if (typeof root !== "string" || root.length === 0) {
    fail("package.invalid_root");
  }
  const resolved = path.resolve(root);
  const status = await fs.lstat(resolved).catch(() => fail("package.invalid_root", resolved));
  if (!status.isDirectory() || status.isSymbolicLink()) {
    fail("package.invalid_root", resolved);
  }
  const real = await fs.realpath(resolved);
  if (real !== resolved) {
    fail("package.invalid_root", resolved);
  }
  return real;
};

const normalizedMode = (status) => ((status.mode & 0o111) === 0 ? "0644" : "0755");

const walkPackage = async (root) => {
  const files = [];
  const scanDirectory = async (directoryHandle, prefix) => {
    const descriptorRoot = `/proc/self/fd/${directoryHandle.fd}`;
    const entries = await fs.readdir(descriptorRoot, { withFileTypes: true });
    entries.sort((left, right) => compareText(left.name, right.name));
    for (const entry of entries) {
      const relativePath = prefix.length === 0 ? entry.name : prefix + "/" + entry.name;
      const descriptorPath = descriptorRoot + "/" + entry.name;
      if (entry.isSymbolicLink()) fail("package.symlink", relativePath);
      if (entry.isDirectory()) {
        const childHandle = await fs.open(
          descriptorPath,
          fsConstants.O_RDONLY | fsConstants.O_DIRECTORY | fsConstants.O_NOFOLLOW,
        ).catch(() => fail("package.symlink", relativePath));
        try {
          await scanDirectory(childHandle, relativePath);
        } finally {
          await childHandle.close();
        }
        continue;
      }
      if (!entry.isFile()) fail("package.invalid_file_type", relativePath);
      const topLevel = relativePath.split("/")[0];
      if (FORBIDDEN_TOP_LEVEL.has(topLevel) || relativePath.split("/").some((segment) => segment.startsWith("."))) {
        fail("package.forbidden_boundary", relativePath);
      }
      const fileHandle = await fs.open(
        descriptorPath,
        fsConstants.O_RDONLY | fsConstants.O_NOFOLLOW,
      ).catch(() => fail("package.symlink", relativePath));
      try {
        const status = await fileHandle.stat();
        if (!status.isFile()) fail("package.invalid_file_type", relativePath);
        const bytes = await fileHandle.readFile();
        const mode = normalizedMode(status);
        const shouldBeExecutable = EXECUTABLE_PACKAGE_PATHS.has(relativePath);
        if ((mode === "0755") !== shouldBeExecutable) fail("package.invalid_mode", relativePath);
        files.push({ path: relativePath, digest: digestBytes(bytes), byteLength: bytes.byteLength, mode, bytes });
      } finally {
        await fileHandle.close();
      }
    }
  };

  const rootHandle = await fs.open(
    root,
    fsConstants.O_RDONLY | fsConstants.O_DIRECTORY | fsConstants.O_NOFOLLOW,
  ).catch(() => fail("package.invalid_root", root));
  try {
    await scanDirectory(rootHandle, "");
  } finally {
    await rootHandle.close();
  }
  files.sort((left, right) => compareText(left.path, right.path));
  return files;
};

const validatePlatform = (platform, index) => {
  const fieldPath = `$.supportedPlatforms[${index}]`;
  assertExactKeys(platform, PLATFORM_KEYS, fieldPath);
  if (platform.schemaVersion !== 1) fail("package.invalid_lock", fieldPath + ".schemaVersion");
  assertString(platform.os, fieldPath + ".os");
  assertString(platform.architecture, fieldPath + ".architecture");
  if (typeof platform.nodeRange !== "string" || !NODE_RANGE_PATTERN.test(platform.nodeRange)) {
    fail("package.invalid_lock", fieldPath + ".nodeRange");
  }
};

const validateComponent = (component, index) => {
  const fieldPath = `$.components[${index}]`;
  assertExactKeys(component, COMPONENT_KEYS, fieldPath);
  if (component.schemaVersion !== 1 || !COMPONENT_KINDS.has(component.kind)) fail("package.invalid_lock", fieldPath);
  assertString(component.name, fieldPath + ".name");
  assertRelativePath(component.path, fieldPath + ".path");
  assertString(component.claimId, fieldPath + ".claimId");
  if (typeof component.defaultEnabled !== "boolean") fail("package.invalid_lock", fieldPath + ".defaultEnabled");
  assertDigest(component.digest, fieldPath + ".digest");
};

const validateRejectedComponent = (component, index) => {
  const fieldPath = `$.rejectedComponents[${index}]`;
  assertExactKeys(component, REJECTED_COMPONENT_KEYS, fieldPath);
  if (component.schemaVersion !== 1 || !/^T[0-9]{3}$/u.test(component.taskId) || !COMPONENT_KINDS.has(component.kind)) {
    fail("package.invalid_lock", fieldPath);
  }
  assertString(component.name, fieldPath + ".name");
  if (component.decision !== "not_selected") fail("package.invalid_lock", fieldPath + ".decision");
  assertRelativePath(component.evidencePath, fieldPath + ".evidencePath");
  assertDigest(component.evidenceDigest, fieldPath + ".evidenceDigest");
};

const validateDependency = (dependency, index) => {
  const fieldPath = `$.dependencies[${index}]`;
  assertExactKeys(dependency, DEPENDENCY_KEYS, fieldPath);
  if (dependency.schemaVersion !== 1) fail("package.invalid_lock", fieldPath + ".schemaVersion");
  assertString(dependency.name, fieldPath + ".name");
  let source;
  try {
    source = new URL(dependency.sourceUrl);
  } catch {
    fail("package.invalid_lock", fieldPath + ".sourceUrl");
  }
  if (source.protocol !== "https:" || source.username || source.password || source.hash) fail("package.invalid_lock", fieldPath + ".sourceUrl");
  if (typeof dependency.revision !== "string" || !GIT_SHA_PATTERN.test(dependency.revision)) fail("package.invalid_lock", fieldPath + ".revision");
  assertString(dependency.license, fieldPath + ".license");
  if (!DEPENDENCY_CONSUMPTIONS.has(dependency.consumption) || typeof dependency.required !== "boolean") fail("package.invalid_lock", fieldPath);
  if (dependency.qualificationEvidence !== "not_qualified") assertRelativePath(dependency.qualificationEvidence, fieldPath + ".qualificationEvidence");
  if (dependency.required && dependency.qualificationEvidence === "not_qualified") fail("package.invalid_lock", fieldPath + ".qualificationEvidence");
};

const validateLifecycle = (lifecycle) => {
  assertExactKeys(lifecycle, LIFECYCLE_KEYS, "$.lifecycle");
  if (!Array.isArray(lifecycle.requiredCommands) || lifecycle.requiredCommands.length === 0) fail("package.invalid_lock", "$.lifecycle.requiredCommands");
  lifecycle.requiredCommands.forEach((command, index) => assertString(command, `$.lifecycle.requiredCommands[${index}]`));
  if (new Set(lifecycle.requiredCommands).size !== lifecycle.requiredCommands.length) fail("package.invalid_lock", "$.lifecycle.requiredCommands");
  assertExactKeys(lifecycle.volatilityPolicy, VOLATILITY_KEYS, "$.lifecycle.volatilityPolicy");
  if (!Array.isArray(lifecycle.volatilityPolicy.ignoredPaths)) fail("package.invalid_lock", "$.lifecycle.volatilityPolicy.ignoredPaths");
  lifecycle.volatilityPolicy.ignoredPaths.forEach((entry, index) => assertRelativePath(entry.replace(/\/\*\*$/u, ""), `$.lifecycle.volatilityPolicy.ignoredPaths[${index}]`));
};

const validateLockShape = (lock) => {
  assertExactKeys(lock, LOCK_KEYS, "$");
  if (lock.schemaVersion !== 1) fail("package.invalid_lock", "$.schemaVersion");
  assertString(lock.packageName, "$.packageName");
  if (typeof lock.packageVersion !== "string" || !SEMVER_PATTERN.test(lock.packageVersion)) fail("package.invalid_lock", "$.packageVersion");
  if (typeof lock.sourceRevision !== "string" || !GIT_SHA_PATTERN.test(lock.sourceRevision)) fail("package.invalid_lock", "$.sourceRevision");
  if (typeof lock.minimumCliVersion !== "string" || !SEMVER_PATTERN.test(lock.minimumCliVersion)) fail("package.invalid_lock", "$.minimumCliVersion");
  if (!Array.isArray(lock.supportedPlatforms) || lock.supportedPlatforms.length === 0) fail("package.invalid_lock", "$.supportedPlatforms");
  lock.supportedPlatforms.forEach(validatePlatform);
  if (!Array.isArray(lock.components) || !Array.isArray(lock.rejectedComponents) || !Array.isArray(lock.dependencies)) fail("package.invalid_lock");
  lock.components.forEach(validateComponent);
  lock.rejectedComponents.forEach(validateRejectedComponent);
  lock.dependencies.forEach(validateDependency);
  validateLifecycle(lock.lifecycle);
  if (!TIMESTAMP_PATTERN.test(lock.generatedAt)) fail("package.invalid_lock", "$.generatedAt");
  assertObject(lock.files, "$.files");
  for (const [relativePath, fileDigest] of Object.entries(lock.files)) {
    assertRelativePath(relativePath, "$.files");
    assertDigest(fileDigest, `$.files.${relativePath}`);
  }
  if (Object.hasOwn(lock.files, "behavior-lock.json")) fail("package.invalid_lock", "$.files.behavior-lock.json");

  const selectedKeys = new Set();
  for (const component of lock.components) {
    const key = component.kind + "\n" + component.name;
    if (selectedKeys.has(key)) fail("package.component_collision", "$.components");
    selectedKeys.add(key);
  }
  const rejectedKeys = new Set();
  for (const component of lock.rejectedComponents) {
    const key = component.kind + "\n" + component.name;
    if (selectedKeys.has(key) || rejectedKeys.has(key)) fail("package.component_collision", "$.rejectedComponents");
    rejectedKeys.add(key);
  }
  const dependencyNames = new Set();
  for (const dependency of lock.dependencies) {
    if (dependencyNames.has(dependency.name)) fail("package.component_collision", "$.dependencies");
    dependencyNames.add(dependency.name);
  }
  return lock;
};

const packageLockDigest = (lock) => {
  const { generatedAt: _generatedAt, ...reproducibleLock } = lock;
  return sha256Digest(canonicalBytes(reproducibleLock));
};

const publicFile = ({ bytes: _bytes, ...entry }) => entry;

export const validatePlugin = async (root, lockInput) => {
  const anchoredRoot = await canonicalRoot(root);
  const lock = validateLockShape(await lockInput);
  const files = await walkPackage(anchoredRoot);
  const byPath = new Map(files.map((entry) => [entry.path, entry]));
  const manifestFile = byPath.get("plugin.json");
  const behaviorLockFile = byPath.get("behavior-lock.json");
  if (!manifestFile || !behaviorLockFile) fail("package.inventory_mismatch", "plugin.json");
  const manifest = parseJson(manifestFile.bytes, "plugin.json", "package.invalid_manifest");
  assertExactKeys(manifest, new Set(["name", "version"]), "plugin.json", "package.invalid_manifest");
  if (manifest.name !== lock.packageName || manifest.version !== lock.packageVersion || !SEMVER_PATTERN.test(manifest.version)) {
    fail("package.invalid_manifest", "plugin.json");
  }
  const onDiskLock = parseJson(behaviorLockFile.bytes, "behavior-lock.json");
  if (!Buffer.from(canonicalBytes(onDiskLock)).equals(Buffer.from(canonicalBytes(lock)))) {
    fail("package.lock_argument_mismatch", "behavior-lock.json");
  }

  const lockedPaths = Object.keys(lock.files);
  if (lockedPaths.some((entry, index) => entry !== [...lockedPaths].sort()[index])) fail("package.invalid_lock", "$.files");
  const actualPaths = files.map(({ path: filePath }) => filePath).filter((filePath) => filePath !== "behavior-lock.json");
  if (actualPaths.length !== lockedPaths.length || actualPaths.some((entry, index) => entry !== lockedPaths[index])) {
    fail("package.inventory_mismatch", "$.files");
  }
  for (const relativePath of lockedPaths) {
    if (byPath.get(relativePath)?.digest !== lock.files[relativePath]) fail("package.digest_mismatch", relativePath);
  }
  for (const component of lock.components) {
    const entry = byPath.get(component.path);
    if (!entry) fail("package.component_missing", component.path);
    if (entry.digest !== component.digest || lock.files[component.path] !== component.digest) fail("package.digest_mismatch", component.path);
  }

  const reportedFiles = actualPaths.map((relativePath) => publicFile(byPath.get(relativePath)));
  return {
    schemaVersion: 1,
    valid: true,
    packageName: lock.packageName,
    packageVersion: lock.packageVersion,
    sourceRevision: lock.sourceRevision,
    minimumCliVersion: lock.minimumCliVersion,
    supportedPlatforms: lock.supportedPlatforms,
    components: lock.components.map((component) => ({
      ...component,
      byteLength: byPath.get(component.path).byteLength,
      mode: byPath.get(component.path).mode,
    })),
    rejectedComponents: lock.rejectedComponents,
    dependencies: lock.dependencies,
    files: reportedFiles,
    forbiddenPackageZonesPresent: [],
    packageLockDigest: packageLockDigest(lock),
    behaviorLockDigest: behaviorLockFile.digest,
    sourceTreeDigest: sha256Digest(canonicalBytes(reportedFiles)),
  };
};

export const inspectComponents = async (root) => {
  const lock = parseJson(await fs.readFile(path.join(root, "behavior-lock.json")), "behavior-lock.json");
  return (await validatePlugin(root, lock)).components;
};

const writeString = (target, offset, length, value) => {
  const bytes = Buffer.from(value, "utf8");
  if (bytes.byteLength > length) fail("package.archive_path_too_long", value);
  bytes.copy(target, offset);
};

const writeOctal = (target, offset, length, value) => {
  const encoded = Math.trunc(value).toString(8).padStart(length - 1, "0") + "\u0000";
  writeString(target, offset, length, encoded);
};

const tarHeader = (entry) => {
  const header = Buffer.alloc(512, 0);
  writeString(header, 0, 100, entry.path);
  writeOctal(header, 100, 8, Number.parseInt(entry.mode, 8));
  writeOctal(header, 108, 8, 0);
  writeOctal(header, 116, 8, 0);
  writeOctal(header, 124, 12, entry.byteLength);
  writeOctal(header, 136, 12, 0);
  header.fill(0x20, 148, 156);
  header[156] = 0x30;
  writeString(header, 257, 6, "ustar\u0000");
  writeString(header, 263, 2, "00");
  const checksum = header.reduce((sum, byte) => sum + byte, 0);
  writeString(header, 148, 8, checksum.toString(8).padStart(6, "0") + "\u0000 ");
  return header;
};

const tarBytes = (entries) => {
  const chunks = [];
  for (const entry of entries) {
    chunks.push(tarHeader(entry), entry.bytes);
    const padding = (512 - (entry.byteLength % 512)) % 512;
    if (padding > 0) chunks.push(Buffer.alloc(padding, 0));
  }
  chunks.push(Buffer.alloc(1024, 0));
  return Buffer.concat(chunks);
};

export const ensureOutputOutsideRoot = async (root, output) => {
  if (typeof output !== "string" || output.length === 0) fail("package.invalid_output", "$.output");
  const absoluteOutput = path.resolve(output);
  const relative = path.relative(root, absoluteOutput);
  if (relative === "" || (!relative.startsWith(".." + path.sep) && relative !== ".." && !path.isAbsolute(relative))) {
    fail("package.output_inside_root", absoluteOutput);
  }
  await fs.mkdir(path.dirname(absoluteOutput), { recursive: true });
  const existing = await fs.lstat(absoluteOutput).catch((error) => (error?.code === "ENOENT" ? null : Promise.reject(error)));
  if (existing?.isSymbolicLink()) fail("package.symlink", absoluteOutput);
  return absoluteOutput;
};

const atomicWrite = async (file, bytes) => {
  const temporary = path.join(path.dirname(file), `.${path.basename(file)}.${process.pid}.${randomBytes(8).toString("hex")}.tmp`);
  let installed = false;
  const handle = await fs.open(temporary, "wx", 0o600);
  try {
    try {
      await handle.writeFile(bytes);
      await handle.sync();
    } finally {
      await handle.close();
    }
    await fs.rename(temporary, file);
    installed = true;
    const directoryHandle = await fs.open(path.dirname(file), fsConstants.O_RDONLY | fsConstants.O_DIRECTORY);
    try {
      await directoryHandle.sync();
    } finally {
      await directoryHandle.close();
    }
  } finally {
    if (!installed) await fs.unlink(temporary).catch(() => {});
  }
};

const createdByDigest = async () => sha256Digest(canonicalBytes({
  schemaVersion: 1,
  algorithm: "abe-plugin-pack-v1",
  nodeVersion: process.version,
  packerDigest: digestBytes(await fs.readFile(new URL(import.meta.url))),
}));

export const packPlugin = async (root, output) => {
  const anchoredRoot = await canonicalRoot(root);
  const lock = parseJson(await fs.readFile(path.join(anchoredRoot, "behavior-lock.json")), "behavior-lock.json");
  const validation = await validatePlugin(anchoredRoot, lock);
  const absoluteOutput = await ensureOutputOutsideRoot(anchoredRoot, output);
  const allFiles = await walkPackage(anchoredRoot);
  const archive = gzipSync(tarBytes(allFiles), { level: 9, mtime: 0 });
  const archiveManifest = allFiles.map(publicFile);
  const record = {
    schemaVersion: 1,
    archiveDigest: digestBytes(archive),
    archiveFormat: { schemaVersion: 1, format: "tgz", version: "1" },
    byteSize: archive.byteLength,
    packageLockDigest: validation.packageLockDigest,
    behaviorLockDigest: validation.behaviorLockDigest,
    sourceTreeDigest: validation.sourceTreeDigest,
    fileManifestDigest: sha256Digest(canonicalBytes(archiveManifest)),
    createdByDigest: await createdByDigest(),
  };
  await atomicWrite(absoluteOutput, archive);
  return record;
};

export const canonicalRecordBytes = (record) => Buffer.from(canonicalBytes(record));

export const writeCanonicalRecord = async (file, record) => {
  const absolute = path.resolve(file);
  await fs.mkdir(path.dirname(absolute), { recursive: true });
  await atomicWrite(absolute, Buffer.concat([canonicalRecordBytes(record), Buffer.from("\n")]));
};
