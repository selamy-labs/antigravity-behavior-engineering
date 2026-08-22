import fs from "node:fs/promises";
import path from "node:path";

import { canonicalBytes, sha256Digest } from "../../packages/contracts/src/canonical-json.mjs";
import {
  ContractValidationError,
  ReasonCodes,
  parseReviewPackageInput,
  parseReviewPairEnvelope,
  parseReviewRequest,
  parseReviewerVerdict,
} from "../../packages/contracts/src/runtime-contracts.mjs";

const REVIEW_ROLES = new Set(["requirements", "quality"]);
const packageInputs = new Map();

const jsonBytes = (value) => Buffer.concat([canonicalBytes(value), Buffer.from("\n")]);
const selfDigest = (value, field) => sha256Digest(canonicalBytes(
  Object.fromEntries(Object.entries(value).filter(([key]) => key !== field)),
));

const assertNoSymlink = async (target) => {
  let cursor = path.resolve(target);
  while (true) {
    try {
      if ((await fs.lstat(cursor)).isSymbolicLink()) {
        throw new TypeError(`symlink path is not allowed: ${cursor}`);
      }
    } catch (error) {
      if (error?.code !== "ENOENT") {
        throw error;
      }
    }
    const parent = path.dirname(cursor);
    if (parent === cursor) {
      return;
    }
    cursor = parent;
  }
};

const readArtifact = async (artifactRoot, expectedDigest) => {
  const absolute = path.resolve(process.cwd(), artifactRoot);
  const relative = path.relative(process.cwd(), absolute);
  if (relative.startsWith(`..${path.sep}`) || relative === ".." || path.isAbsolute(relative)) {
    throw new ContractValidationError(ReasonCodes.INVALID_PATH, "$.artifactRoot");
  }
  await assertNoSymlink(absolute);
  const stat = await fs.stat(absolute);
  if (!stat.isFile()) {
    throw new ContractValidationError(ReasonCodes.INVALID_PATH, "$.artifactRoot");
  }
  const bytes = await fs.readFile(absolute);
  if (sha256Digest(bytes) !== expectedDigest) {
    throw new ContractValidationError(ReasonCodes.BINDING_MISMATCH, "$.artifactDigest");
  }
  return bytes;
};

const commonFiles = (input, artifactBytes) => ({
  "approved-obligations.json": jsonBytes(input.obligations),
  "artifact-or-diff.patch": artifactBytes,
  "authority.json": jsonBytes(input.authorityManifest),
  "verification-interface.json": jsonBytes(input.verificationInterface),
});

const fileManifest = (files) => Object.fromEntries(
  Object.entries(files)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([name, bytes]) => [name, sha256Digest(bytes)]),
);

export const buildReviewPairEnvelope = (value) => {
  const input = parseReviewPackageInput(value);
  const sharedPackageManifest = {
    "approved-obligations.json": sha256Digest(jsonBytes(input.obligations)),
    "artifact-or-diff.patch": input.artifactDigest,
    "authority.json": sha256Digest(jsonBytes(input.authorityManifest)),
    "verification-interface.json": sha256Digest(jsonBytes(input.verificationInterface)),
  };
  const sharedPackageManifestDigest = sha256Digest(canonicalBytes(sharedPackageManifest));
  const envelope = {
    schemaVersion: 1,
    pairId: `pair-${sharedPackageManifestDigest.slice("sha256:".length, "sha256:".length + 24)}`,
    artifactDigest: input.artifactDigest,
    obligationDigest: input.obligationDigest,
    verificationInterfaceDigest: input.verificationInterfaceDigest,
    authorityDigest: input.authorityDigest,
    sharedPackageManifestDigest,
    reviewPairEnvelopeDigest: "",
  };
  envelope.reviewPairEnvelopeDigest = selfDigest(envelope, "reviewPairEnvelopeDigest");
  const parsed = parseReviewPairEnvelope(envelope);
  packageInputs.set(parsed.reviewPairEnvelopeDigest, input);
  return parsed;
};

export const buildReviewPackage = async (value, role, root) => {
  if (!REVIEW_ROLES.has(role)) {
    throw new ContractValidationError(ReasonCodes.INVALID_REVIEW_ROLE, "$.reviewerRole");
  }
  const envelope = parseReviewPairEnvelope(value);
  const input = packageInputs.get(envelope.reviewPairEnvelopeDigest);
  if (!input) {
    throw new ContractValidationError(ReasonCodes.BINDING_MISMATCH, "$.reviewPairEnvelopeDigest");
  }
  await assertNoSymlink(root);
  const artifactBytes = await readArtifact(input.artifactRoot, input.artifactDigest);
  const common = commonFiles(input, artifactBytes);
  const actualSharedDigest = sha256Digest(canonicalBytes(fileManifest(common)));
  if (actualSharedDigest !== envelope.sharedPackageManifestDigest) {
    throw new ContractValidationError(ReasonCodes.BINDING_MISMATCH, "$.sharedPackageManifestDigest");
  }

  const envelopeBytes = jsonBytes(envelope);
  const visibleFiles = { ...common, "review-pair-envelope.json": envelopeBytes };
  const manifest = fileManifest(visibleFiles);
  const request = {
    schemaVersion: 1,
    requestId: `request-${role}-${envelope.reviewPairEnvelopeDigest.slice("sha256:".length, "sha256:".length + 16)}`,
    reviewerRole: role,
    reviewPairEnvelopeDigest: envelope.reviewPairEnvelopeDigest,
    artifactDigest: envelope.artifactDigest,
    obligationDigest: envelope.obligationDigest,
    verificationInterfaceDigest: envelope.verificationInterfaceDigest,
    authorityDigest: envelope.authorityDigest,
    packageManifestDigest: sha256Digest(canonicalBytes(manifest)),
    reviewRequestDigest: "",
  };
  request.reviewRequestDigest = selfDigest(request, "reviewRequestDigest");
  const parsedRequest = parseReviewRequest(request, {
    reviewerRole: role,
    reviewPairEnvelopeDigest: envelope.reviewPairEnvelopeDigest,
    artifactDigest: envelope.artifactDigest,
    obligationDigest: envelope.obligationDigest,
    verificationInterfaceDigest: envelope.verificationInterfaceDigest,
    authorityDigest: envelope.authorityDigest,
  });

  const packageRoot = path.join(
    path.resolve(root),
    `${role}-${parsedRequest.reviewRequestDigest.slice("sha256:".length)}`,
  );
  await fs.mkdir(path.resolve(root), { recursive: true });
  await fs.mkdir(packageRoot);
  for (const [name, bytes] of Object.entries(visibleFiles)) {
    await fs.writeFile(path.join(packageRoot, name), bytes, { flag: "wx" });
  }
  await fs.writeFile(path.join(packageRoot, "artifact-manifest.json"), jsonBytes(manifest), { flag: "wx" });
  await fs.writeFile(path.join(packageRoot, "review-request.json"), jsonBytes(parsedRequest), { flag: "wx" });
  return parsedRequest;
};

export const validateReviewerVerdict = (requestValue, verdictValue) => {
  const request = parseReviewRequest(requestValue);
  return parseReviewerVerdict(verdictValue, {
    reviewerRole: request.reviewerRole,
    reviewRequestDigest: request.reviewRequestDigest,
    reviewPairEnvelopeDigest: request.reviewPairEnvelopeDigest,
    artifactDigest: request.artifactDigest,
    obligationDigest: request.obligationDigest,
    verificationInterfaceDigest: request.verificationInterfaceDigest,
    authorityDigest: request.authorityDigest,
  });
};
