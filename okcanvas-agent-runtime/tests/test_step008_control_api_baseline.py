from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step008_runtime_capabilities_are_explicit() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.control_api_implemented is True
    assert info.control_api_mode == "local-admin-development-and-multi-user-service"
    assert info.control_api_network_live_accepted is False
    assert info.persisted_sse_implemented is True
    assert info.persisted_sse_cursor_resume_accepted is True
    assert info.active_run_restart_recovery_implemented is False
    assert info.distributed_worker_lease_implemented is False
    assert info.direct_reference_import_forbidden is True


def test_step008_records_exact_reference_paths_and_decisions() -> None:
    plan = (ROOT / "docs/plans/STEP008_CONTROL_API_AND_PERSISTED_SSE.md").read_text(
        encoding="utf-8"
    )
    for path in [
        "src/agents/stream_events.py",
        "src/agents/run_internal/streaming.py",
        "src/api/utils/agent_router.py",
        "python-backend/server.py",
    ]:
        assert path in plan
    assert "ADAPT" in plan
    assert "REJECT" in plan
    assert "DEFER" in plan


def test_reference_is_never_a_runtime_import_dependency() -> None:
    constitution = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Never import executable application code from `/reference`" in constitution
    assert (ROOT / "scripts/verify_no_reference_imports.py").is_file()
