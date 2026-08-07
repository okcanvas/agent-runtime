from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo


def test_step014_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.acceptance_workspace_manager_implemented is True
    assert info.acceptance_workspace_compact_evidence_export_implemented is True
    assert info.acceptance_workspace_failure_preservation_implemented is True
    assert info.acceptance_workspace_bounded_cleanup_retry_implemented is True
    assert info.acceptance_workspace_deterministic_accepted is True
    assert info.acceptance_workspace_windows_live_accepted is True
