import { canonicalBytes, sha256Digest } from "../../packages/contracts/src/canonical-json.mjs";
import {
  ContractValidationError,
  parseReviewJoinRecord,
  parseReviewPairEnvelope,
  parseReviewRequest,
  parseReviewerVerdict,
} from "../../packages/contracts/src/runtime-contracts.mjs";
import { validatePublishedReviewPair } from "./reviewer-package.mjs";

const REVIEW_ROLES = ["requirements", "quality"];

const parseRequest = (value, role, envelope) => parseReviewRequest(value, {
  reviewerRole: role,
  reviewPairEnvelopeDigest: envelope.reviewPairEnvelopeDigest,
  artifactDigest: envelope.artifactDigest,
  obligationDigest: envelope.obligationDigest,
  verificationInterfaceDigest: envelope.verificationInterfaceDigest,
  authorityDigest: envelope.authorityDigest,
});

const validateTerminalVerdict = (value, role, request) => {
  try {
    return {
      verdict: parseReviewerVerdict(value, {
        reviewerRole: role,
        reviewRequestDigest: request.reviewRequestDigest,
        reviewPairEnvelopeDigest: request.reviewPairEnvelopeDigest,
        artifactDigest: request.artifactDigest,
        obligationDigest: request.obligationDigest,
        verificationInterfaceDigest: request.verificationInterfaceDigest,
        authorityDigest: request.authorityDigest,
      }),
      limitation: undefined,
    };
  } catch (error) {
    if (!(error instanceof ContractValidationError)) {
      throw error;
    }
    return {
      verdict: undefined,
      limitation: `${role} verdict indeterminate: ${error.reasonCode}`,
    };
  }
};

const separationEvidence = (envelope, requirementsRequest, qualityRequest) => ({
  schemaVersion: 1,
  publishedPackageEvidence: validatePublishedReviewPair(
    envelope,
    requirementsRequest,
    qualityRequest,
  ),
  invocationIsolation: "distinct role-scoped content-addressed package roots",
  joinTiming: "after both terminal outputs",
});

export const joinReviewerVerdicts = (
  envelopeValue,
  requirementsRequestValue,
  requirementsVerdictValue,
  qualityRequestValue,
  qualityVerdictValue,
) => {
  const envelope = parseReviewPairEnvelope(envelopeValue);
  const requirementsRequest = parseRequest(requirementsRequestValue, "requirements", envelope);
  const qualityRequest = parseRequest(qualityRequestValue, "quality", envelope);
  const terminal = {
    requirements: validateTerminalVerdict(
      requirementsVerdictValue,
      "requirements",
      requirementsRequest,
    ),
    quality: validateTerminalVerdict(qualityVerdictValue, "quality", qualityRequest),
  };
  const findings = REVIEW_ROLES.flatMap((role) => (
    terminal[role].verdict?.findings.map(({ id }) => ({
      schemaVersion: 1,
      reviewerRole: role,
      findingId: id,
    })) ?? []
  ));
  const limitations = REVIEW_ROLES.flatMap((role) => {
    if (terminal[role].limitation !== undefined) {
      return [terminal[role].limitation];
    }
    return terminal[role].verdict.limitations.map(
      (limitation) => `${role} verdict limitation: ${limitation}`,
    );
  });
  const record = {
    schemaVersion: 1,
    reviewPairEnvelopeDigest: envelope.reviewPairEnvelopeDigest,
    requirementsReviewRequestDigest: requirementsRequest.reviewRequestDigest,
    qualityReviewRequestDigest: qualityRequest.reviewRequestDigest,
    requirementsVerdictDigest: terminal.requirements.verdict === undefined
      ? "indeterminate"
      : sha256Digest(canonicalBytes(terminal.requirements.verdict)),
    qualityVerdictDigest: terminal.quality.verdict === undefined
      ? "indeterminate"
      : sha256Digest(canonicalBytes(terminal.quality.verdict)),
    roleSeparationEvidenceDigest: sha256Digest(canonicalBytes(
      separationEvidence(envelope, requirementsRequest, qualityRequest),
    )),
    findings,
    joinState: REVIEW_ROLES.every((role) => terminal[role].verdict !== undefined)
      ? "complete"
      : "indeterminate",
    limitations,
  };
  const context = {
    reviewPairEnvelope: envelope,
    requirementsRequest,
    qualityRequest,
    ...(terminal.requirements.verdict === undefined
      ? {}
      : { requirementsVerdict: terminal.requirements.verdict }),
    ...(terminal.quality.verdict === undefined
      ? {}
      : { qualityVerdict: terminal.quality.verdict }),
  };
  return parseReviewJoinRecord(record, context);
};
