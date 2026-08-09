from pathlib import Path
import json

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.application.assistant_routing.cross_domain_session import CrossDomainSessionDelegationCatalog

ROOT = Path(__file__).resolve().parents[1]


def _request(capability: str) -> str:
    payload = {
        "status": "EXECUTABLE",
        "selected_agent_definition_id": "organization-assistant-session-agent",
        "required_capabilities": [capability],
    }
    return "OKCANVAS ROUTING CONTEXT (product-owned, immutable):\n" + json.dumps(payload) + "\n\nUSER REQUEST:\nhello"


def test_unified_cross_domain_session_root_declares_exact_two_stateless_children() -> None:
    definition = AgentDefinitionCatalog(ROOT).resolve("organization-assistant-session-agent")
    assert definition.version == "1.2.0"
    assert definition.agent_tools == ("groupware-read-agent", "organization-context-read-agent")
    binding = CrossDomainSessionDelegationCatalog(ROOT).resolve(definition)
    assert tuple(item.domain for item in binding.targets) == ("GROUPWARE", "ORGANIZATION_CONTEXT")


def test_unified_runtime_binding_owns_both_child_mcp_boundaries() -> None:
    definition = AgentDefinitionCatalog(ROOT).resolve("organization-assistant-session-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    assert binding.execution_path == "sqlite-session-bounded-cross-domain-read-subagent-execution-v1"
    owners = {(item["server_id"], item["owner_agent_id"]) for item in binding.mcp_servers}
    assert owners == {
        ("groupware-read", "groupware-read-agent"),
        ("organization-context-read", "organization-context-read-agent"),
    }


def test_immutable_route_context_selects_exactly_one_cross_domain_child() -> None:
    definition = AgentDefinitionCatalog(ROOT).resolve("organization-assistant-session-agent")
    binding = CrossDomainSessionDelegationCatalog(ROOT).resolve(definition)
    groupware = binding.target_for_request(_request("groupware-read-v1"))
    organization = binding.target_for_request(_request("organization-context-read-v1"))
    assert groupware is not None and groupware.child.agent_id == "groupware-read-agent"
    assert organization is not None and organization.child.agent_id == "organization-context-read-agent"
