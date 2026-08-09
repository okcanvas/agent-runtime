from pathlib import Path

from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_step009_runtime_capabilities_are_explicit() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.mcp_enabled is True
    assert info.mcp_mode == "allowlisted-read-only-local-stdio-and-remote-streamable-http"
    assert info.mcp_server_catalog_implemented is True
    assert info.mcp_reference_server_implemented is True
    assert info.mcp_tool_event_normalization_implemented is True
    assert info.mcp_protocol_live_accepted is True
    assert info.mcp_agent_live_accepted is True
    assert info.reference_catalog_mcp_exposed is True
    assert info.generic_agent_execution_live_accepted is True
    assert info.direct_reference_import_forbidden is True


def test_reference_research_agent_uses_only_allowlisted_mcp_server() -> None:
    from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog

    definition = AgentDefinitionCatalog(ROOT).resolve("reference-research-agent")
    assert definition.tools == ()
    assert definition.mcp_servers == ("reference-catalog",)
    assert definition.handoffs == ()
    assert definition.session_mode == "disabled"
