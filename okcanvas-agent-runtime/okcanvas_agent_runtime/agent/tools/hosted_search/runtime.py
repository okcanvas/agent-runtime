from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import unquote, urlsplit, urlunsplit

from okcanvas_agent_runtime.agent.tools.hosted_search.errors import HostedWebSearchEvidenceError
from okcanvas_agent_runtime.agent.tools.hosted_search.models import HostedWebSearchEvidence, HostedWebSearchPolicy, HostedWebSearchSource

_BLOCKED_SUFFIXES = (
    ".css",
    ".eot",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".svg",
    ".svgz",
    ".tar",
    ".tgz",
    ".woff",
    ".woff2",
    ".zip",
    ".gz",
)


def _field(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def normalize_source_url(url: str, policy: HostedWebSearchPolicy) -> str:
    if not isinstance(url, str) or not url or len(url) > 4096:
        raise HostedWebSearchEvidenceError("Hosted Web Search source URL is invalid")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise HostedWebSearchEvidenceError("Hosted Web Search source URL is invalid") from exc
    hostname = parsed.hostname.lower().rstrip(".") if parsed.hostname else None
    if (
        parsed.scheme not in {"http", "https"}
        or hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or not any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in policy.allowed_domains
        )
    ):
        raise HostedWebSearchEvidenceError("Hosted Web Search source URL violates domain policy")
    path = parsed.path.rstrip("/")
    decoded_path = unquote(path)
    if (
        not path
        or any(character in decoded_path for character in "?#")
        or any(ord(character) < 32 or ord(character) == 127 for character in decoded_path)
        or decoded_path.lower().endswith(_BLOCKED_SUFFIXES)
    ):
        raise HostedWebSearchEvidenceError("Hosted Web Search source path is invalid")
    return urlunsplit((parsed.scheme, hostname, path, "", ""))


def _bounded_title(value: Any, *, fallback: str, maximum: int) -> str:
    if not isinstance(value, str):
        return fallback
    normalized = " ".join(value.split())
    if not normalized or any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        return fallback
    return normalized[:maximum]


def build_sdk_web_search_tool(policy: HostedWebSearchPolicy) -> Any:
    from agents import WebSearchTool

    if policy.user_location_enabled:
        raise ValueError("STEP067 forbids Web Search user location")
    return WebSearchTool(
        user_location=None,
        filters={"allowed_domains": list(policy.allowed_domains)},
        search_context_size=policy.search_context_size,
        external_web_access=policy.external_web_access,
    )


def hosted_web_search_model_settings_kwargs(policy: HostedWebSearchPolicy) -> dict[str, object]:
    return {
        "reasoning": None,
        "response_include": list(policy.response_include),
        "store": False,
        "tool_choice": policy.tool_choice,
        "parallel_tool_calls": policy.parallel_tool_calls,
    }


def extract_hosted_web_search_evidence(
    items: Sequence[Any], policy: HostedWebSearchPolicy
) -> HostedWebSearchEvidence:
    search_calls: list[Any] = []
    retrieved_urls: list[str] = []
    seen_retrieved: set[str] = set()
    citation_titles: dict[str, str] = {}
    citation_counts: dict[str, int] = {}
    total_citations = 0

    for item in items:
        raw_item = _field(item, "raw_item")
        item_type = _field(raw_item, "type")
        if item_type == "file_search_call":
            raise HostedWebSearchEvidenceError("File Search output is outside STEP067")
        if item_type == "web_search_call":
            search_calls.append(raw_item)
            if _field(raw_item, "status") != "completed":
                raise HostedWebSearchEvidenceError("Hosted Web Search call did not complete")
            action = _field(raw_item, "action")
            sources = _field(action, "sources") if action is not None else None
            if not isinstance(sources, list):
                raise HostedWebSearchEvidenceError("Hosted Web Search sources are missing")
            for source in sources:
                raw_url = _field(source, "url")
                if not isinstance(raw_url, str):
                    raise HostedWebSearchEvidenceError("Hosted Web Search source URL is missing")
                normalized = normalize_source_url(raw_url, policy)
                if normalized not in seen_retrieved:
                    seen_retrieved.add(normalized)
                    retrieved_urls.append(normalized)
        elif item_type == "message":
            content = _field(raw_item, "content")
            if not isinstance(content, list):
                continue
            for part in content:
                if _field(part, "type") != "output_text":
                    continue
                annotations = _field(part, "annotations")
                if not isinstance(annotations, list):
                    continue
                for annotation in annotations:
                    if _field(annotation, "type") != "url_citation":
                        continue
                    raw_url = _field(annotation, "url")
                    if not isinstance(raw_url, str):
                        raise HostedWebSearchEvidenceError("Hosted Web Search citation URL is missing")
                    normalized = normalize_source_url(raw_url, policy)
                    total_citations += 1
                    if total_citations > policy.max_citations:
                        raise HostedWebSearchEvidenceError("Hosted Web Search citation limit exceeded")
                    citation_counts[normalized] = citation_counts.get(normalized, 0) + 1
                    citation_titles.setdefault(
                        normalized,
                        _bounded_title(
                            _field(annotation, "title"),
                            fallback=normalized,
                            maximum=policy.max_title_chars,
                        ),
                    )

    if len(search_calls) != policy.max_search_calls:
        raise HostedWebSearchEvidenceError("Hosted Web Search call count is not exact")
    if len(retrieved_urls) > policy.max_retrieved_sources:
        raise HostedWebSearchEvidenceError("Hosted Web Search source limit exceeded")
    if policy.require_retrieved_source and not retrieved_urls:
        raise HostedWebSearchEvidenceError("Hosted Web Search returned no source evidence")
    if policy.require_inline_citation and total_citations == 0:
        raise HostedWebSearchEvidenceError("Hosted Web Search returned no inline citation")
    if set(citation_counts) - set(retrieved_urls):
        raise HostedWebSearchEvidenceError("Hosted Web Search citation was not retrieved")

    sources = tuple(
        HostedWebSearchSource(
            url=url,
            title=citation_titles.get(url, url),
            cited=url in citation_counts,
            citation_count=citation_counts.get(url, 0),
        )
        for url in retrieved_urls
    )
    return HostedWebSearchEvidence(
        policy_id=policy.policy_id,
        policy_sha256=policy.policy_sha256,
        search_call_count=len(search_calls),
        retrieved_source_count=len(retrieved_urls),
        citation_count=total_citations,
        sources=sources,
    )
