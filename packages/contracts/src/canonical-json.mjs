import { createHash, randomUUID } from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';

const MAX_SAFE_INTEGER = Number.MAX_SAFE_INTEGER;
const encoder = new TextEncoder();

const assertWellFormedUnicode = (value) => {
  for (let index = 0; index < value.length; index += 1) {
    const codeUnit = value.charCodeAt(index);
    if (codeUnit >= 0xd800 && codeUnit <= 0xdbff) {
      const next = value.charCodeAt(index + 1);
      if (next < 0xdc00 || next > 0xdfff) {
        throw new TypeError('JSON strings must not contain unpaired surrogates');
      }
      index += 1;
    } else if (codeUnit >= 0xdc00 && codeUnit <= 0xdfff) {
      throw new TypeError('JSON strings must not contain unpaired surrogates');
    }
  }
};

const isPlainObject = (value) => {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    return false;
  }
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
};

const serialize = (value, ancestors) => {
  if (value === null) {
    return 'null';
  }
  if (typeof value === 'string') {
    assertWellFormedUnicode(value);
    return JSON.stringify(value);
  }
  if (typeof value === 'boolean') {
    return value ? 'true' : 'false';
  }
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) {
      throw new TypeError('JSON numbers must be finite');
    }
    if (!Number.isSafeInteger(value)) {
      throw new TypeError('JSON numbers must be safe integers');
    }
    return String(value);
  }
  if (Array.isArray(value)) {
    if (ancestors.has(value)) {
      throw new TypeError('JSON values must not be cyclic');
    }
    ancestors.add(value);
    const serialized = '[' + value.map((item) => serialize(item, ancestors)).join(',') + ']';
    ancestors.delete(value);
    return serialized;
  }
  if (isPlainObject(value)) {
    if (ancestors.has(value)) {
      throw new TypeError('JSON values must not be cyclic');
    }
    ancestors.add(value);
    const keys = Object.keys(value).sort();
    const serialized = '{' + keys.map((key) => {
      assertWellFormedUnicode(key);
      return JSON.stringify(key) + ':' + serialize(value[key], ancestors);
    }).join(',') + '}';
    ancestors.delete(value);
    return serialized;
  }
  throw new TypeError('unsupported JSON value; expected null, boolean, string, safe integer, array, or plain object');
};

export const canonicalBytes = (value) => encoder.encode(serialize(value, new WeakSet()));

export const sha256Digest = (bytes) => {
  if (!(bytes instanceof Uint8Array)) {
    throw new TypeError('sha256Digest expects Uint8Array bytes');
  }
  return 'sha256:' + createHash('sha256').update(bytes).digest('hex');
};

export const writeCanonicalAtomic = async (root, relativePath, value) => {
  if (typeof root !== 'string' || root.length === 0) {
    throw new TypeError('root must be a non-empty path string');
  }
  if (typeof relativePath !== 'string' || relativePath.length === 0 || path.isAbsolute(relativePath) || relativePath.includes('\u0000')) {
    throw new TypeError('relativePath must be a non-empty relative path');
  }
  const pathSegments = relativePath.split(/[\\/]/u);
  if (pathSegments.some((segment) => segment.length === 0 || segment === '.' || segment === '..')) {
    throw new TypeError('relativePath must not contain traversal or empty segments');
  }

  const canonicalRoot = await fs.realpath(root);
  const rootStatus = await fs.stat(canonicalRoot);
  if (!rootStatus.isDirectory()) {
    throw new TypeError('root must be a directory');
  }

  let parent = canonicalRoot;
  for (const segment of pathSegments.slice(0, -1)) {
    parent = path.join(parent, segment);
    try {
      const status = await fs.lstat(parent);
      if (status.isSymbolicLink()) {
        throw new TypeError('relativePath must not traverse a symlink');
      }
      if (!status.isDirectory()) {
        throw new TypeError('relativePath parent must be a directory');
      }
    } catch (error) {
      if (error && error.code !== 'ENOENT') {
        throw error;
      }
      try {
        await fs.mkdir(parent);
      } catch (mkdirError) {
        if (!mkdirError || mkdirError.code !== 'EEXIST') {
          throw mkdirError;
        }
      }
      const createdStatus = await fs.lstat(parent);
      if (createdStatus.isSymbolicLink() || !createdStatus.isDirectory()) {
        throw new TypeError('relativePath parent escaped the root');
      }
    }
  }

  const destination = path.join(parent, pathSegments.at(-1));
  const relativeDestination = path.relative(canonicalRoot, destination);
  if (relativeDestination === '' || relativeDestination.startsWith('..' + path.sep) || path.isAbsolute(relativeDestination)) {
    throw new TypeError('relativePath escaped the root');
  }
  try {
    if ((await fs.lstat(destination)).isSymbolicLink()) {
      throw new TypeError('relativePath must not target a symlink');
    }
  } catch (error) {
    if (error && error.code !== 'ENOENT') {
      throw error;
    }
  }

  const bytes = canonicalBytes(value);
  const temporaryPath = path.join(parent, '.' + pathSegments.at(-1) + '.' + randomUUID() + '.tmp');
  let handle;
  try {
    handle = await fs.open(temporaryPath, 'wx', 0o600);
    await handle.writeFile(bytes);
    await handle.sync();
    await handle.close();
    handle = undefined;
    await fs.rename(temporaryPath, destination);
    const directoryHandle = await fs.open(parent, 'r');
    try {
      await directoryHandle.sync();
    } finally {
      await directoryHandle.close();
    }
    return sha256Digest(bytes);
  } finally {
    if (handle) {
      await handle.close();
    }
    await fs.rm(temporaryPath, { force: true });
  }
};
