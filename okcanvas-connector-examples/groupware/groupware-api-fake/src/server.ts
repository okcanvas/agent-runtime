import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import { FakeState } from "./state.js";
import type { FaultMode, Role } from "./types.js";

const PRODUCT_TOKEN = "example-groupware-api-token";

function json(response: ServerResponse, status: number, payload: unknown): void {
  response.statusCode = status;
  response.setHeader("content-type", "application/json; charset=utf-8");
  response.end(JSON.stringify(payload));
}

async function readJson(request: IncomingMessage): Promise<unknown> {
  const chunks: Uint8Array[] = [];
  for await (const chunk of request) chunks.push(chunk);
  if (chunks.length === 0) return {};
  const text = new TextDecoder().decode(concat(chunks));
  return JSON.parse(text);
}

function concat(chunks: Uint8Array[]): Uint8Array {
  const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const result = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.length;
  }
  return result;
}

function header(request: IncomingMessage, name: string): string {
  const value = request.headers[name.toLowerCase()];
  return Array.isArray(value) ? value.join(",") : value ?? "";
}

function roles(request: IncomingMessage): string[] {
  return header(request, "x-principal-roles")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .sort();
}

function requireProductIdentity(request: IncomingMessage, response: ServerResponse): boolean {
  if (header(request, "authorization") !== `Bearer ${PRODUCT_TOKEN}`) {
    json(response, 401, { error: "expired_or_invalid_token" });
    return false;
  }
  if (!header(request, "x-tenant-id") || !header(request, "x-principal-id")) {
    json(response, 403, { error: "delegated_identity_missing" });
    return false;
  }
  const delegatedRoles = roles(request);
  if (!delegatedRoles.includes("agent-user")) {
    json(response, 403, { error: "role_denied" });
    return false;
  }
  if (!header(request, "x-delegation-id").startsWith("delegation_")) {
    json(response, 403, { error: "delegation_invalid" });
    return false;
  }
  return true;
}

function statusForFault(mode: FaultMode): number {
  return {
    NONE: 200,
    EXPIRED_TOKEN: 401,
    PERMISSION_DENIED: 403,
    NOT_FOUND: 404,
    VERSION_CONFLICT: 409,
    RATE_LIMITED: 429,
    INTERNAL_ERROR: 500,
    UNAVAILABLE: 503,
    TIMEOUT: 503,
    MALFORMED_RESPONSE: 200,
    PARTIAL_RESPONSE: 200,
  }[mode];
}

async function applyFault(mode: FaultMode, response: ServerResponse): Promise<boolean> {
  if (mode === "TIMEOUT") {
    await new Promise<void>((resolve) => setTimeout(resolve, 250));
    json(response, 503, { error: "timeout_simulated" });
    return true;
  }
  if (mode === "MALFORMED_RESPONSE") {
    response.statusCode = 200;
    response.setHeader("content-type", "application/json");
    response.end("{not-json");
    return true;
  }
  if (mode !== "NONE" && mode !== "PARTIAL_RESPONSE") {
    json(response, statusForFault(mode), { error: mode.toLowerCase() });
    return true;
  }
  return false;
}

export function createGroupwareFake(state = new FakeState()): { server: Server; state: FakeState } {
  const server = createServer(async (request, response) => {
    const method = request.method ?? "GET";
    const path = new URL(request.url ?? "/", "http://groupware-fake").pathname;

    if (method === "GET" && path === "/healthz") {
      json(response, 200, { state: "READY", example_template_only: true, version: "0.1.0" });
      return;
    }
    if (path.startsWith("/_fake/")) {
      if (method === "POST" && path === "/_fake/reset") {
        state.reset();
        json(response, 200, { state: "RESET", clock: state.clock });
        return;
      }
      if (method === "PUT" && path === "/_fake/clock") {
        const body = (await readJson(request)) as { now?: unknown };
        if (typeof body.now !== "string" || body.now.length === 0) {
          json(response, 400, { error: "invalid_clock" });
          return;
        }
        state.clock = { now: body.now };
        json(response, 200, state.clock);
        return;
      }
      if (method === "PUT" && path === "/_fake/faults") {
        const body = (await readJson(request)) as { operation?: unknown; mode?: unknown; count?: unknown };
        if (typeof body.operation !== "string" || typeof body.mode !== "string" || typeof body.count !== "number") {
          json(response, 400, { error: "invalid_fault" });
          return;
        }
        state.setFault({ operation: body.operation, mode: body.mode as FaultMode, remaining: body.count });
        json(response, 200, { faults: state.faults });
        return;
      }
      if (method === "GET" && path === "/_fake/requests") {
        json(response, 200, { requests: state.requests });
        return;
      }
      if (method === "GET" && path === "/_fake/state") {
        json(response, 200, {
          clock: state.clock,
          notice_count: state.notices.length,
          mail_count: state.mail.length,
          calendar_count: state.calendar.length,
          faults: state.faults,
        });
        return;
      }
      json(response, 404, { error: "fake_control_not_found" });
      return;
    }

    const operations: Record<string, string> = {
      "/api/v1/notices/search": "notices.search",
      "/api/v1/mail/search": "mail.search",
      "/api/v1/calendar/events/list": "calendar.list",
    };
    const operation = operations[path];
    if (method !== "POST" || !operation) {
      json(response, 404, { error: "product_api_not_found" });
      return;
    }
    const body = await readJson(request);
    state.capture({
      method,
      path,
      tenant_id: header(request, "x-tenant-id") || null,
      principal_id: header(request, "x-principal-id") || null,
      roles: roles(request),
      delegation_id: header(request, "x-delegation-id") || null,
      request_id: header(request, "x-request-id") || null,
      authorization_present: Boolean(header(request, "authorization")),
      authorization_value_recorded: false,
      body,
    });
    if (!requireProductIdentity(request, response)) return;
    const fault = state.consumeFault(operation);
    if (fault && (await applyFault(fault.mode, response))) return;

    const tenant = header(request, "x-tenant-id");
    const principal = header(request, "x-principal-id");
    const delegatedRoles = roles(request) as Role[];
    const limit = typeof (body as { limit?: unknown }).limit === "number" ? (body as { limit: number }).limit : 20;
    const query = typeof (body as { query?: unknown }).query === "string" ? (body as { query: string }).query.toLowerCase() : "";
    let records: unknown[];
    if (operation === "notices.search") {
      records = state.notices.filter(
        (item) => item.tenant_id === tenant && item.visible_to_roles.some((role) => delegatedRoles.includes(role)) &&
          (!query || item.title.toLowerCase().includes(query) || item.body.toLowerCase().includes(query)),
      );
    } else if (operation === "mail.search") {
      records = state.mail.filter(
        (item) => item.tenant_id === tenant && item.owner_principal_id === principal &&
          (!query || item.subject.toLowerCase().includes(query) || item.body.toLowerCase().includes(query)),
      );
    } else {
      records = state.calendar.filter(
        (item) => item.tenant_id === tenant &&
          (item.owner_principal_id === principal || delegatedRoles.includes("manager") || delegatedRoles.includes("admin")),
      );
    }
    if (fault?.mode === "PARTIAL_RESPONSE") {
      json(response, 200, { records: records.slice(0, 1), partial: true });
      return;
    }
    json(response, 200, { records: records.slice(0, Math.max(0, Math.min(limit, 50))) });
  });
  return { server, state };
}

