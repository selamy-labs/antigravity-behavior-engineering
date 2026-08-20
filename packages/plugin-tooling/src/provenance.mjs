import fs from "node:fs/promises";
import path from "node:path";

import { canonicalBytes, sha256Digest } from "../../contracts/src/canonical-json.mjs";

const encoder = new TextEncoder();
const DIGEST_PATTERN = /^sha256:[0-9a-f]{64}$/u;
const HTTPS_URL_PATTERN = /^https:\/\/[^ ]+$/u;
const PINNED_REVISION_PATTERN = /^[0-9a-f]{40}$/u;
const UNPINNED_REVISIONS = new Set(["HEAD", "latest", "main", "master"]);

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

const sourceRecordFromDependency = (dependency, index) => {
  assertObject(dependency, "$.packageLock.dependencies[" + index + "]");
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
  for (const field of ["license", "consumption"]) {
    if (typeof dependency[field] !== "string" || dependency[field].length === 0) {
      fail("provenance.invalid_field", "$.packageLock.dependencies[" + index + "]." + field);
    }
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
  const actual = new Map(files.map((file) => [file.relativePath, digestBytes(file.bytes)]));
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

const materializeAdaptations = (adaptations) => {
  if (!Array.isArray(adaptations)) {
    fail("provenance.invalid_field", "$.adaptations");
  }
  return adaptations.map((adaptation, index) => {
    assertObject(adaptation, "$.adaptations[" + index + "]");
    validateDigest(adaptation.sourceDigest, "$.adaptations[" + index + "].sourceDigest");
    assertRelativePath(adaptation.localPath, "$.adaptations[" + index + "].localPath");
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
  const files = await listFiles(root);
  validateFileLock(files, packageLock.files);

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
  const adaptations = materializeAdaptations(lockSet.adaptations);
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
