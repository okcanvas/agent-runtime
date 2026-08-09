import type { EntityType, ReferenceDataset, ReferenceRecord } from "./types.js";

const ENTITY_COLLECTIONS: Array<{ type: EntityType; collection: keyof ReferenceDataset; id: string; names: string[] }> = [
  { type: "TERM", collection: "glossary", id: "term_id", names: ["canonical_name"] },
  { type: "DEPARTMENT", collection: "departments", id: "department_id", names: ["name", "department_code"] },
  { type: "POSITION", collection: "positions", id: "position_id", names: ["name"] },
  { type: "EMPLOYEE", collection: "employees", id: "employee_id", names: ["name", "employee_number", "email"] },
  { type: "PRODUCT", collection: "products", id: "product_id", names: ["name", "product_code"] },
  { type: "CLIENT", collection: "clients", id: "client_id", names: ["display_name", "legal_name", "client_code"] },
  { type: "PROJECT", collection: "projects", id: "project_id", names: ["name", "project_code"] },
  { type: "SYSTEM", collection: "systems", id: "system_id", names: ["name"] },
  { type: "CAPABILITY", collection: "capabilities", id: "capability_id", names: ["name"] },
];

function normalize(value: string): string {
  return value.trim().toLocaleLowerCase("ko-KR").replace(/[㈜()\[\],.]/g, " ").replace(/\s+/g, " ");
}

function strings(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => typeof item === "string" ? [item] : item && typeof item === "object" && typeof (item as Record<string, unknown>).value === "string" ? [(item as Record<string, unknown>).value as string] : []);
}

function id(record: ReferenceRecord, field: string): string {
  return String(record[field] ?? "");
}

function departmentEvidence(dataset: ReferenceDataset, record: ReferenceRecord, query: string): { matched: boolean; id: string | null; name: string | null } {
  const departmentId = typeof record.department_id === "string" ? record.department_id : typeof record.owning_department_id === "string" ? record.owning_department_id : null;
  if (!departmentId) return { matched: false, id: null, name: null };
  const department = dataset.departments.find((item) => item.department_id === departmentId);
  if (!department) return { matched: false, id: departmentId, name: null };
  const values = [String(department.name ?? ""), ...strings(department.aliases)];
  return { matched: values.some((value) => normalize(query).includes(normalize(value))), id: departmentId, name: String(department.name ?? "") };
}

function positionEvidence(dataset: ReferenceDataset, record: ReferenceRecord, query: string): string[] {
  if (!Array.isArray(record.position_ids)) return [];
  const matches: string[] = [];
  for (const positionId of record.position_ids) {
    const position = dataset.positions.find((item) => item.position_id === positionId);
    if (!position) continue;
    const values = [String(position.name ?? ""), ...strings(position.aliases)];
    if (values.some((value) => normalize(query).includes(normalize(value)))) matches.push(String(position.name ?? ""));
  }
  return matches;
}

function entitySummary(dataset: ReferenceDataset, entityType: EntityType, entityId: string): Record<string, unknown> | null {
  const spec = ENTITY_COLLECTIONS.find((item) => item.type === entityType);
  if (!spec) return null;
  const collection = dataset[spec.collection];
  if (!Array.isArray(collection)) return null;
  const record = (collection as ReferenceRecord[]).find((item) => id(item, spec.id) === entityId);
  if (!record) return null;
  return {
    entity_type: entityType,
    entity_id: entityId,
    display_name: String(record.canonical_name ?? record.name ?? record.display_name ?? record.legal_name ?? record.capability_id ?? record.system_id ?? entityId),
    status: record.status ?? "ACTIVE",
  };
}

function related(dataset: ReferenceDataset, entityType: EntityType, entityId: string): Array<Record<string, unknown>> {
  const relations = dataset.relations.filter((item) =>
    (item.from_entity_type === entityType && item.from_entity_id === entityId) ||
    (item.to_entity_type === entityType && item.to_entity_id === entityId));
  return relations.map((item) => {
    const outbound = item.from_entity_type === entityType && item.from_entity_id === entityId;
    const relatedType = String(outbound ? item.to_entity_type : item.from_entity_type) as EntityType;
    const relatedId = String(outbound ? item.to_entity_id : item.from_entity_id);
    return {
      relation_type: item.relation_type,
      direction: outbound ? "OUTBOUND" : "INBOUND",
      related_entity: entitySummary(dataset, relatedType, relatedId),
    };
  });
}

function publicRecord(dataset: ReferenceDataset, type: EntityType, record: ReferenceRecord, idField: string, matchedBy: string[], score: number, includeDetails = true): Record<string, unknown> {
  const entityId = id(record, idField);
  const displayName = String(record.canonical_name ?? record.name ?? record.display_name ?? record.legal_name ?? record.capability_id ?? record.system_id ?? entityId);
  const department = departmentEvidence(dataset, record, "");
  const allRelations = includeDetails ? related(dataset, type, entityId) : [];
  const boundedRelations = allRelations.slice(0, 100);
  return {
    entity_type: type,
    entity_id: entityId,
    display_name: displayName,
    matched_by: matchedBy,
    score,
    status: record.status ?? "ACTIVE",
    row_version: record.row_version ?? 1,
    context: {
      department_id: department.id,
      department_name: department.name,
      positions: type === "EMPLOYEE" && Array.isArray(record.position_ids)
        ? record.position_ids.map((positionId) => dataset.positions.find((item) => item.position_id === positionId)?.name).filter(Boolean)
        : [],
    },
    ...(includeDetails ? { record } : {}),
    provenance: {
      source: `fixtures/${dataset.tenant_id}/${String(ENTITY_COLLECTIONS.find((item) => item.type === type)?.collection)}.json`,
      catalog_revision: dataset.catalog_revision,
      row_version: record.row_version ?? 1,
    },
    ...(includeDetails ? {
      relations: boundedRelations,
      relation_count: allRelations.length,
      relations_returned_count: boundedRelations.length,
      relations_truncated: allRelations.length > boundedRelations.length,
    } : {}),
  };
}

type RankedCandidate = { type: EntityType; record: ReferenceRecord; idField: string; score: number; matchedBy: string[] };

function rankCandidates(dataset: ReferenceDataset, query: string, entityTypes?: EntityType[], organizationUnitId: string | null = null): RankedCandidate[] {
  const normalized = normalize(query);
  const candidates: Array<{ type: EntityType; record: ReferenceRecord; idField: string; score: number; matchedBy: string[] }> = [];
  for (const spec of ENTITY_COLLECTIONS) {
    if (entityTypes && entityTypes.length > 0 && !entityTypes.includes(spec.type)) continue;
    const collection = dataset[spec.collection];
    if (!Array.isArray(collection)) continue;
    for (const record of collection as ReferenceRecord[]) {
      if (record.status === "RETIRED") continue;
      const matchedBy: string[] = [];
      let score = 99;
      const recordId = id(record, spec.id);
      if (normalize(recordId) === normalized) { score = 0; matchedBy.push("EXACT_ID"); }
      for (const field of spec.names) {
        const fieldValue = typeof record[field] === "string" ? record[field] as string : "";
        if (!fieldValue) continue;
        if (normalize(fieldValue) === normalized) { score = Math.min(score, 0); matchedBy.push(field.includes("code") || field.includes("number") ? "EXACT_CODE" : "EXACT_NAME"); }
        else if (normalized.includes(normalize(fieldValue))) { score = Math.min(score, 2); matchedBy.push(field.includes("code") ? "CODE_CONTEXT" : "NAME_CONTEXT"); }
        else if (normalize(fieldValue).includes(normalized)) { score = Math.min(score, 4); matchedBy.push("PARTIAL_NAME"); }
      }
      for (const alias of strings(record.aliases)) {
        if (normalize(alias) === normalized) { score = Math.min(score, 1); matchedBy.push("EXACT_ALIAS"); }
        else if (normalized.includes(normalize(alias))) { score = Math.min(score, 3); matchedBy.push("ALIAS_CONTEXT"); }
      }
      if (spec.type === "TERM" && typeof record.definition === "string" && normalize(record.definition).includes(normalized)) { score = Math.min(score, 6); matchedBy.push("DEFINITION"); }
      const department = departmentEvidence(dataset, record, query);
      if (department.matched) { score -= 2; matchedBy.push("DEPARTMENT_CONTEXT"); }
      if (organizationUnitId && department.id === organizationUnitId) { score -= 2; matchedBy.push("ORGANIZATION_UNIT_SCOPE"); }
      const positions = positionEvidence(dataset, record, query);
      if (positions.length > 0) { score -= 2; matchedBy.push("POSITION_CONTEXT"); }
      if (score < 99) candidates.push({ type: spec.type, record, idField: spec.id, score: Math.max(0, score), matchedBy: [...new Set(matchedBy)] });
    }
  }
  candidates.sort((a, b) => a.score - b.score || a.type.localeCompare(b.type) || id(a.record, a.idField).localeCompare(id(b.record, b.idField)));
  return candidates;
}

export function resolveContext(dataset: ReferenceDataset, query: string, entityTypes?: EntityType[], limit = 20, organizationUnitId: string | null = null): Record<string, unknown> {
  const candidates = rankCandidates(dataset, query, entityTypes, organizationUnitId);
  const topScore = candidates[0]?.score;
  const top = topScore === undefined ? [] : candidates.filter((item) => item.score === topScore);
  const boundedLimit = Math.max(1, Math.min(limit, 20));
  const selected = top.slice(0, boundedLimit);
  return {
    schema_version: "okcanvas-organization-context-unified-resolve-v1",
    catalog_revision: dataset.catalog_revision,
    query,
    resolved: top.length === 1,
    ambiguous: top.length > 1,
    reason: top.length > 1 ? `MULTIPLE_${top[0]?.type ?? "ENTITY"}_CANDIDATES` : top.length === 0 ? "NO_MATCH" : null,
    required_disambiguators: top.length > 1 ? ["entity_type", "department", "stable_id_or_code"] : [],
    response_shape: "TOP_SCORE_CANDIDATES_WITH_DETAILS",
    candidate_count: candidates.length,
    top_candidate_count: top.length,
    returned_count: selected.length,
    truncated: top.length > selected.length,
    matches: selected.map((item) => publicRecord(dataset, item.type, item.record, item.idField, item.matchedBy, item.score, true)),
  };
}

export function searchContext(dataset: ReferenceDataset, query: string, entityTypes?: EntityType[], limit = 20, organizationUnitId: string | null = null): Record<string, unknown> {
  const candidates = rankCandidates(dataset, query, entityTypes, organizationUnitId);
  const boundedLimit = Math.max(1, Math.min(limit, 20));
  const selected = candidates.slice(0, boundedLimit);
  return {
    schema_version: "okcanvas-organization-context-unified-search-v1",
    catalog_revision: dataset.catalog_revision,
    query,
    resolved: null,
    ambiguous: null,
    response_shape: "RANKED_ENTITY_SUMMARIES",
    candidate_count: candidates.length,
    returned_count: selected.length,
    truncated: candidates.length > selected.length,
    matches: selected.map((item) => publicRecord(dataset, item.type, item.record, item.idField, item.matchedBy, item.score, false)),
  };
}

export function getEntity(dataset: ReferenceDataset, entityType: EntityType, entityId: string): Record<string, unknown> | null {
  const spec = ENTITY_COLLECTIONS.find((item) => item.type === entityType);
  if (!spec) return null;
  const collection = dataset[spec.collection];
  if (!Array.isArray(collection)) return null;
  const record = (collection as ReferenceRecord[]).find((item) => id(item, spec.id) === entityId);
  return record ? publicRecord(dataset, entityType, record, spec.id, ["EXACT_ID"], 0) : null;
}
