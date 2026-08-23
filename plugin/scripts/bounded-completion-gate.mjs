import { constants as fsConstants } from "node:fs";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  canonicalBytes,
  parseCompletionGateEvent,
  parseTaskState,
  sha256Digest,
} from "./runtime-lib.mjs";

export const COMPLETION_GATE_LIMITS = Object.freeze({
  frozenBound: 1,
  maximumInputBytes: 1024 * 1024,
  maximumStateBytes: 1024 * 1024,
  maximumLedgerBytes: 4 * 1024 * 1024,
  maximumWorkspacePaths: 8,
  maximumTaskDirectories: 128,
  maximumStringBytes: 4096,
  lockWaitMilliseconds: 150,
});

const DIGEST_PATTERN = /^sha256:[0-9a-f]{64}$/u;
const TASK_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/u;
const allow = Object.freeze({ decision: "" });
const canonicalLine = (value) => Buffer.from(canonicalBytes(value)).toString("utf8") + "\n";
const immediateHonestReport = "Do not use tools or perform more work in response to this Stop; immediately report an honest non-complete terminal state and name this condition.";

class InvalidInputError extends Error {}
class FailOpenError extends Error {
  constructor(reasonCode) {
    super(reasonCode);
    this.reasonCode = reasonCode;
  }
}

const failOpen = (reasonCode) => {
  throw new FailOpenError(reasonCode);
};

const validString = (value) => typeof value === "string"
  && Buffer.byteLength(value, "utf8") <= COMPLETION_GATE_LIMITS.maximumStringBytes
  && !value.includes("\0");

const parseStopInput = (value) => {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new InvalidInputError("completion_gate_invalid_input");
  }
  for (const field of ["conversationId", "transcriptPath", "artifactDirectoryPath", "modelName", "terminationReason", "error"]) {
    if (!validString(value[field])) throw new InvalidInputError("completion_gate_invalid_input");
  }
  if (!Array.isArray(value.workspacePaths)
    || value.workspacePaths.length === 0
    || value.workspacePaths.length > COMPLETION_GATE_LIMITS.maximumWorkspacePaths
    || value.workspacePaths.some((workspace) => !validString(workspace) || !path.isAbsolute(workspace))) {
    throw new InvalidInputError("completion_gate_invalid_input");
  }
  if (!Number.isSafeInteger(value.executionNum) || value.executionNum < 0 || typeof value.fullyIdle !== "boolean") {
    throw new InvalidInputError("completion_gate_invalid_input");
  }
  return value;
};

const readStdin = async (stream) => {
  const chunks = [];
  let size = 0;
  for await (const chunk of stream) {
    size += chunk.length;
    if (size > COMPLETION_GATE_LIMITS.maximumInputBytes) {
      throw new InvalidInputError("completion_gate_invalid_input");
    }
    chunks.push(chunk);
  }
  try {
    return parseStopInput(JSON.parse(Buffer.concat(chunks).toString("utf8")));
  } catch (error) {
    if (error instanceof InvalidInputError) throw error;
    throw new InvalidInputError("completion_gate_invalid_input");
  }
};

const openDirectory = async (directory, expectedIdentity = undefined) => {
  let handle;
  try {
    handle = await fs.open(
      directory,
      fsConstants.O_RDONLY | fsConstants.O_DIRECTORY | fsConstants.O_NOFOLLOW,
    );
    const status = await handle.stat({ bigint: true });
    if (!status.isDirectory()
      || (expectedIdentity !== undefined
        && (status.dev !== expectedIdentity.device || status.ino !== expectedIdentity.inode))) {
      failOpen("state_path_escape");
    }
    for (const descriptorRoot of ["/proc/self/fd", "/dev/fd"]) {
      const anchored = path.join(descriptorRoot, String(handle.fd));
      try {
        const anchoredStatus = await fs.stat(anchored, { bigint: true });
        if (anchoredStatus.isDirectory() && anchoredStatus.dev === status.dev && anchoredStatus.ino === status.ino) {
          return { directory: anchored, handle };
        }
      } catch (error) {
        if (!['ENOENT', 'ENOTDIR'].includes(error?.code)) throw error;
      }
    }
    failOpen("directory_anchor_unsupported");
  } catch (error) {
    if (handle) await handle.close().catch(() => {});
    if (["ELOOP", "ENOTDIR"].includes(error?.code)) failOpen("state_path_escape");
    throw error;
  }
};

const closeDirectory = async (anchor) => {
  if (anchor) await anchor.handle.close().catch(() => {});
};

const openChildDirectory = async (parent, child, { allowMissing = false } = {}) => {
  try {
    return await openDirectory(path.join(parent.directory, child));
  } catch (error) {
    if (allowMissing && error?.code === "ENOENT") return null;
    if (["ELOOP", "ENOTDIR"].includes(error?.code)) failOpen("state_path_escape");
    throw error;
  }
};

const readAnchoredFile = async (directory, leaf, { allowMissing = false, maximumBytes, reasonCode }) => {
  const file = path.join(directory.directory, leaf);
  let handle;
  try {
    const initial = await fs.lstat(file);
    if (initial.isSymbolicLink() || !initial.isFile()) failOpen("state_path_escape");
    handle = await fs.open(file, fsConstants.O_RDONLY | fsConstants.O_NOFOLLOW);
    const status = await handle.stat();
    if (!status.isFile()) failOpen("state_path_escape");
    if (status.size > maximumBytes) failOpen(reasonCode);
    return await handle.readFile();
  } catch (error) {
    if (allowMissing && error?.code === "ENOENT") return null;
    if (["ELOOP", "ENOTDIR"].includes(error?.code)) failOpen("state_path_escape");
    if (error?.code === "ENOENT") failOpen(reasonCode);
    throw error;
  } finally {
    if (handle) await handle.close().catch(() => {});
  }
};

const identityEnvelope = (state, taskId) => state !== null
  && typeof state === "object"
  && !Array.isArray(state)
  && state.taskId === taskId
  && DIGEST_PATTERN.test(state.workspaceDigest)
  && DIGEST_PATTERN.test(state.requestDigest)
  && state.workflowTier === "substantial";

const parseJson = (bytes) => {
  try {
    return JSON.parse(bytes.toString("utf8"));
  } catch {
    return undefined;
  }
};

const inspectCandidate = (stateBytes, taskId) => {
  const raw = parseJson(stateBytes);
  if (!identityEnvelope(raw, taskId)) {
    if (raw && raw.workflowTier === "substantial") failOpen("task_state_foreign");
    if (raw === undefined) failOpen("task_state_invalid_unbound");
    try {
      parseTaskState(raw, { taskId });
    } catch {
      failOpen("task_state_invalid_unbound");
    }
    return null;
  }
  try {
    const state = parseTaskState(raw, { taskId });
    return { taskId, raw, state, stateBytes, invalid: false };
  } catch {
    return { taskId, raw, state: null, stateBytes, invalid: true };
  }
};

const discoverTask = async (workspacePaths) => {
  const candidates = [];
  const roots = [];
  try {
    for (const workspacePath of workspacePaths) {
      let canonicalRoot;
      let status;
      try {
        canonicalRoot = await fs.realpath(workspacePath);
        status = await fs.lstat(canonicalRoot, { bigint: true });
      } catch {
        failOpen("workspace_invalid");
      }
      if (!status.isDirectory() || status.isSymbolicLink()) failOpen("workspace_invalid");
      if (roots.includes(canonicalRoot)) continue;
      roots.push(canonicalRoot);

      let rootAnchor;
      let agentsAnchor;
      let abeAnchor;
      try {
        rootAnchor = await openDirectory(canonicalRoot, { device: status.dev, inode: status.ino });
        agentsAnchor = await openChildDirectory(rootAnchor, ".agents", { allowMissing: true });
        if (agentsAnchor === null) continue;
        abeAnchor = await openChildDirectory(agentsAnchor, "abe", { allowMissing: true });
        if (abeAnchor === null) continue;
        const entries = await fs.readdir(abeAnchor.directory, { withFileTypes: true });
        if (entries.length > COMPLETION_GATE_LIMITS.maximumTaskDirectories) failOpen("task_state_limit");
        for (const entry of entries) {
          if (!entry.isDirectory() || entry.name.startsWith(".")) continue;
          if (!TASK_ID_PATTERN.test(entry.name)) failOpen("task_state_foreign");
          let taskAnchor;
          let retained = false;
          try {
            taskAnchor = await openChildDirectory(abeAnchor, entry.name);
            const stateBytes = await readAnchoredFile(taskAnchor, "state.json", {
              maximumBytes: COMPLETION_GATE_LIMITS.maximumStateBytes,
              reasonCode: "task_state_invalid_unbound",
            });
            const candidate = inspectCandidate(stateBytes, entry.name);
            if (candidate !== null) {
              candidates.push({ ...candidate, root: canonicalRoot, taskAnchor });
              retained = true;
            }
          } finally {
            if (!retained) await closeDirectory(taskAnchor);
          }
        }
      } finally {
        await closeDirectory(abeAnchor);
        await closeDirectory(agentsAnchor);
        await closeDirectory(rootAnchor);
      }
    }
  } catch (error) {
    await Promise.all(candidates.map((candidate) => candidate.taskAnchor.handle.close().catch(() => {})));
    throw error;
  }
  if (candidates.length === 0) return null;
  if (candidates.length !== 1) {
    await Promise.all(candidates.map((candidate) => candidate.taskAnchor.handle.close().catch(() => {})));
    failOpen("task_state_ambiguous");
  }
  return candidates[0];
};

const staleObligationIds = (raw) => Array.isArray(raw?.obligations)
  ? raw.obligations
    .filter((obligation) => obligation?.required === true
      && obligation.status === "passing"
      && DIGEST_PATTERN.test(obligation.lastRelevantChangeDigest)
      && (!Array.isArray(obligation.evidence)
        || !obligation.evidence.some((evidence) => evidence?.result === "pass"
          && evidence.afterChangeDigest === obligation.lastRelevantChangeDigest)))
    .map((obligation) => obligation.id)
    .filter(validString)
    .sort()
  : [];

const mechanicalCondition = (candidate) => {
  const staleIds = staleObligationIds(candidate.raw);
  if (staleIds.length > 0) {
    return {
      reasonCode: "stale_passing_evidence",
      reason: `Completion evidence is stale for required obligation(s) ${staleIds.join(", ")}. ${immediateHonestReport}`,
    };
  }
  if (candidate.invalid) {
    return {
      reasonCode: "invalid_task_state",
      reason: `TaskState schema is invalid for ${candidate.taskId}. ${immediateHonestReport}`,
    };
  }
  const state = candidate.state;
  if (state.terminalState.activeWork) {
    return {
      reasonCode: "active_work",
      reason: `TaskState reports active work. ${immediateHonestReport}`,
    };
  }
  const unresolvedIds = state.obligations
    .filter((obligation) => obligation.required && obligation.status !== "passing")
    .map((obligation) => obligation.id)
    .sort();
  if (unresolvedIds.length > 0) {
    return {
      reasonCode: "unresolved_required_obligation",
      reason: `Required obligation(s) ${unresolvedIds.join(", ")} remain unresolved. ${immediateHonestReport}`,
    };
  }
  const acceptedIds = state.reviewFindings
    .filter((finding) => ["critical", "important"].includes(finding.severity) && finding.status === "accepted")
    .map((finding) => finding.id)
    .sort();
  if (acceptedIds.length > 0) {
    return {
      reasonCode: "accepted_finding_unverified",
      reason: `Accepted material finding(s) ${acceptedIds.join(", ")} are not freshly verified. ${immediateHonestReport}`,
    };
  }
  return null;
};

const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

const acquireLock = async (taskAnchor) => {
  const lockFile = path.join(taskAnchor.directory, ".completion-gate.lock");
  const deadline = Date.now() + COMPLETION_GATE_LIMITS.lockWaitMilliseconds;
  while (true) {
    try {
      const handle = await fs.open(
        lockFile,
        fsConstants.O_CREAT | fsConstants.O_EXCL | fsConstants.O_WRONLY | fsConstants.O_NOFOLLOW,
        0o600,
      );
      await handle.writeFile(String(process.pid) + "\n");
      await handle.sync();
      return { handle, lockFile };
    } catch (error) {
      if (error?.code !== "EEXIST") throw error;
      if (Date.now() >= deadline) failOpen("ledger_locked");
      await delay(3);
    }
  }
};

const releaseLock = async (lock) => {
  if (!lock) return;
  await lock.handle.close().catch(() => {});
  await fs.rm(lock.lockFile, { force: true }).catch(() => {});
};

const readLedger = async (candidate) => {
  const bytes = await readAnchoredFile(candidate.taskAnchor, "completion-gate.ndjson", {
    maximumBytes: COMPLETION_GATE_LIMITS.maximumLedgerBytes,
    reasonCode: "ledger_missing",
  });
  if (bytes.length === 0) failOpen("ledger_empty");
  if (bytes.at(-1) !== 0x0a) failOpen("ledger_malformed");
  let events;
  try {
    events = bytes.toString("utf8").trimEnd().split("\n").map(JSON.parse);
  } catch {
    failOpen("ledger_malformed");
  }
  if (events.length === 0) failOpen("ledger_empty");
  const seenEvents = new Set();
  const seenStops = new Set();
  for (const [index, event] of events.entries()) {
    try {
      parseCompletionGateEvent(event, {
        taskId: candidate.taskId,
        workspaceDigest: candidate.raw.workspaceDigest,
        requestDigest: candidate.raw.requestDigest,
      });
    } catch {
      failOpen("ledger_foreign_or_malformed");
    }
    if (event.frozenBound !== COMPLETION_GATE_LIMITS.frozenBound
      || event.continuationOrdinal !== index
      || (index === 0 && event.eventKind !== "initialized")
      || (index > 0 && event.eventKind !== "continued")) {
      failOpen("ledger_stale");
    }
    const expectedPrevious = index === 0 ? "genesis" : sha256Digest(canonicalBytes(events[index - 1]));
    if (event.previousEventDigest !== expectedPrevious || seenEvents.has(event.eventId)) failOpen("ledger_stale");
    seenEvents.add(event.eventId);
    if (index > 0) {
      if (seenStops.has(event.stopSequenceId)) failOpen("ledger_stale");
      seenStops.add(event.stopSequenceId);
    }
  }
  if (events.length - 1 > COMPLETION_GATE_LIMITS.frozenBound) failOpen("ledger_stale");
  return { bytes, events };
};

const stopSequenceId = (input, candidate) => "stop:" + sha256Digest(canonicalBytes({
  conversationId: input.conversationId,
  executionNum: input.executionNum,
  terminationReason: input.terminationReason,
  error: input.error,
  fullyIdle: input.fullyIdle,
  modelName: input.modelName,
  taskId: candidate.taskId,
  workspaceDigest: candidate.raw.workspaceDigest,
  requestDigest: candidate.raw.requestDigest,
})).slice("sha256:".length, "sha256:".length + 32);

const appendEvent = async (candidate, bytes, event) => {
  const nextBytes = Buffer.concat([bytes, Buffer.from(canonicalLine(event), "utf8")]);
  if (nextBytes.length > COMPLETION_GATE_LIMITS.maximumLedgerBytes) failOpen("ledger_limit");
  const temporaryName = `.completion-gate.${process.pid}.${Date.now()}.tmp`;
  const temporary = path.join(candidate.taskAnchor.directory, temporaryName);
  const ledger = path.join(candidate.taskAnchor.directory, "completion-gate.ndjson");
  let handle;
  try {
    handle = await fs.open(
      temporary,
      fsConstants.O_CREAT | fsConstants.O_EXCL | fsConstants.O_WRONLY | fsConstants.O_NOFOLLOW,
      0o600,
    );
    await handle.writeFile(nextBytes);
    await handle.sync();
    await handle.close();
    handle = null;
    await fs.rename(temporary, ledger);
    await candidate.taskAnchor.handle.sync();
  } catch (error) {
    if (handle) await handle.close().catch(() => {});
    await fs.rm(temporary, { force: true }).catch(() => {});
    throw error;
  }
};

export const evaluateCompletionGate = async ({ input, occurredAt = new Date().toISOString() }) => {
  input = parseStopInput(input);
  if (!input.fullyIdle || input.error.length > 0) {
    return { output: allow, diagnostic: input.fullyIdle ? "stop_has_error" : "stop_not_fully_idle" };
  }
  const candidate = await discoverTask(input.workspacePaths);
  if (candidate === null) return { output: allow, diagnostic: "task_state_missing" };
  let lock;
  try {
    const condition = mechanicalCondition(candidate);
    if (condition === null) return { output: allow };
    lock = await acquireLock(candidate.taskAnchor);
    const lockedStateBytes = await readAnchoredFile(candidate.taskAnchor, "state.json", {
      maximumBytes: COMPLETION_GATE_LIMITS.maximumStateBytes,
      reasonCode: "task_state_stale",
    });
    if (!lockedStateBytes.equals(candidate.stateBytes)) failOpen("task_state_stale");
    const lockedCandidate = inspectCandidate(lockedStateBytes, candidate.taskId);
    if (lockedCandidate === null || mechanicalCondition(lockedCandidate)?.reasonCode !== condition.reasonCode) {
      failOpen("task_state_stale");
    }
    const { bytes, events } = await readLedger(candidate);
    const sequenceId = stopSequenceId(input, candidate);
    if (events.some((event) => event.stopSequenceId === sequenceId)) {
      return { output: { decision: "continue", reason: condition.reason }, diagnostic: "duplicate_stop_delivery" };
    }
    const continuationCount = events.length - 1;
    if (continuationCount >= COMPLETION_GATE_LIMITS.frozenBound) {
      return { output: allow, diagnostic: "retry_bound_reached" };
    }
    const continuationOrdinal = continuationCount + 1;
    const event = {
      schemaVersion: 1,
      eventId: `${candidate.taskId}:continued:${continuationOrdinal}:${sequenceId.slice("stop:".length)}`,
      taskId: candidate.taskId,
      workspaceDigest: candidate.raw.workspaceDigest,
      requestDigest: candidate.raw.requestDigest,
      eventKind: "continued",
      stopSequenceId: sequenceId,
      continuationOrdinal,
      frozenBound: COMPLETION_GATE_LIMITS.frozenBound,
      decision: "continue",
      reasonCode: condition.reasonCode,
      previousEventDigest: sha256Digest(canonicalBytes(events.at(-1))),
      occurredAt,
    };
    parseCompletionGateEvent(event, {
      taskId: candidate.taskId,
      workspaceDigest: candidate.raw.workspaceDigest,
      requestDigest: candidate.raw.requestDigest,
    });
    await appendEvent(candidate, bytes, event);
    return { output: { decision: "continue", reason: condition.reason }, event };
  } finally {
    await releaseLock(lock);
    await candidate.taskAnchor.handle.close().catch(() => {});
  }
};

const run = async () => {
  let input;
  try {
    input = await readStdin(process.stdin);
  } catch (error) {
    process.stderr.write("completion_gate_invalid_input\n");
    process.exitCode = 1;
    return;
  }
  try {
    const result = await evaluateCompletionGate({ input });
    if (result.diagnostic) process.stderr.write(result.diagnostic + "\n");
    process.stdout.write(canonicalLine(result.output));
  } catch (error) {
    const reason = error instanceof FailOpenError ? error.reasonCode : "unexpected_failure";
    process.stderr.write(`completion_gate_fail_open:${reason}\n`);
    process.stdout.write(canonicalLine(allow));
  }
};

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await run();
}
