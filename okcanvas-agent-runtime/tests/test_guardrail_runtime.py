from pathlib import Path

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.execution import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.agent.guardrails import GuardrailKind, GuardrailRuntimeCatalog

ROOT = Path(__file__).resolve().parents[1]


def test_guardrail_catalog_has_four_closed_runtimes() -> None:
    items = GuardrailRuntimeCatalog(ROOT).list_runtimes()
    assert len(items) == 4
    assert {item.kind for item in items} == {
        GuardrailKind.INPUT,
        GuardrailKind.OUTPUT,
        GuardrailKind.TOOL_INPUT,
        GuardrailKind.TOOL_OUTPUT,
    }
    assert all(item.behavior == "RAISE_EXCEPTION" for item in items)


def test_guardrail_agents_are_session_child_mcp_workspace_free() -> None:
    catalog = AgentDefinitionCatalog(ROOT)
    for agent_id in (
        "guardrail-language-agent",
        "guardrail-tool-input-agent",
        "guardrail-tool-output-agent",
    ):
        item = catalog.resolve(agent_id)
        assert item.guardrails
        assert item.session_mode == "disabled"
        assert item.handoffs == ()
        assert item.agent_tools == ()
        assert item.mcp_servers == ()
        assert item.workspace_access == "none"


def test_guardrail_runtime_binding_contains_policy_and_implementation() -> None:
    definitions = AgentDefinitionCatalog(ROOT)
    bindings = AgentRuntimeBindingCatalog(ROOT)
    for agent_id in (
        "guardrail-language-agent",
        "guardrail-tool-input-agent",
        "guardrail-tool-output-agent",
    ):
        binding = bindings.resolve(definitions.resolve(agent_id))
        assert binding.execution_path == "native-guardrail-execution-v1"
        assert binding.guardrail_runtime_sha256
        assert binding.guardrails
        assert all(item["definition_sha256"] for item in binding.guardrails)
        assert all(item["implementation_sha256"] for item in binding.guardrails)
