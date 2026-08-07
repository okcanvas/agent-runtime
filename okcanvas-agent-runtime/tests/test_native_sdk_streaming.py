from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import httpx

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.application.execution import OpenAIGenericAgentGateway
from okcanvas_agent_runtime.application.execution import openai_gateway as gateway_module
from okcanvas_agent_runtime.adapters.openai.runtime import sdk_readiness
from okcanvas_agent_runtime.adapters.streaming import (
    InMemoryNativeSDKStreamBroker,
    adapt_sdk_stream_event,
)


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


def test_native_stream_adapter_forwards_only_safe_event_shapes() -> None:
    text = adapt_sdk_stream_event(
        SimpleNamespace(
            type="raw_response_event",
            data=SimpleNamespace(type="response.output_text.delta", delta="hello"),
        )
    )
    assert text == (
        "model.text.delta",
        {
            "delta": "hello",
            "response_event_type": "response.output_text.delta",
            "persisted": False,
        },
    )
    assert (
        adapt_sdk_stream_event(
            SimpleNamespace(
                type="raw_response_event",
                data=SimpleNamespace(
                    type="response.function_call_arguments.delta", delta='{"secret":'
                ),
            )
        )
        is None
    )
    item = adapt_sdk_stream_event(
        SimpleNamespace(
            type="run_item_stream_event",
            name="tool_called",
            item=SimpleNamespace(type="tool_call_item", agent=SimpleNamespace(name="A")),
        )
    )
    assert item is not None
    assert item[0] == "run.item"
    assert item[1]["item_type"] == "tool_call_item"
    assert "output" not in item[1]
    updated = adapt_sdk_stream_event(
        SimpleNamespace(
            type="agent_updated_stream_event", new_agent=SimpleNamespace(name="B")
        )
    )
    assert updated == (
        "agent.updated",
        {"agent_name": "B", "instructions_persisted": False},
    )


def test_gateway_uses_native_sdk_streaming_when_broker_is_configured(monkeypatch) -> None:
    captured: dict[str, object] = {"canonical": []}
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"

    class FakeAgent:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FakeRunConfig:
        def __init__(self, **kwargs):
            captured["run_config"] = kwargs

    class FakeRunHooks:
        pass

    output = CodingAgentResult(
        status=AgentStatus.PARTIAL,
        summary="streamed",
        findings=[],
        unverified=[],
    )
    usage = SimpleNamespace(
        requests=1,
        input_tokens=9,
        output_tokens=6,
        total_tokens=15,
        input_tokens_details=SimpleNamespace(cached_tokens=0),
        output_tokens_details=SimpleNamespace(reasoning_tokens=0),
    )

    class FakeStreamingResult:
        context_wrapper = SimpleNamespace(usage=usage)
        last_response_id = "resp_stream"

        async def stream_events(self):
            agent = captured["agent"]
            hooks = captured["hooks"]
            await hooks.on_agent_start(SimpleNamespace(), agent)
            await hooks.on_llm_start(SimpleNamespace(), agent, agent.instructions, [{"role": "user"}])
            yield SimpleNamespace(type="agent_updated_stream_event", new_agent=agent)
            yield SimpleNamespace(
                type="raw_response_event",
                data=SimpleNamespace(type="response.output_text.delta", delta="hel"),
            )
            yield SimpleNamespace(
                type="raw_response_event",
                data=SimpleNamespace(type="response.function_call_arguments.delta", delta="SECRET"),
            )
            yield SimpleNamespace(
                type="run_item_stream_event",
                name="message_output_created",
                item=SimpleNamespace(type="message_output_item", agent=agent, output="SECRET"),
            )
            yield SimpleNamespace(
                type="raw_response_event",
                data=SimpleNamespace(type="response.output_text.delta", delta="lo"),
            )
            response = SimpleNamespace(response_id="resp_stream", request_id="req", output=[1])
            await hooks.on_llm_end(SimpleNamespace(), agent, response)
            await hooks.on_agent_end(SimpleNamespace(), agent, output)

        def final_output_as(self, output_type, raise_if_incorrect_type=False):
            assert output_type is CodingAgentResult
            assert raise_if_incorrect_type is True
            return output

    class FakeRunner:
        @classmethod
        async def run(cls, *args, **kwargs):
            raise AssertionError("non-streaming Runner.run must not be used")

        @classmethod
        def run_streamed(cls, agent, request, **kwargs):
            captured["agent"] = agent
            captured["request"] = request
            captured["hooks"] = kwargs["hooks"]
            captured["run_streamed_calls"] = int(captured.get("run_streamed_calls", 0)) + 1
            return FakeStreamingResult()

    fake_agents.Agent = FakeAgent
    fake_agents.RunConfig = FakeRunConfig
    _install_step052_model_contract(fake_agents)
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.gen_trace_id = lambda: "trace_stream"
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

    broker = InMemoryNativeSDKStreamBroker()

    async def scenario():
        async def sink(event):
            captured["canonical"].append(event)

        result = await OpenAIGenericAgentGateway(native_stream_broker=broker).run(
            definition=AgentDefinitionCatalog(ROOT).resolve("coding-agent"),
            request="supplied text",
            run_id="run_streamed",
            settings=RuntimeSettings(model="explicit-model", api_key="hidden-key"),
            lifecycle_sink=sink,
        )
        return result, await broker.snapshot("run_streamed")

    result, events = asyncio.run(scenario())
    assert captured["run_streamed_calls"] == 1
    assert result.output.summary == "streamed"
    assert result.usage.total_tokens == 15
    assert [event.event_type for event in events] == [
        "sdk.stream.started",
        "agent.updated",
        "model.text.delta",
        "run.item",
        "model.text.delta",
        "sdk.stream.completed",
    ]
    serialized = " ".join(str(event.payload) for event in events)
    assert "SECRET" not in serialized
    assert [event.event_type for event in captured["canonical"]] == [
        "agent.started",
        "model.started",
        "model.completed",
        "agent.completed",
    ]


def test_subscriber_disconnect_does_not_cancel_or_close_native_stream() -> None:
    async def scenario():
        broker = InMemoryNativeSDKStreamBroker()
        await broker.register("run_disconnect")
        iterator = broker.subscribe(run_id="run_disconnect")
        first_task = asyncio.create_task(anext(iterator))
        await broker.publish(
            run_id="run_disconnect",
            event_type="sdk.stream.started",
            payload={"persisted": False},
        )
        first = await first_task
        await iterator.aclose()
        await broker.publish(
            run_id="run_disconnect",
            event_type="model.text.delta",
            payload={"delta": "still-running", "persisted": False},
        )
        await broker.complete(run_id="run_disconnect", state="SUCCEEDED")
        return first, await broker.snapshot("run_disconnect")

    first, events = asyncio.run(scenario())
    assert first.event_type == "sdk.stream.started"
    assert [item.event_type for item in events] == [
        "sdk.stream.started",
        "model.text.delta",
        "sdk.stream.completed",
    ]


def test_control_api_exposes_authenticated_ephemeral_native_stream(tmp_path: Path) -> None:
    app = create_app(
        project_root=ROOT,
        product_db=tmp_path / "product.sqlite3",
        artifact_root=tmp_path / "artifacts",
        admin_key="admin-key-123456789",
    )
    store = app.state.product_store
    task = store.create_task(
        task_type="TEST",
        input_sha256="a" * 64,
        agent_definition_id="coding-agent",
        agent_definition_version="1.0.0",
    )
    run = store.create_run(task_id=task.task_id)

    async def scenario():
        broker = app.state.native_sdk_stream_broker
        await broker.publish(
            run_id=run.run_id,
            event_type="sdk.stream.started",
            payload={"persisted": False},
        )
        await broker.publish(
            run_id=run.run_id,
            event_type="model.text.delta",
            payload={"delta": "visible", "persisted": False},
        )
        await broker.complete(run_id=run.run_id, state="SUCCEEDED")
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            unauthorized = await client.get(f"/v1/runs/{run.run_id}/sdk-stream")
            assert unauthorized.status_code == 401
            response = await client.get(
                f"/v1/runs/{run.run_id}/sdk-stream",
                headers={"X-OKCanvas-Admin-Key": "admin-key-123456789"},
            )
        return response

    response = asyncio.run(scenario())
    assert response.status_code == 200
    assert response.headers["x-okcanvas-stream-durability"] == "ephemeral"
    assert "event: model.text.delta" in response.text
    assert '"delta":"visible"' in response.text
    assert "event: sdk.stream.completed" in response.text
