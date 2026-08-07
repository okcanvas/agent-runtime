from pathlib import Path

from okcanvas_agent_runtime.compatibility.source_contracts import legacy_source_contract
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts.package_source import DEFAULT_OUTPUT

ROOT = Path(__file__).resolve().parents[1]


def test_step043_runtime_and_session_assets_exist() -> None:
    required = [
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/sessions/models.py"),
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/sessions/policy.py"),
        legacy_source_contract(ROOT, "okcanvas_agent_runtime/sessions/service.py"),
        ROOT / "specs/runtime/sqlite-session-policy.json",
        ROOT / "specs/agents/session-continuity-agent/definition.json",
        ROOT / "specs/evaluations/sqlite-session-v1/case.json",
        ROOT / "scripts/run_step043_acceptance.py",
        ROOT / "sh_run_step043_acceptance.cmd",
        ROOT / "docs/plans/STEP045_INTEGRATED_WALKING_SKELETON_ACCEPTANCE.md",
        ROOT / "docs/reference/STEP043_SQLITE_SESSION_RUNTIME_CODE_AUDIT.md",
        ROOT / "docs/evidence/STEP043_ACCEPTANCE.json",
        ROOT / "docs/evidence/STEP043_VALIDATION.txt",
        ROOT / "docs/evidence/STEP042_WINDOWS_LIVE_ACCEPTANCE_SUMMARY.json",
    ]
    assert all(path.is_file() for path in required)


def test_step043_baseline_identifiers_are_current() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.agent_as_tool_windows_live_accepted is True
    assert info.generic_agent_sessions_enabled is True
    assert info.sqlite_session_runtime_implemented is True
    assert info.sqlite_session_backend == "installed-sdk-sqlite-session"
    assert info.sqlite_session_product_catalog_implemented is True
    assert info.sqlite_session_max_active_turns == 1
    assert info.sqlite_session_history_copied_to_product_events is False
    assert info.sqlite_session_history_encrypted is True
    assert info.sqlite_session_compaction_enabled is True
    assert info.sqlite_session_deterministic_accepted is True
    assert info.sqlite_session_windows_live_accepted is True


def test_step043_session_contract_is_explicit() -> None:
    service = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/sessions/service.py")).read_text(encoding="utf-8")
    execution = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/service.py")).read_text(encoding="utf-8")
    gateway = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/execution/openai_gateway.py")).read_text(encoding="utf-8")
    policy = (ROOT / "specs/runtime/sqlite-session-policy.json").read_text(encoding="utf-8")
    runner = (legacy_source_contract(ROOT, "okcanvas_agent_runtime/interactive_runner/assets/runner.js")).read_text(encoding="utf-8")
    packaging = (ROOT / "scripts/package_source.py").read_text(encoding="utf-8")
    assert "active_run_id" in service
    assert "session.turn.started" in execution
    assert "session.turn.completed" in execution
    assert "session_runtime.sdk_session" in gateway
    assert '"max_active_turns": 1' in policy
    assert '"compaction_enabled": true' in policy
    assert '"encryption_enabled": true' in policy
    assert "/v1/sessions" in runner and "session_id" in runner
    assert DEFAULT_OUTPUT.name in packaging
