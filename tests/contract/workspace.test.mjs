import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(process.cwd());

const readJson = (relativePath) => {
  const absolutePath = path.join(ROOT, relativePath);
  return JSON.parse(fs.readFileSync(absolutePath, 'utf8'));
};

const packageJson = readJson('package.json');
const pyproject = fs.readFileSync(path.join(ROOT, 'evaluator', 'pyproject.toml'), 'utf8');
const ignoreLines = fs
  .readFileSync(path.join(ROOT, '.gitignore'), 'utf8')
  .split('\n')
  .map((line) => line.trim())
  .filter((line) => line.length > 0 && !line.startsWith('#'));

const nodeVersion = process.versions.node.split('.').map((value) => Number(value));
assert(nodeVersion[0] >= 22 && nodeVersion[0] < 25, `node range unsupported: ${process.version}`);

const pythonRangeLine = pyproject
  .split('\n')
  .find((line) => line.trim().startsWith('requires-python'));
assert.ok(pythonRangeLine, 'evaluator pyproject must define requires-python');
assert.equal(
  pythonRangeLine.split('=')[1]?.trim().replaceAll('"', ''),
  '>=3.12,<3.14',
  `unexpected evaluator python range: ${pythonRangeLine}`,
);

for (const expected of [
  {
    id: 'root',
    path: '.',
    spec: {
      name: 'antigravity-behavior-engineering',
      version: '0.0.0',
      license: 'Apache-2.0',
      type: 'module',
      packageManager: 'pnpm@11.9.0',
      scripts: ['test:node', 'test:python', 'verify:offline'],
      workspaces: ['packages/contracts', 'packages/plugin-tooling'],
      dependencies: {},
      devDependencies: {},
      ignoredPaths: [
        '/evidence/raw',
        '/evidence/publishable',
        '/evidence/qualification',
      ],
    },
  },
  {
    id: 'contracts',
    path: 'packages/contracts/package.json',
    spec: {
      name: '@antigravity/abe-contracts',
      version: '0.0.0',
      license: 'Apache-2.0',
      type: 'module',
      exports: { '.': './src/index.mjs' },
      bin: { 'abe-contracts': 'bin/abi.js' },
      dependencies: {},
      devDependencies: {},
    },
  },
  {
    id: 'plugin-tooling',
    path: 'packages/plugin-tooling/package.json',
    spec: {
      name: '@antigravity/abe-plugin-tooling',
      version: '0.0.0',
      license: 'Apache-2.0',
      type: 'module',
      exports: { '.': './src/index.mjs' },
      bin: { 'abe-plugin-tooling': 'bin/tooling.js' },
      dependencies: {},
      devDependencies: {},
    },
  },
]) {
  const loaded = expected.path === '.' ? packageJson : readJson(expected.path);
  for (const key of ['name', 'version', 'license', 'type']) {
    assert.equal(loaded[key], expected.spec[key], `${expected.id}: ${key}`);
  }
  if (expected.spec.packageManager) {
    assert.equal(loaded.packageManager, expected.spec.packageManager, `${expected.id}: packageManager`);
  }
  if (expected.spec.workspaces) {
    assert.deepEqual(loaded.workspaces, expected.spec.workspaces, `${expected.id}: workspaces`);
  }
  if (expected.spec.dependencies) {
    assert.deepEqual(loaded.dependencies, expected.spec.dependencies, `${expected.id}: dependencies`);
  }
  if (expected.spec.devDependencies) {
    assert.deepEqual(loaded.devDependencies, expected.spec.devDependencies, `${expected.id}: devDependencies`);
  }
  if (expected.spec.exports) {
    assert.deepEqual(loaded.exports, expected.spec.exports, `${expected.id}: exports`);
  }
  if (expected.spec.bin) {
    assert.deepEqual(loaded.bin, expected.spec.bin, `${expected.id}: bin`);
  }
  if (expected.spec.scripts) {
    for (const script of expected.spec.scripts) {
      assert.ok(loaded.scripts?.[script], `${expected.id}: missing script ${script}`);
    }
  }
  if (expected.spec.ignoredPaths) {
    for (const ignored of expected.spec.ignoredPaths) {
      assert.ok(ignoreLines.includes(ignored), `missing .gitignore entry ${ignored}`);
    }
  }
}
