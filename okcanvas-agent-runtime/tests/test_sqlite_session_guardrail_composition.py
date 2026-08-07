from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.domain.sessions import SQLiteSessionGuardrailPolicyCatalog

ROOT = Path(__file__).resolve().parents[1]


def test_step048_definition_and_binding_are_exact() -> None:
    definition = AgentDefinitionCatalog(ROOT).resolve("session-guardrail-language-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)

    assert definition.session_mode == "sqlite-v1"
    assert definition.guardrails == ("block-input-marker", "block-output-marker")
    assert not definition.tools
    assert not definition.mcp_servers
    assert not definition.handoffs
    assert not definition.agent_tools
    assert definition.workspace_access == "none"
    assert binding.execution_path == "sqlite-session-native-guardrail-execution-v1"
    assert binding.session_policy is not None
    assert binding.session_policy["sqlite_session"]["policy_id"] == "local-strict-encrypted-compacted-sqlite-session-v1"
    composition = binding.session_policy["guardrail_composition"]
    assert composition["policy_id"] == "local-sqlite-session-native-guardrail-v1"
    assert composition["allowed_guardrail_kinds"] == ["INPUT", "OUTPUT"]
    assert binding.guardrail_runtime_sha256
    assert binding.session_runtime_sha256
    assert [item["kind"] for item in binding.guardrails] == ["INPUT", "OUTPUT"]


def test_step048_composition_policy_is_closed() -> None:
    policy = SQLiteSessionGuardrailPolicyCatalog(ROOT).resolve()
    assert policy.allowed_guardrail_kinds == ("INPUT", "OUTPUT")
    assert policy.max_per_kind == 1
    assert policy.commit_successful_turn is True
    assert policy.rollback_tripped_turn is True
    assert policy.history_copy_to_product is False
    assert policy.workspace_access == "none"


def test_step048_policy_file_has_no_implicit_capability() -> None:
    payload = json.loads(
        (ROOT / "specs/runtime/sqlite-session-guardrail-policy.json").read_text()
    )
    assert payload == {
        "schema_version": "okcanvas-sqlite-session-guardrail-policy-v1",
        "policy_id": "local-sqlite-session-native-guardrail-v1",
        "version": "1.0.0",
        "session_mode": "sqlite-v1",
        "allowed_guardrail_kinds": ["INPUT", "OUTPUT"],
        "max_per_kind": 1,
        "commit_successful_turn": True,
        "rollback_tripped_turn": True,
        "history_copy_to_product": False,
        "workspace_access": "none",
    }


def test_step048_rejects_tool_guardrail_or_tool_composition(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "specs", tmp_path / "specs")
    path = tmp_path / "specs/agents/session-guardrail-language-agent/definition.json"
    payload = json.loads(path.read_text())
    payload["tools"] = ["local_text_fingerprint"]
    payload["guardrails"] = ["deny-local-text-tool-input"]
    path.write_text(json.dumps(payload, indent=2) + "\n")

    with pytest.raises(Exception):
        AgentDefinitionCatalog(tmp_path).resolve("session-guardrail-language-agent")
