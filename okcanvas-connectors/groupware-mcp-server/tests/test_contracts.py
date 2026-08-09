from __future__ import annotations

import json
from pathlib import Path

from groupware_mcp_server.baseline import CURRENT_STEP, PROJECT_VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_provider_contract_is_read_only_and_roles_header_is_explicit() -> None:
    payload = json.loads((ROOT / "contracts/runtime-provider-contract.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "okcanvas-groupware-read-provider-contract-v3"
    assert payload["external_connector_project_path"] == "okcanvas-connectors/groupware-mcp-server"
    assert payload["required_identity_headers"] == [
        "X-OKCanvas-Tenant-ID",
        "X-OKCanvas-Principal-ID",
        "X-OKCanvas-Roles",
        "X-OKCanvas-Delegation-ID",
    ]
    assert payload["credential_reference_transmitted"] is False
    assert all(item["mutates"] is False for item in payload["tools"])


def test_connector_binding_contract_adds_transport_auth_without_leaking_credential_reference() -> None:
    payload = json.loads((ROOT / "contracts/connector-binding-contract.json").read_text(encoding="utf-8"))
    assert payload["required_http_headers"] == [
        "Authorization",
        "X-OKCanvas-Tenant-ID",
        "X-OKCanvas-Principal-ID",
        "X-OKCanvas-Roles",
        "X-OKCanvas-Delegation-ID",
    ]
    assert payload["required_role"] == "agent-user"
    assert payload["credential_reference_transmitted"] is False


def test_identity_and_version_are_exact() -> None:
    assert CURRENT_STEP == "CONNECTOR_STEP002_STABLE_ORGANIZATION_CONTEXT_REFERENCE_FILTER"
    assert PROJECT_VERSION == "0.2.0"


def test_async_scenarios_use_stdlib_runner_without_pytest_async_plugin() -> None:
    test_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted((ROOT / "tests").glob("test_*.py"))
    )
    async_marker = "pytest.mark." + "asyncio"
    async_plugin = "pytest" + "_asyncio"
    assert async_marker not in test_sources
    assert async_plugin not in test_sources
    assert "asyncio.run(" in test_sources


def test_context_ref_filter_is_declared_on_all_read_tools() -> None:
    payload = json.loads((ROOT / "contracts/runtime-provider-contract.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "okcanvas-groupware-read-provider-contract-v3"
    assert all(item["input_schema_version"].endswith("-v2") for item in payload["tools"])
    source = (ROOT / "groupware_mcp_server/mcp_protocol.py").read_text(encoding="utf-8")
    assert source.count('"context_ref"') >= 3
    assert all(token in source for token in ("EMPLOYEE", "PROJECT", "CLIENT", "PRODUCT", "DEPARTMENT"))


def test_context_ref_path_requires_canonical_non_narrowing_arguments() -> None:
    source = (ROOT / "groupware_mcp_server/contracts.py").read_text(encoding="utf-8")
    assert 'context_ref search requires empty query and limit 20' in source
    assert 'context_ref calendar lookup requires no time range and limit 20' in source
    client = (ROOT / "groupware_mcp_server/groupware_client.py").read_text(encoding="utf-8")
    assert client.count('"context_ref": context_ref') >= 3
