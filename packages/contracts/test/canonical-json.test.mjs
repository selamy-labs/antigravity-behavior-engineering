import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

import { canonicalBytes, sha256Digest } from '../src/canonical-json.mjs';
import { writeCanonicalAtomic } from '../src/fs-boundary.mjs';

const digest = (bytes) => 'sha256:' + createHash('sha256').update(bytes).digest('hex');

const temporaryRoot = async (t) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'abe-canonical-'));
  t.after(() => fs.rm(root, { force: true, recursive: true }));
  return root;
};

test('canonical bytes sort object keys and preserve UTF-8 values', () => {
  const value = {
    z: null,
    a: [true, false, -7, 9007199254740991],
    message: 'café ☕',
  };

  assert.equal(
    new TextDecoder().decode(canonicalBytes(value)),
    '{"a":[true,false,-7,9007199254740991],"message":"café ☕","z":null}',
  );
  assert.deepEqual(canonicalBytes({ b: 2, a: 1 }), canonicalBytes({ a: 1, b: 2 }));
  assert.equal(
    new TextDecoder().decode(canonicalBytes({ '': 1, '😀': 2 })),
    '{"😀":2,"":1}',
  );
  assert.equal(
    new TextDecoder().decode(canonicalBytes([-Number.MAX_SAFE_INTEGER, Number.MAX_SAFE_INTEGER])),
    '[-9007199254740991,9007199254740991]',
  );
  assert.equal(sha256Digest(canonicalBytes({ b: 2, a: 1 })), 'sha256:43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777');
});

test('canonical bytes reject values outside the shared integer JSON subset', () => {
  for (const value of [NaN, Infinity, -Infinity, 1.5, 9007199254740992, -9007199254740992]) {
    assert.throws(() => canonicalBytes(value), /integer|finite|safe/i);
  }
  for (const value of [undefined, BigInt(1), new Date(), { nested: undefined }]) {
    assert.throws(() => canonicalBytes(value), /JSON|unsupported|plain/i);
  }
  for (const value of [new Array(1), new Array(2)]) {
    assert.throws(() => canonicalBytes(value), /sparse/i);
  }
  for (const value of ['\ud800', { '\udc00': 'invalid key' }]) {
    assert.throws(() => canonicalBytes(value), /surrogate/i);
  }
});

test('canonical digest consumes exact bytes and uses a lowercase SHA-256 prefix', () => {
  const bytes = new TextEncoder().encode('{"message":"café ☕"}');
  const actual = sha256Digest(bytes);

  assert.equal(actual, digest(bytes));
  assert.match(actual, /^sha256:[0-9a-f]{64}$/);
});

test('atomic write rejects traversal and absolute paths without escaping the root', async (t) => {
  const root = await temporaryRoot(t);
  const outside = path.join(path.dirname(root), 'abe-canonical-escape.json');
  t.after(() => fs.rm(outside, { force: true }));

  for (const relativePath of ['../abe-canonical-escape.json', '/tmp/abe-canonical-escape.json', 'nested/../../abe-canonical-escape.json']) {
    await assert.rejects(writeCanonicalAtomic(root, relativePath, { ok: true }), /relative|traversal|escape/i);
  }
  await assert.rejects(fs.access(outside));
  assert.deepEqual(await fs.readdir(root), []);
});

test('atomic write refuses symlink traversal', async (t) => {
  const root = await temporaryRoot(t);
  const outside = await fs.mkdtemp(path.join(os.tmpdir(), 'abe-canonical-outside-'));
  t.after(() => fs.rm(outside, { force: true, recursive: true }));
  await fs.symlink(outside, path.join(root, 'link'));

  await assert.rejects(writeCanonicalAtomic(root, 'link/escape.json', { ok: true }), /symlink|escape/i);
  assert.deepEqual(await fs.readdir(outside), []);
});

test('atomic write leaves no temporary file after a rename failure', async (t) => {
  const root = await temporaryRoot(t);
  await fs.mkdir(path.join(root, 'destination'));

  await assert.rejects(writeCanonicalAtomic(root, 'destination', { complete: true }));
  assert.deepEqual(await fs.readdir(root), ['destination']);
});

test('atomic write removes a partially written temporary file after a write failure', async (t) => {
  const root = await temporaryRoot(t);
  const originalOpen = fs.open;
  t.mock.method(fs, 'open', async (...arguments_) => {
    const handle = await originalOpen(...arguments_);
    if (typeof arguments_[0] !== 'string' || !path.basename(arguments_[0]).startsWith('.state.json.')) {
      return handle;
    }
    return {
      close: () => handle.close(),
      sync: () => handle.sync(),
      writeFile: async (bytes) => {
        await handle.writeFile(bytes.subarray(0, 1));
        throw new Error('injected partial write failure');
      },
    };
  });

  await assert.rejects(writeCanonicalAtomic(root, 'state.json', { complete: true }), /injected partial write failure/);
  assert.deepEqual(await fs.readdir(root), []);
  await assert.rejects(fs.access(path.join(root, 'state.json')));
});

test('atomic write retains the write and close failures while still removing a temporary file', async (t) => {
  const root = await temporaryRoot(t);
  const originalOpen = fs.open;
  const originalRm = fs.rm;
  let removalAttempted = false;
  t.mock.method(fs, 'open', async (...arguments_) => {
    const handle = await originalOpen(...arguments_);
    if (typeof arguments_[0] !== 'string' || !path.basename(arguments_[0]).startsWith('.state.json.')) {
      return handle;
    }
    return {
      close: async () => {
        await handle.close();
        throw new Error('injected close failure');
      },
      sync: () => handle.sync(),
      writeFile: async (bytes) => {
        await handle.writeFile(bytes.subarray(0, 1));
        throw new Error('injected partial write failure');
      },
    };
  });
  t.mock.method(fs, 'rm', async (...arguments_) => {
    if (typeof arguments_[0] === 'string' && path.basename(arguments_[0]).startsWith('.state.json.')) {
      removalAttempted = true;
    }
    return originalRm(...arguments_);
  });

  let failure;
  try {
    await writeCanonicalAtomic(root, 'state.json', { complete: true });
  } catch (error) {
    failure = error;
  }

  assert.ok(failure instanceof AggregateError);
  assert.deepEqual(failure.errors.map((error) => error.message), [
    'injected partial write failure',
    'injected close failure',
  ]);
  assert.equal(removalAttempted, true);
  assert.deepEqual(await fs.readdir(root), []);
});

test('atomic write syncs each containing directory created for nested ancestry', async (t) => {
  const root = await temporaryRoot(t);
  const firstParent = path.join(root, 'first');
  const finalParent = path.join(firstParent, 'second');
  const syncedDirectories = [];
  const originalOpen = fs.open;
  t.mock.method(fs, 'open', async (...arguments_) => {
    const handle = await originalOpen(...arguments_);
    if (arguments_[1] !== 'r' || ![root, firstParent, finalParent].includes(arguments_[0])) {
      return handle;
    }
    return {
      close: () => handle.close(),
      sync: async () => {
        syncedDirectories.push(arguments_[0]);
        await handle.sync();
      },
    };
  });

  await writeCanonicalAtomic(root, 'first/second/state.json', { complete: true });

  assert.deepEqual(syncedDirectories, [root, firstParent, finalParent]);
  assert.deepEqual(await fs.readdir(finalParent), ['state.json']);
});

test('cooperating creators sync shared missing ancestry after either mkdir result', async (t) => {
  const root = await temporaryRoot(t);
  const sharedParent = path.join(root, 'shared');
  const originalLstat = fs.lstat;
  const originalMkdir = fs.mkdir;
  const originalOpen = fs.open;
  const mkdirResults = [];
  const syncCounts = new Map([[root, 0], [sharedParent, 0]]);
  let missingLstatCalls = 0;
  let releaseMissingLstats;
  const bothMissingLstats = new Promise((resolve) => {
    releaseMissingLstats = resolve;
  });
  t.mock.method(fs, 'lstat', async (...arguments_) => {
    if (arguments_[0] === sharedParent && missingLstatCalls < 2) {
      missingLstatCalls += 1;
      if (missingLstatCalls === 2) {
        releaseMissingLstats();
      }
      await bothMissingLstats;
      const error = new Error('interlocked missing directory');
      error.code = 'ENOENT';
      throw error;
    }
    return originalLstat(...arguments_);
  });
  t.mock.method(fs, 'mkdir', async (...arguments_) => {
    try {
      const result = await originalMkdir(...arguments_);
      if (arguments_[0] === sharedParent) {
        mkdirResults.push('created');
      }
      return result;
    } catch (error) {
      if (arguments_[0] === sharedParent) {
        mkdirResults.push(error.code);
      }
      throw error;
    }
  });
  t.mock.method(fs, 'open', async (...arguments_) => {
    const handle = await originalOpen(...arguments_);
    if (arguments_[1] !== 'r' || !syncCounts.has(arguments_[0])) {
      return handle;
    }
    return {
      close: () => handle.close(),
      sync: async () => {
        syncCounts.set(arguments_[0], syncCounts.get(arguments_[0]) + 1);
        await handle.sync();
      },
    };
  });

  await Promise.all([
    writeCanonicalAtomic(root, 'shared/first.json', { writer: 'first' }),
    writeCanonicalAtomic(root, 'shared/second.json', { writer: 'second' }),
  ]);

  assert.deepEqual(mkdirResults.sort(), ['EEXIST', 'created']);
  assert.equal(syncCounts.get(root), 2);
  assert.equal(syncCounts.get(sharedParent), 2);
  assert.deepEqual((await fs.readdir(sharedParent)).sort(), ['first.json', 'second.json']);
});

test('concurrent atomic writes leave one complete canonical object', async (t) => {
  const root = await temporaryRoot(t);
  const first = { writer: 'first', values: [1, 2, 3] };
  const second = { writer: 'second', values: [4, 5, 6] };
  const results = await Promise.all([
    writeCanonicalAtomic(root, 'task/state.json', first),
    writeCanonicalAtomic(root, 'task/state.json', second),
  ]);
  const taskRoot = path.join(root, 'task');
  const written = new Uint8Array(await fs.readFile(path.join(taskRoot, 'state.json')));

  assert.ok(results.includes(sha256Digest(written)));
  assert.ok([first, second].some((value) => Buffer.compare(Buffer.from(written), Buffer.from(canonicalBytes(value))) === 0));
  assert.deepEqual(await fs.readdir(root), ['task']);
  assert.deepEqual(await fs.readdir(taskRoot), ['state.json']);
});
