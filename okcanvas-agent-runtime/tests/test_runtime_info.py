from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo


def test_step004a_architecture_boundary() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.openai_agents_version == "0.19.0"
    assert info.codex_readonly_implemented is True
    assert info.codex_live_accepted is True
    assert info.workspace_write_implemented is True
    assert info.workspace_write_live_accepted is True
    assert info.independent_validation_implemented is True
    assert info.persisted_approval_implemented is True
    assert info.persisted_approval_live_accepted is False
    assert info.approval_resume_enabled_for_controlled_fixture is True
    assert info.workspace_write_enabled is False
    assert info.mcp_enabled is True
    assert info.arbitrary_shell_enabled is False
    assert info.handoffs_enabled is True
    assert info.specification_root == "specs"


def test_step010_evaluation_capabilities():
    info = RuntimeInfo()
    assert info.evaluation_service_implemented is True
    assert info.evaluation_service_accepted is True
    assert info.evaluation_model_live_accepted is False


def test_step011_catalog_api_capabilities():
    info = RuntimeInfo()
    assert info.agent_definition_catalog_api_implemented is True
    assert info.evaluation_catalog_api_implemented is True
    assert info.evaluation_history_api_implemented is True
    assert info.evaluation_comparison_api_implemented is True
    assert info.catalog_api_read_only is True
    assert info.catalog_api_accepted is True
