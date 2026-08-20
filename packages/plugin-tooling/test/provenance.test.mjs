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

const lockSetFor = (files, overrides = {}) => ({
  schemaVersion: 1,
  policyDigest: "sha256:" + "8".repeat(64),
  noticePath: "NOTICE",
  packageLock: {
    schemaVersion: 1,
    dependencies: fixtures.pinnedDependencies,
    files: Object.fromEntries(Object.entries(files).map(([relativePath, contents]) => [relativePath, rawDigest(contents)])),
  },
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
      packageLock: {
        schemaVersion: 1,
        dependencies: [...fixtures.pinnedDependencies, fixtures.humanReviewOnlyDependency],
        files: Object.fromEntries(Object.entries(fixtures.benignFiles).map(([relativePath, contents]) => [relativePath, rawDigest(contents)])),
      },
    });
    const inventory = await buildProvenanceInventory(root, lockSet);
    assert.equal(inventory.sources.some((source) => source.license === "GPL-3.0-only"), true);
    assert.equal(Object.hasOwn(inventory, "supportedLicenseVerdict"), false);
  });
});

test("provenance fails visibly for unpinned sources, missing notices, unexpected files, and hash drift", async () => {
  await withTree(fixtures.benignFiles, async (root) => {
    await expectProvenanceError("provenance.unpinned_source", () => buildProvenanceInventory(root, lockSetFor(fixtures.benignFiles, {
      packageLock: {
        schemaVersion: 1,
        dependencies: [{ ...fixtures.pinnedDependencies[0], revision: "main" }],
        files: Object.fromEntries(Object.entries(fixtures.benignFiles).map(([relativePath, contents]) => [relativePath, rawDigest(contents)])),
      },
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
