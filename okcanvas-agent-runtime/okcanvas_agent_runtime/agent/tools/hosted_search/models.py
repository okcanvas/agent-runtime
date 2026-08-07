from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HostedWebSearchPolicy:
    schema_version: str
    policy_id: str
    version: str
    tool_id: str
    allowed_domains: tuple[str, ...]
    search_context_size: str
    external_web_access: bool
    user_location_enabled: bool
    max_search_calls: int
    max_retrieved_sources: int
    max_citations: int
    max_title_chars: int
    require_retrieved_source: bool
    require_inline_citation: bool
    raw_query_persisted: bool
    raw_content_persisted: bool
    provider_call_id_persisted: bool
    response_include: tuple[str, ...]
    tool_choice: str
    parallel_tool_calls: bool
    max_turns: int
    policy_sha256: str

    def to_binding_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "version": self.version,
            "tool_id": self.tool_id,
            "allowed_domains": list(self.allowed_domains),
            "search_context_size": self.search_context_size,
            "external_web_access": self.external_web_access,
            "user_location_enabled": self.user_location_enabled,
            "max_search_calls": self.max_search_calls,
            "max_retrieved_sources": self.max_retrieved_sources,
            "max_citations": self.max_citations,
            "max_title_chars": self.max_title_chars,
            "require_retrieved_source": self.require_retrieved_source,
            "require_inline_citation": self.require_inline_citation,
            "raw_query_persisted": self.raw_query_persisted,
            "raw_content_persisted": self.raw_content_persisted,
            "provider_call_id_persisted": self.provider_call_id_persisted,
            "response_include": list(self.response_include),
            "tool_choice": self.tool_choice,
            "parallel_tool_calls": self.parallel_tool_calls,
            "max_turns": self.max_turns,
            "policy_sha256": self.policy_sha256,
        }


@dataclass(frozen=True)
class HostedWebSearchSource:
    url: str
    title: str
    cited: bool
    citation_count: int

    def to_artifact_dict(self) -> dict[str, object]:
        return {
            "url": self.url,
            "title": self.title,
            "cited": self.cited,
            "citation_count": self.citation_count,
        }


@dataclass(frozen=True)
class HostedWebSearchEvidence:
    policy_id: str
    policy_sha256: str
    search_call_count: int
    retrieved_source_count: int
    citation_count: int
    sources: tuple[HostedWebSearchSource, ...]
    raw_query_persisted: bool = False
    raw_content_persisted: bool = False
    provider_call_id_persisted: bool = False

    def to_artifact_dict(self) -> dict[str, object]:
        return {
            "schema_version": "okcanvas-hosted-web-search-evidence-v1",
            "policy_id": self.policy_id,
            "policy_sha256": self.policy_sha256,
            "search_call_count": self.search_call_count,
            "retrieved_source_count": self.retrieved_source_count,
            "citation_count": self.citation_count,
            "sources": [item.to_artifact_dict() for item in self.sources],
            "raw_query_persisted": self.raw_query_persisted,
            "raw_content_persisted": self.raw_content_persisted,
            "provider_call_id_persisted": self.provider_call_id_persisted,
        }
