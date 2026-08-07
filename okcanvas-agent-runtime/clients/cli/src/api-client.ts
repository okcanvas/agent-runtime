import { randomUUID } from "node:crypto";
import { CliError, type RuntimeConfig } from "./config.js";
import { parseSseJson } from "./sse.js";
import type {
  AgentDefinition,
  Artifact,
  ExecutionObserver,
  JsonObject,
  ProductSession,
  RunEvent,
  RunOutcome,
  RunSnapshot
} from "./types.js";

function asObject(value: unknown, message: string): JsonObject {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new CliError("CLI_RESPONSE_INVALID", message);
  }
  return value as JsonObject;
}

export class ControlApiClient {
  readonly config: RuntimeConfig;

  constructor(config: RuntimeConfig) {
    this.config = config;
  }

  async health(): Promise<JsonObject> {
    return this.request("GET", "/healthz", "none");
  }

  async listAgents(): Promise<AgentDefinition[]> {
    const payload = await this.request("GET", "/v1/agent-definitions", "admin");
    const definitions = payload.definitions;
    if (!Array.isArray(definitions)) throw new CliError("CLI_RESPONSE_INVALID", "Agent catalog response is invalid");
    return definitions.map((item) => asObject(item, "Agent catalog item is invalid") as AgentDefinition);
  }

  async getAgent(agentId: string): Promise<AgentDefinition> {
    return (await this.request("GET", `/v1/agent-definitions/${encodeURIComponent(agentId)}`, "admin")) as AgentDefinition;
  }

  async createSession(agentId: string): Promise<ProductSession> {
    return (await this.request("POST", "/v1/sessions", "submitter", {
      agent_definition_id: agentId
    })) as ProductSession;
  }

  async listSessions(): Promise<ProductSession[]> {
    const payload = await this.request("GET", "/v1/sessions?limit=200", "admin");
    const sessions = payload.sessions;
    if (!Array.isArray(sessions)) throw new CliError("CLI_RESPONSE_INVALID", "Session catalog response is invalid");
    return sessions.map((item) => asObject(item, "Session catalog item is invalid") as ProductSession);
  }

  async getSession(sessionId: string): Promise<ProductSession> {
    return (await this.request("GET", `/v1/sessions/${encodeURIComponent(sessionId)}`, "admin")) as ProductSession;
  }

  async clearSession(sessionId: string): Promise<ProductSession> {
    return (await this.request("POST", `/v1/sessions/${encodeURIComponent(sessionId)}/clear`, "submitter")) as ProductSession;
  }

  async evaluate(runId: string, caseId: string): Promise<JsonObject> {
    return this.request(
      "POST",
      `/v1/runs/${encodeURIComponent(runId)}/evaluations`,
      "admin",
      { case_id: caseId }
    );
  }

  async execute(
    agent: AgentDefinition,
    requestText: string,
    model: string | undefined,
    sessionId: string | undefined,
    confirm: (challenge: string) => Promise<boolean>,
    evaluationCaseId?: string,
    observer?: ExecutionObserver
  ): Promise<RunOutcome | null> {
    const preflightBody: JsonObject = {
      agent_definition_id: agent.agent_id,
      input: requestText,
      idempotency_key: `node-cli-${randomUUID()}`
    };
    if (model) preflightBody.model = model;
    if (sessionId) preflightBody.session_id = sessionId;
    const preflight = await this.request("POST", "/v1/run-submissions/preflight", "submitter", preflightBody);
    await observer?.onPreflight?.(preflight, agent, model);
    if (preflight.approval_required !== false || preflight.executable_now !== true) {
      throw new CliError("CLI_PREFLIGHT_NOT_EXECUTABLE", "Selected Agent is not immediately executable in the current CLI");
    }
    const challenge = typeof preflight.confirmation_challenge === "string" ? preflight.confirmation_challenge : "";
    if (!challenge) throw new CliError("CLI_CONFIRMATION_MISSING", "Control API returned no confirmation challenge");
    if (!(await confirm(challenge))) return null;
    const submissionId = String(preflight.submission_id ?? "");
    const confirmed = await this.request(
      "POST",
      `/v1/run-submissions/${encodeURIComponent(submissionId)}/confirm`,
      "submitter",
      { confirmation: challenge }
    );
    await observer?.onConfirmed?.(confirmed);
    const runId = String(confirmed.run_id ?? "");
    if (!runId) throw new CliError("CLI_RESPONSE_INVALID", "Control API returned no Run ID");

    const events: RunEvent[] = [];
    for await (const event of this.streamEvents(runId)) {
      if (event.run_id !== runId) throw new CliError("CLI_SSE_RUN_ID_MISMATCH", "Persisted SSE returned another Run");
      events.push(event);
      await observer?.onEvent?.(event);
    }
    const run = (await this.request("GET", `/v1/runs/${encodeURIComponent(runId)}`, "admin")) as RunSnapshot;
    if (run.status !== "SUCCEEDED") {
      throw new CliError("CLI_RUN_FAILED", `Governed Run ended in ${String(run.status)}`);
    }
    const invocationPayload = await this.request("GET", `/v1/runs/${encodeURIComponent(runId)}/invocations`, "admin");
    const invocations = Array.isArray(invocationPayload.invocations)
      ? invocationPayload.invocations.map((item) => asObject(item, "Invocation item is invalid"))
      : [];
    const artifact = (await this.request("GET", `/v1/runs/${encodeURIComponent(runId)}/artifact`, "admin")) as Artifact;
    let evaluation: JsonObject | undefined;
    if (evaluationCaseId) {
      evaluation = await this.evaluate(runId, evaluationCaseId);
    }
    return { agent, preflight, confirmed, events, run, invocations, artifact, ...(evaluation ? { evaluation } : {}) };
  }

  private async *streamEvents(runId: string): AsyncGenerator<RunEvent> {
    const response = await fetch(`${this.config.baseUrl}/v1/runs/${encodeURIComponent(runId)}/events/stream?cursor=0`, {
      headers: {
        Accept: "text/event-stream",
        "Last-Event-ID": "0",
        "X-OKCanvas-Admin-Key": this.config.adminKey
      }
    });
    if (!response.ok) await this.raiseApiError(response);
    if (!response.body) throw new CliError("CLI_SSE_RESPONSE_INVALID", "Persisted SSE response has no body");
    yield* parseSseJson(response.body);
  }

  private headers(authority: "none" | "admin" | "submitter"): Record<string, string> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (authority !== "none") headers["X-OKCanvas-Admin-Key"] = this.config.adminKey;
    if (authority === "submitter") headers["X-OKCanvas-Run-Submitter-Key"] = this.config.submitterKey;
    return headers;
  }

  private async request(
    method: string,
    path: string,
    authority: "none" | "admin" | "submitter",
    body?: JsonObject
  ): Promise<JsonObject> {
    let response: Response;
    try {
      response = await fetch(`${this.config.baseUrl}${path}`, {
        method,
        headers: { ...this.headers(authority), ...(body ? { "Content-Type": "application/json" } : {}) },
        ...(body ? { body: JSON.stringify(body) } : {})
      });
    } catch {
      throw new CliError("CLI_CONNECTION_FAILED", "Unable to reach the local Control API");
    }
    if (!response.ok) await this.raiseApiError(response);
    return asObject(await response.json(), "Control API returned an invalid JSON object");
  }

  private async raiseApiError(response: Response): Promise<never> {
    let payload: JsonObject = {};
    try {
      payload = asObject(await response.json(), "Control API returned an invalid error body");
    } catch {
      // Keep the bounded fallback below.
    }
    throw new CliError(
      String(payload.code ?? "CLI_CONTROL_API_ERROR"),
      String(payload.message ?? `Control API request failed (${response.status})`),
      response.status
    );
  }
}
