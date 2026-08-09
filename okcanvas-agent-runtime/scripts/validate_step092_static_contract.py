from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent
STEP = "STEP092_SESSION_CONTEXTUAL_FOLLOW_UP_AND_STABLE_ENTITY_FOCUS"
VERSION = "2.76.0"
WORKSPACE_STEP = "WORKSPACE_STEP008R4R8_RUNTIME_STEP092_SESSION_CONTEXTUAL_FOLLOW_UP_AND_STABLE_ENTITY_FOCUS"
WORKSPACE_VERSION = "0.8.4-r8"
FOCUS_TABLE = "product_session_context_focus"


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


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
    baseline = _text("okcanvas_agent_runtime/core/baseline.py")
    policy = _json(ROOT / "specs/assistant/session-context-follow-up-policy.json")
    focus = _text("okcanvas_agent_runtime/domain/sessions/context_focus.py")
    sqlite_session = _text("okcanvas_agent_runtime/adapters/persistence/sessions/runtime_service.py")
    pg_session = _text("okcanvas_agent_runtime/adapters/persistence/postgresql/session_runtime.py")
    router = _text("okcanvas_agent_runtime/application/assistant_routing/session_context.py")
    routing_service = _text("okcanvas_agent_runtime/application/assistant_routing/service.py")
    normalizer = _text("okcanvas_agent_runtime/application/organization_context/result_normalization.py")
    execution = _text("okcanvas_agent_runtime/application/execution/service.py")
    service = _text("okcanvas_agent_runtime/application/service/use_cases.py")
    admin = _text("okcanvas_agent_runtime/application/admin/use_cases.py")
    runtime_info = _text("okcanvas_agent_runtime/core/runtime_info/foundation.py")
    historical_pg = _text("scripts/run_step091b3r1_postgresql_live_acceptance.py")
    current = _json(WORKSPACE_ROOT / "specs/workspace/current-baseline.json")

    historical_tables = _literal_assignment(historical_pg, "EXPECTED_TABLES")
    if not isinstance(historical_tables, (tuple, list, set)):
        historical_tables = ()
    historical_tables = tuple(historical_tables)

    checks = {
        "runtime_identity_exact": f'PROJECT_VERSION = "{VERSION}"' in baseline and f'CURRENT_STEP = "{STEP}"' in baseline,
        "workspace_identity_exact": current.get("workspace_step") == WORKSPACE_STEP and current.get("workspace_version") == WORKSPACE_VERSION and current.get("runtime_step") == STEP and current.get("runtime_version") == VERSION,
        "tests_deferred_and_promotion_not_ready": current.get("test_execution") == "DEFERRED_BY_USER_UNTIL_MINIO_READY" and current.get("promotion") == "NOT_READY",
        "policy_exact_and_bounded": policy.get("schema_version") == "okcanvas-session-context-follow-up-policy-v1" and policy.get("policy_id") == "session-contextual-follow-up-stable-entity-v1" and policy.get("version") == "1.0.0" and policy.get("max_candidates") == 20,
        "focus_is_strict_canonical_metadata": "SessionContextFocusObservation" in focus and "if set(value) !=" in focus and "canonical_json" in focus and "source_turn_count" in focus,
        "sqlite_focus_schema_present": f"CREATE TABLE IF NOT EXISTS {FOCUS_TABLE}" in sqlite_session and "source_turn_count INTEGER NOT NULL" in sqlite_session and "context_sha256" in sqlite_session,
        "postgresql_focus_schema_present": f"CREATE TABLE IF NOT EXISTS {FOCUS_TABLE}" in pg_session and "source_turn_count INTEGER NOT NULL" in pg_session and "context_sha256" in pg_session,
        "focus_history_key_and_recency_fenced": "self._validate_record_key(session_record)" in sqlite_session and "record.source_turn_count != session_record.turn_count" in sqlite_session and "source_turn_count=turn_count" in sqlite_session,
        "focus_commit_is_successful_turn_atomic": "if should_commit and context_focus is not None" in sqlite_session and "_commit_context_focus" in sqlite_session,
        "contextual_follow_up_uses_stable_get": "OrganizationContextPreferredOperation.GET" in router and "stable-entity-id-bound-in-immutable-read-routing-hint" in router,
        "contextual_ambiguity_is_fail_closed": "model-guessing-blocked" in router and "SessionContextResolutionStatus.AMBIGUOUS" in router,
        "tool_focus_metadata_is_json_mapping": "return observation.to_public_dict()" in normalizer and '"session_context_focus": focus' in normalizer,
        "ambiguous_public_and_focus_bounds_match": "candidates = candidates[:20]" in normalizer,
        "get_result_exact_cardinality_and_identity_fence": "len(records) != 1" in normalizer and "GET_STABLE_ENTITY_CARDINALITY_MISMATCH" in normalizer and "GET_STABLE_ENTITY_EVIDENCE_MISMATCH" in normalizer and "ROUTING_HINT_TOOL_MISMATCH" in normalizer,
        "execution_captures_and_commits_focus": 'event.event_type == "agent.tool.output.normalized"' in execution and 'payload.get("session_context_focus")' in execution and "context_focus=session_context_focus" in execution,
        "one_service_preflight_route_snapshot": service.count("decision = self._assistant_route_decision(route_request, principal)") == 1 and service.count("session_context_focus=session_context_focus") == 1,
        "one_admin_preflight_route_snapshot": admin.count("decision = self._assistant_route_decision(route_request)") == 1 and admin.count("session_context_focus=session_context_focus") == 1,
        "admin_service_org_context_wrapping_aligned": "self._assistant.organization_remote.policy.root_agent_id" in service and "self._assistant.organization_remote.policy.root_agent_id" in admin and "self._assistant.organization_remote.policy.agent_id" in service and "self._assistant.organization_remote.policy.agent_id" in admin,
        "router_contextual_precedence_present": "self._session_context_resolver.resolve" in routing_service and "session_context_focus is not None" in routing_service,
        "runtime_info_acceptance_flags_false": "organization_context_session_follow_up_deterministic_accepted: bool = False" in runtime_info and "organization_context_session_follow_up_windows_live_accepted: bool = False" in runtime_info,
        "historical_postgresql_identity_immutable": 'STEP = "STEP091B3R1_REAL_POSTGRESQL_LIVE_ACCEPTANCE_GATE"' in historical_pg and 'VERSION = "2.74.1"' in historical_pg and FOCUS_TABLE not in historical_pg,
        "historical_postgresql_table_count_15": len(historical_tables) == 15 and FOCUS_TABLE not in historical_tables,
        "current_postgresql_expected_table_count_16": len(set(historical_tables) | {FOCUS_TABLE}) == 16,
    }
    failed = [key for key, value in checks.items() if value is not True]
    return {
        "schema_version": "okcanvas-step092-static-contract-validation-v1",
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
            "windows_live_openai_executed": False,
            "step092_contextual_multi_turn_live_coverage_executed": False,
            "object_storage_live_executed": False,
        },
    }


def main() -> int:
    payload = validate()
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["state"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
