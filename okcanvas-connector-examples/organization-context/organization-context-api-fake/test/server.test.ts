import assert from "node:assert/strict";
import test from "node:test";
import { createOrganizationContextFake } from "../src/server.js";

async function withServer(run: (baseUrl: string) => Promise<void>): Promise<void> {
  const { server } = createOrganizationContextFake();
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("No server address");
  try {
    await run(`http://127.0.0.1:${address.port}`);
  } finally {
    await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
}

function headers(roles = "agent-user,employee", organizationUnit = "department.human-resources", tenant = "tenant-a"): Record<string, string> {
  return {
    Authorization: "Bearer example-organization-context-api-token",
    "Content-Type": "application/json",
    "X-Tenant-ID": tenant,
    "X-Principal-ID": "user-001",
    "X-Principal-Roles": roles,
    "X-Organization-Unit-ID": organizationUnit,
    "X-Delegation-ID": "delegation_0123456789abcdef0123456789abcdef",
    "X-Request-ID": "request-001",
  };
}

test("loads the committed JSON reference dataset with validated minimum counts", async () => {
  await withServer(async (baseUrl) => {
    const payload = await (await fetch(`${baseUrl}/_fake/state`)).json() as {
      production_sot: string; example_sot: string; dataset_counts: Record<string, number>; fixture_validations: Record<string, { valid: boolean }>;
    };
    assert.equal(payload.production_sot, "DATABASE");
    assert.equal(payload.example_sot, "COMMITTED_JSON_FIXTURES");
    assert.equal(payload.fixture_validations["tenant-a"]?.valid, true);
    assert.equal(payload.dataset_counts.departments, 13);
    assert.equal(payload.dataset_counts.positions, 12);
    assert.equal(payload.dataset_counts.employees, 48);
    assert.equal(payload.dataset_counts.products, 120);
    assert.equal(payload.dataset_counts.clients, 120);
    assert.equal(payload.dataset_counts.glossary, 80);
    assert.equal(payload.dataset_counts.relations, 893);
  });
});

test("resolves department-scoped glossary alias deterministically", async () => {
  await withServer(async (baseUrl) => {
    const response = await fetch(`${baseUrl}/api/v1/glossary/resolve`, {
      method: "POST", headers: headers(), body: JSON.stringify({ query: "PI", organization_unit_id: "department.human-resources", limit: 10 }),
    });
    const payload = await response.json() as { resolved: boolean; ambiguous: boolean; matches: Array<{ term_id: string }> };
    assert.equal(response.status, 200);
    assert.equal(payload.resolved, true);
    assert.equal(payload.ambiguous, false);
    assert.deepEqual(payload.matches.map((item) => item.term_id), ["term.performance-index"]);
  });
});

test("returns glossary ambiguity when organization unit is absent", async () => {
  await withServer(async (baseUrl) => {
    const h = headers();
    delete h["X-Organization-Unit-ID"];
    const payload = await (await fetch(`${baseUrl}/api/v1/glossary/resolve`, {
      method: "POST", headers: h, body: JSON.stringify({ query: "PI", limit: 10 }),
    })).json() as { resolved: boolean; ambiguous: boolean; matches: Array<{ term_id: string }> };
    assert.equal(payload.resolved, false);
    assert.equal(payload.ambiguous, true);
    assert.deepEqual(payload.matches.map((item) => item.term_id), ["term.performance-index", "term.program-increment"]);
  });
});

test("resolves an employee using name department and position context", async () => {
  await withServer(async (baseUrl) => {
    const payload = await (await fetch(`${baseUrl}/api/v1/context/resolve`, {
      method: "POST", headers: headers(), body: JSON.stringify({ query: "플랫폼팀 김민수 선임", entity_types: ["EMPLOYEE"] }),
    })).json() as { resolved: boolean; ambiguous: boolean; matches: Array<{ entity_id: string; matched_by: string[] }> };
    assert.equal(payload.resolved, true);
    assert.equal(payload.ambiguous, false);
    assert.equal(payload.matches[0]?.entity_id, "employee-0017");
    assert.ok(payload.matches[0]?.matched_by.includes("DEPARTMENT_CONTEXT"));
    assert.ok(payload.matches[0]?.matched_by.includes("POSITION_CONTEXT"));
  });
});

test("keeps employee scalar facts and relationship facts consistent", async () => {
  await withServer(async (baseUrl) => {
    for (const expected of [
      { employeeId: "employee-0017", departmentId: "department.platform-development", positionIds: ["position.senior"] },
      { employeeId: "employee-0034", departmentId: "department.enterprise-sales", positionIds: ["position.lead", "position.team-leader"] },
    ]) {
      const payload = await (await fetch(`${baseUrl}/api/v1/context/entities/EMPLOYEE/${expected.employeeId}`, { headers: headers() })).json() as {
        record: {
          record: { department_id: string; position_ids: string[] };
          relations: Array<{ relation_type: string; direction: string; related_entity: { entity_id: string } | null }>;
        };
      };
      assert.equal(payload.record.record.department_id, expected.departmentId);
      assert.deepEqual([...payload.record.record.position_ids].sort(), expected.positionIds);
      const departments = payload.record.relations
        .filter((item) => item.direction === "OUTBOUND" && item.relation_type === "EMPLOYEE_BELONGS_TO_DEPARTMENT")
        .map((item) => item.related_entity?.entity_id).filter((item): item is string => Boolean(item)).sort();
      const positions = payload.record.relations
        .filter((item) => item.direction === "OUTBOUND" && item.relation_type === "EMPLOYEE_HAS_POSITION")
        .map((item) => item.related_entity?.entity_id).filter((item): item is string => Boolean(item)).sort();
      assert.deepEqual(departments, [expected.departmentId]);
      assert.deepEqual(positions, expected.positionIds);
    }
  });
});

test("preserves same-name employee ambiguity without guessing", async () => {
  await withServer(async (baseUrl) => {
    const payload = await (await fetch(`${baseUrl}/api/v1/context/resolve`, {
      method: "POST", headers: headers(), body: JSON.stringify({ query: "김민수", entity_types: ["EMPLOYEE"] }),
    })).json() as { resolved: boolean; ambiguous: boolean; required_disambiguators: string[]; matches: Array<{ entity_id: string }> };
    assert.equal(payload.resolved, false);
    assert.equal(payload.ambiguous, true);
    assert.deepEqual(payload.matches.slice(0, 2).map((item) => item.entity_id), ["employee-0017", "employee-0034"]);
    assert.ok(payload.required_disambiguators.includes("department"));
  });
});

test("preserves similar-client ambiguity and resolves a stable client code", async () => {
  await withServer(async (baseUrl) => {
    const ambiguous = await (await fetch(`${baseUrl}/api/v1/context/resolve`, {
      method: "POST", headers: headers(), body: JSON.stringify({ query: "한빛", entity_types: ["CLIENT"] }),
    })).json() as { ambiguous: boolean; matches: Array<{ entity_id: string }> };
    assert.equal(ambiguous.ambiguous, true);
    assert.equal(ambiguous.matches.slice(0, 4).length, 4);
    const exact = await (await fetch(`${baseUrl}/api/v1/context/resolve`, {
      method: "POST", headers: headers(), body: JSON.stringify({ query: "C-00042", entity_types: ["CLIENT"] }),
    })).json() as { resolved: boolean; matches: Array<{ entity_id: string }> };
    assert.equal(exact.resolved, true);
    assert.equal(exact.matches[0]?.entity_id, "client-0042");
  });
});

test("returns one entity with resolved relationship summaries", async () => {
  await withServer(async (baseUrl) => {
    const payload = await (await fetch(`${baseUrl}/api/v1/context/entities/CLIENT/client-0042`, { headers: headers() })).json() as {
      record: { entity_id: string; relations: Array<{ relation_type: string; related_entity: { display_name: string } | null }> };
    };
    assert.equal(payload.record.entity_id, "client-0042");
    assert.ok(payload.record.relations.some((item) => item.relation_type === "EMPLOYEE_MANAGES_CLIENT" && Boolean(item.related_entity?.display_name)));
    assert.ok(payload.record.relations.some((item) => item.relation_type === "CLIENT_USES_PRODUCT" && Boolean(item.related_entity?.display_name)));
  });
});

test("isolates tenant-specific meanings", async () => {
  await withServer(async (baseUrl) => {
    const tenantB = headers("agent-user,employee", "department.operations", "tenant-b");
    const payload = await (await fetch(`${baseUrl}/api/v1/glossary/resolve`, {
      method: "POST", headers: tenantB, body: JSON.stringify({ query: "PI" }),
    })).json() as { resolved: boolean; matches: Array<{ term_id: string; canonical_name: string }> };
    assert.equal(payload.resolved, true);
    assert.equal(payload.matches[0]?.term_id, "term.pi");
    assert.equal(payload.matches[0]?.canonical_name, "프로세스 혁신");
  });
});

test("supports immediate-publish glossary CRUD, CAS, change feed and tombstone", async () => {
  await withServer(async (baseUrl) => {
    const admin = headers("agent-user,admin", "department.strategy-planning");
    const createBody = {
      term_id: "term.okr", tenant_id: "tenant-a", canonical_name: "목표 및 핵심 결과", definition: "조직 목표 관리 방식",
      classification: "STRATEGY", status: "ACTIVE", visible_to_roles: ["agent-user", "employee", "manager", "admin"],
      aliases: [{ value: "OKR", organization_unit_id: null, locale: "ko-KR" }],
      bindings: [{ system_id: "strategy", capability_id: "objectives.read", entity_type: "OBJECTIVE", default_operation: "READ", risk_level: "LOW" }],
      source: { reference: "org://tenant-a/strategy/okr", version: "1", approved_by: "strategy-admin" },
    };
    const created = await fetch(`${baseUrl}/api/v1/admin/glossary/terms`, { method: "POST", headers: admin, body: JSON.stringify(createBody) });
    const createPayload = await created.json() as { catalog_revision: number; record: { row_version: number } };
    assert.equal(created.status, 201);
    assert.equal(createPayload.catalog_revision, 501);
    const conflict = await fetch(`${baseUrl}/api/v1/admin/glossary/terms/term.okr`, {
      method: "PUT", headers: { ...admin, "If-Match": "99" }, body: JSON.stringify({ canonical_name: "OKR", definition: "bad", aliases: [], bindings: [] }),
    });
    assert.equal(conflict.status, 409);
    const deleted = await fetch(`${baseUrl}/api/v1/admin/glossary/terms/term.okr`, { method: "DELETE", headers: { ...admin, "If-Match": String(createPayload.record.row_version) } });
    assert.equal(deleted.status, 200);
    const changes = await (await fetch(`${baseUrl}/api/v1/glossary/changes?after=500`, { headers: admin })).json() as { changes: Array<{ change_type: string }> };
    assert.deepEqual(changes.changes.map((item) => item.change_type), ["CREATE", "DELETE"]);
  });
});

test("captures delegated identity without authorization value and supports faults", async () => {
  await withServer(async (baseUrl) => {
    await fetch(`${baseUrl}/api/v1/context/search`, { method: "POST", headers: headers(), body: JSON.stringify({ query: "연차" }) });
    const requests = await (await fetch(`${baseUrl}/_fake/requests`)).json() as { requests: Array<Record<string, unknown>> };
    assert.equal(requests.requests[0]?.authorization_present, true);
    assert.equal(requests.requests[0]?.authorization_value_recorded, false);
    assert.equal(JSON.stringify(requests).includes("example-organization-context-api-token"), false);
    await fetch(`${baseUrl}/_fake/faults`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ operation: "context.resolve", mode: "PERMISSION_DENIED", count: 1 }) });
    const denied = await fetch(`${baseUrl}/api/v1/context/resolve`, { method: "POST", headers: headers(), body: JSON.stringify({ query: "김민수" }) });
    assert.equal(denied.status, 403);
  });
});


test("bounds resolve to top-score detailed candidates and search to compact summaries", async () => {
  await withServer(async (baseUrl) => {
    const exactResponse = await fetch(`${baseUrl}/api/v1/context/resolve`, {
      method: "POST", headers: headers(), body: JSON.stringify({ query: "플랫폼팀 김민수 선임", entity_types: ["EMPLOYEE"], limit: 20 }),
    });
    const exactText = await exactResponse.text();
    const exact = JSON.parse(exactText) as { response_shape: string; candidate_count: number; top_candidate_count: number; returned_count: number; matches: Array<{ entity_id: string; record?: unknown; relations?: unknown[] }> };
    assert.equal(exact.response_shape, "TOP_SCORE_CANDIDATES_WITH_DETAILS");
    assert.ok(exact.candidate_count > exact.returned_count);
    assert.equal(exact.top_candidate_count, 1);
    assert.equal(exact.returned_count, 1);
    assert.equal(exact.matches[0]?.entity_id, "employee-0017");
    assert.ok(exact.matches[0]?.record);
    assert.ok(Array.isArray(exact.matches[0]?.relations));
    assert.ok(exactText.length < 32000);

    const searchResponse = await fetch(`${baseUrl}/api/v1/context/search`, {
      method: "POST", headers: headers(), body: JSON.stringify({ query: "", limit: 100 }),
    });
    const searchText = await searchResponse.text();
    const search = JSON.parse(searchText) as { response_shape: string; returned_count: number; truncated: boolean; matches: Array<{ record?: unknown; relations?: unknown }> };
    assert.equal(search.response_shape, "RANKED_ENTITY_SUMMARIES");
    assert.equal(search.returned_count, 20);
    assert.equal(search.truncated, true);
    assert.equal(search.matches.length, 20);
    assert.equal(search.matches.some((item) => item.record !== undefined || item.relations !== undefined), false);
    assert.ok(searchText.length < 32000);
  });
});
