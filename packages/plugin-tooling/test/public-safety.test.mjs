import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { scanPublicTree } from "../src/public-safety.mjs";

const fixturePath = new URL("../../../tests/provenance/fixtures.json", import.meta.url);
const fixtures = JSON.parse(await fs.readFile(fixturePath, "utf8"));
const encoder = new TextEncoder();

const rawDigest = (text) => "sha256:" + createHash("sha256").update(encoder.encode(text.trim().replace(/\s+/gu, " "))).digest("hex");

const withTree = async (files, fn) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "abe-public-safety-"));
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

const policyFor = (expectedFiles) => ({
  schemaVersion: 1,
  policyId: fixtures.policyId,
  expectedFiles,
  requiredNoticeFiles: ["NOTICE"],
  copiedBodyFingerprints: [
    {
      fingerprintId: "synthetic-copied-body",
      digest: rawDigest(fixtures.copiedBodyText),
      normalizedTokenCount: fixtures.copiedBodyText.trim().split(/\s+/u).length,
      severity: "critical",
    },
  ],
});

test("benign public Google terminology produces a deterministic empty safety report", async () => {
  await withTree(fixtures.benignFiles, async (root) => {
    const policy = policyFor(Object.keys(fixtures.benignFiles).sort());
    const first = await scanPublicTree(root, policy);
    const second = await scanPublicTree(root, policy);

    assert.deepEqual(first, second);
    assert.equal(first.schemaVersion, 1);
    assert.match(first.reportId, /^safety-report-[0-9a-f]{12}$/u);
    assert.match(first.rootDigest, /^sha256:[0-9a-f]{64}$/u);
    assert.match(first.policyDigest, /^sha256:[0-9a-f]{64}$/u);
    assert.deepEqual(first.findings, []);
    assert.equal(first.criticalOpenCount, 0);
    assert.deepEqual([...first.scannerDigests].sort(), first.scannerDigests);
  });
});

test("synthetic public-safety lookalikes produce exact open critical findings", async () => {
  await withTree(fixtures.unsafeFiles, async (root) => {
    const expectedFiles = Object.keys(fixtures.unsafeFiles).filter((file) => file !== "extra/unexpected.md").concat("NOTICE").sort();
    const report = await scanPublicTree(root, policyFor(expectedFiles));

    const byId = Object.fromEntries(report.findings.map((finding) => [finding.findingId, finding]));
    assert.deepEqual(Object.keys(byId), [
      "public-safety.copied_body_fingerprint.001",
      "public-safety.credential.001",
      "public-safety.credential.002",
      "public-safety.google_confidential_identifier.001",
      "public-safety.google_confidential_identifier.002",
      "public-safety.missing_notice.001",
      "public-safety.private_path.001",
      "public-safety.private_path.002",
      "public-safety.unexpected_file.001",
      "public-safety.unpinned_source.001",
    ]);
    assert.equal(report.criticalOpenCount, 10);
    for (const finding of report.findings) {
      assert.equal(finding.schemaVersion, 1);
      assert.equal(finding.severity, "critical");
      assert.equal(finding.status, "open");
      assert.match(finding.evidenceDigest, /^sha256:[0-9a-f]{64}$/u);
    }
    assert.equal(byId["public-safety.credential.001"].location, "bad/credentials.md#L1C33");
    assert.equal(byId["public-safety.google_confidential_identifier.001"].location, "bad/google-confidential.md#L1C46");
    assert.equal(byId["public-safety.private_path.001"].location, "bad/private-path.md#L1C35");
    assert.equal(byId["public-safety.credential.002"].location, "bad/zz-credential-format.md#L1C38");
    assert.equal(byId["public-safety.google_confidential_identifier.002"].location, "bad/zz-google-confidential-label.md#L1C18");
    assert.equal(byId["public-safety.private_path.002"].location, "bad/zz-private-path.md#L1C22");
    assert.equal(byId["public-safety.copied_body_fingerprint.001"].location, "bad/copied-body.md#L1C1");
    assert.equal(byId["public-safety.unpinned_source.001"].location, "bad/unpinned-source.md#L1C28");
    assert.equal(byId["public-safety.missing_notice.001"].location, "NOTICE");
    assert.equal(byId["public-safety.unexpected_file.001"].location, "extra/unexpected.md");
  });
});

test("safety scanner does not let binary framing or wrapping hide known public-release leaks", async () => {
  const wrappedCopiedBody = fixtures.copiedBodyText.replace("this sentence is", "this\nsentence is");
  await withTree({
    "README.md": "Synthetic binary-framed leak: ABE_SYNTHETIC_SECRET_ABCDEFGHIJKLMNOP\u0000\n",
    "NOTICE": "notice\n",
    "docs/wrapped.md": wrappedCopiedBody + "\n",
  }, async (root) => {
    const report = await scanPublicTree(root, policyFor(["README.md", "NOTICE", "docs/wrapped.md"]));
    const byKind = Object.groupBy(report.findings, (finding) => finding.findingId.split(".")[1]);
    const credentials = byKind.credential ?? [];
    const copiedBodyFindings = byKind.copied_body_fingerprint ?? [];

    assert.equal(credentials.length, 1);
    assert.equal(credentials[0].location, "README.md#L1C31");
    assert.equal(copiedBodyFindings.length, 1);
    assert.equal(copiedBodyFindings[0].location, "docs/wrapped.md#L1C1");
    assert.equal(report.criticalOpenCount, 2);
  });
});

test("safety reports fail visibly instead of emitting schema-invalid policy digests", async () => {
  await withTree(fixtures.benignFiles, async (root) => {
    await assert.rejects(
      () => scanPublicTree(root, { ...policyFor(Object.keys(fixtures.benignFiles).sort()), policyDigest: "not-a-digest" }),
      /policyDigest/u,
    );
  });
});

test("fixture lookalikes are absent from benign publishable samples", () => {
  const benignText = JSON.stringify(fixtures.benignFiles);
  assert.equal(benignText.includes("ABE_SYNTHETIC_SECRET_"), false);
  assert.equal(benignText.includes("GOOGLE_CONFIDENTIAL_SYNTHETIC_"), false);
  assert.equal(benignText.includes("/Users/synthetic-private-maintainer/"), false);
  assert.equal(benignText.includes(fixtures.copiedBodyText), false);
});
