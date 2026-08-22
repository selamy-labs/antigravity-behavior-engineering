import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import test from "node:test";

import { canonicalBytes, sha256Digest } from "../../packages/contracts/src/canonical-json.mjs";

const repoRoot = path.resolve(new URL("../..", import.meta.url).pathname);
const protocolPath = path.join(repoRoot, "evals", "protocols", "customization-conformance.json");

const digestObject = (value) => sha256Digest(canonicalBytes(value));

const readJson = async (file) => JSON.parse(await fs.readFile(file, "utf8"));

const aggregateConformance = (protocol) => {
  const content = protocol.probeResult;
  const execution = protocol.executionConformance.probeResult;
  const aggregate = protocol.aggregateConformance;
  const contradictions = [];
  if (aggregate.contentEvidenceDigest !== content.evidenceDigest) {
    contradictions.push("content_digest_mismatch");
  }
  if (aggregate.executionEvidenceDigest !== execution.evidenceDigest) {
    contradictions.push("execution_digest_mismatch");
  }
  if (content.rule === "disqualified" && aggregate.qualifiedSurfaces.includes("rule")) {
    contradictions.push("disqualified_rule_promoted");
  }
  if (execution.hookResolution !== "plugin-root" && aggregate.qualifiedSurfaces.includes("hook")) {
    contradictions.push("unqualified_hook_promoted");
  }
  if (execution.agentInheritance !== "explicit" && aggregate.qualifiedSurfaces.includes("agent")) {
    contradictions.push("unqualified_agent_promoted");
  }
  return {
    schemaVersion: 1,
    contradictions,
    supportDecision: contradictions.length === 0 ? aggregate.supportDecision : "contradiction",
  };
};

test("aggregate customization protocol binds content and execution checkpoints", async () => {
  const protocol = await readJson(protocolPath);
  const protocolBody = { ...protocol };
  delete protocolBody.protocolDigest;

  assert.equal(protocol.protocolDigest, digestObject(protocolBody));
  assert.equal(protocol.aggregateConformance.contentEvidenceDigest, protocol.probeResult.evidenceDigest);
  assert.equal(protocol.aggregateConformance.executionEvidenceDigest, protocol.executionConformance.probeResult.evidenceDigest);
  assert.deepEqual(aggregateConformance(protocol), {
    schemaVersion: 1,
    contradictions: [],
    supportDecision: "qualified_surfaces_only",
  });
  assert.deepEqual(protocol.aggregateConformance.qualifiedSurfaces, ["skill", "hook", "agent"]);
  assert.deepEqual(protocol.aggregateConformance.disqualifiedSurfaces, ["rule"]);
  assert.equal(protocol.aggregateConformance.unknowns.includes("agent_kill_semantics"), true);
});

test("aggregate customization protocol rejects cross-surface contradictions", async () => {
  const protocol = await readJson(protocolPath);

  assert.deepEqual(aggregateConformance({
    ...protocol,
    aggregateConformance: {
      ...protocol.aggregateConformance,
      qualifiedSurfaces: ["skill", "rule", "hook", "agent"],
    },
  }), {
    schemaVersion: 1,
    contradictions: ["disqualified_rule_promoted"],
    supportDecision: "contradiction",
  });

  assert.deepEqual(aggregateConformance({
    ...protocol,
    executionConformance: {
      ...protocol.executionConformance,
      probeResult: {
        ...protocol.executionConformance.probeResult,
        hookResolution: "unknown",
      },
    },
  }), {
    schemaVersion: 1,
    contradictions: ["unqualified_hook_promoted"],
    supportDecision: "contradiction",
  });
});
