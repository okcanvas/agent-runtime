from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
STEP = "STEP093R1_RELATION_ROUTE_PROTOCOL_AND_LIVE_FALSE_POSITIVE_CLOSURE"
VERSION = "2.77.1"
WORKSPACE_STEP = "WORKSPACE_STEP008R4R9B_RUNTIME_STEP093R1_RELATION_ROUTE_PROTOCOL_AND_LIVE_FALSE_POSITIVE_CLOSURE"
WORKSPACE_VERSION = "0.8.4-r9b"
FOCUS_TABLE = "product_session_context_focus"
CONNECTOR_STEP = "CONNECTOR_ORGANIZATION_CONTEXT_STEP003_RELATION_COMPLETENESS_EVIDENCE"
EXAMPLE_STEP = "EXAMPLE_ORGANIZATION_CONTEXT_STEP003_RELATION_COMPLETENESS_EVIDENCE"


def _text(base: Path, relative: str) -> str:
    return (base / relative).read_text(encoding="utf-8")


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return value


def _literal_assignment(source: str, name: str):
    module = ast.parse(source)
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return ast.literal_eval(node.value)
    raise ValueError(f"Assignment not found: {name}")


def validate() -> dict[str, object]:
    baseline = _text(ROOT, "okcanvas_agent_runtime/core/baseline.py")
    pyproject = _text(ROOT, "pyproject.toml")
    relation_policy = _json(ROOT / "specs/assistant/session-context-relation-follow-up-policy.json")
    relation_router = _text(ROOT, "okcanvas_agent_runtime/application/assistant_routing/relation_context.py")
    routing_service = _text(ROOT, "okcanvas_agent_runtime/application/assistant_routing/service.py")
    models = _text(ROOT, "okcanvas_agent_runtime/application/assistant_routing/models.py")
    normalizer = _text(ROOT, "okcanvas_agent_runtime/application/organization_context/result_normalization.py")
    runtime_info = _text(ROOT, "okcanvas_agent_runtime/core/runtime_info/foundation.py")
    historical_pg = _text(ROOT, "scripts/run_step091b3r1_postgresql_live_acceptance.py")
    current = _json(WORKSPACE_ROOT / "specs/workspace/current-baseline.json")
    catalog = _json(WORKSPACE_ROOT / "specs/workspace/project-catalog.json")
    contracts = _json(WORKSPACE_ROOT / "specs/workspace/integration-contracts.json")
    connector_root = WORKSPACE_ROOT / "okcanvas-connectors/organization-context-mcp-server"
    example_root = WORKSPACE_ROOT / "okcanvas-connector-examples/organization-context/organization-context-api-fake"
    connector_baseline = _text(connector_root, "organization_context_mcp_server/baseline.py")
    connector_service = _text(connector_root, "organization_context_mcp_server/service.py")
    connector_protocol = _text(connector_root, "organization_context_mcp_server/mcp_protocol.py")
    connector_pyproject = _text(connector_root, "pyproject.toml")
    example_resolver = _text(example_root, "src/context-resolver.ts")
    example_package = _json(example_root / "package.json")
    example_lock = _json(example_root / "package-lock.json")
    launcher = _json(ROOT / "specs/acceptance/launcher-registry.json")
    focused_live = _text(WORKSPACE_ROOT, "scripts/run_workspace_step008r4r9_relation_live_acceptance.py")
    focused_live_entrypoint = _text(WORKSPACE_ROOT, "scripts/run_workspace_step008r4r9_relation_live_entrypoint.py")
    focused_live_launcher = _text(WORKSPACE_ROOT, "sh_run_workspace_step008r4r9_relation_live_acceptance.cmd")
    rest_protocol = _text(ROOT, "okcanvas_agent_protocols/rest/admin.py")

    historical_tables = tuple(_literal_assignment(historical_pg, "EXPECTED_TABLES"))
    projects = {item["project_id"]: item for item in catalog.get("projects", []) if isinstance(item, dict) and isinstance(item.get("project_id"), str)}
    contract_map = {item["id"]: item for item in contracts.get("contracts", []) if isinstance(item, dict) and isinstance(item.get("id"), str)}
    runtime_contract = contract_map.get("runtime-organization-context-connector", {})
    connector_contract = contract_map.get("connector-organization-context-api", {})

    relation_types = {
        item.get("relation_type")
        for item in relation_policy.get("relations", [])
        if isinstance(item, dict)
    }
    checks = {
        "runtime_identity_exact": f'PROJECT_VERSION = "{VERSION}"' in baseline and f'CURRENT_STEP = "{STEP}"' in baseline,
        "runtime_pyproject_version_exact": f'version = "{VERSION}"' in pyproject,
        "workspace_identity_exact": current.get("workspace_step") == WORKSPACE_STEP and current.get("workspace_version") == WORKSPACE_VERSION and current.get("runtime_step") == STEP and current.get("runtime_version") == VERSION,
        "tests_deferred_and_promotion_not_ready": current.get("test_execution") == "USER_RELATION_LIVE_EXPOSED_PROTOCOL_500_AND_FALSE_POSITIVE_HARNESS_R9B_CORRECTION_APPLIED" and current.get("promotion") == "NOT_READY",
        "relation_policy_exact_and_bounded": relation_policy.get("schema_version") == "okcanvas-session-context-relation-follow-up-policy-v1" and relation_policy.get("policy_id") == "session-context-relation-follow-up-v1" and relation_policy.get("version") == "1.0.0" and relation_policy.get("max_results") == 20 and len(relation_policy.get("relations", [])) == 10,
        "relation_policy_uses_only_published_relation_types": relation_types == {"EMPLOYEE_BELONGS_TO_DEPARTMENT", "EMPLOYEE_REPORTS_TO_EMPLOYEE", "PRODUCT_OWNED_BY_DEPARTMENT", "EMPLOYEE_MANAGES_PRODUCT", "EMPLOYEE_MANAGES_CLIENT", "CLIENT_USES_PRODUCT", "PROJECT_FOR_CLIENT", "EMPLOYEE_MANAGES_PROJECT"},
        "relation_router_has_exact_allowlists": all(token in relation_router for token in ("_ALLOWED_RELATIONS", "_ALLOWED_REVERSE_RELATIONS", "model-guessing-blocked", "selection-bounded-to-prior-tool-evidence", "relation-source-stable-id-bound-in-immutable-routing-hint")),
        "relation_hint_is_typed_and_nested": "OrganizationContextRelationTraversalHint" in models and '"okcanvas-organization-context-relation-traversal-hint-v1"' in models and 'payload["relation_traversal"]' in models,
        "relation_rest_response_is_typed_and_nested": "OrganizationContextRelationTraversalHintResponse" in rest_protocol and "relation_traversal: OrganizationContextRelationTraversalHintResponse | None = None" in rest_protocol,
        "focused_live_exception_cannot_flip_to_passed": '"harness_execution_completed_without_exception": False' in focused_live and 'payload.get("state") == "PASSED" and all(checks.values())' in focused_live,
        "relation_model_context_rules_fail_closed": all(token in routing_service for token in ("source_stable_id_must_be_used_for_get", "relationship_evidence_must_be_complete", "truncated_relationship_evidence_must_fail_closed", "do_not_infer_inverse_or_unlisted_relations")),
        "normalizer_requires_exact_source_and_completeness": all(token in normalizer for token in ("GET_STABLE_ENTITY_CARDINALITY_MISMATCH", "GET_STABLE_ENTITY_EVIDENCE_MISMATCH", "RELATION_COMPLETENESS_EVIDENCE_MISSING", "RELATION_EVIDENCE_TRUNCATED", "RELATION_TARGET_TYPE_MISMATCH", "RELATION_RESULT_BOUND_EXCEEDED")),
        "relation_projection_drives_next_focus": "focus_records = _relation_projected_records" in normalizer and 'strategy = "tool-evidence-relation-projection-v1"' in normalizer and '"relation_projected_count"' in normalizer,
        "connector_identity_exact": f'CURRENT_STEP = "{CONNECTOR_STEP}"' in connector_baseline and 'PROJECT_VERSION = "0.3.0"' in connector_baseline and 'version = "0.3.0"' in connector_pyproject,
        "connector_rejects_invalid_relation_completeness": "ORGANIZATION_CONTEXT_RELATION_COMPLETENESS_INVALID" in connector_service and "relations_returned_count" in connector_service and "relations_truncated" in connector_service,
        "connector_get_tool_documents_completeness": "including explicit relationship completeness metadata" in connector_protocol,
        "example_identity_exact": example_package.get("version") == "0.3.0" and example_lock.get("version") == "0.3.0" and (example_lock.get("packages") or {}).get("", {}).get("version") == "0.3.0" and projects.get("organization-context-api-fake-example", {}).get("baseline") == EXAMPLE_STEP,
        "example_publishes_relation_completeness": all(token in example_resolver for token in ("allRelations.slice(0, 100)", "relation_count: allRelations.length", "relations_returned_count: boundedRelations.length", "relations_truncated: allRelations.length > boundedRelations.length")),
        "workspace_catalog_current_projects_exact": catalog.get("workspace_step") == WORKSPACE_STEP and catalog.get("workspace_version") == WORKSPACE_VERSION and projects.get("agent-runtime", {}).get("baseline") == STEP and projects.get("agent-runtime", {}).get("version") == VERSION and projects.get("organization-context-mcp-connector", {}).get("baseline") == CONNECTOR_STEP and projects.get("organization-context-mcp-connector", {}).get("version") == "0.3.0",
        "workspace_relation_contract_exact": runtime_contract.get("runtime_baseline") == STEP and runtime_contract.get("runtime_version") == VERSION and runtime_contract.get("session_context_relation_follow_up_implemented") is True and runtime_contract.get("relation_completeness_required") is True and runtime_contract.get("relation_truncated_evidence_allowed") is False and runtime_contract.get("model_inferred_relations_allowed") is False,
        "connector_relation_contract_exact": connector_contract.get("get_entity_relation_completeness_metadata") is True and connector_contract.get("get_entity_relation_count_field") == "relation_count" and connector_contract.get("get_entity_relations_returned_count_field") == "relations_returned_count" and connector_contract.get("get_entity_relations_truncated_field") == "relations_truncated",
        "launcher_registry_current_step093_exact": launcher.get("current_step") == STEP and launcher.get("current_step_token") == "093" and sum(1 for item in launcher.get("records", []) if isinstance(item, dict) and item.get("classification") == "CURRENT") == 2,
        "runtime_info_acceptance_flags_false": "organization_context_relation_follow_up_deterministic_accepted: bool = False" in runtime_info and "organization_context_relation_follow_up_windows_live_accepted: bool = False" in runtime_info,
        "focused_relation_live_source_prepared_not_executed": all(token in focused_live for token in ("김선임 연락처", "그 사람이 담당하는 제품은?", "첫 번째 제품 고객사는?", "EMPLOYEE_MANAGES_PRODUCT", "CLIENT_USES_PRODUCT", "relation_projection_focus_chain_exact", "WINDOWS_LIVE_OPENAI_ORGANIZATION_CONTEXT_RELATION_CHAIN_E2E")) and "OKCANVAS_WORKSPACE_STEP008R4R9_RELATION_LIVE_ACCEPTANCE" in focused_live_entrypoint and "run_workspace_step008r4r9_relation_live_acceptance.py" in focused_live_entrypoint,
        "focused_relation_live_launcher_canonical_lf": "run_workspace_step008r4r9_relation_live_entrypoint.py" in focused_live_launcher and "\r" not in focused_live_launcher,
        "historical_postgresql_identity_and_15_tables_immutable": 'STEP = "STEP091B3R1_REAL_POSTGRESQL_LIVE_ACCEPTANCE_GATE"' in historical_pg and 'VERSION = "2.74.1"' in historical_pg and len(historical_tables) == 15 and FOCUS_TABLE not in historical_tables,
        "current_postgresql_table_count_still_16": len(set(historical_tables) | {FOCUS_TABLE}) == 16,
        "step093_adds_no_new_database_table": "CREATE TABLE" not in relation_router and "CREATE TABLE" not in normalizer,
    }
    failed = [key for key, value in checks.items() if value is not True]
    return {
        "schema_version": "okcanvas-step093r1-static-contract-validation-v1",
        "step": STEP,
        "version": VERSION,
        "validation_mode": "STATIC_SOURCE_AND_CONTRACT_ONLY_NO_TEST_EXECUTION",
        "state": "PASSED" if not failed else "FAILED",
        "checks": checks,
        "passed_checks": sum(value is True for value in checks.values()),
        "total_checks": len(checks),
        "failed_checks": failed,
        "historical_postgresql_expected_table_count": len(historical_tables),
        "current_postgresql_expected_table_count": len(set(historical_tables) | {FOCUS_TABLE}),
        "limitations": {
            "unit_tests_executed": False,
            "deterministic_acceptance_executed": False,
            "connector_acceptance_executed": False,
            "example_acceptance_executed": False,
            "windows_live_openai_executed": False,
            "step093_relation_multi_turn_live_executed": False,
            "object_storage_live_executed": False,
        },
    }


def main() -> int:
    payload = validate()
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
