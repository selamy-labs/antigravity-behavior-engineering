#!/bin/sh
set -eu

if [ "$#" -eq 4 ] && [ "$1" = "node" ] && [ "$2" = "/opt/abe/verify-image.mjs" ] && [ "$3" = "--expected" ]; then
  exec /usr/local/bin/node /opt/abe/verify-image.mjs --expected "$4"
fi

if [ "$#" -ne 2 ] || [ "$1" != "--invocation" ] || [ "$2" != "/workspace/input/worker-invocation.json" ]; then
  echo "entrypoint accepts only --invocation /workspace/input/worker-invocation.json" >&2
  exit 64
fi

/usr/local/bin/node /opt/abe/verify-image.mjs --expected /workspace/input/qualification-lock.json

exec /usr/local/bin/node - <<'NODE'
const fs = require("node:fs");
const path = require("node:path");
const childProcess = require("node:child_process");

const outputRoot = "/workspace/output";
const invocation = JSON.parse(fs.readFileSync("/workspace/input/worker-invocation.json", "utf8"));
const lock = JSON.parse(fs.readFileSync("/workspace/input/qualification-lock.json", "utf8"));
const verification = JSON.parse(fs.readFileSync(path.join(outputRoot, "image-verification.json"), "utf8"));
const visibleRequest = fs.readFileSync(invocation.requestPath, "utf8");

const repoCanaries = fs
  .readdirSync("/workspace/repo", { withFileTypes: true })
  .filter((entry) => entry.isFile() && entry.name.endsWith("-visible-canary.txt"))
  .map((entry) => fs.readFileSync(path.join("/workspace/repo", entry.name), "utf8").trim())
  .sort();

const agyVersion = childProcess.execFileSync("/opt/antigravity/bin/agy", ["--version"], {
  encoding: "utf8",
  timeout: 10_000,
}).trim();

if (agyVersion !== lock.expectedRuntime.cliVersion) {
  throw new Error(`CLI version mismatch: expected ${lock.expectedRuntime.cliVersion}, got ${agyVersion}`);
}

const result = {
  schemaVersion: 1,
  runtime: verification.runtime,
  invocation: verification.invocation,
  qualification: verification.qualification,
  cli: {
    ...verification.cli,
    version: agyVersion,
  },
  paths: verification.paths,
  visibleRequest,
  repoCanaries,
};

fs.writeFileSync(path.join(outputRoot, "worker-result.json"), JSON.stringify(result, null, 2) + "\n");
NODE
