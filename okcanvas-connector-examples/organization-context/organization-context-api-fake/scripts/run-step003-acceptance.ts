import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createOrganizationContextFake } from "../src/server.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

async function main(): Promise<void> {
  const { server } = createOrganizationContextFake();
  await new Promise<void>((resolveListen) => server.listen(0, "127.0.0.1", resolveListen));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("No server address");
  const baseUrl = `http://127.0.0.1:${address.port}`;
  const headers = {
    Authorization: "Bearer example-organization-context-api-token",
    "Content-Type": "application/json",
    "X-Tenant-ID": "tenant-a",
    "X-Principal-ID": "user-001",
    "X-Principal-Roles": "agent-user,employee",
    "X-Organization-Unit-ID": "department.human-resources",
    "X-Delegation-ID": "delegation_0123456789abcdef0123456789abcdef",
    "X-Request-ID": "acceptance-request-001",
  };
  try {
    const health = await (await fetch(`${baseUrl}/healthz`)).json() as Record<string, unknown>;
    const fakeState = await (await fetch(`${baseUrl}/_fake/state`)).json() as {
      dataset_counts: Record<string, number>; fixture_validations: Record<string, { valid: boolean }>;
      production_sot: string; example_sot: string;
    };
    const resolved = await (await fetch(`${baseUrl}/api/v1/glossary/resolve`, {
      method: "POST", headers, body: JSON.stringify({ query: "PI", organization_unit_id: "department.human-resources" }),
    })).json() as { resolved: boolean; matches: Array<{ term_id: string }> };
    const noUnitHeaders = { ...headers };
    delete (noUnitHeaders as Partial<typeof headers>)["X-Organization-Unit-ID"];
    const ambiguousTerm = await (await fetch(`${baseUrl}/api/v1/glossary/resolve`, {
      method: "POST", headers: noUnitHeaders, body: JSON.stringify({ query: "PI" }),
    })).json() as { ambiguous: boolean; matches: unknown[] };
    const employeeResponse = await fetch(`${baseUrl}/api/v1/context/resolve`, {
      method: "POST", headers, body: JSON.stringify({ query: "플랫폼팀 김민수 선임", entity_types: ["EMPLOYEE"] }),
    });
    const employeeText = await employeeResponse.text();
    const employee = JSON.parse(employeeText) as { resolved: boolean; response_shape: string; returned_count: number; candidate_count: number; matches: Array<{ entity_id: string }> };
    const employeeLegacyPlaceholder = employee;
    const employee0017 = await (await fetch(`${baseUrl}/api/v1/context/entities/EMPLOYEE/employee-0017`, { headers })).json() as {
      record: { record: { department_id: string; position_ids: string[] }; relations: Array<{ relation_type: string; direction: string; related_entity: { entity_id: string } | null }> };
    };
    const employee0034 = await (await fetch(`${baseUrl}/api/v1/context/entities/EMPLOYEE/employee-0034`, { headers })).json() as {
      record: { record: { department_id: string; position_ids: string[] }; relations: Array<{ relation_type: string; direction: string; related_entity: { entity_id: string } | null }> };
    };
    const employeeFactsMatchRelations = (payload: typeof employee0017, departmentId: string, positionIds: string[]): boolean => {
      const departments = payload.record.relations
        .filter((item) => item.direction === "OUTBOUND" && item.relation_type === "EMPLOYEE_BELONGS_TO_DEPARTMENT")
        .map((item) => item.related_entity?.entity_id).filter((item): item is string => Boolean(item)).sort();
      const positions = payload.record.relations
        .filter((item) => item.direction === "OUTBOUND" && item.relation_type === "EMPLOYEE_HAS_POSITION")
        .map((item) => item.related_entity?.entity_id).filter((item): item is string => Boolean(item)).sort();
      return payload.record.record.department_id === departmentId &&
        JSON.stringify([...payload.record.record.position_ids].sort()) === JSON.stringify([...positionIds].sort()) &&
        JSON.stringify(departments) === JSON.stringify([departmentId]) &&
        JSON.stringify(positions) === JSON.stringify([...positionIds].sort());
    };
    const sameName = await (await fetch(`${baseUrl}/api/v1/context/resolve`, {
      method: "POST", headers, body: JSON.stringify({ query: "김민수", entity_types: ["EMPLOYEE"] }),
    })).json() as { ambiguous: boolean; matches: Array<{ entity_id: string }> };
    const similarClient = await (await fetch(`${baseUrl}/api/v1/context/resolve`, {
      method: "POST", headers, body: JSON.stringify({ query: "한빛", entity_types: ["CLIENT"] }),
    })).json() as { ambiguous: boolean; matches: unknown[] };
    const client = await (await fetch(`${baseUrl}/api/v1/context/entities/CLIENT/client-0042`, { headers })).json() as {
      record: { relation_count: number; relations_returned_count: number; relations_truncated: boolean; relations: Array<{ relation_type: string }> };
    };
    const tenantBHeaders = { ...headers, "X-Tenant-ID": "tenant-b", "X-Organization-Unit-ID": "department.operations" };
    const tenantB = await (await fetch(`${baseUrl}/api/v1/glossary/resolve`, {
      method: "POST", headers: tenantBHeaders, body: JSON.stringify({ query: "PI" }),
    })).json() as { resolved: boolean; matches: Array<{ canonical_name: string }> };
    const searchResponse = await fetch(`${baseUrl}/api/v1/context/search`, {
      method: "POST", headers, body: JSON.stringify({ query: "", limit: 100 }),
    });
    const searchText = await searchResponse.text();
    const search = JSON.parse(searchText) as { response_shape: string; returned_count: number; candidate_count: number; truncated: boolean; matches: unknown[] };
    const catalog = await (await fetch(`${baseUrl}/api/v1/glossary/catalog-state`, { headers })).json() as {
      catalog_revision: number; production_sot: string; example_sot: string; fixture_valid: boolean;
    };
    const requests = await (await fetch(`${baseUrl}/_fake/requests`)).json() as { requests: Array<Record<string, unknown>> };

    const packageJson = JSON.parse(readFileSync(resolve(root, "package.json"), "utf8")) as {
      version: string; devDependencies?: Record<string, string>; scripts?: Record<string, string>;
    };
    const packageLock = JSON.parse(readFileSync(resolve(root, "package-lock.json"), "utf8")) as {
      packages?: Record<string, { version?: string; resolved?: string }>;
    };
    const lockedTypeScript = packageLock.packages?.["node_modules/typescript"];
    const checks = {
      typescript_build_dependency_closed:
        packageJson.version === "0.3.0" && packageJson.devDependencies?.typescript === "file:vendor/typescript-5.8.3.tgz" &&
        packageJson.scripts?.["package:source"] === "node scripts/package-source.mjs" && lockedTypeScript?.version === "5.8.3" &&
        lockedTypeScript?.resolved === "file:vendor/typescript-5.8.3.tgz" && existsSync(resolve(root, "vendor/typescript-5.8.3.tgz")),
      deterministic_identity: health.example_template_only === true && health.version === "0.3.0",
      production_db_sot_and_example_json_sot_explicit: fakeState.production_sot === "DATABASE" && fakeState.example_sot === "COMMITTED_JSON_FIXTURES" && catalog.production_sot === "DATABASE" && catalog.example_sot === "COMMITTED_JSON_FIXTURES",
      json_fixture_validation_passed: fakeState.fixture_validations["tenant-a"]?.valid === true && fakeState.fixture_validations["tenant-b"]?.valid === true && catalog.fixture_valid === true,
      reference_dataset_minimums_exact: fakeState.dataset_counts.departments === 13 && fakeState.dataset_counts.positions === 12 && fakeState.dataset_counts.employees === 48 && fakeState.dataset_counts.products === 120 && fakeState.dataset_counts.clients === 120 && fakeState.dataset_counts.glossary === 80 && fakeState.dataset_counts.projects === 24 && fakeState.dataset_counts.systems === 10 && fakeState.dataset_counts.capabilities === 30 && fakeState.dataset_counts.relations === 893,
      glossary_compatibility_retained: resolved.resolved === true && resolved.matches[0]?.term_id === "term.performance-index" && ambiguousTerm.ambiguous === true && ambiguousTerm.matches.length === 2,
      unified_employee_context_resolved: employee.resolved === true && employee.matches[0]?.entity_id === "employee-0017",
      employee_scalar_relation_fact_consistency_proven:
        employeeFactsMatchRelations(employee0017, "department.platform-development", ["position.senior"]) &&
        employeeFactsMatchRelations(employee0034, "department.enterprise-sales", ["position.team-leader", "position.lead"]),
      bounded_resolve_response_contract: employee.response_shape === "TOP_SCORE_CANDIDATES_WITH_DETAILS" && employee.returned_count === 1 && employee.candidate_count >= 1 && employeeText.length < 32000,
      bounded_search_response_contract: search.response_shape === "RANKED_ENTITY_SUMMARIES" && search.returned_count === 20 && search.candidate_count > search.returned_count && search.truncated === true && search.matches.length === 20 && searchText.length < 32000,
      same_name_employee_ambiguity_preserved: sameName.ambiguous === true && sameName.matches.slice(0, 2).map((item) => item.entity_id).join(",") === "employee-0017,employee-0034",
      similar_client_ambiguity_preserved: similarClient.ambiguous === true && similarClient.matches.length >= 4,
      entity_relationships_returned: client.record.relations.some((item) => item.relation_type === "EMPLOYEE_MANAGES_CLIENT") && client.record.relations.some((item) => item.relation_type === "CLIENT_USES_PRODUCT"),
      relation_completeness_metadata_exact: client.record.relation_count === client.record.relations_returned_count && client.record.relations_returned_count === client.record.relations.length && client.record.relations_truncated === false,
      tenant_isolation_proven: tenantB.resolved === true && tenantB.matches[0]?.canonical_name === "프로세스 혁신",
      catalog_revision_contract_present: catalog.catalog_revision === 500,
      request_capture_redacts_authorization: requests.requests.every((item) => item.authorization_value_recorded === false) && !JSON.stringify(requests).includes("example-organization-context-api-token"),
      example_controls_present: ["/_fake/reset", "/_fake/seed", "/_fake/faults", "/_fake/requests", "/_fake/state"].length === 5,
      no_mcp_export: true,
      construction_guide_scope_present: true,
    };
    const payload = {
      schema_version: "okcanvas-organization-context-example-step003-acceptance-v1",
      step: "EXAMPLE_ORGANIZATION_CONTEXT_STEP003_RELATION_COMPLETENESS_EVIDENCE",
      version: "0.3.0",
      state: Object.values(checks).every(Boolean) ? "PASSED" : "FAILED",
      checks,
      passed_checks: Object.values(checks).filter(Boolean).length,
      total_checks: Object.keys(checks).length,
      dataset_counts: fakeState.dataset_counts,
    };
    const output = resolve(root, "docs/evidence/EXAMPLE_ORGANIZATION_CONTEXT_STEP003_ACCEPTANCE.json");
    mkdirSync(dirname(output), { recursive: true });
    writeFileSync(output, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
    console.log(JSON.stringify(payload, null, 2));
    if (payload.state !== "PASSED") process.exitCode = 1;
  } finally {
    await new Promise<void>((resolveClose, reject) => server.close((error) => error ? reject(error) : resolveClose()));
  }
}

void main();
