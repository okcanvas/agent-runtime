from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.agent.tools.hosted_search.errors import HostedWebSearchPolicyError
from okcanvas_agent_runtime.agent.tools.hosted_search.models import HostedWebSearchPolicy

SDK_TOOL_SOURCE_SHA256 = "1ba4d71d2e6b59638ce2bfee53529b36373ba6e8dadd1fdf68c6fea040bf6a3e"
SDK_RESPONSES_SOURCE_SHA256 = "37817cc1ba836f5cdfc59d4ab519f19f29432b0fb60d7c713cc5fba7a682a252"
SDK_TURN_RESOLUTION_SOURCE_SHA256 = "3bf639e8730785a591a0c70210f80cc1022be43b59b297df7c64a40387df36ae"

_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)


class HostedWebSearchPolicyCatalog:
    """Load the single immutable hosted Web Search policy."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.path = self.project_root / "specs/runtime/hosted-web-search-policy.json"

    def resolve(self) -> HostedWebSearchPolicy:
        if self.path.is_symlink() or not self.path.is_file():
            raise HostedWebSearchPolicyError("Hosted Web Search policy is missing or unsafe")
        try:
            raw = self.path.read_bytes()
            payload = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HostedWebSearchPolicyError("Hosted Web Search policy could not be decoded") from exc
        if not isinstance(payload, dict):
            raise HostedWebSearchPolicyError("Hosted Web Search policy must be an object")
        expected = {
            "schema_version",
            "policy_id",
            "version",
            "tool_id",
            "allowed_domains",
            "search_context_size",
            "external_web_access",
            "user_location_enabled",
            "max_search_calls",
            "max_retrieved_sources",
            "max_citations",
            "max_title_chars",
            "require_retrieved_source",
            "require_inline_citation",
            "raw_query_persisted",
            "raw_content_persisted",
            "provider_call_id_persisted",
            "response_include",
            "tool_choice",
            "parallel_tool_calls",
            "max_turns",
        }
        if set(payload) != expected:
            raise HostedWebSearchPolicyError("Hosted Web Search policy fields are not exact")
        if payload["schema_version"] != "okcanvas-hosted-web-search-policy-v1":
            raise HostedWebSearchPolicyError("Unsupported hosted Web Search policy schema")
        if payload["policy_id"] != "official-openai-docs-web-search-v1":
            raise HostedWebSearchPolicyError("STEP067 permits only the official docs policy")
        if payload["version"] != "1.0.0" or payload["tool_id"] != "web-search-v1":
            raise HostedWebSearchPolicyError("Hosted Web Search policy identity is invalid")
        domains = payload["allowed_domains"]
        if not isinstance(domains, list) or not 1 <= len(domains) <= 8:
            raise HostedWebSearchPolicyError("Hosted Web Search domains must contain 1..8 entries")
        normalized_domains: list[str] = []
        for value in domains:
            if not isinstance(value, str):
                raise HostedWebSearchPolicyError("Hosted Web Search domain must be a string")
            domain = value.strip().lower().rstrip(".")
            if domain != value or not _DOMAIN_RE.fullmatch(domain):
                raise HostedWebSearchPolicyError("Hosted Web Search domain is not canonical")
            if domain in normalized_domains:
                raise HostedWebSearchPolicyError("Hosted Web Search domains must be unique")
            normalized_domains.append(domain)
        if payload["search_context_size"] not in {"low", "medium", "high"}:
            raise HostedWebSearchPolicyError("Hosted Web Search context size is invalid")
        if payload["external_web_access"] is not True:
            raise HostedWebSearchPolicyError("STEP067 requires explicit external Web access")
        if payload["user_location_enabled"] is not False:
            raise HostedWebSearchPolicyError("STEP067 forbids user location")
        exact_ints = {
            "max_search_calls": 1,
            "max_retrieved_sources": 8,
            "max_citations": 8,
            "max_title_chars": 200,
            "max_turns": 2,
        }
        for key, expected_value in exact_ints.items():
            if payload[key] != expected_value or isinstance(payload[key], bool):
                raise HostedWebSearchPolicyError(f"Hosted Web Search {key} is invalid")
        if payload["require_retrieved_source"] is not True:
            raise HostedWebSearchPolicyError("STEP067 requires at least one retrieved source")
        if payload["require_inline_citation"] is not True:
            raise HostedWebSearchPolicyError("STEP067 requires at least one inline citation")
        for key in (
            "raw_query_persisted",
            "raw_content_persisted",
            "provider_call_id_persisted",
            "parallel_tool_calls",
        ):
            if payload[key] is not False:
                raise HostedWebSearchPolicyError(f"Hosted Web Search {key} must be false")
        if payload["response_include"] != ["web_search_call.action.sources"]:
            raise HostedWebSearchPolicyError("Hosted Web Search response include is invalid")
        if payload["tool_choice"] != "required":
            raise HostedWebSearchPolicyError("Hosted Web Search tool choice must be required")
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return HostedWebSearchPolicy(
            schema_version=str(payload["schema_version"]),
            policy_id=str(payload["policy_id"]),
            version=str(payload["version"]),
            tool_id=str(payload["tool_id"]),
            allowed_domains=tuple(normalized_domains),
            search_context_size=str(payload["search_context_size"]),
            external_web_access=True,
            user_location_enabled=False,
            max_search_calls=1,
            max_retrieved_sources=8,
            max_citations=8,
            max_title_chars=200,
            require_retrieved_source=True,
            require_inline_citation=True,
            raw_query_persisted=False,
            raw_content_persisted=False,
            provider_call_id_persisted=False,
            response_include=("web_search_call.action.sources",),
            tool_choice="required",
            parallel_tool_calls=False,
            max_turns=2,
            policy_sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        )
