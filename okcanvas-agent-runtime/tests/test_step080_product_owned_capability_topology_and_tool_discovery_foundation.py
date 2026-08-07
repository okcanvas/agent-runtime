from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.agent.capabilities.topology import (
    AgentCapabilityTopologyCatalog,
    CapabilityActivation,
    CapabilityContractError,
    CapabilityFamily,
    CapabilityFoundationCatalog,
    CapabilityLoading,
    SDKExampleCatalog,
)
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog

ROOT = Path(__file__).resolve().parents[1]


def _definitions():
    return AgentDefinitionCatalog(ROOT).list_definitions()


def _bindings_by_id(agent_id: str):
    definition = AgentDefinitionCatalog(ROOT).resolve(agent_id)
    topology = AgentCapabilityTopologyCatalog(ROOT).resolve(definition)
    return {binding.capability_id: binding for binding in topology.bindings}


def test_all_agent_surfaces_normalize_into_one_immutable_topology() -> None:
    definitions = _definitions()
    assert len(definitions) == 32
    catalog = AgentCapabilityTopologyCatalog(ROOT)
    topologies = [catalog.resolve(definition) for definition in definitions]
    assert len({item.agent_id for item in topologies}) == 32
    assert len({item.topology_sha256 for item in topologies}) == 32

    actual = {
        (binding.family.value, binding.kind)
        for topology in topologies
        for binding in topology.bindings
    }
    assert actual == {
        ("tool", "function-tool"),
        ("tool", "hosted-web-search"),
        ("skill", "product-instruction-skill"),
        ("sub-agent", "handoff"),
        ("sub-agent", "agent-as-tool"),
        ("sub-agent", "product-orchestration-child"),
        ("mcp", "builtin-stdio"),
        ("mcp", "remote-streamable-http"),
        ("guardrail", "input"),
        ("guardrail", "output"),
        ("guardrail", "tool-input"),
        ("guardrail", "tool-output"),
        ("workspace", "sandbox-readonly-v1"),
        ("input", "local-attachment-v1"),
        ("session", "sqlite-v1"),
    }

    for topology in topologies:
        assert topology.schema_version == "okcanvas-agent-capability-topology-v1"
        assert all(binding.activation is CapabilityActivation.ACTIVE for binding in topology.bindings)
        assert all(binding.loading is not CapabilityLoading.DEFERRED for binding in topology.bindings)
        assert all(binding.programmatic_call_allowed is False for binding in topology.bindings)
        assert topology.discovery_policy.tool_search_runtime_enabled is False
        assert topology.discovery_policy.programmatic_tool_calling_runtime_enabled is False


def test_function_tool_discovery_metadata_is_ready_but_runtime_search_is_disabled() -> None:
    bindings = _bindings_by_id("local-text-fingerprint-agent")
    binding = bindings["local_text_fingerprint"]
    assert binding.family is CapabilityFamily.TOOL
    assert binding.kind == "function-tool"
    assert binding.sdk_surface == "Agent.tools/FunctionTool"
    assert binding.namespace_id == "local-text"
    assert binding.tool_search_eligible is True
    assert binding.loading is CapabilityLoading.EAGER
    assert binding.direct_call_allowed is True
    assert binding.programmatic_call_allowed is False

    topology = AgentCapabilityTopologyCatalog(ROOT).resolve(
        AgentDefinitionCatalog(ROOT).resolve("local-text-fingerprint-agent")
    )
    assert len(topology.namespaces) == 1
    namespace = topology.namespaces[0]
    assert namespace.namespace_id == "local-text"
    assert namespace.activation is CapabilityActivation.STRUCTURE_ONLY
    assert namespace.loading is CapabilityLoading.EAGER


def test_current_mcp_and_product_skill_are_not_misclassified_as_sdk_tool_search_or_shell_skill() -> None:
    mcp = _bindings_by_id("reference-research-agent")["reference-catalog"]
    assert mcp.family is CapabilityFamily.MCP
    assert mcp.sdk_surface == "Agent.mcp_servers/MCPServer"
    assert mcp.tool_search_eligible is False
    assert mcp.programmatic_call_allowed is False

    skill = _bindings_by_id("skill-document-review-agent")["document-review-v1"]
    assert skill.family is CapabilityFamily.SKILL
    assert skill.kind == "product-instruction-skill"
    assert skill.sdk_surface == "Agent.instructions/Product-owned Skill"
    assert skill.loading is CapabilityLoading.INSTRUCTION_COMPOSED
    assert skill.direct_call_allowed is False
    assert skill.programmatic_call_allowed is False


def test_sdk_examples_are_hash_pinned_and_cover_extension_families() -> None:
    inventory = SDKExampleCatalog(ROOT).resolve()
    assert inventory.sdk_version == "0.19.0"
    assert len(inventory.records) == 30
    records = {record.example_id: record for record in inventory.records}

    assert records["tool-search"].product_status is CapabilityActivation.STRUCTURE_ONLY
    tool_search = (
        ROOT
        / "reference/upstream/openai-agents-python-0.19.0/examples/tools/tool_search.py"
    ).read_text(encoding="utf-8")
    assert "ToolSearchTool" in tool_search
    assert "tool_namespace(" in tool_search
    assert "defer_loading=True" in tool_search

    assert records["programmatic-tool-calling"].product_status is CapabilityActivation.STRUCTURE_ONLY
    programmatic = (
        ROOT
        / "reference/upstream/openai-agents-python-0.19.0/examples/tools/programmatic_tool_calling.py"
    ).read_text(encoding="utf-8")
    assert "ProgrammaticToolCallingTool" in programmatic
    assert 'allowed_callers=["programmatic"]' in programmatic

    assert records["local-shell-skill"].family is CapabilityFamily.SKILL
    local_skill = (
        ROOT
        / "reference/upstream/openai-agents-python-0.19.0/examples/tools/local_shell_skill.py"
    ).read_text(encoding="utf-8")
    assert "ShellToolLocalSkill" in local_skill
    assert "ShellTool(" in local_skill


def test_foundation_snapshot_binds_all_agents_examples_and_discovery_policy() -> None:
    foundation = CapabilityFoundationCatalog(ROOT).resolve()
    assert foundation.schema_version == "okcanvas-capability-foundation-v1"
    assert foundation.agent_topology_count == 32
    assert foundation.binding_count == 39
    assert dict(foundation.family_counts) == {
        "guardrail": 6,
        "input": 2,
        "mcp": 4,
        "session": 9,
        "skill": 1,
        "sub-agent": 8,
        "tool": 8,
        "workspace": 1,
    }
    assert len(foundation.sdk_example_inventory.records) == 30
    assert foundation.discovery_policy.tool_search_runtime_enabled is False
    assert foundation.discovery_policy.programmatic_tool_calling_runtime_enabled is False
    assert len(foundation.topology_root_sha256) == 64


def test_agent_public_contract_and_runtime_binding_include_capability_topology() -> None:
    definition = AgentDefinitionCatalog(ROOT).resolve("sandbox-readonly-coding-agent")
    public = definition.to_public_dict()
    topology = public["capability_topology"]
    assert topology["agent_id"] == "sandbox-readonly-coding-agent"
    assert topology["topology_sha256"]
    assert {item["family"] for item in topology["bindings"]} == {"tool", "workspace"}

    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    assert binding.capability_topology == topology
    assert len(binding.capability_topology_runtime_sha256) == 64
    assert binding.sdk_example_inventory_sha256 == SDKExampleCatalog(ROOT).resolve().inventory_sha256
    assert binding.to_fingerprint_dict()["capability_topology"] == topology


def test_discovery_policy_change_changes_agent_topology_and_runtime_fingerprint(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "specs", tmp_path / "specs")
    shutil.copytree(ROOT / "reference", tmp_path / "reference")
    before_definition = AgentDefinitionCatalog(tmp_path).resolve("local-text-fingerprint-agent")
    before_topology = AgentCapabilityTopologyCatalog(tmp_path).resolve(before_definition)
    before_binding = AgentRuntimeBindingCatalog(tmp_path).resolve(before_definition)

    policy_path = tmp_path / "specs/capabilities/tool-discovery-policy.json"
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    payload["tool_search"]["max_deferred_tools_per_agent"] = 63
    policy_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    after_definition = AgentDefinitionCatalog(tmp_path).resolve("local-text-fingerprint-agent")
    after_topology = AgentCapabilityTopologyCatalog(tmp_path).resolve(after_definition)
    after_binding = AgentRuntimeBindingCatalog(tmp_path).resolve(after_definition)
    assert before_topology.topology_sha256 != after_topology.topology_sha256
    assert before_binding.runtime_binding_sha256 != after_binding.runtime_binding_sha256


def test_policy_rejects_runtime_tool_search_or_programmatic_activation(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "specs", tmp_path / "specs")
    shutil.copytree(ROOT / "reference", tmp_path / "reference")
    path = tmp_path / "specs/capabilities/tool-discovery-policy.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["tool_search"]["runtime_enabled"] = True
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(CapabilityContractError, match="must not enable Tool Search"):
        CapabilityFoundationCatalog(tmp_path).resolve()


def test_service_capability_contract_exposes_extension_foundation(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    from tests.test_step069_multi_user_service_client_contract import ALICE_TOKEN, _app, _headers

    with TestClient(_app(tmp_path)) as client:
        response = client.get("/v1/service/capabilities", headers=_headers(ALICE_TOKEN))
        assert response.status_code == 200, response.text
        payload = response.json()
    foundation = CapabilityFoundationCatalog(ROOT).resolve()
    assert payload["runtime_version"] == "2.75.0"
    assert payload["capability_topology_available"] is True
    assert payload["capability_foundation_schema"] == foundation.schema_version
    assert payload["capability_topology_schema"] == "okcanvas-agent-capability-topology-v1"
    assert payload["capability_agent_topology_count"] == 32
    assert payload["capability_binding_count"] == 39
    assert payload["capability_families"] == [
        "guardrail", "input", "mcp", "session", "skill", "sub-agent", "tool", "workspace"
    ]
    assert payload["capability_tool_search_structure_ready"] is True
    assert payload["capability_tool_search_runtime_enabled"] is False
    assert payload["capability_programmatic_tool_calling_structure_ready"] is True
    assert payload["capability_programmatic_tool_calling_runtime_enabled"] is False
    assert payload["capability_sdk_example_inventory_count"] == 30
    assert payload["capability_sdk_example_inventory_sha256"] == foundation.sdk_example_inventory.inventory_sha256
    assert payload["capability_topology_root_sha256"] == foundation.topology_root_sha256
    assert payload["next_selected_step"] == "UNSELECTED_PENDING_USER_SELECTION"
