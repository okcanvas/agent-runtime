from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from okcanvas_agent_runtime.agent.mcp.definitions import MCPServerCatalog
from okcanvas_agent_runtime.application.groupware_read import GroupwareDeploymentCatalog
from okcanvas_agent_runtime.application.mcp_access import DelegatedMCPIdentity, MCPAccessCatalog
from okcanvas_agent_runtime.core.baseline import CURRENT_STEP, PROJECT_VERSION
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo

STEP = "STEP086R2_DELEGATED_ROLE_HEADER_AND_EXTERNAL_CONNECTOR_CONTRACT_CLOSURE"
VERSION = "2.66.2"
PARENT_EVIDENCE = ROOT / "docs/evidence/STEP086R1_WINDOWS_DETERMINISTIC_ACCEPTANCE.json"


def validate() -> dict[str, object]:
    info = RuntimeInfo()
    parent = json.loads(PARENT_EVIDENCE.read_text(encoding="utf-8"))
    deployment = GroupwareDeploymentCatalog(ROOT)
    definition = MCPServerCatalog(ROOT).resolve("groupware-read")
    identity = DelegatedMCPIdentity.create(
        tenant_id="tenant-a", principal_id="user-001", roles=("employee", "agent-user")
    )
    access = MCPAccessCatalog(ROOT)
    binding = access.bind_many((definition,), identity)[0]
    assert binding is not None
    headers = binding.identity_headers()
    checks = {
        "identity_exact": CURRENT_STEP == info.step == STEP and PROJECT_VERSION == info.version == VERSION,
        "step086r1_windows_parent_accepted": parent.get("state") == "PASSED"
        and parent.get("step") == "STEP086R1_GROUPWARE_SUBAGENT_AND_EXTERNAL_MCP_BOUNDARY_ALIGNMENT"
        and parent.get("version") == "2.66.1"
        and parent.get("passed_checks") == parent.get("total_checks") == 13,
        "delegated_role_header_transmitted": headers.get("X-OKCanvas-Roles") == "agent-user,employee",
        "delegation_fingerprint_retained": headers.get("X-OKCanvas-Delegation-ID") == identity.delegation_id,
        "access_policy_headers_exact": set(access.policy.delegated_headers) == {
            "X-OKCanvas-Tenant-ID", "X-OKCanvas-Principal-ID",
            "X-OKCanvas-Roles", "X-OKCanvas-Delegation-ID",
        },
        "external_connector_path_exact": deployment.boundary.external_groupware_connector_path
        == "okcanvas-connectors/groupware-mcp-server"
        and deployment.provider.external_connector_project_path
        == "okcanvas-connectors/groupware-mcp-server",
        "example_repository_optional": deployment.boundary.connector_examples_repository
        == "okcanvas-connector-examples"
        and deployment.boundary.groupware_api_fake_example_path
        == "okcanvas-connector-examples/groupware/groupware-api-fake"
        and deployment.boundary.connector_examples_required is False,
        "example_is_not_mcp": deployment.boundary.groupware_api_fake_is_mcp_server is False,
        "credential_reference_stays_internal": deployment.provider.credential_reference_transmitted is False
        and info.delegated_mcp_credential_reference_transmitted is False,
        "runtime_external_connector_status_exact": info.groupware_read_external_connector_contract_implemented
        is True
        and info.groupware_read_external_connector_local_verified is True
        and info.groupware_read_mcp_provider_live_verified is False,
        "read_only_and_future_write_separate": info.groupware_read_permanently_read_only is True
        and info.groupware_action_agent_implemented is False
        and info.groupware_action_mcp_server_implemented is False,
    }
    return {
        "schema_version": "okcanvas-step086r2-connector-contract-validation-v1",
        "step": STEP,
        "version": VERSION,
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "delegated_headers": headers,
        "deployment": deployment.to_public_dict(),
    }


if __name__ == "__main__":
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if result["state"] == "PASSED" else 1)
