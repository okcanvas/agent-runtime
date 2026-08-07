from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo


def test_step013_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.evaluation_sqlite_windows_cleanup_live_accepted is True
    assert info.evaluation_suite_service_implemented is True
    assert info.evaluation_suite_catalog_implemented is True
    assert info.evaluation_suite_bounded_batch_implemented is True
    assert info.evaluation_suite_atomic_persistence_implemented is True
    assert info.evaluation_baseline_explicit_only is True
    assert info.evaluation_baseline_comparison_implemented is True
    assert info.evaluation_suite_control_api_implemented is True
    assert info.evaluation_suite_service_accepted is True
