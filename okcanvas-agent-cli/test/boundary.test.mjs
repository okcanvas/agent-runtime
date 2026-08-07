import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import test from 'node:test';
import {
  AUTHORITY, AUTOMATIC_ASSISTANT_ROUTING, CLI_STEP, CLI_VERSION, DURABLE_EVENT_STREAM,
  IMPLEMENTATION_STATE, REQUEST_EXECUTION_IMPLEMENTED, SERVICE_API_PREFIX, SESSION_EXECUTION_IMPLEMENTED,
} from '../src/boundary.mjs';

const ROOT = resolve(import.meta.dirname, '..');
function files(dir) {
  const result = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (['node_modules', 'dist'].includes(name)) continue;
    if (statSync(path).isDirectory()) result.push(...files(path)); else result.push(path);
  }
  return result;
}

test('product service CLI implementation identity is exact', () => {
  assert.equal(CLI_STEP, 'CLI_STEP001R1_WINDOWS_NODE_TEST_RUNNER_PATH_SPACE_CLOSURE');
  assert.equal(CLI_VERSION, '0.2.1');
  assert.equal(IMPLEMENTATION_STATE, 'PRODUCT_READY');
  assert.equal(REQUEST_EXECUTION_IMPLEMENTED, true);
  assert.equal(SESSION_EXECUTION_IMPLEMENTED, true);
  assert.equal(AUTOMATIC_ASSISTANT_ROUTING, true);
  assert.equal(DURABLE_EVENT_STREAM, 'PERSISTED_SSE');
  assert.equal(SERVICE_API_PREFIX, '/v1/service/');
  assert.equal(AUTHORITY, 'EXTERNAL_BEARER');
});

test('product sources use no administrator boundary or cross-project source import', () => {
  const source = files(join(ROOT, 'src')).map((path) => readFileSync(path, 'utf8')).join('\n');
  const forbidden = [
    '/v1/' + 'run-submissions', '/v1/' + 'agent-definitions',
    'X-OKCanvas-' + 'Admin-Key', 'X-OKCanvas-' + 'Run-Submitter-Key',
    'okcanvas_' + 'agent_runtime', 'groupware_' + 'mcp_server', '../okcanvas-agent-runtime', '../okcanvas-connectors',
  ];
  for (const token of forbidden) assert.equal(source.includes(token), false, token);
});
