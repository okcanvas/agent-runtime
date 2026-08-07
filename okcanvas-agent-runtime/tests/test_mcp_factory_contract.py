from __future__ import annotations

import sys
import types
from pathlib import Path

from okcanvas_agent_runtime.adapters.mcp.clients import create_openai_mcp_runtime, minimal_mcp_environment
from okcanvas_agent_runtime.agent.mcp.definitions import MCPServerCatalog

ROOT = Path(__file__).resolve().parents[1]


def test_minimal_mcp_environment_excludes_openai_secrets(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")
    monkeypatch.setenv("UNRELATED_SECRET", "other-secret")
    definition = MCPServerCatalog(ROOT).resolve("reference-catalog")
    env = minimal_mcp_environment(ROOT, definition)
    assert "OPENAI_API_KEY" not in env
    assert "UNRELATED_SECRET" not in env
    assert env["OKCANVAS_PROJECT_ROOT"] == str(ROOT.resolve())
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"


def test_factory_uses_official_stdio_manager_static_allowlist_and_timeouts(monkeypatch) -> None:
    captured: dict[str, object] = {"servers": []}
    agents_mcp = types.ModuleType("agents.mcp")
    agents_mcp_util = types.ModuleType("agents.mcp.util")

    class FakeServer:
        def __init__(self, **kwargs):
            captured["servers"].append(kwargs)
            self.name = kwargs["name"]

    class FakeManager:
        def __init__(self, servers, **kwargs):
            captured["manager"] = {"servers": servers, **kwargs}
            self.active_servers = servers

    def fake_filter(*, allowed_tool_names=None, blocked_tool_names=None):
        return {"allowed_tool_names": allowed_tool_names, "blocked_tool_names": blocked_tool_names}

    agents_mcp.MCPServerStdio = FakeServer
    agents_mcp.MCPServerManager = FakeManager
    agents_mcp_util.create_static_tool_filter = fake_filter
    monkeypatch.setitem(sys.modules, "agents.mcp", agents_mcp)
    monkeypatch.setitem(sys.modules, "agents.mcp.util", agents_mcp_util)

    definition = MCPServerCatalog(ROOT).resolve("reference-catalog")
    runtime = create_openai_mcp_runtime((definition,), project_root=ROOT)
    assert len(runtime.servers) == 1
    server = captured["servers"][0]
    assert server["name"] == "reference-catalog"
    assert server["params"]["args"] == ["-m", definition.module]
    assert server["tool_filter"]["allowed_tool_names"] == list(definition.allowed_tools)
    assert server["require_approval"] == "never"
    assert server["failure_error_function"] is None
    assert server["client_session_timeout_seconds"] == definition.tool_timeout_seconds
    manager = captured["manager"]
    assert manager["strict"] is True
    assert manager["drop_failed_servers"] is True
