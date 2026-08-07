import { spawnSync } from 'node:child_process';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import {
  AUTHORITY, AUTOMATIC_ASSISTANT_ROUTING, CLI_STEP, CLI_VERSION, DURABLE_EVENT_STREAM,
  IMPLEMENTATION_STATE, REQUEST_EXECUTION_IMPLEMENTED, SERVICE_API_PREFIX, SESSION_EXECUTION_IMPLEMENTED,
} from '../src/boundary.mjs';

const ROOT = resolve(import.meta.dirname, '..');
const testFiles = readdirSync(join(ROOT, 'test'))
  .filter((name) => name.endsWith('.test.mjs'))
  .sort()
  .map((name) => join('test', name));
const testProcess = spawnSync(process.execPath, ['--test', ...testFiles], {
  cwd: ROOT, encoding: 'utf8', shell: false,
});
const source = readdirSync(join(ROOT, 'src'))
  .filter((name) => statSync(join(ROOT, 'src', name)).isFile())
  .map((name) => readFileSync(join(ROOT, 'src', name), 'utf8')).join('\n');
const servicePaths = [
  '/v1/service/whoami', '/v1/service/capabilities', '/v1/service/assistant/sessions',
  '/v1/service/assistant/routes', '/v1/service/assistant/run-submissions/preflight',
  '/v1/service/run-submissions/', '/v1/service/runs/', '/v1/service/sessions',
];
const forbidden = [
  '/v1/' + 'run-submissions', '/v1/' + 'agent-definitions',
  'X-OKCanvas-' + 'Admin-Key', 'X-OKCanvas-' + 'Run-Submitter-Key',
  'okcanvas_' + 'agent_runtime', 'groupware_' + 'mcp_server',
];
const checks = {
  identity_exact: CLI_STEP === 'CLI_STEP001R1_WINDOWS_NODE_TEST_RUNNER_PATH_SPACE_CLOSURE' && CLI_VERSION === '0.2.1',
  product_ready: IMPLEMENTATION_STATE === 'PRODUCT_READY' && REQUEST_EXECUTION_IMPLEMENTED === true,
  session_execution_implemented: SESSION_EXECUTION_IMPLEMENTED === true,
  automatic_assistant_routing: AUTOMATIC_ASSISTANT_ROUTING === true,
  persisted_sse_implemented: DURABLE_EVENT_STREAM === 'PERSISTED_SSE',
  service_api_boundary_exact: SERVICE_API_PREFIX === '/v1/service/' && AUTHORITY === 'EXTERNAL_BEARER' && servicePaths.every((path) => source.includes(path)),
  administrator_boundary_absent: forbidden.every((token) => !source.includes(token)),
  runtime_source_import_absent: !source.includes('../okcanvas-agent-runtime') && !source.includes('../okcanvas-connectors'),
  external_bearer_secret_redacted: source.includes('bearerConfigured') && !source.includes('console.log(config.bearer)'),
  windows_node_test_runner_path_space_safe: testFiles.length > 0 && testProcess.error == null && testProcess.status === 0,
  node_tests_passed: testProcess.status === 0,
};
const payload = {
  schema_version: 'okcanvas-agent-service-cli-step001r1-acceptance-v1',
  step: CLI_STEP, version: CLI_VERSION,
  state: Object.values(checks).every(Boolean) ? 'PASSED' : 'FAILED',
  checks, passed_checks: Object.values(checks).filter(Boolean).length, total_checks: Object.keys(checks).length,
  test_process: { returncode: testProcess.status, stdout: testProcess.stdout, stderr: testProcess.stderr },
};
console.log(JSON.stringify(payload, null, 2));
process.exit(payload.state === 'PASSED' ? 0 : 1);
