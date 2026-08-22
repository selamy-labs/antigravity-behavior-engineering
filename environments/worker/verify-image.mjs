import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const DIGEST_PATTERN = /^sha256:[0-9a-f]{64}$/;

function fail(message) {
  throw new Error(message);
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function canonical(value) {
  if (value === null) {
    return "null";
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (typeof value === "string") {
    return JSON.stringify(value);
  }
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value)) {
      fail("non-canonical number");
    }
    return String(value);
  }
  if (Array.isArray(value)) {
    return "[" + value.map((item) => canonical(item)).join(",") + "]";
  }
  if (typeof value === "object") {
    const keys = Object.keys(value).sort();
    return "{" + keys.map((key) => JSON.stringify(key) + ":" + canonical(value[key])).join(",") + "}";
  }
  fail("unsupported JSON value");
}

function digestJson(value) {
  return "sha256:" + crypto.createHash("sha256").update(Buffer.from(canonical(value), "utf8")).digest("hex");
}

function digestFile(filePath) {
  return "sha256:" + crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
}

function requireArgs() {
  if (process.argv.length !== 4 || process.argv[2] !== "--expected") {
    fail("usage: node /opt/abe/verify-image.mjs --expected /workspace/input/qualification-lock.json");
  }
  if (process.argv[3] !== "/workspace/input/qualification-lock.json") {
    fail("verification lock must be /workspace/input/qualification-lock.json");
  }
  return process.argv[3];
}

function readProcStatus() {
  const status = fs.readFileSync("/proc/self/status", "utf8");
  return Object.fromEntries(
    status
      .split("\n")
      .filter((line) => line.includes(":"))
      .map((line) => {
        const [key, ...rest] = line.split(":");
        return [key.trim(), rest.join(":").trim()];
      }),
  );
}

function canWrite(targetPath) {
  try {
    fs.accessSync(targetPath, fs.constants.W_OK);
    return true;
  } catch {
    return false;
  }
}

function assertNoForbiddenInputKeys(value, forbidden, found = new Set()) {
  if (!value || typeof value !== "object") {
    return found;
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      assertNoForbiddenInputKeys(item, forbidden, found);
    }
    return found;
  }
  for (const [key, item] of Object.entries(value)) {
    if (forbidden.has(key)) {
      found.add(key);
    }
    assertNoForbiddenInputKeys(item, forbidden, found);
  }
  return found;
}

function assertEnvironmentQualification(qualification) {
  const required = [
    "schemaVersion",
    "qualificationId",
    "scope",
    "cliVersion",
    "cliDigest",
    "imageDigest",
    "platform",
    "modelConfigurationEvidence",
    "unknownModelFallbackEvidence",
    "structuredCaptureEvidence",
    "pluginLifecycleEvidence",
    "customizationConformanceEvidence",
    "authorityToolCapabilityEvidence",
    "supportDecision",
    "limitations",
    "qualifiedAt",
  ];
  for (const field of required) {
    if (!Object.hasOwn(qualification, field)) {
      fail(`missing qualification field ${field}`);
    }
  }
  if (qualification.schemaVersion !== 1) {
    fail("unsupported qualification schemaVersion");
  }
  if (qualification.scope !== "cli_core" && qualification.scope !== "release_candidate") {
    fail("invalid qualification scope");
  }
  for (const field of [
    "cliDigest",
    "imageDigest",
    "unknownModelFallbackEvidence",
    "structuredCaptureEvidence",
    "authorityToolCapabilityEvidence",
  ]) {
    if (!DIGEST_PATTERN.test(qualification[field])) {
      fail(`invalid qualification digest ${field}`);
    }
  }
  if (qualification.platform?.os !== "linux" || qualification.platform?.architecture !== "x64") {
    fail("qualification platform must be linux/x64");
  }
  if (qualification.supportDecision !== "qualified") {
    fail("worker requires a qualified environment");
  }
}

const expectedPath = requireArgs();
const lock = readJson(expectedPath);
const invocation = readJson("/workspace/input/worker-invocation.json");
const qualification = lock.environmentQualification;
assertEnvironmentQualification(qualification);

const actualQualificationDigest = digestJson(qualification);
const expectedQualificationDigest = lock.environmentQualificationDigest;
if (actualQualificationDigest !== expectedQualificationDigest) {
  fail(`qualification digest mismatch: expected ${expectedQualificationDigest}, got ${actualQualificationDigest}`);
}
if (invocation.environmentQualificationDigest !== expectedQualificationDigest) {
  fail("invocation is not bound to the supplied EnvironmentQualificationRecord");
}
if (invocation.cliDigest !== qualification.cliDigest) {
  fail("invocation CLI digest does not match qualification");
}
if (invocation.cliPath !== "/opt/antigravity/bin/agy") {
  fail("worker invocation uses an unexpected CLI path");
}
if (invocation.outputPath !== "/workspace/output") {
  fail("worker invocation uses an unexpected output path");
}
if (invocation.requestPath !== "/workspace/input/request.txt") {
  fail("worker invocation uses an unexpected request path");
}

const expectedRuntime = lock.expectedRuntime;
if (process.getuid?.() !== expectedRuntime.uid || process.getgid?.() !== expectedRuntime.gid) {
  fail("worker is not running as the exact non-root uid/gid");
}
if (process.platform !== "linux" || process.arch !== "x64") {
  fail("worker platform mismatch");
}
if (process.env.HOME !== "/workspace/profile") {
  fail("HOME must be the fresh worker profile");
}

const status = readProcStatus();
if (expectedRuntime.noNewPrivileges && status.NoNewPrivs !== "1") {
  fail("no-new-privileges is not set");
}
if (expectedRuntime.capabilities === "none" && status.CapEff !== "0000000000000000") {
  fail("effective Linux capabilities are not dropped");
}

const cliPath = "/opt/antigravity/bin/agy";
const cliStat = fs.lstatSync(cliPath);
if (!cliStat.isFile()) {
  fail("authorized CLI mount is not a regular file");
}
if (cliStat.isSymbolicLink()) {
  fail("authorized CLI mount must not be a symlink");
}
const cliDigest = digestFile(cliPath);
if (cliDigest !== qualification.cliDigest || cliDigest !== expectedRuntime.cliDigest) {
  fail("authorized CLI digest mismatch");
}
if (process.env.ABE_WORKER_IMAGE_DIGEST !== qualification.imageDigest) {
  fail("runtime image digest does not match qualification");
}

const forbiddenInputKeys = new Set(lock.forbiddenInputKeys);
const forbiddenKeysPresent = [...assertNoForbiddenInputKeys(invocation, forbiddenInputKeys)].sort();
if (forbiddenKeysPresent.length) {
  fail(`worker invocation exposes forbidden keys: ${forbiddenKeysPresent.join(", ")}`);
}

const forbiddenVisible = lock.forbiddenPaths.filter((targetPath) => fs.existsSync(targetPath));
if (forbiddenVisible.length) {
  fail(`worker can see forbidden paths: ${forbiddenVisible.join(", ")}`);
}

const readOnlyFailures = lock.requiredReadOnlyPaths.filter((targetPath) => {
  if (!fs.existsSync(targetPath)) {
    return true;
  }
  return canWrite(targetPath);
});
if (readOnlyFailures.length) {
  fail(`expected read-only paths are writable or absent: ${readOnlyFailures.join(", ")}`);
}

const writableFailures = lock.requiredWritableRoots.filter((targetPath) => {
  if (!fs.existsSync(targetPath)) {
    return true;
  }
  return !canWrite(targetPath);
});
if (writableFailures.length) {
  fail(`expected writable roots are not writable: ${writableFailures.join(", ")}`);
}

const verification = {
  schemaVersion: 1,
  runtime: {
    uid: process.getuid?.(),
    gid: process.getgid?.(),
    home: process.env.HOME,
    platform: `${process.platform}/${process.arch}`,
    noNewPrivileges: status.NoNewPrivs === "1",
    capEff: status.CapEff,
    pid1Comm: fs.readFileSync("/proc/1/comm", "utf8").trim(),
  },
  invocation: {
    keys: Object.keys(invocation).sort(),
    forbiddenKeysPresent,
  },
  qualification: {
    digest: expectedQualificationDigest,
    digestMatchesInvocation: invocation.environmentQualificationDigest === expectedQualificationDigest,
  },
  cli: {
    path: cliPath,
    digest: cliDigest,
    regularFile: cliStat.isFile(),
    symlink: cliStat.isSymbolicLink(),
    writableByWorker: canWrite(cliPath),
  },
  paths: {
    forbiddenVisible,
    readOnlyFailures,
    writableFailures,
  },
  network: {
    hostname: os.hostname(),
  },
};

fs.mkdirSync("/workspace/output", { recursive: true });
fs.writeFileSync(path.join("/workspace/output", "image-verification.json"), JSON.stringify(verification, null, 2) + "\n");
console.log(JSON.stringify({ ok: true, qualificationDigest: expectedQualificationDigest }) + "\n");
