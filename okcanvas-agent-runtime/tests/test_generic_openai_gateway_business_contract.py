from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import StoreReplenishmentReviewResult
from okcanvas_agent_runtime.application.execution import OpenAIGenericAgentGateway
from okcanvas_agent_runtime.application.execution import openai_gateway as gateway_module
from okcanvas_agent_runtime.adapters.openai.runtime import sdk_readiness


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
EXPECTED = json.loads(
    (
        ROOT
        / "specs"
        / "business-cases"
        / "store-replenishment-review"
        / "case001-shortage"
        / "expected.json"
    ).read_text(encoding="utf-8")
)


def test_openai_gateway_resolves_business_output_type(monkeypatch) -> None:
    captured: dict[str, object] = {"events": []}
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
            await hooks.on_agent_start(SimpleNamespace(), agent)
            await hooks.on_llm_start(SimpleNamespace(), agent, agent.instructions, [{"role": "user"}])
            response = SimpleNamespace(response_id="resp_business", request_id="req", output=[1])
            await hooks.on_llm_end(SimpleNamespace(), agent, response)
            output = StoreReplenishmentReviewResult.model_validate(EXPECTED)
            await hooks.on_agent_end(SimpleNamespace(), agent, output)
            usage = SimpleNamespace(
                requests=1,
                input_tokens=20,
                output_tokens=30,
                total_tokens=50,
                input_tokens_details=SimpleNamespace(cached_tokens=0),
                output_tokens_details=SimpleNamespace(reasoning_tokens=0),
            )

            class Result:
                context_wrapper = SimpleNamespace(usage=usage)
                last_response_id = "resp_business"

                def final_output_as(self, output_type, raise_if_incorrect_type=False):
                    assert output_type is StoreReplenishmentReviewResult
                    assert raise_if_incorrect_type is True
                    return output

            return Result()

    fake_agents.Agent = FakeAgent
    fake_agents.RunConfig = FakeRunConfig
    _install_step052_model_contract(fake_agents)
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.gen_trace_id = lambda: "trace_business"
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
            definition=AgentDefinitionCatalog(ROOT).resolve(
                "store-replenishment-review-agent"
            ),
            request='{"snapshot_id":"case001-shortage"}',
            run_id="run_business",
            settings=RuntimeSettings(model="explicit-model", api_key="hidden-key"),
            lifecycle_sink=sink,
        )
    )
    assert captured["agent"]["output_type"] is StoreReplenishmentReviewResult
    assert result.output.total_reorder_units == 19
    assert result.trace_id == "trace_business"


def test_openai_gateway_recovers_invalid_business_final_output(monkeypatch) -> None:
    captured: dict[str, object] = {"events": []}
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
        ):
            assert error_handlers is not None
            assert "invalid_final_output" in error_handlers
            await hooks.on_agent_start(SimpleNamespace(), agent)
            await hooks.on_llm_start(SimpleNamespace(), agent, agent.instructions, [{"role": "user"}])
            response = SimpleNamespace(response_id="resp_invalid", request_id="req", output=[1])
            await hooks.on_llm_end(SimpleNamespace(), agent, response)
            output = error_handlers["invalid_final_output"](SimpleNamespace())
            await hooks.on_agent_end(SimpleNamespace(), agent, output)
            usage = SimpleNamespace(
                requests=1,
                input_tokens=20,
                output_tokens=30,
                total_tokens=50,
                input_tokens_details=SimpleNamespace(cached_tokens=0),
                output_tokens_details=SimpleNamespace(reasoning_tokens=0),
            )

            class Result:
                context_wrapper = SimpleNamespace(usage=usage)
                last_response_id = "resp_invalid"

                def final_output_as(self, output_type, raise_if_incorrect_type=False):
                    assert output_type is StoreReplenishmentReviewResult
                    return output

            return Result()

    fake_agents.Agent = FakeAgent
    fake_agents.RunConfig = FakeRunConfig
    _install_step052_model_contract(fake_agents)
    fake_agents.RunHooks = FakeRunHooks
    fake_agents.Runner = FakeRunner
    fake_agents.gen_trace_id = lambda: "trace_recovered"
    fake_agents.set_default_openai_key = lambda value: captured.setdefault("api_key", value)
    monkeypatch.setitem(sys.modules, "agents", fake_agents)
    monkeypatch.setattr(sdk_readiness.importlib.metadata, "version", lambda name: "0.19.0")
    monkeypatch.setattr(gateway_module.importlib.metadata, "version", lambda name: "0.19.0")

    async def sink(event):
        captured["events"].append(event)

    request = json.dumps(
        {
            "snapshot_id": "case001-shortage",
            "safety_stock_units": 5,
            "items": [
                {
                    "sku": "desk-lamp",
                    "available_units": 12,
                    "forecast_units": 18,
                    "inbound_units": 4,
                },
                {
                    "sku": "ergonomic-keyboard",
                    "available_units": 7,
                    "forecast_units": 16,
                    "inbound_units": 2,
                },
                {
                    "sku": "usb-c-dock",
                    "available_units": 22,
                    "forecast_units": 14,
                    "inbound_units": 0,
                },
            ],
        },
        separators=(",", ":"),
    )
    result = asyncio.run(
        OpenAIGenericAgentGateway().run(
            definition=AgentDefinitionCatalog(ROOT).resolve(
                "store-replenishment-review-agent"
            ),
            request=request,
            run_id="run_recovered",
            settings=RuntimeSettings(model="explicit-model", api_key="hidden-key"),
            lifecycle_sink=sink,
        )
    )
    assert result.output.total_reorder_units == 19
    assert [item.reorder_units for item in result.output.recommendations] == [12, 7, 0]
    assert any(event.event_type == "agent.output.recovered" for event in captured["events"])
