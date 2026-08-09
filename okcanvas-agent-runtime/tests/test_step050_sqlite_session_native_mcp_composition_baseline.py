from __future__ import annotations

from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step050_assets_exist() -> None:
    required = [
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/sessions/mcp_policy.py"),
        ROOT / "specs/runtime/sqlite-session-mcp-policy.json",
        ROOT / "specs/agents/session-reference-research-agent/definition.json",
        ROOT / "specs/evaluations/sqlite-session-native-mcp-v1/case.json",
        ROOT / "scripts/run_step050_acceptance.py",
        ROOT / "sh_run_step050_acceptance.cmd",
        ROOT / "docs/plans/STEP059_BOUNDED_PROJECT_READONLY_CODING_WORKFLOW.md",
        ROOT / "docs/reference/STEP050_SQLITE_SESSION_NATIVE_MCP_COMPOSITION_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP049_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
    ]
    assert all(path.is_file() for path in required)


def test_step050_runtime_info_declares_exact_boundary() -> None:
    info = RuntimeInfo()
    assert info.version == "2.77.0"
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.sqlite_session_agent_tool_windows_live_accepted is True
    assert info.sqlite_session_mcp_composition_implemented is True
    assert info.sqlite_session_mcp_max_servers_per_turn == 1
    assert info.sqlite_session_mcp_read_only_local_stdio_only is True
    assert info.sqlite_session_mcp_manager_scope == "per-turn"
    assert info.sqlite_session_mcp_failed_turn_rolled_back is True
    assert info.sqlite_session_mcp_raw_content_persisted_in_product_events is False
    assert info.sqlite_session_mcp_deterministic_accepted is True
    assert info.sqlite_session_mcp_windows_live_accepted is True


def test_step050_source_contract_is_explicit() -> None:
    gateway = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text()
    execution = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/service.py")).read_text()
    binding = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/runtime_binding.py")).read_text()
    acceptance = (ROOT / "scripts/run_step050_acceptance.py").read_text()
    assert "session_mcp_mode" in gateway
    assert "definition.mcp_servers" in execution and "rollback_to_item_count" in execution
    assert 'execution_path = "sqlite-session-native-mcp-execution-v1"' in binding
    assert "SQLiteSessionMCPPolicyCatalog" in binding
    assert "manager_exit_2" in acceptance and "rollback_pop_2" in acceptance
    assert "workspace.finalize(report)" in acceptance
