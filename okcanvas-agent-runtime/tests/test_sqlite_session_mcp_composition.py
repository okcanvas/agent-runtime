from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.domain.sessions import SQLiteSessionMCPPolicyCatalog

ROOT = Path(__file__).resolve().parents[1]


def test_step050_definition_binding_and_policy_are_exact() -> None:
    definition = AgentDefinitionCatalog(ROOT).resolve("session-reference-research-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    policy = SQLiteSessionMCPPolicyCatalog(ROOT).resolve()

    assert definition.session_mode == "sqlite-v1"
    assert definition.mcp_servers == ("reference-catalog",)
    assert not definition.tools and not definition.handoffs
    assert not definition.agent_tools and not definition.guardrails
    assert definition.workspace_access == "none"
    assert binding.execution_path == "sqlite-session-native-mcp-execution-v1"
    assert binding.mcp_servers[0]["server_id"] == "reference-catalog"
    assert binding.session_policy is not None
    assert binding.session_policy["sqlite_session"]["policy_id"] == "local-strict-encrypted-compacted-sqlite-session-v1"
    assert binding.session_policy["mcp_composition"]["policy_id"] == "local-sqlite-session-native-mcp-v1"
    assert binding.session_runtime_sha256
    assert policy.max_mcp_servers_per_turn == 1
    assert policy.read_only_required is True
    assert policy.local_stdio_only is True
    assert policy.manager_scope == "per-turn"
    assert policy.hold_turn_lease_until_manager_cleanup is True
    assert policy.rollback_failed_turn is True
    assert policy.history_copy_to_product is False
    assert policy.mcp_content_copy_to_product is False


def test_step050_rejects_multiple_or_mixed_mcp_session_graph(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "specs", tmp_path / "specs")
    definition_path = tmp_path / "specs/agents/session-reference-research-agent/definition.json"
    payload = json.loads(definition_path.read_text())
    payload["mcp_servers"] = ["reference-catalog", "reference-catalog"]
    definition_path.write_text(json.dumps(payload, indent=2) + "\n")
    with pytest.raises(Exception):
        AgentDefinitionCatalog(tmp_path).resolve("session-reference-research-agent")

    payload["mcp_servers"] = ["reference-catalog"]
    payload["agent_tools"] = ["agent-tool-specialist-agent"]
    definition_path.write_text(json.dumps(payload, indent=2) + "\n")
    with pytest.raises(Exception):
        AgentDefinitionCatalog(tmp_path).resolve("session-reference-research-agent")


def test_step050_binding_changes_when_composition_policy_changes(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "specs", tmp_path / "specs")
    original = AgentDefinitionCatalog(tmp_path).resolve("session-reference-research-agent")
    before = AgentRuntimeBindingCatalog(tmp_path).resolve(original).runtime_binding_sha256
    policy_path = tmp_path / "specs/runtime/sqlite-session-mcp-policy.json"
    payload = json.loads(policy_path.read_text())
    payload["version"] = "1.0.1"
    policy_path.write_text(json.dumps(payload, indent=2) + "\n")
    after = AgentRuntimeBindingCatalog(tmp_path).resolve(original).runtime_binding_sha256
    assert before != after
