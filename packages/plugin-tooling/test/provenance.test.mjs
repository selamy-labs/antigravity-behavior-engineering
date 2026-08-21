import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { buildProvenanceInventory, ProvenanceValidationError } from "../src/provenance.mjs";

const fixturePath = new URL("../../../tests/provenance/fixtures.json", import.meta.url);
const fixtures = JSON.parse(await fs.readFile(fixturePath, "utf8"));

const rawDigest = (text) => "sha256:" + createHash("sha256").update(Buffer.from(text, "utf8")).digest("hex");

const fileLockFor = (files) => Object.fromEntries(Object.entries(files).map(([relativePath, contents]) => [relativePath, rawDigest(contents)]));

const withTree = async (files, fn) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "abe-provenance-"));
  for (const [relativePath, contents] of Object.entries(files)) {
    await fs.mkdir(path.dirname(path.join(root, relativePath)), { recursive: true });
    await fs.writeFile(path.join(root, relativePath), contents, "utf8");
  }
  try {
    return await fn(root);
  } finally {
    await fs.rm(root, { recursive: true, force: true });
  }
};

const packageLockFor = (files, overrides = {}) => ({
  schemaVersion: 1,
  packageName: "antigravity-behavior-engineering",
  packageVersion: "0.1.0",
  sourceRevision: "1234567890abcdef1234567890abcdef12345678",
  minimumCliVersion: "0.1.0",
  supportedPlatforms: [{ schemaVersion: 1, os: "linux", architecture: "x64", nodeRange: ">=22 <25" }],
  components: [],
  dependencies: fixtures.pinnedDependencies,
  files: fileLockFor(files),
  generatedAt: "2026-08-18T00:00:00Z",
  ...overrides,
});

const lockSetFor = (files, overrides = {}) => ({
  schemaVersion: 1,
  policyDigest: "sha256:" + "8".repeat(64),
  noticePath: "NOTICE",
  packageLock: packageLockFor(files),
  adaptations: fixtures.adaptations,
  ...overrides,
});

const expectProvenanceError = async (code, fn) => {
  await assert.rejects(fn, (error) => error instanceof ProvenanceValidationError && error.code === code);
};

test("provenance inventory is deterministic, attributed, pinned, and not a legal approval", async () => {
  await withTree(fixtures.benignFiles, async (root) => {
    const lockSet = lockSetFor(fixtures.benignFiles);
    const first = await buildProvenanceInventory(root, lockSet);
    const second = await buildProvenanceInventory(root, lockSet);

    assert.deepEqual(first, second);
    assert.equal(first.schemaVersion, 1);
    assert.match(first.inventoryId, /^provenance-inventory-[0-9a-f]{12}$/u);
    assert.match(first.rootDigest, /^sha256:[0-9a-f]{64}$/u);
    assert.equal(first.noticeDigest, rawDigest(fixtures.benignFiles.NOTICE));
    assert.equal(first.policyDigest, lockSet.policyDigest);
    assert.deepEqual(first.sources, fixtures.pinnedDependencies.map(({ sourceUrl, revision, license, consumption }) => ({
      schemaVersion: 1,
      sourceUrl,
      revision,
      license,
      consumption,
    })).sort((left, right) => left.sourceUrl.localeCompare(right.sourceUrl)));
    assert.deepEqual(first.adaptations, fixtures.adaptations);
    assert.equal(Object.hasOwn(first, "licenseVerdict"), false);
    assert.equal(Object.hasOwn(first, "approvalDecision"), false);
  });
});

test("human-review-only license policy remains inventoried without an automated compatibility verdict", async () => {
  await withTree(fixtures.benignFiles, async (root) => {
    const lockSet = lockSetFor(fixtures.benignFiles, {
      packageLock: packageLockFor(fixtures.benignFiles, {
        dependencies: [...fixtures.pinnedDependencies, fixtures.humanReviewOnlyDependency],
      }),
    });
    const inventory = await buildProvenanceInventory(root, lockSet);
    assert.equal(inventory.sources.some((source) => source.license === "GPL-3.0-only"), true);
    assert.equal(Object.hasOwn(inventory, "supportedLicenseVerdict"), false);
  });
});

test("provenance fails visibly for unpinned sources, missing notices, unexpected files, and hash drift", async () => {
  await withTree(fixtures.benignFiles, async (root) => {
    await expectProvenanceError("provenance.unpinned_source", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, {
      packageLock: packageLockFor(fixtures.benignFiles, {
        dependencies: [{ ...fixtures.pinnedDependencies[0], revision: "main" }],
      }),
    })));

    const missingNotice = { ...fixtures.benignFiles };
    delete missingNotice.NOTICE;
    await withTree(missingNotice, async (missingRoot) => {
      await expectProvenanceError("provenance.missing_notice", () => buildProvenanceInventory(missingRoot, lockSetFor(missingNotice)));
    });

    const unexpected = { ...fixtures.benignFiles, "extra/unexpected.md": "not in lock\n" };
    await withTree(unexpected, async (unexpectedRoot) => {
      await expectProvenanceError("provenance.unexpected_file", () => buildProvenanceInventory(unexpectedRoot, lockSetFor(fixtures.benignFiles)));
    });

    const driftedLock = lockSetFor(fixtures.benignFiles);
    driftedLock.packageLock.files["README.md"] = "sha256:" + "0".repeat(64);
    await expectProvenanceError("provenance.file_digest_mismatch", () => buildProvenanceInventory(root, driftedLock));
  });
});

test("provenance fails closed for malformed locks and schema-invalid source records", async () => {
  await withTree(fixtures.benignFiles, async (root) => {
    await expectProvenanceError("provenance.invalid_field", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, {
      packageLock: packageLockFor(fixtures.benignFiles, {
        dependencies: "not-an-array",
      }),
    })));

    await expectProvenanceError("provenance.invalid_field", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, {
      adaptations: "not-an-array",
    })));

    await expectProvenanceError("provenance.invalid_source", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, {
      packageLock: packageLockFor(fixtures.benignFiles, {
        dependencies: [{ ...fixtures.pinnedDependencies[0], sourceUrl: "https://example.com/bad source" }],
      }),
    })));

    for (const sourceUrl of ["https://github.com/example/repo\nhttps://evil.example/repo", "https://github.com/example/repo\twith-tab"]) {
      await expectProvenanceError("provenance.invalid_source", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, {
        packageLock: packageLockFor(fixtures.benignFiles, {
          dependencies: [{ ...fixtures.pinnedDependencies[0], sourceUrl }],
        }),
      })));
    }

    await expectProvenanceError("provenance.invalid_source", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, {
      packageLock: packageLockFor(fixtures.benignFiles, {
        dependencies: [{ ...fixtures.pinnedDependencies[0], sourceUrl: "https://#fragment-only" }],
      }),
    })));

    await expectProvenanceError("provenance.invalid_digest", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, {
      policyDigest: 7,
    })));

    await expectProvenanceError("provenance.invalid_path", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, {
      noticePath: 7,
    })));

    await expectProvenanceError("provenance.unqualified_required_dependency", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, {
      packageLock: packageLockFor(fixtures.benignFiles, {
        dependencies: [{ ...fixtures.pinnedDependencies[0], required: true, qualificationEvidence: "not_qualified" }],
      }),
    })));
  });
});

test("provenance fails closed for incomplete or unpinned package locks", async () => {
  await withTree(fixtures.benignFiles, async (root) => {
    const missingName = packageLockFor(fixtures.benignFiles);
    delete missingName.packageName;
    await expectProvenanceError("provenance.invalid_package_lock", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, { packageLock: missingName })));

    await expectProvenanceError("provenance.unpinned_source", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, {
      packageLock: packageLockFor(fixtures.benignFiles, { sourceRevision: "main" }),
    })));

    await expectProvenanceError("provenance.invalid_package_lock", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, {
      packageLock: packageLockFor(fixtures.benignFiles, { supportedPlatforms: [] }),
    })));

    const missingNodeRange = packageLockFor(fixtures.benignFiles, {
      supportedPlatforms: [{ schemaVersion: 1, os: "linux", architecture: "x64" }],
    });
    await expectProvenanceError("provenance.invalid_package_lock", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, { packageLock: missingNodeRange })));

    await expectProvenanceError("provenance.invalid_package_lock", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, {
      packageLock: packageLockFor(fixtures.benignFiles, {
        supportedPlatforms: [{ schemaVersion: 1, os: "linux", architecture: "x64", nodeRange: "not a semver range" }],
      }),
    })));
  });
});

test("provenance enforces package identity, component uniqueness, and lock self-digest exception", async () => {
  await withTree({ ...fixtures.benignFiles, "behavior-lock.json": "{\"self\":\"excluded\"}\n" }, async (root) => {
    const inventory = await buildProvenanceInventory(root, lockSetFor({ ...fixtures.benignFiles, "behavior-lock.json": "{\"self\":\"excluded\"}\n" }, {
      packageLock: packageLockFor(fixtures.benignFiles),
    }));
    assert.match(inventory.rootDigest, /^sha256:[0-9a-f]{64}$/u);

    await expectProvenanceError("provenance.invalid_package_lock", () => buildProvenanceInventory(root, lockSetFor({ ...fixtures.benignFiles, "behavior-lock.json": "{\"self\":\"excluded\"}\n" }, {
      packageLock: packageLockFor(fixtures.benignFiles, { packageName: "different-lock-name" }),
    })));

    const component = {
      schemaVersion: 1,
      kind: "skill",
      name: "example",
      path: "skills/example/SKILL.md",
      claimId: "claim-example",
      defaultEnabled: true,
      digest: "sha256:" + "9".repeat(64),
    };
    await expectProvenanceError("provenance.invalid_package_lock", () => buildProvenanceInventory(root, lockSetFor({ ...fixtures.benignFiles, "behavior-lock.json": "{\"self\":\"excluded\"}\n" }, {
      packageLock: packageLockFor(fixtures.benignFiles, { components: [component, { ...component, path: "skills/example-copy/SKILL.md" }] }),
    })));
  });
});

test("provenance rejects hidden lock fields and control-bearing source URLs", async () => {
  await withTree(fixtures.benignFiles, async (root) => {
    await expectProvenanceError("provenance.invalid_field", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, {
      packageLock: packageLockFor(fixtures.benignFiles, {
        dependencies: [{ ...fixtures.pinnedDependencies[0], hiddenReviewerNote: "must not be silently dropped" }],
      }),
    })));

    await expectProvenanceError("provenance.invalid_field", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, {
      adaptations: [{ ...fixtures.adaptations[0], approvalDecision: "must remain a human provenance record" }],
    })));

    await expectProvenanceError("provenance.invalid_source", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, {
      packageLock: packageLockFor(fixtures.benignFiles, {
        dependencies: [{ ...fixtures.pinnedDependencies[0], sourceUrl: "https://github.com/example/repo" + "\u0000" + "suffix" }],
      }),
    })));
  });
});

test("provenance binds component locks to package files", async () => {
  await withTree(fixtures.benignFiles, async (root) => {
    const component = {
      schemaVersion: 1,
      kind: "skill",
      name: "example",
      path: "src/index.md",
      claimId: "claim-example",
      defaultEnabled: true,
      digest: rawDigest(fixtures.benignFiles["src/index.md"]),
    };

    const inventory = await buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, {
      packageLock: packageLockFor(fixtures.benignFiles, { components: [component] }),
    }));
    assert.match(inventory.rootDigest, /^sha256:[0-9a-f]{64}$/u);

    await expectProvenanceError("provenance.file_digest_mismatch", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, {
      packageLock: packageLockFor(fixtures.benignFiles, { components: [{ ...component, digest: "sha256:" + "0".repeat(64) }] }),
    })));

    await expectProvenanceError("provenance.missing_file", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, {
      packageLock: packageLockFor(fixtures.benignFiles, { components: [{ ...component, path: "skills/missing/SKILL.md" }] }),
    })));
  });
});

test("provenance validates license identifiers and adaptation targets", async () => {
  await withTree(fixtures.benignFiles, async (root) => {
    await expectProvenanceError("provenance.invalid_field", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, {
      packageLock: packageLockFor(fixtures.benignFiles, {
        dependencies: [{ ...fixtures.pinnedDependencies[0], license: "not an SPDX id" }],
      }),
    })));

    await expectProvenanceError("provenance.missing_file", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, {
      adaptations: [{ ...fixtures.adaptations[0], localPath: "does/not/exist.md" }],
    })));
  });
});
