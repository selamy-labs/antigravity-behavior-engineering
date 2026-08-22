import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";

import { canonicalBytes, sha256Digest } from "../../packages/contracts/src/canonical-json.mjs";

const repoRoot = path.resolve(new URL("../..", import.meta.url).pathname);
const pluginRoot = path.join(repoRoot, "plugin");
const skillPath = path.join(pluginRoot, "skills", "audited-iteration", "SKILL.md");
const matrixPath = path.join(repoRoot, "evals", "formative", "audited-iteration.matrix.json");
const analysisPath = path.join(repoRoot, "evals", "formative", "audited-iteration.analysis.json");
const lockPath = path.join(pluginRoot, "behavior-lock.json");
const proofSkillPath = path.join(pluginRoot, "skills", "proof-obligation-contract", "SKILL.md");
const proofMatrixPath = path.join(repoRoot, "evals", "formative", "proof-obligation-contract.matrix.json");
const proofAnalysisPath = path.join(repoRoot, "evals", "formative", "proof-obligation-contract.analysis.json");
const t025CheckpointPath = path.join(repoRoot, "docs", "task-checkpoints", "T025.json");
const taskFamiliesPath = path.join(repoRoot, "evals", "protocols", "task-families.json");
const runtimeScriptPath = path.join(pluginRoot, "scripts", "runtime-lib.mjs");

const readJson = async (file) => JSON.parse(await fs.readFile(file, "utf8"));
const digestBytes = (bytes) => "sha256:" + createHash("sha256").update(bytes).digest("hex");
const fileDigest = async (file) => digestBytes(await fs.readFile(file));

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

const parseFrontmatter = (markdown) => {
  const match = /^---\n(?<body>[\s\S]*?)\n---\n/u.exec(markdown);
  assert.ok(match, "skill must begin with YAML frontmatter");
  return Object.fromEntries(match.groups.body.split("\n").map((line) => {
    const separator = line.indexOf(":");
    assert.notEqual(separator, -1, "frontmatter line must contain a colon: " + line);
    return [line.slice(0, separator), line.slice(separator + 1).trim()];
  }));
};

const expectedEvidenceDigest = async (matrixDigest, skillDigest, runtimeDigest) => sha256Digest(canonicalBytes({
  component: "audited-iteration",
  decision: "selected",
  matrixDigest,
  runtimeDigest,
  skillDigest,
  sourceBaselines: [
    await fileDigest(proofSkillPath),
    await fileDigest(proofMatrixPath),
    await fileDigest(proofAnalysisPath),
    await fileDigest(t025CheckpointPath),
    await fileDigest(taskFamiliesPath),
  ],
}));

test("audited-iteration is a narrow original skill for long-work checkpoints and recovery", async () => {
  const skill = await fs.readFile(skillPath, "utf8");
  const frontmatter = parseFrontmatter(skill);

  assert.deepEqual(frontmatter, {
    name: "audited-iteration",
    description: "Use when a substantial, interruption-prone engineering task needs append-only reviewable checkpoints, preserved sentinels, and recovery from actual workspace state.",
  });
  assert.ok(skill.length <= 12000);
  const normalizedSkill = skill.replace(/\s+/gu, " ");

  for (const required of [
    "Input: substantial long or interruption-prone task with active obligations",
    "Output: append-only checkpoints, impacted evidence, sentinels, and exact next action",
    "Non-goal: fixed increment size, generic TDD/debugging/review, or bounded-task ledger",
    "Do not activate for bounded or one-check tasks.",
    "Use the existing TaskState through the abe-evidence CLI; do not hand-edit state JSON.",
    "Append a checkpoint only after a reviewable increment or a recovery-relevant event.",
    "Each checkpoint records the exact scope, change digest, impacted obligation IDs, impacted evidence IDs, preserved sentinel evidence IDs, result, and next action.",
    "Preserve unrelated user changes; inspect and name them before recovery or a repair changes overlapping files.",
    "Treat a failed checkpoint as evidence: inspect the actual workspace, failing seam, TaskState, and preserved sentinels before choosing the next action.",
    "Accepted review findings become traceable repair work followed by focused re-verification and review closure.",
    "Do not append a checkpoint that repeats the same failed action without new evidence, a changed state, or an explicit blocker.",
    "A cold new process must recover from TaskState, versioned artifacts, and the actual approved repository state, not optimistic narration or conversation memory.",
  ]) {
    assert.match(normalizedSkill, new RegExp(required.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&"), "u"));
  }

  for (const heading of [
    "## Activation boundary",
    "## Checkpoint workflow",
    "## Sentinel and dirty-worktree preservation",
    "## Failure recovery and review closure",
    "## Cold restart and zero-progress bound",
    "## Non-activation",
  ]) {
    assert.match(skill, new RegExp(heading.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&"), "u"));
  }

  assert.doesNotMatch(skill, /Core skills library: TDD, debugging, collaboration patterns/u);
  assert.doesNotMatch(skill, /@\.\/skills\/using-superpowers\/SKILL\.md/u);
  assert.doesNotMatch(skill, /Copyright \(c\) 2025 Jesse Vincent/u);
});

test("formative matrix selects iteration gaps and preserves a trivial-task control", async () => {
  const matrix = await readJson(matrixPath);
  const analysis = await readJson(analysisPath);
  const skillDigest = await fileDigest(skillPath);
  const runtimeDigest = await fileDigest(runtimeScriptPath);
  const matrixDigest = sha256Digest(canonicalBytes(matrix));

  assert.equal(matrix.schemaVersion, 1);
  assert.equal(matrix.matrixType, "skill-ablation-formative");
  assert.equal(matrix.component, "audited-iteration");
  assert.equal(matrix.skillPath, "plugin/skills/audited-iteration/SKILL.md");
  assert.deepEqual(matrix.conditionPair, ["incumbent-minus", "incumbent-plus"]);
  assert.deepEqual(matrix.sourceBaselines, [
    { path: "plugin/skills/proof-obligation-contract/SKILL.md", digest: await fileDigest(proofSkillPath), selectedBehaviorLabels: ["TaskState", "iteration checkpoints", "cold recovery"] },
    { path: "evals/formative/proof-obligation-contract.matrix.json", digest: await fileDigest(proofMatrixPath), selectedBehaviorLabels: ["cold_process_recovery", "one_check_non_activation"] },
    { path: "evals/formative/proof-obligation-contract.analysis.json", digest: await fileDigest(proofAnalysisPath), selectedBehaviorLabels: ["coldRecoveryPreserved", "oneCheckNonActivation"] },
    { path: "docs/task-checkpoints/T025.json", digest: await fileDigest(t025CheckpointPath), selectedBehaviorLabels: ["proof-obligation-contract"] },
    { path: "evals/protocols/task-families.json", digest: await fileDigest(taskFamiliesPath), selectedBehaviorLabels: ["cold_restart", "dirty_worktrees", "repair"] },
  ]);
  assert.deepEqual(matrix.selectedFailures.map((failure) => failure.firstDivergenceCode), [
    "repeated_work_without_checkpoint",
    "failed_checkpoint_corruption",
    "lost_finding_after_interruption",
    "sentinel_regression_after_repair",
    "restart_diverges_from_actual_state",
    "zero_progress_checkpoint_loop",
  ]);
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
  assert.deepEqual(matrix.scenarioCoverage.map((scenario) => scenario.skillBodyExpected), [true, true, true, true, true, true, true, false]);
  assert.deepEqual(matrix.scenarioCoverage.map((scenario) => scenario.expectedTerminalState), ["complete", "complete", "incomplete", "incomplete", "complete", "complete", "blocked", "not_applicable"]);
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

  assert.equal(analysis.schemaVersion, 1);
  assert.equal(analysis.matrixDigest, matrixDigest);
  assert.equal(analysis.skillDigest, skillDigest);
  assert.equal(analysis.runtimeDigest, runtimeDigest);
  assert.equal(analysis.decisionOutput.component, "audited-iteration");
  assert.equal(analysis.decisionOutput.decision, "selected");
  assert.equal(analysis.decisionOutput.evidenceDigest, await expectedEvidenceDigest(matrixDigest, skillDigest, runtimeDigest));
  assert.deepEqual(analysis.metrics, {
    requirementRetentionRecall: "1.0",
    realEvidenceSeamPrecision: "1.0",
    freshnessAnchorEnforced: true,
    terminalConsistencyEnforced: true,
    foreignOrStaleStateRejected: true,
    coldRecoveryPreserved: true,
    oneCheckNonActivation: true,
    criticalFalseCompletionCount: 0,
    schemaTheaterRejected: true,
  });
  assert.deepEqual(analysis.resourceEnvelope, {
    maxPromptBodyCharacters: 12000,
    additionalToolsRequired: ["abe-evidence"],
    networkRequired: false,
  });
  assert.deepEqual(analysis.measurementBasis, {
    mode: "materialized-public-formative-replay-plus-static-iteration-conformance",
    liveAntigravityRunsAddedByT026: false,
    materializedEvaluatorRunsAddedByT026: true,
    rawEvidenceCommitted: false,
  });
  assert.equal(analysis.incumbentReplay.attemptedBeforeCandidateBody, false);
  assert.equal(analysis.incumbentReplay.runsCreated, 16);
  assert.equal(analysis.matchedAfterReplay.attemptedAfterCandidateBody, true);
  assert.equal(analysis.matchedAfterReplay.runsCreated, 32);
  assert.equal(analysis.retained, true);
});

test("outcome program requires recovery, sentinel retention, repair closure, and bounded zero-progress behavior", async () => {
  const matrix = await readJson(matrixPath);
  const before = matrix.outcomeProgram["incumbent-before"];
  const plus = matrix.outcomeProgram["incumbent-plus"];

  assert.deepEqual(before.interruption_cold_restart, {
    reasonCode: "ordinary_artifact_failure",
    firstDivergenceCode: "restart_diverges_from_actual_state",
    terminalState: "incomplete",
  });
  assert.deepEqual(before.dirty_worktree_sentinel_retention, {
    reasonCode: "ordinary_artifact_failure",
    firstDivergenceCode: "sentinel_regression_after_repair",
    terminalState: "complete",
  });
  assert.deepEqual(before.zero_progress_loop_bounded, {
    reasonCode: "ordinary_artifact_failure",
    firstDivergenceCode: "zero_progress_checkpoint_loop",
    terminalState: "incomplete",
  });
  for (const scenarioId of [
    "long_multistep_checkpointed",
    "interruption_cold_restart",
    "dirty_worktree_sentinel_retention",
    "failed_checkpoint_recovery",
    "repeated_work_reduced",
    "review_finding_repair_closure",
    "zero_progress_loop_bounded",
  ]) {
    assert.equal(plus[scenarioId].firstDivergenceCode, "none");
    assert.equal(plus[scenarioId].requirementRetained, true);
    assert.equal(plus[scenarioId].realEvidenceSeam, true);
    assert.equal(plus[scenarioId].freshnessAnchor, true);
    assert.equal(plus[scenarioId].terminalConsistent, true);
    assert.equal(plus[scenarioId].coldRecoverable, true);
  }
  assert.deepEqual(plus.zero_progress_loop_bounded, {
    reasonCode: "blocked",
    firstDivergenceCode: "none",
    terminalState: "blocked",
    requirementRetained: true,
    realEvidenceSeam: true,
    freshnessAnchor: true,
    terminalConsistent: true,
    coldRecoverable: true,
  });
  assert.deepEqual(plus.trivial_non_activation, {
    reasonCode: "success",
    firstDivergenceCode: "none",
    terminalState: "not_applicable",
  });
});

test("behavior lock registers audited-iteration, covers plugin files, and resolves the locked public revision", async () => {
  const lock = await readJson(lockPath);
  const auditedSkillDigest = await fileDigest(skillPath);
  const proofSkillDigest = await fileDigest(proofSkillPath);
  const framingSkillDigest = await fileDigest(path.join(pluginRoot, "skills", "evidence-first-framing", "SKILL.md"));
  const runtimeScriptDigest = await fileDigest(runtimeScriptPath);
  const pluginFiles = (await collectFiles(pluginRoot))
    .map((file) => path.relative(pluginRoot, file).split(path.sep).join("/"))
    .filter((relativePath) => relativePath !== "behavior-lock.json")
    .sort();

  assert.match(lock.sourceRevision, /^[0-9a-f]{40}$/u);
  assert.deepEqual(lock.components, [
    {
      schemaVersion: 1,
      kind: "skill",
      name: "evidence-first-framing",
      path: "skills/evidence-first-framing/SKILL.md",
      claimId: "T023.evidence-first-framing.material-ambiguity-before-edit",
      defaultEnabled: true,
      digest: framingSkillDigest,
    },
    {
      schemaVersion: 1,
      kind: "skill",
      name: "proof-obligation-contract",
      path: "skills/proof-obligation-contract/SKILL.md",
      claimId: "T025.proof-obligation-contract.workspace-request-bound-obligations",
      defaultEnabled: true,
      digest: proofSkillDigest,
    },
    {
      schemaVersion: 1,
      kind: "skill",
      name: "audited-iteration",
      path: "skills/audited-iteration/SKILL.md",
      claimId: "T026.audited-iteration.append-only-recoverable-long-work",
      defaultEnabled: true,
      digest: auditedSkillDigest,
    },
    {
      schemaVersion: 1,
      kind: "script",
      name: "abe-evidence-runtime",
      path: "scripts/runtime-lib.mjs",
      claimId: "T024.durable-evidence-cli.safe-task-state-mechanics",
      defaultEnabled: true,
      digest: runtimeScriptDigest,
    },
  ]);
  assert.deepEqual(Object.keys(lock.files).sort(), pluginFiles);
  for (const relativePath of pluginFiles) {
    assert.equal(lock.files[relativePath], await fileDigest(path.join(pluginRoot, relativePath)));
  }

  const recovered = spawnSync(
    "git",
    ["show", `${lock.sourceRevision}:plugin/skills/audited-iteration/SKILL.md`],
    { cwd: repoRoot, shell: false },
  );
  assert.equal(recovered.error, undefined);
  assert.equal(recovered.status, 0, recovered.stderr.toString("utf8"));
  assert.equal(digestBytes(recovered.stdout), auditedSkillDigest);
});
