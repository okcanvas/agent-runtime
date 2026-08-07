from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import (
    AgentStatus,
    CodingAgentResult,
    CodingFinding,
    FindingConfidence,
    FindingSeverity,
)
from okcanvas_agent_runtime.application.execution import OpenAIGenericAgentGateway
from okcanvas_agent_runtime.application.execution import openai_gateway as gateway_module
from okcanvas_agent_runtime.domain.runs import EventSource
from okcanvas_agent_runtime.adapters.openai.runtime import sdk_readiness

ROOT = Path(__file__).resolve().parents[1]


def test_generic_gateway_executes_registered_non_approval_function_tool(monkeypatch) -> None:
    captured: dict[str, object] = {"events": [], "tool_calls": 0}
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"

    class FakeToolContext:
        @classmethod
        def __class_getitem__(cls, _item):
            return cls

    def fake_function_tool(**kwargs):
        def decorate(func):
            return SimpleNamespace(
                name=kwargs["name_override"],
                needs_approval=kwargs["needs_approval"],
                invoke=func,
            )

        return decorate

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["agent"] = kwargs
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeModelSettings:
        def __init__(self, **kwargs):
            captured.setdefault("model_settings_calls", []).append(kwargs)
            captured["model_settings"] = kwargs

    class FakeRunConfig:
        def __init__(self, **kwargs):
            captured["run_config"] = kwargs

    class FakeRunHooks:
        pass

    class FakeRunner:
        @classmethod
        async def run(
            cls,
            agent,
            request,
            *,
            max_turns,
            hooks,
            run_config,
            error_handlers=None,
            session,
            context,
        ):
            captured["request"] = request
            captured["context"] = context
            captured["max_turns"] = max_turns
            await hooks.on_agent_start(SimpleNamespace(), agent)
            await hooks.on_llm_start(
                SimpleNamespace(), agent, agent.instructions, [{"role": "user"}]
            )
            tool = agent.tools[0]
            tool_context = SimpleNamespace(
                context=context,
                tool_name=tool.name,
                tool_call_id="call-hidden",
                tool_arguments='{"execution_id":"hidden"}',
            )
            await hooks.on_tool_start(tool_context, agent, tool)
            captured["tool_calls"] += 1
            result = await tool.invoke(tool_context, context["execution_id"])
            await hooks.on_tool_end(tool_context, agent, tool, result)
            response = SimpleNamespace(
                response_id="resp-function-tool",
                request_id="request-hidden",
                output=[1],
            )
            await hooks.on_llm_end(SimpleNamespace(), agent, response)
            output = CodingAgentResult(
                status=AgentStatus.PASS,
                summary="The registered local Function Tool completed.",
                findings=[
                    CodingFinding(
                        severity=FindingSeverity.INFO,
                        confidence=FindingConfidence.CONFIRMED,
                        title="Protected request fingerprint",
                        detail=f"sha256={result.sha256}, characters={result.characters}",
                        evidence=["local_text_fingerprint execution"],
                    )
                ],
                unverified=[],
            )
            await hooks.on_agent_end(SimpleNamespace(), agent, output)
            usage = SimpleNamespace(
                requests=2,
                input_tokens=20,
                output_tokens=10,
                total_tokens=30,
                input_tokens_details=None,
                output_tokens_details=None,
            )

            class Result:
                context_wrapper = SimpleNamespace(usage=usage)
                last_response_id = "resp-function-tool"

                def final_output_as(self, output_type, raise_if_incorrect_type=False):
                    return output

            return Result()

    fake_agents.Agent = FakeAgent
    fake_agents.ModelSettings = FakeModelSettings
    fake_agents.RunConfig = FakeRunConfig
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_tool_context = types.ModuleType("agents.tool_context")
    fake_tool_context.ToolContext = FakeToolContext
    fake_agents.function_tool = fake_function_tool
    fake_agents.gen_trace_id = lambda: "trace-function-tool"
    fake_agents.set_default_openai_key = lambda value: captured.setdefault("api_key", value)
    class _Step052FakeModelRetrySettings:
        def __init__(self, **kwargs):
            self.max_retries = kwargs.get("max_retries")
            self.policy = kwargs.get("policy")

    fake_agents.ModelRetrySettings = _Step052FakeModelRetrySettings
    fake_agents.retry_policies = types.SimpleNamespace(
        never=lambda: (lambda _context: False)
    )

    monkeypatch.setitem(sys.modules, "agents", fake_agents)
    monkeypatch.setitem(sys.modules, "agents.tool_context", fake_tool_context)
    monkeypatch.setattr(sdk_readiness.importlib.metadata, "version", lambda name: "0.19.0")
    monkeypatch.setattr(gateway_module.importlib.metadata, "version", lambda name: "0.19.0")

    async def sink(event):
        captured["events"].append(event)

    result = asyncio.run(
        OpenAIGenericAgentGateway().run(
            definition=AgentDefinitionCatalog(ROOT).resolve(
                "local-text-fingerprint-agent"
            ),
            request="fingerprint this governed request",
            run_id="run_function_tool",
            settings=RuntimeSettings(model="explicit-model", api_key="hidden-key"),
            lifecycle_sink=sink,
        )
    )
    assert captured["tool_calls"] == 1
    assert captured["agent"]["mcp_servers"] == []
    assert [tool.name for tool in captured["agent"]["tools"]] == [
        "local_text_fingerprint"
    ]
    assert any(
        item.get("tool_choice") == "required"
        for item in captured["model_settings_calls"]
    )
    assert any(
        getattr(item.get("retry"), "max_retries", None) == 0
        for item in captured["model_settings_calls"]
    )
    assert captured["context"]["execution_id"].startswith("execution_")
    assert "fingerprint this governed request" not in captured["request"]
    tool_events = [
        event for event in captured["events"] if event.event_type.startswith("tool.")
    ]
    assert [event.event_type for event in tool_events] == [
        "tool.started",
        "tool.completed",
    ]
    assert all(event.source is EventSource.AGENT_SDK for event in tool_events)
    assert tool_events[0].payload["tool_id"] == "local_text_fingerprint"
    assert tool_events[0].payload["arguments_persisted"] is False
    assert tool_events[1].payload["result_persisted"] is False
    serialized = repr([event.payload for event in tool_events])
    assert "fingerprint this governed request" not in serialized
    assert "call-hidden" not in serialized
    assert result.output.status is AgentStatus.PASS
