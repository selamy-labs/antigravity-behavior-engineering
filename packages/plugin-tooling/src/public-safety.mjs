import fs from "node:fs/promises";
import path from "node:path";

import { canonicalBytes, sha256Digest } from "../../contracts/src/canonical-json.mjs";

const encoder = new TextEncoder();

const DETECTORS = Object.freeze([
  {
    kind: "credential",
    severity: "critical",
    pattern: /ABE_SYNTHETIC_SECRET_[A-Z0-9]{16}/gu,
  },
  {
    kind: "google_confidential_identifier",
    severity: "critical",
    pattern: /GOOGLE_CONFIDENTIAL_SYNTHETIC_[A-Z0-9_-]+/gu,
  },
  {
    kind: "private_path",
    severity: "critical",
    pattern: /(?:\/Users\/synthetic-private-maintainer|\/home\/synthetic-private-maintainer)\b[^\s]*/gu,
  },
  {
    kind: "unpinned_source",
    severity: "critical",
    pattern: /https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(?:\.git)?#(?:main|master|latest|HEAD)\b/gu,
  },
]);

const SCANNER_DIGESTS = Object.freeze([
  sha256Digest(canonicalBytes({ schemaVersion: 1, scanner: "public-safety", detectorKinds: DETECTORS.map((detector) => detector.kind).sort() })),
]);

const asObject = (value, name) => {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError(name + " must be an object");
  }
  return value;
};

const assertRelativePath = (relativePath) => {
  if (typeof relativePath !== "string" || relativePath.length === 0 || path.isAbsolute(relativePath) || relativePath.includes("\\") || relativePath.includes("\u0000")) {
    throw new TypeError("relative path must be a normalized POSIX path");
  }
  const segments = relativePath.split("/");
  if (segments.some((segment) => segment === "" || segment === "." || segment === "..")) {
    throw new TypeError("relative path must be a normalized POSIX path");
  }
};

const toPosixRelative = (root, absolutePath) => {
  const relativePath = path.relative(root, absolutePath).split(path.sep).join("/");
  assertRelativePath(relativePath);
  return relativePath;
};

const listFiles = async (root) => {
  if (typeof root !== "string" || root.length === 0) {
    throw new TypeError("root must be a non-empty path string");
  }
  const canonicalRoot = await fs.realpath(root);
  const rootStatus = await fs.stat(canonicalRoot);
  if (!rootStatus.isDirectory()) {
    throw new TypeError("root must be a directory");
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
        files.push({ relativePath: toPosixRelative(canonicalRoot, absolutePath), symlink: true, bytes: new Uint8Array() });
      } else if (entry.isDirectory()) {
        pending.push(absolutePath);
      } else if (entry.isFile()) {
        files.push({ relativePath: toPosixRelative(canonicalRoot, absolutePath), bytes: await fs.readFile(absolutePath), symlink: false });
      }
    }
  }
  files.sort((left, right) => left.relativePath.localeCompare(right.relativePath));
  return files;
};

const digestBytes = (bytes) => sha256Digest(bytes instanceof Uint8Array ? bytes : encoder.encode(String(bytes)));

const digestObject = (value) => sha256Digest(canonicalBytes(value));

const rootDigest = (files) => digestObject(Object.fromEntries(files.map((file) => [file.relativePath, digestBytes(file.bytes)])));

const policyDigest = (policy) => {
  if (typeof policy.policyDigest === "string") {
    return policy.policyDigest;
  }
  return digestObject(policy);
};

const lineStarts = (text) => {
  const starts = [0];
  for (let index = 0; index < text.length; index += 1) {
    if (text[index] === "\n") {
      starts.push(index + 1);
    }
  }
  return starts;
};

const lineColumnFor = (starts, index) => {
  let line = 0;
  while (line + 1 < starts.length && starts[line + 1] <= index) {
    line += 1;
  }
  return { line: line + 1, column: index - starts[line] + 1 };
};

const normalizedFingerprint = (text) => sha256Digest(encoder.encode(text.trim().replace(/\s+/gu, " ")));

const addTextDetectorFindings = (candidates, file) => {
  const text = Buffer.from(file.bytes).toString("utf8");
  if (text.includes("\u0000")) {
    return;
  }
  const starts = lineStarts(text);
  for (const detector of DETECTORS) {
    for (const match of text.matchAll(detector.pattern)) {
      const position = lineColumnFor(starts, match.index);
      candidates.push({
        kind: detector.kind,
        severity: detector.severity,
        location: file.relativePath + "#L" + position.line + "C" + position.column,
        evidence: detector.kind + "\n" + match[0],
      });
    }
  }
};

const addCopiedBodyFindings = (candidates, file, policy) => {
  const fingerprints = Array.isArray(policy.copiedBodyFingerprints) ? policy.copiedBodyFingerprints : [];
  if (fingerprints.length === 0) {
    return;
  }
  const byDigest = new Map(fingerprints.map((fingerprint) => [fingerprint.digest, fingerprint]));
  const text = Buffer.from(file.bytes).toString("utf8");
  const lines = text.split(/\r?\n/u);
  for (const [lineIndex, line] of lines.entries()) {
    if (line.trim().length > 0) {
      const digest = normalizedFingerprint(line);
      const fingerprint = byDigest.get(digest);
      if (fingerprint) {
        const column = line.search(/\S/u) + 1;
        candidates.push({
          kind: "copied_body_fingerprint",
          severity: fingerprint.severity || "critical",
          location: file.relativePath + "#L" + (lineIndex + 1) + "C" + column,
          evidence: "copied_body_fingerprint\n" + digest,
        });
      }
    }
  }
};

const findingIdFor = (kind, ordinal) => "public-safety." + kind + "." + String(ordinal).padStart(3, "0");

const materializeFindings = (candidates) => {
  candidates.sort((left, right) => left.kind.localeCompare(right.kind) || left.location.localeCompare(right.location) || left.evidence.localeCompare(right.evidence));
  const ordinals = new Map();
  return candidates.map((candidate) => {
    const next = (ordinals.get(candidate.kind) || 0) + 1;
    ordinals.set(candidate.kind, next);
    return {
      schemaVersion: 1,
      findingId: findingIdFor(candidate.kind, next),
      severity: candidate.severity,
      location: candidate.location,
      evidenceDigest: digestBytes(encoder.encode(candidate.evidence)),
      status: "open",
    };
  });
};

export const scanPublicTree = async (root, policy) => {
  const checkedPolicy = asObject(policy, "policy");
  const files = await listFiles(root);
  const candidates = [];

  const actualPaths = new Set(files.map((file) => file.relativePath));
  const expectedFiles = Array.isArray(checkedPolicy.expectedFiles) ? [...checkedPolicy.expectedFiles].sort() : [];
  for (const expectedFile of expectedFiles) {
    assertRelativePath(expectedFile);
  }
  for (const requiredNotice of Array.isArray(checkedPolicy.requiredNoticeFiles) ? checkedPolicy.requiredNoticeFiles : []) {
    assertRelativePath(requiredNotice);
    if (!actualPaths.has(requiredNotice)) {
      candidates.push({ kind: "missing_notice", severity: "critical", location: requiredNotice, evidence: "missing_notice\n" + requiredNotice });
    }
  }
  if (expectedFiles.length > 0) {
    const expected = new Set(expectedFiles);
    for (const file of files) {
      if (!expected.has(file.relativePath)) {
        candidates.push({ kind: "unexpected_file", severity: "critical", location: file.relativePath, evidence: "unexpected_file\n" + file.relativePath });
      }
    }
  }

  for (const file of files) {
    if (file.symlink) {
      candidates.push({ kind: "unexpected_file", severity: "critical", location: file.relativePath, evidence: "unexpected_symlink\n" + file.relativePath });
      continue;
    }
    addTextDetectorFindings(candidates, file);
    addCopiedBodyFindings(candidates, file, checkedPolicy);
  }

  const findings = materializeFindings(candidates);
  const criticalOpenCount = findings.filter((finding) => finding.severity === "critical" && finding.status === "open").length;
  const digest = rootDigest(files);
  return {
    schemaVersion: 1,
    reportId: "safety-report-" + digest.slice("sha256:".length, "sha256:".length + 12),
    rootDigest: digest,
    policyDigest: policyDigest(checkedPolicy),
    findings,
    criticalOpenCount,
    scannerDigests: [...SCANNER_DIGESTS].sort(),
  };
};
