from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.agent.subagents.agent_tools import (
    AgentToolPolicyCatalog,
    validate_sqlite_session_agent_tool_definitions,
)
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.domain.sessions import SQLiteSessionAgentToolPolicyCatalog

ROOT = Path(__file__).resolve().parents[1]


def test_step049_definition_and_binding_are_exact() -> None:
    catalog = AgentDefinitionCatalog(ROOT)
    root = catalog.resolve("session-agent-tool-manager-agent")
    child = catalog.resolve("agent-tool-specialist-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(root)

    assert root.session_mode == "sqlite-v1"
    assert root.agent_tools == ("agent-tool-specialist-agent",)
    assert not root.tools and not root.mcp_servers and not root.handoffs and not root.guardrails
    assert child.session_mode == "disabled"
    assert not child.tools and not child.mcp_servers and not child.handoffs and not child.agent_tools
    assert binding.execution_path == "sqlite-session-native-agent-tool-execution-v1"
    assert binding.session_policy is not None
    assert binding.session_policy["sqlite_session"]["policy_id"] == "local-strict-encrypted-compacted-sqlite-session-v1"
    assert binding.session_policy["agent_tool_composition"]["policy_id"] == "local-sqlite-session-native-agent-tool-v1"
    assert binding.agent_tool_policy is not None
    assert binding.agent_tool_policy["policy_id"] == "default-agent-as-tool-policy"
    assert binding.session_runtime_sha256
    assert binding.agent_tool_runtime_sha256
    assert binding.child_agents[0]["child_agent_id"] == "agent-tool-specialist-agent"


def test_step049_composition_policy_is_closed() -> None:
    policy = SQLiteSessionAgentToolPolicyCatalog(ROOT).resolve()
    assert policy.max_agent_tool_calls_per_turn == 1
    assert policy.max_depth == 1
    assert policy.root_session_only is True
    assert policy.child_session_mode == "disabled"
    assert policy.hold_turn_lease_until_parent_completion is True
    assert policy.commit_completed_turn is True
    assert policy.rollback_failed_turn is True
    assert policy.history_copy_to_product is False
    assert policy.workspace_access == "none"


def test_step049_validator_accepts_only_session_root_and_terminal_child() -> None:
    catalog = AgentDefinitionCatalog(ROOT)
    root = catalog.resolve("session-agent-tool-manager-agent")
    child = catalog.resolve("agent-tool-specialist-agent")
    policy = AgentToolPolicyCatalog(ROOT).resolve()
    validate_sqlite_session_agent_tool_definitions(parent=root, child=child, policy=policy)

    ordinary = catalog.resolve("agent-tool-manager-agent")
    with pytest.raises(Exception):
        validate_sqlite_session_agent_tool_definitions(parent=ordinary, child=child, policy=policy)


def test_step049_rejects_mixed_capability_or_session_child(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "specs", tmp_path / "specs")
    root_path = tmp_path / "specs/agents/session-agent-tool-manager-agent/definition.json"
    root_payload = json.loads(root_path.read_text())
    root_payload["mcp_servers"] = ["reference-catalog"]
    root_path.write_text(json.dumps(root_payload, indent=2) + "\n")
    with pytest.raises(Exception):
        AgentDefinitionCatalog(tmp_path).resolve("session-agent-tool-manager-agent")

    root_payload["mcp_servers"] = []
    root_path.write_text(json.dumps(root_payload, indent=2) + "\n")
    child_path = tmp_path / "specs/agents/agent-tool-specialist-agent/definition.json"
    child_payload = json.loads(child_path.read_text())
    child_payload["session_mode"] = "sqlite-v1"
    child_path.write_text(json.dumps(child_payload, indent=2) + "\n")
    child = AgentDefinitionCatalog(tmp_path).resolve("agent-tool-specialist-agent")
    root = AgentDefinitionCatalog(tmp_path).resolve("session-agent-tool-manager-agent")
    with pytest.raises(Exception):
        validate_sqlite_session_agent_tool_definitions(
            parent=root,
            child=child,
            policy=AgentToolPolicyCatalog(tmp_path).resolve(),
        )
