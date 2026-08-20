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
  assert.equal(sha256Digest(canonicalBytes({ b: 2, a: 1 })), 'sha256:43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777');
});

test('canonical bytes reject values outside the shared integer JSON subset', () => {
  for (const value of [NaN, Infinity, -Infinity, 1.5, 9007199254740992, -9007199254740992]) {
    assert.throws(() => canonicalBytes(value), /integer|finite|safe/i);
  }
  for (const value of [undefined, BigInt(1), new Date(), { nested: undefined }]) {
    assert.throws(() => canonicalBytes(value), /JSON|unsupported|plain/i);
  }
});

test('canonical digest consumes exact bytes and uses a lowercase SHA-256 prefix', () => {
  const bytes = new TextEncoder().encode('{message:café ☕}');
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

test('concurrent atomic writes leave one complete canonical object', async (t) => {
  const root = await temporaryRoot(t);
  const first = { writer: 'first', values: [1, 2, 3] };
  const second = { writer: 'second', values: [4, 5, 6] };
  const results = await Promise.all([
    writeCanonicalAtomic(root, 'state.json', first),
    writeCanonicalAtomic(root, 'state.json', second),
  ]);
  const written = new Uint8Array(await fs.readFile(path.join(root, 'state.json')));

  assert.ok(results.includes(sha256Digest(written)));
  assert.ok([first, second].some((value) => Buffer.compare(Buffer.from(written), Buffer.from(canonicalBytes(value))) === 0));
  assert.deepEqual((await fs.readdir(root)).sort(), ['state.json']);
});
