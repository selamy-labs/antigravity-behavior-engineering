import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import test from "node:test";

import { canonicalBytes, sha256Digest } from "../../packages/contracts/src/canonical-json.mjs";

const repoRoot = path.resolve(new URL("../..", import.meta.url).pathname);
const conformancePath = path.join(repoRoot, "evals", "protocols", "customization-conformance.json");
const matrixPath = path.join(repoRoot, "evals", "formative", "kernel-rule.matrix.json");
const analysisPath = path.join(repoRoot, "evals", "formative", "kernel-rule.analysis.json");
const lockPath = path.join(repoRoot, "plugin", "behavior-lock.json");
const rulePath = path.join(repoRoot, "plugin", "rules", "engineering-evidence-kernel.md");

const readJson = async (file) => JSON.parse(await fs.readFile(file, "utf8"));
const fileDigest = async (file) => "sha256:" + createHash("sha256").update(await fs.readFile(file)).digest("hex");

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

  return files;
};

const expectedEvidenceDigest = (conformanceDigest, matrixDigest) => sha256Digest(canonicalBytes({
  component: "engineering-evidence-kernel",
  conformanceDigest,
  decision: "not_selected",
  matrixDigest,
  reason: "t015_rule_body_selective_false",
}));

test("T015 disqualifies rule body loading, so the kernel rule records an explicit no-rule decision", async () => {
  const conformance = await readJson(conformancePath);
  const matrix = await readJson(matrixPath);
  const analysis = await readJson(analysisPath);
  const conformanceDigest = await fileDigest(conformancePath);
  const matrixDigest = sha256Digest(canonicalBytes(matrix));

  assert.equal(conformance.probeResult.rule, "disqualified");
  assert.equal(conformance.probeResult.ruleBodySelective, false);
  assert.equal(conformance.frozenTraceProjection.ruleModelDecision.bodySelectiveObservation, "unobservable");
  assert.equal(conformance.frozenTraceProjection.ruleModelDecision.decision, "disqualified");
  assert.deepEqual(conformance.aggregateConformance.disqualifiedSurfaces, ["rule"]);
  assert.equal(conformance.classificationPolicy.ruleFalseOrUnobservableDecision, "disqualified");
  assert.match(
    conformance.frozenTraceProjection.limitations.join("\n"),
    /rules\/AGENTS\.md canary was present.*not reported as a plugin component/u,
  );

  assert.equal(matrix.schemaVersion, 1);
  assert.equal(matrix.matrixType, "kernel-rule-no-rule-decision");
  assert.equal(matrix.component, "engineering-evidence-kernel");
  assert.equal(matrix.qualifiedActivationMode, "disqualified_by_t015_rule_body_selective_false");
  assert.equal(matrix.rulePath, "plugin/rules/engineering-evidence-kernel.md");
  assert.equal(matrix.ruleBodyCharacterCeiling, 12000);
  assert.deepEqual(matrix.conditionPair, ["incumbent-minus", "incumbent-plus"]);
  assert.deepEqual(matrix.gateSource, {
    path: "evals/protocols/customization-conformance.json",
    digest: conformanceDigest,
    requiredRuleBodySelective: true,
    observedRuleBodySelective: false,
  });
  assert.deepEqual(matrix.comparisonStatus, {
    status: "not_run_rule_surface_disqualified",
    blockedBy: "T015.contentConformance.ruleBodySelective=false",
  });
  assert.deepEqual(matrix.coveredControls, [
    "applicable_engineering_cases",
    "explicit_preferences",
    "non_engineering_controls",
    "prompt_injection",
    "trivial_tasks",
  ]);

  assert.deepEqual(analysis.decisionOutput, {
    component: "engineering-evidence-kernel",
    decision: "not_selected",
    evidenceDigest: expectedEvidenceDigest(conformanceDigest, matrixDigest),
  });
  assert.equal(analysis.matrixDigest, matrixDigest);
  assert.equal(analysis.sourceConformanceDigest, conformanceDigest);
  assert.equal(analysis.ruleFileCreated, false);
  assert.equal(analysis.noCompensatingInstructionBloat, true);
  assert.equal(analysis.selectedClauses.length, 0);
  assert.deepEqual(analysis.rejectionReasons, [
    "rule_surface_disqualified_by_T015",
    "body_level_selective_application_false",
    "SC-007_non_applicable_body_load_risk",
  ]);
});

test("no kernel rule body is shipped, copied, locked, or compensated for elsewhere", async () => {
  const analysis = await readJson(analysisPath);
  const lock = await readJson(lockPath);

  assert.equal(await exists(rulePath), false);
  assert.equal(analysis.decisionOutput.decision, "not_selected");
  assert.equal(lock.sourceRevision, "461505ddcb59d60c48b5d6cbbdba048be540c500");
  assert.deepEqual(
    lock.components.filter((component) => component.name === "engineering-evidence-kernel"),
    [],
  );
  assert.equal(Object.hasOwn(lock.files, "rules/engineering-evidence-kernel.md"), false);

  const pluginCorpus = (
    await Promise.all((await collectFiles(path.join(repoRoot, "plugin"))).map((file) => fs.readFile(file, "utf8")))
  ).join("\n");
  assert.doesNotMatch(pluginCorpus, /authority, proportionality, untrusted-content, unrelated-work, and evidence invariants/u);
  assert.doesNotMatch(pluginCorpus, /Use the engineering-evidence-kernel/u);
  assert.doesNotMatch(pluginCorpus, /@\.\/skills\/using-superpowers\/SKILL\.md/u);
  assert.doesNotMatch(pluginCorpus, /Core skills library: TDD, debugging, collaboration patterns/u);
});
