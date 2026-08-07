export type Role = "agent-user" | "employee" | "manager" | "admin";
export type TermStatus = "ACTIVE" | "RETIRED";
export type EntityStatus = "ACTIVE" | "PLANNED" | "MAINTENANCE" | "PROSPECT" | "SUSPENDED" | "ON_HOLD" | "COMPLETED" | "END_OF_SALE" | "END_OF_SUPPORT" | "RETIRED";
export type ChangeType = "CREATE" | "UPDATE" | "DELETE";
export type EntityType = "TERM" | "DEPARTMENT" | "POSITION" | "EMPLOYEE" | "PRODUCT" | "CLIENT" | "PROJECT" | "SYSTEM" | "CAPABILITY";

export interface TermAlias {
  value: string;
  organization_unit_id: string | null;
  locale: string;
}

export interface TermBinding {
  system_id: string;
  capability_id: string;
  entity_type: string;
  default_operation: "READ" | "WRITE" | "AUTOMATE";
  risk_level: "LOW" | "MEDIUM" | "HIGH";
}

export interface TermSource {
  reference: string;
  version: string;
  approved_by: string;
}

export interface OrganizationTerm {
  term_id: string;
  tenant_id: string;
  canonical_name: string;
  definition: string;
  classification: string;
  status: TermStatus;
  revision: number;
  row_version: number;
  visible_to_roles: Role[];
  aliases: TermAlias[];
  bindings: TermBinding[];
  source: TermSource;
  updated_at: string;
  deleted_at: string | null;
}

export type ReferenceRecord = Record<string, unknown> & {
  tenant_id: string;
  status?: EntityStatus;
  row_version?: number;
};

export interface ReferenceDataset {
  tenant_id: string;
  catalog_revision: number;
  manifest: FixtureManifest;
  departments: ReferenceRecord[];
  positions: ReferenceRecord[];
  employees: ReferenceRecord[];
  products: ReferenceRecord[];
  clients: ReferenceRecord[];
  glossary: OrganizationTerm[];
  projects: ReferenceRecord[];
  systems: ReferenceRecord[];
  capabilities: ReferenceRecord[];
  relations: ReferenceRecord[];
}

export interface FixtureManifest {
  schema_version: "okcanvas-organization-context-reference-fixture-v1";
  tenant_id: string;
  catalog_revision: number;
  fixture_role: string;
  production_sot: "DATABASE";
  example_sot: "COMMITTED_JSON_FIXTURES";
  files: Record<string, string>;
  expected_counts: Record<string, number>;
}

export interface FixtureValidation {
  valid: boolean;
  errors: string[];
  counts: Record<string, number>;
}

export interface CatalogChange {
  change_seq: number;
  change_type: ChangeType;
  entity_type: EntityType | "GLOSSARY_TERM";
  entity_id: string;
  occurred_at: string;
}

export interface CapturedRequest {
  sequence: number;
  method: string;
  path: string;
  tenant_id: string | null;
  principal_id: string | null;
  roles: string[];
  organization_unit_id: string | null;
  delegation_id: string | null;
  request_id: string | null;
  authorization_present: boolean;
  authorization_value_recorded: false;
  body: unknown;
}

export type FaultMode =
  | "NONE"
  | "EXPIRED_TOKEN"
  | "PERMISSION_DENIED"
  | "NOT_FOUND"
  | "VERSION_CONFLICT"
  | "RATE_LIMITED"
  | "INTERNAL_ERROR"
  | "UNAVAILABLE"
  | "TIMEOUT"
  | "MALFORMED_RESPONSE";

export interface FaultRule {
  operation: string;
  mode: FaultMode;
  remaining: number;
}
