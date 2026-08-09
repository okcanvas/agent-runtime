from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo


def test_step024_business_agent_baseline() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.store_replenishment_agent_implemented is True
    assert info.store_replenishment_agent_deterministic_accepted is True
    assert info.store_replenishment_agent_live_accepted is True
    assert info.governed_local_tool_approval_live_sdk_accepted is True
    assert info.windows_live_acceptance_closure_complete is True


def test_step024a_live_diagnostics_baseline() -> None:
    info = RuntimeInfo()
    assert info.business_output_contract_round_trip_validation_implemented is True
    assert info.step024_live_failure_diagnostics_implemented is True
    assert info.store_replenishment_agent_live_accepted is True
