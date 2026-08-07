from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MCPServerDefinition:
    schema_version: str
    server_id: str
    version: str
    name: str
    kind: str
    module: str | None
    url: str | None
    url_template: str | None
    endpoint_mode: str
    authorization_mode: str
    authorization_env: str | None
    credential_ref: str | None
    required_roles: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    read_only: bool
    cache_tools_list: bool
    connect_timeout_seconds: float
    cleanup_timeout_seconds: float
    tool_timeout_seconds: float
    http_timeout_seconds: float | None
    sse_read_timeout_seconds: float | None
    max_retry_attempts: int
    retry_backoff_seconds_base: float
    max_result_chars: int
    health_mode: str
    circuit_breaker_failure_threshold: int
    circuit_breaker_reset_seconds: float
    definition_sha256: str
    definition_path: Path

    @property
    def is_local_stdio(self) -> bool:
        return self.kind == "builtin-stdio"

    @property
    def is_remote_streamable_http(self) -> bool:
        return self.kind == "remote-streamable-http"

    @property
    def requires_delegated_identity(self) -> bool:
        return self.authorization_mode == "delegated-bearer-ref"

    def to_public_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "server_id": self.server_id,
            "version": self.version,
            "name": self.name,
            "kind": self.kind,
            "allowed_tools": list(self.allowed_tools),
            "read_only": self.read_only,
            "cache_tools_list": self.cache_tools_list,
            "connect_timeout_seconds": self.connect_timeout_seconds,
            "cleanup_timeout_seconds": self.cleanup_timeout_seconds,
            "tool_timeout_seconds": self.tool_timeout_seconds,
            "max_retry_attempts": self.max_retry_attempts,
            "retry_backoff_seconds_base": self.retry_backoff_seconds_base,
            "max_result_chars": self.max_result_chars,
            "health_mode": self.health_mode,
            "circuit_breaker_failure_threshold": self.circuit_breaker_failure_threshold,
            "circuit_breaker_reset_seconds": self.circuit_breaker_reset_seconds,
            "definition_sha256": self.definition_sha256,
        }
        if self.is_local_stdio:
            payload["module"] = self.module
        else:
            payload.update(
                {
                    "endpoint_mode": self.endpoint_mode,
                    "url": self.url,
                    "url_template": self.url_template,
                    "authorization_mode": self.authorization_mode,
                    "authorization_env": self.authorization_env,
                    "credential_ref": self.credential_ref,
                    "required_roles": list(self.required_roles),
                    "http_timeout_seconds": self.http_timeout_seconds,
                    "sse_read_timeout_seconds": self.sse_read_timeout_seconds,
                    "tls_required": True,
                    "redirects_enabled": False,
                    "proxy_environment_enabled": False,
                }
            )
        return payload
