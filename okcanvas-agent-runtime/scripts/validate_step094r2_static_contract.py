from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEP = "STEP094R2_CROSS_DOMAIN_RUN_SUBMISSION_ADMISSION_OWNER_CLOSURE"
VERSION = "2.78.2"


def validate() -> dict[str, object]:
    baseline = (ROOT / "okcanvas_agent_runtime/core/baseline.py").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    submission = (ROOT / "okcanvas_agent_runtime/application/submissions/service.py").read_text(encoding="utf-8")
    gateway = (ROOT / "okcanvas_agent_runtime/adapters/openai/generic_gateway.py").read_text(encoding="utf-8")
    binding = (ROOT / "okcanvas_agent_runtime/bootstrap/runtime_binding.py").read_text(encoding="utf-8")
    cross_domain = (ROOT / "okcanvas_agent_runtime/application/assistant_routing/cross_domain_session.py").read_text(encoding="utf-8")
    definition = json.loads((ROOT / "specs/agents/organization-assistant-session-agent/definition.json").read_text(encoding="utf-8"))
    policy = json.loads((ROOT / "specs/assistant/cross-domain-session-delegation-policy.json").read_text(encoding="utf-8"))
    test_source = (ROOT / "tests/test_step094r2_cross_domain_submission_admission_owner.py").read_text(encoding="utf-8")
    checks = {
        "identity_exact": f'CURRENT_STEP = "{STEP}"' in baseline and f'PROJECT_VERSION = "{VERSION}"' in baseline and f'version = "{VERSION}"' in pyproject,
        "unified_root_exact_two_children": definition.get("agent_tools") == ["groupware-read-agent", "organization-context-read-agent"],
        "cross_domain_policy_exact_two_targets": [item.get("domain") for item in policy.get("targets", [])] == ["GROUPWARE", "ORGANIZATION_CONTEXT"],
        "submission_imports_unified_owner": "CrossDomainSessionDelegationCatalog" in submission and "CrossDomainSessionContractError" in submission,
        "submission_legacy_groupware_owner_removed": "GroupwareSessionDelegationCatalog" not in submission and "requires_groupware_session_delegation" not in submission,
        "submission_selects_target_from_immutable_request": "cross_domain_binding.target_for_request(normalized)" in submission,
        "submission_adds_only_selected_target_mcp": "mcp_server_ids.append(cross_domain_target.mcp_server_id)" in submission and "cross_domain_binding.targets" not in submission,
        "submission_keeps_legacy_org_context_root_explicit": "OrganizationContextSessionDelegationCatalog" in submission and "requires_organization_context_session_delegation(normalized)" in submission,
        "submission_session_binding_remains_strict": "self._sessions.validate_binding(" in submission and "runtime_binding.runtime_binding_sha256" in submission,
        "gateway_uses_same_unified_owner": "CrossDomainSessionDelegationCatalog" in gateway and "target_for_request(request)" in gateway and "GroupwareSessionDelegationCatalog" not in gateway,
        "runtime_binding_uses_same_unified_owner": "CrossDomainSessionDelegationCatalog" in binding and "cross_domain_session_binding.targets" in binding and "GroupwareSessionDelegationCatalog" not in binding,
        "one_domain_per_turn_fail_closed": "Exactly one delegated read domain is required per Turn" in cross_domain,
        "no_alias_or_display_name_fallback": all(token not in submission.lower() for token in ("agent alias", "display-name fallback", "label fallback")),
        "r2_regression_source_present": all(token in test_source for token in ("GroupwareSessionDelegationCatalog\" not in source", "Exactly one delegated read domain", "organization-context-read", "groupware-read")),
        "acceptance_source_present": (ROOT / "scripts/run_step094r2_acceptance.py").is_file() and (ROOT / "sh_run_step094r2_acceptance.cmd").is_file(),
    }
    return {
        "state": "PASSED" if all(checks.values()) else "FAILED",
        "step": STEP,
        "version": VERSION,
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
    }


if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2))
