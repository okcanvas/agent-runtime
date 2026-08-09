from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_STEP = "WORKSPACE_STEP008R4R10C_RUNTIME_STEP094R1_UNIFIED_CROSS_DOMAIN_SESSION_ROOT_AND_BINDING_CLOSURE"
WORKSPACE_VERSION = "0.8.4-r10c"
RUNTIME_STEP = "STEP094R1_UNIFIED_CROSS_DOMAIN_SESSION_ROOT_AND_BINDING_CLOSURE"
RUNTIME_VERSION = "2.78.1"
PARENT_SHA = "33851ccddfbdf2d9be56e0b95867e5edd75da44fa91953dfa8b7d8ffc5977e86"


def _load(relative: str) -> dict[str, object]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def validate() -> dict[str, object]:
    baseline = _load("specs/workspace/current-baseline.json")
    catalog = _load("specs/workspace/project-catalog.json")
    integrations = _load("specs/workspace/integration-contracts.json")
    agent_def = _load("okcanvas-agent-runtime/specs/agents/organization-assistant-session-agent/definition.json")
    org_policy = _load("okcanvas-agent-runtime/specs/organization-context/read-policy.json")
    cross_policy = _load("okcanvas-agent-runtime/specs/assistant/cross-domain-session-delegation-policy.json")
    issue = (ROOT / "docs/issues/WORKSPACE-ISSUE-053-CROSS-DOMAIN-SESSION-ROOT-AND-ROUTED-AGENT-BINDING-DIVERGED.md").read_text(encoding="utf-8")
    handoff = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
    runtime = next(p for p in catalog["projects"] if p["project_id"] == "agent-runtime")
    org_contract = next(c for c in integrations["contracts"] if c["id"] == "runtime-organization-context-connector")
    gw_contract = next(c for c in integrations["contracts"] if c["id"] == "runtime-main-assistant-groupware-subagent")
    checks = {
        "workspace_identity_exact": baseline.get("workspace_step") == WORKSPACE_STEP and baseline.get("workspace_version") == WORKSPACE_VERSION,
        "runtime_identity_exact": baseline.get("runtime_step") == RUNTIME_STEP and baseline.get("runtime_version") == RUNTIME_VERSION,
        "parent_r10b_exact": baseline.get("parent_workspace_step") == "WORKSPACE_STEP008R4R10B_POST_CLI_REQUEST_COMPLETION_AND_RUN_CARDINALITY_DIAGNOSTIC_CLOSURE" and baseline.get("source_release_sha256") == PARENT_SHA,
        "catalog_runtime_exact": runtime.get("baseline") == RUNTIME_STEP and runtime.get("version") == RUNTIME_VERSION,
        "unified_root_exact": baseline.get("cross_domain_session_root") == "organization-assistant-session-agent" and agent_def.get("version") == "1.2.0",
        "unified_children_exact": agent_def.get("agent_tools") == ["groupware-read-agent", "organization-context-read-agent"] and baseline.get("cross_domain_session_children") == ["groupware-read-agent", "organization-context-read-agent"],
        "cross_domain_policy_exact": cross_policy.get("policy_id") == "organization-assistant-cross-domain-read-session-v1" and [t.get("domain") for t in cross_policy.get("targets", [])] == ["GROUPWARE", "ORGANIZATION_CONTEXT"],
        "organization_policy_uses_unified_root": org_policy.get("root_agent_id") == "organization-assistant-session-agent",
        "organization_integration_uses_unified_root": org_contract.get("root_agent_id") == "organization-assistant-session-agent",
        "organization_integration_new_execution_path": org_contract.get("runtime_execution_path") == "sqlite-session-bounded-cross-domain-read-subagent-execution-v1",
        "groupware_integration_new_execution_path": gw_contract.get("runtime_execution_path") == "sqlite-session-bounded-cross-domain-read-subagent-execution-v1" and gw_contract.get("runtime_baseline") == RUNTIME_STEP and gw_contract.get("runtime_version") == RUNTIME_VERSION,
        "binding_fence_current": baseline.get("cross_domain_binding_fence") == "EXECUTABLE_ROUTE_SELECTED_AGENT_MUST_EQUAL_BOUND_SESSION_AGENT",
        "actual_r10b_failure_retained": all(token in issue for token in ("returncode=0", "one_request_completed=false", "run_count=0", "Session Agent or Runtime binding changed")),
        "forbidden_nonfixes_explicit": all(token in issue for token in ("switch Session IDs", "helper alias", "display-name lookup", "weaken `SessionRuntime.validate_binding()`")),
        "live_rerun_required": "FOCUSED_LIVE_RERUN_REQUIRED" in handoff and baseline.get("promotion") == "NOT_READY",
        "runtime_product_source_changed": baseline.get("runtime_product_source_changed") is True,
    }
    return {
        "schema_version": "okcanvas-workspace-step008r4r10c-static-contract-v1",
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
