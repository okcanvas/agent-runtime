from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.agent.model.retry import (
    ModelRetryPolicyCatalog,
    ModelRetryPolicyError,
    build_sdk_model_retry_settings,
)

ROOT = Path(__file__).resolve().parents[1]


def test_zero_retry_policy_is_exact_and_runtime_bound() -> None:
    policy = ModelRetryPolicyCatalog(ROOT).resolve()
    assert policy.policy_id == "local-openai-zero-retry-v1"
    assert policy.runner_managed_max_retries == 0
    assert policy.provider_managed_max_retries == 0
    assert policy.retryable_categories == ()
    assert policy.conversation_locked_compatibility_retries is False
    assert policy.automatic_model_fallback is False
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(
        AgentDefinitionCatalog(ROOT).resolve("coding-agent")
    )
    assert binding.model_retry_policy["policy_sha256"] == policy.policy_sha256
    assert len(binding.model_retry_runtime_sha256) == 64


def test_zero_retry_policy_builds_explicit_sdk_never_policy(monkeypatch) -> None:
    captured: dict[str, object] = {}
    fake_agents = types.ModuleType("agents")

    class FakeModelRetrySettings:
        def __init__(self, **kwargs):
            captured["settings"] = kwargs
            self.max_retries = kwargs["max_retries"]
            self.policy = kwargs["policy"]

    class FakeRetryPolicies:
        @staticmethod
        def never():
            def policy(_context):
                return False

            captured["never_policy"] = policy
            return policy

    fake_agents.ModelRetrySettings = FakeModelRetrySettings
    fake_agents.retry_policies = FakeRetryPolicies()
    monkeypatch.setitem(sys.modules, "agents", fake_agents)
    policy = ModelRetryPolicyCatalog(ROOT).resolve()
    settings = build_sdk_model_retry_settings(policy)
    assert settings.max_retries == 0
    assert settings.policy(object()) is False
    assert captured["settings"] == {
        "max_retries": 0,
        "policy": captured["never_policy"],
    }


def test_retry_policy_drift_changes_runtime_binding(tmp_path: Path) -> None:
    import shutil

    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs", project / "specs")
    definition = AgentDefinitionCatalog(project).resolve("coding-agent")
    before = AgentRuntimeBindingCatalog(project).resolve(definition)
    path = project / "specs/runtime/model-retry-policy.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = "1.0.1-drift"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    after = AgentRuntimeBindingCatalog(project).resolve(definition)
    assert before.runtime_binding_sha256 != after.runtime_binding_sha256
    assert before.model_retry_policy["version"] == "1.0.0"
    assert after.model_retry_policy["version"] == "1.0.1-drift"
