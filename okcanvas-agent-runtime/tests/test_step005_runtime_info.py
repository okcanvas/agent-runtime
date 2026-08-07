from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo


def test_step005_product_state_capabilities_are_explicit() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.product_store_implemented is True
    assert info.product_store_backend == "sqlite"
    assert info.canonical_run_events_implemented is True
    assert info.artifact_integrity_implemented is True
    assert info.mcp_enabled is True
    assert info.workspace_write_enabled is False
    assert info.reference_catalog_implemented is True
    assert info.reference_catalog_accepted is True
    assert info.reference_tree_verification_enabled is True
    assert info.reference_catalog_mcp_exposed is True
