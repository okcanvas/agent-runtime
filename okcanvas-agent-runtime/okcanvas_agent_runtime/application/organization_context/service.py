from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .catalog import OrganizationContextCatalog
from .models import (
    OrganizationAccessContext,
    OrganizationContextMatch,
    OrganizationContextRecord,
    OrganizationContextSearchResult,
)


_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣_.-]+")


def _normalize(value: str) -> str:
    return " ".join(value.casefold().strip().split())


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(token.casefold() for token in _TOKEN_RE.findall(value) if len(token) >= 2))[:20]


class OrganizationContextService:
    def __init__(self, project_root: str | Path, catalog_root: str | Path | None = None) -> None:
        self.catalog = OrganizationContextCatalog(project_root, catalog_root)

    def glossary(self, query: str, access: OrganizationAccessContext, limit: int = 10) -> OrganizationContextSearchResult:
        return self._search("GLOSSARY", query, access, limit, self.catalog.glossary_records)

    def knowledge(self, query: str, access: OrganizationAccessContext, limit: int = 10) -> OrganizationContextSearchResult:
        return self._search("KNOWLEDGE", query, access, limit, self.catalog.knowledge_records)

    def directory(self, query: str, access: OrganizationAccessContext, limit: int = 10) -> OrganizationContextSearchResult:
        return self._search("DIRECTORY", query, access, limit, self.catalog.directory_records)

    def combined(self, query: str, access: OrganizationAccessContext, limit: int = 8) -> OrganizationContextSearchResult:
        records = self.catalog.glossary_records + self.catalog.knowledge_records + self.catalog.directory_records
        return self._search("COMBINED", query, access, limit, records)

    def _search(self, query_kind: str, query: str, access: OrganizationAccessContext, limit: int, records: tuple[OrganizationContextRecord, ...]) -> OrganizationContextSearchResult:
        normalized = _normalize(query)
        if not normalized or "\x00" in normalized or len(normalized) > 100_000:
            raise ValueError("Organization context query must be bounded, non-empty, and NUL-free")
        if not isinstance(limit, int) or not 1 <= limit <= 20:
            raise ValueError("Organization context result limit must be between 1 and 20")
        query_tokens = _tokens(normalized)
        scored: list[tuple[int, str, OrganizationContextRecord]] = []
        filtered = 0
        effective_date = self.catalog.effective_at[:10]
        for record in records:
            if not self._visible(record, access, effective_date):
                filtered += 1
                continue
            score, match_type = self._score(record, normalized, query_tokens)
            if score > 0:
                scored.append((score, match_type, record))
        scored.sort(key=lambda item: (-item[0], item[2].kind, item[2].label.casefold(), item[2].record_id))
        selected = scored[:limit]
        matches = tuple(
            OrganizationContextMatch(
                kind=record.kind,
                record_id=record.record_id,
                label=record.label,
                summary=record.summary,
                source_title=record.source_title,
                source_version=record.source_version,
                source_reference=record.source_reference,
                classification=record.classification,
                match_type=match_type,
                score=score,
            )
            for score, match_type, record in selected
        )
        ambiguous = len(matches) > 1 and matches[0].score >= 90 and matches[0].score == matches[1].score
        return OrganizationContextSearchResult(
            catalog_id=self.catalog.catalog_id,
            catalog_version=self.catalog.version,
            effective_at=self.catalog.effective_at,
            catalog_state=self.catalog.state,
            query_kind=query_kind,
            query_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
            matches=matches,
            filtered_count=filtered,
            ambiguous=ambiguous,
        )

    @staticmethod
    def _visible(record: OrganizationContextRecord, access: OrganizationAccessContext, effective_date: str) -> bool:
        if record.valid_from is not None and effective_date < record.valid_from:
            return False
        if record.valid_until is not None and effective_date > record.valid_until:
            return False
        if record.tenant_id is not None and record.tenant_id != access.tenant_id:
            return False
        if record.allowed_principal_ids and access.principal_id not in record.allowed_principal_ids:
            return False
        if record.allowed_roles and not set(record.allowed_roles).intersection(access.roles):
            return False
        return True

    @staticmethod
    def _score(record: OrganizationContextRecord, normalized_query: str, query_tokens: tuple[str, ...]) -> tuple[int, str]:
        label = _normalize(record.label)
        aliases = tuple(_normalize(value) for value in record.aliases)
        corpus = _normalize(record.searchable_text)
        if normalized_query == label:
            return 100, "EXACT_CANONICAL"
        if normalized_query in aliases:
            return 98, "EXACT_ALIAS"
        if any(alias and alias in normalized_query for alias in aliases):
            return 92, "ALIAS_IN_QUERY"
        if label and label in normalized_query:
            return 90, "CANONICAL_IN_QUERY"
        if normalized_query in corpus:
            return 75, "PHRASE_IN_RECORD"
        if query_tokens:
            matched = sum(1 for token in query_tokens if token in corpus)
            if matched == len(query_tokens):
                return min(70, 50 + matched * 3), "ALL_QUERY_TOKENS"
            if matched >= max(1, len(query_tokens) // 2):
                return min(49, 30 + matched * 2), "PARTIAL_QUERY_TOKENS"
        return 0, "NONE"
