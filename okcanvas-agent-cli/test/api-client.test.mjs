import assert from 'node:assert/strict';
import test from 'node:test';
import { ServiceApiClient } from '../src/api-client.mjs';
import { startMockRuntime } from './mock-runtime.mjs';

test('service client executes automatic route, confirm, SSE, outcome, and final artifact', async (t) => {
  const runtime = await startMockRuntime();
  t.after(runtime.close);
  const client = new ServiceApiClient({ baseUrl: runtime.baseUrl, bearer: 'service-token' });
  const session = await client.createAssistantSession();
  const events = [];
  const outcome = await client.executeAssistant('첫 요청', {
    sessionId: session.session_id,
    confirm: async () => true,
    onEvent: (event) => events.push(event.event_type),
  });
  assert.equal(outcome.state, 'COMPLETED');
  assert.equal(outcome.run.status, 'SUCCEEDED');
  assert.equal(outcome.artifact.content.answer, '응답 1');
  assert.deepEqual(events, ['run.started', 'model.completed', 'run.completed']);
  assert.ok(runtime.state.requests.every((item) => item.authorization === 'Bearer service-token'));
  assert.ok(runtime.state.requests.every((item) => item.path.startsWith('/v1/service/')));
});

test('service client preserves non-executable route without confirmation', async (t) => {
  const runtime = await startMockRuntime();
  t.after(runtime.close);
  const client = new ServiceApiClient({ baseUrl: runtime.baseUrl, bearer: 'service-token' });
  const outcome = await client.executeAssistant('미구성 시스템 조회', { confirm: async () => { throw new Error('must not confirm'); } });
  assert.equal(outcome.state, 'NOT_EXECUTED');
  assert.equal(outcome.route.status, 'NOT_CONFIGURED');
});
