import { canonicalBytes, sha256Digest } from './canonical-json.mjs';

export const ReasonCodes = Object.freeze({
  NOT_OBJECT: 'contract.not_object',
  MISSING_FIELD: 'contract.missing_field',
  UNKNOWN_FIELD: 'contract.unknown_field',
  UNSUPPORTED_SCHEMA_VERSION: 'contract.unsupported_schema_version',
  INVALID_FIELD: 'contract.invalid_field',
  INVALID_NUMBER: 'contract.invalid_number',
  INVALID_PATH: 'contract.invalid_path',
  DUPLICATE_ID: 'contract.duplicate_id',
  INVALID_CONTEXT: 'contract.invalid_context',
  FOREIGN_IDENTITY: 'contract.foreign_identity',
  TERMINAL_INCONSISTENT: 'task_state.terminal_inconsistent',
  STALE_EVIDENCE: 'task_state.stale_evidence',
  INVALID_GATE_EVENT: 'completion_gate.invalid_event',
  SELF_DIGEST_MISMATCH: 'review.self_digest_mismatch',
  BINDING_MISMATCH: 'review.binding_mismatch',
  INVALID_REVIEW_ROLE: 'review.invalid_role',
  INVALID_REVIEW_VERDICT: 'review.invalid_verdict',
  INVALID_REVIEW_JOIN: 'review.invalid_join',
});

export class ContractValidationError extends TypeError {
  constructor(reasonCode, path = '$') {
    super(reasonCode + ' at ' + path);
    this.name = 'ContractValidationError';
    this.reasonCode = reasonCode;
    this.path = path;
  }
}

const fail = (reasonCode, path) => {
  throw new ContractValidationError(reasonCode, path);
};

const isPlainObject = (value, path = '$') => {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    return false;
  }
  let prototype;
  try {
    prototype = Object.getPrototypeOf(value);
  } catch {
    fail(ReasonCodes.INVALID_FIELD, path);
  }
  return prototype === Object.prototype || prototype === null;
};

const assertWellFormedUnicode = (value, path) => {
  for (let index = 0; index < value.length; index += 1) {
    const codeUnit = value.charCodeAt(index);
    if (codeUnit >= 0xd800 && codeUnit <= 0xdbff) {
      const next = value.charCodeAt(index + 1);
      if (!Number.isInteger(next) || next < 0xdc00 || next > 0xdfff) {
        fail(ReasonCodes.INVALID_FIELD, path);
      }
      index += 1;
    } else if (codeUnit >= 0xdc00 && codeUnit <= 0xdfff) {
      fail(ReasonCodes.INVALID_FIELD, path);
    }
  }
};

const assertSharedJson = (value, path = '$') => {
  const active = new WeakSet();
  const clones = new WeakMap();
  const stack = [{
    source: value,
    path,
    target: undefined,
    key: undefined,
    leaving: false,
  }];
  let clone;

  const assign = (frame, clonedValue) => {
    if (frame.target === undefined) {
      clone = clonedValue;
      return;
    }
    Object.defineProperty(frame.target, frame.key, {
      value: clonedValue,
      enumerable: true,
      configurable: true,
      writable: true,
    });
  };

  while (stack.length > 0) {
    const current = stack.pop();
    if (current.leaving) {
      active.delete(current.source);
      continue;
    }

    const currentValue = current.source;
    if (currentValue === null || typeof currentValue === 'boolean') {
      assign(current, currentValue);
      continue;
    }
    if (typeof currentValue === 'string') {
      assertWellFormedUnicode(currentValue, current.path);
      assign(current, currentValue);
      continue;
    }
    if (typeof currentValue === 'number') {
      if (!Number.isSafeInteger(currentValue)) {
        fail(ReasonCodes.INVALID_NUMBER, current.path);
      }
      assign(current, currentValue);
      continue;
    }
    if (typeof currentValue !== 'object') {
      fail(ReasonCodes.INVALID_FIELD, current.path);
    }
    if (active.has(currentValue)) {
      fail(ReasonCodes.INVALID_FIELD, current.path);
    }
    if (clones.has(currentValue)) {
      assign(current, clones.get(currentValue));
      continue;
    }

    let isArray;
    let prototype;
    let keys;
    let descriptors;
    try {
      isArray = Array.isArray(currentValue);
      prototype = Object.getPrototypeOf(currentValue);
      keys = Reflect.ownKeys(currentValue);
      descriptors = new Map();
      for (const key of keys) {
        descriptors.set(key, Object.getOwnPropertyDescriptor(currentValue, key));
      }
    } catch {
      fail(ReasonCodes.INVALID_FIELD, current.path);
    }
    if (
      (isArray && prototype !== Array.prototype)
      || (!isArray && prototype !== Object.prototype && prototype !== null)
    ) {
      fail(ReasonCodes.INVALID_FIELD, current.path);
    }

    const container = isArray ? [] : {};
    clones.set(currentValue, container);
    assign(current, container);
    active.add(currentValue);
    stack.push({ source: currentValue, leaving: true });
    const children = [];
    const lengthDescriptor = isArray ? descriptors.get('length') : undefined;
    if (
      isArray
      && (
        lengthDescriptor === undefined
        || !Object.hasOwn(lengthDescriptor, 'value')
        || !Number.isSafeInteger(lengthDescriptor.value)
        || lengthDescriptor.value < 0
      )
    ) {
      fail(ReasonCodes.INVALID_FIELD, current.path + '.length');
    }
    const arrayLength = isArray ? lengthDescriptor.value : 0;
    let arrayIndexCount = 0;

    for (const key of keys) {
      if (typeof key === 'symbol') {
        fail(ReasonCodes.INVALID_FIELD, current.path);
      }
      assertWellFormedUnicode(key, current.path);
      const descriptor = descriptors.get(key);
      if (descriptor === undefined || !Object.hasOwn(descriptor, 'value')) {
        fail(ReasonCodes.INVALID_FIELD, current.path + '.' + key);
      }
      if (isArray && key === 'length') {
        continue;
      }
      if (!descriptor.enumerable) {
        fail(ReasonCodes.INVALID_FIELD, current.path + '.' + key);
      }
      if (isArray) {
        const index = Number(key);
        if (!Number.isInteger(index) || index < 0 || index >= arrayLength || String(index) !== key) {
          fail(ReasonCodes.INVALID_FIELD, current.path + '.' + key);
        }
        arrayIndexCount += 1;
      }
      children.push({
        source: descriptor.value,
        path: isArray ? current.path + '[' + key + ']' : current.path + '.' + key,
        target: container,
        key,
        leaving: false,
      });
    }

    if (isArray && (keys.length !== arrayLength + 1 || arrayIndexCount !== arrayLength)) {
      fail(ReasonCodes.INVALID_FIELD, current.path);
    }
    for (let index = children.length - 1; index >= 0; index -= 1) {
      stack.push(children[index]);
    }
  }
  return clone;
};

const object = (value, allowed, required, path) => {
  if (!isPlainObject(value, path)) {
    fail(ReasonCodes.NOT_OBJECT, path);
  }
  for (const key of Object.keys(value)) {
    if (!allowed.includes(key)) {
      fail(ReasonCodes.UNKNOWN_FIELD, path + '.' + key);
    }
  }
  for (const key of required) {
    if (!Object.hasOwn(value, key)) {
      fail(ReasonCodes.MISSING_FIELD, path + '.' + key);
    }
  }
  return value;
};

const versioned = (value, fields, path, optional = []) => {
  object(value, ['schemaVersion', ...fields], ['schemaVersion', ...fields.filter((field) => !optional.includes(field))], path);
  if (value.schemaVersion !== 1) {
    fail(ReasonCodes.UNSUPPORTED_SCHEMA_VERSION, path + '.schemaVersion');
  }
  return value;
};

const string = (value, path, { nonempty = true, noNul = true } = {}) => {
  if (
    typeof value !== 'string'
    || (nonempty && value.length === 0)
    || (noNul && value.includes('\u0000'))
  ) {
    fail(ReasonCodes.INVALID_FIELD, path);
  }
};

const boolean = (value, path) => {
  if (typeof value !== 'boolean') {
    fail(ReasonCodes.INVALID_FIELD, path);
  }
};

const integer = (value, path, minimum = 0) => {
  if (!Number.isSafeInteger(value) || value < minimum) {
    fail(ReasonCodes.INVALID_NUMBER, path);
  }
};

const array = (value, path, { nonempty = false } = {}) => {
  if (!Array.isArray(value) || (nonempty && value.length === 0)) {
    fail(ReasonCodes.INVALID_FIELD, path);
  }
};

const oneOf = (value, values, path, reasonCode = ReasonCodes.INVALID_FIELD) => {
  if (!values.includes(value)) {
    fail(reasonCode, path);
  }
};

const DIGEST_PATTERN = /^sha256:[0-9a-f]{64}$/u;
const RFC3339_PATTERN = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-](\d{2}):(\d{2}))$/u;

const digest = (value, path) => {
  if (typeof value !== 'string' || !DIGEST_PATTERN.test(value)) {
    fail(ReasonCodes.INVALID_FIELD, path);
  }
};

const timestamp = (value, path) => {
  const match = typeof value === 'string' ? value.match(RFC3339_PATTERN) : null;
  if (match === null) {
    fail(ReasonCodes.INVALID_FIELD, path);
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
    fail(ReasonCodes.INVALID_FIELD, path);
  }
};

const relativePath = (value, path, allowDot = false) => {
  if (allowDot && value === '.') {
    return;
  }
  string(value, path, { noNul: false });
  if (
    value.startsWith('/')
    || /^[A-Za-z]:/u.test(value)
    || value.includes('\u0000')
    || value.includes('\\')
    || value.split('/').some((segment) => segment === '' || segment === '.' || segment === '..')
  ) {
    fail(ReasonCodes.INVALID_PATH, path);
  }
};

const strings = (value, path, options = {}) => {
  array(value, path, options);
  value.forEach((item, index) => string(item, path + '[' + index + ']'));
};

const unique = (values, key, path) => {
  const seen = new Set();
  for (const value of values) {
    const identity = key(value);
    if (seen.has(identity)) {
      fail(ReasonCodes.DUPLICATE_ID, path);
    }
    seen.add(identity);
  }
};

const sortedUniqueStrings = (value, path) => {
  strings(value, path);
  unique(value, (item) => item, path);
  const sorted = [...value].sort();
  if (sorted.some((item, index) => item !== value[index])) {
    fail(ReasonCodes.INVALID_FIELD, path);
  }
};

const validateContext = (context, allowed, path) => {
  if (context === undefined) {
    return {};
  }
  context = assertSharedJson(context, path);
  if (!isPlainObject(context, path)) {
    fail(ReasonCodes.INVALID_CONTEXT, path);
  }
  for (const key of Object.keys(context)) {
    if (!allowed.includes(key)) {
      fail(ReasonCodes.INVALID_CONTEXT, path + '.' + key);
    }
  }
  return context;
};

const validateBindingContextFields = (context, { ids = [], digests = [], roles = [] } = {}) => {
  for (const field of ids) {
    if (
      Object.hasOwn(context, field)
      && (typeof context[field] !== 'string' || context[field].length === 0 || context[field].includes('\u0000'))
    ) {
      fail(ReasonCodes.INVALID_CONTEXT, '$context.' + field);
    }
  }
  for (const field of digests) {
    if (
      Object.hasOwn(context, field)
      && (typeof context[field] !== 'string' || !DIGEST_PATTERN.test(context[field]))
    ) {
      fail(ReasonCodes.INVALID_CONTEXT, '$context.' + field);
    }
  }
  for (const field of roles) {
    if (Object.hasOwn(context, field)) {
      if (!['requirements', 'quality'].includes(context[field])) {
        fail(ReasonCodes.INVALID_CONTEXT, '$context.' + field);
      }
    }
  }
};

const applyBindings = (value, context, fields, reasonCode = ReasonCodes.BINDING_MISMATCH) => {
  for (const field of fields) {
    if (Object.hasOwn(context, field) && value[field] !== context[field]) {
      fail(reasonCode, '$context.' + field);
    }
  }
};

const validateEvidenceReference = (value, path) => {
  versioned(value, ['kind', 'locator', 'digest', 'observedAt', 'afterChangeDigest', 'result'], path, ['digest']);
  oneOf(value.kind, ['test', 'command', 'artifact', 'diff', 'review', 'observation'], path + '.kind');
  relativePath(value.locator, path + '.locator');
  if (Object.hasOwn(value, 'digest')) {
    digest(value.digest, path + '.digest');
  }
  timestamp(value.observedAt, path + '.observedAt');
  if (value.afterChangeDigest !== 'none') {
    digest(value.afterChangeDigest, path + '.afterChangeDigest');
  }
  oneOf(value.result, ['pass', 'fail', 'indeterminate'], path + '.result');
};

const validateAssumption = (value, path) => {
  versioned(value, ['id', 'question', 'disposition', 'decision', 'evidence', 'reversible', 'material'], path, ['decision']);
  string(value.id, path + '.id');
  string(value.question, path + '.question');
  oneOf(value.disposition, ['user_direction', 'safe_default', 'bounded_out', 'needs_input'], path + '.disposition');
  if (value.disposition === 'needs_input') {
    if (Object.hasOwn(value, 'decision')) {
      fail(ReasonCodes.INVALID_FIELD, path + '.decision');
    }
  } else {
    string(value.decision, path + '.decision');
  }
  array(value.evidence, path + '.evidence');
  value.evidence.forEach((item, index) => validateEvidenceReference(item, path + '.evidence[' + index + ']'));
  if (value.disposition !== 'user_direction' && value.evidence.length === 0) {
    fail(ReasonCodes.INVALID_FIELD, path + '.evidence');
  }
  boolean(value.reversible, path + '.reversible');
  boolean(value.material, path + '.material');
  if (value.disposition === 'safe_default' && !value.reversible) {
    fail(ReasonCodes.INVALID_FIELD, path + '.reversible');
  }
};

const validateProofObligation = (value, path) => {
  versioned(
    value,
    ['id', 'requirement', 'evidenceSeam', 'negativeCases', 'authority', 'required', 'status', 'evidence', 'lastRelevantChangeDigest'],
    path,
  );
  for (const field of ['id', 'requirement', 'evidenceSeam', 'authority']) {
    string(value[field], path + '.' + field);
  }
  strings(value.negativeCases, path + '.negativeCases');
  boolean(value.required, path + '.required');
  oneOf(value.status, ['pending', 'passing', 'failing', 'blocked', 'indeterminate', 'not_applicable'], path + '.status');
  array(value.evidence, path + '.evidence');
  value.evidence.forEach((item, index) => validateEvidenceReference(item, path + '.evidence[' + index + ']'));
  if (value.lastRelevantChangeDigest !== 'none') {
    digest(value.lastRelevantChangeDigest, path + '.lastRelevantChangeDigest');
  }
  if (
    value.status === 'passing'
    && (
      value.lastRelevantChangeDigest === 'none'
      || !value.evidence.some(
        (item) => item.result === 'pass' && item.afterChangeDigest === value.lastRelevantChangeDigest,
      )
    )
  ) {
    fail(ReasonCodes.STALE_EVIDENCE, path + '.evidence');
  }
};

const validateIteration = (value, path) => {
  versioned(
    value,
    ['sequence', 'scope', 'changeDigest', 'impactedObligationIds', 'impactedEvidenceIds', 'sentinelEvidenceIds', 'result', 'nextAction'],
    path,
  );
  integer(value.sequence, path + '.sequence', 1);
  string(value.scope, path + '.scope');
  digest(value.changeDigest, path + '.changeDigest');
  strings(value.impactedObligationIds, path + '.impactedObligationIds', { nonempty: true });
  unique(value.impactedObligationIds, (item) => item, path + '.impactedObligationIds');
  strings(value.impactedEvidenceIds, path + '.impactedEvidenceIds');
  unique(value.impactedEvidenceIds, (item) => item, path + '.impactedEvidenceIds');
  strings(value.sentinelEvidenceIds, path + '.sentinelEvidenceIds');
  unique(value.sentinelEvidenceIds, (item) => item, path + '.sentinelEvidenceIds');
  oneOf(value.result, ['passing', 'failing', 'blocked', 'indeterminate'], path + '.result');
  string(value.nextAction, path + '.nextAction', { nonempty: false });
  if (value.result === 'passing' && value.impactedEvidenceIds.length === 0) {
    fail(ReasonCodes.INVALID_FIELD, path + '.impactedEvidenceIds');
  }
  if (value.sentinelEvidenceIds.length === 0 && value.nextAction.length === 0) {
    fail(ReasonCodes.INVALID_FIELD, path + '.nextAction');
  }
};

const validateTaskReviewFinding = (value, path) => {
  versioned(
    value,
    ['id', 'reviewerRole', 'severity', 'claim', 'evidence', 'status', 'dispositionReason', 'repairChangeDigest', 'verificationEvidenceIds'],
    path,
  );
  string(value.id, path + '.id');
  oneOf(value.reviewerRole, ['requirements', 'quality'], path + '.reviewerRole', ReasonCodes.INVALID_REVIEW_ROLE);
  oneOf(value.severity, ['critical', 'important', 'minor'], path + '.severity');
  string(value.claim, path + '.claim');
  array(value.evidence, path + '.evidence', { nonempty: true });
  value.evidence.forEach((item, index) => validateEvidenceReference(item, path + '.evidence[' + index + ']'));
  oneOf(value.status, ['open', 'accepted', 'rejected', 'repaired', 'verified'], path + '.status');
  string(value.dispositionReason, path + '.dispositionReason', { nonempty: false });
  if (['rejected', 'repaired', 'verified'].includes(value.status) && value.dispositionReason.length === 0) {
    fail(ReasonCodes.INVALID_FIELD, path + '.dispositionReason');
  }
  if (value.repairChangeDigest !== 'none') {
    digest(value.repairChangeDigest, path + '.repairChangeDigest');
  }
  if (['repaired', 'verified'].includes(value.status) && value.repairChangeDigest === 'none') {
    fail(ReasonCodes.INVALID_FIELD, path + '.repairChangeDigest');
  }
  strings(value.verificationEvidenceIds, path + '.verificationEvidenceIds');
  unique(value.verificationEvidenceIds, (item) => item, path + '.verificationEvidenceIds');
  if (value.status === 'verified' && value.verificationEvidenceIds.length === 0) {
    fail(ReasonCodes.INVALID_FIELD, path + '.verificationEvidenceIds');
  }
};

const validateTerminalState = (value, path) => {
  versioned(value, ['declared', 'reason', 'unresolvedObligationIds', 'activeWork'], path);
  oneOf(value.declared, ['complete', 'incomplete', 'blocked', 'failed', 'indeterminate', 'needs_input'], path + '.declared');
  string(value.reason, path + '.reason');
  strings(value.unresolvedObligationIds, path + '.unresolvedObligationIds');
  unique(value.unresolvedObligationIds, (item) => item, path + '.unresolvedObligationIds');
  boolean(value.activeWork, path + '.activeWork');
};

// Optional contexts are caller authority for environmental bindings. Omitting
// one preserves the documented one-argument structural parser contract.
export const parseTaskState = (value, context = {}) => {
  value = assertSharedJson(value);
  versioned(
    value,
    ['taskId', 'workspaceDigest', 'requestDigest', 'workflowTier', 'intent', 'assumptions', 'obligations', 'iterations', 'reviewFindings', 'terminalState', 'updatedAt'],
    '$',
  );
  string(value.taskId, '$.taskId');
  digest(value.workspaceDigest, '$.workspaceDigest');
  digest(value.requestDigest, '$.requestDigest');
  oneOf(value.workflowTier, ['trivial', 'substantial'], '$.workflowTier');
  string(value.intent, '$.intent');
  array(value.assumptions, '$.assumptions');
  value.assumptions.forEach((item, index) => validateAssumption(item, '$.assumptions[' + index + ']'));
  unique(value.assumptions, (item) => item.id, '$.assumptions');
  array(value.obligations, '$.obligations', { nonempty: value.workflowTier === 'substantial' });
  value.obligations.forEach((item, index) => validateProofObligation(item, '$.obligations[' + index + ']'));
  unique(value.obligations, (item) => item.id, '$.obligations');
  array(value.iterations, '$.iterations');
  value.iterations.forEach((item, index) => {
    validateIteration(item, '$.iterations[' + index + ']');
    if (index > 0 && item.sequence <= value.iterations[index - 1].sequence) {
      fail(ReasonCodes.INVALID_FIELD, '$.iterations[' + index + '].sequence');
    }
  });
  array(value.reviewFindings, '$.reviewFindings');
  value.reviewFindings.forEach((item, index) => validateTaskReviewFinding(item, '$.reviewFindings[' + index + ']'));
  unique(value.reviewFindings, (item) => item.id, '$.reviewFindings');
  validateTerminalState(value.terminalState, '$.terminalState');
  timestamp(value.updatedAt, '$.updatedAt');

  const unresolved = value.obligations
    .filter((item) => item.required && item.status !== 'passing')
    .map((item) => item.id)
    .sort();
  const declaredUnresolved = [...value.terminalState.unresolvedObligationIds].sort();
  if (
    unresolved.length !== declaredUnresolved.length
    || unresolved.some((item, index) => item !== declaredUnresolved[index])
  ) {
    fail(ReasonCodes.TERMINAL_INCONSISTENT, '$.terminalState.unresolvedObligationIds');
  }
  if (value.terminalState.declared === 'complete') {
    if (value.terminalState.activeWork || unresolved.length > 0) {
      fail(ReasonCodes.TERMINAL_INCONSISTENT, '$.terminalState');
    }
    const unverifiedMaterial = value.reviewFindings.some(
      (item) => ['critical', 'important'].includes(item.severity)
        && !['rejected', 'verified'].includes(item.status),
    );
    if (unverifiedMaterial) {
      fail(ReasonCodes.TERMINAL_INCONSISTENT, '$.reviewFindings');
    }
  }

  context = validateContext(context, ['taskId', 'workspaceDigest', 'requestDigest'], '$context');
  validateBindingContextFields(context, {
    ids: ['taskId'],
    digests: ['workspaceDigest', 'requestDigest'],
  });
  applyBindings(value, context, ['taskId', 'workspaceDigest', 'requestDigest'], ReasonCodes.FOREIGN_IDENTITY);
  return value;
};

export const parseEvidenceEvent = (value, context = {}) => {
  value = assertSharedJson(value);
  versioned(
    value,
    ['eventId', 'taskId', 'sequence', 'eventKind', 'toolName', 'resultClass', 'redactedPayloadDigest', 'previousEventDigest', 'occurredAt'],
    '$',
  );
  string(value.eventId, '$.eventId');
  string(value.taskId, '$.taskId');
  integer(value.sequence, '$.sequence');
  oneOf(value.eventKind, ['post_tool_use', 'post_invocation'], '$.eventKind');
  if (value.eventKind === 'post_tool_use' && value.toolName === 'not_applicable') {
    fail(ReasonCodes.INVALID_FIELD, '$.toolName');
  }
  if (value.eventKind === 'post_invocation' && value.toolName !== 'not_applicable') {
    fail(ReasonCodes.INVALID_FIELD, '$.toolName');
  }
  if (value.toolName !== 'not_applicable') {
    string(value.toolName, '$.toolName');
  }
  oneOf(value.resultClass, ['success', 'error', 'indeterminate'], '$.resultClass');
  digest(value.redactedPayloadDigest, '$.redactedPayloadDigest');
  if (value.previousEventDigest !== 'genesis') {
    digest(value.previousEventDigest, '$.previousEventDigest');
  }
  timestamp(value.occurredAt, '$.occurredAt');
  context = validateContext(context, ['taskId'], '$context');
  validateBindingContextFields(context, { ids: ['taskId'] });
  applyBindings(value, context, ['taskId'], ReasonCodes.FOREIGN_IDENTITY);
  return value;
};

const GATE_REASONS = [
  'task_state_initialized',
  'active_work',
  'invalid_task_state',
  'unresolved_required_obligation',
  'stale_passing_evidence',
  'accepted_finding_unverified',
  'retry_bound_reached',
];

export const parseCompletionGateEvent = (value, context = {}) => {
  value = assertSharedJson(value);
  versioned(
    value,
    ['eventId', 'taskId', 'workspaceDigest', 'requestDigest', 'eventKind', 'stopSequenceId', 'continuationOrdinal', 'frozenBound', 'decision', 'reasonCode', 'previousEventDigest', 'occurredAt'],
    '$',
  );
  string(value.eventId, '$.eventId');
  string(value.taskId, '$.taskId');
  digest(value.workspaceDigest, '$.workspaceDigest');
  digest(value.requestDigest, '$.requestDigest');
  oneOf(value.eventKind, ['initialized', 'continued'], '$.eventKind');
  if (value.stopSequenceId !== 'not_applicable') {
    string(value.stopSequenceId, '$.stopSequenceId');
  }
  integer(value.continuationOrdinal, '$.continuationOrdinal');
  integer(value.frozenBound, '$.frozenBound');
  oneOf(value.decision, ['none', 'continue'], '$.decision');
  oneOf(value.reasonCode, GATE_REASONS, '$.reasonCode');
  if (value.previousEventDigest !== 'genesis') {
    digest(value.previousEventDigest, '$.previousEventDigest');
  }
  timestamp(value.occurredAt, '$.occurredAt');
  const genesis = value.eventKind === 'initialized'
    && value.stopSequenceId === 'not_applicable'
    && value.continuationOrdinal === 0
    && value.decision === 'none'
    && value.reasonCode === 'task_state_initialized'
    && value.previousEventDigest === 'genesis';
  const continued = value.eventKind === 'continued'
    && value.stopSequenceId !== 'not_applicable'
    && value.continuationOrdinal > 0
    && value.decision === 'continue'
    && value.continuationOrdinal <= value.frozenBound
    && value.reasonCode !== 'task_state_initialized'
    && value.reasonCode !== 'retry_bound_reached'
    && value.previousEventDigest !== 'genesis';
  const boundReached = value.eventKind === 'continued'
    && value.stopSequenceId !== 'not_applicable'
    && value.continuationOrdinal > value.frozenBound
    && value.decision === 'none'
    && value.reasonCode === 'retry_bound_reached'
    && value.previousEventDigest !== 'genesis';
  if (!genesis && !continued && !boundReached) {
    fail(ReasonCodes.INVALID_GATE_EVENT, '$');
  }
  context = validateContext(context, ['taskId', 'workspaceDigest', 'requestDigest'], '$context');
  validateBindingContextFields(context, {
    ids: ['taskId'],
    digests: ['workspaceDigest', 'requestDigest'],
  });
  applyBindings(value, context, ['taskId', 'workspaceDigest', 'requestDigest'], ReasonCodes.FOREIGN_IDENTITY);
  return value;
};

const validateVerificationCommand = (value, path) => {
  versioned(value, ['id', 'executable', 'arguments', 'workingDirectory', 'timeoutMs'], path);
  string(value.id, path + '.id');
  string(value.executable, path + '.executable');
  array(value.arguments, path + '.arguments');
  value.arguments.forEach((item, index) => {
    string(item, path + '.arguments[' + index + ']', { nonempty: false });
  });
  relativePath(value.workingDirectory, path + '.workingDirectory', true);
  integer(value.timeoutMs, path + '.timeoutMs', 1);
};

const validateVerificationInterface = (value, path) => {
  versioned(value, ['interfaceId', 'commands', 'artifacts'], path);
  string(value.interfaceId, path + '.interfaceId');
  array(value.commands, path + '.commands', { nonempty: true });
  value.commands.forEach((item, index) => validateVerificationCommand(item, path + '.commands[' + index + ']'));
  unique(value.commands, (item) => item.id, path + '.commands');
  array(value.artifacts, path + '.artifacts');
  value.artifacts.forEach((item, index) => relativePath(item, path + '.artifacts[' + index + ']'));
  unique(value.artifacts, (item) => item, path + '.artifacts');
};

const REVIEW_AUTHORITY_ACTIONS = ['execute_verification', 'read', 'write_verdict'];

const validateAuthorityManifest = (value, path) => {
  versioned(
    value,
    ['manifestId', 'allowedActions', 'allowedResources', 'networkPolicyDigest', 'credentialGrantDigests', 'expiresAt'],
    path,
  );
  string(value.manifestId, path + '.manifestId');
  sortedUniqueStrings(value.allowedActions, path + '.allowedActions');
  value.allowedActions.forEach((item, index) => {
    oneOf(item, REVIEW_AUTHORITY_ACTIONS, path + '.allowedActions[' + index + ']');
  });
  sortedUniqueStrings(value.allowedResources, path + '.allowedResources');
  value.allowedResources.forEach((item, index) => {
    relativePath(item, path + '.allowedResources[' + index + ']');
    if (/[*?[\]]/u.test(item)) {
      fail(ReasonCodes.INVALID_PATH, path + '.allowedResources[' + index + ']');
    }
  });
  digest(value.networkPolicyDigest, path + '.networkPolicyDigest');
  sortedUniqueStrings(value.credentialGrantDigests, path + '.credentialGrantDigests');
  value.credentialGrantDigests.forEach((item, index) => digest(item, path + '.credentialGrantDigests[' + index + ']'));
  if (value.expiresAt !== 'not_applicable') {
    timestamp(value.expiresAt, path + '.expiresAt');
  }
};

export const parseReviewPackageInput = (value) => {
  value = assertSharedJson(value);
  versioned(
    value,
    ['artifactRoot', 'artifactDigest', 'obligations', 'obligationDigest', 'verificationInterface', 'verificationInterfaceDigest', 'authorityManifest', 'authorityDigest'],
    '$',
  );
  relativePath(value.artifactRoot, '$.artifactRoot');
  digest(value.artifactDigest, '$.artifactDigest');
  array(value.obligations, '$.obligations', { nonempty: true });
  value.obligations.forEach((item, index) => validateProofObligation(item, '$.obligations[' + index + ']'));
  unique(value.obligations, (item) => item.id, '$.obligations');
  digest(value.obligationDigest, '$.obligationDigest');
  validateVerificationInterface(value.verificationInterface, '$.verificationInterface');
  digest(value.verificationInterfaceDigest, '$.verificationInterfaceDigest');
  validateAuthorityManifest(value.authorityManifest, '$.authorityManifest');
  digest(value.authorityDigest, '$.authorityDigest');
  for (const [field, content] of [
    ['obligationDigest', value.obligations],
    ['verificationInterfaceDigest', value.verificationInterface],
    ['authorityDigest', value.authorityManifest],
  ]) {
    if (value[field] !== sha256Digest(canonicalBytes(content))) {
      fail(ReasonCodes.BINDING_MISMATCH, '$.' + field);
    }
  }
  return value;
};

const REVIEW_BINDINGS = [
  'artifactDigest',
  'obligationDigest',
  'verificationInterfaceDigest',
  'authorityDigest',
];

const selfDigest = (value, field) => {
  const body = Object.fromEntries(Object.entries(value).filter(([key]) => key !== field));
  return sha256Digest(canonicalBytes(body));
};

export const parseReviewPairEnvelope = (value, context = {}) => {
  value = assertSharedJson(value);
  versioned(
    value,
    ['pairId', ...REVIEW_BINDINGS, 'sharedPackageManifestDigest', 'reviewPairEnvelopeDigest'],
    '$',
  );
  string(value.pairId, '$.pairId');
  for (const field of [...REVIEW_BINDINGS, 'sharedPackageManifestDigest', 'reviewPairEnvelopeDigest']) {
    digest(value[field], '$.' + field);
  }
  if (selfDigest(value, 'reviewPairEnvelopeDigest') !== value.reviewPairEnvelopeDigest) {
    fail(ReasonCodes.SELF_DIGEST_MISMATCH, '$.reviewPairEnvelopeDigest');
  }
  context = validateContext(context, ['pairId', ...REVIEW_BINDINGS, 'sharedPackageManifestDigest'], '$context');
  validateBindingContextFields(context, {
    ids: ['pairId'],
    digests: [...REVIEW_BINDINGS, 'sharedPackageManifestDigest'],
  });
  applyBindings(value, context, ['pairId', ...REVIEW_BINDINGS, 'sharedPackageManifestDigest']);
  return value;
};

export const parseReviewRequest = (value, context = {}) => {
  value = assertSharedJson(value);
  versioned(
    value,
    ['requestId', 'reviewerRole', 'reviewPairEnvelopeDigest', ...REVIEW_BINDINGS, 'packageManifestDigest', 'reviewRequestDigest'],
    '$',
  );
  string(value.requestId, '$.requestId');
  oneOf(value.reviewerRole, ['requirements', 'quality'], '$.reviewerRole', ReasonCodes.INVALID_REVIEW_ROLE);
  for (const field of ['reviewPairEnvelopeDigest', ...REVIEW_BINDINGS, 'packageManifestDigest', 'reviewRequestDigest']) {
    digest(value[field], '$.' + field);
  }
  if (selfDigest(value, 'reviewRequestDigest') !== value.reviewRequestDigest) {
    fail(ReasonCodes.SELF_DIGEST_MISMATCH, '$.reviewRequestDigest');
  }
  context = validateContext(
    context,
    ['reviewerRole', 'reviewPairEnvelopeDigest', ...REVIEW_BINDINGS],
    '$context',
  );
  validateBindingContextFields(context, {
    digests: ['reviewPairEnvelopeDigest', ...REVIEW_BINDINGS],
    roles: ['reviewerRole'],
  });
  applyBindings(value, context, ['reviewerRole', 'reviewPairEnvelopeDigest', ...REVIEW_BINDINGS]);
  return value;
};

const validateReviewerFinding = (value, path) => {
  versioned(value, ['id', 'severity', 'claim', 'evidence', 'affectedObligationIds', 'suggestedFalsification'], path);
  string(value.id, path + '.id');
  oneOf(value.severity, ['critical', 'important', 'minor'], path + '.severity');
  string(value.claim, path + '.claim');
  array(value.evidence, path + '.evidence', { nonempty: true });
  value.evidence.forEach((item, index) => validateEvidenceReference(item, path + '.evidence[' + index + ']'));
  sortedUniqueStrings(value.affectedObligationIds, path + '.affectedObligationIds');
  string(value.suggestedFalsification, path + '.suggestedFalsification');
};

export const parseReviewerVerdict = (value, context = {}) => {
  value = assertSharedJson(value);
  versioned(
    value,
    ['reviewerRole', 'reviewRequestDigest', 'reviewPairEnvelopeDigest', ...REVIEW_BINDINGS, 'findings', 'verdict', 'inspectedEvidence', 'limitations'],
    '$',
  );
  oneOf(value.reviewerRole, ['requirements', 'quality'], '$.reviewerRole', ReasonCodes.INVALID_REVIEW_ROLE);
  for (const field of ['reviewRequestDigest', 'reviewPairEnvelopeDigest', ...REVIEW_BINDINGS]) {
    digest(value[field], '$.' + field);
  }
  array(value.findings, '$.findings');
  value.findings.forEach((item, index) => validateReviewerFinding(item, '$.findings[' + index + ']'));
  unique(value.findings, (item) => item.id, '$.findings');
  oneOf(value.verdict, ['pass', 'fail', 'indeterminate'], '$.verdict');
  array(value.inspectedEvidence, '$.inspectedEvidence');
  value.inspectedEvidence.forEach((item, index) => validateEvidenceReference(item, '$.inspectedEvidence[' + index + ']'));
  if (
    (value.verdict !== 'indeterminate' || value.findings.length > 0)
    && value.inspectedEvidence.length === 0
  ) {
    fail(ReasonCodes.INVALID_REVIEW_VERDICT, '$.inspectedEvidence');
  }
  strings(value.limitations, '$.limitations');
  context = validateContext(
    context,
    ['reviewerRole', 'reviewRequestDigest', 'reviewPairEnvelopeDigest', ...REVIEW_BINDINGS],
    '$context',
  );
  validateBindingContextFields(context, {
    digests: ['reviewRequestDigest', 'reviewPairEnvelopeDigest', ...REVIEW_BINDINGS],
    roles: ['reviewerRole'],
  });
  applyBindings(value, context, ['reviewerRole', 'reviewRequestDigest', 'reviewPairEnvelopeDigest', ...REVIEW_BINDINGS]);
  return value;
};

const validateJoinFinding = (value, path) => {
  versioned(value, ['reviewerRole', 'findingId'], path);
  oneOf(value.reviewerRole, ['requirements', 'quality'], path + '.reviewerRole', ReasonCodes.INVALID_REVIEW_ROLE);
  string(value.findingId, path + '.findingId');
};

export const parseReviewJoinRecord = (value, context = {}) => {
  value = assertSharedJson(value);
  versioned(
    value,
    ['reviewPairEnvelopeDigest', 'requirementsReviewRequestDigest', 'qualityReviewRequestDigest', 'requirementsVerdictDigest', 'qualityVerdictDigest', 'roleSeparationEvidenceDigest', 'findings', 'joinState', 'limitations'],
    '$',
  );
  for (const field of [
    'reviewPairEnvelopeDigest',
    'requirementsReviewRequestDigest',
    'qualityReviewRequestDigest',
    'roleSeparationEvidenceDigest',
  ]) {
    digest(value[field], '$.' + field);
  }
  for (const field of ['requirementsVerdictDigest', 'qualityVerdictDigest']) {
    if (value[field] !== 'indeterminate') {
      digest(value[field], '$.' + field);
    }
  }
  array(value.findings, '$.findings');
  value.findings.forEach((item, index) => validateJoinFinding(item, '$.findings[' + index + ']'));
  unique(value.findings, (item) => item.reviewerRole + '\u0000' + item.findingId, '$.findings');
  oneOf(value.joinState, ['complete', 'indeterminate'], '$.joinState');
  strings(value.limitations, '$.limitations');
  if (value.requirementsReviewRequestDigest === value.qualityReviewRequestDigest) {
    fail(ReasonCodes.INVALID_REVIEW_JOIN, '$.qualityReviewRequestDigest');
  }
  const bothPresent = value.requirementsVerdictDigest !== 'indeterminate'
    && value.qualityVerdictDigest !== 'indeterminate';
  if (bothPresent && value.requirementsVerdictDigest === value.qualityVerdictDigest) {
    fail(ReasonCodes.INVALID_REVIEW_JOIN, '$.qualityVerdictDigest');
  }
  if ((value.joinState === 'complete') !== bothPresent) {
    fail(ReasonCodes.INVALID_REVIEW_JOIN, '$.joinState');
  }
  for (const role of ['requirements', 'quality']) {
    if (
      value[role + 'VerdictDigest'] === 'indeterminate'
      && value.findings.some((item) => item.reviewerRole === role)
    ) {
      fail(ReasonCodes.INVALID_REVIEW_JOIN, '$.findings');
    }
  }

  context = validateContext(
    context,
    [
      'reviewPairEnvelope',
      'requirementsRequest',
      'qualityRequest',
      'requirementsVerdict',
      'qualityVerdict',
    ],
    '$context',
  );
  const suppliedArtifacts = [];
  let envelope;
  if (Object.hasOwn(context, 'reviewPairEnvelope')) {
    envelope = parseReviewPairEnvelope(context.reviewPairEnvelope);
    suppliedArtifacts.push(envelope);
    if (value.reviewPairEnvelopeDigest !== envelope.reviewPairEnvelopeDigest) {
      fail(ReasonCodes.BINDING_MISMATCH, '$context.reviewPairEnvelope');
    }
  }
  for (const role of ['requirements', 'quality']) {
    const requestField = role + 'Request';
    const verdictField = role + 'Verdict';
    let request;
    if (Object.hasOwn(context, requestField)) {
      request = parseReviewRequest(context[requestField], {
        reviewerRole: role,
        reviewPairEnvelopeDigest: value.reviewPairEnvelopeDigest,
        ...(envelope === undefined ? {} : {
          artifactDigest: envelope.artifactDigest,
          obligationDigest: envelope.obligationDigest,
          verificationInterfaceDigest: envelope.verificationInterfaceDigest,
          authorityDigest: envelope.authorityDigest,
        }),
      });
      const recordRequestDigest = value[role + 'ReviewRequestDigest'];
      if (recordRequestDigest !== request.reviewRequestDigest) {
        fail(ReasonCodes.BINDING_MISMATCH, '$context.' + requestField);
      }
      suppliedArtifacts.push(request);
    }
    if (!Object.hasOwn(context, verdictField)) {
      continue;
    }
    const verdict = parseReviewerVerdict(context[verdictField], {
      reviewerRole: role,
      reviewRequestDigest: value[role + 'ReviewRequestDigest'],
      reviewPairEnvelopeDigest: value.reviewPairEnvelopeDigest,
      ...(request === undefined ? {} : {
        artifactDigest: request.artifactDigest,
        obligationDigest: request.obligationDigest,
        verificationInterfaceDigest: request.verificationInterfaceDigest,
        authorityDigest: request.authorityDigest,
      }),
    });
    const recordVerdictDigest = value[role + 'VerdictDigest'];
    if (
      recordVerdictDigest === 'indeterminate'
      || recordVerdictDigest !== sha256Digest(canonicalBytes(verdict))
    ) {
      fail(ReasonCodes.BINDING_MISMATCH, '$context.' + verdictField);
    }
    suppliedArtifacts.push(verdict);
    const expected = verdict.findings.map((item) => ({
      schemaVersion: 1,
      reviewerRole: role,
      findingId: item.id,
    }));
    const actual = value.findings.filter((item) => item.reviewerRole === role);
    if (
      actual.length !== expected.length
      || actual.some((item, index) => (
        item.schemaVersion !== expected[index].schemaVersion
        || item.reviewerRole !== expected[index].reviewerRole
        || item.findingId !== expected[index].findingId
      ))
    ) {
      fail(ReasonCodes.INVALID_REVIEW_JOIN, '$.findings');
    }
  }
  if (Object.hasOwn(context, 'requirementsVerdict') && Object.hasOwn(context, 'qualityVerdict')) {
    const expected = [
      ...context.requirementsVerdict.findings.map((item) => ({
        schemaVersion: 1,
        reviewerRole: 'requirements',
        findingId: item.id,
      })),
      ...context.qualityVerdict.findings.map((item) => ({
        schemaVersion: 1,
        reviewerRole: 'quality',
        findingId: item.id,
      })),
    ];
    if (
      value.findings.length !== expected.length
      || value.findings.some((item, index) => (
        item.schemaVersion !== expected[index].schemaVersion
        || item.reviewerRole !== expected[index].reviewerRole
        || item.findingId !== expected[index].findingId
      ))
    ) {
      fail(ReasonCodes.INVALID_REVIEW_JOIN, '$.findings');
    }
  }
  if (suppliedArtifacts.length > 1) {
    const expectedBindings = suppliedArtifacts[0];
    for (let index = 1; index < suppliedArtifacts.length; index += 1) {
      for (const field of REVIEW_BINDINGS) {
        if (suppliedArtifacts[index][field] !== expectedBindings[field]) {
          fail(ReasonCodes.BINDING_MISMATCH, '$context.' + field);
        }
      }
    }
  }
  return value;
};
