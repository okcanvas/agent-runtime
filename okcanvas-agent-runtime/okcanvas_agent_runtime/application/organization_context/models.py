from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OrganizationCatalogState(StrEnum):
    EMPTY = "EMPTY"
    READY = "READY"


@dataclass(frozen=True)
class OrganizationAccessContext:
    tenant_id: str | None = None
    principal_id: str | None = None
    roles: tuple[str, ...] = ()


@dataclass(frozen=True)
class OrganizationContextRecord:
    kind: str
    record_id: str
    label: str
    aliases: tuple[str, ...]
    summary: str
    source_title: str
    source_version: str
    source_reference: str
    tenant_id: str | None
    allowed_principal_ids: tuple[str, ...]
    allowed_roles: tuple[str, ...]
    valid_from: str | None
    valid_until: str | None
    classification: str
    searchable_text: str


@dataclass(frozen=True)
class OrganizationContextMatch:
    kind: str
    record_id: str
    label: str
    summary: str
    source_title: str
    source_version: str
    source_reference: str
    classification: str
    match_type: str
    score: int

    def to_public_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "record_id": self.record_id,
            "label": self.label,
            "summary": self.summary,
            "source_title": self.source_title,
            "source_version": self.source_version,
            "source_reference": self.source_reference,
            "classification": self.classification,
            "match_type": self.match_type,
            "score": self.score,
        }


@dataclass(frozen=True)
class OrganizationContextSearchResult:
    catalog_id: str
    catalog_version: str
    effective_at: str
    catalog_state: OrganizationCatalogState
    query_kind: str
    query_sha256: str
    matches: tuple[OrganizationContextMatch, ...]
    filtered_count: int
    ambiguous: bool

    @property
    def authoritative_match_found(self) -> bool:
        return bool(self.matches) and not self.ambiguous

    def to_public_dict(self) -> dict[str, object]:
        return {
            "schema_version": "okcanvas-organization-context-query-v1",
            "catalog_id": self.catalog_id,
            "catalog_version": self.catalog_version,
            "effective_at": self.effective_at,
            "catalog_state": self.catalog_state.value,
            "query_kind": self.query_kind,
            "query_sha256": self.query_sha256,
            "authoritative_match_found": self.authoritative_match_found,
            "ambiguous": self.ambiguous,
            "filtered_count": self.filtered_count,
            "matches": [item.to_public_dict() for item in self.matches],
        }

    def to_grounding_dict(self) -> dict[str, object]:
        return {
            "schema_version": "okcanvas-organization-grounding-context-v1",
            "catalog_id": self.catalog_id,
            "catalog_version": self.catalog_version,
            "effective_at": self.effective_at,
            "query_kind": self.query_kind,
            "query_sha256": self.query_sha256,
            "matches": [item.to_public_dict() for item in self.matches],
        }
