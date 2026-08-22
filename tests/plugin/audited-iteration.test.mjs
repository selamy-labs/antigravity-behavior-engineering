import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";

import { canonicalBytes, sha256Digest } from "../../packages/contracts/src/canonical-json.mjs";

const repoRoot = path.resolve(new URL("../..", import.meta.url).pathname);
const pluginRoot = path.join(repoRoot, "plugin");
const skillPath = path.join(pluginRoot, "skills", "audited-iteration", "SKILL.md");
const matrixPath = path.join(repoRoot, "evals", "formative", "audited-iteration.matrix.json");
const analysisPath = path.join(repoRoot, "evals", "formative", "audited-iteration.analysis.json");
const evaluatorPath = path.join(repoRoot, "evaluator", "src", "abe_eval", "skill_ablation.py");
const runtimePath = path.join(pluginRoot, "scripts", "runtime-lib.mjs");
const lockPath = path.join(pluginRoot, "behavior-lock.json");
const contractFixturesPath = path.join(repoRoot, "tests", "contract", "fixtures", "evaluation-contracts.json");

const rejectionReasons = [
  "formative_replay_copies_preprogrammed_outcomes",
  "no_observed_long_task_ablation",
  "review_closure_unexecutable_through_t024_cli",
  "resource_envelope_unmeasured",
];

const readJson = async (file) => JSON.parse(await fs.readFile(file, "utf8"));
const digestBytes = (bytes) => "sha256:" + createHash("sha256").update(bytes).digest("hex");
const fileDigest = async (file) => digestBytes(await fs.readFile(file));

const exists = async (file) => {
  try {
    await fs.access(file);
    return true;
  } catch (error) {
    if (error?.code === "ENOENT") {
      return false;
    }
    throw error;
  }
};

const collectFiles = async (directory) => {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const entryPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...await collectFiles(entryPath));
    } else if (entry.isFile()) {
      files.push(entryPath);
    }
  }

  return files.sort();
};

const expectedEvidenceDigest = ({ evaluatorDigest, formativeReplay, liveActivationEvidence, matrixDigest, metricsInterpretation, resourceEnvelope, runtimeDigest, selectionGate }) => sha256Digest(canonicalBytes({
  component: "audited-iteration",
  decision: "not_selected",
  evaluatorDigest,
  formativeReplay,
  liveActivationEvidence,
  matrixDigest,
  metricsInterpretation,
  rejectionReasons,
  resourceEnvelope,
  runtimeDigest,
  selectionGate,
}));

const runEvaluator = (...args) => spawnSync(
  "uv",
  ["run", "--project", "evaluator", "--locked", "--offline", "abe-eval", ...args],
  { cwd: repoRoot, encoding: "utf8", shell: false },
);

const assertEvaluatorSuccess = (result) => {
  assert.equal(result.error, undefined);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  return JSON.parse(result.stdout);
};

test("audited-iteration is rejected when replay is synthetic and repair closure is not executable", async () => {
  const matrix = await readJson(matrixPath);
  const analysis = await readJson(analysisPath);
  const evaluator = await fs.readFile(evaluatorPath, "utf8");
  const runtime = await fs.readFile(runtimePath, "utf8");
  const matrixDigest = sha256Digest(canonicalBytes(matrix));
  const evaluatorDigest = await fileDigest(evaluatorPath);
  const runtimeDigest = await fileDigest(runtimePath);

  assert.equal(await exists(skillPath), false);
  assert.equal(analysis.schemaVersion, 1);
  assert.equal(analysis.analysisType, "skill-ablation-formative-analysis");
  assert.equal(analysis.component, "audited-iteration");
  assert.equal(analysis.matrixPath, "evals/formative/audited-iteration.matrix.json");
  assert.equal(analysis.matrixDigest, matrixDigest);
  assert.equal(analysis.evaluatorPath, "evaluator/src/abe_eval/skill_ablation.py");
  assert.equal(analysis.evaluatorDigest, evaluatorDigest);
  assert.equal(analysis.runtimePath, "plugin/scripts/runtime-lib.mjs");
  assert.equal(analysis.runtimeDigest, runtimeDigest);
  assert.deepEqual(analysis.rejectionReasons, rejectionReasons);
  assert.deepEqual(analysis.selectionGate, {
    behavioralIncumbentReplay: "not_observed",
    matchedLongTaskAblation: "not_observed",
    negativeActivationPrecision: "activation_smoke_only",
    resourceEnvelope: "not_measured",
    materialRegression: "not_measured",
    reviewRepairClosure: "runtime_update_operation_missing",
  });
  assert.deepEqual(analysis.metricsInterpretation, {
    evidenceClass: "deterministic_outcome_program_materialization",
    supportsSelection: false,
  });
  assert.deepEqual(analysis.resourceEnvelope, {
    status: "not_measured",
    supportsSelection: false,
    declaredCandidateLimits: {
      maxPromptBodyCharacters: 12000,
      additionalToolsRequired: ["abe-evidence"],
      networkRequired: false,
    },
  });
  assert.equal(analysis.retained, false);
  assert.deepEqual(analysis.decisionOutput, {
    component: "audited-iteration",
    decision: "not_selected",
    evidenceDigest: expectedEvidenceDigest({
      evaluatorDigest,
      formativeReplay: analysis.formativeReplay,
      liveActivationEvidence: analysis.liveActivationEvidence,
      matrixDigest,
      metricsInterpretation: analysis.metricsInterpretation,
      resourceEnvelope: analysis.resourceEnvelope,
      runtimeDigest,
      selectionGate: analysis.selectionGate,
    }),
    reason: "The candidate is not retained because T026 has no observed incumbent-versus-treatment long-task ablation, its deterministic replay copies authored outcomes, the T024 CLI cannot close accepted findings or pending obligations, and the required resource and regression gates are unmeasured.",
  });

  assert.match(evaluator, /outcome = _outcome_for\(matrix, condition_id, scenario_id\)/u);
  assert.match(evaluator, /outcomes = _assert_mapping\(matrix\["outcomeProgram"\]/u);
  assert.doesNotMatch(evaluator, /\bsubprocess\b|\bagy\b/u);
  assert.match(runtime, /"appendObligation"/u);
  assert.match(runtime, /"appendReviewFinding"/u);
  assert.doesNotMatch(runtime, /"updateObligation"|"updateReviewFinding"/u);
});

test("the frozen intervention card remains expectations rather than observed evidence", async () => {
  const matrix = await readJson(matrixPath);
  const analysis = await readJson(analysisPath);

  assert.equal(matrix.schemaVersion, 1);
  assert.equal(matrix.matrixType, "skill-ablation-formative");
  assert.equal(matrix.partition, "formative");
  assert.equal(matrix.component, "audited-iteration");
  assert.equal(matrix.incumbentCondition, "incumbent-before");
  assert.deepEqual(matrix.conditionPair, ["incumbent-minus", "incumbent-plus"]);
  assert.deepEqual(matrix.modelRequests, ["gemini-3.1-pro-high", "gemini-3.7-flash-high"]);
  assert.deepEqual(matrix.scenarioCoverage.map((scenario) => scenario.scenarioId), [
    "long_multistep_checkpointed",
    "interruption_cold_restart",
    "dirty_worktree_sentinel_retention",
    "failed_checkpoint_recovery",
    "repeated_work_reduced",
    "review_finding_repair_closure",
    "zero_progress_loop_bounded",
    "trivial_non_activation",
  ]);
  assert.deepEqual(matrix.frozenGate, {
    coldRecoveryMinimum: "0.90",
    repeatedWorkReductionRequired: true,
    unrelatedChangesPreserved: true,
    zeroProgressCheckpointBound: 1,
    oneCheckNonActivationMinimum: "0.95",
    maxPromptBodyCharacters: 12000,
    networkRequired: false,
    additionalToolsRequired: ["abe-evidence"],
  });
  assert.deepEqual(analysis.formativeReplay, {
    evidenceClass: "deterministic_outcome_program_materialization",
    supportsSelection: false,
    incumbentBefore: {
      attemptedBeforeCandidateBody: true,
      runsCreated: 16,
    },
    matchedAfter: {
      attemptedAfterCandidateBody: true,
      runsCreated: 32,
    },
  });
  assert.equal(analysis.liveActivationEvidence.status, "collected");
  assert.equal(analysis.liveActivationEvidence.supportsSelection, false);
  assert.deepEqual(analysis.liveActivationEvidence.models, ["gemini-3.1-pro-high", "gemini-3.7-flash-high"]);
  assert.deepEqual(analysis.liveActivationEvidence.runDigests.map((record) => record.outputDigest), [
    "sha256:72f559c5b55c4359d7ecab2c1d2dbb46c6e53645c2421ca8f995dd4ff0571049",
    "sha256:2a8555a06af8f95a25d5c5acb8e162553089b50c988b435b64a00fd15479ff0a",
    "sha256:c70f00ce7d7af547e16e02fe46f916ae19764f0cfa910e4eb38332a833f5698a",
    "sha256:32da87a5bfee4a028a89ab91fe33ea2280b5a0a7634854aff86e38314cd25c45",
  ]);
});

test("the rejection analysis validates and binds both deterministic replay indexes", async (context) => {
  const temporaryRoot = await fs.mkdtemp(path.join(os.tmpdir(), "abe-t026-replay-"));
  context.after(() => fs.rm(temporaryRoot, { recursive: true, force: true }));

  const fixtures = await readJson(contractFixturesPath);
  const qualification = fixtures.validCases.find((item) => item.name === "EnvironmentQualificationRecord")?.value;
  assert.ok(qualification);
  const qualificationPath = path.join(temporaryRoot, "qualification.json");
  await fs.writeFile(
    qualificationPath,
    Buffer.concat([
      canonicalBytes({ schemaVersion: 1, environmentQualification: qualification }),
      Buffer.from("\n"),
    ]),
  );

  const analysis = await readJson(analysisPath);
  const matrix = await readJson(matrixPath);
  const evaluatorDigest = await fileDigest(evaluatorPath);
  const incumbentPackageDigest = await fileDigest(lockPath);
  const phases = [
    {
      key: "incumbentBefore",
      conditions: ["incumbent-before"],
      args: ["--condition", "incumbent-before"],
      runsCreated: 16,
    },
    {
      key: "matchedAfter",
      conditions: ["incumbent-minus", "incumbent-plus"],
      args: ["--condition-pair", "incumbent-minus", "incumbent-plus"],
      runsCreated: 32,
    },
  ];
  const replayIndexes = new Map();

  for (const phase of phases) {
    const rawRoot = path.join(temporaryRoot, phase.key, "raw");
    const outputRoot = path.join(temporaryRoot, phase.key, "publishable");
    const runResult = assertEvaluatorSuccess(runEvaluator(
      "run-matrix",
      "--matrix",
      matrixPath,
      ...phase.args,
      "--qualification",
      qualificationPath,
      "--raw-root",
      rawRoot,
    ));
    assert.equal(runResult.runsCreated, phase.runsCreated);

    const runIndex = await readJson(path.join(rawRoot, "run-index.json"));
    replayIndexes.set(phase.key, runIndex);
    const recorded = analysis.formativeReplay[phase.key];
    assert.deepEqual(recorded.conditions, phase.conditions);
    assert.equal(recorded.conditionDigest, sha256Digest(canonicalBytes(phase.conditions)));
    assert.equal(recorded.qualificationDigest, runIndex.qualificationDigest);
    assert.equal(recorded.runIndexDigest, sha256Digest(canonicalBytes(runIndex)));
    assert.equal(recorded.runSetDigest, sha256Digest(canonicalBytes(runIndex.runDigests)));
    assert.equal(recorded.runsCreated, phase.runsCreated);

    const gradeResult = assertEvaluatorSuccess(runEvaluator(
      "grade",
      "--analysis",
      analysisPath,
      "--raw-root",
      rawRoot,
    ));
    assert.equal(gradeResult.runsGraded, phase.runsCreated);

    const reportResult = assertEvaluatorSuccess(runEvaluator(
      "report",
      "--analysis",
      analysisPath,
      "--raw-root",
      rawRoot,
      "--output",
      outputRoot,
    ));
    const report = await readJson(reportResult.reportPath);
    assert.deepEqual(report.decisionOutput, analysis.decisionOutput);
    assert.deepEqual(report.resourceEnvelope, analysis.resourceEnvelope);
  }

  const protocol = {
    schemaVersion: 1,
    analysisCodeDigest: evaluatorDigest,
    incumbentPackageDigest,
    matrixDigest: sha256Digest(canonicalBytes(matrix)),
    modelRequests: matrix.modelRequests,
    phaseConditions: {
      incumbentBefore: phases[0].conditions,
      matchedAfter: phases[1].conditions,
    },
    qualificationDigest: replayIndexes.get("incumbentBefore").qualificationDigest,
    reasoningRequest: matrix.reasoningRequest,
    repetitionsPerScenario: matrix.repetitionsPerScenario,
  };
  assert.equal(replayIndexes.get("matchedAfter").qualificationDigest, protocol.qualificationDigest);
  assert.deepEqual(analysis.formativeReplay.protocol, protocol);
  assert.equal(analysis.formativeReplay.protocolDigest, sha256Digest(canonicalBytes(protocol)));
});

test("behavior lock omits the rejected skill and resolves every shipped file from its public revision", async () => {
  const lock = await readJson(lockPath);
  const pluginFiles = (await collectFiles(pluginRoot))
    .map((file) => path.relative(pluginRoot, file).split(path.sep).join("/"))
    .filter((relativePath) => relativePath !== "behavior-lock.json")
    .sort();

  assert.equal(await exists(skillPath), false);
  assert.equal(lock.sourceRevision, "72651577666fca7f56849ec952dad641a31a43ea");
  assert.deepEqual(lock.components.filter((component) => component.name === "audited-iteration"), []);
  assert.equal(Object.hasOwn(lock.files, "skills/audited-iteration/SKILL.md"), false);
  assert.deepEqual(Object.keys(lock.files).sort(), pluginFiles);

  for (const relativePath of pluginFiles) {
    assert.equal(lock.files[relativePath], await fileDigest(path.join(pluginRoot, relativePath)));
    const recovered = spawnSync(
      "git",
      ["show", `${lock.sourceRevision}:plugin/${relativePath}`],
      { cwd: repoRoot, shell: false },
    );
    assert.equal(recovered.error, undefined);
    assert.equal(recovered.status, 0, recovered.stderr.toString("utf8"));
    assert.equal(digestBytes(recovered.stdout), lock.files[relativePath]);
  }
});
