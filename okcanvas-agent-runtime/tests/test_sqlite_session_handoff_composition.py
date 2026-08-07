from __future__ import annotations

import json
from pathlib import Path

import pytest

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.agent.subagents.handoffs import (
    NativeHandoffPolicyCatalog,
    validate_sqlite_session_handoff_definitions,
)
from okcanvas_agent_runtime.domain.sessions import SQLiteSessionHandoffPolicyCatalog

ROOT = Path(__file__).resolve().parents[1]


def test_step047_definition_and_binding_are_exact() -> None:
    definition = AgentDefinitionCatalog(ROOT).resolve("session-handoff-triage-agent")
    child = AgentDefinitionCatalog(ROOT).resolve("handoff-specialist-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)

    assert definition.session_mode == "sqlite-v1"
    assert definition.handoffs == ("handoff-specialist-agent",)
    assert not definition.tools
    assert not definition.mcp_servers
    assert not definition.agent_tools
    assert not definition.guardrails
    assert child.session_mode == "disabled"
    assert binding.execution_path == "sqlite-session-native-handoff-execution-v1"
    assert binding.session_policy is not None
    assert binding.session_policy["sqlite_session"]["policy_id"] == "local-strict-encrypted-compacted-sqlite-session-v1"
    assert binding.session_policy["handoff_composition"]["policy_id"] == "local-sqlite-session-native-handoff-v1"
    assert binding.handoff_policy is not None
    assert binding.handoff_policy["policy_id"] == "native-handoff-v1"
    assert binding.session_runtime_sha256
    assert binding.handoff_runtime_sha256
    assert binding.child_agents[0]["child_agent_id"] == "handoff-specialist-agent"


def test_step047_composition_policy_is_closed() -> None:
    policy = SQLiteSessionHandoffPolicyCatalog(ROOT).resolve()
    assert policy.max_handoffs_per_turn == 1
    assert policy.max_depth == 1
    assert policy.require_same_sdk_session is True
    assert policy.hold_turn_lease_until_child_completion is True
    assert policy.commit_completed_turn is True
    assert policy.rollback_failed_turn is True
    assert policy.history_copy_to_product is False
    assert policy.workspace_access == "none"


def test_step047_native_handoff_validator_accepts_only_session_root() -> None:
    catalog = AgentDefinitionCatalog(ROOT)
    root = catalog.resolve("session-handoff-triage-agent")
    child = catalog.resolve("handoff-specialist-agent")
    policy = NativeHandoffPolicyCatalog(ROOT).resolve()
    validate_sqlite_session_handoff_definitions(parent=root, child=child, policy=policy)

    ordinary = catalog.resolve("handoff-triage-agent")
    with pytest.raises(Exception):
        validate_sqlite_session_handoff_definitions(parent=ordinary, child=child, policy=policy)


def test_step047_policy_file_has_no_implicit_capability() -> None:
    payload = json.loads((ROOT / "specs/runtime/sqlite-session-handoff-policy.json").read_text())
    assert payload == {
        "schema_version": "okcanvas-sqlite-session-handoff-policy-v1",
        "policy_id": "local-sqlite-session-native-handoff-v1",
        "version": "1.0.0",
        "session_mode": "sqlite-v1",
        "handoff_policy_id": "native-handoff-v1",
        "max_handoffs_per_turn": 1,
        "max_depth": 1,
        "require_same_sdk_session": True,
        "hold_turn_lease_until_child_completion": True,
        "commit_completed_turn": True,
        "rollback_failed_turn": True,
        "history_copy_to_product": False,
        "workspace_access": "none",
    }
