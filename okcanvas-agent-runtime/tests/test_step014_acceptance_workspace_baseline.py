from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo


def test_step014_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.acceptance_workspace_manager_implemented is True
    assert info.acceptance_workspace_compact_evidence_export_implemented is True
    assert info.acceptance_workspace_failure_preservation_implemented is True
    assert info.acceptance_workspace_bounded_cleanup_retry_implemented is True
    assert info.acceptance_workspace_deterministic_accepted is True
    assert info.acceptance_workspace_windows_live_accepted is True
