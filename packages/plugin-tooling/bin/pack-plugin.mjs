#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";

import {
  canonicalRecordBytes,
  ensureOutputOutsideRoot,
  packPlugin,
  writeCanonicalRecord,
} from "../src/package-lock.mjs";

const usage = "usage: pack-plugin --root <plugin-root> --output <archive.tgz> --manifest-out <record.json> [--require-archive-match <archive.tgz>] [--require-manifest-match <record.json>]\n";

const parseArgs = (argv) => {
  const allowed = new Set(["--root", "--output", "--manifest-out", "--require-archive-match", "--require-manifest-match"]);
  const values = {};
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    if (!allowed.has(flag) || index + 1 >= argv.length || Object.hasOwn(values, flag)) throw new Error("package.invalid_args");
    values[flag] = argv[index + 1];
  }
  if (!values["--root"] || !values["--output"] || !values["--manifest-out"]) throw new Error("package.invalid_args");
  const artifactPaths = [values["--output"], values["--manifest-out"]].map((value) => path.resolve(value));
  if (new Set(artifactPaths).size !== artifactPaths.length) throw new Error("package.invalid_args");
  if (values["--require-archive-match"] && path.resolve(values["--require-archive-match"]) === artifactPaths[0]) throw new Error("package.invalid_args");
  if (values["--require-manifest-match"] && path.resolve(values["--require-manifest-match"]) === artifactPaths[1]) throw new Error("package.invalid_args");
  return values;
};

try {
  const args = parseArgs(process.argv.slice(2));
  await ensureOutputOutsideRoot(await fs.realpath(args["--root"]), args["--manifest-out"]);
  const record = await packPlugin(args["--root"], args["--output"]);
  if (args["--require-archive-match"]) {
    const [actual, expected] = await Promise.all([
      fs.readFile(args["--output"]),
      fs.readFile(args["--require-archive-match"]),
    ]);
    if (!actual.equals(expected)) throw new Error("package.archive_mismatch");
  }
  if (args["--require-manifest-match"]) {
    const expected = JSON.parse(await fs.readFile(args["--require-manifest-match"], "utf8"));
    if (!canonicalRecordBytes(record).equals(canonicalRecordBytes(expected))) throw new Error("package.manifest_mismatch");
  }
  await writeCanonicalRecord(args["--manifest-out"], record);
  process.stdout.write(canonicalRecordBytes(record).toString("utf8") + "\n");
} catch (error) {
  process.stderr.write(usage);
  process.stderr.write(String(error?.message || error) + "\n");
  process.exitCode = 2;
}
