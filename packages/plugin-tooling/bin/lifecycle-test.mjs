#!/usr/bin/env node
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";

import { canonicalBytes } from "../../contracts/src/canonical-json.mjs";
import { ensureOutputOutsideRoot, writeCanonicalRecord } from "../src/package-lock.mjs";
import { materializeProfileFixture, runReleaseLifecycle } from "../src/lifecycle.mjs";

const usage = "usage: lifecycle-test --plugin <plugin-root> --profile-fixture <clean|customized|fixture.json> --record-timing <record.json> [--profile-root <disposable-profile>] [--cli <agy-path>]\n";

const parseArgs = (argv) => {
  const allowed = new Set(["--plugin", "--profile-fixture", "--record-timing", "--profile-root", "--cli"]);
  const values = {};
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    if (!allowed.has(flag) || index + 1 >= argv.length || Object.hasOwn(values, flag)) throw new Error("lifecycle.invalid_args");
    values[flag] = argv[index + 1];
  }
  if (!values["--plugin"] || !values["--profile-fixture"] || !values["--record-timing"]) throw new Error("lifecycle.invalid_args");
  return values;
};

const loadFixture = async (value) => {
  if (value === "clean") return { schemaVersion: 1, fixtureId: "clean", files: {} };
  const fixturePath = value === "customized"
    ? new URL("../../../tests/lifecycle/fixtures/customized-profile.json", import.meta.url)
    : path.resolve(value);
  return JSON.parse(await fs.readFile(fixturePath, "utf8"));
};

let temporaryProfile = null;
try {
  const args = parseArgs(process.argv.slice(2));
  const pluginRoot = await fs.realpath(args["--plugin"]);
  const fixture = await loadFixture(args["--profile-fixture"]);
  const profileRoot = args["--profile-root"]
    ? path.resolve(args["--profile-root"])
    : (temporaryProfile = await fs.mkdtemp(path.join(os.tmpdir(), "abe-release-profile-")));
  await materializeProfileFixture(profileRoot, fixture);
  await ensureOutputOutsideRoot(profileRoot, args["--record-timing"]);
  const report = await runReleaseLifecycle({
    cliPath: args["--cli"] || "agy",
    pluginRoot,
    profileRoot,
    profileFixture: fixture.fixtureId,
  });
  await writeCanonicalRecord(args["--record-timing"], report, pluginRoot);
  process.stdout.write(Buffer.from(canonicalBytes(report)).toString("utf8") + "\n");
  if (!report.valid) process.exitCode = 2;
} catch (error) {
  process.stderr.write(usage);
  process.stderr.write(String(error?.message || error) + "\n");
  process.exitCode = 2;
} finally {
  if (temporaryProfile) await fs.rm(temporaryProfile, { recursive: true, force: true });
}
