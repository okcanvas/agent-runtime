from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path

import pytest

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.agent.model.retry import ModelRetryPolicyCatalog
from okcanvas_agent_runtime.agent.model.routing import (
    ModelRouteDeniedError,
    ModelRoutingPolicyCatalog,
    PinnedOpenAIResponsesProvider,
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


def test_model_routing_policy_is_exact_and_runtime_bound() -> None:
    policy = ModelRoutingPolicyCatalog(ROOT).resolve()
    assert policy.route_id == "openai:responses:http"
    assert policy.provider_adapter == "agents.models.openai_provider.OpenAIProvider"
    assert policy.base_url == "https://api.openai.com/v1"
    assert policy.automatic_fallback is False
    assert policy.fallback_model_ids == ()
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(
        AgentDefinitionCatalog(ROOT).resolve("coding-agent")
    )
    assert binding.model_routing_policy["policy_sha256"] == policy.policy_sha256
    assert len(binding.model_provider_runtime_sha256) == 64


def test_model_routing_rejects_provider_prefixed_model() -> None:
    catalog = ModelRoutingPolicyCatalog(ROOT)
    with pytest.raises(ModelRouteDeniedError):
        catalog.resolve_model("litellm/anthropic/claude")
    assert catalog.resolve_model("deterministic-test-model").model_id == "deterministic-test-model"


def test_pinned_provider_forces_exact_sdk_configuration(monkeypatch) -> None:
    captured: dict[str, object] = {}
    fake_agents = types.ModuleType("agents")
    fake_openai = types.ModuleType("openai")

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

    class FakeProvider:
        def __init__(self, **kwargs):
            captured["kwargs"] = kwargs
            self.closed = False

        def get_model(self, model_name):
            captured["model"] = model_name
            return model_name

        async def aclose(self):
            self.closed = True
            captured["closed"] = True

    fake_agents.OpenAIProvider = FakeProvider
    fake_openai.AsyncOpenAI = FakeAsyncOpenAI
    class _Step052FakeModelRetrySettings:
        def __init__(self, **kwargs):
            self.max_retries = kwargs.get("max_retries")
            self.policy = kwargs.get("policy")

    fake_agents.ModelRetrySettings = _Step052FakeModelRetrySettings
    fake_agents.retry_policies = types.SimpleNamespace(
        never=lambda: (lambda _context: False)
    )

    monkeypatch.setitem(sys.modules, "agents", fake_agents)
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    route = ModelRoutingPolicyCatalog(ROOT).resolve_model("deterministic-test-model")
    retry_policy = ModelRetryPolicyCatalog(ROOT).resolve()
    provider = PinnedOpenAIResponsesProvider(
        route=route, retry_policy=retry_policy, api_key="hidden"
    )
    assert provider.get_model("deterministic-test-model") == "deterministic-test-model"
    asyncio.run(provider.aclose())
    assert captured["client_kwargs"] == {
        "api_key": "hidden",
        "base_url": "https://api.openai.com/v1",
        "max_retries": 0,
    }
    assert captured["kwargs"] == {
        "openai_client": captured["kwargs"]["openai_client"],
        "use_responses": True,
        "use_responses_websocket": False,
        "strict_feature_validation": True,
    }
    assert captured["closed"] is True


def test_model_routing_policy_drift_changes_runtime_binding(tmp_path: Path) -> None:
    import shutil

    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs", project / "specs")
    definition = AgentDefinitionCatalog(project).resolve("coding-agent")
    before = AgentRuntimeBindingCatalog(project).resolve(definition)
    path = project / "specs/runtime/model-routing-policy.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = "1.0.1"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    after = AgentRuntimeBindingCatalog(project).resolve(definition)
    assert before.runtime_binding_sha256 != after.runtime_binding_sha256
