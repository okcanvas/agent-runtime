from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.application.assistant_routing import OrganizationAssistantRoutingService
from okcanvas_agent_runtime.application.groupware_read import GroupwareReadCatalog, GroupwareReadState
from okcanvas_agent_runtime.application.mcp_access import DelegatedMCPIdentity, MCPAccessCatalog
from okcanvas_agent_runtime.bootstrap.runtime_binding import AgentRuntimeBindingCatalog
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

STEP = "STEP086_GROUPWARE_READ_ONLY_VERTICAL"
VERSION = "2.66.0"
GROUPWARE_ENV = "OKCANVAS_GROUPWARE_READ_BEARER"
WINDOWS_EVIDENCE = ROOT / "docs/evidence/STEP085_WINDOWS_DETERMINISTIC_ACCEPTANCE.json"


def _configured_project() -> Path:
    root = Path(tempfile.mkdtemp(prefix="okcanvas-step086-groupware-"))
    shutil.copytree(ROOT / "specs", root / "specs")
    shutil.copytree(ROOT / "reference", root / "reference")
    server_path = root / "specs/mcp/servers/groupware-read/server.json"
    payload = json.loads(server_path.read_text(encoding="utf-8"))
    payload["url_template"] = "https://groupware.example.com/tenants/{tenant_id}/mcp"
    server_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return root


def _identity(*roles: str) -> DelegatedMCPIdentity:
    return DelegatedMCPIdentity.create(
        tenant_id="tenant-a",
        principal_id="alice",
        roles=roles,
    )


def validate() -> dict[str, object]:
    info = RuntimeInfo()
    windows = json.loads(WINDOWS_EVIDENCE.read_text(encoding="utf-8"))
    default_catalog = GroupwareReadCatalog(ROOT)
    default_identity = _identity("agent-user")
    default_readiness = default_catalog.readiness(default_identity)
    definition = AgentDefinitionCatalog(ROOT).resolve("groupware-read-agent")
    binding = AgentRuntimeBindingCatalog(ROOT).resolve(definition)
    access_public = MCPAccessCatalog(ROOT).to_public_dict()

    configured_root = _configured_project()
    previous = os.environ.get(GROUPWARE_ENV)
    try:
        os.environ[GROUPWARE_ENV] = "step086-validator-secret-value"
        configured_catalog = GroupwareReadCatalog(configured_root)
        configured_readiness = configured_catalog.readiness(default_identity)
        denied_readiness = configured_catalog.readiness(_identity("approval-operator"))
        router = OrganizationAssistantRoutingService(str(configured_root))
        configured_route = router.route(
            request="이번 주 그룹웨어 일정을 보여줘.",
            tenant_id="tenant-a",
            principal_id="alice",
            roles=("agent-user",),
        )
        model_request = router.build_model_request(configured_route, "이번 주 그룹웨어 일정을 보여줘.")
    finally:
        if previous is None:
            os.environ.pop(GROUPWARE_ENV, None)
        else:
            os.environ[GROUPWARE_ENV] = previous
        shutil.rmtree(configured_root, ignore_errors=True)

    default_router = OrganizationAssistantRoutingService(str(ROOT))
    default_route = default_router.route(
        request="최근 그룹웨어 공지 목록을 보여줘.",
        tenant_id="tenant-a",
        principal_id="alice",
        roles=("agent-user",),
    )
    write_route = default_router.route(
        request="이 메일을 발송해줘.",
        tenant_id="tenant-a",
        principal_id="alice",
        roles=("agent-user",),
    )
    draft_route = default_router.route(
        request="프로젝트 지연 안내 메일 초안을 작성해줘.",
        tenant_id="tenant-a",
        principal_id="alice",
        roles=("agent-user",),
    )

    public_repr = repr(default_catalog.to_public_dict(default_identity)) + repr(access_public)
    model_lower = model_request.casefold()
    checks = {
        "identity_exact": CURRENT_STEP == info.step == STEP and PROJECT_VERSION == info.version == VERSION,
        "step085_windows_evidence_exact": windows.get("state") == "PASSED"
        and windows.get("step") == "STEP085_MULTI_MCP_AND_DELEGATED_IDENTITY_FOUNDATION"
        and windows.get("version") == "2.65.0"
        and windows.get("passed_checks") == windows.get("total_checks") == 12,
        "policy_schema_exact": default_catalog.policy.policy_id == "groupware-read-v1"
        and default_catalog.policy.version == "1.0.0",
        "policy_binding_exact": default_catalog.policy.capability_id == "groupware-read-v1"
        and default_catalog.policy.agent_id == "groupware-read-agent"
        and default_catalog.policy.server_id == "groupware-read",
        "read_tool_allowlist_exact": default_catalog.policy.allowed_tools
        == ("search_notices", "search_mail", "list_calendar_events"),
        "result_bound_exact": default_catalog.policy.max_results == 50,
        "mcp_v3_delegated_read_only_exact": default_catalog.server.schema_version == "okcanvas-mcp-server-v3"
        and default_catalog.server.read_only is True
        and default_catalog.server.requires_delegated_identity is True
        and default_catalog.server.endpoint_mode == "tenant-template",
        "mcp_no_retry_passive_circuit_exact": default_catalog.server.max_retry_attempts == 0
        and default_catalog.server.health_mode == "passive"
        and default_catalog.server.circuit_breaker_failure_threshold == 2,
        "role_gate_exact": default_catalog.policy.required_roles == ("agent-user",)
        and default_catalog.server.required_roles == ("agent-user",),
        "default_endpoint_is_non_routable": default_catalog.server.url_template
        == "https://groupware.example.invalid/tenants/{tenant_id}/mcp",
        "default_secret_value_absent": default_readiness.credential_value_configured is False,
        "default_state_fails_closed": default_readiness.state is GroupwareReadState.NOT_CONFIGURED
        and default_readiness.executable_now is False,
        "credential_reference_metadata_only": default_readiness.credential_reference_configured is True
        and default_catalog.server.credential_ref == "groupware-read-credential"
        and access_public.get("credential_values_exposed") is False,
        "secret_not_exposed_publicly": "step086-validator-secret-value" not in public_repr,
        "agent_has_no_non_mcp_execution_surfaces": definition.tools == ()
        and definition.hosted_tools == ()
        and definition.agent_tools == ()
        and definition.handoffs == ()
        and definition.orchestration_children == ()
        and definition.skills == ()
        and definition.session_mode == "disabled"
        and definition.workspace_access == "none",
        "agent_single_groupware_mcp_exact": definition.mcp_servers == ("groupware-read",),
        "runtime_binding_reuses_step085_path": binding.execution_path
        == "multi-remote-mcp-delegated-identity-execution-v1"
        and len(binding.mcp_servers) == 1,
        "configured_fixture_becomes_ready": configured_readiness.state is GroupwareReadState.READY
        and configured_readiness.executable_now is True,
        "configured_identity_is_bound": configured_readiness.identity_bound is True
        and configured_readiness.role_allowed is True,
        "unallowed_role_is_denied": denied_readiness.state is GroupwareReadState.ACCESS_DENIED
        and denied_readiness.executable_now is False,
        "default_groupware_route_is_not_configured": default_route.request_class == "READ_SYSTEM"
        and default_route.status.value == "NOT_CONFIGURED"
        and default_route.selected_agent_id is None,
        "configured_groupware_route_selects_agent": configured_route.status.value == "EXECUTABLE"
        and configured_route.selected_agent_id == "groupware-read-agent",
        "write_request_remains_proposal_only": write_route.request_class == "WRITE_ACTION"
        and write_route.status.value == "PROPOSAL_ONLY",
        "draft_request_not_stolen": draft_route.request_class == "WRITE_CONTENT"
        and draft_route.status.value == "EXECUTABLE",
        "model_context_bounded": '"groupware_read_policy"' in model_request
        and '"max_results": 50' in model_request
        and '"write_enabled": false' in model_lower,
        "model_context_has_no_endpoint_reference_or_secret": "groupware.example.com" not in model_request
        and "groupware-read-credential" not in model_request
        and "step086-validator-secret-value" not in model_request,
        "runtime_info_limits_exact": info.groupware_read_only_vertical_implemented is True
        and info.groupware_read_allowed_tool_count == 3
        and info.groupware_read_default_state == "NOT_CONFIGURED"
        and info.groupware_read_real_endpoint_configured is False
        and info.groupware_read_secret_value_configured is False,
        "writes_and_automation_remain_disabled": info.groupware_read_write_enabled is False
        and info.groupware_read_durable_automation_enabled is False
        and info.delegated_mcp_write_enabled is False
        and info.organization_assistant_enterprise_write_configured is False
        and info.organization_assistant_durable_automation_configured is False,
        "advanced_tool_calling_remains_disabled": info.organization_assistant_tool_search_runtime_enabled is False
        and info.organization_assistant_programmatic_tool_calling_runtime_enabled is False,
        "next_step_unselected": info.next_selected_step == "UNSELECTED_PENDING_USER_SELECTION",
    }
    return {
        "schema_version": "okcanvas-step086-groupware-read-only-validation-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "default_groupware": default_catalog.to_public_dict(default_identity),
        "configured_readiness": configured_readiness.to_public_dict(),
        "denied_readiness": denied_readiness.to_public_dict(),
        "configured_route": configured_route.to_public_dict(),
        "runtime_binding": {
            "execution_path": binding.execution_path,
            "mcp_server_count": len(binding.mcp_servers),
            "runtime_binding_sha256": binding.runtime_binding_sha256,
        },
    }


if __name__ == "__main__":
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if result["state"] == "PASSED" else 1)
