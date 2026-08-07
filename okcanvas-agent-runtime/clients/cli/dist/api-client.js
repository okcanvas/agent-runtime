import { randomUUID } from "node:crypto";
import { CliError } from "./config.js";
import { parseSseJson } from "./sse.js";
function asObject(value, message) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
        throw new CliError("CLI_RESPONSE_INVALID", message);
    }
    return value;
}
export class ControlApiClient {
    config;
    constructor(config) {
        this.config = config;
    }
    async health() {
        return this.request("GET", "/healthz", "none");
    }
    async listAgents() {
        const payload = await this.request("GET", "/v1/agent-definitions", "admin");
        const definitions = payload.definitions;
        if (!Array.isArray(definitions))
            throw new CliError("CLI_RESPONSE_INVALID", "Agent catalog response is invalid");
        return definitions.map((item) => asObject(item, "Agent catalog item is invalid"));
    }
    async getAgent(agentId) {
        return (await this.request("GET", `/v1/agent-definitions/${encodeURIComponent(agentId)}`, "admin"));
    }
    async createSession(agentId) {
        return (await this.request("POST", "/v1/sessions", "submitter", {
            agent_definition_id: agentId
        }));
    }
    async listSessions() {
        const payload = await this.request("GET", "/v1/sessions?limit=200", "admin");
        const sessions = payload.sessions;
        if (!Array.isArray(sessions))
            throw new CliError("CLI_RESPONSE_INVALID", "Session catalog response is invalid");
        return sessions.map((item) => asObject(item, "Session catalog item is invalid"));
    }
    async getSession(sessionId) {
        return (await this.request("GET", `/v1/sessions/${encodeURIComponent(sessionId)}`, "admin"));
    }
    async clearSession(sessionId) {
        return (await this.request("POST", `/v1/sessions/${encodeURIComponent(sessionId)}/clear`, "submitter"));
    }
    async evaluate(runId, caseId) {
        return this.request("POST", `/v1/runs/${encodeURIComponent(runId)}/evaluations`, "admin", { case_id: caseId });
    }
    async execute(agent, requestText, model, sessionId, confirm, evaluationCaseId, observer) {
        const preflightBody = {
            agent_definition_id: agent.agent_id,
            input: requestText,
            idempotency_key: `node-cli-${randomUUID()}`
        };
        if (model)
            preflightBody.model = model;
        if (sessionId)
            preflightBody.session_id = sessionId;
        const preflight = await this.request("POST", "/v1/run-submissions/preflight", "submitter", preflightBody);
        await observer?.onPreflight?.(preflight, agent, model);
        if (preflight.approval_required !== false || preflight.executable_now !== true) {
            throw new CliError("CLI_PREFLIGHT_NOT_EXECUTABLE", "Selected Agent is not immediately executable in the current CLI");
        }
        const challenge = typeof preflight.confirmation_challenge === "string" ? preflight.confirmation_challenge : "";
        if (!challenge)
            throw new CliError("CLI_CONFIRMATION_MISSING", "Control API returned no confirmation challenge");
        if (!(await confirm(challenge)))
            return null;
        const submissionId = String(preflight.submission_id ?? "");
        const confirmed = await this.request("POST", `/v1/run-submissions/${encodeURIComponent(submissionId)}/confirm`, "submitter", { confirmation: challenge });
        await observer?.onConfirmed?.(confirmed);
        const runId = String(confirmed.run_id ?? "");
        if (!runId)
            throw new CliError("CLI_RESPONSE_INVALID", "Control API returned no Run ID");
        const events = [];
        for await (const event of this.streamEvents(runId)) {
            if (event.run_id !== runId)
                throw new CliError("CLI_SSE_RUN_ID_MISMATCH", "Persisted SSE returned another Run");
            events.push(event);
            await observer?.onEvent?.(event);
        }
        const run = (await this.request("GET", `/v1/runs/${encodeURIComponent(runId)}`, "admin"));
        if (run.status !== "SUCCEEDED") {
            throw new CliError("CLI_RUN_FAILED", `Governed Run ended in ${String(run.status)}`);
        }
        const invocationPayload = await this.request("GET", `/v1/runs/${encodeURIComponent(runId)}/invocations`, "admin");
        const invocations = Array.isArray(invocationPayload.invocations)
            ? invocationPayload.invocations.map((item) => asObject(item, "Invocation item is invalid"))
            : [];
        const artifact = (await this.request("GET", `/v1/runs/${encodeURIComponent(runId)}/artifact`, "admin"));
        let evaluation;
        if (evaluationCaseId) {
            evaluation = await this.evaluate(runId, evaluationCaseId);
        }
        return { agent, preflight, confirmed, events, run, invocations, artifact, ...(evaluation ? { evaluation } : {}) };
    }
    async *streamEvents(runId) {
        const response = await fetch(`${this.config.baseUrl}/v1/runs/${encodeURIComponent(runId)}/events/stream?cursor=0`, {
            headers: {
                Accept: "text/event-stream",
                "Last-Event-ID": "0",
                "X-OKCanvas-Admin-Key": this.config.adminKey
            }
        });
        if (!response.ok)
            await this.raiseApiError(response);
        if (!response.body)
            throw new CliError("CLI_SSE_RESPONSE_INVALID", "Persisted SSE response has no body");
        yield* parseSseJson(response.body);
    }
    headers(authority) {
        const headers = { Accept: "application/json" };
        if (authority !== "none")
            headers["X-OKCanvas-Admin-Key"] = this.config.adminKey;
        if (authority === "submitter")
            headers["X-OKCanvas-Run-Submitter-Key"] = this.config.submitterKey;
        return headers;
    }
    async request(method, path, authority, body) {
        let response;
        try {
            response = await fetch(`${this.config.baseUrl}${path}`, {
                method,
                headers: { ...this.headers(authority), ...(body ? { "Content-Type": "application/json" } : {}) },
                ...(body ? { body: JSON.stringify(body) } : {})
            });
        }
        catch {
            throw new CliError("CLI_CONNECTION_FAILED", "Unable to reach the local Control API");
        }
        if (!response.ok)
            await this.raiseApiError(response);
        return asObject(await response.json(), "Control API returned an invalid JSON object");
    }
    async raiseApiError(response) {
        let payload = {};
        try {
            payload = asObject(await response.json(), "Control API returned an invalid error body");
        }
        catch {
            // Keep the bounded fallback below.
        }
        throw new CliError(String(payload.code ?? "CLI_CONTROL_API_ERROR"), String(payload.message ?? `Control API request failed (${response.status})`), response.status);
    }
}
//# sourceMappingURL=api-client.js.map