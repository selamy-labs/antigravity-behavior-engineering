import fs from "node:fs/promises";
import path from "node:path";

import { canonicalBytes, sha256Digest } from "../../contracts/src/canonical-json.mjs";

const encoder = new TextEncoder();
const DIGEST_PATTERN = /^sha256:[0-9a-f]{64}$/u;
const HTTPS_URL_PATTERN = /^https:\/\/[^\s\u0000-\u001f\u007f]+$/u;
const PINNED_REVISION_PATTERN = /^[0-9a-f]{40}$/u;
const SEMVER_PATTERN = /^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$/u;
const SPDX_LICENSE_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9.-]*(?:\+)?$/u;
const TIMESTAMP_PATTERN = /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$/u;
const UNPINNED_REVISIONS = new Set(["HEAD", "latest", "main", "master"]);
const PACKAGE_LOCK_KEYS = new Set(["schemaVersion", "packageName", "packageVersion", "sourceRevision", "minimumCliVersion", "supportedPlatforms", "components", "dependencies", "files", "generatedAt"]);
const PLATFORM_KEYS = new Set(["schemaVersion", "os", "architecture"]);
const COMPONENT_KEYS = new Set(["schemaVersion", "kind", "name", "path", "claimId", "defaultEnabled", "digest"]);
const COMPONENT_KINDS = new Set(["skill", "rule", "agent", "hook", "script"]);
const DEPENDENCY_KEYS = new Set(["schemaVersion", "name", "sourceUrl", "revision", "license", "consumption", "required", "qualificationEvidence"]);
const ADAPTATION_KEYS = new Set(["schemaVersion", "sourceDigest", "localPath", "classification"]);

export class ProvenanceValidationError extends TypeError {
  constructor(code, path = "$") {
    super(code + " at " + path);
    this.name = "ProvenanceValidationError";
    this.code = code;
    this.path = path;
  }
}

const fail = (code, path = "$") => {
  throw new ProvenanceValidationError(code, path);
};

const assertObject = (value, path) => {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    fail("provenance.invalid_field", path);
  }
  return value;
};

const assertKnownKeys = (record, allowedKeys, fieldPath, code = "provenance.invalid_field") => {
  for (const key of Object.keys(record)) {
    if (!allowedKeys.has(key)) {
      fail(code, fieldPath + "." + key);
    }
  }
  for (const key of allowedKeys) {
    if (!Object.hasOwn(record, key)) {
      fail(code, fieldPath + "." + key);
    }
  }
};

const assertNonEmptyString = (value, fieldPath, code = "provenance.invalid_field") => {
  if (typeof value !== "string" || value.length === 0) {
    fail(code, fieldPath);
  }
};

const assertRelativePath = (relativePath, fieldPath) => {
  if (typeof relativePath !== "string" || relativePath.length === 0 || path.isAbsolute(relativePath) || relativePath.includes("\\") || relativePath.includes("\u0000")) {
    fail("provenance.invalid_path", fieldPath);
  }
  const segments = relativePath.split("/");
  if (segments.some((segment) => segment === "" || segment === "." || segment === "..")) {
    fail("provenance.invalid_path", fieldPath);
  }
};

const toPosixRelative = (root, absolutePath) => {
  const relativePath = path.relative(root, absolutePath).split(path.sep).join("/");
  assertRelativePath(relativePath, "$.root");
  return relativePath;
};

const listFiles = async (root) => {
  if (typeof root !== "string" || root.length === 0) {
    fail("provenance.invalid_root", "$.root");
  }
  const canonicalRoot = await fs.realpath(root);
  const rootStatus = await fs.stat(canonicalRoot);
  if (!rootStatus.isDirectory()) {
    fail("provenance.invalid_root", "$.root");
  }
  const pending = [canonicalRoot];
  const files = [];
  while (pending.length > 0) {
    const directory = pending.pop();
    const entries = await fs.readdir(directory, { withFileTypes: true });
    entries.sort((left, right) => left.name.localeCompare(right.name));
    for (const entry of entries) {
      const absolutePath = path.join(directory, entry.name);
      if (entry.isSymbolicLink()) {
        fail("provenance.unexpected_file", toPosixRelative(canonicalRoot, absolutePath));
      }
      if (entry.isDirectory()) {
        pending.push(absolutePath);
      } else if (entry.isFile()) {
        files.push({ relativePath: toPosixRelative(canonicalRoot, absolutePath), bytes: await fs.readFile(absolutePath) });
      }
    }
  }
  files.sort((left, right) => left.relativePath.localeCompare(right.relativePath));
  return files;
};

const digestBytes = (bytes) => sha256Digest(bytes instanceof Uint8Array ? bytes : encoder.encode(String(bytes)));

const digestObject = (value) => sha256Digest(canonicalBytes(value));

const rootDigest = (files) => digestObject(Object.fromEntries(files.map((file) => [file.relativePath, digestBytes(file.bytes)])));

const validateDigest = (value, fieldPath) => {
  if (typeof value !== "string" || !DIGEST_PATTERN.test(value)) {
    fail("provenance.invalid_digest", fieldPath);
  }
};

const validatePinnedRevision = (revision, fieldPath) => {
  if (typeof revision !== "string" || UNPINNED_REVISIONS.has(revision) || !PINNED_REVISION_PATTERN.test(revision)) {
    fail("provenance.unpinned_source", fieldPath);
  }
};

const validateSemVer = (value, fieldPath) => {
  if (typeof value !== "string" || !SEMVER_PATTERN.test(value)) {
    fail("provenance.invalid_package_lock", fieldPath);
  }
};

const validateTimestamp = (value, fieldPath) => {
  if (typeof value !== "string" || !TIMESTAMP_PATTERN.test(value)) {
    fail("provenance.invalid_package_lock", fieldPath);
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime()) || parsed.toISOString().replace(".000Z", "Z") !== value) {
    fail("provenance.invalid_package_lock", fieldPath);
  }
};

const validatePlatformRecord = (platform, index) => {
  assertObject(platform, "$.packageLock.supportedPlatforms[" + index + "]");
  assertKnownKeys(platform, PLATFORM_KEYS, "$.packageLock.supportedPlatforms[" + index + "]", "provenance.invalid_package_lock");
  if (platform.schemaVersion !== 1) {
    fail("provenance.invalid_package_lock", "$.packageLock.supportedPlatforms[" + index + "].schemaVersion");
  }
  assertNonEmptyString(platform.os, "$.packageLock.supportedPlatforms[" + index + "].os", "provenance.invalid_package_lock");
  assertNonEmptyString(platform.architecture, "$.packageLock.supportedPlatforms[" + index + "].architecture", "provenance.invalid_package_lock");
};

const validateComponentLock = (component, index) => {
  assertObject(component, "$.packageLock.components[" + index + "]");
  assertKnownKeys(component, COMPONENT_KEYS, "$.packageLock.components[" + index + "]", "provenance.invalid_package_lock");
  if (component.schemaVersion !== 1 || !COMPONENT_KINDS.has(component.kind)) {
    fail("provenance.invalid_package_lock", "$.packageLock.components[" + index + "].kind");
  }
  assertNonEmptyString(component.name, "$.packageLock.components[" + index + "].name", "provenance.invalid_package_lock");
  assertRelativePath(component.path, "$.packageLock.components[" + index + "].path");
  assertNonEmptyString(component.claimId, "$.packageLock.components[" + index + "].claimId", "provenance.invalid_package_lock");
  if (typeof component.defaultEnabled !== "boolean") {
    fail("provenance.invalid_package_lock", "$.packageLock.components[" + index + "].defaultEnabled");
  }
  validateDigest(component.digest, "$.packageLock.components[" + index + "].digest");
};

const validatePackageLock = (packageLock) => {
  assertKnownKeys(packageLock, PACKAGE_LOCK_KEYS, "$.packageLock", "provenance.invalid_package_lock");
  if (packageLock.schemaVersion !== 1) {
    fail("provenance.invalid_package_lock", "$.packageLock.schemaVersion");
  }
  assertNonEmptyString(packageLock.packageName, "$.packageLock.packageName", "provenance.invalid_package_lock");
  validateSemVer(packageLock.packageVersion, "$.packageLock.packageVersion");
  validatePinnedRevision(packageLock.sourceRevision, "$.packageLock.sourceRevision");
  validateSemVer(packageLock.minimumCliVersion, "$.packageLock.minimumCliVersion");
  if (!Array.isArray(packageLock.supportedPlatforms) || packageLock.supportedPlatforms.length === 0) {
    fail("provenance.invalid_package_lock", "$.packageLock.supportedPlatforms");
  }
  packageLock.supportedPlatforms.forEach(validatePlatformRecord);
  if (!Array.isArray(packageLock.components)) {
    fail("provenance.invalid_package_lock", "$.packageLock.components");
  }
  const componentIdentities = new Set();
  packageLock.components.forEach((component, index) => {
    validateComponentLock(component, index);
    const identity = component.kind + "\n" + component.name;
    if (componentIdentities.has(identity)) {
      fail("provenance.invalid_package_lock", "$.packageLock.components");
    }
    componentIdentities.add(identity);
  });
  validateTimestamp(packageLock.generatedAt, "$.packageLock.generatedAt");
};

const validatePackageIdentity = (files, packageLock) => {
  const pluginFile = files.find((file) => file.relativePath === "plugin.json");
  if (!pluginFile) {
    fail("provenance.missing_file", "plugin.json");
  }
  let pluginJson;
  try {
    pluginJson = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(pluginFile.bytes));
  } catch {
    fail("provenance.invalid_package_lock", "$.packageLock.packageName");
  }
  if (pluginJson === null || typeof pluginJson !== "object" || Array.isArray(pluginJson) || typeof pluginJson.name !== "string" || pluginJson.name.length === 0) {
    fail("provenance.invalid_package_lock", "$.packageLock.packageName");
  }
  if (packageLock.packageName !== pluginJson.name) {
    fail("provenance.invalid_package_lock", "$.packageLock.packageName");
  }
};

const sourceRecordFromDependency = (dependency, index) => {
  assertObject(dependency, "$.packageLock.dependencies[" + index + "]");
  assertKnownKeys(dependency, DEPENDENCY_KEYS, "$.packageLock.dependencies[" + index + "]");
  if (dependency.schemaVersion !== 1) {
    fail("provenance.invalid_field", "$.packageLock.dependencies[" + index + "].schemaVersion");
  }
  if (typeof dependency.name !== "string" || dependency.name.length === 0) {
    fail("provenance.invalid_field", "$.packageLock.dependencies[" + index + "].name");
  }
  if (typeof dependency.sourceUrl !== "string" || !HTTPS_URL_PATTERN.test(dependency.sourceUrl)) {
    fail("provenance.invalid_source", "$.packageLock.dependencies[" + index + "].sourceUrl");
  }
  validatePinnedRevision(dependency.revision, "$.packageLock.dependencies[" + index + "].revision");
  if (typeof dependency.license !== "string" || !SPDX_LICENSE_ID_PATTERN.test(dependency.license)) {
    fail("provenance.invalid_field", "$.packageLock.dependencies[" + index + "].license");
  }
  if (typeof dependency.consumption !== "string" || dependency.consumption.length === 0) {
    fail("provenance.invalid_field", "$.packageLock.dependencies[" + index + "].consumption");
  }
  if (!["runtime", "development", "research"].includes(dependency.consumption)) {
    fail("provenance.invalid_field", "$.packageLock.dependencies[" + index + "].consumption");
  }
  if (typeof dependency.required !== "boolean") {
    fail("provenance.invalid_field", "$.packageLock.dependencies[" + index + "].required");
  }
  if (dependency.qualificationEvidence !== "not_qualified") {
    assertRelativePath(dependency.qualificationEvidence, "$.packageLock.dependencies[" + index + "].qualificationEvidence");
  }
  if (dependency.required && dependency.qualificationEvidence === "not_qualified") {
    fail("provenance.unqualified_required_dependency", "$.packageLock.dependencies[" + index + "].qualificationEvidence");
  }
  return {
    schemaVersion: 1,
    sourceUrl: dependency.sourceUrl,
    revision: dependency.revision,
    license: dependency.license,
    consumption: dependency.consumption,
  };
};

const validateFileLock = (files, packageFiles) => {
  assertObject(packageFiles, "$.packageLock.files");
  const actual = new Map(files.filter((file) => file.relativePath !== "behavior-lock.json").map((file) => [file.relativePath, digestBytes(file.bytes)]));
  const lockedPaths = Object.keys(packageFiles).sort();
  for (const lockedPath of lockedPaths) {
    assertRelativePath(lockedPath, "$.packageLock.files." + lockedPath);
    validateDigest(packageFiles[lockedPath], "$.packageLock.files." + lockedPath);
  }
  const actualPaths = [...actual.keys()].sort();
  if (actualPaths.length !== lockedPaths.length) {
    const missing = lockedPaths.find((lockedPath) => !actual.has(lockedPath));
    if (missing) {
      fail("provenance.missing_file", missing);
    }
    const unexpected = actualPaths.find((actualPath) => !Object.hasOwn(packageFiles, actualPath));
    fail("provenance.unexpected_file", unexpected || "$.packageLock.files");
  }
  for (const actualPath of actualPaths) {
    if (!Object.hasOwn(packageFiles, actualPath)) {
      fail("provenance.unexpected_file", actualPath);
    }
    if (packageFiles[actualPath] !== actual.get(actualPath)) {
      fail("provenance.file_digest_mismatch", actualPath);
    }
  }
};

const validateComponentFiles = (files, components) => {
  const actual = new Map(files.map((file) => [file.relativePath, digestBytes(file.bytes)]));
  for (const component of components) {
    if (!actual.has(component.path)) {
      fail("provenance.missing_file", component.path);
    }
    if (actual.get(component.path) !== component.digest) {
      fail("provenance.file_digest_mismatch", component.path);
    }
  }
};

const materializeAdaptations = (adaptations, files) => {
  if (!Array.isArray(adaptations)) {
    fail("provenance.invalid_field", "$.adaptations");
  }
  const actualPaths = new Set(files.map((file) => file.relativePath));
  return adaptations.map((adaptation, index) => {
    assertObject(adaptation, "$.adaptations[" + index + "]");
    assertKnownKeys(adaptation, ADAPTATION_KEYS, "$.adaptations[" + index + "]");
    validateDigest(adaptation.sourceDigest, "$.adaptations[" + index + "].sourceDigest");
    assertRelativePath(adaptation.localPath, "$.adaptations[" + index + "].localPath");
    if (!actualPaths.has(adaptation.localPath)) {
      fail("provenance.missing_file", adaptation.localPath);
    }
    if (typeof adaptation.classification !== "string" || adaptation.classification.length === 0) {
      fail("provenance.invalid_field", "$.adaptations[" + index + "].classification");
    }
    return {
      schemaVersion: 1,
      sourceDigest: adaptation.sourceDigest,
      localPath: adaptation.localPath,
      classification: adaptation.classification,
    };
  }).sort((left, right) => left.localPath.localeCompare(right.localPath) || left.sourceDigest.localeCompare(right.sourceDigest));
};

export const buildProvenanceInventory = async (root, locks) => {
  const lockSet = assertObject(locks, "$locks");
  const packageLock = assertObject(lockSet.packageLock, "$.packageLock");
  validatePackageLock(packageLock);
  const files = await listFiles(root);
  validatePackageIdentity(files, packageLock);
  validateFileLock(files, packageLock.files);
  validateComponentFiles(files, packageLock.components);

  const noticePath = typeof lockSet.noticePath === "string" ? lockSet.noticePath : "NOTICE";
  assertRelativePath(noticePath, "$.noticePath");
  const noticeFile = files.find((file) => file.relativePath === noticePath);
  if (!noticeFile) {
    fail("provenance.missing_notice", noticePath);
  }

  if (!Array.isArray(packageLock.dependencies)) {
    fail("provenance.invalid_field", "$.packageLock.dependencies");
  }
  if (!Array.isArray(lockSet.adaptations)) {
    fail("provenance.invalid_field", "$.adaptations");
  }
  const dependencies = packageLock.dependencies;
  const sources = dependencies.map(sourceRecordFromDependency).sort((left, right) => left.sourceUrl.localeCompare(right.sourceUrl) || left.revision.localeCompare(right.revision));
  const adaptations = materializeAdaptations(lockSet.adaptations, files);
  const digest = rootDigest(files);
  const policyDigest = typeof lockSet.policyDigest === "string" ? lockSet.policyDigest : digestObject({ schemaVersion: 1, policy: "human-provenance-review-required" });
  validateDigest(policyDigest, "$.policyDigest");

  return {
    schemaVersion: 1,
    inventoryId: "provenance-inventory-" + digest.slice("sha256:".length, "sha256:".length + 12),
    rootDigest: digest,
    sources,
    adaptations,
    noticeDigest: digestBytes(noticeFile.bytes),
    policyDigest,
  };
};
