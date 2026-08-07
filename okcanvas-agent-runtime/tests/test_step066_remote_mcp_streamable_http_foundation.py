from __future__ import annotations

import asyncio
import json
import shutil
import sys
import types
from pathlib import Path

import pytest

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.adapters.mcp.clients import (
    RemoteMCPConfigurationError,
    RemoteMCPResultLimitError,
    create_openai_mcp_runtime,
    remote_mcp_headers,
    strict_remote_http_client_factory,
)
from okcanvas_agent_runtime.agent.mcp.definitions import (
    MCPDefinitionContractError,
    MCPServerCatalog,
)

ROOT = Path(__file__).resolve().parents[1]
REMOTE_ID = "organization-search"
REMOTE_ENV = "OKCANVAS_MCP_ORGANIZATION_SEARCH_BEARER"
REMOTE_URL = "https://mcp.example.invalid/mcp"


def _remote_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "okcanvas-mcp-server-v2",
        "server_id": REMOTE_ID,
        "version": "1.0.0",
        "name": "Organization Search MCP",
        "kind": "remote-streamable-http",
        "url": REMOTE_URL,
        "authorization_mode": "bearer-env",
        "authorization_env": REMOTE_ENV,
        "allowed_tools": ["search_documents", "read_document"],
        "read_only": True,
        "cache_tools_list": True,
        "connect_timeout_seconds": 10.0,
        "cleanup_timeout_seconds": 5.0,
        "tool_timeout_seconds": 15.0,
        "http_timeout_seconds": 15.0,
        "sse_read_timeout_seconds": 120.0,
        "max_retry_attempts": 0,
        "retry_backoff_seconds_base": 1.0,
        "max_result_chars": 24000,
    }
    payload.update(overrides)
    return payload


def _project_with_remote(tmp_path: Path, *, payload: dict[str, object] | None = None) -> Path:
    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs", project / "specs")
    allowlist_path = project / "specs/mcp/allowlist.json"
    allowlist = json.loads(allowlist_path.read_text(encoding="utf-8"))
    allowlist["allowed_server_ids"].append(REMOTE_ID)
    allowlist_path.write_text(json.dumps(allowlist, indent=2) + "\n", encoding="utf-8")
    remote_dir = project / "specs/mcp/servers" / REMOTE_ID
    remote_dir.mkdir()
    (remote_dir / "server.json").write_text(
        json.dumps(payload or _remote_payload(), indent=2) + "\n",
        encoding="utf-8",
    )
    return project


def _add_remote_agent(project: Path, *, session_mode: str = "disabled") -> None:
    source = project / "specs/agents/reference-research-agent"
    target = project / "specs/agents/remote-organization-search-agent"
    shutil.copytree(source, target)
    definition_path = target / "definition.json"
    definition = json.loads(definition_path.read_text(encoding="utf-8"))
    definition.update(
        {
            "agent_id": "remote-organization-search-agent",
            "version": "1.0.0",
            "name": "Remote Organization Search Agent",
            "mcp_servers": [REMOTE_ID],
            "workflow_name": "Remote Organization Search",
            "session_mode": session_mode,
        }
    )
    definition_path.write_text(json.dumps(definition, indent=2) + "\n", encoding="utf-8")


def test_remote_definition_is_exact_https_readonly_single_server_contract(tmp_path: Path) -> None:
    project = _project_with_remote(tmp_path)
    definition = MCPServerCatalog(project).resolve(REMOTE_ID)
    assert definition.schema_version == "okcanvas-mcp-server-v2"
    assert definition.kind == "remote-streamable-http"
    assert definition.url == REMOTE_URL
    assert definition.module is None
    assert definition.allowed_tools == ("search_documents", "read_document")
    assert definition.read_only is True
    assert definition.cache_tools_list is True
    assert definition.max_retry_attempts == 0
    assert definition.authorization_mode == "bearer-env"
    assert definition.authorization_env == REMOTE_ENV
    public = definition.to_public_dict()
    assert public["tls_required"] is True
    assert public["redirects_enabled"] is False
    assert public["proxy_environment_enabled"] is False
    assert "Authorization" not in repr(public)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"url": "http://mcp.example.invalid/mcp"}, "https"),
        ({"url": "https://user:secret@mcp.example.invalid/mcp"}, "authority"),
        ({"url": "https://mcp.example.invalid/mcp?tenant=1"}, "query"),
        ({"cache_tools_list": False}, "cache_tools_list"),
        ({"max_retry_attempts": 1}, "max_retry_attempts"),
        ({"authorization_mode": "bearer-env", "authorization_env": "bad-name"}, "uppercase"),
        ({"authorization_mode": "none", "authorization_env": REMOTE_ENV}, "must be null"),
    ],
)
def test_remote_definition_rejects_mutable_or_unsafe_transport_contract(
    tmp_path: Path,
    override: dict[str, object],
    message: str,
) -> None:
    project = _project_with_remote(tmp_path, payload=_remote_payload(**override))
    with pytest.raises(MCPDefinitionContractError, match=message):
        MCPServerCatalog(project).resolve(REMOTE_ID)


def test_remote_definition_cannot_mix_with_stdio_or_second_remote(tmp_path: Path) -> None:
    project = _project_with_remote(tmp_path)
    catalog = MCPServerCatalog(project)
    with pytest.raises(MCPDefinitionContractError, match="exactly one"):
        catalog.resolve_many(("reference-catalog", REMOTE_ID))


def test_remote_bearer_header_is_external_only_and_validated(tmp_path: Path, monkeypatch) -> None:
    definition = MCPServerCatalog(_project_with_remote(tmp_path)).resolve(REMOTE_ID)
    monkeypatch.delenv(REMOTE_ENV, raising=False)
    with pytest.raises(RemoteMCPConfigurationError, match=REMOTE_ENV):
        remote_mcp_headers(definition)
    monkeypatch.setenv(REMOTE_ENV, "secret-token")
    assert remote_mcp_headers(definition) == {"Authorization": "Bearer secret-token"}
    monkeypatch.setenv(REMOTE_ENV, "bad\r\nvalue")
    with pytest.raises(RemoteMCPConfigurationError, match="invalid"):
        remote_mcp_headers(definition)


def test_remote_factory_uses_official_streamable_http_static_filter_and_no_retry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = _project_with_remote(tmp_path)
    definition = MCPServerCatalog(project).resolve(REMOTE_ID)
    monkeypatch.setenv(REMOTE_ENV, "secret-token")
    captured: dict[str, object] = {}
    agents_mcp = types.ModuleType("agents.mcp")
    agents_mcp_util = types.ModuleType("agents.mcp.util")

    class FakeStdio:
        def __init__(self, **kwargs):
            raise AssertionError("Remote definition must not construct stdio")

    class FakeRemote:
        def __init__(self, **kwargs):
            captured["remote"] = kwargs
            self.name = kwargs["name"]
            self.cached_tools = None

        async def connect(self):
            return None

        async def cleanup(self):
            return None

        async def list_tools(self, *args, **kwargs):
            return []

        async def call_tool(self, *args, **kwargs):
            return types.SimpleNamespace(model_dump_json=lambda: '{"content":"ok"}')

    class FakeManager:
        def __init__(self, servers, **kwargs):
            captured["manager"] = {"servers": servers, **kwargs}
            self.active_servers = list(servers)

    def fake_filter(*, allowed_tool_names=None, blocked_tool_names=None):
        return {"allowed": allowed_tool_names, "blocked": blocked_tool_names}

    agents_mcp.MCPServerStdio = FakeStdio
    agents_mcp.MCPServerStreamableHttp = FakeRemote
    agents_mcp.MCPServerManager = FakeManager
    agents_mcp_util.create_static_tool_filter = fake_filter
    monkeypatch.setitem(sys.modules, "agents.mcp", agents_mcp)
    monkeypatch.setitem(sys.modules, "agents.mcp.util", agents_mcp_util)

    runtime = create_openai_mcp_runtime((definition,), project_root=project)
    assert len(runtime.servers) == 1
    remote = captured["remote"]
    assert isinstance(remote, dict)
    params = remote["params"]
    assert params["url"] == REMOTE_URL
    assert params["headers"] == {"Authorization": "Bearer secret-token"}
    assert params["httpx_client_factory"] is strict_remote_http_client_factory
    assert params["terminate_on_close"] is True
    assert params["ignore_initialized_notification_failure"] is False
    assert remote["tool_filter"]["allowed"] == ["search_documents", "read_document"]
    assert remote["require_approval"] == "never"
    assert remote["max_retry_attempts"] == 0
    manager = captured["manager"]
    assert manager["strict"] is True
    assert manager["connect_in_parallel"] is False
    assert "secret-token" not in repr(definition.to_public_dict())



def test_remote_wrapper_rejects_oversized_tool_result_before_return(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = _project_with_remote(tmp_path, payload=_remote_payload(max_result_chars=1024))
    definition = MCPServerCatalog(project).resolve(REMOTE_ID)
    monkeypatch.setenv(REMOTE_ENV, "secret-token")
    agents_mcp = types.ModuleType("agents.mcp")
    agents_mcp_util = types.ModuleType("agents.mcp.util")

    class FakeRemote:
        def __init__(self, **kwargs):
            self.name = kwargs["name"]
            self.cached_tools = None

        async def connect(self): return None
        async def cleanup(self): return None
        async def list_tools(self, *args, **kwargs): return []
        async def call_tool(self, *args, **kwargs):
            return types.SimpleNamespace(model_dump_json=lambda: "x" * 1025)

    class FakeManager:
        def __init__(self, servers, **kwargs): self.active_servers = list(servers)

    agents_mcp.MCPServerStdio = object
    agents_mcp.MCPServerStreamableHttp = FakeRemote
    agents_mcp.MCPServerManager = FakeManager
    agents_mcp_util.create_static_tool_filter = lambda **kwargs: kwargs
    monkeypatch.setitem(sys.modules, "agents.mcp", agents_mcp)
    monkeypatch.setitem(sys.modules, "agents.mcp.util", agents_mcp_util)

    runtime = create_openai_mcp_runtime((definition,), project_root=project)
    with pytest.raises(RemoteMCPResultLimitError, match="exceeds") as captured:
        asyncio.run(runtime.servers[0].call_tool("search_documents", {"query": "x"}))
    assert captured.value.server_id == REMOTE_ID
    assert captured.value.observed_chars == 1025
    assert captured.value.max_result_chars == 1024


def test_strict_http_client_disables_redirects_and_proxy_environment(monkeypatch) -> None:
    captured: dict[str, object] = {}
    import httpx

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    strict_remote_http_client_factory(headers={"X-Test": "1"}, timeout=3.0)
    assert captured["follow_redirects"] is False
    assert captured["trust_env"] is False
    assert captured["headers"] == {"X-Test": "1"}
    assert captured["timeout"] == 3.0


def test_remote_runtime_binding_includes_exact_transport_without_secret(tmp_path: Path) -> None:
    project = _project_with_remote(tmp_path)
    _add_remote_agent(project)
    definition = AgentDefinitionCatalog(project).resolve("remote-organization-search-agent")
    binding = AgentRuntimeBindingCatalog(project).resolve(definition)
    assert binding.execution_path == "remote-mcp-streamable-http-execution-v1"
    assert len(binding.mcp_servers) == 1
    entry = binding.mcp_servers[0]
    assert entry["kind"] == "remote-streamable-http"
    assert entry["url"] == REMOTE_URL
    assert entry["authorization_mode"] == "bearer-env"
    assert entry["authorization_env"] == REMOTE_ENV
    assert entry["tls_required"] == "true"
    assert entry["redirects_enabled"] == "false"
    assert len(entry["factory_sha256"]) == 64
    assert "secret-token" not in repr(binding.to_fingerprint_dict())


def test_remote_mcp_is_not_silently_added_to_session_composition(tmp_path: Path) -> None:
    project = _project_with_remote(tmp_path)
    _add_remote_agent(project, session_mode="sqlite-v1")
    definition = AgentDefinitionCatalog(project).resolve("remote-organization-search-agent")
    with pytest.raises(RuntimeError, match="builtin-stdio"):
        AgentRuntimeBindingCatalog(project).resolve(definition)
