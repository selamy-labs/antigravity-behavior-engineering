import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

import { canonicalBytes, sha256Digest } from '../src/canonical-json.mjs';
import {
  ContractValidationError, ReasonCodes, parseCompletionGateEvent, parseEvidenceEvent,
  parseReviewJoinRecord, parseReviewPackageInput, parseReviewPairEnvelope, parseReviewRequest,
  parseReviewerVerdict, parseTaskState,
} from '../src/runtime-contracts.mjs';

const digest = (character) => 'sha256:' + character.repeat(64);
const now = '2026-08-20T12:00:00Z';
const clone = (value) => structuredClone(value);
const without = (value, key) => Object.fromEntries(Object.entries(value).filter(([name]) => name !== key));
const identityDigest = (value, key) => sha256Digest(canonicalBytes(without(value, key)));

const evidence = {
  schemaVersion: 1, kind: 'test', locator: 'evidence/focused.txt', digest: digest('a'),
  observedAt: now, afterChangeDigest: digest('b'), result: 'pass',
};
const obligation = {
  schemaVersion: 1, id: 'O-1', requirement: 'The observable behavior is preserved.',
  evidenceSeam: 'node --test focused.test.mjs', negativeCases: ['rejects malformed input'],
  authority: 'read workspace and run focused tests', required: true, status: 'passing',
  evidence: [evidence], lastRelevantChangeDigest: digest('b'),
};
const taskState = {
  schemaVersion: 1, taskId: 'task-1', workspaceDigest: digest('c'), requestDigest: digest('d'),
  workflowTier: 'substantial', intent: 'Implement the bounded runtime contract.', assumptions: [],
  obligations: [obligation],
  iterations: [{
    schemaVersion: 1, sequence: 1, scope: 'Add contract parsing.', changeDigest: digest('b'),
    impactedObligationIds: ['O-1'], impactedEvidenceIds: ['evidence/focused.txt'],
    sentinelEvidenceIds: [], result: 'passing', nextAction: '',
  }],
  reviewFindings: [],
  terminalState: {
    schemaVersion: 1, declared: 'complete',
    reason: 'All mechanical obligations have fresh passing evidence.',
    unresolvedObligationIds: [], activeWork: false,
  },
  updatedAt: now,
};
const gateEvent = {
  schemaVersion: 1, eventId: 'gate-1', taskId: 'task-1', workspaceDigest: digest('c'),
  requestDigest: digest('d'), eventKind: 'initialized', stopSequenceId: 'not_applicable',
  continuationOrdinal: 0, frozenBound: 1, decision: 'none',
  reasonCode: 'task_state_initialized', previousEventDigest: 'genesis', occurredAt: now,
};
const evidenceEvent = {
  schemaVersion: 1, eventId: 'event-1', taskId: 'task-1', sequence: 0,
  eventKind: 'post_tool_use', toolName: 'node', resultClass: 'success',
  redactedPayloadDigest: digest('e'), previousEventDigest: 'genesis', occurredAt: now,
};
const verificationInterface = {
  schemaVersion: 1, interfaceId: 'focused-tests',
  commands: [{
    schemaVersion: 1, id: 'focused', executable: 'node',
    arguments: ['--test', 'test/focused.test.mjs'], workingDirectory: '.', timeoutMs: 30000,
  }],
  artifacts: ['test/focused.test.mjs'],
};
const authorityManifest = {
  schemaVersion: 1, manifestId: 'review-read-only',
  allowedActions: ['execute_verification', 'read'], allowedResources: ['src', 'test'],
  networkPolicyDigest: digest('f'), credentialGrantDigests: [], expiresAt: 'not_applicable',
};
const reviewPackage = {
  schemaVersion: 1, artifactRoot: 'artifact', artifactDigest: digest('1'),
  obligations: [obligation], obligationDigest: digest('2'), verificationInterface,
  verificationInterfaceDigest: digest('3'), authorityManifest, authorityDigest: digest('4'),
};
const pairEnvelope = {
  schemaVersion: 1, pairId: 'pair-1', artifactDigest: digest('1'), obligationDigest: digest('2'),
  verificationInterfaceDigest: digest('3'), authorityDigest: digest('4'),
  sharedPackageManifestDigest: digest('5'), reviewPairEnvelopeDigest: '',
};
pairEnvelope.reviewPairEnvelopeDigest = identityDigest(pairEnvelope, 'reviewPairEnvelopeDigest');
const reviewRequest = {
  schemaVersion: 1, requestId: 'request-requirements-1', reviewerRole: 'requirements',
  reviewPairEnvelopeDigest: pairEnvelope.reviewPairEnvelopeDigest, artifactDigest: digest('1'),
  obligationDigest: digest('2'), verificationInterfaceDigest: digest('3'), authorityDigest: digest('4'),
  packageManifestDigest: digest('6'), reviewRequestDigest: '',
};
reviewRequest.reviewRequestDigest = identityDigest(reviewRequest, 'reviewRequestDigest');
const reviewerFinding = {
  schemaVersion: 1, id: 'R-1', severity: 'important', claim: 'A negative case is not exercised.',
  evidence: [{ ...evidence, result: 'fail' }], affectedObligationIds: ['O-1'],
  suggestedFalsification: 'Run the declared focused command with malformed input.',
};
const reviewerVerdict = {
  schemaVersion: 1, reviewerRole: 'requirements', reviewRequestDigest: reviewRequest.reviewRequestDigest,
  reviewPairEnvelopeDigest: pairEnvelope.reviewPairEnvelopeDigest, artifactDigest: digest('1'),
  obligationDigest: digest('2'), verificationInterfaceDigest: digest('3'), authorityDigest: digest('4'),
  findings: [reviewerFinding], verdict: 'fail', inspectedEvidence: [evidence], limitations: [],
};
const joinRecord = {
  schemaVersion: 1, reviewPairEnvelopeDigest: pairEnvelope.reviewPairEnvelopeDigest,
  requirementsReviewRequestDigest: reviewRequest.reviewRequestDigest,
  qualityReviewRequestDigest: digest('7'),
  requirementsVerdictDigest: sha256Digest(canonicalBytes(reviewerVerdict)),
  qualityVerdictDigest: 'indeterminate', roleSeparationEvidenceDigest: digest('9'),
  findings: [{ schemaVersion: 1, reviewerRole: 'requirements', findingId: 'R-1' }],
  joinState: 'indeterminate', limitations: ['quality reviewer unavailable'],
};

const expectCode = (function_, code) => {
  assert.throws(function_, (error) => {
    assert.ok(error instanceof ContractValidationError);
    assert.equal(error.reasonCode, code);
    return true;
  });
};

test('valid fixtures for all eight parsers hash through the T002 canonical subset', () => {
  const fixtures = [
    parseTaskState(taskState), parseEvidenceEvent(evidenceEvent),
    parseCompletionGateEvent(gateEvent), parseReviewPackageInput(reviewPackage),
    parseReviewPairEnvelope(pairEnvelope), parseReviewRequest(reviewRequest),
    parseReviewerVerdict(reviewerVerdict), parseReviewJoinRecord(joinRecord),
  ];
  for (const parsed of fixtures) {
    assert.match(sha256Digest(canonicalBytes(parsed)), /^sha256:[0-9a-f]{64}$/);
  }
});

test('published schemas are closed Draft 2020-12 contracts', () => {
  for (const name of [
    'task-state', 'evidence-event', 'completion-gate-event', 'review-package-input',
    'review-pair-envelope', 'review-request', 'reviewer-verdict', 'reviewer-join',
  ]) {
    const schema = JSON.parse(fs.readFileSync(path.resolve('plugin/schemas', name + '.schema.json'), 'utf8'));
    assert.equal(schema.$schema, 'https://json-schema.org/draft/2020-12/schema');
    assert.equal(schema.additionalProperties, false);
    assert.equal(schema.properties.schemaVersion.const, 1);
  }
});

test('invalid, unknown-field, wrong-version, float, and unsafe-integer fixtures fail closed', () => {
  expectCode(() => parseTaskState(null), ReasonCodes.NOT_OBJECT);
  expectCode(() => parseTaskState({ ...taskState, unexpected: true }), ReasonCodes.UNKNOWN_FIELD);
  expectCode(() => parseTaskState({ ...taskState, schemaVersion: 2 }), ReasonCodes.UNSUPPORTED_SCHEMA_VERSION);
  expectCode(() => parseEvidenceEvent({ ...evidenceEvent, sequence: 1.5 }), ReasonCodes.INVALID_NUMBER);
  expectCode(() => parseEvidenceEvent({ ...evidenceEvent, sequence: Number.MAX_SAFE_INTEGER + 1 }), ReasonCodes.INVALID_NUMBER);
  expectCode(
    () => parseEvidenceEvent({ ...evidenceEvent, occurredAt: '2026-02-30T12:00:00Z' }),
    ReasonCodes.INVALID_FIELD,
  );
  expectCode(
    () => parseEvidenceEvent({ ...evidenceEvent, eventId: '\ud800' }),
    ReasonCodes.INVALID_FIELD,
  );
  const nestedUnknown = clone(taskState);
  nestedUnknown.obligations[0].unexpected = true;
  expectCode(() => parseTaskState(nestedUnknown), ReasonCodes.UNKNOWN_FIELD);
  const nestedVersion = clone(taskState);
  nestedVersion.obligations[0].schemaVersion = 2;
  expectCode(() => parseTaskState(nestedVersion), ReasonCodes.UNSUPPORTED_SCHEMA_VERSION);
  for (const [parser, fixture] of [
    [parseEvidenceEvent, evidenceEvent],
    [parseCompletionGateEvent, gateEvent],
    [parseReviewPackageInput, reviewPackage],
    [parseReviewPairEnvelope, pairEnvelope],
    [parseReviewRequest, reviewRequest],
    [parseReviewerVerdict, reviewerVerdict],
    [parseReviewJoinRecord, joinRecord],
  ]) {
    expectCode(
      () => parser({ ...fixture, schemaVersion: 2 }),
      ReasonCodes.UNSUPPORTED_SCHEMA_VERSION,
    );
  }
});

test('normalized relative paths reject absolute, traversal, empty segments, backslashes, and NUL', () => {
  for (const artifactRoot of ['/tmp/artifact', 'C:/artifact', '../artifact', 'one//two', 'one\\two', 'one\u0000two']) {
    expectCode(() => parseReviewPackageInput({ ...reviewPackage, artifactRoot }), ReasonCodes.INVALID_PATH);
  }
  const invalidWorkingDirectory = clone(reviewPackage);
  invalidWorkingDirectory.verificationInterface.commands[0].workingDirectory = '..';
  expectCode(() => parseReviewPackageInput(invalidWorkingDirectory), ReasonCodes.INVALID_PATH);
});

test('foreign task, workspace, and request identities fail only under explicit closed context', () => {
  assert.deepEqual(parseTaskState(taskState), taskState);
  expectCode(() => parseTaskState(taskState, { workspaceDigest: digest('0') }), ReasonCodes.FOREIGN_IDENTITY);
  expectCode(() => parseTaskState(taskState, { taskId: 'other-task' }), ReasonCodes.FOREIGN_IDENTITY);
  expectCode(() => parseCompletionGateEvent(gateEvent, { requestDigest: digest('0') }), ReasonCodes.FOREIGN_IDENTITY);
  expectCode(
    () => parseTaskState(taskState, { workspaceDigest: digest('c'), unexpected: true }),
    ReasonCodes.INVALID_CONTEXT,
  );
});

test('terminal inconsistency and stale passing evidence have distinct stable failures', () => {
  const unresolvedMismatch = clone(taskState);
  unresolvedMismatch.obligations[0].status = 'failing';
  unresolvedMismatch.terminalState.declared = 'incomplete';
  expectCode(() => parseTaskState(unresolvedMismatch), ReasonCodes.TERMINAL_INCONSISTENT);
  const active = clone(taskState);
  active.terminalState.activeWork = true;
  expectCode(() => parseTaskState(active), ReasonCodes.TERMINAL_INCONSISTENT);
  const stale = clone(taskState);
  stale.obligations[0].evidence[0].afterChangeDigest = digest('0');
  expectCode(() => parseTaskState(stale), ReasonCodes.STALE_EVIDENCE);
  const accepted = clone(taskState);
  accepted.reviewFindings = [{
    schemaVersion: 1, id: 'finding-1', reviewerRole: 'quality', severity: 'important',
    claim: 'The implementation leaks state.', evidence: [{ ...evidence, result: 'fail' }],
    status: 'accepted', dispositionReason: '', repairChangeDigest: 'none', verificationEvidenceIds: [],
  }];
  expectCode(() => parseTaskState(accepted), ReasonCodes.TERMINAL_INCONSISTENT);
});

test('completion-gate genesis and continuation fields remain mechanically consistent', () => {
  expectCode(() => parseCompletionGateEvent({ ...gateEvent, decision: 'continue' }), ReasonCodes.INVALID_GATE_EVENT);
  const continued = {
    ...gateEvent, eventKind: 'continued', stopSequenceId: 'stop-1', continuationOrdinal: 1,
    decision: 'continue', previousEventDigest: digest('a'), reasonCode: 'unresolved_required_obligation',
  };
  assert.deepEqual(parseCompletionGateEvent(continued), continued);
  expectCode(
    () => parseCompletionGateEvent({ ...continued, continuationOrdinal: 2, frozenBound: 1 }),
    ReasonCodes.INVALID_GATE_EVENT,
  );
  const boundReached = {
    ...continued,
    continuationOrdinal: 2,
    decision: 'none',
    reasonCode: 'retry_bound_reached',
  };
  assert.deepEqual(parseCompletionGateEvent(boundReached), boundReached);
});

test('verification interfaces are closed, path-safe, integer-only, and unique by command id', () => {
  const duplicate = clone(reviewPackage);
  duplicate.verificationInterface.commands.push(clone(duplicate.verificationInterface.commands[0]));
  expectCode(() => parseReviewPackageInput(duplicate), ReasonCodes.DUPLICATE_ID);
  const nul = clone(reviewPackage);
  nul.verificationInterface.commands[0].arguments = ['ok\u0000bad'];
  expectCode(() => parseReviewPackageInput(nul), ReasonCodes.INVALID_FIELD);
  const unknown = clone(reviewPackage);
  unknown.verificationInterface.commands[0].writes = true;
  expectCode(() => parseReviewPackageInput(unknown), ReasonCodes.UNKNOWN_FIELD);
  const unsorted = clone(reviewPackage);
  unsorted.authorityManifest.allowedActions = ['read', 'execute_verification'];
  expectCode(() => parseReviewPackageInput(unsorted), ReasonCodes.INVALID_FIELD);
  const unknownAction = clone(reviewPackage);
  unknownAction.authorityManifest.allowedActions = ['delete'];
  expectCode(() => parseReviewPackageInput(unknownAction), ReasonCodes.INVALID_FIELD);
  const wildcardRoot = clone(reviewPackage);
  wildcardRoot.authorityManifest.allowedResources = ['*'];
  expectCode(() => parseReviewPackageInput(wildcardRoot), ReasonCodes.INVALID_PATH);
});

test('envelope and request self-digests are recomputed without external context', () => {
  expectCode(
    () => parseReviewPairEnvelope({ ...pairEnvelope, reviewPairEnvelopeDigest: digest('0') }),
    ReasonCodes.SELF_DIGEST_MISMATCH,
  );
  expectCode(
    () => parseReviewRequest({ ...reviewRequest, reviewRequestDigest: digest('0') }),
    ReasonCodes.SELF_DIGEST_MISMATCH,
  );
  expectCode(
    () => parseReviewPairEnvelope(pairEnvelope, { artifactDigest: digest('0') }),
    ReasonCodes.BINDING_MISMATCH,
  );
});

test('changed pair-envelope/request/artifact/obligation/interface/authority digests fail replay validation', () => {
  const context = {
    reviewerRole: 'requirements', reviewRequestDigest: reviewRequest.reviewRequestDigest,
    reviewPairEnvelopeDigest: pairEnvelope.reviewPairEnvelopeDigest, artifactDigest: digest('1'),
    obligationDigest: digest('2'), verificationInterfaceDigest: digest('3'), authorityDigest: digest('4'),
  };
  assert.deepEqual(parseReviewerVerdict(reviewerVerdict, context), reviewerVerdict);
  for (const field of [
    'reviewRequestDigest', 'reviewPairEnvelopeDigest', 'artifactDigest',
    'obligationDigest', 'verificationInterfaceDigest', 'authorityDigest',
  ]) {
    expectCode(
      () => parseReviewerVerdict({ ...reviewerVerdict, [field]: digest('0') }, context),
      ReasonCodes.BINDING_MISMATCH,
    );
  }
  const requestContext = {
    reviewPairEnvelopeDigest: pairEnvelope.reviewPairEnvelopeDigest,
    artifactDigest: digest('1'),
    obligationDigest: digest('2'),
    verificationInterfaceDigest: digest('3'),
    authorityDigest: digest('4'),
  };
  for (const field of ['artifactDigest', 'obligationDigest', 'verificationInterfaceDigest', 'authorityDigest']) {
    expectCode(
      () => parseReviewRequest(reviewRequest, { ...requestContext, [field]: digest('0') }),
      ReasonCodes.BINDING_MISMATCH,
    );
  }
});

test('invalid reviewer role and inspected-evidence rules fail closed', () => {
  expectCode(
    () => parseReviewerVerdict({ ...reviewerVerdict, reviewerRole: 'implementer' }),
    ReasonCodes.INVALID_REVIEW_ROLE,
  );
  expectCode(
    () => parseReviewerVerdict({ ...reviewerVerdict, inspectedEvidence: [] }),
    ReasonCodes.INVALID_REVIEW_VERDICT,
  );
  const inaccessible = { ...reviewerVerdict, verdict: 'indeterminate', findings: [], inspectedEvidence: [] };
  assert.deepEqual(parseReviewerVerdict(inaccessible), inaccessible);
});

test('review join is role-separated, reference-complete, and never promotes a missing role to complete', () => {
  expectCode(() => parseReviewJoinRecord({ ...joinRecord, joinState: 'complete' }), ReasonCodes.INVALID_REVIEW_JOIN);
  const duplicate = clone(joinRecord);
  duplicate.findings.push(clone(duplicate.findings[0]));
  expectCode(() => parseReviewJoinRecord(duplicate), ReasonCodes.DUPLICATE_ID);
  const missing = clone(joinRecord);
  missing.findings[0].findingId = 'missing';
  expectCode(
    () => parseReviewJoinRecord(missing, { requirementsVerdict: reviewerVerdict }),
    ReasonCodes.INVALID_REVIEW_JOIN,
  );
  expectCode(
    () => parseReviewJoinRecord(
      { ...joinRecord, requirementsVerdictDigest: digest('0') },
      { requirementsVerdict: reviewerVerdict },
    ),
    ReasonCodes.BINDING_MISMATCH,
  );
  assert.deepEqual(parseReviewJoinRecord(joinRecord, { requirementsVerdict: reviewerVerdict }), joinRecord);
});

test('contexts reject unknown fields and never turn structural parsing into semantic success', () => {
  expectCode(
    () => parseReviewerVerdict(reviewerVerdict, { reviewerRole: 'requirements', conclusion: 'pass' }),
    ReasonCodes.INVALID_CONTEXT,
  );
  expectCode(
    () => parseReviewerVerdict(reviewerVerdict, { authorityDigest: 'not-a-digest' }),
    ReasonCodes.INVALID_CONTEXT,
  );
  assert.equal(parseReviewerVerdict(reviewerVerdict).verdict, 'fail');
});
