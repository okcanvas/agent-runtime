from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from okcanvas_agent_runtime.application.assistant_routing import OrganizationAssistantRoutingService
from okcanvas_agent_runtime.application.organization_context.result_normalization import (
    normalize_organization_context_nested_result,
)
from okcanvas_agent_runtime.core.contracts import OrganizationContextReadResult, OrganizationContextReadStatus
from okcanvas_agent_runtime.core.runtime_info import RuntimeInfo
from okcanvas_agent_runtime.domain.sessions import (
    SessionContextEntityRef,
    SessionContextFocusObservation,
    SessionContextFocusRecord,
    SessionContextFocusState,
)

ROOT = Path(__file__).resolve().parents[1]
ORG_CONTEXT_ENV = "OKCANVAS_ORGANIZATION_CONTEXT_READ_BEARER"


def _configured_project(tmp_path: Path) -> Path:
    project = tmp_path / "configured-project"
    shutil.copytree(ROOT / "specs", project / "specs")
    shutil.copytree(ROOT / "reference", project / "reference")
    server_path = project / "specs/mcp/servers/organization-context-read/server.json"
    payload = json.loads(server_path.read_text(encoding="utf-8"))
    payload["url_template"] = "https://connector.example.com/tenants/{tenant_id}/mcp"
    server_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return project


def _ref(entity_type: str, entity_id: str, label: str, *qualifiers: str) -> SessionContextEntityRef:
    return SessionContextEntityRef(entity_type=entity_type, entity_id=entity_id, label=label, qualifiers=tuple(qualifiers))


def _focus(state: SessionContextFocusState, candidates: tuple[SessionContextEntityRef, ...]) -> SessionContextFocusRecord:
    return SessionContextFocusRecord(
        session_id="session-step093",
        observation=SessionContextFocusObservation(
            domain="ORGANIZATION_CONTEXT", state=state, candidates=candidates, catalog_revision=500,
        ),
        source_run_id="run-step093-source", source_turn_count=1, updated_at="2026-08-08T00:00:00Z",
    )


def _route(router: OrganizationAssistantRoutingService, request: str, focus: SessionContextFocusRecord):
    return router.route(
        request=request, session_id=focus.session_id, tenant_id="tenant-a", principal_id="alice",
        roles=("agent-user",), session_context_focus=focus,
    )


def _tool_result(record: dict[str, object], *, revision: int = 501):
    payload = {
        "result_schema_version": "okcanvas-organization-context-get-entity-tool-result-v1",
        "tool_name": "get_organization_entity", "catalog_revision": revision,
        "records": [record], "changes": [],
    }
    return SimpleNamespace(new_items=[SimpleNamespace(output={"type": "text", "text": json.dumps(payload, ensure_ascii=False)})])


def test_step093_runtime_contract_declares_evidence_bound_relation_follow_up() -> None:
    info = RuntimeInfo()
    policy = json.loads((ROOT / "specs/assistant/session-context-relation-follow-up-policy.json").read_text(encoding="utf-8"))
    assert info.step == "STEP093_RELATION_AWARE_CONTEXTUAL_FOLLOW_UP_AND_EVIDENCE_BOUND_TRAVERSAL"
    assert info.version == "2.77.0"
    assert info.organization_context_relation_follow_up_implemented is True
    assert info.organization_context_relation_follow_up_source == "GET_TOOL_RELATIONSHIP_EVIDENCE"
    assert info.organization_context_relation_follow_up_completeness_required is True
    assert info.organization_context_relation_follow_up_truncated_evidence_allowed is False
    assert info.organization_context_relation_follow_up_model_inferred_relations_allowed is False
    assert info.organization_context_relation_follow_up_deterministic_accepted is False
    assert info.organization_context_relation_follow_up_windows_live_accepted is False
    assert policy["policy_id"] == "session-context-relation-follow-up-v1"
    assert policy["max_results"] == 20


def test_step093_resolved_employee_focus_routes_relation_get(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _configured_project(tmp_path)
    monkeypatch.setenv(ORG_CONTEXT_ENV, "connector-secret")
    router = OrganizationAssistantRoutingService(str(project))
    focus = _focus(SessionContextFocusState.RESOLVED, (_ref("EMPLOYEE", "employee-0017", "김민수", "플랫폼개발팀", "선임"),))
    decision = _route(router, "그 사람이 담당하는 제품은?", focus)
    assert decision.status.value == "EXECUTABLE"
    hint = decision.organization_context_request_hint
    assert hint is not None and hint.preferred_operation.value == "GET"
    assert hint.target_expression == "employee-0017"
    assert hint.relation_traversal is not None
    assert hint.relation_traversal.relation_type == "EMPLOYEE_MANAGES_PRODUCT"
    assert hint.relation_traversal.direction == "OUTBOUND"
    assert hint.relation_traversal.result_entity_types == ("PRODUCT",)
    model_request = router.build_model_request(decision, "그 사람이 담당하는 제품은?")
    assert "EMPLOYEE_MANAGES_PRODUCT" in model_request
    assert "employee-0017" in model_request
    assert "connector-secret" not in model_request


def test_step093_relation_projection_becomes_next_focus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _configured_project(tmp_path)
    monkeypatch.setenv(ORG_CONTEXT_ENV, "connector-secret")
    router = OrganizationAssistantRoutingService(str(project))
    source_focus = _focus(SessionContextFocusState.RESOLVED, (_ref("EMPLOYEE", "employee-0017", "김민수"),))
    decision = _route(router, "그 사람이 담당하는 제품은?", source_focus)
    request = router.build_model_request(decision, "그 사람이 담당하는 제품은?")
    source = {
        "entity_type": "EMPLOYEE", "entity_id": "employee-0017", "display_name": "김민수",
        "relations": [
            {"relation_type": "EMPLOYEE_MANAGES_PRODUCT", "direction": "OUTBOUND", "related_entity": {"entity_type": "PRODUCT", "entity_id": "product-016", "display_name": "제품16"}},
            {"relation_type": "EMPLOYEE_MANAGES_PRODUCT", "direction": "OUTBOUND", "related_entity": {"entity_type": "PRODUCT", "entity_id": "product-064", "display_name": "제품64"}},
            {"relation_type": "EMPLOYEE_MANAGES_CLIENT", "direction": "OUTBOUND", "related_entity": {"entity_type": "CLIENT", "entity_id": "client-0032", "display_name": "고객32"}},
        ],
        "relation_count": 3, "relations_returned_count": 3, "relations_truncated": False,
    }
    normalized = normalize_organization_context_nested_result(
        result=_tool_result(source),
        output=OrganizationContextReadResult(status=OrganizationContextReadStatus.ANSWERED, answer="제품16과 제품64를 담당합니다."),
        request=request,
    )
    focus_payload = normalized.metadata["session_context_focus"]
    assert focus_payload["state"] == "MULTIPLE"
    assert [item["entity_id"] for item in focus_payload["candidates"]] == ["product-016", "product-064"]
    assert [item.reference for item in normalized.output.citations] == ["product-016", "product-064"]
    assert normalized.metadata["relation_type"] == "EMPLOYEE_MANAGES_PRODUCT"
    assert normalized.metadata["relation_projected_count"] == 2


def test_step093_multi_product_focus_requires_selection_before_client_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _configured_project(tmp_path)
    monkeypatch.setenv(ORG_CONTEXT_ENV, "connector-secret")
    router = OrganizationAssistantRoutingService(str(project))
    focus = _focus(SessionContextFocusState.MULTIPLE, (
        _ref("PRODUCT", "product-016", "제품16"), _ref("PRODUCT", "product-064", "제품64"),
    ))
    vague = _route(router, "그 제품 고객사는?", focus)
    assert vague.status.value == "AMBIGUOUS"
    assert vague.selected_agent_id is None
    selected = _route(router, "첫 번째 제품 고객사는?", focus)
    hint = selected.organization_context_request_hint
    assert selected.status.value == "EXECUTABLE"
    assert hint is not None and hint.target_expression == "product-016"
    assert hint.relation_traversal is not None
    assert hint.relation_traversal.relation_type == "CLIENT_USES_PRODUCT"
    assert hint.relation_traversal.direction == "INBOUND"
    assert hint.relation_traversal.result_entity_types == ("CLIENT",)


def test_step093_relation_traversal_requires_complete_relationship_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _configured_project(tmp_path)
    monkeypatch.setenv(ORG_CONTEXT_ENV, "connector-secret")
    router = OrganizationAssistantRoutingService(str(project))
    focus = _focus(SessionContextFocusState.RESOLVED, (_ref("PRODUCT", "product-016", "제품16"),))
    decision = _route(router, "그 제품 고객사는?", focus)
    request = router.build_model_request(decision, "그 제품 고객사는?")
    draft = OrganizationContextReadResult(status=OrganizationContextReadStatus.ANSWERED, answer="고객 목록입니다.")
    truncated = {
        "entity_type": "PRODUCT", "entity_id": "product-016", "display_name": "제품16",
        "relations": [{"relation_type": "CLIENT_USES_PRODUCT", "direction": "INBOUND", "related_entity": {"entity_type": "CLIENT", "entity_id": "client-0001", "display_name": "고객1"}}],
        "relation_count": 2, "relations_returned_count": 1, "relations_truncated": True,
    }
    with pytest.raises(ValueError, match="refuses incomplete GET relationship evidence"):
        normalize_organization_context_nested_result(result=_tool_result(truncated), output=draft, request=request)

    malformed = dict(truncated)
    malformed.update({"relation_count": 1, "relations_returned_count": 1, "relations_truncated": False})
    malformed["relations"] = [{"relation_type": "CLIENT_USES_PRODUCT", "direction": "INBOUND", "related_entity": {"entity_type": "EMPLOYEE", "entity_id": "employee-0001", "display_name": "잘못된 대상"}}]
    with pytest.raises(ValueError, match="target type disagrees"):
        normalize_organization_context_nested_result(result=_tool_result(malformed), output=draft, request=request)


def test_step093_possessive_deictic_relation_form_routes_from_resolved_focus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _configured_project(tmp_path)
    monkeypatch.setenv(ORG_CONTEXT_ENV, "connector-secret")
    router = OrganizationAssistantRoutingService(str(project))
    focus = _focus(SessionContextFocusState.RESOLVED, (_ref("PRODUCT", "product-016", "제품16"),))
    decision = _route(router, "그 제품의 고객사는?", focus)
    hint = decision.organization_context_request_hint
    assert decision.status.value == "EXECUTABLE"
    assert hint is not None and hint.target_expression == "product-016"
    assert hint.relation_traversal is not None
    assert hint.relation_traversal.relation_type == "CLIENT_USES_PRODUCT"
    assert hint.relation_traversal.direction == "INBOUND"
