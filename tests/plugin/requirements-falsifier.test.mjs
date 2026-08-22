import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { canonicalBytes, sha256Digest } from "../../packages/contracts/src/canonical-json.mjs";

const repoRoot = path.resolve(new URL("../..", import.meta.url).pathname);
const agentPath = path.join(repoRoot, "plugin", "agents", "requirements-falsifier.md");
const builderPath = path.join(repoRoot, "plugin", "scripts", "reviewer-package.mjs");
const matrixPath = path.join(repoRoot, "evals", "formative", "requirements-reviewer.matrix.json");
const analysisPath = path.join(repoRoot, "evals", "formative", "requirements-reviewer.analysis.json");
const lockPath = path.join(repoRoot, "plugin", "behavior-lock.json");

const readJson = async (file) => JSON.parse(await fs.readFile(file, "utf8"));
const digestFile = async (file) => sha256Digest(await fs.readFile(file));
const digest = (character) => `sha256:${character.repeat(64)}`;
const observedAt = "2026-08-20T12:00:00Z";
const evidence = {
  schemaVersion: 1,
  kind: "test",
  locator: "evidence/focused.txt",
  digest: digest("a"),
  observedAt,
  afterChangeDigest: digest("b"),
  result: "pass",
};
const obligation = {
  schemaVersion: 1,
  id: "O-1",
  requirement: "The observable behavior is preserved.",
  evidenceSeam: "node --test focused.test.mjs",
  negativeCases: ["rejects malformed input"],
  authority: "read workspace and run focused tests",
  required: true,
  status: "passing",
  evidence: [evidence],
  lastRelevantChangeDigest: digest("b"),
};
const verificationInterface = {
  schemaVersion: 1,
  interfaceId: "focused-tests",
  commands: [{
    schemaVersion: 1,
    id: "focused",
    executable: "node",
    arguments: ["--test", "test/focused.test.mjs"],
    workingDirectory: ".",
    timeoutMs: 30_000,
  }],
  artifacts: ["test/focused.test.mjs"],
};
const authorityManifest = {
  schemaVersion: 1,
  manifestId: "review-read-only",
  allowedActions: ["execute_verification", "read"],
  allowedResources: ["src", "test"],
  networkPolicyDigest: digest("f"),
  credentialGrantDigests: [],
  expiresAt: "not_applicable",
};
const reviewPackageInput = {
  schemaVersion: 1,
  artifactRoot: "artifact",
  artifactDigest: digest("1"),
  obligations: [obligation],
  obligationDigest: sha256Digest(canonicalBytes([obligation])),
  verificationInterface,
  verificationInterfaceDigest: sha256Digest(canonicalBytes(verificationInterface)),
  authorityManifest,
  authorityDigest: sha256Digest(canonicalBytes(authorityManifest)),
};
const reviewerVerdictFixture = {
  schemaVersion: 1,
  reviewerRole: "requirements",
  reviewRequestDigest: digest("2"),
  reviewPairEnvelopeDigest: digest("3"),
  artifactDigest: digest("1"),
  obligationDigest: reviewPackageInput.obligationDigest,
  verificationInterfaceDigest: reviewPackageInput.verificationInterfaceDigest,
  authorityDigest: reviewPackageInput.authorityDigest,
  findings: [{
    schemaVersion: 1,
    id: "R-1",
    severity: "important",
    claim: "A negative case is not exercised.",
    evidence: [{ ...evidence, result: "fail" }],
    affectedObligationIds: ["O-1"],
    suggestedFalsification: "Run the declared focused command with malformed input.",
  }],
  verdict: "fail",
  inspectedEvidence: [evidence],
  limitations: [],
};

test("requirements-falsifier is not packaged when incumbent replay closes the gap", async () => {
  const analysis = await readJson(analysisPath);

  assert.equal(analysis.incumbentReplay.attemptedBeforeCandidateBody, true);
  assert.equal(analysis.incumbentReplay.materialDefectRecall, "1.00");
  assert.equal(analysis.incumbentReplay.precision, "1.00");
  assert.ok(analysis.incumbentReplay.observations.every(
    (observation) => /^sha256:[0-9a-f]{64}$/u.test(observation.responseDigest)
      && /^sha256:[0-9a-f]{64}$/u.test(observation.runRecordDigest),
  ));
  assert.match(analysis.protectedEvidence.recordDigest, /^sha256:[0-9a-f]{64}$/u);
  assert.equal(analysis.selectionGate.supportsSelection, false);
  assert.equal(analysis.candidateBodyCreated, false);
  assert.equal(analysis.decisionOutput.decision, "not_selected");
  await assert.rejects(() => fs.access(agentPath), /ENOENT/u);
});

test("review packages bind the shared subject without circular or competing-review content", async (context) => {
  const temporaryRoot = await fs.mkdtemp(path.join(os.tmpdir(), "abe-t027-review-"));
  context.after(() => fs.rm(temporaryRoot, { recursive: true, force: true }));
  const artifactRoot = "README.md";
  const input = structuredClone(reviewPackageInput);
  input.artifactRoot = artifactRoot;
  input.artifactDigest = await digestFile(path.join(repoRoot, artifactRoot));
  const {
    buildReviewPairEnvelope,
    buildReviewPackage,
    validateReviewerVerdict,
  } = await import(builderPath);

  const envelope = buildReviewPairEnvelope(input);
  const envelopeBody = Object.fromEntries(
    Object.entries(envelope).filter(([key]) => key !== "reviewPairEnvelopeDigest"),
  );
  assert.equal(envelope.reviewPairEnvelopeDigest, sha256Digest(canonicalBytes(envelopeBody)));
  assert.equal(envelope.artifactDigest, input.artifactDigest);
  assert.equal(envelope.obligationDigest, input.obligationDigest);
  assert.equal(envelope.verificationInterfaceDigest, input.verificationInterfaceDigest);
  assert.equal(envelope.authorityDigest, input.authorityDigest);

  const request = await buildReviewPackage(envelope, "requirements", temporaryRoot);
  const packageRoot = path.join(
    temporaryRoot,
    `requirements-${request.reviewRequestDigest.slice("sha256:".length)}`,
  );
  assert.deepEqual((await fs.readdir(packageRoot)).sort(), [
    "approved-obligations.json",
    "artifact-manifest.json",
    "artifact-or-diff.patch",
    "authority.json",
    "review-pair-envelope.json",
    "review-request.json",
    "verification-interface.json",
  ]);
  const manifest = await readJson(path.join(packageRoot, "artifact-manifest.json"));
  assert.equal(manifest["review-pair-envelope.json"], await digestFile(path.join(packageRoot, "review-pair-envelope.json")));
  assert.equal(Object.hasOwn(manifest, "review-request.json"), false);
  assert.equal(Object.hasOwn(manifest, "reviewer-verdict.json"), false);
  assert.equal(request.packageManifestDigest, sha256Digest(canonicalBytes(manifest)));
  const requestBody = Object.fromEntries(Object.entries(request).filter(([key]) => key !== "reviewRequestDigest"));
  assert.equal(request.reviewRequestDigest, sha256Digest(canonicalBytes(requestBody)));
  assert.equal(request.reviewerRole, "requirements");
  assert.deepEqual(await buildReviewPackage(envelope, "requirements", temporaryRoot), request);

  const verdict = structuredClone(reviewerVerdictFixture);
  Object.assign(verdict, {
    reviewerRole: "requirements",
    reviewRequestDigest: request.reviewRequestDigest,
    reviewPairEnvelopeDigest: request.reviewPairEnvelopeDigest,
    artifactDigest: request.artifactDigest,
    obligationDigest: request.obligationDigest,
    verificationInterfaceDigest: request.verificationInterfaceDigest,
    authorityDigest: request.authorityDigest,
  });
  assert.deepEqual(validateReviewerVerdict(request, verdict), verdict);
  for (const field of [
    "artifactDigest",
    "obligationDigest",
    "verificationInterfaceDigest",
    "authorityDigest",
  ]) {
    assert.throws(
      () => validateReviewerVerdict(request, { ...verdict, [field]: `sha256:${"0".repeat(64)}` }),
      /binding_mismatch/u,
    );
  }
  assert.throws(
    () => validateReviewerVerdict(request, { ...verdict, verdict: "pass", inspectedEvidence: [] }),
    /invalid_verdict/u,
  );
  const qualityRequest = await buildReviewPackage(envelope, "quality", temporaryRoot);
  assert.throws(() => validateReviewerVerdict(qualityRequest, verdict), /(?:invalid_role|binding_mismatch)/u);
  assert.throws(() => validateReviewerVerdict(request, undefined), /invalid_field/u);
  assert.throws(
    () => validateReviewerVerdict(request, { status: "permission_blocked" }),
    /(?:missing_field|unknown_field)/u,
  );
});

test("review package output rejects symlink roots and role replay", async (context) => {
  const temporaryRoot = await fs.mkdtemp(path.join(os.tmpdir(), "abe-t027-path-"));
  context.after(() => fs.rm(temporaryRoot, { recursive: true, force: true }));
  const input = structuredClone(reviewPackageInput);
  input.artifactRoot = "README.md";
  input.artifactDigest = await digestFile(path.join(repoRoot, "README.md"));
  const { buildReviewPairEnvelope, buildReviewPackage } = await import(builderPath);
  const envelope = buildReviewPairEnvelope(input);
  const realRoot = path.join(temporaryRoot, "real");
  const linkedRoot = path.join(temporaryRoot, "linked");
  await fs.mkdir(realRoot);
  await fs.symlink(realRoot, linkedRoot);

  await assert.rejects(() => buildReviewPackage(envelope, "requirements", linkedRoot), /symlink/u);
  await assert.rejects(() => buildReviewPackage(envelope, "unknown", realRoot), /invalid_role/u);
});

test("formative reviewer evidence freezes mixed controls, profiles, and selection gates", async () => {
  const matrix = await readJson(matrixPath);
  const analysis = await readJson(analysisPath);
  const lock = await readJson(lockPath);

  assert.equal(matrix.component, "requirements-falsifier");
  assert.deepEqual(matrix.modelRequests, ["gemini-3.1-pro-high", "gemini-3.7-flash-high"]);
  assert.deepEqual(matrix.profiles.map((profile) => profile.profileId), ["matched", "higher-cost-labeled"]);
  assert.ok(matrix.scenarios.some((scenario) => scenario.plantedMaterialDefect === false));
  assert.ok(matrix.scenarios.some((scenario) => scenario.workflowTier === "trivial"));
  assert.deepEqual(analysis.frozenGate, {
    materialDefectRecallMinimum: "0.85",
    precisionMinimum: "0.80",
    acceptedRepairFreshChecksRequired: true,
    materialRegressionMaximum: 0,
  });
  assert.equal(analysis.invalidVerdictsBecomePass, false);
  assert.equal(analysis.replayedVerdictsBecomePass, false);
  assert.equal(analysis.timedOutVerdictsBecomePass, false);
  assert.equal(analysis.permissionBlockedVerdictsBecomePass, false);
  assert.equal(analysis.retained, false);
  assert.equal(lock.components.some((component) => component.name === "requirements-falsifier"), false);
  assert.equal(Object.hasOwn(lock.files, "agents/requirements-falsifier.md"), false);
  assert.equal(lock.files["scripts/reviewer-package.mjs"], await digestFile(builderPath));
});
