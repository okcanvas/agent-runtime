import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
import test from 'node:test';

const ROOT = resolve(import.meta.dirname, '..');

test('CLI entrypoint exposes help without requiring a bearer', () => {
  const child = spawnSync(process.execPath, ['src/cli.mjs', '--help'], { cwd: ROOT, encoding: 'utf8' });
  assert.equal(child.status, 0, child.stderr);
  assert.match(child.stdout, /OKCanvas Agent Service CLI/u);
  assert.match(child.stdout, /OKCANVAS_SERVICE_BEARER/u);
});

test('CLI entrypoint fails closed when bearer is missing', () => {
  const env = { ...process.env };
  delete env.OKCANVAS_SERVICE_BEARER;
  const processResult = spawnSync(process.execPath, ['src/cli.mjs'], { cwd: ROOT, env, encoding: 'utf8' });
  assert.equal(processResult.status, 1);
  assert.match(processResult.stderr, /CLI_BEARER_REQUIRED/u);
});
