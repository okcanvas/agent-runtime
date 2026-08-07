import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import { FakeState } from "./state.js";
import { getEntity, resolveContext, searchContext } from "./context-resolver.js";
import type { EntityType, FaultMode, OrganizationTerm, Role, TermAlias } from "./types.js";

export const PRODUCT_TOKEN = "example-organization-context-api-token";

function json(response: ServerResponse, status: number, payload: unknown): void {
  response.statusCode = status;
  response.setHeader("content-type", "application/json; charset=utf-8");
  response.end(JSON.stringify(payload));
}

async function readJson(request: IncomingMessage): Promise<unknown> {
  const chunks: Uint8Array[] = [];
  for await (const chunk of request) chunks.push(chunk);
  if (chunks.length === 0) return {};
  const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const result = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.length;
  }
  return JSON.parse(new TextDecoder().decode(result));
}

function header(request: IncomingMessage, name: string): string {
  const value = request.headers[name.toLowerCase()];
  return Array.isArray(value) ? value.join(",") : value ?? "";
}

function roles(request: IncomingMessage): string[] {
  return header(request, "x-principal-roles").split(",").map((item) => item.trim()).filter(Boolean).sort();
}

function identityOk(request: IncomingMessage, response: ServerResponse, admin = false): boolean {
  if (header(request, "authorization") !== `Bearer ${PRODUCT_TOKEN}`) {
    json(response, 401, { error: "expired_or_invalid_token" });
    return false;
  }
  if (!header(request, "x-tenant-id") || !header(request, "x-principal-id")) {
    json(response, 403, { error: "delegated_identity_missing" });
    return false;
  }
  const delegatedRoles = roles(request);
  if (!delegatedRoles.includes("agent-user") || (admin && !delegatedRoles.includes("admin"))) {
    json(response, 403, { error: "role_denied" });
    return false;
  }
  if (!header(request, "x-delegation-id").startsWith("delegation_")) {
    json(response, 403, { error: "delegation_invalid" });
    return false;
  }
  return true;
}

function operationFor(method: string, path: string): string | null {
  if (method === "POST" && path === "/api/v1/context/resolve") return "context.resolve";
  if (method === "POST" && path === "/api/v1/context/search") return "context.search";
  if (method === "GET" && path.startsWith("/api/v1/context/entities/")) return "context.get";
  if (method === "POST" && path === "/api/v1/glossary/resolve") return "glossary.resolve";
  if (method === "POST" && path === "/api/v1/glossary/search") return "glossary.search";
  if (method === "GET" && path === "/api/v1/glossary/catalog-state") return "catalog.state";
  if (method === "GET" && path === "/api/v1/glossary/changes") return "catalog.changes";
  if (method === "POST" && path === "/api/v1/admin/glossary/terms") return "admin.create";
  if (method === "PUT" && path.startsWith("/api/v1/admin/glossary/terms/")) return "admin.update";
  if (method === "DELETE" && path.startsWith("/api/v1/admin/glossary/terms/")) return "admin.delete";
  if (method === "GET" && path.startsWith("/api/v1/glossary/terms/")) return "glossary.get";
  return null;
}

async function applyFault(mode: FaultMode, response: ServerResponse): Promise<boolean> {
  const status: Record<FaultMode, number> = {
    NONE: 200, EXPIRED_TOKEN: 401, PERMISSION_DENIED: 403, NOT_FOUND: 404,
    VERSION_CONFLICT: 409, RATE_LIMITED: 429, INTERNAL_ERROR: 500, UNAVAILABLE: 503,
    TIMEOUT: 503, MALFORMED_RESPONSE: 200,
  };
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
  if (mode !== "NONE") {
    json(response, status[mode], { error: mode.toLowerCase() });
    return true;
  }
  return false;
}

function normalize(value: string): string {
  return value.trim().toLocaleLowerCase("ko-KR").replace(/\s+/g, " ");
}

function scopedAliases(term: OrganizationTerm, organizationUnitId: string | null): TermAlias[] {
  if (organizationUnitId === null) return term.aliases;
  return term.aliases.filter((alias) => alias.organization_unit_id === null || alias.organization_unit_id === organizationUnitId);
}

function visibleTerms(state: FakeState, request: IncomingMessage): OrganizationTerm[] {
  const tenant = header(request, "x-tenant-id");
  const delegatedRoles = roles(request) as Role[];
  return state.terms.filter((term) => term.tenant_id === tenant && term.status === "ACTIVE" &&
    term.visible_to_roles.some((role) => delegatedRoles.includes(role)));
}

function matchTerm(term: OrganizationTerm, query: string, organizationUnitId: string | null): {
  score: number; match_type: string; matched_alias: string | null;
} | null {
  const normalizedQuery = normalize(query);
  const canonical = normalize(term.canonical_name);
  if (normalizedQuery === canonical) return { score: 0, match_type: "EXACT_CANONICAL", matched_alias: null };
  for (const alias of scopedAliases(term, organizationUnitId)) {
    if (normalizedQuery === normalize(alias.value)) return { score: 1, match_type: "EXACT_ALIAS", matched_alias: alias.value };
  }
  if (normalizedQuery.includes(canonical) || canonical.includes(normalizedQuery)) {
    return { score: 2, match_type: "CONTAINS_CANONICAL", matched_alias: null };
  }
  for (const alias of scopedAliases(term, organizationUnitId)) {
    const normalizedAlias = normalize(alias.value);
    if (normalizedQuery.includes(normalizedAlias) || normalizedAlias.includes(normalizedQuery)) {
      return { score: 3, match_type: "CONTAINS_ALIAS", matched_alias: alias.value };
    }
  }
  if (normalize(term.definition).includes(normalizedQuery)) return { score: 4, match_type: "DEFINITION", matched_alias: null };
  return null;
}

function publicTerm(term: OrganizationTerm, matchedAlias: string | null = null, matchType: string | null = null): Record<string, unknown> {
  return {
    term_id: term.term_id,
    canonical_name: term.canonical_name,
    definition: term.definition,
    classification: term.classification,
    status: term.status,
    revision: term.revision,
    row_version: term.row_version,
    aliases: term.aliases,
    bindings: term.bindings,
    source: term.source,
    updated_at: term.updated_at,
    deleted_at: term.deleted_at,
    matched_alias: matchedAlias,
    match_type: matchType,
  };
}

function validTermBody(value: unknown): value is Omit<OrganizationTerm, "revision" | "row_version" | "updated_at" | "deleted_at"> {
  if (!value || typeof value !== "object") return false;
  const body = value as Record<string, unknown>;
  return typeof body.term_id === "string" && typeof body.tenant_id === "string" &&
    typeof body.canonical_name === "string" && typeof body.definition === "string" &&
    typeof body.classification === "string" && body.status === "ACTIVE" &&
    Array.isArray(body.visible_to_roles) && Array.isArray(body.aliases) && Array.isArray(body.bindings) &&
    Boolean(body.source) && typeof body.source === "object";
}

export function createOrganizationContextFake(state = new FakeState()): { server: Server; state: FakeState } {
  const server = createServer(async (request, response) => {
    const method = request.method ?? "GET";
    const url = new URL(request.url ?? "/", "http://organization-context-fake");
    const path = url.pathname;

    if (method === "GET" && path === "/healthz") {
      json(response, 200, { state: "READY", example_template_only: true, version: "0.2.2", catalog_revision: state.catalog_revision, production_sot: "DATABASE", example_sot: "COMMITTED_JSON_FIXTURES", fixture_valid: Object.values(state.validations).every((item) => item.valid) });
      return;
    }
    if (path.startsWith("/_fake/")) {
      if (method === "POST" && path === "/_fake/reset") {
        state.reset();
        json(response, 200, { state: "RESET", catalog_revision: state.catalog_revision, fixture_valid: Object.values(state.validations).every((item) => item.valid) });
        return;
      }
      if (method === "POST" && path === "/_fake/seed") {
        const body = await readJson(request) as { terms?: unknown; catalog_revision?: unknown };
        if (!Array.isArray(body.terms) || typeof body.catalog_revision !== "number") {
          json(response, 400, { error: "invalid_seed" });
          return;
        }
        state.replaceSeed(body.terms as OrganizationTerm[], body.catalog_revision);
        json(response, 200, { state: "SEEDED", catalog_revision: state.catalog_revision, term_count: state.terms.length });
        return;
      }
      if (method === "PUT" && path === "/_fake/clock") {
        const body = await readJson(request) as { now?: unknown };
        if (typeof body.now !== "string" || body.now.length === 0) {
          json(response, 400, { error: "invalid_clock" });
          return;
        }
        state.clock = { now: body.now };
        json(response, 200, state.clock);
        return;
      }
      if (method === "PUT" && path === "/_fake/faults") {
        const body = await readJson(request) as { operation?: unknown; mode?: unknown; count?: unknown };
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
        json(response, 200, { clock: state.clock, catalog_revision: state.catalog_revision, term_count: state.terms.filter((term) => term.tenant_id === "tenant-a").length, dataset_counts: state.validations["tenant-a"]?.counts ?? {}, fixture_validations: state.validations, change_count: state.changes.length, faults: state.faults, production_sot: "DATABASE", example_sot: "COMMITTED_JSON_FIXTURES" });
        return;
      }
      json(response, 404, { error: "fake_control_not_found" });
      return;
    }

    const operation = operationFor(method, path);
    if (!operation) {
      json(response, 404, { error: "product_api_not_found" });
      return;
    }
    const body = method === "POST" || method === "PUT" ? await readJson(request) : {};
    state.capture({
      method, path,
      tenant_id: header(request, "x-tenant-id") || null,
      principal_id: header(request, "x-principal-id") || null,
      roles: roles(request),
      organization_unit_id: header(request, "x-organization-unit-id") || null,
      delegation_id: header(request, "x-delegation-id") || null,
      request_id: header(request, "x-request-id") || null,
      authorization_present: Boolean(header(request, "authorization")),
      authorization_value_recorded: false,
      body,
    });
    const admin = operation.startsWith("admin.");
    if (!identityOk(request, response, admin)) return;
    const fault = state.consumeFault(operation);
    if (fault && await applyFault(fault.mode, response)) return;

    if (operation === "context.resolve" || operation === "context.search") {
      const input = body as { query?: unknown; entity_types?: unknown; organization_unit_id?: unknown; limit?: unknown };
      if (typeof input.query !== "string" || (operation === "context.resolve" && input.query.trim().length === 0)) {
        json(response, 400, { error: "invalid_query" });
        return;
      }
      const tenant = header(request, "x-tenant-id");
      const dataset = state.dataset(tenant);
      if (!dataset) {
        json(response, 404, { error: "tenant_catalog_not_found" });
        return;
      }
      const allowedTypes: EntityType[] = ["TERM", "DEPARTMENT", "POSITION", "EMPLOYEE", "PRODUCT", "CLIENT", "PROJECT", "SYSTEM", "CAPABILITY"];
      const entityTypes = Array.isArray(input.entity_types)
        ? input.entity_types.filter((item): item is EntityType => typeof item === "string" && allowedTypes.includes(item as EntityType))
        : undefined;
      const unit = typeof input.organization_unit_id === "string" ? input.organization_unit_id : header(request, "x-organization-unit-id") || null;
      const limit = typeof input.limit === "number" ? Math.max(1, Math.min(input.limit, 20)) : 20;
      const result = operation === "context.search"
        ? searchContext(dataset, input.query, entityTypes, limit, unit)
        : resolveContext(dataset, input.query, entityTypes, limit, unit);
      json(response, 200, result);
      return;
    }

    if (operation === "context.get") {
      const tenant = header(request, "x-tenant-id");
      const dataset = state.dataset(tenant);
      if (!dataset) { json(response, 404, { error: "tenant_catalog_not_found" }); return; }
      const suffix = path.slice("/api/v1/context/entities/".length).split("/");
      if (suffix.length !== 2) { json(response, 400, { error: "invalid_entity_path" }); return; }
      const entityType = decodeURIComponent(suffix[0] ?? "") as EntityType;
      const entityId = decodeURIComponent(suffix[1] ?? "");
      const record = getEntity(dataset, entityType, entityId);
      if (!record) { json(response, 404, { error: "organization_entity_not_found" }); return; }
      json(response, 200, { schema_version: "okcanvas-organization-context-entity-v1", catalog_revision: dataset.catalog_revision, record });
      return;
    }

    if (operation === "glossary.resolve") {
      const input = body as { query?: unknown; organization_unit_id?: unknown; limit?: unknown };
      if (typeof input.query !== "string" || input.query.trim().length === 0) {
        json(response, 400, { error: "invalid_query" });
        return;
      }
      const unit = typeof input.organization_unit_id === "string" ? input.organization_unit_id : header(request, "x-organization-unit-id") || null;
      const limit = typeof input.limit === "number" ? Math.max(1, Math.min(input.limit, 20)) : 10;
      const candidates = visibleTerms(state, request).map((term) => ({ term, match: matchTerm(term, input.query as string, unit) }))
        .filter((item): item is { term: OrganizationTerm; match: { score: number; match_type: string; matched_alias: string | null } } => item.match !== null)
        .sort((a, b) => a.match.score - b.match.score || a.term.term_id.localeCompare(b.term.term_id));
      const topScore = candidates[0]?.match.score;
      const topCount = topScore === undefined ? 0 : candidates.filter((item) => item.match.score === topScore).length;
      const matches = candidates.slice(0, limit).map((item) => publicTerm(item.term, item.match.matched_alias, item.match.match_type));
      json(response, 200, {
        schema_version: "okcanvas-organization-context-resolve-v1",
        catalog_revision: state.catalogRevision(header(request, "x-tenant-id")),
        query: input.query,
        organization_unit_id: unit,
        resolved: topCount === 1,
        ambiguous: topCount > 1,
        matches,
      });
      return;
    }

    if (operation === "glossary.search") {
      const input = body as { query?: unknown; organization_unit_id?: unknown; limit?: unknown };
      const query = typeof input.query === "string" ? input.query : "";
      const unit = typeof input.organization_unit_id === "string" ? input.organization_unit_id : header(request, "x-organization-unit-id") || null;
      const limit = typeof input.limit === "number" ? Math.max(1, Math.min(input.limit, 50)) : 20;
      const records = visibleTerms(state, request).filter((term) => query.length === 0 || matchTerm(term, query, unit) !== null)
        .sort((a, b) => a.term_id.localeCompare(b.term_id)).slice(0, limit).map((term) => publicTerm(term));
      json(response, 200, { schema_version: "okcanvas-organization-context-search-v1", catalog_revision: state.catalogRevision(header(request, "x-tenant-id")), records });
      return;
    }

    if (operation === "glossary.get") {
      const termId = decodeURIComponent(path.slice("/api/v1/glossary/terms/".length));
      const term = visibleTerms(state, request).find((item) => item.term_id === termId);
      if (!term) {
        json(response, 404, { error: "term_not_found" });
        return;
      }
      json(response, 200, { schema_version: "okcanvas-organization-context-term-v1", catalog_revision: state.catalogRevision(header(request, "x-tenant-id")), record: publicTerm(term) });
      return;
    }

    if (operation === "catalog.state") {
      const tenant = header(request, "x-tenant-id");
      const dataset = state.dataset(tenant);
      json(response, 200, { schema_version: "okcanvas-organization-context-catalog-state-v2", catalog_revision: state.catalogRevision(tenant), effective_at: state.clock.now, production_sot: "DATABASE", example_sot: "COMMITTED_JSON_FIXTURES", dataset_counts: state.validations[tenant]?.counts ?? {}, fixture_valid: state.validations[tenant]?.valid ?? false, fixture_role: dataset?.manifest.fixture_role ?? null });
      return;
    }

    if (operation === "catalog.changes") {
      const after = Number(url.searchParams.get("after") ?? "0");
      const limit = Math.max(1, Math.min(Number(url.searchParams.get("limit") ?? "100"), 200));
      json(response, 200, { schema_version: "okcanvas-organization-context-change-feed-v1", current_revision: state.catalog_revision, changes: state.changes.filter((item) => item.change_seq > after).slice(0, limit) });
      return;
    }

    if (operation === "admin.create") {
      if (!validTermBody(body)) {
        json(response, 400, { error: "invalid_term" });
        return;
      }
      const tenant = header(request, "x-tenant-id");
      if (body.tenant_id !== tenant || state.terms.some((term) => term.tenant_id === tenant && term.term_id === body.term_id)) {
        json(response, 409, { error: "term_conflict" });
        return;
      }
      const revision = state.appendChange("CREATE", body.term_id);
      const term: OrganizationTerm = { ...body, revision, row_version: 1, updated_at: state.clock.now, deleted_at: null };
      state.terms.push(term);
      json(response, 201, { catalog_revision: state.catalog_revision, record: publicTerm(term) });
      return;
    }

    const adminPrefix = "/api/v1/admin/glossary/terms/";
    const termId = decodeURIComponent(path.slice(adminPrefix.length));
    const term = state.terms.find((item) => item.tenant_id === header(request, "x-tenant-id") && item.term_id === termId);
    if (!term) {
      json(response, 404, { error: "term_not_found" });
      return;
    }
    const expected = Number(header(request, "if-match"));
    if (!Number.isInteger(expected) || expected !== term.row_version) {
      json(response, 409, { error: "row_version_conflict", current_row_version: term.row_version });
      return;
    }
    if (operation === "admin.update") {
      const update = body as Record<string, unknown>;
      if (typeof update.canonical_name !== "string" || typeof update.definition !== "string" || !Array.isArray(update.aliases) || !Array.isArray(update.bindings)) {
        json(response, 400, { error: "invalid_update" });
        return;
      }
      term.canonical_name = update.canonical_name;
      term.definition = update.definition;
      term.aliases = update.aliases as OrganizationTerm["aliases"];
      term.bindings = update.bindings as OrganizationTerm["bindings"];
      term.row_version += 1;
      term.revision = state.appendChange("UPDATE", term.term_id);
      term.updated_at = state.clock.now;
      json(response, 200, { catalog_revision: state.catalog_revision, record: publicTerm(term) });
      return;
    }
    term.status = "RETIRED";
    term.deleted_at = state.clock.now;
    term.updated_at = state.clock.now;
    term.row_version += 1;
    term.revision = state.appendChange("DELETE", term.term_id);
    json(response, 200, { catalog_revision: state.catalog_revision, record: publicTerm(term) });
  });
  return { server, state };
}
