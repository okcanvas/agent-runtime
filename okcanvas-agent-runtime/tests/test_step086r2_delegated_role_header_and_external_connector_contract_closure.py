from __future__ import annotations

import json
from pathlib import Path

from okcanvas_agent_runtime.application.groupware_read import GroupwareDeploymentCatalog
from okcanvas_agent_runtime.application.mcp_access import DelegatedMCPIdentity, MCPAccessCatalog
from okcanvas_agent_runtime.agent.mcp.definitions import MCPServerCatalog
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

ROOT = Path(__file__).resolve().parents[1]


def test_roles_header_is_transmitted_and_matches_access_policy() -> None:
    identity = DelegatedMCPIdentity.create(
        tenant_id="tenant-a", principal_id="user-001", roles=("employee", "agent-user")
    )
    definition = MCPServerCatalog(ROOT).resolve("groupware-read")
    binding = MCPAccessCatalog(ROOT).bind_many((definition,), identity)[0]
    assert binding is not None
    assert binding.identity_headers() == {
        "X-OKCanvas-Tenant-ID": "tenant-a",
        "X-OKCanvas-Principal-ID": "user-001",
        "X-OKCanvas-Roles": "agent-user,employee",
        "X-OKCanvas-Delegation-ID": identity.delegation_id,
    }
    policy = MCPAccessCatalog(ROOT).policy
    assert policy.delegated_headers == (
        "X-OKCanvas-Delegation-ID",
        "X-OKCanvas-Principal-ID",
        "X-OKCanvas-Roles",
        "X-OKCanvas-Tenant-ID",
    )


def test_external_connector_and_optional_example_paths_are_exact() -> None:
    deployment = GroupwareDeploymentCatalog(ROOT)
    boundary = deployment.boundary
    provider = deployment.provider
    assert boundary.external_connector_repository == "okcanvas-connectors"
    assert boundary.external_groupware_connector_path == "okcanvas-connectors/groupware-mcp-server"
    assert boundary.connector_examples_repository == "okcanvas-connector-examples"
    assert boundary.groupware_api_fake_example_path == (
        "okcanvas-connector-examples/groupware/groupware-api-fake"
    )
    assert boundary.connector_examples_required is False
    assert boundary.groupware_api_fake_is_mcp_server is False
    assert provider.external_connector_project_path == boundary.external_groupware_connector_path
    assert provider.credential_reference_transmitted is False
    assert provider.required_identity_headers == (
        "X-OKCanvas-Tenant-ID",
        "X-OKCanvas-Principal-ID",
        "X-OKCanvas-Roles",
        "X-OKCanvas-Delegation-ID",
    )


def test_step086r1_windows_parent_is_preserved_and_current_runtime_is_r2() -> None:
    evidence = json.loads(
        (ROOT / "docs/evidence/STEP086R1_WINDOWS_DETERMINISTIC_ACCEPTANCE.json").read_text(
            encoding="utf-8"
        )
    )
    assert evidence["state"] == "PASSED"
    assert evidence["step"] == "STEP086R1_GROUPWARE_SUBAGENT_AND_EXTERNAL_MCP_BOUNDARY_ALIGNMENT"
    assert evidence["version"] == "2.66.1"
    assert evidence["passed_checks"] == evidence["total_checks"] == 13
    info = RuntimeInfo()
    assert info.step == "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    assert info.version == "2.75.0"
    assert info.step086r1_windows_deterministic_accepted is True
    assert info.step086r1_windows_deterministic_passed_checks == 13
    assert info.delegated_mcp_roles_header == "X-OKCanvas-Roles"
    assert info.delegated_mcp_roles_transmitted is True
    assert info.delegated_mcp_credential_reference_transmitted is False
    assert info.groupware_read_external_connector_project_path == (
        "okcanvas-connectors/groupware-mcp-server"
    )
    assert info.groupware_read_api_fake_example_required is False
    assert info.groupware_read_api_fake_example_is_mcp_server is False


def test_step086r2_launcher_registry_and_windows_dispatch(monkeypatch) -> None:
    from scripts import windows_entrypoint
    from scripts.validate_acceptance_launcher_registry import validate

    registry = validate()
    assert registry["state"] == "PASSED"
    assert registry["current_step"] == (
        "STEP091D_OBJECT_STORAGE_DEPLOYMENT_COMPOSITION_AND_LIVE_ACCEPTANCE_GATE"
    )
    registry_payload = __import__("json").loads(
        (ROOT / "specs/acceptance/launcher-registry.json").read_text(encoding="utf-8")
    )
    assert registry["current_record_count"] == len(registry_payload["required_current_records"])

    import subprocess

    captured: dict[str, object] = {}

    def fake_run(command, *, cwd, env, check):
        captured.update(command=command, cwd=cwd, env=env, check=check)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", lambda: ({}, None))
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run(["groupware-connector-contract-acceptance"]) == 0
    launched = captured["command"]
    assert launched[0] == windows_entrypoint.sys.executable
    assert launched[1] == str(ROOT / "scripts/run_step086r2_acceptance.py")
    assert captured["cwd"] == ROOT


def test_step086r2_local_evidence_is_not_packaged() -> None:
    from scripts.step081_product_inventory import included_relative_path

    assert included_relative_path(
        Path("docs/evidence/step086r2-local/STEP086R2_ACCEPTANCE.json")
    ) is False


def test_step086r2_handoff_preserves_exact_external_connector_and_example_identifiers() -> None:
    handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
    required = (
        "external-connector-service",
        "okcanvas-connectors/groupware-mcp-server",
        "EXAMPLE_TEMPLATE_ONLY",
        "okcanvas-connector-examples/groupware/groupware-api-fake",
    )
    assert all(identity in handoff for identity in required)
