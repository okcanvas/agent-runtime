from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo


def test_step019_runtime_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.governed_execution_claim_restart_recovery_implemented is True
    assert info.governed_execution_claim_generation_fencing_implemented is True
    assert info.governed_execution_claim_recovery_mode == "explicit-local-operator"
    assert info.protected_payload_retention_implemented is True
    assert info.protected_payload_success_cleanup_implemented is True
    assert info.protected_payload_failure_retention_days == 7
    assert info.governed_recovery_retention_deterministic_accepted is True
    assert info.governed_recovery_retention_windows_live_accepted is False
    assert info.active_run_restart_recovery_implemented is False
    assert info.distributed_worker_lease_implemented is False
