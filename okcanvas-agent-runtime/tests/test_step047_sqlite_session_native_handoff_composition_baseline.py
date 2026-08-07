from __future__ import annotations

from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step047_assets_exist() -> None:
    required = [
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/sessions/handoff_policy.py"),
        ROOT / "specs/runtime/sqlite-session-handoff-policy.json",
        ROOT / "specs/agents/session-handoff-triage-agent/definition.json",
        ROOT / "specs/evaluations/sqlite-session-native-handoff-v1/case.json",
        ROOT / "scripts/run_step047_acceptance.py",
        ROOT / "sh_run_step047_acceptance.cmd",
        ROOT / "docs/plans/STEP047_SQLITE_SESSION_NATIVE_HANDOFF_COMPOSITION_V1.md",
        ROOT / "docs/reference/STEP047_SQLITE_SESSION_NATIVE_HANDOFF_COMPOSITION_CODE_AUDIT.md",
    ]
    assert all(path.is_file() for path in required)


def test_step047_runtime_info_declares_exact_boundary() -> None:
    info = RuntimeInfo()
    assert info.sqlite_session_approval_windows_live_accepted is True
    assert info.sqlite_session_handoff_composition_implemented is True
    assert info.sqlite_session_handoff_max_per_turn == 1
    assert info.sqlite_session_handoff_max_depth == 1
    assert info.sqlite_session_handoff_same_sdk_session_required is True
    assert info.sqlite_session_handoff_turn_lease_held_until_child_completion is True
    assert info.sqlite_session_handoff_failed_turn_rolled_back is True
    assert info.sqlite_session_handoff_raw_history_persisted_in_product_events is False
    assert info.sqlite_session_handoff_deterministic_accepted is True
    assert info.sqlite_session_handoff_windows_live_accepted is True


def test_step047_source_contract_is_explicit() -> None:
    gateway = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text()
    execution = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/service.py")).read_text()
    binding = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/runtime_binding.py")).read_text()
    assert "validate_sqlite_session_handoff_definitions" in gateway
    assert '"sdk_session_history_active": definition.session_mode == "sqlite-v1"' in gateway
    assert "rollback_to_item_count" in execution
    assert 'execution_path = "sqlite-session-native-handoff-execution-v1"' in binding
