from __future__ import annotations

from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step049_assets_exist() -> None:
    required = [
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/sessions/agent_tool_policy.py"),
        ROOT / "specs/runtime/sqlite-session-agent-tool-policy.json",
        ROOT / "specs/agents/session-agent-tool-manager-agent/definition.json",
        ROOT / "specs/evaluations/sqlite-session-native-agent-tool-v1/case.json",
        ROOT / "scripts/run_step049_acceptance.py",
        ROOT / "sh_run_step049_acceptance.cmd",
        ROOT / "docs/plans/STEP049_SQLITE_SESSION_NATIVE_AGENT_AS_TOOL_COMPOSITION_V1.md",
        ROOT / "docs/reference/STEP049_SQLITE_SESSION_NATIVE_AGENT_AS_TOOL_COMPOSITION_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP048_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
    ]
    assert all(path.is_file() for path in required)


def test_step049_runtime_info_declares_exact_boundary() -> None:
    info = RuntimeInfo()
    assert info.version == "2.77.0"
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.sqlite_session_guardrail_windows_live_accepted is True
    assert info.sqlite_session_agent_tool_composition_implemented is True
    assert info.sqlite_session_agent_tool_max_per_turn == 1
    assert info.sqlite_session_agent_tool_max_depth == 1
    assert info.sqlite_session_agent_tool_root_session_only is True
    assert info.sqlite_session_agent_tool_child_session_enabled is False
    assert info.sqlite_session_agent_tool_failed_turn_rolled_back is True
    assert info.sqlite_session_agent_tool_raw_history_persisted_in_product_events is False
    assert info.sqlite_session_agent_tool_deterministic_accepted is True
    assert info.sqlite_session_agent_tool_windows_live_accepted is True


def test_step049_source_contract_is_explicit() -> None:
    gateway = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text()
    execution = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/service.py")).read_text()
    binding = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/runtime_binding.py")).read_text()
    sdk_tool = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/agent_tools/runtime.py")).read_text()
    acceptance = (ROOT / "scripts/run_step049_acceptance.py").read_text()
    assert "validate_sqlite_session_agent_tool_definitions" in gateway
    assert "definition.agent_tools" in execution and "rollback_to_item_count" in execution
    assert 'execution_path = "sqlite-session-native-agent-tool-execution-v1"' in binding
    assert "SQLiteSessionAgentToolPolicyCatalog" in binding
    assert "session=None" in sdk_tool
    assert "workspace.finalize(report)" in acceptance
    assert "history_item_count = _history_count(runtime.history_db, session_id)" in acceptance
    assert "connection.close()" in acceptance
