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
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.agent.subagents.handoffs import NativeHandoffPolicyCatalog
from okcanvas_agent_runtime.adapters.openai.runtime import sdk_readiness
from okcanvas_agent_runtime.adapters.streaming import InMemoryNativeSDKStreamBroker


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


def _install_fake_agents(monkeypatch, captured: dict[str, object]) -> None:
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"
    extensions = types.ModuleType("agents.extensions")
    filters = types.ModuleType("agents.extensions.handoff_filters")

    def remove_all_tools(data):
        return data

    filters.remove_all_tools = remove_all_tools
    extensions.handoff_filters = filters

    class FakeAgent:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeHandoff:
        def __init__(self, agent, **kwargs):
            self.agent = agent
            for key, value in kwargs.items():
                setattr(self, key, value)

    def fake_handoff(agent, **kwargs):
        captured["handoff"] = FakeHandoff(agent, **kwargs)
        return captured["handoff"]

    class FakeRunConfig:
        def __init__(self, **kwargs):
            captured["run_config"] = kwargs

    class FakeRunHooks:
        pass

    parent_usage = SimpleNamespace(
        requests=1,
        input_tokens=12,
        output_tokens=4,
        total_tokens=16,
        input_tokens_details=SimpleNamespace(cached_tokens=0),
        output_tokens_details=SimpleNamespace(reasoning_tokens=0),
    )
    total_usage = SimpleNamespace(
        requests=2,
        input_tokens=30,
        output_tokens=10,
        total_tokens=40,
        input_tokens_details=SimpleNamespace(cached_tokens=0),
        output_tokens_details=SimpleNamespace(reasoning_tokens=0),
    )
    output = CodingAgentResult(
        status=AgentStatus.PASS,
        summary="Native Handoff completed.",
        findings=[],
        unverified=[],
    )

    class FakeResult:
        context_wrapper = SimpleNamespace(usage=total_usage)
        last_response_id = "resp-handoff"

        async def stream_events(self):
            root = captured["root_agent"]
            handoff = root.handoffs[0]
            child = handoff.agent
            hooks = captured["hooks"]
            await hooks.on_agent_start(SimpleNamespace(usage=SimpleNamespace()), root)
            await hooks.on_llm_start(SimpleNamespace(), root, root.instructions, [{"role": "user"}])
            await hooks.on_llm_end(
                SimpleNamespace(usage=parent_usage),
                root,
                SimpleNamespace(response_id="resp-root", request_id="req-root", output=[1]),
            )
            await hooks.on_handoff(SimpleNamespace(usage=parent_usage), root, child)
            yield SimpleNamespace(type="agent_updated_stream_event", new_agent=child)
            await hooks.on_agent_start(SimpleNamespace(usage=total_usage), child)
            await hooks.on_llm_start(SimpleNamespace(), child, child.instructions, [{"role": "user"}])
            yield SimpleNamespace(
                type="raw_response_event",
                data=SimpleNamespace(type="response.output_text.delta", delta="handoff"),
            )
            await hooks.on_llm_end(
                SimpleNamespace(usage=total_usage),
                child,
                SimpleNamespace(response_id="resp-child", request_id="req-child", output=[1]),
            )
            await hooks.on_agent_end(SimpleNamespace(usage=total_usage), child, output)

        def final_output_as(self, output_type, raise_if_incorrect_type=False):
            assert output_type is CodingAgentResult
            assert raise_if_incorrect_type is True
            return output

    class FakeRunner:
        @classmethod
        async def run(cls, *args, **kwargs):
            raise AssertionError("Handoff test uses streaming")

        @classmethod
        def run_streamed(cls, agent, request, **kwargs):
            captured["root_agent"] = agent
            captured["hooks"] = kwargs["hooks"]
            captured["request"] = request
            return FakeResult()

    fake_agents.Agent = FakeAgent
    fake_agents.RunConfig = FakeRunConfig
    _install_step052_model_contract(fake_agents)
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.handoff = fake_handoff
    fake_agents.gen_trace_id = lambda: "trace-handoff"
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
    monkeypatch.setitem(sys.modules, "agents.extensions", extensions)
    monkeypatch.setitem(sys.modules, "agents.extensions.handoff_filters", filters)
    monkeypatch.setattr(sdk_readiness.importlib.metadata, "version", lambda name: "0.19.0")
    monkeypatch.setattr(gateway_module.importlib.metadata, "version", lambda name: "0.19.0")


def test_native_handoff_policy_and_runtime_binding_are_explicit() -> None:
    policy = NativeHandoffPolicyCatalog(ROOT).resolve()
    assert policy.max_handoffs_per_run == 1
    assert policy.max_depth == 1
    assert policy.input_filter_mode == "REMOVE_ALL_TOOLS"
    assert policy.nest_handoff_history is False
    definition = AgentDefinitionCatalog(ROOT).resolve("handoff-triage-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    assert binding.execution_path == "native-handoff-execution-v1"
    assert binding.handoff_policy is not None
    assert binding.handoff_policy["policy_sha256"] == policy.policy_sha256
    assert binding.handoff_runtime_sha256
    assert len(binding.child_agents) == 1


def test_gateway_builds_one_filtered_handoff_and_streams_child_agent(monkeypatch) -> None:
    captured: dict[str, object] = {"events": []}
    _install_fake_agents(monkeypatch, captured)
    broker = InMemoryNativeSDKStreamBroker()

    async def scenario():
        async def sink(event):
            captured["events"].append(event)

        result = await OpenAIGenericAgentGateway(native_stream_broker=broker).run(
            definition=AgentDefinitionCatalog(ROOT).resolve("handoff-triage-agent"),
            request="route this request",
            run_id="run-handoff-unit",
            settings=RuntimeSettings(model="test-model", api_key="hidden"),
            lifecycle_sink=sink,
        )
        return result, await broker.snapshot("run-handoff-unit")

    result, stream = asyncio.run(scenario())
    handoff = captured["handoff"]
    assert handoff.tool_name_override == "transfer_to_handoff_specialist_agent"
    assert handoff.nest_handoff_history is False
    assert handoff.input_filter.__name__ == "remove_all_tools"
    events = captured["events"]
    assert [item.event_type for item in events].count("agent.handoff") == 1
    handoff_event = next(item for item in events if item.event_type == "agent.handoff")
    assert handoff_event.payload["from_agent_id"] == "handoff-triage-agent"
    assert handoff_event.payload["to_agent_id"] == "handoff-specialist-agent"
    assert handoff_event.payload["history_persisted"] is False
    assert result.output.status is AgentStatus.PASS
    updated = next(item for item in stream if item.event_type == "agent.updated")
    assert updated.payload["agent_id"] == "handoff-specialist-agent"
