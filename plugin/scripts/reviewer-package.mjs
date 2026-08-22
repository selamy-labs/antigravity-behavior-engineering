import fs from "node:fs/promises";
import fsSync, { constants } from "node:fs";
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
const REQUIRED_REVIEW_ACTIONS = ["execute_verification", "read", "write_verdict"];
const packageInputs = new Map();
const publishedPackages = new Map();
const PACKAGE_FILE_NAMES = [
  "approved-obligations.json",
  "artifact-manifest.json",
  "artifact-or-diff.patch",
  "authority.json",
  "review-pair-envelope.json",
  "review-request.json",
  "verification-interface.json",
];
const MANIFEST_FILE_NAMES = PACKAGE_FILE_NAMES.filter(
  (name) => !["artifact-manifest.json", "review-request.json"].includes(name),
);

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

const assertNoSymlinkSync = (target) => {
  let cursor = path.resolve(target);
  while (true) {
    try {
      if (fsSync.lstatSync(cursor).isSymbolicLink()) {
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
  const workspaceRoot = await fs.realpath(process.cwd());
  const absolute = path.resolve(workspaceRoot, artifactRoot);
  if (!isContained(workspaceRoot, absolute)) {
    throw new ContractValidationError(ReasonCodes.INVALID_PATH, "$.artifactRoot");
  }
  await assertNoSymlink(absolute);
  const handle = await fs.open(absolute, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const stat = await handle.stat();
    const openedPath = await fs.realpath(`/proc/self/fd/${handle.fd}`);
    if (!stat.isFile() || !isContained(workspaceRoot, openedPath)) {
      throw new ContractValidationError(ReasonCodes.INVALID_PATH, "$.artifactRoot");
    }
    const bytes = await handle.readFile();
    if (sha256Digest(bytes) !== expectedDigest) {
      throw new ContractValidationError(ReasonCodes.BINDING_MISMATCH, "$.artifactDigest");
    }
    return bytes;
  } finally {
    await handle.close();
  }
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

const isContained = (root, target) => {
  const relative = path.relative(root, target);
  return relative === "" || (!relative.startsWith(`..${path.sep}`) && relative !== ".." && !path.isAbsolute(relative));
};

const openOutputRoot = async (root) => {
  if (typeof root !== "string" || root.length === 0) {
    throw new ContractValidationError(ReasonCodes.INVALID_PATH, "$.root");
  }
  const absolute = path.resolve(root);
  await assertNoSymlink(absolute);
  await fs.mkdir(absolute, { recursive: true });
  await assertNoSymlink(absolute);
  const handle = await fs.open(
    absolute,
    constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW,
  );
  try {
    if (!(await handle.stat()).isDirectory()) {
      throw new ContractValidationError(ReasonCodes.INVALID_PATH, "$.root");
    }
    const anchoredPath = `/proc/self/fd/${handle.fd}`;
    await fs.realpath(anchoredPath);
    return { handle, anchoredPath };
  } catch (error) {
    await handle.close();
    throw error;
  }
};

const validateAuthority = (input) => {
  if (!REQUIRED_REVIEW_ACTIONS.every(
    (action) => input.authorityManifest.allowedActions.includes(action),
  )) {
    throw new ContractValidationError(
      ReasonCodes.INVALID_FIELD,
      "$.authorityManifest.allowedActions",
    );
  }
  if (input.authorityManifest.expiresAt !== "not_applicable"
    && Date.parse(input.authorityManifest.expiresAt) <= Date.now()) {
    throw new ContractValidationError(ReasonCodes.INVALID_FIELD, "$.authorityManifest.expiresAt");
  }
};

const validatePublishedPackage = async (finalPath, files) => {
  const stat = await fs.lstat(finalPath);
  if (!stat.isDirectory() || stat.isSymbolicLink()) {
    throw new TypeError(`symlink package directory is not allowed: ${finalPath}`);
  }
  const packageHandle = await fs.open(
    finalPath,
    constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW,
  );
  try {
    const anchoredPath = `/proc/self/fd/${packageHandle.fd}`;
    const actualNames = (await fs.readdir(anchoredPath)).sort();
    const expectedNames = Object.keys(files).sort();
    if (actualNames.length !== expectedNames.length
      || actualNames.some((name, index) => name !== expectedNames[index])) {
      throw new ContractValidationError(ReasonCodes.BINDING_MISMATCH, "$.packageManifestDigest");
    }
    for (const [name, bytes] of Object.entries(files)) {
      const entryPath = path.join(anchoredPath, name);
      if ((await fs.lstat(entryPath)).isSymbolicLink()) {
        throw new TypeError(`symlink package entry is not allowed: ${name}`);
      }
      const entryHandle = await fs.open(entryPath, constants.O_RDONLY | constants.O_NOFOLLOW);
      try {
        if (!(await entryHandle.stat()).isFile() || !(await entryHandle.readFile()).equals(bytes)) {
          throw new ContractValidationError(ReasonCodes.BINDING_MISMATCH, "$.packageManifestDigest");
        }
      } finally {
        await entryHandle.close();
      }
    }
  } finally {
    await packageHandle.close();
  }
};

const publishPackage = async (root, directoryName, files) => {
  const { handle, anchoredPath } = await openOutputRoot(root);
  const finalPath = path.join(anchoredPath, directoryName);
  let stagingPath;
  try {
    stagingPath = await fs.mkdtemp(path.join(anchoredPath, ".review-package-"));
    for (const [name, bytes] of Object.entries(files)) {
      await fs.writeFile(path.join(stagingPath, name), bytes, { flag: "wx" });
    }
    try {
      await fs.rename(stagingPath, finalPath);
      stagingPath = undefined;
      return;
    } catch (error) {
      if (!["EEXIST", "ENOTEMPTY"].includes(error?.code)) {
        throw error;
      }
    }
    await fs.rm(stagingPath, { recursive: true, force: true });
    stagingPath = undefined;
    await validatePublishedPackage(finalPath, files);
  } finally {
    if (stagingPath !== undefined) {
      await fs.rm(stagingPath, { recursive: true, force: true }).catch(() => {});
    }
    await handle.close();
  }
};

export const buildReviewPairEnvelope = (value) => {
  const input = parseReviewPackageInput(value);
  validateAuthority(input);
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
  validateAuthority(input);
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

  const directoryName = `${role}-${parsedRequest.reviewRequestDigest.slice("sha256:".length)}`;
  await publishPackage(root, directoryName, {
    ...visibleFiles,
    "artifact-manifest.json": jsonBytes(manifest),
    "review-request.json": jsonBytes(parsedRequest),
  });
  publishedPackages.set(parsedRequest.reviewRequestDigest, {
    directoryName,
    root: path.resolve(root),
  });
  return parsedRequest;
};

const readPackageSnapshot = (request, envelope) => {
  const published = publishedPackages.get(request.reviewRequestDigest);
  if (published === undefined) {
    throw new ContractValidationError(ReasonCodes.BINDING_MISMATCH, "$.reviewRequestDigest");
  }
  assertNoSymlinkSync(published.root);
  const rootHandle = fsSync.openSync(
    published.root,
    constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW,
  );
  let packageHandle;
  try {
    packageHandle = fsSync.openSync(
      path.join(`/proc/self/fd/${rootHandle}`, published.directoryName),
      constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW,
    );
    const packageRoot = `/proc/self/fd/${packageHandle}`;
    const names = fsSync.readdirSync(packageRoot).sort();
    if (names.length !== PACKAGE_FILE_NAMES.length
      || names.some((name, index) => name !== PACKAGE_FILE_NAMES[index])) {
      throw new ContractValidationError(ReasonCodes.BINDING_MISMATCH, "$.packageManifestDigest");
    }
    const bytesByName = {};
    for (const name of names) {
      const entryHandle = fsSync.openSync(
        path.join(packageRoot, name),
        constants.O_RDONLY | constants.O_NOFOLLOW,
      );
      try {
        if (!fsSync.fstatSync(entryHandle).isFile()) {
          throw new ContractValidationError(
            ReasonCodes.BINDING_MISMATCH,
            "$.packageManifestDigest",
          );
        }
        bytesByName[name] = fsSync.readFileSync(entryHandle);
      } finally {
        fsSync.closeSync(entryHandle);
      }
    }
    if (!bytesByName["review-request.json"].equals(jsonBytes(request))
      || !bytesByName["review-pair-envelope.json"].equals(jsonBytes(envelope))) {
      throw new ContractValidationError(ReasonCodes.BINDING_MISMATCH, "$.reviewRequestDigest");
    }
    const manifest = JSON.parse(bytesByName["artifact-manifest.json"].toString("utf8"));
    const manifestNames = Object.keys(manifest).sort();
    if (manifestNames.length !== MANIFEST_FILE_NAMES.length
      || manifestNames.some((name, index) => name !== MANIFEST_FILE_NAMES[index])) {
      throw new ContractValidationError(ReasonCodes.BINDING_MISMATCH, "$.packageManifestDigest");
    }
    for (const name of MANIFEST_FILE_NAMES) {
      if (manifest[name] !== sha256Digest(bytesByName[name])) {
        throw new ContractValidationError(ReasonCodes.BINDING_MISMATCH, "$.packageManifestDigest");
      }
    }
    if (sha256Digest(canonicalBytes(manifest)) !== request.packageManifestDigest
      || !bytesByName["artifact-manifest.json"].equals(jsonBytes(manifest))) {
      throw new ContractValidationError(ReasonCodes.BINDING_MISMATCH, "$.packageManifestDigest");
    }
    return {
      reviewRequestDigest: request.reviewRequestDigest,
      reviewerRole: request.reviewerRole,
      packageManifestDigest: request.packageManifestDigest,
      fileNames: names,
    };
  } finally {
    if (packageHandle !== undefined) {
      fsSync.closeSync(packageHandle);
    }
    fsSync.closeSync(rootHandle);
  }
};

export const validatePublishedReviewPair = (
  envelopeValue,
  requirementsRequestValue,
  qualityRequestValue,
) => {
  const envelope = parseReviewPairEnvelope(envelopeValue);
  const requirementsRequest = parseReviewRequest(requirementsRequestValue, {
    reviewerRole: "requirements",
    reviewPairEnvelopeDigest: envelope.reviewPairEnvelopeDigest,
    artifactDigest: envelope.artifactDigest,
    obligationDigest: envelope.obligationDigest,
    verificationInterfaceDigest: envelope.verificationInterfaceDigest,
    authorityDigest: envelope.authorityDigest,
  });
  const qualityRequest = parseReviewRequest(qualityRequestValue, {
    reviewerRole: "quality",
    reviewPairEnvelopeDigest: envelope.reviewPairEnvelopeDigest,
    artifactDigest: envelope.artifactDigest,
    obligationDigest: envelope.obligationDigest,
    verificationInterfaceDigest: envelope.verificationInterfaceDigest,
    authorityDigest: envelope.authorityDigest,
  });
  return {
    schemaVersion: 1,
    reviewPairEnvelopeDigest: envelope.reviewPairEnvelopeDigest,
    packageFilePolicy: PACKAGE_FILE_NAMES,
    requirements: readPackageSnapshot(requirementsRequest, envelope),
    quality: readPackageSnapshot(qualityRequest, envelope),
    competingReviewArtifactsPresent: false,
  };
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
