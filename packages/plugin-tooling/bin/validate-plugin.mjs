#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";

import { canonicalRecordBytes, validatePlugin, writeCanonicalRecord } from "../src/package-lock.mjs";

const usage = "usage: validate-plugin --root <plugin-root> [--output <report.json>]\n";

const parseArgs = (argv) => {
  const values = {};
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    if (!["--root", "--output"].includes(flag) || index + 1 >= argv.length) throw new Error("package.invalid_args");
    values[flag.slice(2)] = argv[index + 1];
  }
  if (!values.root) throw new Error("package.invalid_args");
  return values;
};

try {
  const args = parseArgs(process.argv.slice(2));
  const lock = JSON.parse(await fs.readFile(path.join(args.root, "behavior-lock.json"), "utf8"));
  const report = await validatePlugin(args.root, lock);
  if (args.output) await writeCanonicalRecord(args.output, report);
  process.stdout.write(canonicalRecordBytes(report).toString("utf8") + "\n");
} catch (error) {
  process.stderr.write(usage);
  process.stderr.write(String(error?.message || error) + "\n");
  process.exitCode = 2;
}
