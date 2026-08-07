from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult
from okcanvas_agent_runtime.application.execution import OpenAIGenericAgentGateway
from okcanvas_agent_runtime.application.execution import openai_gateway as gateway_module
from okcanvas_agent_runtime.domain.runs import EventSource
from okcanvas_agent_runtime.adapters.openai.runtime import sdk_readiness

ROOT = Path(__file__).resolve().parents[1]


def test_gateway_connects_allowlisted_mcp_and_emits_redacted_tool_events(monkeypatch) -> None:
    captured: dict[str, object] = {"events": []}
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"

    class FakeServer:
        name = "reference-catalog"

    class FakeManager:
        active_servers = [FakeServer()]

        async def __aenter__(self):
            captured["manager_entered"] = True
            return self

        async def __aexit__(self, exc_type, exc, tb):
            captured["manager_exited"] = True
            return False

    fake_runtime = SimpleNamespace(manager=FakeManager())
    monkeypatch.setattr(gateway_module, "create_openai_mcp_runtime", lambda *a, **k: fake_runtime)

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["agent"] = kwargs
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeRunConfig:
        def __init__(self, **kwargs):
            captured["run_config"] = kwargs

    class FakeModelSettings:
        def __init__(self, **kwargs):
            self.values = kwargs

    class FakeRunHooks:
        pass

    class FakeRunner:
        @classmethod
        async def run(cls, agent, request, *, max_turns, hooks, run_config, error_handlers=None, session):
            await hooks.on_agent_start(SimpleNamespace(), agent)
            await hooks.on_llm_start(SimpleNamespace(), agent, agent.instructions, [{"role": "user"}])
            tool = SimpleNamespace(
                name="search_reference",
                _tool_origin=SimpleNamespace(mcp_server_name="reference-catalog"),
            )
            context = SimpleNamespace(
                tool_name="search_reference",
                tool_call_id="call-secret-id",
                tool_arguments='{"query":"sensitive query"}',
            )
            await hooks.on_tool_start(context, agent, tool)
            await hooks.on_tool_end(context, agent, tool, '{"sensitive":"result"}')
            response = SimpleNamespace(response_id="resp_mcp", request_id="req", output=[1])
            await hooks.on_llm_end(SimpleNamespace(), agent, response)
            output = CodingAgentResult(
                status=AgentStatus.PASS,
                summary="Reference evidence was inspected.",
                findings=[],
                unverified=[],
            )
            await hooks.on_agent_end(SimpleNamespace(), agent, output)
            usage = SimpleNamespace(
                requests=2,
                input_tokens=100,
                output_tokens=20,
                total_tokens=120,
                input_tokens_details=SimpleNamespace(cached_tokens=10),
                output_tokens_details=SimpleNamespace(reasoning_tokens=2),
            )

            class Result:
                context_wrapper = SimpleNamespace(usage=usage)
                last_response_id = "resp_mcp"

                def final_output_as(self, output_type, raise_if_incorrect_type=False):
                    return output

            return Result()

    fake_agents.Agent = FakeAgent
    fake_agents.RunConfig = FakeRunConfig
    fake_agents.ModelSettings = FakeModelSettings
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.gen_trace_id = lambda: "trace_mcp"
    fake_agents.set_default_openai_key = lambda value: None
    class _Step052FakeModelRetrySettings:
        def __init__(self, **kwargs):
            self.max_retries = kwargs.get("max_retries")
            self.policy = kwargs.get("policy")

    fake_agents.ModelRetrySettings = _Step052FakeModelRetrySettings
    fake_agents.retry_policies = types.SimpleNamespace(
        never=lambda: (lambda _context: False)
    )

    monkeypatch.setitem(sys.modules, "agents", fake_agents)
    monkeypatch.setattr(sdk_readiness.importlib.metadata, "version", lambda name: "0.19.0")
    monkeypatch.setattr(gateway_module.importlib.metadata, "version", lambda name: "0.19.0")

    async def sink(event):
        captured["events"].append(event)

    result = asyncio.run(
        OpenAIGenericAgentGateway().run(
            definition=AgentDefinitionCatalog(ROOT).resolve("reference-research-agent"),
            request="Find the RunState implementation using MCP.",
            run_id="run_mcp",
            settings=RuntimeSettings(model="explicit-model", api_key="hidden-key"),
            lifecycle_sink=sink,
        )
    )
    assert captured["manager_entered"] is True
    assert captured["manager_exited"] is True
    assert [server.name for server in captured["agent"]["mcp_servers"]] == ["reference-catalog"]
    events = captured["events"]
    tool_events = [event for event in events if event.event_type.startswith("tool.")]
    assert [event.event_type for event in tool_events] == ["tool.started", "tool.completed"]
    assert all(event.source is EventSource.MCP for event in tool_events)
    serialized = repr([event.payload for event in tool_events])
    assert "sensitive query" not in serialized
    assert '"sensitive":"result"' not in serialized
    assert "call-secret-id" not in serialized
    assert tool_events[0].payload["tool_call_id_present"] is True
    assert result.trace_id == "trace_mcp"


def test_gateway_rejects_tool_from_unallowlisted_mcp_server(monkeypatch) -> None:
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"

    class FakeManager:
        active_servers = [SimpleNamespace(name="reference-catalog")]
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False

    monkeypatch.setattr(
        gateway_module,
        "create_openai_mcp_runtime",
        lambda *a, **k: SimpleNamespace(manager=FakeManager()),
    )

    class FakeAgent:
        def __init__(self, **kwargs):
            for key, value in kwargs.items(): setattr(self, key, value)
    class FakeRunConfig:
        def __init__(self, **kwargs): pass
    class FakeModelSettings:
        def __init__(self, **kwargs):
            self.values = kwargs
    class FakeRunHooks: pass
    class FakeRunner:
        @classmethod
        async def run(cls, agent, request, *, max_turns, hooks, run_config, error_handlers=None, session):
            tool = SimpleNamespace(
                name="write_file",
                _tool_origin=SimpleNamespace(mcp_server_name="unapproved-server"),
            )
            await hooks.on_tool_start(SimpleNamespace(tool_name="write_file"), agent, tool)

    fake_agents.Agent=FakeAgent; fake_agents.RunConfig=FakeRunConfig; fake_agents.ModelSettings=FakeModelSettings; fake_agents.RunHooks=FakeRunHooks
    fake_agents.Runner=FakeRunner; fake_agents.gen_trace_id=lambda:"trace"; fake_agents.set_default_openai_key=lambda v:None
    class _Step052FakeModelRetrySettings:
        def __init__(self, **kwargs):
            self.max_retries = kwargs.get("max_retries")
            self.policy = kwargs.get("policy")
    fake_agents.ModelRetrySettings = _Step052FakeModelRetrySettings
    fake_agents.retry_policies = types.SimpleNamespace(never=lambda: (lambda _context: False))
    monkeypatch.setitem(sys.modules,"agents",fake_agents)
    monkeypatch.setattr(sdk_readiness.importlib.metadata,"version",lambda name:"0.19.0")
    monkeypatch.setattr(gateway_module.importlib.metadata,"version",lambda name:"0.19.0")

    from okcanvas_agent_runtime.application.execution.errors import GenericExecutionFailure
    from okcanvas_agent_runtime.application.execution import GenericExecutionErrorCode

    try:
        asyncio.run(
            OpenAIGenericAgentGateway().run(
                definition=AgentDefinitionCatalog(ROOT).resolve("reference-research-agent"),
                request="work",
                run_id="run",
                settings=RuntimeSettings(model="model", api_key="key"),
                lifecycle_sink=lambda event: asyncio.sleep(0),
            )
        )
    except GenericExecutionFailure as exc:
        assert exc.code is GenericExecutionErrorCode.MCP_TOOL_POLICY_VIOLATION
    else:
        raise AssertionError("unallowlisted MCP Tool must fail")
