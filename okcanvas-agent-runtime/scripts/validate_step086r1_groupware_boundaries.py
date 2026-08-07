from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.execution.output_registry import resolve_output_contract
from okcanvas_agent_runtime.application.groupware_read import (
    GroupwareDeploymentCatalog,
    GroupwareReadCatalog,
)
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.contracts import (
    GroupwareReadCitation,
    GroupwareReadResult,
    GroupwareReadStatus,
)
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

STEP = "STEP086R1_GROUPWARE_SUBAGENT_AND_EXTERNAL_MCP_BOUNDARY_ALIGNMENT"
VERSION = "2.66.1"
WINDOWS_EVIDENCE = ROOT / "docs/evidence/STEP086_WINDOWS_DETERMINISTIC_ACCEPTANCE.json"


def _write_shaped_output_rejected() -> bool:
    valid = GroupwareReadResult(
        status=GroupwareReadStatus.ANSWERED,
        answer="공지 1건",
        queried_operations=["search_notices"],
        result_count=1,
        citations=[GroupwareReadCitation(label="notice-001", reference="notice:notice-001")],
    )
    try:
        GroupwareReadResult.model_validate(
            {
                **valid.model_dump(mode="json"),
                "pending_approvals": [
                    {
                        "capability_id": "groupware-write-v1",
                        "summary": "send",
                        "side_effect": "WRITE_IRREVERSIBLE",
                    }
                ],
            }
        )
    except ValidationError:
        return True
    return False


def validate() -> dict[str, object]:
    info = RuntimeInfo()
    windows = json.loads(WINDOWS_EVIDENCE.read_text(encoding="utf-8"))
    deployment = GroupwareDeploymentCatalog(ROOT)
    groupware = GroupwareReadCatalog(ROOT)
    definition = AgentDefinitionCatalog(ROOT).resolve("groupware-read-agent")
    output_runtime = resolve_output_contract("GroupwareReadResult")
    fixtures = deployment.validate_fixture_directory()
    schema_properties = definition.output_schema.get("properties", {})
    actual_provider_paths = (
        ROOT / "okcanvas_agent_runtime/adapters/mcp/servers/groupware_read.py",
        ROOT / "okcanvas_agent_runtime/adapters/groupware",
    )
    checks = {
        "identity_exact": CURRENT_STEP == info.step == STEP
        and PROJECT_VERSION == info.version == VERSION,
        "step086_windows_parent_accepted": windows.get("state") == "PASSED"
        and windows.get("step") == "STEP086_GROUPWARE_READ_ONLY_VERTICAL"
        and windows.get("version") == "2.66.0"
        and windows.get("passed_checks") == windows.get("total_checks") == 14,
        "subagent_definition_internal": deployment.boundary.read_agent_definition_location
        == "runtime-internal",
        "mcp_client_declaration_internal": deployment.boundary.mcp_client_declaration_location
        == "runtime-internal",
        "actual_mcp_provider_external": deployment.boundary.mcp_provider_deployment
        == "external-connector-service",
        "actual_mcp_provider_not_in_runtime": deployment.boundary.mcp_provider_implementation_in_runtime
        is False
        and not any(path.exists() for path in actual_provider_paths),
        "organization_adapter_not_in_runtime": deployment.boundary.organization_specific_adapter_in_runtime
        is False,
        "fixture_internal_but_nonproduction": deployment.boundary.test_fixture_location
        == "runtime-internal"
        and len(fixtures) == 3
        and all(item["mutated"] is False for item in fixtures),
        "provider_contract_external_and_unimplemented": deployment.provider.provider_deployment
        == "external-connector-service"
        and deployment.provider.provider_implemented_in_runtime is False,
        "provider_identity_contract_exact": deployment.provider.required_identity_fields
        == ("tenant_id", "principal_id", "roles", "delegation_id"),
        "provider_tool_contract_exact": deployment.provider.allowed_tools
        == ("search_notices", "search_mail", "list_calendar_events")
        and all(item.mutates is False for item in deployment.provider.tools),
        "policy_client_provider_tools_aligned": groupware.policy.allowed_tools
        == groupware.server.allowed_tools
        == deployment.provider.allowed_tools,
        "read_agent_permanent": deployment.boundary.read_agent_permanently_read_only is True
        and info.groupware_read_permanently_read_only is True,
        "future_write_is_separate": deployment.boundary.write_extension_strategy
        == "separate-agent-separate-mcp-separate-credential"
        and deployment.boundary.future_write_agent_id == "groupware-action-agent"
        and deployment.boundary.future_write_mcp_server_id == "groupware-action"
        and info.groupware_action_agent_implemented is False
        and info.groupware_action_mcp_server_implemented is False,
        "subagent_runtime_bound": definition.agent_id == "groupware-read-agent"
        and definition.mcp_servers == ("groupware-read",)
        and definition.tools == ()
        and definition.hosted_tools == ()
        and definition.agent_tools == ()
        and definition.handoffs == ()
        and definition.orchestration_children == (),
        "dedicated_output_contract_bound": definition.output_contract == "GroupwareReadResult"
        and output_runtime.output_type is GroupwareReadResult
        and definition.output_schema == GroupwareReadResult.model_json_schema(),
        "output_request_and_side_effect_literal": schema_properties.get("request_class", {}).get("const")
        == "READ_SYSTEM"
        and schema_properties.get("side_effect", {}).get("const") == "READ",
        "output_has_no_action_fields": not {
            "completed_actions",
            "proposed_actions",
            "pending_approvals",
            "follow_up_state",
        }.intersection(schema_properties),
        "write_shaped_output_rejected": _write_shaped_output_rejected(),
        "nonempty_result_requires_citation": _nonempty_without_citation_rejected(),
        "overclaim_corrected": info.groupware_read_only_vertical_implemented is False
        and info.groupware_read_integration_boundary_implemented is True
        and info.groupware_read_integration_boundary_status
        == "SUBAGENT_AND_CLIENT_BOUNDARY_ONLY",
        "runtime_provider_status_exact": info.groupware_read_mcp_provider_deployment
        == "external-connector-service"
        and info.groupware_read_mcp_provider_implemented_in_runtime is False
        and info.groupware_read_mcp_provider_live_verified is False,
        "default_pack_still_fail_closed": info.groupware_read_default_state == "NOT_CONFIGURED"
        and info.groupware_read_real_endpoint_configured is False
        and info.groupware_read_secret_value_configured is False,
        "writes_and_automation_disabled": info.groupware_read_write_enabled is False
        and info.groupware_read_durable_automation_enabled is False
        and info.delegated_mcp_write_enabled is False
        and info.organization_assistant_enterprise_write_configured is False,
        "next_step_unselected": info.next_selected_step == "UNSELECTED_PENDING_USER_SELECTION",
    }
    return {
        "schema_version": "okcanvas-step086r1-groupware-boundary-validation-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "deployment": deployment.to_public_dict(),
        "agent": {
            "agent_id": definition.agent_id,
            "version": definition.version,
            "output_contract": definition.output_contract,
            "mcp_servers": list(definition.mcp_servers),
            "definition_sha256": definition.definition_sha256,
        },
        "runtime_status": {
            "integration_boundary": info.groupware_read_integration_boundary_status,
            "provider_implemented_in_runtime": info.groupware_read_mcp_provider_implemented_in_runtime,
            "provider_live_verified": info.groupware_read_mcp_provider_live_verified,
        },
    }


def _nonempty_without_citation_rejected() -> bool:
    try:
        GroupwareReadResult(
            status=GroupwareReadStatus.ANSWERED,
            answer="메일 1건",
            queried_operations=["search_mail"],
            result_count=1,
        )
    except ValidationError:
        return True
    return False


if __name__ == "__main__":
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if result["state"] == "PASSED" else 1)
