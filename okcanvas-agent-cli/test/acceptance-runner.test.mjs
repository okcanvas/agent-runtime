import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

const ROOT = resolve(import.meta.dirname, '..');

test('acceptance runner is safe when node executable path contains spaces', () => {
  const source = readFileSync(resolve(ROOT, 'scripts/run-acceptance.mjs'), 'utf8');
  assert.equal(source.includes("spawnSync(process.execPath, ['--test', ...testFiles]"), true);
  assert.equal(source.includes('shell: false'), true);
  assert.equal(source.includes('test/*.test.mjs'), false);
  assert.equal(source.includes('shell: process.platform'), false);
});
