#!/usr/bin/env node
import { pathToFileURL } from "node:url";

import {
  EVIDENCE_OBSERVER_LIMITS,
  EvidenceCliError,
  appendEvidenceObservation,
  parseEvidenceObserverInput,
} from "./runtime-lib.mjs";

const readBoundedStdin = async (stdin) => {
  const chunks = [];
  let length = 0;
  for await (const chunk of stdin) {
    length += chunk.length;
    if (length > EVIDENCE_OBSERVER_LIMITS.maxInputBytes) {
      throw new EvidenceCliError("observer.input_limit");
    }
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf8");
};

const parseStdin = async (stdin) => {
  let input;
  try {
    input = JSON.parse(await readBoundedStdin(stdin));
  } catch (error) {
    if (error instanceof EvidenceCliError && error.reasonCode === "observer.input_limit") {
      throw error;
    }
    throw new EvidenceCliError("observer.invalid_json");
  }
  parseEvidenceObserverInput(input);
  return input;
};

const observationReason = (error) => {
  if (error instanceof EvidenceCliError) {
    return error.reasonCode;
  }
  return "observer.write_failed";
};

const inputDiagnostic = (error) => {
  const reason = observationReason(error);
  return error instanceof EvidenceCliError && error.path !== "$"
    ? reason + " " + error.path
    : reason;
};

export const main = async (io = process) => {
  let input;
  try {
    input = await parseStdin(io.stdin);
  } catch (error) {
    io.stderr.write(inputDiagnostic(error) + "\n");
    return 1;
  }

  try {
    await appendEvidenceObservation({ input });
  } catch (error) {
    io.stderr.write("observer.not_recorded " + observationReason(error) + "\n");
  }
  io.stdout.write("{}\n");
  return 0;
};

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().then((exitCode) => {
    process.exitCode = exitCode;
  }).catch(() => {
    process.stderr.write("observer.internal_error\n");
    process.exitCode = 1;
  });
}
