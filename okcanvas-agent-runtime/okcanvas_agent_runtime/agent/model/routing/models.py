from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRoutingPolicy:
    schema_version: str
    policy_id: str
    version: str
    provider_id: str
    provider_adapter: str
    api: str
    transport: str
    base_url: str
    model_id_pattern: str
    allow_provider_prefixes: bool
    automatic_fallback: bool
    fallback_model_ids: tuple[str, ...]
    trace_include_sensitive_data: bool
    policy_sha256: str

    @property
    def route_id(self) -> str:
        return f"{self.provider_id}:{self.api}:{self.transport}"

    def to_binding_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_id": self.policy_id,
            "version": self.version,
            "route_id": self.route_id,
            "provider_id": self.provider_id,
            "provider_adapter": self.provider_adapter,
            "api": self.api,
            "transport": self.transport,
            "base_url": self.base_url,
            "model_id_pattern": self.model_id_pattern,
            "allow_provider_prefixes": self.allow_provider_prefixes,
            "automatic_fallback": self.automatic_fallback,
            "fallback_model_ids": list(self.fallback_model_ids),
            "trace_include_sensitive_data": self.trace_include_sensitive_data,
            "policy_sha256": self.policy_sha256,
        }


@dataclass(frozen=True)
class ResolvedModelRoute:
    policy: ModelRoutingPolicy
    model_id: str

    def to_safe_event_dict(self) -> dict[str, object]:
        return {
            "model_route_id": self.policy.route_id,
            "provider_id": self.policy.provider_id,
            "api": self.policy.api,
            "transport": self.policy.transport,
            "model": self.model_id,
            "automatic_fallback": self.policy.automatic_fallback,
        }
