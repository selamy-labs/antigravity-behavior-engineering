import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
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
    sentinelEvidenceIds: [], result: 'passing',
    nextAction: 'No sentinel evidence applies to this focused contract-only increment.',
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
const obligationDigest = sha256Digest(canonicalBytes([obligation]));
const verificationInterfaceDigest = sha256Digest(canonicalBytes(verificationInterface));
const authorityDigest = sha256Digest(canonicalBytes(authorityManifest));
const reviewPackage = {
  schemaVersion: 1, artifactRoot: 'artifact', artifactDigest: digest('1'),
  obligations: [obligation], obligationDigest, verificationInterface,
  verificationInterfaceDigest, authorityManifest, authorityDigest,
};
const pairEnvelope = {
  schemaVersion: 1, pairId: 'pair-1', artifactDigest: digest('1'), obligationDigest,
  verificationInterfaceDigest, authorityDigest,
  sharedPackageManifestDigest: digest('5'), reviewPairEnvelopeDigest: '',
};
pairEnvelope.reviewPairEnvelopeDigest = identityDigest(pairEnvelope, 'reviewPairEnvelopeDigest');
const reviewRequest = {
  schemaVersion: 1, requestId: 'request-requirements-1', reviewerRole: 'requirements',
  reviewPairEnvelopeDigest: pairEnvelope.reviewPairEnvelopeDigest, artifactDigest: digest('1'),
  obligationDigest, verificationInterfaceDigest, authorityDigest,
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
  obligationDigest, verificationInterfaceDigest, authorityDigest,
  findings: [reviewerFinding], verdict: 'fail', inspectedEvidence: [evidence], limitations: [],
};
const qualityRequest = {
  ...reviewRequest,
  requestId: 'request-quality-1',
  reviewerRole: 'quality',
  packageManifestDigest: digest('7'),
  reviewRequestDigest: '',
};
qualityRequest.reviewRequestDigest = identityDigest(qualityRequest, 'reviewRequestDigest');
const qualityFinding = {
  ...reviewerFinding,
  id: 'Q-1',
  claim: 'The implementation exposes an avoidable maintenance hazard.',
  affectedObligationIds: [],
};
const qualityVerdict = {
  ...reviewerVerdict,
  reviewerRole: 'quality',
  reviewRequestDigest: qualityRequest.reviewRequestDigest,
  findings: [qualityFinding],
};
const passVerdict = {
  ...qualityVerdict,
  findings: [],
  verdict: 'pass',
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
const completeJoinRecord = {
  ...joinRecord,
  qualityReviewRequestDigest: qualityRequest.reviewRequestDigest,
  qualityVerdictDigest: sha256Digest(canonicalBytes(qualityVerdict)),
  findings: [
    { schemaVersion: 1, reviewerRole: 'requirements', findingId: 'R-1' },
    { schemaVersion: 1, reviewerRole: 'quality', findingId: 'Q-1' },
  ],
  joinState: 'complete',
  limitations: [],
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
    [parseTaskState, taskState],
    [parseEvidenceEvent, evidenceEvent],
    [parseCompletionGateEvent, gateEvent],
    [parseReviewPackageInput, reviewPackage],
    [parseReviewPairEnvelope, pairEnvelope],
    [parseReviewRequest, reviewRequest],
    [parseReviewerVerdict, reviewerVerdict],
    [parseReviewJoinRecord, joinRecord],
  ];
  for (const [parser, fixture] of fixtures) {
    const parsed = parser(fixture);
    assert.notStrictEqual(parsed, fixture);
    assert.deepEqual(parsed, fixture);
    assert.match(sha256Digest(canonicalBytes(parsed)), /^sha256:[0-9a-f]{64}$/);
  }
});

test('published schemas are recursively closed and validate a durable root fixture corpus', () => {
  const schemaFixtures = {
    'task-state': taskState,
    'evidence-event': evidenceEvent,
    'completion-gate-event': gateEvent,
    'review-package-input': reviewPackage,
    'review-pair-envelope': pairEnvelope,
    'review-request': reviewRequest,
    'reviewer-verdict': reviewerVerdict,
    'reviewer-join': joinRecord,
  };
  const schemas = {};
  for (const [name, fixture] of Object.entries(schemaFixtures)) {
    const schema = JSON.parse(fs.readFileSync(path.resolve('plugin/schemas', name + '.schema.json'), 'utf8'));
    schemas[name] = schema;
    assert.equal(schema.$schema, 'https://json-schema.org/draft/2020-12/schema');
    assert.equal(schema.additionalProperties, false);
    assert.equal(schema.properties.schemaVersion.const, 1);
    const pending = [{ value: schema, path: name }];
    while (pending.length > 0) {
      const current = pending.pop();
      if (current.value && typeof current.value === 'object') {
        if (current.value.type === 'object') {
          assert.equal(current.value.additionalProperties, false, current.path);
        }
        if (current.value.type === 'string') {
          assert.equal(typeof current.value.pattern, 'string', current.path);
          assert.equal(
            new RegExp(current.value.pattern, 'u').test('\u0000'),
            false,
            current.path,
          );
        }
        for (const [key, child] of Object.entries(current.value)) {
          pending.push({ value: child, path: current.path + '/' + key });
        }
      }
    }
    assert.doesNotThrow(() => canonicalBytes(fixture));
  }

  const annotationSafeExpiry = schemas['review-package-input']
    .$defs.authorityManifest.properties.expiresAt;
  assert.ok(annotationSafeExpiry.anyOf);
  assert.equal(annotationSafeExpiry.oneOf, undefined);
  for (const [schemaName, definition] of [
    ['task-state', schemas['task-state'].$defs.evidenceReference],
    ['review-package-input', schemas['review-package-input'].$defs.evidenceReference],
    ['reviewer-verdict', schemas['reviewer-verdict'].$defs.evidenceReference],
  ]) {
    assert.equal(definition.required.includes('digest'), false, schemaName);
  }
  for (const schemaName of [
    'task-state',
    'evidence-event',
    'completion-gate-event',
    'review-package-input',
    'reviewer-verdict',
  ]) {
    assert.ok(schemas[schemaName].$defs.timestamp.allOf, schemaName);
  }

  const verifiedFinding = {
    schemaVersion: 1, id: 'schema-finding', reviewerRole: 'quality', severity: 'important',
    claim: 'The repair requires verification.', evidence: [{ ...evidence, result: 'fail' }],
    status: 'verified', dispositionReason: 'Verified by focused evidence.',
    repairChangeDigest: digest('b'), verificationEvidenceIds: ['E-1'],
  };
  const stateWithFinding = (finding) => ({ ...taskState, reviewFindings: [finding] });
  const openMaterialFinding = {
    ...verifiedFinding,
    status: 'open',
    dispositionReason: '',
    repairChangeDigest: 'none',
    verificationEvidenceIds: [],
  };
  const completeWithUnresolved = clone(taskState);
  completeWithUnresolved.obligations[0].status = 'failing';
  completeWithUnresolved.terminalState.unresolvedObligationIds = ['O-1'];
  const assumptionFixture = {
    schemaVersion: 1,
    id: 'schema-assumption',
    question: 'Which reversible default applies?',
    disposition: 'safe_default',
    decision: 'Use the evidence-backed default.',
    evidence: [evidence],
    reversible: true,
    material: false,
  };
  const scalarNulSchemaCases = [
    ['task-state', { ...taskState, intent: 'bad\u0000intent' }],
    ['evidence-event', { ...evidenceEvent, eventId: 'bad\u0000event' }],
    ['completion-gate-event', { ...gateEvent, eventId: 'bad\u0000gate' }],
    ['review-package-input', {
      ...reviewPackage,
      verificationInterface: {
        ...reviewPackage.verificationInterface,
        interfaceId: 'bad\u0000interface',
      },
    }],
    ['review-pair-envelope', { ...pairEnvelope, pairId: 'bad\u0000pair' }],
    ['review-request', { ...reviewRequest, requestId: 'bad\u0000request' }],
    ['reviewer-verdict', {
      ...reviewerVerdict,
      findings: [{ ...reviewerFinding, id: 'bad\u0000finding' }],
    }],
    ['reviewer-join', {
      ...joinRecord,
      findings: [{
        ...joinRecord.findings[0],
        findingId: 'bad\u0000reference',
      }],
    }],
  ];
  const exactDuplicateSchemaCases = [
    ['task-state', { ...taskState, assumptions: [assumptionFixture, assumptionFixture] }],
    ['task-state', { ...taskState, obligations: [obligation, obligation] }],
    ['task-state', {
      ...taskState,
      iterations: [taskState.iterations[0], taskState.iterations[0]],
    }],
    ['task-state', { ...taskState, reviewFindings: [verifiedFinding, verifiedFinding] }],
    ['review-package-input', {
      ...reviewPackage,
      obligations: [obligation, obligation],
    }],
    ['review-package-input', {
      ...reviewPackage,
      verificationInterface: {
        ...reviewPackage.verificationInterface,
        commands: [
          reviewPackage.verificationInterface.commands[0],
          reviewPackage.verificationInterface.commands[0],
        ],
      },
    }],
    ['reviewer-verdict', {
      ...reviewerVerdict,
      findings: [reviewerFinding, reviewerFinding],
    }],
    ['reviewer-join', {
      ...joinRecord,
      findings: [joinRecord.findings[0], joinRecord.findings[0]],
    }],
  ];
  const validSchemaCases = [
    ['evidence-event', { ...evidenceEvent, occurredAt: '2024-02-29T12:00:00Z' }],
    ['evidence-event', { ...evidenceEvent, occurredAt: '2000-02-29T12:00:00Z' }],
    ['evidence-event', { ...evidenceEvent, occurredAt: '2400-02-29T12:00:00Z' }],
    ['task-state', stateWithFinding(verifiedFinding)],
  ];
  const invalidSchemaCases = [
    ...Object.entries(schemaFixtures).flatMap(([name, fixture]) => [
      [name, { ...fixture, unexpected: true }],
      [name, { ...fixture, schemaVersion: 2 }],
    ]),
    ['evidence-event', { ...evidenceEvent, occurredAt: '2026-02-30T12:00:00Z' }],
    ['evidence-event', { ...evidenceEvent, occurredAt: '2025-02-29T12:00:00Z' }],
    ['evidence-event', { ...evidenceEvent, occurredAt: '1900-02-29T12:00:00Z' }],
    ['evidence-event', { ...evidenceEvent, occurredAt: '2100-02-29T12:00:00Z' }],
    ['evidence-event', { ...evidenceEvent, toolName: 'not_applicable' }],
    ['review-package-input', { ...reviewPackage, artifactRoot: '../artifact' }],
    ['reviewer-verdict', { ...reviewerVerdict, limitations: [''] }],
    ['reviewer-verdict', { ...reviewerVerdict, limitations: ['bad\u0000value'] }],
    ['reviewer-join', { ...joinRecord, limitations: [''] }],
    ['reviewer-join', { ...joinRecord, limitations: ['bad\u0000value'] }],
    ['task-state', stateWithFinding({ ...verifiedFinding, status: 'rejected', dispositionReason: '' })],
    ['task-state', stateWithFinding({
      ...verifiedFinding, status: 'repaired', repairChangeDigest: 'none',
    })],
    ['task-state', stateWithFinding({ ...verifiedFinding, verificationEvidenceIds: [] })],
    ['task-state', {
      ...taskState,
      iterations: [{
        ...taskState.iterations[0],
        impactedEvidenceIds: ['E-1', 'E-1'],
      }],
    }],
    ['task-state', {
      ...taskState,
      iterations: [{
        ...taskState.iterations[0],
        sentinelEvidenceIds: ['S-1', 'S-1'],
      }],
    }],
    ['task-state', {
      ...taskState,
      obligations: [{ ...obligation, negativeCases: [''] }],
    }],
    ['task-state', {
      ...taskState,
      terminalState: { ...taskState.terminalState, activeWork: true },
    }],
    ['task-state', completeWithUnresolved],
    ['task-state', stateWithFinding({ ...openMaterialFinding, severity: 'critical' })],
    ['task-state', stateWithFinding({ ...openMaterialFinding, severity: 'important' })],
    ['review-package-input', {
      ...reviewPackage,
      obligations: [{ ...obligation, negativeCases: [''] }],
    }],
    ['reviewer-verdict', {
      ...reviewerVerdict,
      verdict: 'indeterminate',
      inspectedEvidence: [],
    }],
    ['reviewer-join', {
      ...joinRecord,
      requirementsVerdictDigest: 'indeterminate',
    }],
    ['reviewer-join', {
      ...joinRecord,
      findings: [{ schemaVersion: 1, reviewerRole: 'quality', findingId: 'Q-1' }],
    }],
    ...scalarNulSchemaCases,
    ...exactDuplicateSchemaCases,
  ];
  // Draft 2020-12 cannot compare sibling digests, recompute canonical hashes,
  // enforce lexical array ordering, or enforce uniqueness by selected object
  // keys when the remaining content differs. Those remain parser-only rules.
  const parserOnlySchemaCases = [
    ['review-package-input', { ...reviewPackage, authorityDigest: digest('0') }],
  ];
  const payload = {
    schemas,
    cases: [
      ...Object.entries(schemaFixtures).map(([name, value]) => ({ name, value, expected: true })),
      ...validSchemaCases.map(([name, value]) => ({ name, value, expected: true })),
      ...invalidSchemaCases.map(([name, value]) => ({ name, value, expected: false })),
      ...parserOnlySchemaCases.map(([name, value]) => ({ name, value, expected: true })),
    ],
  };
  const pythonPath = path.resolve(
    'evaluator',
    '.venv',
    process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
  );
  const pythonSource = [
    'import json, sys',
    'from jsonschema import Draft202012Validator, FormatChecker',
    'payload = json.load(sys.stdin)',
    'for schema in payload["schemas"].values():',
    '    Draft202012Validator.check_schema(schema)',
    'for case in payload["cases"]:',
    '    validator = Draft202012Validator(payload["schemas"][case["name"]], format_checker=FormatChecker())',
    '    actual = not any(validator.iter_errors(case["value"]))',
    '    if actual != case["expected"]:',
    '        raise AssertionError(f"schema case {case[\'name\']} expected {case[\'expected\']} got {actual}")',
  ].join('\n');
  const validation = spawnSync(pythonPath, ['-c', pythonSource], {
    cwd: path.resolve('.'),
    encoding: 'utf8',
    input: JSON.stringify(payload),
    shell: false,
  });
  assert.equal(validation.error, undefined);
  assert.equal(validation.status, 0, validation.stderr || validation.stdout);
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
  const rootParserFixtures = [
    [parseTaskState, taskState],
    [parseEvidenceEvent, evidenceEvent],
    [parseCompletionGateEvent, gateEvent],
    [parseReviewPackageInput, reviewPackage],
    [parseReviewPairEnvelope, pairEnvelope],
    [parseReviewRequest, reviewRequest],
    [parseReviewerVerdict, reviewerVerdict],
    [parseReviewJoinRecord, joinRecord],
  ];
  for (const [parser, fixture] of rootParserFixtures) {
    expectCode(
      () => parser({ ...fixture, unexpected: true }),
      ReasonCodes.UNKNOWN_FIELD,
    );
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

test('scalar semantic strings reject NUL across all eight runtime roots', () => {
  const packageWithNul = clone(reviewPackage);
  packageWithNul.verificationInterface.interfaceId = 'bad\u0000interface';
  const verdictWithNul = clone(reviewerVerdict);
  verdictWithNul.findings[0].id = 'bad\u0000finding';
  const joinWithNul = clone(joinRecord);
  joinWithNul.findings[0].findingId = 'bad\u0000reference';
  for (const [parser, fixture] of [
    [parseTaskState, { ...taskState, intent: 'bad\u0000intent' }],
    [parseEvidenceEvent, { ...evidenceEvent, eventId: 'bad\u0000event' }],
    [parseCompletionGateEvent, { ...gateEvent, eventId: 'bad\u0000gate' }],
    [parseReviewPackageInput, packageWithNul],
    [parseReviewPairEnvelope, { ...pairEnvelope, pairId: 'bad\u0000pair' }],
    [parseReviewRequest, { ...reviewRequest, requestId: 'bad\u0000request' }],
    [parseReviewerVerdict, verdictWithNul],
    [parseReviewJoinRecord, joinWithNul],
  ]) {
    expectCode(() => parser(fixture), ReasonCodes.INVALID_FIELD);
  }
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
  const completeWithUnresolved = clone(taskState);
  completeWithUnresolved.obligations[0].status = 'failing';
  completeWithUnresolved.terminalState.unresolvedObligationIds = ['O-1'];
  expectCode(
    () => parseTaskState(completeWithUnresolved),
    ReasonCodes.TERMINAL_INCONSISTENT,
  );
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
  expectCode(
    () => parseTaskState({
      ...accepted,
      reviewFindings: [{ ...accepted.reviewFindings[0], severity: 'critical', status: 'open' }],
    }),
    ReasonCodes.TERMINAL_INCONSISTENT,
  );
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
    obligationDigest, verificationInterfaceDigest, authorityDigest,
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
    obligationDigest,
    verificationInterfaceDigest,
    authorityDigest,
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
  expectCode(
    () => parseReviewerVerdict({
      ...reviewerVerdict,
      verdict: 'indeterminate',
      inspectedEvidence: [],
    }),
    ReasonCodes.INVALID_REVIEW_VERDICT,
  );
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
  expectCode(
    () => parseReviewJoinRecord({
      ...joinRecord,
      requirementsVerdictDigest: 'indeterminate',
    }),
    ReasonCodes.INVALID_REVIEW_JOIN,
  );
  expectCode(
    () => parseReviewJoinRecord({
      ...joinRecord,
      findings: [{ schemaVersion: 1, reviewerRole: 'quality', findingId: 'Q-1' }],
    }),
    ReasonCodes.INVALID_REVIEW_JOIN,
  );
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

test('review package content digests bind obligations, verification interface, and authority', () => {
  assert.deepEqual(parseReviewPackageInput(reviewPackage), reviewPackage);
  const mutations = [
    (value) => { value.obligations[0].requirement = 'substituted requirement'; },
    (value) => { value.verificationInterface.commands[0].executable = 'substituted-node'; },
    (value) => { value.authorityManifest.manifestId = 'substituted-authority'; },
  ];
  for (const mutate of mutations) {
    const replay = clone(reviewPackage);
    mutate(replay);
    expectCode(() => parseReviewPackageInput(replay), ReasonCodes.BINDING_MISMATCH);
  }
});

test('partial join contexts bind envelope, request, and verdict identities directly to the record', () => {
  const foreignEnvelope = { ...pairEnvelope, pairId: 'pair-foreign', reviewPairEnvelopeDigest: '' };
  foreignEnvelope.reviewPairEnvelopeDigest = identityDigest(foreignEnvelope, 'reviewPairEnvelopeDigest');
  expectCode(
    () => parseReviewJoinRecord(joinRecord, { reviewPairEnvelope: foreignEnvelope }),
    ReasonCodes.BINDING_MISMATCH,
  );

  const foreignPairRequest = {
    ...reviewRequest,
    reviewPairEnvelopeDigest: foreignEnvelope.reviewPairEnvelopeDigest,
    reviewRequestDigest: '',
  };
  foreignPairRequest.reviewRequestDigest = identityDigest(foreignPairRequest, 'reviewRequestDigest');
  expectCode(
    () => parseReviewJoinRecord(joinRecord, { requirementsRequest: foreignPairRequest }),
    ReasonCodes.BINDING_MISMATCH,
  );

  expectCode(
    () => parseReviewJoinRecord(joinRecord, {
      requirementsVerdict: { ...reviewerVerdict, reviewPairEnvelopeDigest: foreignEnvelope.reviewPairEnvelopeDigest },
    }),
    ReasonCodes.BINDING_MISMATCH,
  );
  expectCode(
    () => parseReviewJoinRecord(joinRecord, {
      requirementsVerdict: { ...reviewerVerdict, reviewRequestDigest: digest('0') },
    }),
    ReasonCodes.BINDING_MISMATCH,
  );
});

test('partial joins centrally reconcile every supplied shared review subject binding', () => {
  const twoRequestRecord = {
    ...joinRecord,
    qualityReviewRequestDigest: qualityRequest.reviewRequestDigest,
  };
  const validCombinations = [
    [joinRecord, {
      reviewPairEnvelope: pairEnvelope,
      requirementsVerdict: reviewerVerdict,
    }],
    [twoRequestRecord, {
      requirementsRequest: reviewRequest,
      qualityRequest,
    }],
    [completeJoinRecord, {
      requirementsRequest: reviewRequest,
      qualityVerdict,
    }],
    [completeJoinRecord, {
      requirementsVerdict: reviewerVerdict,
      qualityVerdict,
    }],
    [completeJoinRecord, {
      reviewPairEnvelope: pairEnvelope,
      requirementsRequest: reviewRequest,
      qualityRequest,
      requirementsVerdict: reviewerVerdict,
      qualityVerdict,
    }],
  ];
  for (const [record, context] of validCombinations) {
    assert.deepEqual(parseReviewJoinRecord(record, context), record);
  }

  const combinations = {
    envelopeAndVerdict(field) {
      const verdict = { ...reviewerVerdict, [field]: digest('0') };
      return [{
        ...joinRecord,
        requirementsVerdictDigest: sha256Digest(canonicalBytes(verdict)),
      }, {
        reviewPairEnvelope: pairEnvelope,
        requirementsVerdict: verdict,
      }];
    },
    twoRequests(field) {
      const request = { ...qualityRequest, [field]: digest('0'), reviewRequestDigest: '' };
      request.reviewRequestDigest = identityDigest(request, 'reviewRequestDigest');
      return [{
        ...twoRequestRecord,
        qualityReviewRequestDigest: request.reviewRequestDigest,
      }, {
        requirementsRequest: reviewRequest,
        qualityRequest: request,
      }];
    },
    crossRoleRequestAndVerdict(field) {
      const verdict = { ...qualityVerdict, [field]: digest('0') };
      return [{
        ...completeJoinRecord,
        qualityVerdictDigest: sha256Digest(canonicalBytes(verdict)),
      }, {
        requirementsRequest: reviewRequest,
        qualityVerdict: verdict,
      }];
    },
    twoVerdicts(field) {
      const verdict = { ...qualityVerdict, [field]: digest('0') };
      return [{
        ...completeJoinRecord,
        qualityVerdictDigest: sha256Digest(canonicalBytes(verdict)),
      }, {
        requirementsVerdict: reviewerVerdict,
        qualityVerdict: verdict,
      }];
    },
  };
  for (const field of [
    'artifactDigest',
    'obligationDigest',
    'verificationInterfaceDigest',
    'authorityDigest',
  ]) {
    for (const makeCase of Object.values(combinations)) {
      const [record, context] = makeCase(field);
      expectCode(
        () => parseReviewJoinRecord(record, context),
        ReasonCodes.BINDING_MISMATCH,
      );
    }
  }
});

test('review join is the exact ordered mechanical union of every supplied role verdict', () => {
  const fullContext = {
    reviewPairEnvelope: pairEnvelope,
    requirementsRequest: reviewRequest,
    qualityRequest,
    requirementsVerdict: reviewerVerdict,
    qualityVerdict,
  };
  assert.deepEqual(parseReviewJoinRecord(completeJoinRecord, fullContext), completeJoinRecord);

  const omitted = clone(completeJoinRecord);
  omitted.findings.pop();
  expectCode(() => parseReviewJoinRecord(omitted, fullContext), ReasonCodes.INVALID_REVIEW_JOIN);

  const extra = clone(completeJoinRecord);
  extra.findings.push({ schemaVersion: 1, reviewerRole: 'quality', findingId: 'Q-extra' });
  expectCode(() => parseReviewJoinRecord(extra, fullContext), ReasonCodes.INVALID_REVIEW_JOIN);

  const reordered = clone(completeJoinRecord);
  reordered.findings.reverse();
  expectCode(() => parseReviewJoinRecord(reordered, fullContext), ReasonCodes.INVALID_REVIEW_JOIN);

  const absentRoleFinding = clone(joinRecord);
  absentRoleFinding.findings.push({ schemaVersion: 1, reviewerRole: 'quality', findingId: 'Q-1' });
  expectCode(() => parseReviewJoinRecord(absentRoleFinding), ReasonCodes.INVALID_REVIEW_JOIN);
});

test('review join structurally requires distinct role request and verdict artifacts', () => {
  expectCode(
    () => parseReviewJoinRecord({
      ...completeJoinRecord,
      qualityReviewRequestDigest: completeJoinRecord.requirementsReviewRequestDigest,
    }),
    ReasonCodes.INVALID_REVIEW_JOIN,
  );
  expectCode(
    () => parseReviewJoinRecord({
      ...completeJoinRecord,
      qualityVerdictDigest: completeJoinRecord.requirementsVerdictDigest,
    }),
    ReasonCodes.INVALID_REVIEW_JOIN,
  );
});

test('assumption evidence, passing anchors, material findings, and iterations enforce exact TaskState invariants', () => {
  const safeDefault = clone(taskState);
  safeDefault.assumptions = [{
    schemaVersion: 1,
    id: 'A-1',
    question: 'Which bounded default applies?',
    disposition: 'safe_default',
    decision: 'Use the reversible local default.',
    evidence: [],
    reversible: true,
    material: true,
  }];
  expectCode(() => parseTaskState(safeDefault), ReasonCodes.INVALID_FIELD);

  const userDirection = clone(safeDefault);
  userDirection.assumptions[0].disposition = 'user_direction';
  assert.deepEqual(parseTaskState(userDirection), userDirection);

  const noneAnchor = clone(taskState);
  noneAnchor.obligations[0].lastRelevantChangeDigest = 'none';
  noneAnchor.obligations[0].evidence[0].afterChangeDigest = 'none';
  expectCode(() => parseTaskState(noneAnchor), ReasonCodes.STALE_EVIDENCE);

  const openMaterial = clone(taskState);
  openMaterial.reviewFindings = [{
    schemaVersion: 1, id: 'finding-open', reviewerRole: 'quality', severity: 'important',
    claim: 'A material finding remains open.', evidence: [{ ...evidence, result: 'fail' }],
    status: 'open', dispositionReason: '', repairChangeDigest: 'none', verificationEvidenceIds: [],
  }];
  expectCode(() => parseTaskState(openMaterial), ReasonCodes.TERMINAL_INCONSISTENT);

  const repairedMaterial = clone(openMaterial);
  repairedMaterial.reviewFindings[0] = {
    ...repairedMaterial.reviewFindings[0],
    status: 'repaired',
    dispositionReason: 'Repair applied but not independently verified.',
    repairChangeDigest: digest('b'),
  };
  expectCode(() => parseTaskState(repairedMaterial), ReasonCodes.TERMINAL_INCONSISTENT);

  for (const finding of [
    {
      ...repairedMaterial.reviewFindings[0],
      status: 'rejected',
      dispositionReason: '',
      repairChangeDigest: 'none',
    },
    {
      ...repairedMaterial.reviewFindings[0],
      status: 'repaired',
      repairChangeDigest: 'none',
    },
    {
      ...repairedMaterial.reviewFindings[0],
      status: 'verified',
      verificationEvidenceIds: [],
    },
  ]) {
    expectCode(
      () => parseTaskState({ ...taskState, reviewFindings: [finding] }),
      ReasonCodes.INVALID_FIELD,
    );
  }

  const missingSentinelReason = clone(taskState);
  missingSentinelReason.iterations[0].nextAction = '';
  expectCode(() => parseTaskState(missingSentinelReason), ReasonCodes.INVALID_FIELD);

  const passingWithoutEvidenceIds = clone(taskState);
  passingWithoutEvidenceIds.iterations[0].impactedEvidenceIds = [];
  expectCode(() => parseTaskState(passingWithoutEvidenceIds), ReasonCodes.INVALID_FIELD);

  const duplicateImpactedEvidence = clone(taskState);
  duplicateImpactedEvidence.iterations[0].impactedEvidenceIds = ['E-1', 'E-1'];
  expectCode(() => parseTaskState(duplicateImpactedEvidence), ReasonCodes.DUPLICATE_ID);

  const duplicateSentinelEvidence = clone(taskState);
  duplicateSentinelEvidence.iterations[0].sentinelEvidenceIds = ['S-1', 'S-1'];
  expectCode(() => parseTaskState(duplicateSentinelEvidence), ReasonCodes.DUPLICATE_ID);
});

test('EvidenceEvent kind controls toolName and RFC3339 validates Gregorian leap dates', () => {
  expectCode(
    () => parseEvidenceEvent({ ...evidenceEvent, toolName: 'not_applicable' }),
    ReasonCodes.INVALID_FIELD,
  );
  const postInvocation = { ...evidenceEvent, eventKind: 'post_invocation', toolName: 'not_applicable' };
  assert.deepEqual(parseEvidenceEvent(postInvocation), postInvocation);
  expectCode(
    () => parseEvidenceEvent({ ...postInvocation, toolName: 'node' }),
    ReasonCodes.INVALID_FIELD,
  );
  expectCode(
    () => parseEvidenceEvent({ ...evidenceEvent, occurredAt: '2026-08-20T12:00:60Z' }),
    ReasonCodes.INVALID_FIELD,
  );
  assert.deepEqual(
    parseEvidenceEvent({ ...evidenceEvent, occurredAt: '2024-02-29T12:00:00Z' }),
    { ...evidenceEvent, occurredAt: '2024-02-29T12:00:00Z' },
  );
  expectCode(
    () => parseEvidenceEvent({ ...evidenceEvent, occurredAt: '2025-02-29T12:00:00Z' }),
    ReasonCodes.INVALID_FIELD,
  );
  for (const occurredAt of [
    '2000-02-29T12:00:00Z',
    '2400-02-29T12:00:00Z',
  ]) {
    assert.equal(parseEvidenceEvent({ ...evidenceEvent, occurredAt }).occurredAt, occurredAt);
  }
  for (const occurredAt of [
    '1900-02-29T12:00:00Z',
    '2100-02-29T12:00:00Z',
  ]) {
    expectCode(
      () => parseEvidenceEvent({ ...evidenceEvent, occurredAt }),
      ReasonCodes.INVALID_FIELD,
    );
  }
});

test('semantic text arrays reject empty strings and NUL across runtime domains', () => {
  expectCode(
    () => parseReviewerVerdict({ ...reviewerVerdict, limitations: [''] }),
    ReasonCodes.INVALID_FIELD,
  );
  expectCode(
    () => parseReviewJoinRecord({ ...joinRecord, limitations: [''] }),
    ReasonCodes.INVALID_FIELD,
  );
  expectCode(
    () => parseReviewerVerdict({ ...reviewerVerdict, limitations: ['bad\u0000value'] }),
    ReasonCodes.INVALID_FIELD,
  );
  expectCode(
    () => parseReviewJoinRecord({ ...joinRecord, limitations: ['bad\u0000value'] }),
    ReasonCodes.INVALID_FIELD,
  );
  const emptyTaskNegativeCase = clone(taskState);
  emptyTaskNegativeCase.obligations[0].negativeCases = [''];
  expectCode(() => parseTaskState(emptyTaskNegativeCase), ReasonCodes.INVALID_FIELD);
  const emptyPackageNegativeCase = clone(reviewPackage);
  emptyPackageNegativeCase.obligations[0].negativeCases = [''];
  expectCode(() => parseReviewPackageInput(emptyPackageNegativeCase), ReasonCodes.INVALID_FIELD);
});

test('EvidenceReference digest is optional and reviewer finding obligation IDs stay structural', () => {
  const evidenceWithoutContentDigest = { ...evidence };
  delete evidenceWithoutContentDigest.digest;
  const passWithoutContentDigest = {
    ...passVerdict,
    inspectedEvidence: [evidenceWithoutContentDigest],
  };
  assert.deepEqual(parseReviewerVerdict(passWithoutContentDigest), passWithoutContentDigest);

  const requirementsWithoutObligationIds = clone(reviewerVerdict);
  requirementsWithoutObligationIds.findings[0].affectedObligationIds = [];
  assert.deepEqual(
    parseReviewerVerdict(requirementsWithoutObligationIds),
    requirementsWithoutObligationIds,
  );
});

test('untrusted object traversal is iterative, descriptor-safe, and fails with project reason codes', () => {
  const getter = clone(taskState);
  Object.defineProperty(getter, 'intent', {
    configurable: true,
    enumerable: true,
    get() { throw new Error('accessor must not run'); },
  });
  expectCode(() => parseTaskState(getter), ReasonCodes.INVALID_FIELD);

  const symbol = clone(taskState);
  symbol[Symbol('hidden')] = true;
  expectCode(() => parseTaskState(symbol), ReasonCodes.INVALID_FIELD);

  const nonEnumerable = clone(taskState);
  Object.defineProperty(nonEnumerable, 'hidden', { enumerable: false, value: true });
  expectCode(() => parseTaskState(nonEnumerable), ReasonCodes.INVALID_FIELD);

  const arrayExtra = clone(taskState);
  arrayExtra.assumptions.extra = true;
  expectCode(() => parseTaskState(arrayExtra), ReasonCodes.INVALID_FIELD);

  const sparse = clone(taskState);
  sparse.assumptions = new Array(1);
  expectCode(() => parseTaskState(sparse), ReasonCodes.INVALID_FIELD);

  let deep = {};
  for (let index = 0; index < 12000; index += 1) {
    deep = { nested: deep };
  }
  expectCode(() => parseTaskState({ ...taskState, unknown: deep }), ReasonCodes.UNKNOWN_FIELD);

  const hostileProxy = new Proxy(taskState, {
    ownKeys() { throw new Error('reflective trap'); },
  });
  expectCode(() => parseTaskState(hostileProxy), ReasonCodes.INVALID_FIELD);

  const cyclic = clone(taskState);
  cyclic.assumptions.push(cyclic);
  expectCode(() => parseTaskState(cyclic), ReasonCodes.INVALID_FIELD);

  const nonPlain = clone(taskState);
  nonPlain.assumptions.push(new Date(now));
  expectCode(() => parseTaskState(nonPlain), ReasonCodes.INVALID_FIELD);

  const revoked = Proxy.revocable(taskState, {});
  revoked.revoke();
  expectCode(() => parseTaskState(revoked.proxy), ReasonCodes.INVALID_FIELD);

  assert.deepEqual(parseTaskState(Object.freeze(clone(taskState))), taskState);
});

test('public parsers return inert descriptor-built clones and never expose hostile inputs', () => {
  const descriptorOnlyProxy = new Proxy(taskState, {
    get() { throw new Error('property get trap must not run'); },
  });
  const descriptorParsed = parseTaskState(descriptorOnlyProxy);
  assert.deepEqual(descriptorParsed, taskState);
  assert.notStrictEqual(descriptorParsed, descriptorOnlyProxy);
  assert.equal(Object.getPrototypeOf(descriptorParsed), Object.prototype);

  const statefulProxy = new Proxy(taskState, {
    getOwnPropertyDescriptor(target, key) {
      const descriptor = Reflect.getOwnPropertyDescriptor(target, key);
      return key === 'schemaVersion' ? { ...descriptor, value: 1 } : descriptor;
    },
    get(target, key, receiver) {
      return key === 'schemaVersion' ? 2 : Reflect.get(target, key, receiver);
    },
  });
  const statefulParsed = parseTaskState(statefulProxy);
  assert.equal(statefulParsed.schemaVersion, 1);
  assert.notStrictEqual(statefulParsed, statefulProxy);

  let ownKeysCalls = 0;
  const oneShotOwnKeys = new Proxy(taskState, {
    ownKeys(target) {
      ownKeysCalls += 1;
      if (ownKeysCalls > 1) {
        throw new Error('original object was reflected twice');
      }
      return Reflect.ownKeys(target);
    },
  });
  assert.deepEqual(parseTaskState(oneShotOwnKeys), taskState);
  assert.equal(ownKeysCalls, 1);

  const contextProxy = new Proxy({ taskId: taskState.taskId }, {
    get() { throw new Error('context get trap must not run'); },
  });
  assert.deepEqual(parseTaskState(taskState, contextProxy), taskState);

  const hostileContext = new Proxy({}, {
    ownKeys() { throw new Error('context ownKeys trap'); },
  });
  expectCode(
    () => parseTaskState(taskState, hostileContext),
    ReasonCodes.INVALID_FIELD,
  );

  const mutableSource = clone(taskState);
  const stableParsed = parseTaskState(mutableSource);
  const stableDigest = sha256Digest(canonicalBytes(stableParsed));
  mutableSource.intent = 'Mutated after parsing.';
  mutableSource.obligations[0].requirement = 'Also mutated after parsing.';
  assert.equal(sha256Digest(canonicalBytes(stableParsed)), stableDigest);
  assert.notDeepEqual(stableParsed, mutableSource);

  const sharedSource = clone(taskState);
  const sharedEvidence = sharedSource.obligations[0].evidence[0];
  sharedSource.assumptions = [{
    schemaVersion: 1,
    id: 'A-shared',
    question: 'Which evidence supports this reversible default?',
    disposition: 'safe_default',
    decision: 'Use the evidence-backed default.',
    evidence: [sharedEvidence],
    reversible: true,
    material: false,
  }];
  const sharedParsed = parseTaskState(sharedSource);
  assert.notStrictEqual(
    sharedParsed.assumptions[0].evidence[0],
    sharedEvidence,
  );
  assert.strictEqual(
    sharedParsed.assumptions[0].evidence[0],
    sharedParsed.obligations[0].evidence[0],
  );
  const sharedParsedDigest = sha256Digest(canonicalBytes(sharedParsed));
  sharedEvidence.locator = 'evidence/source-mutated.txt';
  assert.equal(sha256Digest(canonicalBytes(sharedParsed)), sharedParsedDigest);

  const protoSource = clone(taskState);
  Object.defineProperty(protoSource, '__proto__', {
    value: { polluted: true },
    enumerable: true,
  });
  expectCode(() => parseTaskState(protoSource), ReasonCodes.UNKNOWN_FIELD);
  assert.equal({}.polluted, undefined);
});

test('compact shared descriptor-only DAGs require linear source reflection', () => {
  const reflectionCounts = [];
  const descriptorOnly = (target) => {
    let ownKeysCalls = 0;
    reflectionCounts.push(() => ownKeysCalls);
    return new Proxy(target, {
      ownKeys(source) {
        ownKeysCalls += 1;
        if (ownKeysCalls > 1) {
          throw new Error('shared source container was reflected more than once');
        }
        return Reflect.ownKeys(source);
      },
      get() {
        throw new Error('descriptor-only DAG must not invoke property get traps');
      },
    });
  };

  let sharedDag = descriptorOnly({ value: 'leaf' });
  for (let depth = 1; depth < 24; depth += 1) {
    sharedDag = descriptorOnly({ left: sharedDag, right: sharedDag });
  }
  expectCode(
    () => parseTaskState({ ...taskState, sharedDag }),
    ReasonCodes.UNKNOWN_FIELD,
  );
  assert.equal(reflectionCounts.length, 24);
  assert.ok(reflectionCounts.every((readCount) => readCount() === 1));
});

test('verification arrays are unique while empty command arguments remain valid', () => {
  const duplicateArtifacts = clone(reviewPackage);
  duplicateArtifacts.verificationInterface.artifacts.push(
    duplicateArtifacts.verificationInterface.artifacts[0],
  );
  expectCode(() => parseReviewPackageInput(duplicateArtifacts), ReasonCodes.DUPLICATE_ID);

  const emptyArgument = clone(reviewPackage);
  emptyArgument.verificationInterface.commands[0].arguments = [''];
  emptyArgument.verificationInterfaceDigest = sha256Digest(
    canonicalBytes(emptyArgument.verificationInterface),
  );
  assert.deepEqual(parseReviewPackageInput(emptyArgument), emptyArgument);

  const duplicateVerificationIds = clone(taskState);
  duplicateVerificationIds.reviewFindings = [{
    schemaVersion: 1, id: 'finding-verified', reviewerRole: 'quality', severity: 'important',
    claim: 'The finding was repaired and reverified.', evidence: [{ ...evidence, result: 'fail' }],
    status: 'verified', dispositionReason: 'Focused verification passed.',
    repairChangeDigest: digest('b'), verificationEvidenceIds: ['E-1', 'E-1'],
  }];
  expectCode(() => parseTaskState(duplicateVerificationIds), ReasonCodes.DUPLICATE_ID);
});

test('runtime keyed uniqueness rejects same identifiers with different content', () => {
  const assumption = {
    schemaVersion: 1,
    id: 'A-duplicate',
    question: 'Which reversible default applies?',
    disposition: 'safe_default',
    decision: 'Use the evidence-backed default.',
    evidence: [evidence],
    reversible: true,
    material: false,
  };
  expectCode(
    () => parseTaskState({
      ...taskState,
      assumptions: [assumption, { ...assumption, question: 'A different question?' }],
    }),
    ReasonCodes.DUPLICATE_ID,
  );
  expectCode(
    () => parseTaskState({
      ...taskState,
      obligations: [obligation, { ...obligation, requirement: 'Different content.' }],
    }),
    ReasonCodes.DUPLICATE_ID,
  );

  const finding = {
    schemaVersion: 1, id: 'finding-duplicate', reviewerRole: 'quality', severity: 'important',
    claim: 'The finding was verified.', evidence: [{ ...evidence, result: 'fail' }],
    status: 'verified', dispositionReason: 'Focused evidence verified the repair.',
    repairChangeDigest: digest('b'), verificationEvidenceIds: ['E-1'],
  };
  expectCode(
    () => parseTaskState({
      ...taskState,
      reviewFindings: [finding, { ...finding, claim: 'Different finding content.' }],
    }),
    ReasonCodes.DUPLICATE_ID,
  );

  const packageObligationDuplicate = clone(reviewPackage);
  packageObligationDuplicate.obligations.push({
    ...packageObligationDuplicate.obligations[0],
    requirement: 'Different package obligation content.',
  });
  expectCode(
    () => parseReviewPackageInput(packageObligationDuplicate),
    ReasonCodes.DUPLICATE_ID,
  );

  const commandDuplicate = clone(reviewPackage);
  commandDuplicate.verificationInterface.commands.push({
    ...commandDuplicate.verificationInterface.commands[0],
    executable: 'different-node',
  });
  expectCode(() => parseReviewPackageInput(commandDuplicate), ReasonCodes.DUPLICATE_ID);

  expectCode(
    () => parseReviewerVerdict({
      ...reviewerVerdict,
      findings: [
        reviewerFinding,
        { ...reviewerFinding, claim: 'Different verdict finding content.' },
      ],
    }),
    ReasonCodes.DUPLICATE_ID,
  );

  const duplicateJoinReference = clone(joinRecord);
  duplicateJoinReference.findings.push(clone(duplicateJoinReference.findings[0]));
  expectCode(() => parseReviewJoinRecord(duplicateJoinReference), ReasonCodes.DUPLICATE_ID);
});

test('valid pass verdict, verified material closure, and full two-role join are accepted', () => {
  assert.deepEqual(parseReviewerVerdict(passVerdict), passVerdict);

  const verified = clone(taskState);
  verified.reviewFindings = [{
    schemaVersion: 1, id: 'finding-verified', reviewerRole: 'quality', severity: 'important',
    claim: 'The finding was repaired and reverified.', evidence: [{ ...evidence, result: 'fail' }],
    status: 'verified', dispositionReason: 'Focused verification passed.',
    repairChangeDigest: digest('b'), verificationEvidenceIds: ['E-1'],
  }];
  assert.deepEqual(parseTaskState(verified), verified);

  assert.deepEqual(parseReviewJoinRecord(completeJoinRecord, {
    reviewPairEnvelope: pairEnvelope,
    requirementsRequest: reviewRequest,
    qualityRequest,
    requirementsVerdict: reviewerVerdict,
    qualityVerdict,
  }), completeJoinRecord);
});
