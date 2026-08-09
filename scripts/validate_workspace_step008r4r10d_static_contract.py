from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_STEP = "WORKSPACE_STEP008R4R10D_RUNTIME_STEP094R2_CROSS_DOMAIN_RUN_SUBMISSION_ADMISSION_OWNER_CLOSURE"
WORKSPACE_VERSION = "0.8.4-r10d"
RUNTIME_STEP = "STEP094R2_CROSS_DOMAIN_RUN_SUBMISSION_ADMISSION_OWNER_CLOSURE"
RUNTIME_VERSION = "2.78.2"
PARENT_SHA = "4eee920fc32fc9f8fd85cd6746a4759da160ec0938000c8d41d750991f7846b2"


def _load(relative: str) -> dict[str, object]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def validate() -> dict[str, object]:
    baseline = _load("specs/workspace/current-baseline.json")
    catalog = _load("specs/workspace/project-catalog.json")
    integrations = _load("specs/workspace/integration-contracts.json")
    submission = (ROOT / "okcanvas-agent-runtime/okcanvas_agent_runtime/application/submissions/service.py").read_text(encoding="utf-8")
    gateway = (ROOT / "okcanvas-agent-runtime/okcanvas_agent_runtime/adapters/openai/generic_gateway.py").read_text(encoding="utf-8")
    binding = (ROOT / "okcanvas-agent-runtime/okcanvas_agent_runtime/bootstrap/runtime_binding.py").read_text(encoding="utf-8")
    issue = (ROOT / "docs/issues/WORKSPACE-ISSUE-054-RUN-SUBMISSION-ADMISSION-RETAINED-LEGACY-GROUPWARE-ONLY-SESSION-GUARD.md").read_text(encoding="utf-8")
    handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
    runtime = next(p for p in catalog["projects"] if p["project_id"] == "agent-runtime")
    org_contract = next(c for c in integrations["contracts"] if c["id"] == "runtime-organization-context-connector")
    gw_contract = next(c for c in integrations["contracts"] if c["id"] == "runtime-main-assistant-groupware-subagent")
    checks = {
        "workspace_identity_exact": baseline.get("workspace_step") == WORKSPACE_STEP and baseline.get("workspace_version") == WORKSPACE_VERSION,
        "runtime_identity_exact": baseline.get("runtime_step") == RUNTIME_STEP and baseline.get("runtime_version") == RUNTIME_VERSION,
        "parent_r10c_exact": baseline.get("parent_workspace_step") == "WORKSPACE_STEP008R4R10C_RUNTIME_STEP094R1_UNIFIED_CROSS_DOMAIN_SESSION_ROOT_AND_BINDING_CLOSURE" and baseline.get("source_release_sha256") == PARENT_SHA,
        "catalog_runtime_exact": runtime.get("baseline") == RUNTIME_STEP and runtime.get("version") == RUNTIME_VERSION,
        "integration_runtime_identity_exact": all(c.get("runtime_baseline") == RUNTIME_STEP and c.get("runtime_version") == RUNTIME_VERSION for c in (org_contract, gw_contract)),
        "submission_uses_unified_owner": "CrossDomainSessionDelegationCatalog" in submission and "cross_domain_binding.target_for_request(normalized)" in submission,
        "submission_legacy_groupware_owner_removed": "GroupwareSessionDelegationCatalog" not in submission and "requires_groupware_session_delegation" not in submission,
        "submission_exact_selected_mcp_only": "mcp_server_ids.append(cross_domain_target.mcp_server_id)" in submission and "cross_domain_binding.targets" not in submission,
        "gateway_same_owner": "CrossDomainSessionDelegationCatalog" in gateway and "GroupwareSessionDelegationCatalog" not in gateway,
        "runtime_binding_same_owner": "CrossDomainSessionDelegationCatalog" in binding and "GroupwareSessionDelegationCatalog" not in binding,
        "strict_binding_retained": "self._sessions.validate_binding(" in submission,
        "actual_r10c_failure_retained": all(token in issue for token in ("returncode=0", "one_request_completed=false", "run_count=0", "Root Agent must declare exactly the Groupware read Sub-agent")),
        "forbidden_nonfixes_explicit": all(token in issue for token in ("Agent aliases", "display-name", "Tool fallback", "compatibility shim", "Session-ID switching", "weakening")),
        "live_rerun_required": "LIVE_RERUN_REQUIRED" in handoff and baseline.get("promotion") == "NOT_READY",
        "runtime_product_source_changed": baseline.get("runtime_product_source_changed") is True,
        "admission_owner_sot_exact": baseline.get("cross_domain_submission_admission_owner") == "CROSS_DOMAIN_SESSION_DELEGATION_CATALOG" and baseline.get("cross_domain_submission_target_rule") == "IMMUTABLE_ROUTING_CONTEXT_SELECTS_AT_MOST_ONE_MCP_PER_TURN",
    }
    return {
        "schema_version": "okcanvas-workspace-step008r4r10d-static-contract-v1",
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "step": WORKSPACE_STEP,
        "version": WORKSPACE_VERSION,
        "runtime_step": RUNTIME_STEP,
        "runtime_version": RUNTIME_VERSION,
        "checks": checks,
        "passed_checks": sum(v is True for v in checks.values()),
        "total_checks": len(checks),
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2, sort_keys=True))
