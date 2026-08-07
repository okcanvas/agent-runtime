import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { ServiceAgentCli } from '../src/app.mjs';
import { ServiceApiClient } from '../src/api-client.mjs';
import { ScriptLineSource } from '../src/line-source.mjs';
import { startMockRuntime } from './mock-runtime.mjs';

test('product CLI keeps one Assistant Session across consecutive prompts', async (t) => {
  const runtime = await startMockRuntime();
  t.after(runtime.close);
  const dir = mkdtempSync(join(tmpdir(), 'okcanvas-cli-'));
  const script = join(dir, 'prompts.txt');
  writeFileSync(script, '첫 질문\n둘째 질문\n/quit\n', 'utf8');
  const output = [];
  const config = Object.freeze({
    baseUrl: runtime.baseUrl, bearer: 'service-token', model: undefined, sessionId: undefined,
    scriptFile: script, assumeYes: true, sessionEnabled: true, debug: false, help: false,
  });
  const input = new ScriptLineSource(script, (value) => output.push(value.trimEnd()));
  const app = new ServiceAgentCli(config, {
    client: new ServiceApiClient(config), input, write: (value = '') => output.push(value),
  });
  assert.equal(await app.run(), 0);
  assert.equal(app.requestCount, 2);
  assert.ok(output.join('\n').includes('응답 1'));
  assert.ok(output.join('\n').includes('응답 2'));
  const preflights = runtime.state.requests.filter((item) => item.path === '/v1/service/assistant/run-submissions/preflight');
  assert.equal(preflights.length, 2);
  assert.equal(preflights[0].payload.session_id, preflights[1].payload.session_id);
  assert.equal(preflights[0].payload.session_id, 'session_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa');
});
