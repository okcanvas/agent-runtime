import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { FixtureManifest, FixtureValidation, OrganizationTerm, ReferenceDataset, ReferenceRecord } from "./types.js";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../fixtures");
const TENANTS = ["tenant-a", "tenant-b"] as const;
const COLLECTIONS = ["departments", "positions", "employees", "products", "clients", "glossary", "projects", "systems", "capabilities", "relations"] as const;

type CollectionName = typeof COLLECTIONS[number];

function readJson(path: string): unknown {
  return JSON.parse(readFileSync(path, "utf8"));
}

function asRecords(value: unknown, name: string): ReferenceRecord[] {
  if (!Array.isArray(value) || value.some((item) => !item || typeof item !== "object" || Array.isArray(item))) {
    throw new Error(`Fixture collection ${name} must be a JSON array of objects`);
  }
  return value as ReferenceRecord[];
}

function idField(name: CollectionName): string | null {
  return {
    departments: "department_id", positions: "position_id", employees: "employee_id",
    products: "product_id", clients: "client_id", glossary: "term_id", projects: "project_id",
    systems: "system_id", capabilities: "capability_id", relations: "relation_id",
  }[name];
}

function value(record: ReferenceRecord, key: string): string | null {
  return typeof record[key] === "string" ? record[key] as string : null;
}

function validate(dataset: ReferenceDataset): FixtureValidation {
  const errors: string[] = [];
  const counts: Record<string, number> = {};
  const allIds = new Map<string, Set<string>>();
  for (const name of COLLECTIONS) {
    const records = dataset[name] as ReferenceRecord[];
    counts[name] = records.length;
    const expected = dataset.manifest.expected_counts[name];
    if (typeof expected === "number" && records.length !== expected) errors.push(`${name}: expected ${expected}, got ${records.length}`);
    if (name === "relations") {
      const minimum = dataset.manifest.expected_counts.relations_minimum ?? 0;
      if (records.length < minimum) errors.push(`relations: expected at least ${minimum}, got ${records.length}`);
    }
    const field = idField(name);
    const ids = new Set<string>();
    for (const record of records) {
      if (record.tenant_id !== dataset.tenant_id) errors.push(`${name}: cross-tenant record detected`);
      if (field) {
        const id = value(record, field);
        if (!id) errors.push(`${name}: missing ${field}`);
        else if (ids.has(id)) errors.push(`${name}: duplicate ${id}`);
        else ids.add(id);
      }
    }
    allIds.set(name, ids);
  }
  const has = (collection: CollectionName, id: unknown): boolean => typeof id === "string" && (allIds.get(collection)?.has(id) ?? false);
  for (const employee of dataset.employees) {
    if (!has("departments", employee.department_id)) errors.push(`employee ${employee.employee_id as string}: department missing`);
    if (!Array.isArray(employee.position_ids) || employee.position_ids.some((id) => !has("positions", id))) errors.push(`employee ${employee.employee_id as string}: position missing`);
    if (employee.manager_employee_id !== null && !has("employees", employee.manager_employee_id)) errors.push(`employee ${employee.employee_id as string}: manager missing`);
  }
  for (const product of dataset.products) {
    if (!has("departments", product.owning_department_id)) errors.push(`product ${product.product_id as string}: department missing`);
    if (!has("employees", product.product_manager_employee_id)) errors.push(`product ${product.product_id as string}: manager missing`);
  }
  for (const client of dataset.clients) {
    if (!has("departments", client.owning_department_id)) errors.push(`client ${client.client_id as string}: department missing`);
    if (!has("employees", client.account_manager_employee_id)) errors.push(`client ${client.client_id as string}: manager missing`);
    if (client.parent_client_id !== null && !has("clients", client.parent_client_id)) errors.push(`client ${client.client_id as string}: parent missing`);
  }
  for (const project of dataset.projects) {
    if (!has("departments", project.owning_department_id)) errors.push(`project ${project.project_id as string}: department missing`);
    if (!has("employees", project.project_manager_employee_id)) errors.push(`project ${project.project_id as string}: manager missing`);
    if (!has("clients", project.client_id)) errors.push(`project ${project.project_id as string}: client missing`);
  }
  for (const capability of dataset.capabilities) {
    if (!has("systems", capability.system_id)) errors.push(`capability ${capability.capability_id as string}: system missing`);
  }
  const typeToCollection: Record<string, CollectionName> = {
    TERM: "glossary", DEPARTMENT: "departments", POSITION: "positions", EMPLOYEE: "employees",
    PRODUCT: "products", CLIENT: "clients", PROJECT: "projects", SYSTEM: "systems", CAPABILITY: "capabilities",
  };
  for (const relation of dataset.relations) {
    const from = typeToCollection[String(relation.from_entity_type)];
    const to = typeToCollection[String(relation.to_entity_type)];
    if (!from || !has(from, relation.from_entity_id)) errors.push(`relation ${relation.relation_id as string}: from entity missing`);
    if (!to || !has(to, relation.to_entity_id)) errors.push(`relation ${relation.relation_id as string}: to entity missing`);
  }
  if (dataset.relations.length > 0) {
    const targets = new Map<string, string[]>();
    for (const relation of dataset.relations) {
      const key = `${String(relation.relation_type)}\u0000${String(relation.from_entity_id)}`;
      const target = value(relation, "to_entity_id");
      if (target) targets.set(key, [...(targets.get(key) ?? []), target]);
    }
    const relationTargets = (relationType: string, fromEntityId: string): string[] =>
      [...(targets.get(`${relationType}\u0000${fromEntityId}`) ?? [])].sort();
    const exact = (actual: string[], expected: string[]): boolean =>
      actual.length === expected.length && actual.every((item, index) => item === expected[index]);
    for (const employee of dataset.employees) {
      const employeeId = value(employee, "employee_id");
      const departmentId = value(employee, "department_id");
      if (!employeeId || !departmentId) continue;
      const actualDepartments = relationTargets("EMPLOYEE_BELONGS_TO_DEPARTMENT", employeeId);
      if (!exact(actualDepartments, [departmentId])) {
        errors.push(`employee ${employeeId}: department scalar/relation mismatch`);
      }
      const expectedPositions = Array.isArray(employee.position_ids)
        ? employee.position_ids.filter((item): item is string => typeof item === "string").sort()
        : [];
      const actualPositions = relationTargets("EMPLOYEE_HAS_POSITION", employeeId);
      if (!exact(actualPositions, expectedPositions)) {
        errors.push(`employee ${employeeId}: position scalar/relation mismatch`);
      }
      const managerId = value(employee, "manager_employee_id");
      const expectedManagers = managerId ? [managerId] : [];
      const actualManagers = relationTargets("EMPLOYEE_REPORTS_TO_EMPLOYEE", employeeId);
      if (!exact(actualManagers, expectedManagers)) {
        errors.push(`employee ${employeeId}: manager scalar/relation mismatch`);
      }
    }
  }
  return { valid: errors.length === 0, errors, counts };
}

export function loadReferenceDatasets(): Map<string, ReferenceDataset> {
  const datasets = new Map<string, ReferenceDataset>();
  for (const tenant of TENANTS) {
    const tenantRoot = resolve(root, tenant);
    const manifest = readJson(resolve(tenantRoot, "manifest.json")) as FixtureManifest;
    if (manifest.schema_version !== "okcanvas-organization-context-reference-fixture-v1" || manifest.tenant_id !== tenant) {
      throw new Error(`Invalid fixture manifest for ${tenant}`);
    }
    if (manifest.production_sot !== "DATABASE" || manifest.example_sot !== "COMMITTED_JSON_FIXTURES") {
      throw new Error(`Invalid SOT declaration for ${tenant}`);
    }
    const loaded: Record<string, ReferenceRecord[]> = {};
    for (const name of COLLECTIONS) {
      const file = manifest.files[name];
      if (!file) throw new Error(`Missing fixture file declaration: ${tenant}/${name}`);
      loaded[name] = asRecords(readJson(resolve(tenantRoot, file)), `${tenant}/${name}`);
    }
    const dataset: ReferenceDataset = {
      tenant_id: tenant,
      catalog_revision: manifest.catalog_revision,
      manifest,
      departments: loaded.departments ?? [], positions: loaded.positions ?? [], employees: loaded.employees ?? [],
      products: loaded.products ?? [], clients: loaded.clients ?? [], glossary: (loaded.glossary ?? []) as unknown as OrganizationTerm[],
      projects: loaded.projects ?? [], systems: loaded.systems ?? [], capabilities: loaded.capabilities ?? [], relations: loaded.relations ?? [],
    };
    const result = validate(dataset);
    if (!result.valid) throw new Error(`Fixture validation failed for ${tenant}: ${result.errors.join("; ")}`);
    datasets.set(tenant, dataset);
  }
  return datasets;
}

export function validateReferenceDatasets(datasets: Map<string, ReferenceDataset>): Record<string, FixtureValidation> {
  return Object.fromEntries([...datasets.entries()].map(([tenant, dataset]) => [tenant, validate(dataset)]));
}
