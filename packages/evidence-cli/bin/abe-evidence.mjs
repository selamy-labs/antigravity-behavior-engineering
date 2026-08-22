#!/usr/bin/env node
import { main } from "../src/task-state.mjs";

main().then((exitCode) => {
  process.exitCode = exitCode;
}).catch((error) => {
  if (error?.reasonCode && error?.path) {
    process.stderr.write(error.reasonCode + " at " + error.path + "\n");
    process.exitCode = 1;
    return;
  }
  process.stderr.write((error && error.stack) ? error.stack + "\n" : String(error) + "\n");
  process.exitCode = 1;
});
