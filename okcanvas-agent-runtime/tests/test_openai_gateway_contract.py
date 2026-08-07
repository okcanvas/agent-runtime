import asyncio
import sys
import types
from types import SimpleNamespace

from okcanvas_agent_runtime.core.config import RuntimeSettings
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult
from okcanvas_agent_runtime.adapters.openai.runtime.openai_gateway import OpenAIAgentsGateway
from okcanvas_agent_runtime.adapters.openai.runtime import sdk_readiness
import okcanvas_agent_runtime.adapters.openai.runtime.openai_gateway as gateway_module



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

def test_openai_gateway_uses_inspected_sdk_contract(monkeypatch) -> None:
    captured = {}
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"

    class FakeAgent:
        def __init__(self, **kwargs):
            captured["agent"] = kwargs

    class FakeRunConfig:
        def __init__(self, **kwargs):
            captured["run_config"] = kwargs

    class FakeRunner:
        @classmethod
        async def run(cls, agent, request, *, max_turns, run_config):
            captured["request"] = request
            captured["max_turns"] = max_turns
            captured["agent_instance"] = agent
            captured["run_config_instance"] = run_config
            output = CodingAgentResult(
                status=AgentStatus.PARTIAL,
                summary="Structured fake output",
                findings=[],
                unverified=["Live model execution"],
            )
            usage = SimpleNamespace(
                requests=1,
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                input_tokens_details=SimpleNamespace(cached_tokens=2),
                output_tokens_details=SimpleNamespace(reasoning_tokens=3),
            )

            class FakeResult:
                context_wrapper = SimpleNamespace(usage=usage)
                last_response_id = "resp_fake"

                def final_output_as(self, cls, raise_if_incorrect_type=False):
                    assert cls is CodingAgentResult
                    assert raise_if_incorrect_type is True
                    return output

            return FakeResult()

    def fake_set_key(value):
        captured["api_key"] = value

    fake_agents.Agent = FakeAgent
    fake_agents.RunConfig = FakeRunConfig
    _install_step052_model_contract(fake_agents)
    fake_agents.Runner = FakeRunner
    fake_agents.gen_trace_id = lambda: "trace_fake"
    fake_agents.set_default_openai_key = fake_set_key

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

    result = asyncio.run(
        OpenAIAgentsGateway().run(
            request="Analyze only this text",
            run_id="run_fixed",
            settings=RuntimeSettings(model="explicit-model", api_key="hidden-key"),
        )
    )

    assert captured["api_key"] == "hidden-key"
    assert captured["agent"]["model"] == "explicit-model"
    assert captured["agent"]["tools"] == []
    assert captured["agent"]["handoffs"] == []
    assert captured["agent"]["output_type"] is CodingAgentResult
    assert captured["max_turns"] == 1
    assert captured["run_config"]["trace_include_sensitive_data"] is False
    assert captured["run_config"]["group_id"] == "run_fixed"
    assert result.trace_id == "trace_fake"
    assert result.usage.total_tokens == 15
    assert result.usage.cached_input_tokens == 2
    assert result.usage.reasoning_tokens == 3
