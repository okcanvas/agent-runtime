from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
STEP = "STEP094_CROSS_DOMAIN_STABLE_FOCUS_AND_GROUPWARE_CONTEXT_FILTER"
VERSION = "2.78.0"
WORKSPACE_STEP = "WORKSPACE_STEP008R4R10_RUNTIME_STEP094_CROSS_DOMAIN_STABLE_FOCUS_AND_GROUPWARE_CONTEXT_FILTER"
WORKSPACE_VERSION = "0.8.4-r10"
GROUPWARE_CONNECTOR_STEP = "CONNECTOR_STEP002_STABLE_ORGANIZATION_CONTEXT_REFERENCE_FILTER"
GROUPWARE_EXAMPLE_STEP = "EXAMPLE_STEP002_GROUPWARE_STABLE_CONTEXT_REFERENCE_FIXTURE"


def _text(base: Path, relative: str) -> str:
    return (base / relative).read_text(encoding="utf-8")


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def validate() -> dict[str, object]:
    current = _json(WORKSPACE_ROOT / "specs/workspace/current-baseline.json")
    catalog = _json(WORKSPACE_ROOT / "specs/workspace/project-catalog.json")
    contracts = _json(WORKSPACE_ROOT / "specs/workspace/integration-contracts.json")
    policy = _json(ROOT / "specs/assistant/session-cross-domain-groupware-policy.json")
    provider = _json(ROOT / "specs/groupware/read-provider-contract.json")
    launcher = _json(ROOT / "specs/acceptance/launcher-registry.json")

    baseline = _text(ROOT, "okcanvas_agent_runtime/core/baseline.py")
    pyproject = _text(ROOT, "pyproject.toml")
    models = _text(ROOT, "okcanvas_agent_runtime/application/assistant_routing/models.py")
    resolver = _text(ROOT, "okcanvas_agent_runtime/application/assistant_routing/cross_domain_context.py")
    routing = _text(ROOT, "okcanvas_agent_runtime/application/assistant_routing/service.py")
    request_exec = _text(ROOT, "okcanvas_agent_runtime/application/groupware_read/request_execution.py")
    normalizer = _text(ROOT, "okcanvas_agent_runtime/application/groupware_read/result_normalization.py")
    gateway = _text(ROOT, "okcanvas_agent_runtime/adapters/openai/generic_gateway.py")
    runtime_info = _text(ROOT, "okcanvas_agent_runtime/core/runtime_info/foundation.py")
    rest = _text(ROOT, "okcanvas_agent_protocols/rest/admin.py")
    connector_root = WORKSPACE_ROOT / "okcanvas-connectors/groupware-mcp-server"
    connector_baseline = _text(connector_root, "groupware_mcp_server/baseline.py")
    connector_contracts = _text(connector_root, "groupware_mcp_server/contracts.py")
    connector_service = _text(connector_root, "groupware_mcp_server/service.py")
    connector_client = _text(connector_root, "groupware_mcp_server/groupware_client.py")
    connector_protocol = _text(connector_root, "groupware_mcp_server/mcp_protocol.py")
    connector_provider = _json(connector_root / "contracts/runtime-provider-contract.json")
    connector_pyproject = _text(connector_root, "pyproject.toml")
    example_root = WORKSPACE_ROOT / "okcanvas-connector-examples/groupware/groupware-api-fake"
    example_package = _json(example_root / "package.json")
    example_lock = _json(example_root / "package-lock.json")
    example_server = _text(example_root, "src/server.ts")
    example_state = _text(example_root, "src/state.ts")
    example_types = _text(example_root, "src/types.ts")

    projects = {
        item.get("project_id"): item
        for item in catalog.get("projects", [])
        if isinstance(item, dict) and isinstance(item.get("project_id"), str)
    }
    contract_map = {
        item.get("id"): item
        for item in contracts.get("contracts", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    runtime_groupware = contract_map.get("runtime-groupware-connector", {})
    connector_groupware = contract_map.get("connector-groupware-api", {})

    current_records = [
        item for item in launcher.get("records", [])
        if isinstance(item, dict) and item.get("classification") == "CURRENT"
    ]
    checks = {
        "runtime_identity_exact": f'PROJECT_VERSION = "{VERSION}"' in baseline and f'CURRENT_STEP = "{STEP}"' in baseline,
        "runtime_pyproject_version_exact": f'version = "{VERSION}"' in pyproject,
        "workspace_identity_exact": current.get("workspace_step") == WORKSPACE_STEP and current.get("workspace_version") == WORKSPACE_VERSION and current.get("runtime_step") == STEP and current.get("runtime_version") == VERSION,
        "promotion_not_ready_and_tests_deferred": current.get("promotion") == "NOT_READY" and current.get("test_execution") == "DEFERRED_BY_USER_MINIO_HOLD_STATIC_ONLY",
        "cross_domain_policy_exact": policy.get("schema_version") == "okcanvas-session-cross-domain-groupware-policy-v1" and policy.get("policy_id") == "session-cross-domain-groupware-v1" and policy.get("version") == "1.0.0" and policy.get("max_results") == 20,
        "cross_domain_policy_fail_closed": policy.get("multiple_focus_must_not_guess") is True and policy.get("preserve_anchor_only_after_exact_tool_filter_evidence") is True,
        "cross_domain_policy_resource_tools_exact": {item.get("tool_name") for item in policy.get("resource_rules", []) if isinstance(item, dict)} == {"search_notices", "search_mail", "list_calendar_events"},
        "cross_domain_policy_source_types_exact": set(policy.get("allowed_source_entity_types", [])) == {"EMPLOYEE", "PROJECT", "CLIENT", "PRODUCT", "DEPARTMENT"},
        "stable_context_filter_model_typed": "class GroupwareContextFilterHint" in models and '"okcanvas-groupware-context-filter-hint-v1"' in models and "groupware_context_filter" in models,
        "stable_context_filter_rest_typed": "class GroupwareContextFilterHintResponse" in rest and "groupware_context_filter: GroupwareContextFilterHintResponse | None = None" in rest,
        "router_requires_resolved_stable_focus": "SessionContextFocusState.RESOLVED" in resolver and "cross-domain-focus-must-not-guess" in resolver and "stable-organization-context-focus-bound" in resolver,
        "router_never_label_fallbacks": "exact-groupware-context-ref-required" in resolver and "do_not_fallback_to_label_search" in routing,
        "model_request_binds_exact_context_ref": all(token in routing for token in ("exact_tool_name_required", "exact_entity_type_and_id_must_be_forwarded", "tool_result_must_confirm_applied_filter", "returned_records_must_carry_exact_context_ref")),
        "model_request_forbids_contextual_narrowing": all(token in routing for token in ("canonical_context_filter_arguments_only", "search_query_must_be_empty", "calendar_time_range_must_be_omitted", "limit_must_equal")),
        "named_tool_choice_is_allowlisted": "groupware_named_tool_choice" in request_exec and "_ALLOWED_TOOLS" in request_exec and "groupware_named_tool_choice(request)" in gateway,
        "nested_result_requires_single_tool": "GROUPWARE_CONTEXT_FILTER_TOOL_RESULT_CARDINALITY_MISMATCH" in normalizer and "len(observed) != 1" in normalizer,
        "nested_result_requires_exact_applied_ref": "GROUPWARE_CONTEXT_FILTER_NOT_APPLIED" in normalizer and 'applied != expected_ref' in normalizer,
        "nested_result_requires_record_refs": "GROUPWARE_CONTEXT_FILTER_EVIDENCE_MISMATCH" in normalizer and "_record_has_context_ref" in normalizer,
        "anchor_preserved_only_after_evidence": '"session_context_focus":focus.to_public_dict()' in normalizer and '"context_filter_applied":True' in normalizer,
        "runtime_info_declares_unaccepted_current_feature": all(token in runtime_info for token in ("cross_domain_groupware_stable_focus_implemented: bool = True", "cross_domain_groupware_context_filter_authorization_additive_only: bool = True", "cross_domain_groupware_tool_evidence_revalidated: bool = True", "cross_domain_groupware_label_fallback_allowed: bool = False", "cross_domain_groupware_deterministic_accepted: bool = False", "cross_domain_groupware_windows_live_accepted: bool = False")),
        "provider_contract_v3_exact": provider.get("schema_version") == "okcanvas-groupware-read-provider-contract-v3" and connector_provider.get("schema_version") == "okcanvas-groupware-read-provider-contract-v3",
        "connector_context_ref_contract_strict": "class ContextRef" in connector_contracts and "extra=\"forbid\"" in connector_contracts and "context_ref" in connector_protocol,
        "connector_context_search_arguments_canonical": "context_ref search requires empty query and limit 20" in connector_contracts and "self.query != \"\" or self.limit != 20" in connector_contracts,
        "connector_context_calendar_arguments_canonical": "context_ref calendar lookup requires no time range and limit 20" in connector_contracts and "self.start_at is not None or self.end_at is not None or self.limit != 20" in connector_contracts,
        "connector_echoes_applied_context_ref": "context_ref=context_ref" in connector_service and "context_ref=parsed.context_ref.model_dump" in connector_service,
        "connector_forwards_calendar_context_ref": '"context_ref": context_ref' in connector_client and "list_calendar_events" in connector_client,
        "connector_identity_exact": f'CURRENT_STEP = "{GROUPWARE_CONNECTOR_STEP}"' in connector_baseline and 'PROJECT_VERSION = "0.2.0"' in connector_baseline and 'version = "0.2.0"' in connector_pyproject,
        "example_identity_exact": example_package.get("version") == "0.2.0" and example_lock.get("version") == "0.2.0" and (example_lock.get("packages") or {}).get("", {}).get("version") == "0.2.0",
        "example_records_publish_stable_refs": "context_refs" in example_types and "employee-0017" in example_state and "project-001" in example_state,
        "example_filter_is_additive_after_auth": "requireProductIdentity(request, response)" in example_server and "matchesContextRef" in example_server and "owner_principal_id === principal" in example_server and "visible_to_roles.some" in example_server,
        "example_rejects_malformed_context_ref": 'context_ref is invalid' in example_server and "CONTEXT_ENTITY_TYPES" in example_server,
        "workspace_catalog_current_exact": catalog.get("workspace_step") == WORKSPACE_STEP and catalog.get("workspace_version") == WORKSPACE_VERSION and projects.get("agent-runtime", {}).get("baseline") == STEP and projects.get("agent-runtime", {}).get("version") == VERSION and projects.get("groupware-mcp-connector", {}).get("baseline") == GROUPWARE_CONNECTOR_STEP and projects.get("groupware-mcp-connector", {}).get("version") == "0.2.0" and projects.get("groupware-api-fake-example", {}).get("baseline") == GROUPWARE_EXAMPLE_STEP and projects.get("groupware-api-fake-example", {}).get("version") == "0.2.0",
        "workspace_runtime_groupware_contract_exact": runtime_groupware.get("stable_context_ref_filter_implemented") is True and runtime_groupware.get("authorization_additive_only") is True and runtime_groupware.get("tool_result_context_ref_revalidated") is True and runtime_groupware.get("label_fallback_allowed") is False,
        "workspace_connector_groupware_contract_exact": connector_groupware.get("stable_context_ref_filter_implemented") is True and connector_groupware.get("authorization_additive_only") is True and connector_groupware.get("context_ref_field") == "context_ref",
        "launcher_registry_current_step094_exact": launcher.get("current_step") == STEP and launcher.get("current_step_token") == "094" and len(current_records) == 2 and {item.get("path") for item in current_records} == {"scripts/run_step094_acceptance.py", "sh_run_step094_acceptance.cmd"},
        "focused_test_source_prepared": (ROOT / "tests/test_step094_cross_domain_stable_focus_and_groupware_context_filter.py").is_file(),
        "focused_cross_domain_live_source_prepared": (WORKSPACE_ROOT / "scripts/run_workspace_step008r4r10_cross_domain_live_acceptance.py").is_file() and (WORKSPACE_ROOT / "scripts/run_workspace_step008r4r10_cross_domain_live_entrypoint.py").is_file() and (WORKSPACE_ROOT / "sh_run_workspace_step008r4r10_cross_domain_live_acceptance.cmd").is_file(),
        "focused_cross_domain_live_evidence_is_privacy_bounded": "normalized_citations" not in _text(WORKSPACE_ROOT, "scripts/run_workspace_step008r4r10_cross_domain_live_acceptance.py") and "context_filtered_record_count" in _text(WORKSPACE_ROOT, "scripts/run_workspace_step008r4r10_cross_domain_live_acceptance.py"),
        "cross_domain_adds_no_database_table": "CREATE TABLE" not in resolver and "CREATE TABLE" not in normalizer,
    }
    failed = [name for name, passed in checks.items() if passed is not True]
    return {
        "schema_version": "okcanvas-step094-static-contract-validation-v1",
        "step": STEP,
        "version": VERSION,
        "workspace_step": WORKSPACE_STEP,
        "workspace_version": WORKSPACE_VERSION,
        "validation_mode": "STATIC_SOURCE_AND_CONTRACT_ONLY_NO_TEST_EXECUTION",
        "state": "PASSED" if not failed else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "failed_checks": failed,
        "limitations": {
            "unit_tests_executed": False,
            "runtime_deterministic_acceptance_executed": False,
            "groupware_connector_acceptance_executed": False,
            "groupware_example_acceptance_executed": False,
            "windows_live_openai_executed": False,
            "cross_domain_multi_turn_live_executed": False,
            "object_storage_live_executed": False,
        },
    }


def main() -> int:
    payload = validate()
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
