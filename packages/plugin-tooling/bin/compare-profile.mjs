#!/usr/bin/env node
import fs from "node:fs/promises";

import { canonicalBytes } from "../../contracts/src/canonical-json.mjs";
import { diffProfileSnapshots } from "../src/lifecycle.mjs";

const usage = "usage: compare-profile --before <profile-manifest.json> --after <profile-manifest.json>\n";

const parseArgs = (argv) => {
  const values = {};
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    if (!["--before", "--after"].includes(flag) || index + 1 >= argv.length || Object.hasOwn(values, flag)) throw new Error("lifecycle.invalid_args");
    values[flag] = argv[index + 1];
  }
  if (!values["--before"] || !values["--after"]) throw new Error("lifecycle.invalid_args");
  return values;
};

try {
  const args = parseArgs(process.argv.slice(2));
  const [before, after] = await Promise.all([
    fs.readFile(args["--before"], "utf8").then(JSON.parse),
    fs.readFile(args["--after"], "utf8").then(JSON.parse),
  ]);
  const diff = diffProfileSnapshots(before, after);
  process.stdout.write(Buffer.from(canonicalBytes(diff)).toString("utf8") + "\n");
  if (diff.changedPaths.length > 0) process.exitCode = 2;
} catch (error) {
  process.stderr.write(usage);
  process.stderr.write(String(error?.message || error) + "\n");
  process.exitCode = 2;
}
