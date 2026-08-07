from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from okcanvas_agent_runtime.agent.mcp.definitions import MCPServerDefinition
from okcanvas_agent_runtime.application.mcp_access import BoundMCPAccess, MCPPassiveHealthRegistry

_ENV_ALLOWLIST = (
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "PATH",
    "HOME",
    "USERPROFILE",
    "LOCALAPPDATA",
    "APPDATA",
    "TEMP",
    "TMP",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
)


class RemoteMCPConfigurationError(RuntimeError):
    pass


class RemoteMCPResultLimitError(RuntimeError):
    def __init__(self, *, server_id: str, observed_chars: int, max_result_chars: int) -> None:
        super().__init__("Remote MCP Tool result exceeds the configured limit")
        self.server_id = server_id
        self.observed_chars = observed_chars
        self.max_result_chars = max_result_chars


@dataclass(frozen=True)
class OpenAIMCPRuntime:
    definitions: tuple[MCPServerDefinition, ...]
    servers: tuple[Any, ...]
    manager: Any


class _BoundedRemoteMCPServer:
    """Delegate one SDK remote server while bounding Tool results before model reuse."""

    def __init__(
        self, delegate: Any, *, max_result_chars: int, server_id: str,
        health_registry: MCPPassiveHealthRegistry | None = None,
        failure_threshold: int = 0, reset_seconds: float = 0.0,
    ) -> None:
        self._delegate = delegate
        self._max_result_chars = max_result_chars
        self._server_id = server_id
        self._health_registry = health_registry
        self._failure_threshold = failure_threshold
        self._reset_seconds = reset_seconds

    @property
    def name(self) -> str:
        return str(self._delegate.name)

    @property
    def cached_tools(self) -> Any:
        return getattr(self._delegate, "cached_tools", None)

    async def connect(self) -> Any:
        if self._health_registry is not None:
            self._health_registry.require_available(self._server_id)
        try:
            result = await self._delegate.connect()
        except Exception:
            if self._health_registry is not None:
                self._health_registry.record_failure(
                    self._server_id, threshold=self._failure_threshold, reset_seconds=self._reset_seconds
                )
            raise
        if self._health_registry is not None:
            self._health_registry.record_success(self._server_id)
        return result

    async def cleanup(self) -> Any:
        return await self._delegate.cleanup()

    async def list_tools(self, *args: Any, **kwargs: Any) -> Any:
        return await self._delegate.list_tools(*args, **kwargs)

    async def call_tool(self, *args: Any, **kwargs: Any) -> Any:
        if self._health_registry is not None:
            self._health_registry.require_available(self._server_id)
        try:
            result = await self._delegate.call_tool(*args, **kwargs)
            serialized = _serialize_mcp_result(result)
            if len(serialized) > self._max_result_chars:
                raise RemoteMCPResultLimitError(server_id=self._server_id, observed_chars=len(serialized), max_result_chars=self._max_result_chars)
        except Exception:
            if self._health_registry is not None:
                self._health_registry.record_failure(
                    self._server_id, threshold=self._failure_threshold, reset_seconds=self._reset_seconds
                )
            raise
        if self._health_registry is not None:
            self._health_registry.record_success(self._server_id)
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)


def _serialize_mcp_result(result: Any) -> str:
    model_dump_json = getattr(result, "model_dump_json", None)
    if callable(model_dump_json):
        return str(model_dump_json())
    model_dump = getattr(result, "model_dump", None)
    if callable(model_dump):
        return json.dumps(
            model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return json.dumps(result, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def minimal_mcp_environment(project_root: str | Path, definition: MCPServerDefinition) -> dict[str, str]:
    if not definition.is_local_stdio:
        raise ValueError("A subprocess environment is valid only for builtin-stdio MCP")
    env = {key: value for key in _ENV_ALLOWLIST if (value := os.environ.get(key))}
    env.update(
        {
            "OKCANVAS_PROJECT_ROOT": str(Path(project_root).resolve()),
            "OKCANVAS_REFERENCE_MCP_MAX_RESULT_CHARS": str(definition.max_result_chars),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return env


def remote_mcp_headers(
    definition: MCPServerDefinition, access: BoundMCPAccess | None = None
) -> dict[str, str] | None:
    if not definition.is_remote_streamable_http:
        raise ValueError("Remote headers are valid only for Streamable HTTP MCP")
    if definition.authorization_mode == "none":
        return None
    environment_name: str | None = None
    headers: dict[str, str] = {}
    if definition.authorization_mode == "bearer-env" and definition.authorization_env:
        environment_name = definition.authorization_env
    elif definition.authorization_mode == "delegated-bearer-ref" and access is not None:
        environment_name = access.credential_environment_variable
        headers.update(access.identity_headers())
    else:
        raise RemoteMCPConfigurationError("Remote MCP authorization definition is invalid")
    token = os.environ.get(environment_name)
    if token is None or not token.strip():
        raise RemoteMCPConfigurationError(
            f"Remote MCP bearer environment is not configured: {environment_name}"
        )
    token = token.strip()
    if len(token) > 8192 or "\r" in token or "\n" in token:
        raise RemoteMCPConfigurationError("Remote MCP bearer value is invalid")
    headers["Authorization"] = f"Bearer {token}"
    return headers


def strict_remote_http_client_factory(
    headers: dict[str, str] | None = None,
    timeout: Any = None,
    auth: Any = None,
) -> Any:
    try:
        import httpx
    except (ImportError, ModuleNotFoundError) as exc:  # pragma: no cover - dependency boundary
        raise RuntimeError("httpx is not installed") from exc
    kwargs: dict[str, Any] = {
        "follow_redirects": False,
        "trust_env": False,
    }
    if headers is not None:
        kwargs["headers"] = headers
    if timeout is not None:
        kwargs["timeout"] = timeout
    if auth is not None:
        kwargs["auth"] = auth
    return httpx.AsyncClient(**kwargs)


def create_openai_mcp_runtime(
    definitions: tuple[MCPServerDefinition, ...],
    *,
    project_root: str | Path,
    access_bindings: tuple[BoundMCPAccess | None, ...] | None = None,
    health_registry: MCPPassiveHealthRegistry | None = None,
) -> OpenAIMCPRuntime:
    if not definitions:
        raise ValueError("At least one MCP server definition is required")
    remote = tuple(item for item in definitions if item.is_remote_streamable_http)
    if remote and len(remote) != len(definitions):
        raise RemoteMCPConfigurationError("Remote MCP servers cannot mix with builtin stdio")
    if len(remote) > 4:
        raise RemoteMCPConfigurationError("At most four remote MCP servers are permitted")
    if access_bindings is None:
        access_bindings = tuple(None for _ in definitions)
    if len(access_bindings) != len(definitions):
        raise RemoteMCPConfigurationError("MCP access binding count does not match definitions")
    try:
        from agents.mcp import MCPServerManager, MCPServerStdio
        from agents.mcp.util import create_static_tool_filter
        if remote:
            from agents.mcp import MCPServerStreamableHttp
        else:
            MCPServerStreamableHttp = None
    except (ImportError, ModuleNotFoundError) as exc:  # pragma: no cover - live dependency boundary
        raise RuntimeError("openai-agents MCP support is not installed") from exc

    root = Path(project_root).resolve()
    servers: list[Any] = []
    for definition, access in zip(definitions, access_bindings, strict=True):
        tool_filter = create_static_tool_filter(allowed_tool_names=list(definition.allowed_tools))
        common = {
            "name": definition.server_id,
            "cache_tools_list": definition.cache_tools_list,
            "client_session_timeout_seconds": definition.tool_timeout_seconds,
            "tool_filter": tool_filter,
            "use_structured_content": False,
            "max_retry_attempts": definition.max_retry_attempts,
            "retry_backoff_seconds_base": definition.retry_backoff_seconds_base,
            "require_approval": "never",
            "failure_error_function": None,
        }
        if definition.is_local_stdio:
            if not definition.module:
                raise RuntimeError("builtin-stdio MCP definition has no module")
            servers.append(
                MCPServerStdio(
                    params={
                        "command": sys.executable,
                        "args": ["-m", definition.module],
                        "cwd": str(root),
                        "env": minimal_mcp_environment(root, definition),
                        "encoding": "utf-8",
                        "encoding_error_handler": "strict",
                    },
                    **common,
                )
            )
            continue
        if not definition.is_remote_streamable_http:
            raise RuntimeError("Unsupported MCP transport")
        if MCPServerStreamableHttp is None:
            raise RuntimeError("OpenAI Agents Streamable HTTP MCP support is unavailable")
        resolved_url = access.url if access is not None else definition.url
        if not resolved_url:
            raise RemoteMCPConfigurationError("Remote MCP endpoint is not bound")
        remote_server = MCPServerStreamableHttp(
            params={
                "url": resolved_url,
                "headers": remote_mcp_headers(definition, access),
                "timeout": definition.http_timeout_seconds,
                "sse_read_timeout": definition.sse_read_timeout_seconds,
                "terminate_on_close": True,
                "httpx_client_factory": strict_remote_http_client_factory,
                "ignore_initialized_notification_failure": False,
            },
            **common,
        )
        servers.append(
            _BoundedRemoteMCPServer(
                remote_server,
                max_result_chars=definition.max_result_chars,
                server_id=definition.server_id,
                health_registry=(health_registry if definition.health_mode == "passive" else None),
                failure_threshold=definition.circuit_breaker_failure_threshold,
                reset_seconds=definition.circuit_breaker_reset_seconds,
            )
        )
    manager = MCPServerManager(
        servers,
        connect_timeout_seconds=max(item.connect_timeout_seconds for item in definitions),
        cleanup_timeout_seconds=max(item.cleanup_timeout_seconds for item in definitions),
        drop_failed_servers=True,
        strict=True,
        connect_in_parallel=(len(servers) > 1),
    )
    return OpenAIMCPRuntime(definitions=definitions, servers=tuple(servers), manager=manager)
