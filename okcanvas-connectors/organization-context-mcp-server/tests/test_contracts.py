import json
from pathlib import Path

from organization_context_mcp_server.mcp_protocol import TOOLS

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_TOOLS = [
    "resolve_organization_context",
    "search_organization_context",
    "get_organization_entity",
    "resolve_organization_terms",
    "search_organization_terms",
    "get_organization_term",
    "get_organization_catalog_state",
    "get_organization_changes",
]


def test_declared_tools_are_exact_and_read_only() -> None:
    names = [item["name"] for item in TOOLS]
    assert names == EXPECTED_TOOLS
    assert all(item["annotations"]["readOnlyHint"] is True for item in TOOLS)
    assert all(item["annotations"]["destructiveHint"] is False for item in TOOLS)


def test_binding_contract_keeps_example_optional_and_fake_mode_absent() -> None:
    contract = json.loads((ROOT / "contracts/connector-binding-contract.json").read_text(encoding="utf-8"))
    assert contract["fake_mode_allowed"] is False
    assert contract["example_project_path"] == "okcanvas-connector-examples/organization-context/organization-context-api-fake"
    assert contract["credential_reference_transmitted"] is False
    assert contract["tool_names"] == EXPECTED_TOOLS
    assert contract["production_source_of_truth"] == "DATABASE"
    assert contract["example_source_of_truth"] == "COMMITTED_JSON_FIXTURES"


def test_step003_get_entity_requires_relation_completeness_evidence() -> None:
    source = (ROOT / "organization_context_mcp_server/service.py").read_text(encoding="utf-8")
    assert "ORGANIZATION_CONTEXT_RELATION_COMPLETENESS_INVALID" in source
    assert 'record.get("relation_count")' in source
    assert 'record.get("relations_returned_count")' in source
    assert 'record.get("relations_truncated")' in source
