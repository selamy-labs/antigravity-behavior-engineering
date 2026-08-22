#!/usr/bin/env node
import { createHash, randomUUID } from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const encoder = new TextEncoder();
const DIGEST_PATTERN = /^sha256:[0-9a-f]{64}$/u;
const RFC3339_PATTERN = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-](\d{2}):(\d{2}))$/u;
const INIT_TIME = "1970-01-01T00:00:00Z";
const INITIAL_FROZEN_BOUND = 1;
const UNSUPPORTED_DIRECTORY_SYNC_CODES = new Set(["EISDIR", "EINVAL", "ENOSYS", "ENOTSUP", "EPERM"]);

export const ReasonCodes = Object.freeze({
  NOT_OBJECT: "contract.not_object",
  MISSING_FIELD: "contract.missing_field",
  UNKNOWN_FIELD: "contract.unknown_field",
  UNSUPPORTED_SCHEMA_VERSION: "contract.unsupported_schema_version",
  INVALID_FIELD: "contract.invalid_field",
  INVALID_NUMBER: "contract.invalid_number",
  INVALID_PATH: "contract.invalid_path",
  DUPLICATE_ID: "contract.duplicate_id",
  INVALID_CONTEXT: "contract.invalid_context",
  FOREIGN_IDENTITY: "contract.foreign_identity",
  TERMINAL_INCONSISTENT: "task_state.terminal_inconsistent",
  STALE_EVIDENCE: "task_state.stale_evidence",
  INVALID_GATE_EVENT: "completion_gate.invalid_event",
});

export class EvidenceCliError extends TypeError {
  constructor(reasonCode, fieldPath = "$") {
    super(reasonCode + " at " + fieldPath);
    this.name = "EvidenceCliError";
    this.reasonCode = reasonCode;
    this.path = fieldPath;
  }
}

const fail = (reasonCode, fieldPath = "$") => {
  throw new EvidenceCliError(reasonCode, fieldPath);
};

const assertWellFormedUnicode = (value, fieldPath) => {
  for (let index = 0; index < value.length; index += 1) {
    const codeUnit = value.charCodeAt(index);
    if (codeUnit >= 0xd800 && codeUnit <= 0xdbff) {
      const next = value.charCodeAt(index + 1);
      if (!Number.isInteger(next) || next < 0xdc00 || next > 0xdfff) {
        fail(ReasonCodes.INVALID_FIELD, fieldPath);
      }
      index += 1;
    } else if (codeUnit >= 0xdc00 && codeUnit <= 0xdfff) {
      fail(ReasonCodes.INVALID_FIELD, fieldPath);
    }
  }
};

const isPlainObject = (value) => {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
};

const serialize = (value, ancestors) => {
  if (value === null) {
    return "null";
  }
  if (typeof value === "string") {
    assertWellFormedUnicode(value, "$");
    return JSON.stringify(value);
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value)) {
      fail(ReasonCodes.INVALID_NUMBER, "$");
    }
    return String(value);
  }
  if (Array.isArray(value)) {
    if (ancestors.has(value)) {
      fail(ReasonCodes.INVALID_FIELD, "$");
    }
    for (let index = 0; index < value.length; index += 1) {
      if (!Object.hasOwn(value, index)) {
        fail(ReasonCodes.INVALID_FIELD, "$");
      }
    }
    ancestors.add(value);
    const serialized = "[" + value.map((item) => serialize(item, ancestors)).join(",") + "]";
    ancestors.delete(value);
    return serialized;
  }
  if (isPlainObject(value)) {
    if (ancestors.has(value)) {
      fail(ReasonCodes.INVALID_FIELD, "$");
    }
    ancestors.add(value);
    const keys = Object.keys(value).sort();
    const serialized = "{" + keys.map((key) => {
      assertWellFormedUnicode(key, "$");
      return JSON.stringify(key) + ":" + serialize(value[key], ancestors);
    }).join(",") + "}";
    ancestors.delete(value);
    return serialized;
  }
  fail(ReasonCodes.INVALID_FIELD, "$");
};

export const canonicalBytes = (value) => encoder.encode(serialize(value, new WeakSet()));

export const sha256Digest = (bytes) => {
  if (!(bytes instanceof Uint8Array)) {
    fail(ReasonCodes.INVALID_FIELD, "$.bytes");
  }
  return "sha256:" + createHash("sha256").update(bytes).digest("hex");
};

const canonicalLine = (value) => Buffer.from(canonicalBytes(value)).toString("utf8") + "\n";

const object = (value, allowed, required, fieldPath) => {
  if (!isPlainObject(value)) {
    fail(ReasonCodes.NOT_OBJECT, fieldPath);
  }
  for (const key of Object.keys(value)) {
    if (!allowed.includes(key)) {
      fail(ReasonCodes.UNKNOWN_FIELD, fieldPath + "." + key);
    }
  }
  for (const key of required) {
    if (!Object.hasOwn(value, key)) {
      fail(ReasonCodes.MISSING_FIELD, fieldPath + "." + key);
    }
  }
  return value;
};

const versioned = (value, fields, fieldPath, optional = []) => {
  object(value, ["schemaVersion", ...fields], ["schemaVersion", ...fields.filter((field) => !optional.includes(field))], fieldPath);
  if (value.schemaVersion !== 1) {
    fail(ReasonCodes.UNSUPPORTED_SCHEMA_VERSION, fieldPath + ".schemaVersion");
  }
  return value;
};

const string = (value, fieldPath, { nonempty = true, noNul = true } = {}) => {
  if (
    typeof value !== "string"
    || (nonempty && value.length === 0)
    || (noNul && value.includes("\u0000"))
  ) {
    fail(ReasonCodes.INVALID_FIELD, fieldPath);
  }
  assertWellFormedUnicode(value, fieldPath);
};

const boolean = (value, fieldPath) => {
  if (typeof value !== "boolean") {
    fail(ReasonCodes.INVALID_FIELD, fieldPath);
  }
};

const integer = (value, fieldPath, minimum = 0) => {
  if (!Number.isSafeInteger(value) || value < minimum) {
    fail(ReasonCodes.INVALID_NUMBER, fieldPath);
  }
};

const array = (value, fieldPath, { nonempty = false } = {}) => {
  if (!Array.isArray(value) || (nonempty && value.length === 0)) {
    fail(ReasonCodes.INVALID_FIELD, fieldPath);
  }
};

const oneOf = (value, values, fieldPath, reasonCode = ReasonCodes.INVALID_FIELD) => {
  if (!values.includes(value)) {
    fail(reasonCode, fieldPath);
  }
};

const digest = (value, fieldPath) => {
  if (typeof value !== "string" || !DIGEST_PATTERN.test(value)) {
    fail(ReasonCodes.INVALID_FIELD, fieldPath);
  }
};

const timestamp = (value, fieldPath) => {
  const match = typeof value === "string" ? value.match(RFC3339_PATTERN) : null;
  if (match === null) {
    fail(ReasonCodes.INVALID_FIELD, fieldPath);
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const second = Number(match[6]);
  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const daysInMonth = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  const offsetHour = match[8] === undefined ? 0 : Number(match[8]);
  const offsetMinute = match[9] === undefined ? 0 : Number(match[9]);
  if (
    month < 1
    || month > 12
    || day < 1
    || day > daysInMonth[month - 1]
    || hour > 23
    || minute > 59
    || second > 59
    || offsetHour > 23
    || offsetMinute > 59
    || Number.isNaN(Date.parse(value))
  ) {
    fail(ReasonCodes.INVALID_FIELD, fieldPath);
  }
};

const relativePathValue = (value, fieldPath, allowDot = false) => {
  if (allowDot && value === ".") {
    return;
  }
  string(value, fieldPath, { noNul: false });
  if (
    value.startsWith("/")
    || /^[A-Za-z]:/u.test(value)
    || value.includes("\u0000")
    || value.includes("\\")
    || value.split("/").some((segment) => segment === "" || segment === "." || segment === "..")
  ) {
    fail(ReasonCodes.INVALID_PATH, fieldPath);
  }
};

const cloneJson = (value) => JSON.parse(Buffer.from(canonicalBytes(value)).toString("utf8"));

const validateContext = (context, allowed, fieldPath) => {
  if (context === undefined) {
    return {};
  }
  context = cloneJson(context);
  if (!isPlainObject(context)) {
    fail(ReasonCodes.INVALID_CONTEXT, fieldPath);
  }
  for (const key of Object.keys(context)) {
    if (!allowed.includes(key)) {
      fail(ReasonCodes.INVALID_CONTEXT, fieldPath + "." + key);
    }
  }
  return context;
};

const strings = (value, fieldPath, options = {}) => {
  array(value, fieldPath, options);
  value.forEach((item, index) => string(item, fieldPath + "[" + index + "]"));
};

const unique = (values, key, fieldPath) => {
  const seen = new Set();
  for (const value of values) {
    const identity = key(value);
    if (seen.has(identity)) {
      fail(ReasonCodes.DUPLICATE_ID, fieldPath);
    }
    seen.add(identity);
  }
};

const validateEvidenceReference = (value, fieldPath) => {
  versioned(value, ["kind", "locator", "digest", "observedAt", "afterChangeDigest", "result"], fieldPath, ["digest"]);
  oneOf(value.kind, ["test", "command", "artifact", "diff", "review", "observation"], fieldPath + ".kind");
  relativePathValue(value.locator, fieldPath + ".locator");
  if (Object.hasOwn(value, "digest")) {
    digest(value.digest, fieldPath + ".digest");
  }
  timestamp(value.observedAt, fieldPath + ".observedAt");
  if (value.afterChangeDigest !== "none") {
    digest(value.afterChangeDigest, fieldPath + ".afterChangeDigest");
  }
  oneOf(value.result, ["pass", "fail", "indeterminate"], fieldPath + ".result");
};

const validateAssumption = (value, fieldPath) => {
  versioned(value, ["id", "question", "disposition", "decision", "evidence", "reversible", "material"], fieldPath, ["decision"]);
  string(value.id, fieldPath + ".id");
  string(value.question, fieldPath + ".question");
  oneOf(value.disposition, ["user_direction", "safe_default", "bounded_out", "needs_input"], fieldPath + ".disposition");
  if (value.disposition === "needs_input") {
    if (Object.hasOwn(value, "decision")) {
      fail(ReasonCodes.INVALID_FIELD, fieldPath + ".decision");
    }
  } else {
    string(value.decision, fieldPath + ".decision");
  }
  array(value.evidence, fieldPath + ".evidence");
  value.evidence.forEach((item, index) => validateEvidenceReference(item, fieldPath + ".evidence[" + index + "]"));
  if (value.disposition !== "user_direction" && value.evidence.length === 0) {
    fail(ReasonCodes.INVALID_FIELD, fieldPath + ".evidence");
  }
  boolean(value.reversible, fieldPath + ".reversible");
  boolean(value.material, fieldPath + ".material");
  if (value.disposition === "safe_default" && !value.reversible) {
    fail(ReasonCodes.INVALID_FIELD, fieldPath + ".reversible");
  }
};

const validateProofObligation = (value, fieldPath) => {
  versioned(
    value,
    ["id", "requirement", "evidenceSeam", "negativeCases", "authority", "required", "status", "evidence", "lastRelevantChangeDigest"],
    fieldPath,
  );
  for (const field of ["id", "requirement", "evidenceSeam", "authority"]) {
    string(value[field], fieldPath + "." + field);
  }
  strings(value.negativeCases, fieldPath + ".negativeCases");
  boolean(value.required, fieldPath + ".required");
  oneOf(value.status, ["pending", "passing", "failing", "blocked", "indeterminate", "not_applicable"], fieldPath + ".status");
  array(value.evidence, fieldPath + ".evidence");
  value.evidence.forEach((item, index) => validateEvidenceReference(item, fieldPath + ".evidence[" + index + "]"));
  if (value.lastRelevantChangeDigest !== "none") {
    digest(value.lastRelevantChangeDigest, fieldPath + ".lastRelevantChangeDigest");
  }
  if (
    value.status === "passing"
    && (
      value.lastRelevantChangeDigest === "none"
      || !value.evidence.some((item) => item.result === "pass" && item.afterChangeDigest === value.lastRelevantChangeDigest)
    )
  ) {
    fail(ReasonCodes.STALE_EVIDENCE, fieldPath + ".evidence");
  }
};

const validateIteration = (value, fieldPath) => {
  versioned(
    value,
    ["sequence", "scope", "changeDigest", "impactedObligationIds", "impactedEvidenceIds", "sentinelEvidenceIds", "result", "nextAction"],
    fieldPath,
  );
  integer(value.sequence, fieldPath + ".sequence", 1);
  string(value.scope, fieldPath + ".scope");
  digest(value.changeDigest, fieldPath + ".changeDigest");
  strings(value.impactedObligationIds, fieldPath + ".impactedObligationIds", { nonempty: true });
  unique(value.impactedObligationIds, (item) => item, fieldPath + ".impactedObligationIds");
  strings(value.impactedEvidenceIds, fieldPath + ".impactedEvidenceIds");
  unique(value.impactedEvidenceIds, (item) => item, fieldPath + ".impactedEvidenceIds");
  strings(value.sentinelEvidenceIds, fieldPath + ".sentinelEvidenceIds");
  unique(value.sentinelEvidenceIds, (item) => item, fieldPath + ".sentinelEvidenceIds");
  oneOf(value.result, ["passing", "failing", "blocked", "indeterminate"], fieldPath + ".result");
  string(value.nextAction, fieldPath + ".nextAction", { nonempty: false });
  if (value.result === "passing" && value.impactedEvidenceIds.length === 0) {
    fail(ReasonCodes.INVALID_FIELD, fieldPath + ".impactedEvidenceIds");
  }
  if (value.sentinelEvidenceIds.length === 0 && value.nextAction.length === 0) {
    fail(ReasonCodes.INVALID_FIELD, fieldPath + ".nextAction");
  }
};

const validateTaskReviewFinding = (value, fieldPath) => {
  versioned(
    value,
    ["id", "reviewerRole", "severity", "claim", "evidence", "status", "dispositionReason", "repairChangeDigest", "verificationEvidenceIds"],
    fieldPath,
  );
  string(value.id, fieldPath + ".id");
  oneOf(value.reviewerRole, ["requirements", "quality"], fieldPath + ".reviewerRole");
  oneOf(value.severity, ["critical", "important", "minor"], fieldPath + ".severity");
  string(value.claim, fieldPath + ".claim");
  array(value.evidence, fieldPath + ".evidence", { nonempty: true });
  value.evidence.forEach((item, index) => validateEvidenceReference(item, fieldPath + ".evidence[" + index + "]"));
  oneOf(value.status, ["open", "accepted", "rejected", "repaired", "verified"], fieldPath + ".status");
  string(value.dispositionReason, fieldPath + ".dispositionReason", { nonempty: false });
  if (["rejected", "repaired", "verified"].includes(value.status) && value.dispositionReason.length === 0) {
    fail(ReasonCodes.INVALID_FIELD, fieldPath + ".dispositionReason");
  }
  if (value.repairChangeDigest !== "none") {
    digest(value.repairChangeDigest, fieldPath + ".repairChangeDigest");
  }
  if (["repaired", "verified"].includes(value.status) && value.repairChangeDigest === "none") {
    fail(ReasonCodes.INVALID_FIELD, fieldPath + ".repairChangeDigest");
  }
  strings(value.verificationEvidenceIds, fieldPath + ".verificationEvidenceIds");
  unique(value.verificationEvidenceIds, (item) => item, fieldPath + ".verificationEvidenceIds");
  if (value.status === "verified" && value.verificationEvidenceIds.length === 0) {
    fail(ReasonCodes.INVALID_FIELD, fieldPath + ".verificationEvidenceIds");
  }
};

const validateTerminalState = (value, fieldPath) => {
  versioned(value, ["declared", "reason", "unresolvedObligationIds", "activeWork"], fieldPath);
  oneOf(value.declared, ["complete", "incomplete", "blocked", "failed", "indeterminate", "needs_input"], fieldPath + ".declared");
  string(value.reason, fieldPath + ".reason");
  strings(value.unresolvedObligationIds, fieldPath + ".unresolvedObligationIds");
  unique(value.unresolvedObligationIds, (item) => item, fieldPath + ".unresolvedObligationIds");
  boolean(value.activeWork, fieldPath + ".activeWork");
};

export const parseTaskState = (value, context = {}) => {
  value = cloneJson(value);
  versioned(
    value,
    ["taskId", "workspaceDigest", "requestDigest", "workflowTier", "intent", "assumptions", "obligations", "iterations", "reviewFindings", "terminalState", "updatedAt"],
    "$",
  );
  string(value.taskId, "$.taskId");
  digest(value.workspaceDigest, "$.workspaceDigest");
  digest(value.requestDigest, "$.requestDigest");
  oneOf(value.workflowTier, ["trivial", "substantial"], "$.workflowTier");
  string(value.intent, "$.intent");
  array(value.assumptions, "$.assumptions");
  value.assumptions.forEach((item, index) => validateAssumption(item, "$.assumptions[" + index + "]"));
  unique(value.assumptions, (item) => item.id, "$.assumptions");
  array(value.obligations, "$.obligations", { nonempty: value.workflowTier === "substantial" });
  value.obligations.forEach((item, index) => validateProofObligation(item, "$.obligations[" + index + "]"));
  unique(value.obligations, (item) => item.id, "$.obligations");
  array(value.iterations, "$.iterations");
  value.iterations.forEach((item, index) => {
    validateIteration(item, "$.iterations[" + index + "]");
    if (index > 0 && item.sequence <= value.iterations[index - 1].sequence) {
      fail(ReasonCodes.INVALID_FIELD, "$.iterations[" + index + "].sequence");
    }
  });
  array(value.reviewFindings, "$.reviewFindings");
  value.reviewFindings.forEach((item, index) => validateTaskReviewFinding(item, "$.reviewFindings[" + index + "]"));
  unique(value.reviewFindings, (item) => item.id, "$.reviewFindings");
  validateTerminalState(value.terminalState, "$.terminalState");
  timestamp(value.updatedAt, "$.updatedAt");

  const unresolved = value.obligations
    .filter((item) => item.required && item.status !== "passing")
    .map((item) => item.id)
    .sort();
  const declaredUnresolved = [...value.terminalState.unresolvedObligationIds].sort();
  if (
    unresolved.length !== declaredUnresolved.length
    || unresolved.some((item, index) => item !== declaredUnresolved[index])
  ) {
    fail(ReasonCodes.TERMINAL_INCONSISTENT, "$.terminalState.unresolvedObligationIds");
  }
  if (value.terminalState.declared === "complete") {
    if (value.terminalState.activeWork || unresolved.length > 0) {
      fail(ReasonCodes.TERMINAL_INCONSISTENT, "$.terminalState");
    }
    if (value.reviewFindings.some((item) => ["critical", "important"].includes(item.severity) && !["rejected", "verified"].includes(item.status))) {
      fail(ReasonCodes.TERMINAL_INCONSISTENT, "$.reviewFindings");
    }
  }

  context = validateContext(context, ["taskId", "workspaceDigest", "requestDigest"], "$context");
  if (context.taskId !== undefined && value.taskId !== context.taskId) {
    fail(ReasonCodes.FOREIGN_IDENTITY, "$context.taskId");
  }
  if (context.workspaceDigest !== undefined && value.workspaceDigest !== context.workspaceDigest) {
    fail(ReasonCodes.FOREIGN_IDENTITY, "$context.workspaceDigest");
  }
  if (context.requestDigest !== undefined && value.requestDigest !== context.requestDigest) {
    fail(ReasonCodes.FOREIGN_IDENTITY, "$context.requestDigest");
  }
  return value;
};

export const parseCompletionGateEvent = (value, context = {}) => {
  value = cloneJson(value);
  versioned(
    value,
    ["eventId", "taskId", "workspaceDigest", "requestDigest", "eventKind", "stopSequenceId", "continuationOrdinal", "frozenBound", "decision", "reasonCode", "previousEventDigest", "occurredAt"],
    "$",
  );
  string(value.eventId, "$.eventId");
  string(value.taskId, "$.taskId");
  digest(value.workspaceDigest, "$.workspaceDigest");
  digest(value.requestDigest, "$.requestDigest");
  oneOf(value.eventKind, ["initialized", "continued"], "$.eventKind");
  if (value.stopSequenceId !== "not_applicable") {
    string(value.stopSequenceId, "$.stopSequenceId");
  }
  integer(value.continuationOrdinal, "$.continuationOrdinal");
  integer(value.frozenBound, "$.frozenBound");
  oneOf(value.decision, ["none", "continue"], "$.decision");
  oneOf(value.reasonCode, [
    "task_state_initialized",
    "active_work",
    "invalid_task_state",
    "unresolved_required_obligation",
    "stale_passing_evidence",
    "accepted_finding_unverified",
    "retry_bound_reached",
  ], "$.reasonCode");
  if (value.previousEventDigest !== "genesis") {
    digest(value.previousEventDigest, "$.previousEventDigest");
  }
  timestamp(value.occurredAt, "$.occurredAt");
  const genesis = value.eventKind === "initialized"
    && value.stopSequenceId === "not_applicable"
    && value.continuationOrdinal === 0
    && value.decision === "none"
    && value.reasonCode === "task_state_initialized"
    && value.previousEventDigest === "genesis";
  const continued = value.eventKind === "continued"
    && value.stopSequenceId !== "not_applicable"
    && value.continuationOrdinal > 0
    && value.decision === "continue"
    && value.continuationOrdinal <= value.frozenBound
    && value.reasonCode !== "task_state_initialized"
    && value.reasonCode !== "retry_bound_reached"
    && value.previousEventDigest !== "genesis";
  const boundReached = value.eventKind === "continued"
    && value.stopSequenceId !== "not_applicable"
    && value.continuationOrdinal > value.frozenBound
    && value.decision === "none"
    && value.reasonCode === "retry_bound_reached"
    && value.previousEventDigest !== "genesis";
  if (!genesis && !continued && !boundReached) {
    fail(ReasonCodes.INVALID_GATE_EVENT, "$");
  }
  context = validateContext(context, ["taskId", "workspaceDigest", "requestDigest"], "$context");
  if (context.taskId !== undefined && value.taskId !== context.taskId) {
    fail(ReasonCodes.FOREIGN_IDENTITY, "$context.taskId");
  }
  if (context.workspaceDigest !== undefined && value.workspaceDigest !== context.workspaceDigest) {
    fail(ReasonCodes.FOREIGN_IDENTITY, "$context.workspaceDigest");
  }
  if (context.requestDigest !== undefined && value.requestDigest !== context.requestDigest) {
    fail(ReasonCodes.FOREIGN_IDENTITY, "$context.requestDigest");
  }
  return value;
};

const validateTaskId = (taskId) => {
  if (
    typeof taskId !== "string"
    || taskId.length === 0
    || taskId.includes("\u0000")
    || taskId.includes("/")
    || taskId.includes("\\")
    || taskId === "."
    || taskId === ".."
  ) {
    fail("state.invalid_task_id", "$.taskId");
  }
};

const syncDirectory = async (directory) => {
  let handle;
  try {
    handle = await fs.open(directory, "r");
    await handle.sync();
  } catch (error) {
    if (!error || !UNSUPPORTED_DIRECTORY_SYNC_CODES.has(error.code)) {
      throw error;
    }
  } finally {
    if (handle) {
      await handle.close();
    }
  }
};

const toWorkspaceRelative = (absoluteRoot, absolutePath) => {
  const relative = path.relative(absoluteRoot, absolutePath);
  if (relative === "" || relative.startsWith(".." + path.sep) || path.isAbsolute(relative)) {
    fail("state.path_escape", "$.path");
  }
  return relative.split(path.sep).join("/");
};

const validateRelativeWorkspacePath = (relative, fieldPath) => {
  if (typeof relative !== "string" || relative.length === 0 || path.isAbsolute(relative) || relative.includes("\\") || relative.includes("\u0000")) {
    fail("state.path_escape", fieldPath);
  }
  const segments = relative.split("/");
  if (segments.some((segment) => segment === "" || segment === "." || segment === "..")) {
    fail("state.path_escape", fieldPath);
  }
  return segments;
};

const ensureWorkspaceDirectory = async (root, relative, fieldPath) => {
  const segments = validateRelativeWorkspacePath(relative, fieldPath);
  const canonicalRoot = await fs.realpath(root);
  let current = canonicalRoot;
  for (const segment of segments) {
    current = path.join(current, segment);
    const relativeCurrent = path.relative(canonicalRoot, current);
    if (relativeCurrent.startsWith(".." + path.sep) || path.isAbsolute(relativeCurrent)) {
      fail("state.path_escape", fieldPath);
    }
    try {
      const status = await fs.lstat(current);
      if (status.isSymbolicLink() || !status.isDirectory()) {
        fail("state.path_escape", fieldPath);
      }
    } catch (error) {
      if (error?.code !== "ENOENT") {
        throw error;
      }
      await fs.mkdir(current, { mode: 0o700 });
      const createdStatus = await fs.lstat(current);
      if (createdStatus.isSymbolicLink() || !createdStatus.isDirectory()) {
        fail("state.path_escape", fieldPath);
      }
      await syncDirectory(path.dirname(current));
    }
  }
  return current;
};

const resolveWorkspaceFile = async (root, relative, fieldPath) => {
  const segments = validateRelativeWorkspacePath(relative, fieldPath);
  const canonicalRoot = await fs.realpath(root);
  let current = canonicalRoot;
  for (let index = 0; index < segments.length; index += 1) {
    current = path.join(current, segments[index]);
    const relativeCurrent = path.relative(canonicalRoot, current);
    if (relativeCurrent.startsWith(".." + path.sep) || path.isAbsolute(relativeCurrent)) {
      fail("state.path_escape", fieldPath);
    }
    try {
      const status = await fs.lstat(current);
      if (status.isSymbolicLink()) {
        fail("state.path_escape", fieldPath);
      }
      if (index < segments.length - 1 && !status.isDirectory()) {
        fail("state.path_escape", fieldPath);
      }
    } catch (error) {
      if (error?.code !== "ENOENT") {
        throw error;
      }
      if (index < segments.length - 1) {
        fail("state.path_escape", fieldPath);
      }
    }
  }
  return current;
};

const writeAtomicBytes = async (destination, bytes) => {
  const parent = path.dirname(destination);
  const temporaryPath = path.join(parent, "." + path.basename(destination) + "." + randomUUID() + ".tmp");
  let handle;
  let operationError;
  try {
    handle = await fs.open(temporaryPath, "wx", 0o600);
    await handle.writeFile(bytes);
    await handle.sync();
    await handle.close();
    handle = undefined;
    await fs.rename(temporaryPath, destination);
    await syncDirectory(parent);
  } catch (error) {
    operationError = error;
  }
  if (handle) {
    await handle.close();
  }
  await fs.rm(temporaryPath, { force: true }).catch(() => {});
  if (operationError) {
    throw operationError;
  }
};

export const writeCanonicalAtomic = async (root, relativePath, value) => {
  const segments = validateRelativeWorkspacePath(relativePath, "$.relativePath");
  const canonicalRoot = await fs.realpath(root);
  let parent = canonicalRoot;
  for (const segment of segments.slice(0, -1)) {
    parent = path.join(parent, segment);
    const relativeParent = path.relative(canonicalRoot, parent);
    if (relativeParent.startsWith(".." + path.sep) || path.isAbsolute(relativeParent)) {
      fail("state.path_escape", "$.relativePath");
    }
    try {
      const status = await fs.lstat(parent);
      if (status.isSymbolicLink() || !status.isDirectory()) {
        fail("state.path_escape", "$.relativePath");
      }
    } catch (error) {
      if (error?.code !== "ENOENT") {
        throw error;
      }
      await fs.mkdir(parent);
      await syncDirectory(path.dirname(parent));
    }
  }
  const destination = path.join(parent, segments.at(-1));
  try {
    if ((await fs.lstat(destination)).isSymbolicLink()) {
      fail("state.path_escape", "$.relativePath");
    }
  } catch (error) {
    if (error?.code !== "ENOENT") {
      throw error;
    }
  }
  const bytes = canonicalBytes(value);
  await writeAtomicBytes(destination, bytes);
  return sha256Digest(bytes);
};

const initialState = ({ taskId, workspaceDigest, requestDigest }) => ({
  schemaVersion: 1,
  taskId,
  workspaceDigest,
  requestDigest,
  workflowTier: "trivial",
  intent: "TaskState initialized; apply an approved or bounded substantial-task patch before implementation.",
  assumptions: [],
  obligations: [],
  iterations: [],
  reviewFindings: [],
  terminalState: {
    schemaVersion: 1,
    declared: "needs_input",
    reason: "Approved or bounded intent and proof obligations are not recorded yet.",
    unresolvedObligationIds: [],
    activeWork: false,
  },
  updatedAt: INIT_TIME,
});

const genesisEvent = ({ taskId, workspaceDigest, requestDigest }) => ({
  schemaVersion: 1,
  eventId: taskId + ":initialized:0",
  taskId,
  workspaceDigest,
  requestDigest,
  eventKind: "initialized",
  stopSequenceId: "not_applicable",
  continuationOrdinal: 0,
  frozenBound: INITIAL_FROZEN_BOUND,
  decision: "none",
  reasonCode: "task_state_initialized",
  previousEventDigest: "genesis",
  occurredAt: INIT_TIME,
});

export const initializeTaskState = async ({ root = process.cwd(), taskId, workspaceDigest, requestDigest }) => {
  validateTaskId(taskId);
  digest(workspaceDigest, "$.workspaceDigest");
  digest(requestDigest, "$.requestDigest");
  const state = initialState({ taskId, workspaceDigest, requestDigest });
  const event = genesisEvent({ taskId, workspaceDigest, requestDigest });
  parseTaskState(state, { taskId, workspaceDigest, requestDigest });
  parseCompletionGateEvent(event, { taskId, workspaceDigest, requestDigest });

  const canonicalRoot = await fs.realpath(root);
  const abeRoot = await ensureWorkspaceDirectory(canonicalRoot, ".agents/abe", "$.stateRoot");
  const destination = path.join(abeRoot, taskId);
  try {
    await fs.lstat(destination);
    fail("state.init_exists", "$.taskId");
  } catch (error) {
    if (error?.code !== "ENOENT") {
      throw error;
    }
  }

  const temporary = path.join(abeRoot, "." + taskId + "." + randomUUID() + ".tmp");
  let operationError;
  try {
    await fs.mkdir(temporary, { mode: 0o700 });
    await writeAtomicBytes(path.join(temporary, "state.json"), canonicalBytes(state));
    await writeAtomicBytes(path.join(temporary, "completion-gate.ndjson"), encoder.encode(canonicalLine(event)));
    await syncDirectory(temporary);
    await fs.rename(temporary, destination);
    await syncDirectory(abeRoot);
  } catch (error) {
    operationError = error;
  }
  if (operationError) {
    await fs.rm(temporary, { recursive: true, force: true }).catch(() => {});
    throw operationError;
  }

  const stateDigest = sha256Digest(canonicalBytes(state));
  const ledgerDigest = sha256Digest(encoder.encode(canonicalLine(event)));
  return {
    ok: true,
    reasonCode: "initialized",
    stateFile: toWorkspaceRelative(canonicalRoot, path.join(destination, "state.json")),
    ledgerFile: toWorkspaceRelative(canonicalRoot, path.join(destination, "completion-gate.ndjson")),
    stateDigest,
    ledgerDigest,
  };
};

const readJsonFile = async (file, reasonCode) => {
  let source;
  try {
    source = await fs.readFile(file, "utf8");
  } catch (error) {
    if (error?.code === "ENOENT") {
      fail("state.file_not_found", "$.path");
    }
    throw error;
  }
  try {
    return JSON.parse(source);
  } catch {
    fail(reasonCode, "$.json");
  }
};

const contextFromStatePath = (relativeStateFile, explicit = {}) => {
  const segments = validateRelativeWorkspacePath(relativeStateFile, "$.stateFile");
  const fileName = segments.at(-1);
  if (fileName !== "state.json") {
    return explicit;
  }
  const inferredTaskId = segments.at(-2);
  if (inferredTaskId === undefined) {
    return explicit;
  }
  return { taskId: inferredTaskId, ...explicit };
};

export const validateTaskStateFile = async ({
  root = process.cwd(),
  stateFile,
  taskId,
  workspaceDigest,
  requestDigest,
} = {}) => {
  const file = await resolveWorkspaceFile(root, stateFile, "$.stateFile");
  const state = await readJsonFile(file, "state.invalid_json");
  const context = contextFromStatePath(stateFile, {
    ...(taskId === undefined ? {} : { taskId }),
    ...(workspaceDigest === undefined ? {} : { workspaceDigest }),
    ...(requestDigest === undefined ? {} : { requestDigest }),
  });
  parseTaskState(state, context);
  return {
    ok: true,
    reasonCode: "valid",
    stateDigest: sha256Digest(await fs.readFile(file)),
  };
};

export const showTaskStateFile = async (options) => {
  const file = await resolveWorkspaceFile(options.root ?? process.cwd(), options.stateFile, "$.stateFile");
  const state = await readJsonFile(file, "state.invalid_json");
  const context = contextFromStatePath(options.stateFile, {
    ...(options.taskId === undefined ? {} : { taskId: options.taskId }),
    ...(options.workspaceDigest === undefined ? {} : { workspaceDigest: options.workspaceDigest }),
    ...(options.requestDigest === undefined ? {} : { requestDigest: options.requestDigest }),
  });
  parseTaskState(state, context);
  return state;
};

const validatePatch = (value) => {
  versioned(value, ["taskId", "workspaceDigest", "requestDigest", "baseStateDigest", "updatedAt", "operations"], "$");
  validateTaskId(value.taskId);
  digest(value.workspaceDigest, "$.workspaceDigest");
  digest(value.requestDigest, "$.requestDigest");
  digest(value.baseStateDigest, "$.baseStateDigest");
  timestamp(value.updatedAt, "$.updatedAt");
  array(value.operations, "$.operations");
  for (const [index, operation] of value.operations.entries()) {
    versioned(operation, ["op", "value"], "$.operations[" + index + "]");
    oneOf(operation.op, [
      "setWorkflowTier",
      "setIntent",
      "appendAssumption",
      "appendObligation",
      "appendIteration",
      "appendReviewFinding",
      "setTerminalState",
    ], "$.operations[" + index + "].op", "state.patch_unknown_operation");
  }
  return value;
};

const applyOperation = (state, operation) => {
  if (operation.op === "setWorkflowTier") {
    oneOf(operation.value, ["trivial", "substantial"], "$.operations.value");
    state.workflowTier = operation.value;
  } else if (operation.op === "setIntent") {
    string(operation.value, "$.operations.value");
    state.intent = operation.value;
  } else if (operation.op === "appendAssumption") {
    state.assumptions.push(operation.value);
  } else if (operation.op === "appendObligation") {
    state.obligations.push(operation.value);
  } else if (operation.op === "appendIteration") {
    state.iterations.push(operation.value);
  } else if (operation.op === "appendReviewFinding") {
    state.reviewFindings.push(operation.value);
  } else if (operation.op === "setTerminalState") {
    state.terminalState = operation.value;
  } else {
    fail("state.patch_unknown_operation", "$.operations.op");
  }
};

const withTaskStateLock = async (root, taskId, fn) => {
  const lockFile = await resolveWorkspaceFile(root, ".agents/abe/" + taskId + "/.state.lock", "$.lockFile");
  let handle;
  try {
    handle = await fs.open(lockFile, "wx", 0o600);
    await handle.writeFile(String(process.pid) + "\n");
    await handle.sync();
  } catch (error) {
    if (error?.code === "EEXIST") {
      fail("state.concurrent_update", "$.lockFile");
    }
    throw error;
  }
  try {
    return await fn();
  } finally {
    if (handle) {
      await handle.close();
    }
    await fs.rm(lockFile, { force: true }).catch(() => {});
    await syncDirectory(path.dirname(lockFile)).catch(() => {});
  }
};

export const applyTaskStatePatch = async ({ root = process.cwd(), patchFile }) => {
  const resolvedPatchFile = await resolveWorkspaceFile(root, patchFile, "$.patchFile");
  const patch = validatePatch(await readJsonFile(resolvedPatchFile, "state.invalid_patch_json"));
  return withTaskStateLock(root, patch.taskId, async () => {
    const relativeStatePath = ".agents/abe/" + patch.taskId + "/state.json";
    const resolvedStateFile = await resolveWorkspaceFile(root, relativeStatePath, "$.stateFile");
    const currentBytes = await fs.readFile(resolvedStateFile);
    const currentDigest = sha256Digest(currentBytes);
    if (currentDigest !== patch.baseStateDigest) {
      fail("state.concurrency_conflict", "$.baseStateDigest");
    }
    const current = await readJsonFile(resolvedStateFile, "state.invalid_json");
    parseTaskState(current, {
      taskId: patch.taskId,
      workspaceDigest: patch.workspaceDigest,
      requestDigest: patch.requestDigest,
    });
    const next = cloneJson(current);
    for (const operation of patch.operations) {
      applyOperation(next, operation);
    }
    next.updatedAt = patch.updatedAt;
    parseTaskState(next, {
      taskId: patch.taskId,
      workspaceDigest: patch.workspaceDigest,
      requestDigest: patch.requestDigest,
    });
    const stateDigest = await writeCanonicalAtomic(root, relativeStatePath, next);
    return { ok: true, reasonCode: "applied", stateDigest };
  });
};

const parseOptions = (args, spec) => {
  const options = {};
  for (let index = 0; index < args.length; index += 1) {
    const name = args[index];
    if (!name.startsWith("--")) {
      fail("state.invalid_arguments", "$.argv[" + index + "]");
    }
    const key = name.slice(2);
    if (!spec.includes(key)) {
      fail("state.invalid_arguments", "$.argv[" + index + "]");
    }
    const value = args[index + 1];
    if (value === undefined || value.startsWith("--")) {
      fail("state.invalid_arguments", "$.argv[" + index + "]");
    }
    options[key.replaceAll("-", "_")] = value;
    index += 1;
  }
  for (const key of spec) {
    const normalized = key.replaceAll("-", "_");
    if (options[normalized] === undefined && !["task-id", "workspace-digest", "request-digest"].includes(key)) {
      fail("state.invalid_arguments", "$.argv." + key);
    }
  }
  return options;
};

export const HELP_TEXT = `abe-evidence init --task-id <id> --workspace-digest <sha256> --request-digest <sha256>
abe-evidence apply --patch-file <workspace-relative-json>
abe-evidence validate --state-file <workspace-relative-json> [--task-id <id>] [--workspace-digest <sha256>] [--request-digest <sha256>]
abe-evidence show --state-file <workspace-relative-json> [--task-id <id>] [--workspace-digest <sha256>] [--request-digest <sha256>]

Dependency-free durable evidence mechanics for TaskState and CompletionGateEvent.
No semantic correctness authority; the tool validates, canonicalizes, and writes only.
`;

export const main = async (args = process.argv.slice(2), io = process) => {
  if (args.length === 0 || args[0] === "--help" || args[0] === "-h") {
    io.stdout.write(HELP_TEXT);
    return 0;
  }
  const command = args[0];
  if (command === "init") {
    const options = parseOptions(args.slice(1), ["task-id", "workspace-digest", "request-digest"]);
    io.stdout.write(canonicalLine(await initializeTaskState({
      taskId: options.task_id,
      workspaceDigest: options.workspace_digest,
      requestDigest: options.request_digest,
    })));
    return 0;
  }
  if (command === "apply") {
    const options = parseOptions(args.slice(1), ["patch-file"]);
    io.stdout.write(canonicalLine(await applyTaskStatePatch({ patchFile: options.patch_file })));
    return 0;
  }
  if (command === "validate") {
    const options = parseOptions(args.slice(1), ["state-file", "task-id", "workspace-digest", "request-digest"]);
    io.stdout.write(canonicalLine(await validateTaskStateFile({
      stateFile: options.state_file,
      taskId: options.task_id,
      workspaceDigest: options.workspace_digest,
      requestDigest: options.request_digest,
    })));
    return 0;
  }
  if (command === "show") {
    const options = parseOptions(args.slice(1), ["state-file", "task-id", "workspace-digest", "request-digest"]);
    io.stdout.write(canonicalLine(await showTaskStateFile({
      stateFile: options.state_file,
      taskId: options.task_id,
      workspaceDigest: options.workspace_digest,
      requestDigest: options.request_digest,
    })));
    return 0;
  }
  fail("state.invalid_arguments", "$.argv[0]");
};

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().then((exitCode) => {
    process.exitCode = exitCode;
  }).catch((error) => {
    if (error instanceof EvidenceCliError) {
      process.stderr.write(error.reasonCode + " at " + error.path + "\n");
      process.exitCode = 1;
      return;
    }
    process.stderr.write((error && error.stack) ? error.stack + "\n" : String(error) + "\n");
    process.exitCode = 1;
  });
}
