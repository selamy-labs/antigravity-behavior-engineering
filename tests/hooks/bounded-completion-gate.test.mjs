import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import test from "node:test";

import { sha256Digest } from "../../plugin/scripts/runtime-lib.mjs";

const repoRoot = path.resolve(new URL("../..", import.meta.url).pathname);
const pluginRoot = path.join(repoRoot, "plugin");
const hooksPath = path.join(pluginRoot, "hooks.json");
const gatePath = path.join(pluginRoot, "scripts", "bounded-completion-gate.mjs");
const matrixPath = path.join(repoRoot, "evals", "formative", "completion-gate.matrix.json");
const repairMatrixPath = path.join(repoRoot, "evals", "formative", "completion-gate.repair-matrix.json");
const analysisPath = path.join(repoRoot, "evals", "formative", "completion-gate.analysis.json");
const lockPath = path.join(pluginRoot, "behavior-lock.json");

const readJson = async (file) => JSON.parse(await fs.readFile(file, "utf8"));

test("the failed bounded completion treatment is absent from the shipped plugin", async () => {
  const hooks = await readJson(hooksPath);
  const lock = await readJson(lockPath);

  assert.equal(Object.hasOwn(hooks, "bounded-completion-gate"), false);
  await assert.rejects(fs.stat(gatePath), { code: "ENOENT" });
  assert.equal(lock.components.some(({ name }) => name === "bounded-completion-gate"), false);
  assert.equal(Object.hasOwn(lock.files, "scripts/bounded-completion-gate.mjs"), false);
  assert.equal(lock.files["hooks.json"], sha256Digest(await fs.readFile(hooksPath)));
});

test("the frozen incumbent and repair protocols remain attributable", async () => {
  const matrix = await readJson(matrixPath);
  const repairMatrix = await readJson(repairMatrixPath);
  const analysis = await readJson(analysisPath);

  assert.equal(matrix.frozenBeforeTreatment, true);
  assert.equal(matrix.candidateBodyPresentAtFreeze, false);
  assert.equal(matrix.resourceEnvelope.initialCandidateBound, 1);
  assert.equal(repairMatrix.frozenBeforeRepairTreatment, true);
  assert.equal(repairMatrix.repairAppliedAtFreeze, false);
  assert.equal(
    repairMatrix.rejectedCandidateScriptDigest,
    "sha256:7d0e7f7a7f61d4d22d07c7379f5acddb52ae1db83ee9749b4bc036b24f074c58",
  );
  assert.equal(analysis.matrixDigest, sha256Digest(await fs.readFile(matrixPath)));
  assert.equal(analysis.repairMatrixDigest, sha256Digest(await fs.readFile(repairMatrixPath)));
  assert.equal(analysis.incumbentReplay.negativeCriticalFalseCompletions, 4);
  assert.equal(analysis.rejectedTreatment.decision, "rejected");
});

test("intent-to-treat analysis records the no-tools violation and rejects the repair", async () => {
  const analysis = await readJson(analysisPath);
  const violatingRun = analysis.rejectedRepairTreatment.runs.find(
    ({ model, scenarioId }) => model === "gemini-3.7-flash-high"
      && scenarioId === "negative-unresolved-obligation",
  );

  assert.equal(analysis.rejectedRepairTreatment.productFailureRuns, 1);
  assert.equal(violatingRun.toolCalls, 17);
  assert.deepEqual(violatingRun.productFailures, ["instruction_violation_tool_use"]);
  assert.deepEqual(analysis.selectionDecision, {
    decision: "not_selected",
    retained: false,
    bound: null,
    smallestPassingBound: null,
    claimId: null,
    reason: "The repaired bound-one treatment preserved completion honesty and recall, but one scheduled no-tools run made 17 unnecessary tool calls. The frozen zero-product-failure selection rule therefore rejects the treatment; the idempotence defect found in review remains unshipped because the component was removed.",
  });
});

test("SC-012 resources report median and p90 for every required dimension", async () => {
  const { resourceReport } = await readJson(analysisPath);

  assert.equal(resourceReport.quantileMethod, "nearest-rank");
  assert.deepEqual(resourceReport.incumbent, {
    durationSeconds: { median: "5.429249200", p90: "9.708998264" },
    totalTokens: { median: "14527.5", p90: 15246 },
    toolCalls: { median: 0, p90: 0 },
    retries: { median: 0, p90: 0 },
    subagentFanOut: { median: 0, p90: 0 },
  });
  assert.deepEqual(resourceReport.repairedTreatment, {
    durationSeconds: { median: "7.979367106", p90: "31.625229915" },
    totalTokens: { median: "12183.5", p90: 129250 },
    toolCalls: { median: 0, p90: 17 },
    retries: { median: 0, p90: 0 },
    subagentFanOut: { median: 0, p90: 0 },
  });
  assert.equal(resourceReport.envelopeResult, "pass");
  assert.equal(resourceReport.selectionRuleResult, "fail");
});

test("the public analysis identifies evaluated bytes without leaking private evidence", async () => {
  const analysis = await readJson(analysisPath);
  const publicAnalysis = await fs.readFile(analysisPath, "utf8");

  assert.equal(analysis.evaluatedCandidate.frozenBound, 1);
  assert.match(analysis.evaluatedCandidate.gateScriptDigest, /^sha256:[0-9a-f]{64}$/u);
  assert.equal(analysis.retainedImplementation.gateScriptPresent, false);
  assert.equal(
    analysis.retainedImplementation.hooksDigest,
    sha256Digest(await fs.readFile(hooksPath)),
  );
  assert.doesNotMatch(publicAnalysis, /\/home\/|\/private\/|\.gemini\/antigravity-cli\/brain/u);
});
