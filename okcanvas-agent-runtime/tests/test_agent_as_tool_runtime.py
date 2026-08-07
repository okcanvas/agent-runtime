from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.agent.subagents.agent_tools import AgentToolPolicyCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult
from okcanvas_agent_runtime.application.execution import OpenAIGenericAgentGateway
from okcanvas_agent_runtime.application.execution import openai_gateway as gateway_module
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.adapters.openai.runtime import sdk_readiness
from okcanvas_agent_runtime.adapters.streaming import InMemoryNativeSDKStreamBroker

ROOT = Path(__file__).resolve().parents[1]
RAW_ARGUMENT_SENTINEL = "STEP042-RAW-TOOL-ARGUMENT-MUST-NOT-PERSIST"
RAW_RESULT_SENTINEL = "STEP042-RAW-CHILD-ITEM-MUST-NOT-PERSIST"


def _usage(input_tokens: int, output_tokens: int):
    return SimpleNamespace(
        requests=1,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        input_tokens_details=SimpleNamespace(cached_tokens=0),
        output_tokens_details=SimpleNamespace(reasoning_tokens=0),
    )


def _install_fake_agents(monkeypatch, captured: dict[str, object]) -> None:
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"

    parent_before = _usage(11, 3)
    after_child = _usage(28, 8)
    total_usage = _usage(40, 12)
    child_output = CodingAgentResult(
        status=AgentStatus.PASS,
        summary="Nested specialist result.",
        findings=[],
        unverified=[],
    )
    parent_output = CodingAgentResult(
        status=AgentStatus.PASS,
        summary="Parent retained control after nested specialist.",
        findings=[],
        unverified=[],
    )

    class FakeRunConfig:
        def __init__(self, **kwargs):
            self.values = kwargs

    class FakeRunHooks:
        pass

    class FakeAgentTool:
        def __init__(self, child, **kwargs):
            self.child = child
            self.name = kwargs["tool_name"]
            self.description = kwargs["tool_description"]
            self._kwargs = kwargs
            self._tool_origin = SimpleNamespace(
                type=SimpleNamespace(value="agent_as_tool"),
                agent_name=child.name,
                agent_tool_name=self.name,
            )

        async def on_invoke_tool(self, context, input_json):
            captured["agent_tool_invocations"] = int(captured.get("agent_tool_invocations", 0)) + 1
            captured["nested_run_streamed"] = int(captured.get("nested_run_streamed", 0)) + 1
            captured["nested_input"] = input_json
            hooks = self._kwargs["hooks"]
            await hooks.on_agent_start(SimpleNamespace(usage=parent_before), self.child)
            await hooks.on_llm_start(
                SimpleNamespace(usage=parent_before),
                self.child,
                self.child.instructions,
                [{"role": "user"}],
            )
            on_stream = self._kwargs["on_stream"]
            await on_stream(
                {
                    "event": SimpleNamespace(
                        type="agent_updated_stream_event", new_agent=self.child
                    ),
                    "agent": self.child,
                    "tool_call": SimpleNamespace(call_id="nested-call"),
                }
            )
            await on_stream(
                {
                    "event": SimpleNamespace(
                        type="raw_response_event",
                        data=SimpleNamespace(
                            type="response.output_text.delta", delta="Nested specialist"
                        ),
                    ),
                    "agent": self.child,
                    "tool_call": SimpleNamespace(call_id="nested-call"),
                }
            )
            await on_stream(
                {
                    "event": SimpleNamespace(
                        type="run_item_stream_event",
                        name="nested_message",
                        item=SimpleNamespace(
                            type="message_output_item",
                            agent=self.child,
                            content=RAW_RESULT_SENTINEL,
                        ),
                    ),
                    "agent": self.child,
                    "tool_call": SimpleNamespace(call_id="nested-call"),
                }
            )
            await hooks.on_llm_end(
                SimpleNamespace(usage=after_child),
                self.child,
                SimpleNamespace(response_id="resp-child", request_id="req-child", output=[1]),
            )
            await hooks.on_agent_end(SimpleNamespace(usage=after_child), self.child, child_output)

            class NestedResult:
                context_wrapper = SimpleNamespace(usage=after_child)
                final_output = child_output
                new_items = []

                def final_output_as(self, output_type, raise_if_incorrect_type=False):
                    assert output_type is CodingAgentResult
                    assert raise_if_incorrect_type is True
                    return child_output

            return await self._kwargs["custom_output_extractor"](NestedResult())

    class FakeAgent:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

        def as_tool(self, **kwargs):
            captured["as_tool_constructed"] = int(captured.get("as_tool_constructed", 0)) + 1
            captured["child_run_config"] = kwargs["run_config"].values
            captured["child_session"] = kwargs["session"]
            return FakeAgentTool(self, **kwargs)

    class FakeStreamingResult:
        context_wrapper = SimpleNamespace(usage=total_usage)
        last_response_id = "resp-parent-final"

        async def stream_events(self):
            parent = captured["parent_agent"]
            hooks = captured["outer_hooks"]
            tool = parent.tools[0]
            await hooks.on_agent_start(SimpleNamespace(usage=_usage(0, 0)), parent)
            await hooks.on_llm_start(
                SimpleNamespace(usage=_usage(0, 0)), parent, parent.instructions, [{"role": "user"}]
            )
            await hooks.on_llm_end(
                SimpleNamespace(usage=parent_before),
                parent,
                SimpleNamespace(response_id="resp-parent-before", request_id="req-1", output=[1]),
            )
            tool_context = SimpleNamespace(
                tool_name=tool.name,
                tool_call_id="agent-tool-call-1",
                tool_arguments='{"input":"' + RAW_ARGUMENT_SENTINEL + '"}',
                tool_call=SimpleNamespace(call_id="agent-tool-call-1"),
                usage=parent_before,
                run_config=SimpleNamespace(parent=True),
                context=None,
            )
            await hooks.on_tool_start(tool_context, parent, tool)
            result = await tool.on_invoke_tool(tool_context, tool_context.tool_arguments)
            tool_context.usage = after_child
            await hooks.on_tool_end(tool_context, parent, tool, result)
            await hooks.on_llm_start(
                SimpleNamespace(usage=after_child), parent, parent.instructions, [{"role": "tool"}]
            )
            await hooks.on_llm_end(
                SimpleNamespace(usage=total_usage),
                parent,
                SimpleNamespace(response_id="resp-parent-final", request_id="req-2", output=[1]),
            )
            await hooks.on_agent_end(SimpleNamespace(usage=total_usage), parent, parent_output)
            yield SimpleNamespace(
                type="raw_response_event",
                data=SimpleNamespace(type="response.output_text.delta", delta="Parent final"),
            )

        def final_output_as(self, output_type, raise_if_incorrect_type=False):
            assert output_type is CodingAgentResult
            assert raise_if_incorrect_type is True
            return parent_output

    class FakeRunner:
        @classmethod
        async def run(cls, *args, **kwargs):
            captured["run"] = int(captured.get("run", 0)) + 1
            raise AssertionError("STEP042 requires streaming")

        @classmethod
        def run_streamed(cls, agent, request, **kwargs):
            captured["run_streamed"] = int(captured.get("run_streamed", 0)) + 1
            captured["parent_agent"] = agent
            captured["outer_hooks"] = kwargs["hooks"]
            captured["request"] = request
            return FakeStreamingResult()

    class FakeModelSettings:
        def __init__(self, **kwargs):
            self.values = kwargs

    fake_agents.Agent = FakeAgent
    fake_agents.RunConfig = FakeRunConfig
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.ModelSettings = FakeModelSettings
    fake_agents.gen_trace_id = lambda: "trace-step042"
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


def test_agent_as_tool_policy_binding_and_gateway(monkeypatch) -> None:
    definition = AgentDefinitionCatalog(ROOT).resolve("agent-tool-manager-agent")
    child = AgentDefinitionCatalog(ROOT).resolve("agent-tool-specialist-agent")
    policy = AgentToolPolicyCatalog(ROOT).resolve()
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    assert definition.agent_tools == (child.agent_id,)
    assert policy.max_agent_tool_calls_per_run == 1
    assert policy.inherit_parent_run_config is False
    assert binding.execution_path == "agent-as-tool-execution-v1"
    assert binding.agent_tool_policy is not None
    assert len(binding.agent_tool_runtime_sha256 or "") == 64

    captured: dict[str, object] = {"events": []}
    _install_fake_agents(monkeypatch, captured)
    broker = InMemoryNativeSDKStreamBroker()

    async def sink(event):
        captured["events"].append(event)

    result = asyncio.run(
        OpenAIGenericAgentGateway(native_stream_broker=broker).run(
            definition=definition,
            request="Use the declared nested specialist.",
            run_id="run-step042-unit",
            settings=RuntimeSettings(model="test-model", api_key="hidden-key"),
            lifecycle_sink=sink,
        )
    )
    events = captured["events"]
    assert captured["as_tool_constructed"] == 1
    assert captured["agent_tool_invocations"] == 1
    assert captured["run_streamed"] == 1
    assert captured["nested_run_streamed"] == 1
    assert captured.get("run", 0) == 0
    assert captured["child_session"] is None
    assert captured["child_run_config"]["trace_metadata"]["run_config_inherited"] is False
    assert captured["child_run_config"]["model_settings"].values["store"] is False
    assert [item.event_type for item in events].count("agent.tool.started") == 1
    assert [item.event_type for item in events].count("agent.tool.completed") == 1
    assert result.usage.total_tokens == 52
    assert result.output.status is AgentStatus.PASS
    serialized_events = str([item.payload for item in events])
    assert RAW_ARGUMENT_SENTINEL not in serialized_events
    assert RAW_RESULT_SENTINEL not in serialized_events
