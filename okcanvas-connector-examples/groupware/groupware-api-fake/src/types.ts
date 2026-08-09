export type Role = "agent-user" | "employee" | "manager" | "admin";

export type OrganizationContextEntityType = "EMPLOYEE" | "PROJECT" | "CLIENT" | "PRODUCT" | "DEPARTMENT";

export interface ContextRef {
  entity_type: OrganizationContextEntityType;
  entity_id: string;
}

export interface FakeClock {
  now: string;
}

export interface NoticeRecord {
  record_id: string;
  tenant_id: string;
  context_refs: ContextRef[];
  title: string;
  body: string;
  visible_to_roles: Role[];
}

export interface MailRecord {
  record_id: string;
  tenant_id: string;
  context_refs: ContextRef[];
  owner_principal_id: string;
  subject: string;
  body: string;
}

export interface CalendarRecord {
  record_id: string;
  tenant_id: string;
  context_refs: ContextRef[];
  owner_principal_id: string;
  title: string;
  start_at: string;
  end_at: string;
}

export interface CapturedRequest {
  sequence: number;
  method: string;
  path: string;
  tenant_id: string | null;
  principal_id: string | null;
  roles: string[];
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
  | "MALFORMED_RESPONSE"
  | "PARTIAL_RESPONSE";

export interface FaultRule {
  operation: string;
  mode: FaultMode;
  remaining: number;
}
