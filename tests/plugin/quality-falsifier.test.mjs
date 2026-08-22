import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { canonicalBytes, sha256Digest } from "../../packages/contracts/src/canonical-json.mjs";

const repoRoot = path.resolve(new URL("../..", import.meta.url).pathname);
const agentPath = path.join(repoRoot, "plugin", "agents", "quality-falsifier.md");
const builderPath = path.join(repoRoot, "plugin", "scripts", "reviewer-package.mjs");
const matrixPath = path.join(repoRoot, "evals", "formative", "reviewer-topology.matrix.json");
const analysisPath = path.join(repoRoot, "evals", "formative", "reviewer-topology.analysis.json");

const digest = (character) => `sha256:${character.repeat(64)}`;
const readJson = async (file) => JSON.parse(await fs.readFile(file, "utf8"));
const fileDigest = async (file) => sha256Digest(await fs.readFile(file));
const passingEvidence = {
  schemaVersion: 1,
  kind: "test",
  locator: "evidence/quality-focused.txt",
  digest: digest("a"),
  observedAt: "2026-08-22T00:00:00Z",
  afterChangeDigest: digest("b"),
  result: "pass",
};

const obligation = {
  schemaVersion: 1,
  id: "O-QUALITY",
  requirement: "The implementation must reject symlink traversal before writing.",
  evidenceSeam: "node --test test/safety.test.mjs",
  negativeCases: ["symlink traversal"],
  authority: "read the package and run the focused test",
  required: true,
  status: "passing",
  evidence: [passingEvidence],
  lastRelevantChangeDigest: digest("b"),
};
const verificationInterface = {
  schemaVersion: 1,
  interfaceId: "quality-focused",
  commands: [{
    schemaVersion: 1,
    id: "focused",
    executable: "node",
    arguments: ["--test", "test/safety.test.mjs"],
    workingDirectory: ".",
    timeoutMs: 30_000,
  }],
  artifacts: ["test/safety.test.mjs"],
};
const authorityManifest = {
  schemaVersion: 1,
  manifestId: "quality-read-only",
  allowedActions: ["execute_verification", "read", "write_verdict"],
  allowedResources: ["approved-obligations.json", "artifact-or-diff.patch", "verification-interface.json"],
  networkPolicyDigest: digest("f"),
  credentialGrantDigests: [],
  expiresAt: "not_applicable",
};

test("quality-role package is clean, read-only, and isolated from the requirements verdict", async (context) => {
  const outputRoot = await fs.mkdtemp(path.join(os.tmpdir(), "abe-t028-quality-"));
  context.after(() => fs.rm(outputRoot, { recursive: true, force: true }));
  const artifactRoot = "README.md";
  const input = {
    schemaVersion: 1,
    artifactRoot,
    artifactDigest: await fileDigest(path.join(repoRoot, artifactRoot)),
    obligations: [obligation],
    obligationDigest: sha256Digest(canonicalBytes([obligation])),
    verificationInterface,
    verificationInterfaceDigest: sha256Digest(canonicalBytes(verificationInterface)),
    authorityManifest,
    authorityDigest: sha256Digest(canonicalBytes(authorityManifest)),
  };
  const { buildReviewPairEnvelope, buildReviewPackage } = await import(builderPath);
  const envelope = buildReviewPairEnvelope(input);
  const requirementsRequest = await buildReviewPackage(envelope, "requirements", outputRoot);
  const qualityRequest = await buildReviewPackage(envelope, "quality", outputRoot);
  const packageRoot = path.join(outputRoot, `quality-${qualityRequest.reviewRequestDigest.slice(7)}`);
  const names = (await fs.readdir(packageRoot)).sort();

  assert.deepEqual(authorityManifest.allowedActions, ["execute_verification", "read", "write_verdict"]);
  assert.equal(qualityRequest.reviewerRole, "quality");
  assert.notEqual(qualityRequest.reviewRequestDigest, requirementsRequest.reviewRequestDigest);
  assert.equal(qualityRequest.reviewPairEnvelopeDigest, requirementsRequest.reviewPairEnvelopeDigest);
  assert.equal(names.includes("requirements-review-request.json"), false);
  assert.equal(names.some((name) => /verdict|conclusion|grader/u.test(name)), false);
  assert.equal(names.some((name) => name === "review-request.json"), true);
});

test("incumbent replay decides whether the quality agent body can exist", async () => {
  const matrix = await readJson(matrixPath);
  const analysis = await readJson(analysisPath);

  assert.deepEqual(matrix.modelRequests, ["gemini-3.1-pro-high", "gemini-3.7-flash-high"]);
  assert.deepEqual(matrix.profiles.map(({ profileId }) => profileId), ["matched", "higher-cost-labeled"]);
  assert.deepEqual(matrix.treatments, ["self-review", "requirements-only", "quality-only", "paired-review"]);
  assert.ok(matrix.scenarios.some(({ defectClass }) => defectClass === "implementation"));
  assert.ok(matrix.scenarios.some(({ defectClass }) => defectClass === "safety"));
  assert.ok(matrix.scenarios.some(({ defectClass }) => defectClass === "maintainability"));
  assert.ok(matrix.scenarios.some(({ plantedMaterialDefect }) => plantedMaterialDefect === false));
  assert.ok(matrix.scenarios.some(({ workflowTier }) => workflowTier === "trivial"));
  assert.equal(matrix.reviewBoundary.qualityMayReadRequirementsVerdict, false);
  assert.equal(matrix.reviewBoundary.reviewersMayCommunicate, false);
  assert.equal(analysis.incumbentReplay.attemptedBeforeCandidateBody, true);
  assert.ok(analysis.incumbentReplay.observations.every(
    ({ responseDigest, runRecordDigest }) => /^sha256:[0-9a-f]{64}$/u.test(responseDigest)
      && /^sha256:[0-9a-f]{64}$/u.test(runRecordDigest),
  ));
  assert.equal(analysis.selectionGate.supportsSelection, false);
  assert.equal(analysis.decisionOutput.decision, "not_selected");
  assert.equal(analysis.candidateBodyCreated, false);
  await assert.rejects(() => fs.access(agentPath), /ENOENT/u);
});
