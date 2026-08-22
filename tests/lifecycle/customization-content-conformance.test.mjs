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

const componentByKind = (components, kind) => components.components.find((component) => component.kind === kind);

const bodyByKind = (components, kind) => components.bodyOnly[kind];

const metadataProjection = (components) => ({
  schemaVersion: components.schemaVersion,
  pluginName: components.pluginName,
  components: components.components.map((component) => ({
    schemaVersion: component.schemaVersion,
    kind: component.kind,
    name: component.name,
    relativePath: component.relativePath,
    description: component.description,
    applicabilitySignal: component.applicabilitySignal,
    defaultEnabled: component.defaultEnabled,
  })),
});

const materializeProbePlugin = async (root, manifest, components) => {
  await fs.mkdir(root, { recursive: true });
  await fs.writeFile(path.join(root, "plugin.json"), JSON.stringify(manifest, null, 2) + "\n", "utf8");
  for (const component of components.components) {
    const destination = path.join(root, component.relativePath);
    await fs.mkdir(path.dirname(destination), { recursive: true });
    const body = bodyByKind(components, component.kind);
    if (component.kind === "skill") {
      await fs.writeFile(
        destination,
        [
          "---",
          "name: " + component.name,
          "description: " + component.description,
          "---",
          body.text,
        ].join("\n"),
        "utf8",
      );
    } else if (component.kind === "rule") {
      await fs.writeFile(
        destination,
        [
          "---",
          "description: " + component.description,
          "---",
          body.text,
        ].join("\n"),
        "utf8",
      );
    } else {
      throw new TypeError("unexpected component kind " + component.kind);
    }
  }
};

const collisionsFor = (records, precedenceOrder) => {
  const precedence = new Map(precedenceOrder.map((scope, index) => [scope, index]));
  const grouped = new Map();
  for (const record of records) {
    const key = record.kind + "\n" + record.name;
    grouped.set(key, [...(grouped.get(key) || []), record]);
  }
  return [...grouped.entries()]
    .filter(([, items]) => new Set(items.map((item) => item.scope)).size > 1)
    .map(([key, items]) => {
      const ordered = [...items].sort((left, right) => precedence.get(left.scope) - precedence.get(right.scope));
      const [kind, name] = key.split("\n");
      return {
        schemaVersion: 1,
        kind,
        name,
        winner: ordered[0].scope,
        blockedScopes: ordered.slice(1).map((item) => item.scope),
        paths: ordered.map((item) => item.path),
      };
    })
    .sort((left, right) => (left.kind + left.name).localeCompare(right.kind + right.name));
};

const classifyContentTrace = (protocol, components, trace) => {
  const policy = protocol.classificationPolicy;
  const collisions = collisionsFor(trace.discoveryRecords, policy.scopePrecedence);
  if (collisions.length > 0) {
    return {
      schemaVersion: 1,
      supportDecision: "content_discovery_failed",
      skill: "blocked_by_collision",
      rule: "blocked_by_collision",
      skillBodyObservable: false,
      ruleBodySelective: false,
      blockingCollisions: collisions,
    };
  }

  const skillBody = bodyByKind(components, "skill");
  const skillObserved = trace.skill.bodyMarkerObservation;
  const skill =
    skillObserved === true && trace.skill.bodyMarker === skillBody.marker && trace.skill.firstApplicableTaskWithoutActivationPhrase === true
      ? "qualified"
      : (skillObserved === "unknown" ? "unknown" : "disqualified");

  const rule = trace.rule.modelDecisionObservable === true
    && trace.rule.applicableBodyObserved === true
    && trace.rule.nonApplicableBodyObserved === false
    ? "qualified"
    : "disqualified";

  let supportDecision = "qualified";
  if (skill === "unknown") {
    supportDecision = "unknown";
  } else if (skill !== "qualified" || rule !== "qualified") {
    supportDecision = "disqualified";
  }

  return {
    schemaVersion: 1,
    supportDecision,
    skill,
    rule,
    skillBodyObservable: skill === "qualified",
    ruleBodySelective: rule === "qualified",
    blockingCollisions: [],
  };
};

test("probe plugin keeps metadata and body surfaces separate while materializing public skill and rule canaries", async () => {
  const manifest = await readJson(manifestPath);
  const components = await readJson(componentsPath);
  const skill = componentByKind(components, "skill");
  const rule = componentByKind(components, "rule");
  const skillBody = bodyByKind(components, "skill");
  const ruleBody = bodyByKind(components, "rule");

  assert.deepEqual(manifest, { name: components.pluginName });
  assert.equal(skill.relativePath, "skills/abe-t015-content-skill/SKILL.md");
  assert.equal(rule.relativePath, "rules/AGENTS.md");
  assert.notEqual(skillBody.marker, ruleBody.marker);

  const metadata = JSON.stringify(metadataProjection(components));
  assert.equal(metadata.includes(skillBody.marker), false);
  assert.equal(metadata.includes(ruleBody.marker), false);
  assert.equal(metadata.includes(skill.applicabilitySignal), true);
  assert.equal(metadata.includes(rule.applicabilitySignal), true);

  await withTemporaryRoot("abe-t015-probe-", async (root) => {
    await materializeProbePlugin(root, manifest, components);
    const materializedManifest = await readJson(path.join(root, "plugin.json"));
    const skillText = await fs.readFile(path.join(root, skill.relativePath), "utf8");
    const ruleText = await fs.readFile(path.join(root, rule.relativePath), "utf8");
    assert.deepEqual(Object.keys(materializedManifest), ["name"]);
    assert.equal(skillText.includes(skillBody.marker), true);
    assert.equal(ruleText.includes(ruleBody.marker), true);
    assert.equal(skillText.includes(ruleBody.marker), false);
    assert.equal(ruleText.includes(skillBody.marker), false);
  });
});

test("customization conformance protocol freezes the live trace and refuses to turn unknown into pass", async () => {
  const manifest = await readJson(manifestPath);
  const components = await readJson(componentsPath);
  const protocol = await readJson(protocolPath);
  const protocolBody = { ...protocol };
  protocolBody.protocolDigest = undefined;
  delete protocolBody.protocolDigest;

  assert.equal(protocol.protocolDigest, digestObject(protocolBody));
  assert.equal(protocol.probeManifestDigest, sha256Digest(await fs.readFile(manifestPath)));
  assert.equal(protocol.probeComponentsDigest, digestObject(components));
  assert.equal(protocol.probeResult.evidenceDigest, digestObject(protocol.frozenTraceProjection));
  assert.equal(protocol.proposedSupportedProfiles.length, 1);
  assert.deepEqual(protocol.proposedSupportedProfiles[0], {
    schemaVersion: 1,
    cliVersion: "1.1.18",
    os: "linux",
    architecture: "x64",
    nodeRange: ">=22 <25",
    status: "supported",
  });
  assert.deepEqual(protocol.probeResult, {
    schemaVersion: 1,
    supportDecision: "disqualified",
    skillBodyObservable: true,
    ruleBodySelective: false,
    rule: "disqualified",
    evidenceDigest: protocol.probeResult.evidenceDigest,
  });
  assert.equal(protocol.classificationPolicy.unknownIsPass, false);
  assert.equal(JSON.stringify({ manifest, components, protocol }).includes("hidden label"), false);
  assert.equal(JSON.stringify({ manifest, components, protocol }).includes("treatment conclusion"), false);
});

test("content classifier covers precedence collisions, skill activation, and rule Model Decision fail-closed", async () => {
  const components = await readJson(componentsPath);
  const protocol = await readJson(protocolPath);
  const skill = componentByKind(components, "skill");
  const skillBody = bodyByKind(components, "skill");

  const qualifiedSkill = {
    bodyMarkerObservation: true,
    bodyMarker: skillBody.marker,
    firstApplicableTaskWithoutActivationPhrase: true,
  };

  assert.deepEqual(
    classifyContentTrace(protocol, components, {
      discoveryRecords: [
        { schemaVersion: 1, scope: "plugin", kind: "skill", name: skill.name, path: skill.relativePath },
        { schemaVersion: 1, scope: "plugin", kind: "rule", name: "abe-t015-content-rule", path: "rules/AGENTS.md" },
      ],
      skill: qualifiedSkill,
      rule: {
        modelDecisionObservable: true,
        applicableBodyObserved: true,
        nonApplicableBodyObserved: false,
      },
    }),
    {
      schemaVersion: 1,
      supportDecision: "qualified",
      skill: "qualified",
      rule: "qualified",
      skillBodyObservable: true,
      ruleBodySelective: true,
      blockingCollisions: [],
    },
  );

  assert.deepEqual(
    classifyContentTrace(protocol, components, {
      discoveryRecords: [
        { schemaVersion: 1, scope: "plugin", kind: "skill", name: skill.name, path: skill.relativePath },
      ],
      skill: { ...qualifiedSkill, bodyMarkerObservation: "unknown" },
      rule: {
        modelDecisionObservable: false,
        applicableBodyObserved: "unknown",
        nonApplicableBodyObserved: "unknown",
      },
    }),
    {
      schemaVersion: 1,
      supportDecision: "unknown",
      skill: "unknown",
      rule: "disqualified",
      skillBodyObservable: false,
      ruleBodySelective: false,
      blockingCollisions: [],
    },
  );

  assert.deepEqual(
    classifyContentTrace(protocol, components, {
      discoveryRecords: [
        { schemaVersion: 1, scope: "plugin", kind: "rule", name: "abe-t015-content-rule", path: "rules/AGENTS.md" },
      ],
      skill: qualifiedSkill,
      rule: {
        modelDecisionObservable: true,
        applicableBodyObserved: true,
        nonApplicableBodyObserved: true,
      },
    }).rule,
    "disqualified",
  );

  const colliding = classifyContentTrace(protocol, components, {
    discoveryRecords: [
      { schemaVersion: 1, scope: "global", kind: "skill", name: skill.name, path: "skills/global/SKILL.md" },
      { schemaVersion: 1, scope: "workspace", kind: "skill", name: skill.name, path: "skills/workspace/SKILL.md" },
      { schemaVersion: 1, scope: "plugin", kind: "skill", name: skill.name, path: skill.relativePath },
    ],
    skill: qualifiedSkill,
    rule: {
      modelDecisionObservable: true,
      applicableBodyObserved: true,
      nonApplicableBodyObserved: false,
    },
  });

  assert.equal(colliding.supportDecision, "content_discovery_failed");
  assert.deepEqual(colliding.blockingCollisions, [
    {
      schemaVersion: 1,
      kind: "skill",
      name: skill.name,
      winner: "global",
      blockedScopes: ["workspace", "plugin"],
      paths: ["skills/global/SKILL.md", "skills/workspace/SKILL.md", skill.relativePath],
    },
  ]);
});
