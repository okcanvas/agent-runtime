from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from okcanvas_agent_runtime.agent.definitions import (
    AgentDefinitionCatalog,
    AgentDefinitionContractError,
)
from okcanvas_agent_runtime.application.execution.output_registry import resolve_output_contract
from okcanvas_agent_runtime.application.groupware_read import (
    GroupwareDeploymentCatalog,
    GroupwareDeploymentContractError,
    GroupwareReadCatalog,
)
from okcanvas_agent_runtime.core.contracts import (
    GroupwareReadCitation,
    GroupwareReadResult,
    GroupwareReadStatus,
)
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from scripts import windows_entrypoint
from scripts.step081_product_inventory import included_relative_path
from scripts.run_step086r1_python_regression import _test_inventory_sha256

ROOT = Path(__file__).resolve().parents[1]


def _copy_product_contracts(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    shutil.copytree(ROOT / "specs", project / "specs")
    shutil.copytree(ROOT / "fixtures", project / "fixtures")
    shutil.copytree(ROOT / "reference", project / "reference")
    return project


def test_product_subagent_is_internal_and_actual_groupware_provider_is_external() -> None:
    catalog = GroupwareDeploymentCatalog(ROOT)
    boundary = catalog.boundary
    provider = catalog.provider
    assert boundary.read_agent_definition_location == "runtime-internal"
    assert boundary.mcp_client_declaration_location == "runtime-internal"
    assert boundary.mcp_provider_deployment == "external-connector-service"
    assert boundary.mcp_provider_implementation_in_runtime is False
    assert boundary.organization_specific_adapter_in_runtime is False
    assert boundary.test_fixture_location == "runtime-internal"
    assert boundary.read_agent_permanently_read_only is True
    assert boundary.write_extension_strategy == "separate-agent-separate-mcp-separate-credential"
    assert boundary.future_write_agent_id == "groupware-action-agent"
    assert boundary.future_write_mcp_server_id == "groupware-action"
    assert boundary.external_groupware_connector_path == "okcanvas-connectors/groupware-mcp-server"
    assert boundary.groupware_api_fake_example_path == "okcanvas-connector-examples/groupware/groupware-api-fake"
    assert boundary.connector_examples_required is False
    assert boundary.groupware_api_fake_is_mcp_server is False
    assert provider.server_id == "groupware-read"
    assert provider.provider_deployment == "external-connector-service"
    assert provider.provider_implemented_in_runtime is False
    assert provider.required_identity_fields == (
        "tenant_id",
        "principal_id",
        "roles",
        "delegation_id",
    )
    assert provider.required_identity_headers == (
        "X-OKCanvas-Tenant-ID",
        "X-OKCanvas-Principal-ID",
        "X-OKCanvas-Roles",
        "X-OKCanvas-Delegation-ID",
    )
    assert provider.credential_reference_transmitted is False


def test_internal_provider_fixtures_validate_contract_but_are_not_a_server() -> None:
    catalog = GroupwareDeploymentCatalog(ROOT)
    fixtures = catalog.validate_fixture_directory()
    assert len(fixtures) == 3
    assert {item["tool_name"] for item in fixtures} == {
        "search_notices",
        "search_mail",
        "list_calendar_events",
    }
    assert all(item["mutated"] is False for item in fixtures)
    assert not (ROOT / "okcanvas_agent_runtime/adapters/mcp/servers/groupware_read.py").exists()
    assert not (ROOT / "okcanvas_agent_runtime/adapters/groupware").exists()
    public = catalog.to_public_dict()
    assert public["actual_external_provider_implemented_in_runtime"] is False
    assert public["external_connector_project_selected"] is True
    assert public["connector_example_required"] is False


def test_groupware_subagent_is_runtime_bound_with_a_dedicated_read_contract() -> None:
    definition = AgentDefinitionCatalog(ROOT).resolve("groupware-read-agent")
    assert definition.version == "1.1.0"
    assert definition.output_contract == "GroupwareReadResult"
    assert definition.output_schema == GroupwareReadResult.model_json_schema()
    assert definition.mcp_servers == ("groupware-read",)
    assert definition.tools == definition.hosted_tools == definition.agent_tools == ()
    assert definition.handoffs == definition.orchestration_children == ()
    runtime = resolve_output_contract("GroupwareReadResult")
    assert runtime.output_type is GroupwareReadResult
    schema_properties = definition.output_schema["properties"]
    assert "completed_actions" not in schema_properties
    assert "proposed_actions" not in schema_properties
    assert "pending_approvals" not in schema_properties
    assert "follow_up_state" not in schema_properties


def test_groupware_read_result_cannot_validate_write_shaped_output() -> None:
    answered = GroupwareReadResult(
        status=GroupwareReadStatus.ANSWERED,
        answer="공지 1건을 찾았습니다.",
        queried_operations=["search_notices"],
        result_count=1,
        citations=[
            GroupwareReadCitation(label="notice-001", reference="notice:notice-001")
        ],
    )
    assert answered.side_effect == "READ"
    assert answered.request_class == "READ_SYSTEM"
    with pytest.raises(ValidationError):
        GroupwareReadResult.model_validate(
            {
                **answered.model_dump(mode="json"),
                "completed_actions": [
                    {
                        "capability_id": "groupware-write-v1",
                        "summary": "메일 발송",
                        "side_effect": "WRITE_IRREVERSIBLE",
                    }
                ],
            }
        )
    with pytest.raises(ValidationError):
        GroupwareReadResult(
            status=GroupwareReadStatus.ANSWERED,
            answer="메일이 있습니다.",
            queried_operations=["search_mail"],
            result_count=1,
            citations=[],
        )
    with pytest.raises(ValidationError):
        GroupwareReadResult(
            status=GroupwareReadStatus.NEEDS_CAPABILITY,
            answer="Provider가 없습니다.",
            result_count=1,
            citations=[GroupwareReadCitation(label="invented")],
            unverified=["external-provider-not-configured"],
        )


def test_groupware_read_catalog_aligns_policy_client_and_external_provider_contract() -> None:
    catalog = GroupwareReadCatalog(ROOT)
    assert catalog.policy.allowed_tools == catalog.server.allowed_tools
    assert catalog.policy.allowed_tools == catalog.deployment.provider.allowed_tools
    deployment = catalog.to_public_dict()["deployment"]
    assert deployment["actual_external_provider_implemented_in_runtime"] is False
    assert deployment["external_connector_project_selected"] is True
    assert deployment["external_connector_live_groupware_verified"] is False


def test_groupware_agent_rejects_shared_write_capable_output_contract(tmp_path: Path) -> None:
    project = _copy_product_contracts(tmp_path)
    definition_path = project / "specs/agents/groupware-read-agent/definition.json"
    payload = json.loads(definition_path.read_text(encoding="utf-8"))
    payload["output_contract"] = "OrganizationAssistantResult"
    definition_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(AgentDefinitionContractError):
        AgentDefinitionCatalog(project).resolve("groupware-read-agent")


def test_groupware_provider_contract_rejects_write_tool_and_internal_provider_claim(tmp_path: Path) -> None:
    project = _copy_product_contracts(tmp_path)
    provider_path = project / "specs/groupware/read-provider-contract.json"
    payload = json.loads(provider_path.read_text(encoding="utf-8"))
    payload["tools"][0]["tool_name"] = "send_mail"
    payload["tools"][0]["mutates"] = True
    payload["provider_implemented_in_runtime"] = True
    provider_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(GroupwareDeploymentContractError):
        GroupwareDeploymentCatalog(project)


def test_runtime_info_corrects_step086_overclaim_and_promotes_windows_parent() -> None:
    info = RuntimeInfo()
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.step086_windows_deterministic_accepted is True
    assert info.step086_windows_deterministic_passed_checks == 14
    assert info.step086_windows_deterministic_total_checks == 14
    assert info.groupware_read_only_vertical_implemented is True
    assert info.groupware_read_integration_boundary_implemented is True
    assert info.groupware_read_integration_boundary_status == "MAIN_SESSION_TO_STATELESS_SUBAGENT_EXTERNAL_CONNECTOR_EXECUTION_PATH"
    assert info.groupware_read_agent_definition_location == "runtime-internal"
    assert info.groupware_read_agent_output_contract == "GroupwareReadResult"
    assert info.groupware_read_agent_runtime_bound is True
    assert info.groupware_read_mcp_client_declaration_location == "runtime-internal"
    assert info.groupware_read_mcp_provider_deployment == "external-connector-service"
    assert info.groupware_read_mcp_provider_implemented_in_runtime is False
    assert info.groupware_read_mcp_provider_live_verified is False
    assert info.groupware_read_provider_contract_fixture_count == 3
    assert info.groupware_read_permanently_read_only is True
    assert info.groupware_write_extension_strategy == "separate-agent-separate-mcp-separate-credential"
    assert info.groupware_action_agent_implemented is False
    assert info.groupware_action_mcp_server_implemented is False


def test_step086r1_windows_entrypoint_dispatches_current_boundary_acceptance(monkeypatch) -> None:
    command_name = "groupware-boundary-acceptance"
    action = next(item for item in windows_entrypoint._parser()._actions if item.dest == "command")
    assert command_name in action.choices
    captured: dict[str, object] = {}

    def fake_run(command, *, cwd, env, check):
        captured.update(command=command, cwd=cwd, env=env, check=check)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(windows_entrypoint, "load_local_environment", lambda: ({}, None))
    monkeypatch.setattr(windows_entrypoint.subprocess, "run", fake_run)
    assert windows_entrypoint.run([command_name]) == 0
    launched = captured["command"]
    assert launched[0] == windows_entrypoint.sys.executable
    assert launched[1] == str(ROOT / "scripts/run_step086r1_acceptance.py")
    assert captured["cwd"] == ROOT


def test_step086r1_local_checkpoint_evidence_is_excluded_from_product_zip() -> None:
    assert included_relative_path(Path("docs/evidence/step086r1-local/STEP086R1_ACCEPTANCE.json")) is False
    assert included_relative_path(Path("docs/evidence/step086r1-local/python-regression/chunk-000-019.txt")) is False


def test_step086r1_bounded_regression_inventory_hash_detects_content_drift() -> None:
    probe = ROOT / "tests/_step086r1_inventory_probe.py"
    try:
        probe.write_text("VALUE = 1\n", encoding="utf-8")
        first = _test_inventory_sha256((probe,))
        probe.write_text("VALUE = 2\n", encoding="utf-8")
        second = _test_inventory_sha256((probe,))
        assert len(first) == len(second) == 64
        assert first != second
    finally:
        probe.unlink(missing_ok=True)
