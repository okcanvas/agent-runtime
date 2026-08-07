from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.agent.model.reasoning_evidence import (
    ReasoningEvidencePolicyCatalog,
    ReasoningEvidencePolicyError,
    build_sdk_reasoning_model_settings_kwargs,
    count_reasoning_items,
)

ROOT = Path(__file__).resolve().parents[1]


def test_reasoning_evidence_policy_is_exact_and_runtime_bound() -> None:
    policy = ReasoningEvidencePolicyCatalog(ROOT).resolve()
    assert policy.policy_id == "local-openai-reasoning-evidence-minimization-v1"
    assert policy.reasoning_summary_requested is False
    assert policy.response_include == ()
    assert policy.persist_reasoning_content is False
    assert policy.persist_reasoning_summary is False
    assert policy.persist_reasoning_item_ids is False
    assert policy.persist_reasoning_provider_data is False
    assert policy.persist_reasoning_token_count is True
    assert build_sdk_reasoning_model_settings_kwargs(policy) == {
        "reasoning": None,
        "response_include": [],
    }
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(
        AgentDefinitionCatalog(ROOT).resolve("coding-agent")
    )
    assert binding.reasoning_evidence_policy["policy_sha256"] == policy.policy_sha256
    assert len(binding.reasoning_evidence_runtime_sha256) == 64


def test_reasoning_item_counter_does_not_read_sensitive_fields() -> None:
    class ExplodingReasoningItem:
        type = "reasoning"

        def __getattribute__(self, name: str):
            if name in {"summary", "content", "encrypted_content", "id", "provider_data"}:
                raise AssertionError(f"sensitive field read: {name}")
            return object.__getattribute__(self, name)

    class MessageItem:
        type = "message"

    response = type("Response", (), {"output": [ExplodingReasoningItem(), MessageItem()]})()
    assert count_reasoning_items(response) == 1


def test_reasoning_evidence_policy_drift_changes_runtime_binding(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs", project / "specs")
    definition = AgentDefinitionCatalog(project).resolve("coding-agent")
    before = AgentRuntimeBindingCatalog(project).resolve(definition)
    path = project / "specs/runtime/reasoning-evidence-policy.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = "1.0.1-drift"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    after = AgentRuntimeBindingCatalog(project).resolve(definition)
    assert before.runtime_binding_sha256 != after.runtime_binding_sha256
    assert before.reasoning_evidence_policy["version"] == "1.0.0"
    assert after.reasoning_evidence_policy["version"] == "1.0.1-drift"


def test_reasoning_evidence_policy_rejects_content_persistence(tmp_path: Path) -> None:
    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs", project / "specs")
    path = project / "specs/runtime/reasoning-evidence-policy.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["persist_reasoning_content"] = True
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ReasoningEvidencePolicyError):
        ReasoningEvidencePolicyCatalog(project).resolve()
