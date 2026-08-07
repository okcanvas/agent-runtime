from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from okcanvas_agent_runtime.agent.mcp.definitions.errors import MCPDefinitionContractError, MCPDefinitionIntegrityError, MCPDefinitionNotFoundError
from okcanvas_agent_runtime.agent.mcp.definitions.models import MCPServerDefinition

_ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_MODULE_RE = re.compile(r"^okcanvas_agent_runtime\.adapters\.mcp\.servers\.[a-z][a-z0-9_]*$")
_ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
_COMMON_KEYS = {
    "schema_version",
    "server_id",
    "version",
    "name",
    "kind",
    "allowed_tools",
    "read_only",
    "cache_tools_list",
    "connect_timeout_seconds",
    "cleanup_timeout_seconds",
    "tool_timeout_seconds",
    "max_retry_attempts",
    "retry_backoff_seconds_base",
    "max_result_chars",
}
_STDIO_KEYS = _COMMON_KEYS | {"module"}
_REMOTE_KEYS = _COMMON_KEYS | {
    "url",
    "authorization_mode",
    "authorization_env",
    "http_timeout_seconds",
    "sse_read_timeout_seconds",
}
_REMOTE_V3_KEYS = _COMMON_KEYS | {
    "endpoint_mode",
    "url_template",
    "authorization_mode",
    "credential_ref",
    "required_roles",
    "http_timeout_seconds",
    "sse_read_timeout_seconds",
    "health_mode",
    "circuit_breaker_failure_threshold",
    "circuit_breaker_reset_seconds",
}
_ROLE_RE = re.compile(r"^[a-z][a-z0-9:_-]{1,63}$")
_CREDENTIAL_REF_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")


class MCPServerCatalog:
    """Resolve immutable, allowlisted MCP server declarations below ``specs/mcp``."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).expanduser().resolve()
        self.spec_root = (self.project_root / "specs" / "mcp").resolve()
        self.server_root = (self.spec_root / "servers").resolve()
        self.allowlist_path = (self.spec_root / "allowlist.json").resolve()
        self._allowlist = self._load_allowlist()

    def list_servers(self) -> tuple[MCPServerDefinition, ...]:
        return tuple(self.resolve(server_id) for server_id in sorted(self._allowlist))

    def resolve(self, server_id: str) -> MCPServerDefinition:
        if not _ID_RE.fullmatch(server_id):
            raise MCPDefinitionContractError("Invalid MCP server ID")
        if server_id not in self._allowlist:
            raise MCPDefinitionContractError(f"MCP server is not allowlisted: {server_id}")
        directory = self.server_root / server_id
        if directory.is_symlink():
            raise MCPDefinitionIntegrityError("Symbolic MCP server directories are forbidden")
        directory = directory.resolve()
        if directory.parent != self.server_root or not directory.is_dir():
            raise MCPDefinitionNotFoundError(f"MCP server definition not found: {server_id}")
        path = directory / "server.json"
        if path.is_symlink() or path.resolve().parent != directory or not path.is_file():
            raise MCPDefinitionIntegrityError("MCP server definition file is missing or unsafe")
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MCPDefinitionIntegrityError("MCP server definition is not valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise MCPDefinitionContractError("MCP server definition must be a JSON object")
        schema_version = self._string(payload, "schema_version")
        kind = self._string(payload, "kind")
        if schema_version == "okcanvas-mcp-server-v1" and kind == "builtin-stdio":
            self._require_exact_keys(payload, _STDIO_KEYS)
            return self._resolve_stdio(payload, server_id=server_id, path=path, raw=raw)
        if schema_version == "okcanvas-mcp-server-v2" and kind == "remote-streamable-http":
            self._require_exact_keys(payload, _REMOTE_KEYS)
            return self._resolve_remote(payload, server_id=server_id, path=path, raw=raw)
        if schema_version == "okcanvas-mcp-server-v3" and kind == "remote-streamable-http":
            self._require_exact_keys(payload, _REMOTE_V3_KEYS)
            return self._resolve_delegated_remote(payload, server_id=server_id, path=path, raw=raw)
        raise MCPDefinitionContractError("Unsupported MCP server definition schema or kind")

    def resolve_many(self, server_ids: tuple[str, ...]) -> tuple[MCPServerDefinition, ...]:
        if len(set(server_ids)) != len(server_ids):
            raise MCPDefinitionContractError("MCP server IDs must not contain duplicates")
        definitions = tuple(self.resolve(server_id) for server_id in server_ids)
        remote = tuple(item for item in definitions if item.is_remote_streamable_http)
        if remote and len(remote) != len(definitions):
            raise MCPDefinitionContractError("Remote Streamable HTTP V1 permits exactly one MCP server and no transport mixing")
        if len(remote) > 4:
            raise MCPDefinitionContractError("Multi-MCP foundation permits at most four remote servers")
        if remote and any(item.schema_version == "okcanvas-mcp-server-v2" for item in remote) and len(remote) != 1:
            raise MCPDefinitionContractError("Remote Streamable HTTP V1 permits exactly one MCP server")
        return definitions

    def _resolve_stdio(
        self,
        payload: dict[str, Any],
        *,
        server_id: str,
        path: Path,
        raw: bytes,
    ) -> MCPServerDefinition:
        common = self._resolve_common(payload, server_id=server_id)
        module = self._string(payload, "module")
        if not _MODULE_RE.fullmatch(module):
            raise MCPDefinitionContractError("MCP module must use the product-owned server namespace")
        return MCPServerDefinition(
            **common,
            module=module,
            url=None,
            url_template=None,
            endpoint_mode="local-stdio",
            authorization_mode="none",
            authorization_env=None,
            credential_ref=None,
            required_roles=(),
            http_timeout_seconds=None,
            sse_read_timeout_seconds=None,
            health_mode="none",
            circuit_breaker_failure_threshold=0,
            circuit_breaker_reset_seconds=0.0,
            definition_sha256=hashlib.sha256(raw).hexdigest(),
            definition_path=path,
        )

    def _resolve_remote(
        self,
        payload: dict[str, Any],
        *,
        server_id: str,
        path: Path,
        raw: bytes,
    ) -> MCPServerDefinition:
        common = self._resolve_common(payload, server_id=server_id)
        if common["cache_tools_list"] is not True:
            raise MCPDefinitionContractError(
                "Remote Streamable HTTP V1 requires cache_tools_list=true"
            )
        if common["max_retry_attempts"] != 0:
            raise MCPDefinitionContractError(
                "Remote Streamable HTTP V1 requires max_retry_attempts=0"
            )
        url = self._validate_remote_url(self._string(payload, "url"))
        authorization_mode = self._string(payload, "authorization_mode")
        authorization_env_raw = payload["authorization_env"]
        if authorization_mode == "none":
            if authorization_env_raw is not None:
                raise MCPDefinitionContractError(
                    "authorization_env must be null when authorization_mode=none"
                )
            authorization_env = None
        elif authorization_mode == "bearer-env":
            if not isinstance(authorization_env_raw, str) or not _ENV_RE.fullmatch(
                authorization_env_raw
            ):
                raise MCPDefinitionContractError(
                    "authorization_env must be an uppercase environment variable name"
                )
            authorization_env = authorization_env_raw
        else:
            raise MCPDefinitionContractError(
                "Remote Streamable HTTP V1 supports authorization_mode none or bearer-env"
            )
        http_timeout = self._bounded_number(payload, "http_timeout_seconds", 0.1, 30.0)
        sse_timeout = self._bounded_number(payload, "sse_read_timeout_seconds", 1.0, 300.0)
        return MCPServerDefinition(
            **common,
            module=None,
            url=url,
            url_template=None,
            endpoint_mode="exact",
            authorization_mode=authorization_mode,
            authorization_env=authorization_env,
            credential_ref=None,
            required_roles=(),
            http_timeout_seconds=http_timeout,
            sse_read_timeout_seconds=sse_timeout,
            health_mode="none",
            circuit_breaker_failure_threshold=0,
            circuit_breaker_reset_seconds=0.0,
            definition_sha256=hashlib.sha256(raw).hexdigest(),
            definition_path=path,
        )

    def _resolve_delegated_remote(
        self, payload: dict[str, Any], *, server_id: str, path: Path, raw: bytes
    ) -> MCPServerDefinition:
        common = self._resolve_common(payload, server_id=server_id)
        if common["cache_tools_list"] is not True:
            raise MCPDefinitionContractError("Delegated Remote MCP requires cache_tools_list=true")
        if common["max_retry_attempts"] != 0:
            raise MCPDefinitionContractError("Delegated Remote MCP requires max_retry_attempts=0")
        if self._string(payload, "endpoint_mode") != "tenant-template":
            raise MCPDefinitionContractError("Delegated Remote MCP requires tenant-template endpoint mode")
        template = self._string(payload, "url_template")
        if template.count("{tenant_id}") != 1:
            raise MCPDefinitionContractError("url_template must contain exactly one {tenant_id}")
        self._validate_remote_url(template.replace("{tenant_id}", "tenant-example"))
        if self._string(payload, "authorization_mode") != "delegated-bearer-ref":
            raise MCPDefinitionContractError("Delegated Remote MCP requires delegated-bearer-ref")
        credential_ref = self._string(payload, "credential_ref")
        if not _CREDENTIAL_REF_RE.fullmatch(credential_ref):
            raise MCPDefinitionContractError("credential_ref is invalid")
        roles = self._string_tuple(payload, "required_roles")
        if not roles or any(not _ROLE_RE.fullmatch(role) for role in roles):
            raise MCPDefinitionContractError("required_roles must contain valid role names")
        health_mode = self._string(payload, "health_mode")
        if health_mode != "passive":
            raise MCPDefinitionContractError("STEP085 supports passive MCP health only")
        threshold = payload["circuit_breaker_failure_threshold"]
        if not isinstance(threshold, int) or isinstance(threshold, bool) or not 1 <= threshold <= 10:
            raise MCPDefinitionContractError("circuit_breaker_failure_threshold must be 1..10")
        reset = self._bounded_number(payload, "circuit_breaker_reset_seconds", 1.0, 300.0)
        return MCPServerDefinition(
            **common, module=None, url=None, url_template=template, endpoint_mode="tenant-template",
            authorization_mode="delegated-bearer-ref", authorization_env=None,
            credential_ref=credential_ref, required_roles=roles,
            http_timeout_seconds=self._bounded_number(payload, "http_timeout_seconds", 0.1, 30.0),
            sse_read_timeout_seconds=self._bounded_number(payload, "sse_read_timeout_seconds", 1.0, 300.0),
            health_mode=health_mode, circuit_breaker_failure_threshold=threshold,
            circuit_breaker_reset_seconds=reset, definition_sha256=hashlib.sha256(raw).hexdigest(),
            definition_path=path,
        )

    def _resolve_common(self, payload: dict[str, Any], *, server_id: str) -> dict[str, Any]:
        if payload["server_id"] != server_id:
            raise MCPDefinitionContractError("MCP server ID does not match its directory")
        version = self._string(payload, "version")
        if not _VERSION_RE.fullmatch(version):
            raise MCPDefinitionContractError("MCP server version must be semantic x.y.z")
        name = self._bounded_string(payload, "name", 200)
        tools = self._string_tuple(payload, "allowed_tools")
        if not tools:
            raise MCPDefinitionContractError("MCP server requires at least one allowed Tool")
        read_only = payload["read_only"]
        if read_only is not True:
            raise MCPDefinitionContractError("Only read-only MCP servers are supported")
        cache = payload["cache_tools_list"]
        if not isinstance(cache, bool):
            raise MCPDefinitionContractError("cache_tools_list must be boolean")
        connect_timeout = self._bounded_number(payload, "connect_timeout_seconds", 0.1, 60.0)
        cleanup_timeout = self._bounded_number(payload, "cleanup_timeout_seconds", 0.1, 60.0)
        tool_timeout = self._bounded_number(payload, "tool_timeout_seconds", 0.1, 60.0)
        retries = payload["max_retry_attempts"]
        if not isinstance(retries, int) or isinstance(retries, bool) or not 0 <= retries <= 3:
            raise MCPDefinitionContractError("max_retry_attempts must be an integer from 0 to 3")
        backoff = self._bounded_number(payload, "retry_backoff_seconds_base", 0.01, 10.0)
        max_chars = payload["max_result_chars"]
        if not isinstance(max_chars, int) or isinstance(max_chars, bool) or not 1024 <= max_chars <= 65536:
            raise MCPDefinitionContractError("max_result_chars must be an integer from 1024 to 65536")
        return {
            "schema_version": str(payload["schema_version"]),
            "server_id": server_id,
            "version": version,
            "name": name,
            "kind": str(payload["kind"]),
            "allowed_tools": tools,
            "read_only": True,
            "cache_tools_list": cache,
            "connect_timeout_seconds": connect_timeout,
            "cleanup_timeout_seconds": cleanup_timeout,
            "tool_timeout_seconds": tool_timeout,
            "max_retry_attempts": retries,
            "retry_backoff_seconds_base": backoff,
            "max_result_chars": max_chars,
        }

    @staticmethod
    def _validate_remote_url(value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme != "https":
            raise MCPDefinitionContractError("Remote MCP URL must use https")
        if not parts.hostname or parts.username or parts.password:
            raise MCPDefinitionContractError("Remote MCP URL authority is invalid")
        try:
            port = parts.port
        except ValueError as exc:
            raise MCPDefinitionContractError("Remote MCP URL port is invalid") from exc
        if port is not None and not 1 <= port <= 65535:
            raise MCPDefinitionContractError("Remote MCP URL port is invalid")
        if parts.query or parts.fragment:
            raise MCPDefinitionContractError("Remote MCP URL query and fragment are forbidden")
        if not parts.path.startswith("/") or parts.path in {"", "/"}:
            raise MCPDefinitionContractError("Remote MCP URL requires an explicit endpoint path")
        return value

    def _load_allowlist(self) -> frozenset[str]:
        if self.allowlist_path.is_symlink() or not self.allowlist_path.is_file():
            raise MCPDefinitionIntegrityError("MCP server allowlist is missing or symbolic")
        try:
            payload = json.loads(self.allowlist_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MCPDefinitionIntegrityError("MCP server allowlist is invalid") from exc
        if not isinstance(payload, dict) or set(payload) != {"schema_version", "allowed_server_ids"}:
            raise MCPDefinitionContractError("MCP server allowlist contract is invalid")
        if payload["schema_version"] != "okcanvas-mcp-allowlist-v1":
            raise MCPDefinitionContractError("Unsupported MCP allowlist schema")
        values = payload["allowed_server_ids"]
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            raise MCPDefinitionContractError("allowed_server_ids must be an array of strings")
        if len(values) != len(set(values)):
            raise MCPDefinitionContractError("MCP allowlist contains duplicates")
        if any(not _ID_RE.fullmatch(item) for item in values):
            raise MCPDefinitionContractError("MCP allowlist contains an invalid server ID")
        return frozenset(values)

    @staticmethod
    def _require_exact_keys(payload: dict[str, Any], expected: set[str]) -> None:
        unknown = set(payload) - expected
        missing = expected - set(payload)
        if unknown or missing:
            raise MCPDefinitionContractError(
                f"MCP definition keys mismatch: missing={sorted(missing)}, unknown={sorted(unknown)}"
            )

    @staticmethod
    def _string(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise MCPDefinitionContractError(f"{key} must be a non-empty string")
        return value.strip()

    @classmethod
    def _bounded_string(cls, payload: dict[str, Any], key: str, maximum: int) -> str:
        value = cls._string(payload, key)
        if len(value) > maximum:
            raise MCPDefinitionContractError(f"{key} exceeds {maximum} characters")
        return value

    @staticmethod
    def _string_tuple(payload: dict[str, Any], key: str) -> tuple[str, ...]:
        value = payload[key]
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            raise MCPDefinitionContractError(f"{key} must be an array of non-empty strings")
        if len(value) != len(set(value)):
            raise MCPDefinitionContractError(f"{key} must not contain duplicates")
        return tuple(value)

    @staticmethod
    def _bounded_number(payload: dict[str, Any], key: str, minimum: float, maximum: float) -> float:
        value = payload[key]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise MCPDefinitionContractError(f"{key} must be numeric")
        result = float(value)
        if not minimum <= result <= maximum:
            raise MCPDefinitionContractError(f"{key} must be between {minimum} and {maximum}")
        return result
