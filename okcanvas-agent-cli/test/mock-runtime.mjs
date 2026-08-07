import { createServer } from 'node:http';

function json(response, status, payload) {
  response.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
  response.end(JSON.stringify(payload));
}

async function body(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  if (chunks.length === 0) return {};
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}

function session(turnCount = 0) {
  return {
    session_id: 'session_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    state: 'ACTIVE',
    agent_definition_id: 'organization-assistant-session-agent',
    agent_definition_version: '1.0.0',
    agent_definition_sha256: 'a'.repeat(64),
    runtime_binding_sha256: 'b'.repeat(64),
    history_encryption_key_id: 'key-1',
    active_run_id: null,
    turn_count: turnCount,
    item_count: turnCount * 2,
    created_at: '2026-08-05T00:00:00Z',
    updated_at: '2026-08-05T00:00:00Z',
    cleared_at: null,
  };
}

export async function startMockRuntime({ bearer = 'service-token' } = {}) {
  const state = { requests: [], turnCount: 0, runCount: 0 };
  const server = createServer(async (request, response) => {
    const url = new URL(request.url, 'http://127.0.0.1');
    const payload = await body(request);
    state.requests.push({ method: request.method, path: url.pathname, search: url.search, authorization: request.headers.authorization, payload });
    if (request.headers.authorization !== `Bearer ${bearer}`) {
      json(response, 401, { code: 'SERVICE_CLIENT_AUTH_INVALID', message: 'invalid bearer' });
      return;
    }
    if (request.method === 'GET' && url.pathname === '/v1/service/whoami') {
      json(response, 200, { token_id: 'token-1', tenant_id: 'tenant-1', principal_id: 'user-1', roles: ['agent-user'] });
      return;
    }
    if (request.method === 'GET' && url.pathname === '/v1/service/capabilities') {
      json(response, 200, {
        runtime_version: '2.66.2',
        organization_assistant_routing_available: true,
        organization_context_catalog_state: 'READY',
        groupware_read_state: 'READY',
        groupware_read_executable_now: true,
      });
      return;
    }
    if (request.method === 'POST' && url.pathname === '/v1/service/assistant/sessions') {
      json(response, 201, session(state.turnCount));
      return;
    }
    if (request.method === 'GET' && url.pathname === '/v1/service/sessions') {
      json(response, 200, { total: 1, sessions: [session(state.turnCount)] });
      return;
    }
    if (request.method === 'GET' && url.pathname === '/v1/service/sessions/session_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa') {
      json(response, 200, session(state.turnCount));
      return;
    }
    if (request.method === 'POST' && url.pathname === '/v1/service/sessions/session_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/clear') {
      state.turnCount = 0;
      json(response, 200, session(0));
      return;
    }
    if (request.method === 'POST' && url.pathname === '/v1/service/assistant/routes') {
      json(response, 200, {
        request_class: 'ANSWER', side_effect: 'NONE', status: 'EXECUTABLE',
        selected_agent_definition_id: payload.session_id ? 'organization-assistant-session-agent' : 'organization-assistant-agent',
        executable_now: true, required_capabilities: [], matched_rule_id: 'general-answer', reasons: [],
        policy_id: 'assistant', policy_version: '1', policy_sha256: 'c'.repeat(64),
        grounding_state: 'NOT_APPLICABLE', grounding_catalog_id: null, grounding_catalog_version: null,
        grounding_effective_at: null, grounding: [],
      });
      return;
    }
    if (request.method === 'POST' && url.pathname === '/v1/service/assistant/run-submissions/preflight') {
      if (String(payload.input).includes('미구성')) {
        json(response, 201, {
          route: { request_class: 'READ_SYSTEM', side_effect: 'READ', status: 'NOT_CONFIGURED', selected_agent_definition_id: null, executable_now: false, required_capabilities: [], matched_rule_id: 'read-system', reasons: ['provider-not-configured'], policy_id: 'assistant', policy_version: '1', policy_sha256: 'c'.repeat(64), grounding_state: 'NOT_CONFIGURED', grounding_catalog_id: null, grounding_catalog_version: null, grounding_effective_at: null, grounding: [] },
          submission: null,
        });
        return;
      }
      const next = state.runCount + 1;
      json(response, 201, {
        route: { request_class: 'ANSWER', side_effect: 'NONE', status: 'EXECUTABLE', selected_agent_definition_id: payload.session_id ? 'organization-assistant-session-agent' : 'organization-assistant-agent', executable_now: true, required_capabilities: [], matched_rule_id: 'general-answer', reasons: [], policy_id: 'assistant', policy_version: '1', policy_sha256: 'c'.repeat(64), grounding_state: 'NOT_APPLICABLE', grounding_catalog_id: null, grounding_catalog_version: null, grounding_effective_at: null, grounding: [] },
        submission: { submission_id: `submission-${next}`, confirmation_challenge: `confirm-${next}`, executable_now: true, approval_required: false },
      });
      return;
    }
    const confirm = url.pathname.match(/^\/v1\/service\/run-submissions\/submission-(\d+)\/confirm$/u);
    if (request.method === 'POST' && confirm) {
      state.runCount = Number(confirm[1]);
      json(response, 202, { run_id: `run-${confirm[1]}`, task_id: `task-${confirm[1]}`, scheduled: true, replayed: false, submission: {} });
      return;
    }
    const sse = url.pathname.match(/^\/v1\/service\/runs\/(run-\d+)\/events\/stream$/u);
    if (request.method === 'GET' && sse) {
      const runId = sse[1];
      response.writeHead(200, { 'Content-Type': 'text/event-stream; charset=utf-8' });
      const events = [
        { run_id: runId, sequence: 1, event_type: 'run.started', payload: {} },
        { run_id: runId, sequence: 2, event_type: 'model.completed', payload: {} },
        { run_id: runId, sequence: 3, event_type: 'run.completed', payload: {} },
      ];
      for (const event of events) response.write(`id: ${event.sequence}\nevent: ${event.event_type}\ndata: ${JSON.stringify(event)}\n\n`);
      response.end();
      return;
    }
    const outcome = url.pathname.match(/^\/v1\/service\/runs\/(run-(\d+))\/outcome$/u);
    if (request.method === 'GET' && outcome) {
      state.turnCount += 1;
      json(response, 200, { run_id: outcome[1], task_id: `task-${outcome[2]}`, attempt: 1, status: 'SUCCEEDED', agent_definition_id: 'organization-assistant-session-agent', agent_definition_version: '1.0.0', trace_id: `trace-${outcome[2]}`, input_tokens: 10, output_tokens: 5, total_tokens: 15, created_at: '2026-08-05T00:00:00Z', started_at: '2026-08-05T00:00:00Z', completed_at: '2026-08-05T00:00:01Z' });
      return;
    }
    const invocations = url.pathname.match(/^\/v1\/service\/runs\/(run-\d+)\/invocations$/u);
    if (request.method === 'GET' && invocations) {
      json(response, 200, { run_id: invocations[1], total: 1, invocations: [{ invocation_id: 'inv-1', invocation_kind: 'ROOT', state: 'SUCCEEDED' }] });
      return;
    }
    const artifacts = url.pathname.match(/^\/v1\/service\/runs\/(run-(\d+))\/artifacts$/u);
    if (request.method === 'GET' && artifacts) {
      json(response, 200, { run_id: artifacts[1], total: 1, artifacts: [{ artifact_id: `artifact-${artifacts[2]}`, run_id: artifacts[1], artifact_type: 'agent.final-output', media_type: 'application/json' }] });
      return;
    }
    const artifact = url.pathname.match(/^\/v1\/service\/runs\/(run-(\d+))\/artifacts\/artifact-(\d+)$/u);
    if (request.method === 'GET' && artifact) {
      json(response, 200, { artifact_id: `artifact-${artifact[2]}`, run_id: artifact[1], artifact_type: 'agent.final-output', media_type: 'application/json', content: { status: 'ANSWERED', answer: `응답 ${artifact[2]}` } });
      return;
    }
    json(response, 404, { code: 'NOT_FOUND', message: `${request.method} ${url.pathname}` });
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const address = server.address();
  return {
    baseUrl: `http://127.0.0.1:${address.port}`,
    state,
    close: () => new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve())),
  };
}
