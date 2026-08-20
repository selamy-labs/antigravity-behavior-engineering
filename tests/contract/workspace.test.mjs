import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(process.cwd());

const readJson = (relativePath) => {
  const absolutePath = path.join(ROOT, relativePath);
  return JSON.parse(fs.readFileSync(absolutePath, 'utf8'));
};

const readTomlSection = (source, sectionName) => {
  const header = `[${sectionName}]`;
  const headerOffset = source.indexOf(header);
  assert.notEqual(headerOffset, -1, `missing TOML section ${header}`);
  const bodyOffset = headerOffset + header.length;
  const nextHeaderOffset = source.indexOf('\n[', bodyOffset);
  return source.slice(bodyOffset, nextHeaderOffset === -1 ? undefined : nextHeaderOffset);
};

const packageJson = readJson('package.json');
const pyproject = fs.readFileSync(path.join(ROOT, 'evaluator', 'pyproject.toml'), 'utf8');
const pnpmWorkspace = fs.readFileSync(path.join(ROOT, 'pnpm-workspace.yaml'), 'utf8');
const pnpmLock = fs.readFileSync(path.join(ROOT, 'pnpm-lock.yaml'), 'utf8');
const uvLock = fs.readFileSync(path.join(ROOT, 'evaluator', 'uv.lock'), 'utf8');
const ignoreLines = fs
  .readFileSync(path.join(ROOT, '.gitignore'), 'utf8')
  .split('\n')
  .map((line) => line.trim())
  .filter((line) => line.length > 0 && !line.startsWith('#'));

const t001TextFiles = [
  '.gitignore',
  'evaluator/pyproject.toml',
  'evaluator/src/abe_eval/__init__.py',
  'evaluator/uv.lock',
  'package.json',
  'packages/contracts/package.json',
  'packages/plugin-tooling/package.json',
  'pnpm-lock.yaml',
  'pnpm-workspace.yaml',
  'tests/contract/workspace.test.mjs',
];
for (const relativePath of t001TextFiles) {
  const contents = fs.readFileSync(path.join(ROOT, relativePath), 'utf8');
  assert.doesNotMatch(contents, /\r/, `${relativePath}: CR newline`);
  assert.doesNotMatch(contents, /[ \t]+$/m, `${relativePath}: trailing whitespace`);
  assert.match(contents, /[^\n]\n$/, `${relativePath}: exactly one final newline`);
}
for (const relativePath of [
  'package.json',
  'packages/contracts/package.json',
  'packages/plugin-tooling/package.json',
]) {
  const contents = fs.readFileSync(path.join(ROOT, relativePath), 'utf8');
  assert.equal(
    contents,
    `${JSON.stringify(JSON.parse(contents), null, 2)}\n`,
    `${relativePath}: canonical two-space JSON`,
  );
}

const nodeVersion = process.versions.node.split('.').map((value) => Number(value));
assert(nodeVersion[0] >= 22 && nodeVersion[0] < 25, `node range unsupported: ${process.version}`);
assert.deepEqual(
  packageJson.engines,
  { node: '>=22 <25', pnpm: '>=10 <12' },
  'root: engines',
);

const pythonRangeMatch = pyproject.match(/^requires-python\s*=\s*"([^"]+)"\s*$/m);
assert.ok(pythonRangeMatch, 'evaluator pyproject must define requires-python');
assert.equal(
  pythonRangeMatch[1],
  '>=3.12,<3.14',
  `unexpected evaluator python range: ${pythonRangeMatch[0]}`,
);

const buildSystemSection = readTomlSection(pyproject, 'build-system');
const projectSection = readTomlSection(pyproject, 'project');
const scriptsSection = readTomlSection(pyproject, 'project.scripts');
const dependencyGroupsSection = readTomlSection(pyproject, 'dependency-groups');
assert.match(
  buildSystemSection,
  /^requires\s*=\s*\["setuptools==84\.0\.0"\]\s*$/m,
  'evaluator: exact build requirement',
);
assert.match(
  buildSystemSection,
  /^build-backend\s*=\s*"setuptools\.build_meta"\s*$/m,
  'evaluator: build backend',
);
assert.match(projectSection, /^name\s*=\s*"abe-eval"\s*$/m, 'evaluator: name');
assert.match(projectSection, /^version\s*=\s*"0\.0\.0"\s*$/m, 'evaluator: version');
assert.match(projectSection, /^license\s*=\s*"Apache-2\.0"\s*$/m, 'evaluator: license');
assert.doesNotMatch(projectSection, /^readme\s*=/m, 'evaluator: nonexistent readme');
assert.match(
  projectSection,
  /^dependencies\s*=\s*\["jsonschema>=4\.23,<5"\]\s*$/m,
  'evaluator: JSON Schema runtime dependency intent',
);
assert.match(scriptsSection, /^abe-eval\s*=\s*"abe_eval\.cli:main"\s*$/m, 'evaluator: CLI entry point');
assert.match(
  dependencyGroupsSection,
  /^dev\s*=\s*\["pytest>=8\.3,<10", "setuptools==84\.0\.0"\]\s*$/m,
  'evaluator: dev dependency group',
);
assert.match(pyproject, /^package\s*=\s*true\s*$/m, 'evaluator: uv package mode');
assert.ok(fs.existsSync(path.join(ROOT, 'evaluator', 'src', 'abe_eval', '__init__.py')), 'evaluator: package marker');

const pnpmWorkspaceMembers = pnpmWorkspace
  .split('\n')
  .map((line) => line.trim())
  .filter((line) => line.startsWith('- '))
  .map((line) => line.slice(2).replace(/^['"]|['"]$/g, ''));
assert.deepEqual(
  pnpmWorkspaceMembers,
  ['packages/contracts', 'packages/plugin-tooling'],
  'pnpm workspace members',
);
assert.match(pnpmLock, /^lockfileVersion: '9\.0'$/m, 'pnpm lockfile version');
assert.deepEqual(
  [...pnpmLock.matchAll(/^  ([^:\n]+): \{\}$/gm)].map((match) => match[1]),
  ['.', 'packages/contracts', 'packages/plugin-tooling'],
  'pnpm lock importers',
);
const uvPackagePairs = [...uvLock.matchAll(/^\[\[package\]\]\nname = "([^"]+)"\nversion = "([^"]+)"$/gm)].map(
  (match) => ({ name: match[1], version: match[2] }),
);
const uvPackageNames = uvPackagePairs.map(({ name }) => name);
assert.ok(uvPackageNames.length > 1, 'uv lock must resolve evaluator dev tools');
assert.ok(uvPackageNames.includes('pytest'), 'uv lock must resolve pytest');
assert.match(uvLock, /^name = "abe-eval"$/m, 'uv lock evaluator package');

const lockedLicenseLines = readTomlSection(pyproject, 'tool.abe.locked-licenses')
  .split('\n')
  .map((line) => line.trim())
  .filter((line) => line.length > 0 && !line.startsWith('#'));
const lockedLicenses = {};
for (const line of lockedLicenseLines) {
  const match = line.match(
    /^([a-z0-9-]+)\s*=\s*\{\s*version\s*=\s*"([^"]+)",\s*spdx\s*=\s*"([^"]+)"\s*\}$/,
  );
  assert.ok(match, `evaluator: malformed locked-license record: ${line}`);
  assert.ok(!Object.hasOwn(lockedLicenses, match[1]), `evaluator: duplicate locked-license record: ${match[1]}`);
  lockedLicenses[match[1]] = { version: match[2], spdx: match[3] };
}
const thirdPartyLockVersions = Object.fromEntries(
  uvPackagePairs
    .filter(({ name }) => name !== 'abe-eval')
    .map(({ name, version }) => [name, version]),
);
assert.deepEqual(
  Object.fromEntries(Object.entries(lockedLicenses).map(([name, record]) => [name, record.version])),
  thirdPartyLockVersions,
  'evaluator: locked-license inventory must cover exactly the third-party lock packages',
);
assert.deepEqual(
  Object.fromEntries(Object.entries(lockedLicenses).map(([name, record]) => [name, record.spdx])),
  {
    attrs: 'MIT',
    colorama: 'BSD-3-Clause',
    iniconfig: 'MIT',
    jsonschema: 'MIT',
    'jsonschema-specifications': 'MIT',
    packaging: 'Apache-2.0 OR BSD-2-Clause',
    pluggy: 'MIT',
    pygments: 'BSD-2-Clause',
    pytest: 'MIT',
    referencing: 'MIT',
    'rpds-py': 'MIT',
    setuptools: 'MIT',
    'typing-extensions': 'PSF-2.0',
  },
  'evaluator: locked-license SPDX inventory',
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
      scripts: {
        'format:check': 'node --test tests/contract/workspace.test.mjs',
        'test:node': 'node --test',
        'test:python': 'uv run --no-project --offline python -c \'import sys; assert (3, 12) <= sys.version_info[:2] < (3, 14), "requires Python >=3.12,<3.14"\' && if [ -d evaluator/tests ]; then uv run --project evaluator --locked --offline pytest evaluator/tests; fi',
        verify: 'pnpm verify:offline',
        'verify:offline': 'pnpm format:check && pnpm test:node && pnpm test:python && uv run --no-project --offline python -m py_compile evaluator/src/abe_eval/__init__.py',
      },
      workspaces: ['packages/contracts', 'packages/plugin-tooling'],
      dependencies: {},
      devDependencies: {},
      main: undefined,
      exports: undefined,
      bin: undefined,
      ignoredPaths: [
        '/evidence/raw/',
        '/evidence/publishable/',
        '/evidence/qualification/',
        '/evidence/locked/',
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
      main: undefined,
      exports: undefined,
      bin: undefined,
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
      main: undefined,
      exports: undefined,
      bin: undefined,
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
  assert.deepEqual(loaded.main, expected.spec.main, `${expected.id}: main`);
  assert.deepEqual(loaded.exports, expected.spec.exports, `${expected.id}: exports`);
  assert.deepEqual(loaded.bin, expected.spec.bin, `${expected.id}: bin`);
  if (expected.spec.scripts) {
    assert.deepEqual(loaded.scripts, expected.spec.scripts, `${expected.id}: scripts`);
  }
  if (expected.spec.ignoredPaths) {
    for (const ignored of expected.spec.ignoredPaths) {
      assert.ok(ignoreLines.includes(ignored), `missing .gitignore entry ${ignored}`);
    }
  }
}

assert.ok(ignoreLines.includes('*.egg-info/'), 'missing .gitignore entry *.egg-info/');
