import { randomUUID } from 'node:crypto';
import { CliError } from './errors.mjs';
import { parseSseJson } from './sse.mjs';

function object(value, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new CliError('CLI_RESPONSE_INVALID', label);
  }
  return value;
}

function array(value, label) {
  if (!Array.isArray(value)) throw new CliError('CLI_RESPONSE_INVALID', label);
  return value;
}

export class ServiceApiClient {
  constructor(config, fetchImpl = globalThis.fetch) {
    if (typeof fetchImpl !== 'function') throw new CliError('CLI_FETCH_UNAVAILABLE', 'Node.js fetch is unavailable');
    this.config = config;
    this.fetchImpl = fetchImpl;
  }

  headers(extra = {}) {
    return {
      Accept: 'application/json',
      Authorization: `Bearer ${this.config.bearer}`,
      ...extra,
    };
  }

  async request(method, path, body = undefined) {
    let response;
    try {
      response = await this.fetchImpl(`${this.config.baseUrl}${path}`, {
        method,
        headers: this.headers(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
    } catch (error) {
      throw new CliError('CLI_CONNECTION_FAILED', `Unable to reach Agent Runtime at ${this.config.baseUrl}`, undefined, {
        cause: error instanceof Error ? error.name : 'unknown',
      });
    }
    if (!response.ok) await this.raiseApiError(response);
    if (response.status === 204) return {};
    let payload;
    try {
      payload = await response.json();
    } catch {
      throw new CliError('CLI_RESPONSE_INVALID', `Runtime returned invalid JSON (${response.status})`);
    }
    return object(payload, 'Runtime returned a non-object JSON response');
  }

  async raiseApiError(response) {
    let payload = {};
    try { payload = object(await response.json(), 'invalid error'); } catch { payload = {}; }
    const detail = payload.detail && typeof payload.detail === 'object' ? payload.detail : {};
    const code = String(payload.code ?? detail.code ?? 'CLI_SERVICE_API_ERROR');
    const message = String(payload.message ?? detail.message ?? `Runtime request failed (${response.status})`);
    throw new CliError(code, message, response.status, payload.details ?? detail.details);
  }

  whoAmI() { return this.request('GET', '/v1/service/whoami'); }
  capabilities() { return this.request('GET', '/v1/service/capabilities'); }
  createAssistantSession() { return this.request('POST', '/v1/service/assistant/sessions', {}); }
  listSessions(limit = 100) { return this.request('GET', `/v1/service/sessions?limit=${encodeURIComponent(limit)}`); }
  getSession(sessionId) { return this.request('GET', `/v1/service/sessions/${encodeURIComponent(sessionId)}`); }
  clearSession(sessionId) { return this.request('POST', `/v1/service/sessions/${encodeURIComponent(sessionId)}/clear`, {}); }
  route(input, sessionId = undefined) {
    return this.request('POST', '/v1/service/assistant/routes', {
      input,
      ...(sessionId ? { session_id: sessionId } : {}),
    });
  }
  preflight(input, { model = undefined, sessionId = undefined } = {}) {
    return this.request('POST', '/v1/service/assistant/run-submissions/preflight', {
      input,
      idempotency_key: `service-cli-${randomUUID()}`,
      ...(model ? { model } : {}),
      ...(sessionId ? { session_id: sessionId } : {}),
    });
  }
  confirm(submissionId, confirmation) {
    return this.request(
      'POST',
      `/v1/service/run-submissions/${encodeURIComponent(submissionId)}/confirm`,
      { confirmation },
    );
  }
  getRun(runId) { return this.request('GET', `/v1/service/runs/${encodeURIComponent(runId)}`); }
  getOutcome(runId) { return this.request('GET', `/v1/service/runs/${encodeURIComponent(runId)}/outcome`); }
  getInvocations(runId) { return this.request('GET', `/v1/service/runs/${encodeURIComponent(runId)}/invocations`); }
  listArtifacts(runId) { return this.request('GET', `/v1/service/runs/${encodeURIComponent(runId)}/artifacts`); }
  getArtifact(runId, artifactId) {
    return this.request('GET', `/v1/service/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactId)}`);
  }

  async *streamEvents(runId, cursor = 0) {
    let response;
    try {
      response = await this.fetchImpl(
        `${this.config.baseUrl}/v1/service/runs/${encodeURIComponent(runId)}/events/stream?cursor=${encodeURIComponent(cursor)}`,
        {
          headers: this.headers({ Accept: 'text/event-stream', 'Last-Event-ID': String(cursor) }),
        },
      );
    } catch {
      throw new CliError('CLI_CONNECTION_FAILED', 'Unable to open Runtime event stream');
    }
    if (!response.ok) await this.raiseApiError(response);
    yield* parseSseJson(response.body);
  }

  async executeAssistant(input, {
    model = undefined,
    sessionId = undefined,
    confirm = async () => true,
    onRoute = undefined,
    onEvent = undefined,
  } = {}) {
    const preflight = await this.preflight(input, { model, sessionId });
    const route = object(preflight.route, 'Assistant preflight has no route');
    await onRoute?.(route, preflight.submission ?? null);
    if (preflight.submission === null || preflight.submission === undefined) {
      return { state: 'NOT_EXECUTED', route, preflight };
    }
    const submission = object(preflight.submission, 'Assistant preflight submission is invalid');
    const challenge = typeof submission.confirmation_challenge === 'string' ? submission.confirmation_challenge : '';
    const submissionId = typeof submission.submission_id === 'string' ? submission.submission_id : '';
    if (!submissionId || !challenge) {
      throw new CliError('CLI_CONFIRMATION_MISSING', 'Runtime preflight did not provide an executable confirmation challenge');
    }
    if (!(await confirm({ route, submission }))) {
      return { state: 'DECLINED', route, preflight, submission };
    }
    const confirmed = await this.confirm(submissionId, challenge);
    const runId = typeof confirmed.run_id === 'string' ? confirmed.run_id : '';
    if (!runId) throw new CliError('CLI_RESPONSE_INVALID', 'Runtime confirmation returned no run_id');

    const events = [];
    for await (const event of this.streamEvents(runId)) {
      if (String(event.run_id ?? '') !== runId) {
        throw new CliError('CLI_SSE_RUN_ID_MISMATCH', 'Runtime SSE returned another Run');
      }
      events.push(event);
      await onEvent?.(event);
    }
    const run = await this.getOutcome(runId);
    const invocationPayload = await this.getInvocations(runId);
    const invocations = array(invocationPayload.invocations ?? [], 'Runtime invocation list is invalid');
    const artifactPayload = await this.listArtifacts(runId);
    const artifacts = array(artifactPayload.artifacts ?? [], 'Runtime artifact list is invalid');
    const finalSummary = artifacts.find((item) => item?.artifact_type === 'agent.final-output');
    if (!finalSummary || typeof finalSummary.artifact_id !== 'string') {
      throw new CliError('CLI_FINAL_ARTIFACT_MISSING', 'Runtime Run has no agent.final-output Artifact');
    }
    const artifact = await this.getArtifact(runId, finalSummary.artifact_id);
    return { state: 'COMPLETED', route, preflight, submission, confirmed, run, events, invocations, artifacts, artifact };
  }
}
