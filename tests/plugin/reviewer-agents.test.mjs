import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test, { after } from "node:test";

import { canonicalBytes, sha256Digest } from "../../packages/contracts/src/canonical-json.mjs";
import { parseReviewJoinRecord } from "../../packages/contracts/src/runtime-contracts.mjs";
import { joinReviewerVerdicts } from "../../plugin/scripts/reviewer-join.mjs";
import {
  buildReviewPackage,
  buildReviewPairEnvelope,
} from "../../plugin/scripts/reviewer-package.mjs";

const repoRoot = path.resolve(new URL("../..", import.meta.url).pathname);
const joinerPath = path.join(repoRoot, "plugin", "scripts", "reviewer-join.mjs");
const lockPath = path.join(repoRoot, "plugin", "behavior-lock.json");
const analysisPath = path.join(repoRoot, "evals", "formative", "reviewer-topology.analysis.json");
const qualityAgentPath = path.join(repoRoot, "plugin", "agents", "quality-falsifier.md");
const digest = (character) => `sha256:${character.repeat(64)}`;
const identityDigest = (value, field) => sha256Digest(canonicalBytes(
  Object.fromEntries(Object.entries(value).filter(([key]) => key !== field)),
));
const readJson = async (file) => JSON.parse(await fs.readFile(file, "utf8"));
const fileDigest = async (file) => sha256Digest(await fs.readFile(file));

const evidence = {
  schemaVersion: 1,
  kind: "test",
  locator: "evidence/focused.txt",
  digest: digest("3"),
  observedAt: "2026-08-22T00:00:00Z",
  afterChangeDigest: digest("4"),
  result: "fail",
};
const packageObligation = {
  schemaVersion: 1,
  id: "O-1",
  requirement: "The implementation must preserve the approved boundary.",
  evidenceSeam: "node --test test/focused.test.mjs",
  negativeCases: ["reject foreign bindings"],
  authority: "read package and run focused verification",
  required: true,
  status: "failing",
  evidence: [evidence],
  lastRelevantChangeDigest: digest("4"),
};
const verificationInterface = {
  schemaVersion: 1,
  interfaceId: "reviewer-join-focused",
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
  manifestId: "reviewer-join-read-only",
  allowedActions: ["execute_verification", "read", "write_verdict"],
  allowedResources: ["README.md", "test/focused.test.mjs"],
  networkPolicyDigest: digest("5"),
  credentialGrantDigests: [],
  expiresAt: "not_applicable",
};
const buildPublishedPair = async (root) => {
  const input = {
    schemaVersion: 1,
    artifactRoot: "README.md",
    artifactDigest: await fileDigest(path.join(repoRoot, "README.md")),
    obligations: [packageObligation],
    obligationDigest: sha256Digest(canonicalBytes([packageObligation])),
    verificationInterface,
    verificationInterfaceDigest: sha256Digest(canonicalBytes(verificationInterface)),
    authorityManifest,
    authorityDigest: sha256Digest(canonicalBytes(authorityManifest)),
  };
  const envelope = buildReviewPairEnvelope(input);
  const requirementsRequest = await buildReviewPackage(envelope, "requirements", root);
  const qualityRequest = await buildReviewPackage(envelope, "quality", root);
  return {
    envelope,
    requirementsRequest,
    qualityRequest,
    qualityPackageRoot: path.join(root, `quality-${qualityRequest.reviewRequestDigest.slice(7)}`),
  };
};
const packageRoot = await fs.mkdtemp(path.join(os.tmpdir(), "abe-t028-join-"));
after(() => fs.rm(packageRoot, { recursive: true, force: true }));
const {
  envelope,
  requirementsRequest,
  qualityRequest,
  qualityPackageRoot,
} = await buildPublishedPair(packageRoot);
const verdictFor = (role, request, id) => ({
  schemaVersion: 1,
  reviewerRole: role,
  reviewRequestDigest: request.reviewRequestDigest,
  reviewPairEnvelopeDigest: envelope.reviewPairEnvelopeDigest,
  artifactDigest: envelope.artifactDigest,
  obligationDigest: envelope.obligationDigest,
  verificationInterfaceDigest: envelope.verificationInterfaceDigest,
  authorityDigest: envelope.authorityDigest,
  findings: [{
    schemaVersion: 1,
    id,
    severity: "important",
    claim: `${role} defect`,
    evidence: [evidence],
    affectedObligationIds: ["O-1"],
    suggestedFalsification: "Run the focused negative case.",
  }],
  verdict: "fail",
  inspectedEvidence: [evidence],
  limitations: [],
});
const requirementsVerdict = verdictFor("requirements", requirementsRequest, "R-1");
const qualityVerdict = verdictFor("quality", qualityRequest, "Q-1");
qualityVerdict.limitations = ["performance trace unavailable"];

test("joiner emits the exact ordered role-tagged union after both terminal verdicts", () => {
  const joined = joinReviewerVerdicts(
    envelope,
    requirementsRequest,
    requirementsVerdict,
    qualityRequest,
    qualityVerdict,
  );

  assert.equal(joined.joinState, "complete");
  assert.deepEqual(joined.findings, [
    { schemaVersion: 1, reviewerRole: "requirements", findingId: "R-1" },
    { schemaVersion: 1, reviewerRole: "quality", findingId: "Q-1" },
  ]);
  assert.equal(joined.requirementsVerdictDigest, sha256Digest(canonicalBytes(requirementsVerdict)));
  assert.equal(joined.qualityVerdictDigest, sha256Digest(canonicalBytes(qualityVerdict)));
  assert.match(joined.roleSeparationEvidenceDigest, /^sha256:[0-9a-f]{64}$/u);
  assert.deepEqual(joined.limitations, [
    "quality verdict limitation: performance trace unavailable",
  ]);
  assert.deepEqual(parseReviewJoinRecord(joined, {
    reviewPairEnvelope: envelope,
    requirementsRequest,
    qualityRequest,
    requirementsVerdict,
    qualityVerdict,
  }), joined);
});

test("missing, timed-out, permission-blocked, stale, and malformed verdicts stay indeterminate", () => {
  const invalidValues = [
    undefined,
    { status: "timed_out" },
    { status: "permission_blocked" },
    { ...requirementsVerdict, reviewRequestDigest: digest("0") },
    { verdict: "pass" },
  ];
  for (const invalid of invalidValues) {
    const joined = joinReviewerVerdicts(
      envelope,
      requirementsRequest,
      invalid,
      qualityRequest,
      qualityVerdict,
    );
    assert.equal(joined.joinState, "indeterminate");
    assert.equal(joined.requirementsVerdictDigest, "indeterminate");
    assert.equal(joined.qualityVerdictDigest, sha256Digest(canonicalBytes(qualityVerdict)));
    assert.deepEqual(joined.findings, [
      { schemaVersion: 1, reviewerRole: "quality", findingId: "Q-1" },
    ]);
    assert.ok(joined.limitations.some((item) => item.startsWith("requirements verdict indeterminate:")));
  }
});

test("joiner rejects crossed roles, replayed envelopes, and mismatched shared subjects", () => {
  assert.throws(
    () => joinReviewerVerdicts(envelope, qualityRequest, qualityVerdict, requirementsRequest, requirementsVerdict),
    /(?:invalid_role|binding_mismatch)/u,
  );
  const foreignEnvelopeRequest = {
    ...qualityRequest,
    reviewPairEnvelopeDigest: digest("9"),
    reviewRequestDigest: "",
  };
  foreignEnvelopeRequest.reviewRequestDigest = identityDigest(
    foreignEnvelopeRequest,
    "reviewRequestDigest",
  );
  assert.throws(
    () => joinReviewerVerdicts(
      envelope,
      requirementsRequest,
      requirementsVerdict,
      foreignEnvelopeRequest,
      qualityVerdict,
    ),
    /binding_mismatch/u,
  );
  const foreignArtifactRequest = {
    ...qualityRequest,
    artifactDigest: digest("8"),
    reviewRequestDigest: "",
  };
  foreignArtifactRequest.reviewRequestDigest = identityDigest(
    foreignArtifactRequest,
    "reviewRequestDigest",
  );
  assert.throws(
    () => joinReviewerVerdicts(
      envelope,
      requirementsRequest,
      requirementsVerdict,
      foreignArtifactRequest,
      qualityVerdict,
    ),
    /(?:binding_mismatch|invalid_digest)/u,
  );
});

test("joiner rejects forged package bindings and injected competing-review artifacts", async () => {
  const forgedRequest = {
    ...qualityRequest,
    packageManifestDigest: digest("7"),
    reviewRequestDigest: "",
  };
  forgedRequest.reviewRequestDigest = identityDigest(forgedRequest, "reviewRequestDigest");
  assert.throws(
    () => joinReviewerVerdicts(
      envelope,
      requirementsRequest,
      requirementsVerdict,
      forgedRequest,
      qualityVerdict,
    ),
    /binding_mismatch/u,
  );

  await fs.writeFile(
    path.join(qualityPackageRoot, "requirements-verdict.json"),
    `${JSON.stringify(requirementsVerdict)}\n`,
  );
  assert.throws(
    () => joinReviewerVerdicts(
      envelope,
      requirementsRequest,
      requirementsVerdict,
      qualityRequest,
      qualityVerdict,
    ),
    /binding_mismatch/u,
  );
});

test("only earned reviewer topology is locked", async () => {
  const lock = await readJson(lockPath);
  const analysis = await readJson(analysisPath);

  assert.equal(lock.files["scripts/reviewer-join.mjs"], await fileDigest(joinerPath));
  assert.equal(Object.hasOwn(lock.files, "agents/quality-falsifier.md"), false);
  assert.equal(lock.components.some(({ name }) => name === "quality-falsifier"), false);
  assert.equal(analysis.retainedTopology, "self-review");
  assert.equal(analysis.invalidVerdictsBecomePass, false);
  assert.equal(analysis.timedOutVerdictsBecomePass, false);
  assert.equal(analysis.permissionBlockedVerdictsBecomePass, false);
  await assert.rejects(() => fs.access(qualityAgentPath), /ENOENT/u);
});
