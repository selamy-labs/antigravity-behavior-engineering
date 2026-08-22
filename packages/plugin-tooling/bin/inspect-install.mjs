#!/usr/bin/env node
import fs from "node:fs/promises";

import { canonicalBytes } from "../../contracts/src/canonical-json.mjs";
import { inspectInstall, loadBehaviorLock } from "../src/lifecycle.mjs";

const usage = () => {
  process.stderr.write("usage: inspect-install --profile <profile-root> --expected <behavior-lock.json> [--output <file>]\n");
};

const parseArgs = (argv) => {
  const parsed = {};
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    if (!["--profile", "--expected", "--output"].includes(flag)) {
      throw new Error("unknown argument: " + flag);
    }
    if (index + 1 >= argv.length) {
      throw new Error("missing value for " + flag);
    }
    parsed[flag.slice(2)] = argv[index + 1];
    index += 1;
  }
  if (!parsed.profile || !parsed.expected) {
    throw new Error("missing required arguments");
  }
  return parsed;
};

try {
  const args = parseArgs(process.argv.slice(2));
  const lock = await loadBehaviorLock(args.expected);
  const inspection = await inspectInstall(args.profile, lock);
  const bytes = canonicalBytes(inspection);
  if (args.output) {
    await fs.writeFile(args.output, bytes);
    await fs.appendFile(args.output, "\n");
  } else {
    process.stdout.write(Buffer.from(bytes).toString("utf8") + "\n");
  }
} catch (error) {
  usage();
  process.stderr.write(String(error?.message || error) + "\n");
  process.exit(2);
}
