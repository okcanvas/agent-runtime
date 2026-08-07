from __future__ import annotations

import asyncio
import sys
import types
from types import SimpleNamespace

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult
from okcanvas_agent_runtime.application.execution import OpenAIGenericAgentGateway
from okcanvas_agent_runtime.application.execution import openai_gateway as gateway_module
from okcanvas_agent_runtime.adapters.openai.runtime import sdk_readiness

from pathlib import Path


class _Step052CompatModelSettings:
    def __init__(self, **kwargs):
        self.values = kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)


class _Step052CompatModelRetrySettings:
    def __init__(self, **kwargs):
        self.max_retries = kwargs.get("max_retries")
        self.policy = kwargs.get("policy")


def _install_step052_model_contract(fake_agents) -> None:
    fake_agents.ModelSettings = _Step052CompatModelSettings
    fake_agents.ModelRetrySettings = _Step052CompatModelRetrySettings
    fake_agents.retry_policies = types.SimpleNamespace(
        never=lambda: (lambda _context: False)
    )

ROOT = Path(__file__).resolve().parents[1]


def test_gateway_uses_definition_hooks_trace_and_no_session(monkeypatch) -> None:
    captured = {"events": []}
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["agent"] = kwargs
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeRunConfig:
        def __init__(self, **kwargs):
            captured["run_config"] = kwargs

    class FakeRunHooks:
        pass

    class FakeRunner:
        @classmethod
        async def run(cls, agent, request, *, max_turns, hooks, run_config, error_handlers=None, session):
            captured["request"] = request
            captured["max_turns"] = max_turns
            captured["session"] = session
            await hooks.on_agent_start(SimpleNamespace(), agent)
            await hooks.on_llm_start(SimpleNamespace(), agent, agent.instructions, [{"role": "user"}])
            response = SimpleNamespace(response_id="resp_generic", request_id="req_transport", output=[1])
            await hooks.on_llm_end(SimpleNamespace(), agent, response)
            output = CodingAgentResult(
                status=AgentStatus.PARTIAL,
                summary="fake",
                findings=[],
                unverified=[],
            )
            await hooks.on_agent_end(SimpleNamespace(), agent, output)
            usage = SimpleNamespace(
                requests=1,
                input_tokens=11,
                output_tokens=4,
                total_tokens=15,
                input_tokens_details=SimpleNamespace(cached_tokens=3),
                output_tokens_details=SimpleNamespace(reasoning_tokens=1),
            )

            class Result:
                context_wrapper = SimpleNamespace(usage=usage)
                last_response_id = "resp_generic"

                def final_output_as(self, output_type, raise_if_incorrect_type=False):
                    assert output_type is CodingAgentResult
                    assert raise_if_incorrect_type is True
                    return output

            return Result()

    fake_agents.Agent = FakeAgent
    fake_agents.RunConfig = FakeRunConfig
    _install_step052_model_contract(fake_agents)
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.gen_trace_id = lambda: "trace_generic"
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
    monkeypatch.setattr(sdk_readiness.importlib.metadata, "version", lambda name: "0.19.0")
    monkeypatch.setattr(gateway_module.importlib.metadata, "version", lambda name: "0.19.0")

    async def sink(event):
        captured["events"].append(event)

    result = asyncio.run(
        OpenAIGenericAgentGateway().run(
            definition=AgentDefinitionCatalog(ROOT).resolve("coding-agent"),
            request="supplied text",
            run_id="run_fixed",
            settings=RuntimeSettings(model="explicit-model", api_key="hidden-key"),
            lifecycle_sink=sink,
        )
    )
    assert captured["api_key"] == "hidden-key"
    assert captured["agent"]["tools"] == []
    assert captured["agent"]["handoffs"] == []
    assert captured["agent"]["output_type"] is CodingAgentResult
    assert captured["max_turns"] == 1
    assert captured["session"] is None
    assert captured["run_config"]["group_id"] == "run_fixed"
    assert captured["run_config"]["trace_include_sensitive_data"] is False
    assert "hidden-key" not in str(captured["run_config"])
    assert [event.event_type for event in captured["events"]] == [
        "agent.started",
        "model.started",
        "model.completed",
        "agent.completed",
    ]
    assert result.trace_id == "trace_generic"
    assert result.usage.total_tokens == 15
