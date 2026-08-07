import { loadReferenceDatasets, validateReferenceDatasets } from "./fixture-loader.js";
import type { CapturedRequest, CatalogChange, FaultRule, FixtureValidation, OrganizationTerm, ReferenceDataset } from "./types.js";

export class FakeState {
  clock = { now: "2026-08-05T09:00:00+09:00" };
  datasets = new Map<string, ReferenceDataset>();
  terms: OrganizationTerm[] = [];
  catalog_revision = 0;
  changes: CatalogChange[] = [];
  requests: CapturedRequest[] = [];
  faults: FaultRule[] = [];
  validations: Record<string, FixtureValidation> = {};
  private requestSequence = 0;

  constructor() {
    this.reset();
  }

  reset(): void {
    this.clock = { now: "2026-08-05T09:00:00+09:00" };
    this.datasets = loadReferenceDatasets();
    this.validations = validateReferenceDatasets(this.datasets);
    this.terms = [...this.datasets.values()].flatMap((dataset) => structuredClone(dataset.glossary));
    this.catalog_revision = this.datasets.get("tenant-a")?.catalog_revision ?? 0;
    this.changes = [];
    this.requests = [];
    this.faults = [];
    this.requestSequence = 0;
  }

  dataset(tenantId: string): ReferenceDataset | undefined {
    const dataset = this.datasets.get(tenantId);
    if (!dataset) return undefined;
    if (tenantId === "tenant-a") return { ...dataset, catalog_revision: this.catalog_revision, glossary: this.terms.filter((term) => term.tenant_id === tenantId) };
    return dataset;
  }

  catalogRevision(tenantId: string): number {
    return tenantId === "tenant-a" ? this.catalog_revision : this.datasets.get(tenantId)?.catalog_revision ?? 0;
  }

  replaceSeed(terms: OrganizationTerm[], catalogRevision: number): void {
    const retained = this.terms.filter((term) => term.tenant_id !== "tenant-a");
    this.terms = [...retained, ...structuredClone(terms)];
    this.catalog_revision = catalogRevision;
    this.changes = [];
    this.requests = [];
  }

  capture(input: Omit<CapturedRequest, "sequence">): void {
    this.requestSequence += 1;
    this.requests.push({ sequence: this.requestSequence, ...input });
  }

  setFault(rule: FaultRule): void {
    this.faults = this.faults.filter((item) => item.operation !== rule.operation);
    if (rule.mode !== "NONE" && rule.remaining > 0) this.faults.push(rule);
  }

  consumeFault(operation: string): FaultRule | undefined {
    const rule = this.faults.find((item) => item.operation === operation && item.remaining > 0);
    if (!rule) return undefined;
    rule.remaining -= 1;
    if (rule.remaining === 0) this.faults = this.faults.filter((item) => item !== rule);
    return { ...rule };
  }

  appendChange(changeType: CatalogChange["change_type"], termId: string): number {
    this.catalog_revision += 1;
    this.changes.push({
      change_seq: this.catalog_revision,
      change_type: changeType,
      entity_type: "GLOSSARY_TERM",
      entity_id: termId,
      occurred_at: this.clock.now,
    });
    return this.catalog_revision;
  }
}
