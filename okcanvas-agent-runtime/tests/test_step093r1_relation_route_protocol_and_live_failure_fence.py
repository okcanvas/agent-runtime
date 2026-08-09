from __future__ import annotations

from pathlib import Path

from okcanvas_agent_protocols.rest.admin import AssistantRouteResponse


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ROOT.parent


def test_step093r1_rest_route_protocol_accepts_typed_relation_traversal() -> None:
    response = AssistantRouteResponse(
        request_class="SEARCH_KNOWLEDGE",
        side_effect="READ",
        status="EXECUTABLE",
        selected_agent_definition_id="organization-context-session-agent",
        executable_now=True,
        required_capabilities=[],
        matched_rule_id="organization-context-short-read-session-stateless-subagent-v1",
        reasons=["relation-aware-session-follow-up"],
        policy_id="assistant-routing-v1",
        policy_version="1.0.0",
        policy_sha256="0" * 64,
        grounding_state="NOT_APPLICABLE",
        grounding_catalog_id=None,
        grounding_catalog_version=None,
        grounding_effective_at=None,
        grounding=[],
        organization_context_request_hint={
            "pattern_id": "session-context-relation-follow-up-v1",
            "intent": "RELATION_LOOKUP",
            "target_expression": "employee-0017",
            "entity_type_hints": ["EMPLOYEE"],
            "requested_fields": [],
            "preferred_operation": "GET",
            "relation_traversal": {
                "schema_version": "okcanvas-organization-context-relation-traversal-hint-v1",
                "source_entity_type": "EMPLOYEE",
                "source_entity_id": "employee-0017",
                "relation_type": "EMPLOYEE_MANAGES_PRODUCT",
                "direction": "OUTBOUND",
                "result_entity_types": ["PRODUCT"],
                "max_results": 20,
            },
        },
    )
    assert response.organization_context_request_hint is not None
    assert response.organization_context_request_hint.relation_traversal is not None
    assert response.organization_context_request_hint.relation_traversal.source_entity_id == "employee-0017"


def test_step093r1_live_harness_exception_path_has_explicit_false_fence() -> None:
    source = (WORKSPACE_ROOT / "scripts/run_workspace_step008r4r9_relation_live_acceptance.py").read_text(
        encoding="utf-8"
    )
    assert '"harness_execution_completed_without_exception": True' in source
    assert '"harness_execution_completed_without_exception": False' in source
    assert 'payload.get("state") == "PASSED" and all(checks.values())' in source
