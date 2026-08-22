import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { canonicalBytes, sha256Digest } from "../../packages/contracts/src/canonical-json.mjs";

const repoRoot = path.resolve(new URL("../..", import.meta.url).pathname);
const fixtureRoot = path.join(repoRoot, "tests", "lifecycle", "fixtures", "probe-plugin");
const manifestPath = path.join(fixtureRoot, "plugin.json");
const componentsPath = path.join(fixtureRoot, "probe-components.json");
const hooksPath = path.join(fixtureRoot, "hooks.json");
const protocolPath = path.join(repoRoot, "evals", "protocols", "customization-conformance.json");

const digestObject = (value) => sha256Digest(canonicalBytes(value));

const readJson = async (file) => JSON.parse(await fs.readFile(file, "utf8"));

const withTemporaryRoot = async (prefix, fn) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), prefix));
  try {
    return await fn(root);
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
};

const execution = (components) => components.executionOnly;

const materializeExecutionPlugin = async (root, manifest, components, hooks) => {
  await fs.mkdir(root, { recursive: true });
  await fs.writeFile(path.join(root, "plugin.json"), JSON.stringify(manifest, null, 2) + "\n", "utf8");
  await fs.writeFile(path.join(root, "hooks.json"), JSON.stringify(hooks, null, 2) + "\n", "utf8");

  const hook = execution(components).hook;
  const hookBody = execution(components).bodyOnly.hook;
  await fs.mkdir(path.join(root, path.dirname(hook.scriptPath)), { recursive: true });
  await fs.writeFile(path.join(root, hook.scriptPath), hookBody.text, "utf8");

  const agent = execution(components).agent;
  const agentBody = execution(components).bodyOnly.agent;
  await fs.mkdir(path.join(root, path.dirname(agent.relativePath)), { recursive: true });
  await fs.writeFile(
    path.join(root, agent.relativePath),
    [
      "---",
      "name: " + agent.name,
      "description: " + agent.description,
      "tools: []",
      "---",
      agentBody.text,
    ].join("\n"),
    "utf8",
  );
};

const classifyExecutionTrace = (components, trace) => {
  const hook = execution(components).hook;
  const hookBody = execution(components).bodyOnly.hook;
  const agent = execution(components).agent;
  const agentBody = execution(components).bodyOnly.agent;

  const hookResolution = trace.hook.timeout === true
    ? "timeout"
    : (trace.hook.malformedOutput === true
      ? "malformed_output"
      : (trace.hook.commandCwd === trace.hook.pluginRoot
        && trace.hook.injectedMarker === hookBody.marker
        && trace.hook.command === hook.command
          ? "plugin-root"
          : (trace.hook.observed === "unknown" ? "unknown" : "wrong-root")));

  const agentInheritance = trace.agent.invalidTools === true
    ? "invalid_tools"
    : (trace.agent.subagentTypeName === agent.name
      && trace.agent.responseMarker === agentBody.marker
      && Array.isArray(trace.agent.tools)
      && trace.agent.tools.length === 0
        ? "explicit"
        : (trace.agent.observed === "unknown" ? "unknown" : "mismatch"));

  const cleanup = trace.cleanup.pluginDirectoryRemoved === true
    && trace.cleanup.importManifestEntryRemoved === true
    && trace.cleanup.configEntryRemoved === true;

  return {
    schemaVersion: 1,
    hookResolution,
    agentInheritance,
    permissionBubbling: trace.agent.permissionMode === "always-proceed" ? "inherited" : "unknown",
    idle: trace.agent.idle ?? "unknown",
    kill: trace.agent.kill ?? "unknown",
    cleanup: cleanup ? "pass" : "fail",
    supportDecision: hookResolution === "plugin-root" && agentInheritance === "explicit" && cleanup ? "qualified" : "disqualified",
  };
};

test("execution canaries materialize a plugin-root hook and explicit no-tool custom agent", async () => {
  const manifest = await readJson(manifestPath);
  const components = await readJson(componentsPath);
  const hooks = await readJson(hooksPath);
  const hook = execution(components).hook;
  const agent = execution(components).agent;
  const hookBody = execution(components).bodyOnly.hook;
  const agentBody = execution(components).bodyOnly.agent;

  assert.deepEqual(hooks, {
    [hook.name]: {
      PreInvocation: [
        {
          type: "command",
          command: hook.command,
          timeout: hook.timeoutSeconds,
        },
      ],
    },
  });
  assert.equal(hook.command, "node hooks/pre-invocation.mjs");
  assert.equal(hook.expectedCwd, "plugin-root");
  assert.deepEqual(agent.tools, []);
  assert.equal(agent.inheritance, "explicit");

  await withTemporaryRoot("abe-t016-execution-", async (root) => {
    await materializeExecutionPlugin(root, manifest, components, hooks);
    const hookText = await fs.readFile(path.join(root, hook.scriptPath), "utf8");
    const agentText = await fs.readFile(path.join(root, agent.relativePath), "utf8");
    assert.equal(hookText.includes(hookBody.marker), true);
    assert.equal(agentText.includes(agentBody.marker), true);
    assert.equal(hookText.includes(agentBody.marker), false);
    assert.equal(agentText.includes(hookBody.marker), false);
  });
});

test("execution protocol freezes hook and agent traces with canonical evidence", async () => {
  const components = await readJson(componentsPath);
  const hooks = await readJson(hooksPath);
  const protocol = await readJson(protocolPath);
  const executionCheckpoint = protocol.executionConformance;

  assert.equal(executionCheckpoint.hooksDigest, digestObject(hooks));
  assert.equal(executionCheckpoint.executionComponentsDigest, digestObject(execution(components)));
  assert.equal(executionCheckpoint.probeResult.evidenceDigest, digestObject(executionCheckpoint.frozenTraceProjection));
  assert.deepEqual(executionCheckpoint.probeResult, {
    schemaVersion: 1,
    hookResolution: "plugin-root",
    agentInheritance: "explicit",
    evidenceDigest: executionCheckpoint.probeResult.evidenceDigest,
  });
  assert.equal(executionCheckpoint.frozenTraceProjection.hook.promptContainedHookMarker, false);
  assert.equal(executionCheckpoint.frozenTraceProjection.agent.promptContainedAgentMarker, false);
  assert.equal(executionCheckpoint.unknowns.includes("agent_kill_semantics"), true);
  assert.equal(executionCheckpoint.unknowns.includes("agent_idle_state"), true);
});

test("execution classifier covers timeout, malformed output, permission bubbling, idle, kill, and cleanup fail-closed", async () => {
  const components = await readJson(componentsPath);
  const protocol = await readJson(protocolPath);
  const trace = protocol.executionConformance.frozenTraceProjection;

  assert.deepEqual(classifyExecutionTrace(components, trace), {
    schemaVersion: 1,
    hookResolution: "plugin-root",
    agentInheritance: "explicit",
    permissionBubbling: "inherited",
    idle: "unknown",
    kill: "unknown",
    cleanup: "pass",
    supportDecision: "qualified",
  });

  assert.equal(classifyExecutionTrace(components, {
    ...trace,
    hook: { ...trace.hook, timeout: true },
  }).hookResolution, "timeout");
  assert.equal(classifyExecutionTrace(components, {
    ...trace,
    hook: { ...trace.hook, malformedOutput: true },
  }).hookResolution, "malformed_output");
  assert.equal(classifyExecutionTrace(components, {
    ...trace,
    agent: { ...trace.agent, invalidTools: true },
  }).agentInheritance, "invalid_tools");
  assert.equal(classifyExecutionTrace(components, {
    ...trace,
    cleanup: { ...trace.cleanup, pluginDirectoryRemoved: false },
  }).supportDecision, "disqualified");
});
